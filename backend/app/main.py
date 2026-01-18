import os
import json
import time
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from .config import settings
from .db import session, models, crud
from .api import interactions, recommend, metrics
from .core.recommender import get_engine

BINARY_FILE = "graph.bin"

def load_from_sql_rows(db, engine):
    print("------------------------------------------------", flush=True)
    print("[Startup] 🛠️ REBUILDING GRAPH FROM SQL ROWS...", flush=True)
    
    print("[Startup] ... Loading Items into Graph", flush=True)
    # Direct DB call - will raise exception if DB down
    all_items = crud.get_items(db, limit=10000)
    
    count_items = 0
    for item in all_items:
        gid = crud.get_genre_id(item.category)
        if hasattr(engine, "set_item_genre"):
            engine.set_item_genre(item.id, gid)
        count_items += 1
    print(f"[Startup] ✅ Loaded {count_items} items into Graph.", flush=True)

    print("[Startup] ... Seeding/Loading Interactions", flush=True)
    crud.seed_interactions(db)
    
    all_interactions = crud.get_all_interactions(db)
    count_int = 0
    for i in all_interactions:
        if hasattr(engine, "add_interaction"):
            engine.add_interaction(i.user_id, i.item_id, i.timestamp)
        count_int += 1
    print(f"[Startup] ✅ Loaded {count_int} interactions.", flush=True)
    print("------------------------------------------------", flush=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. HARD DB CONNECTION
    # If this fails, the app CRASHES (No "Degraded Mode")
    print("[Startup] Connecting to Database...", flush=True)
    models.Base.metadata.create_all(bind=session.engine)
    db = session.SessionLocal()
    engine = get_engine()
    
    try:
        print("[Startup] Verifying Catalog...", flush=True)
        crud.seed_items(db)
        
        # 2. Snapshot Logic
        snapshot_bytes = crud.get_latest_snapshot(db)
        graph_loaded = False
        
        if snapshot_bytes and len(snapshot_bytes) > 0:
            print("[Startup] Found Snapshot. Downloading...", flush=True)
            with open(BINARY_FILE, "wb") as f:
                f.write(snapshot_bytes)
            
            if hasattr(engine, "load_model"):
                try:
                    engine.load_model(BINARY_FILE)
                    if engine.get_item_count() > 0:
                        print(f"[Startup] ✅ Graph loaded! ({engine.get_item_count()} items)", flush=True)
                        graph_loaded = True
                    else:
                        print("[Startup] ⚠️ Snapshot empty.", flush=True)
                except Exception as e:
                    print(f"[Startup Error] Snapshot corrupt: {e}", flush=True)

        if not graph_loaded:
            print("[Startup] Building from SQL...", flush=True)
            load_from_sql_rows(db, engine)
            
            if hasattr(engine, "save_model") and engine.get_item_count() > 0:
                print("[Startup] Saving Initial Snapshot...", flush=True)
                engine.save_model(BINARY_FILE)
                with open(BINARY_FILE, "rb") as f:
                    crud.save_snapshot(db, f.read())
                print("[Startup] ✅ Snapshot Created.", flush=True)

    finally:
        db.close()
    
    yield 
    
    # 3. Shutdown Save
    print("------------------------------------------------", flush=True)
    print("[Shutdown] Saving State...", flush=True)
    db_shutdown = session.SessionLocal()
    try:
        if hasattr(engine, "save_model") and engine.get_item_count() > 0:
            engine.save_model(BINARY_FILE)
            with open(BINARY_FILE, "rb") as f:
                crud.save_snapshot(db_shutdown, f.read())
            print("[Shutdown] ✅ Snapshot Synced.", flush=True)
    except Exception as e:
        print(f"[Shutdown Error] {e}", flush=True)
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

@app.get("/api/config")
def get_frontend_config():
    return {
        "supabase_url": settings.SUPABASE_URL,
        "supabase_key": settings.SUPABASE_ANON_KEY
    }

@app.get("/api/health")
def health_check():
    # Simple health check
    return {"status": "online", "db": "Connected"}

@app.head("/")
def root_head(): return Response(status_code=200)

@app.get("/items")
def get_all_items_endpoint():
    # Direct DB access. Fails if DB down.
    db = session.SessionLocal()
    try:
        items = crud.get_items(db, limit=5000)
        return [{"id": i.id, "title": i.title, "category": i.category} for i in items]
    finally:
        db.close()

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
    print("Warning: Frontend directory not found.", flush=True)
    FRONTEND_DIR = backend_dir

if os.path.exists(os.path.join(FRONTEND_DIR, "css")):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
if os.path.exists(os.path.join(FRONTEND_DIR, "js")):
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    if full_path == "login":
        full_path = "login.html"

    if full_path.startswith(("api", "interaction", "recommend/", "metrics", "items", "docs", "openapi")):
        return {"error": "Not Found"}
    
    target_file = os.path.join(FRONTEND_DIR, full_path)
    if os.path.exists(target_file) and os.path.isfile(target_file):
        return FileResponse(target_file)
    
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"error": "Frontend not found"}