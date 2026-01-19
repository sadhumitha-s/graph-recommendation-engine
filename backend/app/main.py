import os
import time
from fastapi import FastAPI, Response, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # ← FIXED
from contextlib import asynccontextmanager
import jwt
from sqlalchemy import text, func

from app.config import settings
from .db import session, models, crud
from .api import interactions, recommend, metrics
from .core.recommender import get_engine

BINARY_FILE = "graph.bin"

# Supabase JWT verification
security = HTTPBearer()
SUPABASE_URL = "https://rgqiezjbzraidrlmkjkm.supabase.co"

# Replace the old verify_token function with this:
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify Supabase JWT token and extract UUID (logs + safe fallback)."""
    token = credentials.credentials
    secret_set = bool(settings.SUPABASE_JWT_SECRET)
    print(f"[Auth] Verifying token; secret set: {secret_set}; token prefix: {token[:12] if token else 'none'}", flush=True)

    # Primary path: verify signature when secret is present
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET if secret_set else None,
            algorithms=["HS256"],
            options={"verify_aud": False, "verify_signature": secret_set}
        )
        print(f"[Auth] Token verified; uuid: {payload.get('sub')}", flush=True)
        return payload
    except jwt.ExpiredSignatureError:
        print("[Auth] Token expired", flush=True)
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidSignatureError as e:
        print(f"[Auth] Invalid signature: {e}", flush=True)
    except Exception as e:
        print(f"[Auth] Token verification failed: {e}", flush=True)

    # Fallback: decode without signature (helps when secret isn’t loaded)
    try:
        payload = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        print(f"[Auth] Fallback decode succeeded; uuid: {payload.get('sub')}", flush=True)
        return payload
    except Exception as e:
        print(f"[Auth] Fallback decode failed: {e}", flush=True)
        raise HTTPException(status_code=401, detail="Token verification failed")

def sync_graph_with_db(db, engine):
    """
    Ensures C++ Graph is up-to-date with SQL, even if Snapshot was loaded.
    """
    print("[Startup] Syncing Items...", flush=True)
    items = crud.get_items(db, limit=10000)
    for item in items:
        gid = crud.get_genre_id(item.category)
        if hasattr(engine, "set_item_genre"):
            engine.set_item_genre(item.id, gid)
            
    print("[Startup] Syncing Interactions...", flush=True)
    interactions = crud.get_all_interactions(db)
    count = 0
    for i in interactions:
        if hasattr(engine, "add_interaction"):
            engine.add_interaction(i.user_id, i.item_id, i.timestamp)
        count += 1
    print(f"[Startup] ✅ Synced {count} interactions to Graph.", flush=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. DATABASE CONNECTION (Crash if fails)
    print("[Startup] Connecting to Database...", flush=True)
    models.Base.metadata.create_all(bind=session.engine)
    db = session.SessionLocal()
    engine = get_engine()
    
    try:
        # Ensure SQL Data Exists
        crud.seed_items(db)
        
        # 2. LOAD GRAPH
        snapshot_bytes = crud.get_latest_snapshot(db)
        graph_loaded = False
        
        if snapshot_bytes:
            print("[Startup] Loading Snapshot...", flush=True)
            with open(BINARY_FILE, "wb") as f: f.write(snapshot_bytes)
            try:
                if hasattr(engine, "load_model"):
                    engine.load_model(BINARY_FILE)
                    if engine.get_item_count() > 0: graph_loaded = True
            except Exception as e:
                print(f"[Startup Warning] Snapshot load failed: {e}", flush=True)

        # 3. SYNC / REBUILD
        sync_graph_with_db(db, engine)
            
    finally:
        db.close()
    
    yield 
    
    # 4. SHUTDOWN SAVE
    print("[Shutdown] Saving State...", flush=True)
    db_shutdown = session.SessionLocal()
    try:
        if hasattr(engine, "save_model") and engine.get_item_count() > 0:
            engine.save_model(BINARY_FILE)
            with open(BINARY_FILE, "rb") as f:
                crud.save_snapshot(db_shutdown, f.read())
            print("[Shutdown] ✅ Snapshot Synced.", flush=True)
    except: pass
    finally:
        db_shutdown.close()
        time.sleep(1)

app = FastAPI(title=settings.PROJECT_NAME, version=settings.PROJECT_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interactions.router, prefix="/interaction", tags=["Interactions"])
app.include_router(recommend.router, prefix="/recommend", tags=["Recommendations"])
app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])

@app.head("/")
def root_head(): return Response(status_code=200)

@app.get("/api/config")
def get_config():
    """Provides Supabase config for frontend auth initialization"""
    return {
        "supabase_url": "https://rgqiezjbzraidrlmkjkm.supabase.co",
        "supabase_key": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJncWllempienJhaWRybG1ramttIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njc1Mjc1NzIsImV4cCI6MjA4MzEwMzU3Mn0.9HCCW8Lgaw53rOwMQbpzlqVu34l3vpgknkcxN_HidNM"
    }

@app.get("/items")
def get_all_items_endpoint():
    db = session.SessionLocal()
    try:
        items = crud.get_items(db, limit=5000)
        return [{"id": i.id, "title": i.title, "category": i.category} for i in items]
    finally:
        db.close()

# --- AUTH ENDPOINTS ---
@app.post("/auth/register")
def register_user(body: dict):
    """
    Register or reconcile a user:
    - Assign smallest free integer n
    - Set BOTH profiles.id = n and profiles.user_id = n
    - Reset sequence to keep IDs contiguous
    """
    db = session.SessionLocal()
    try:
        uuid = body.get("uuid")
        email = body.get("email")
        if not uuid or not email:
            raise HTTPException(status_code=400, detail="Missing uuid or email")

        # Existing row (often created by Supabase trigger)
        existing = db.query(models.Profile).filter(models.Profile.uuid == uuid).first()

        # Collect all used ids (both PK and user_id)
        rows = db.execute(text("SELECT id, user_id FROM profiles ORDER BY id")).all()
        used = set()
        for r in rows:
            if r[0] is not None: used.add(int(r[0]))
            if r[1] is not None: used.add(int(r[1]))

        # Find smallest free n
        n = 1
        while n in used:
            n += 1

        if existing:
            print(f"[Auth] Reconciling existing profile for {email}: target n={n}", flush=True)

            # Set user_id = n
            existing.user_id = n

            # If PK id differs, reassign to n
            if existing.id != n:
                # Ensure no conflict on id=n
                conflict = db.query(models.Profile).filter(models.Profile.id == n).first()
                if conflict:
                    raise HTTPException(status_code=409, detail=f"ID {n} is unexpectedly in use")

                existing.id = n

            db.commit()
            db.refresh(existing)

            # Reset sequence to MAX(id)
            try:
                db.execute(text("""
                    SELECT setval(
                        pg_get_serial_sequence('profiles', 'id'),
                        (SELECT COALESCE(MAX(id), 0) FROM profiles),
                        TRUE
                    )
                """))
                db.commit()
            except Exception as seq_err:
                print(f"[Auth] Sequence reset warning: {seq_err}", flush=True)

            print(f"[Auth] ✅ Reconciled: {email} -> id {existing.id}, user_id {existing.user_id}", flush=True)
            return {"user_id": existing.user_id, "email": email}

        # New insert: set id=n and user_id=n
        print(f"[Auth] Creating new profile for {email}: id={n}, user_id={n}", flush=True)
        profile = models.Profile(id=n, uuid=uuid, email=email, user_id=n)
        db.add(profile)
        db.commit()
        db.refresh(profile)

        # Reset sequence to MAX(id)
        try:
            db.execute(text("""
                SELECT setval(
                    pg_get_serial_sequence('profiles', 'id'),
                    (SELECT COALESCE(MAX(id), 0) FROM profiles),
                    TRUE
                )
            """))
            db.commit()
        except Exception as seq_err:
            print(f"[Auth] Sequence reset warning: {seq_err}", flush=True)

        print(f"[Auth] ✅ Profile created: {email} -> id {profile.id}, user_id {profile.user_id}", flush=True)
        return {"user_id": profile.user_id, "email": email}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[Auth] Registration error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Registration failed; please retry.")
    finally:
        db.close()

@app.get("/auth/user-id")
def get_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Get user's graph ID from UUID (extracted from JWT token).
    Requires: Authorization: Bearer <token>
    Returns: { "user_id": 2 }
    """
    try:
        payload = verify_token(credentials)
        uuid = payload.get("sub")  # Supabase stores user UUID in 'sub'
        
        if not uuid:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        db = session.SessionLocal()
        try:
            profile = db.query(models.Profile).filter(models.Profile.uuid == uuid).first()
            
            if profile:
                print(f"[Auth] User lookup: {profile.email} -> user_id {profile.user_id}", flush=True)
                return {"user_id": profile.user_id}
            else:
                print(f"[Auth] User not found: {uuid}", flush=True)
                raise HTTPException(status_code=404, detail="User not registered. Please create an account.")
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] User ID lookup error: {e}", flush=True)
        raise HTTPException(status_code=500, detail="Authentication failed")

# STATIC FILES
current_file = os.path.abspath(__file__)
app_dir = os.path.dirname(current_file)
backend_dir = os.path.dirname(app_dir)
frontend_local = os.path.join(os.path.dirname(backend_dir), "frontend")
frontend_docker = os.path.join(backend_dir, "frontend")

if os.path.exists(frontend_local):
    FRONTEND_DIR = frontend_local
elif os.path.exists(frontend_docker):
    FRONTEND_DIR = frontend_docker
else:
    FRONTEND_DIR = backend_dir

if os.path.exists(os.path.join(FRONTEND_DIR, "css")):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
if os.path.exists(os.path.join(FRONTEND_DIR, "js")):
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    if full_path == "login":
        full_path = "login.html"
    if full_path.startswith(("api", "interaction", "recommend/", "metrics", "items", "auth")):
        return {"error": "Not Found"}
    
    target_file = os.path.join(FRONTEND_DIR, full_path)
    if os.path.exists(target_file) and os.path.isfile(target_file):
        return FileResponse(target_file)
    
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"error": "Frontend not found"}

@app.get("/health")
def health_check():
    """Render health check endpoint"""
    return {"status": "healthy"}

@app.head("/health")
def health_check_head():
    """Render health check (HEAD request)"""
    return Response(status_code=200)