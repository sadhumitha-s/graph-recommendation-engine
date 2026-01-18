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

def sync_items_to_graph(db, engine):
    """Ensure C++ Engine knows about all items in DB, even if Snapshot was old."""
    print("[Startup] Syncing DB Items to Graph Engine...", flush=True)
    items = crud.get_items(db, limit=10000)
    count = 0
    for item in items:
        gid = crud.get_genre_id(item.category)
        if hasattr(engine, "set_item_genre"):
            engine.set_item_genre(item.id, gid)
        count += 1
    print(f"[Startup] ✅ Synced {count} items to Graph.", flush=True)

def load_all_from_sql(db, engine):
    print("[Startup] Rebuilding Graph from Scratch...", flush=True)
    sync_items_to_graph(db, engine)
    
    # Interactions
    all_interactions = crud.get_all_interactions(db)
    for i in all_interactions:
        if hasattr(engine, "add_interaction"):
            engine.add_interaction(i.user_id, i.item_id, i.timestamp)
    print(f"[Startup] ✅ Loaded {len(all_interactions)} interactions.", flush=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Startup] Connecting to Database...", flush=True)
    models.Base.metadata.create_all(bind=session.engine)
    db = session.SessionLocal()
    engine = get_engine()
    
    try:
        # 1. Ensure Catalog Exists
        crud.seed_items(db)
        
        # 2. Try Snapshot
        snapshot_bytes = crud.get_latest_snapshot(db)
        graph_loaded = False
        
        if snapshot_bytes:
            print("[Startup] Loading Snapshot...", flush=True)
            with open(BINARY_FILE, "wb") as f: f.write(snapshot_bytes)
            try:
                if hasattr(engine, "load_model"):
                    engine.load_model(BINARY_FILE)
                    if engine.get_item_count() > 0: 
                        graph_loaded = True
                        # FIX: Even if snapshot loaded, sync items to ensure we have all 20
                        sync_items_to_graph(db, engine)
            except Exception as e:
                print(f"[Startup Warning] Snapshot load failed: {e}", flush=True)

        # 3. Fallback
        if not graph_loaded:
            load_all_from_sql(db, engine)
            # Save the fixed graph immediately
            if hasattr(engine, "save_model") and engine.get_item_count() > 0:
                engine.save_model(BINARY_FILE)
                with open(BINARY_FILE, "rb") as f:
                    crud.save_snapshot(db, f.read())

    finally:
        db.close()
    
    yield 
    
    # Shutdown Save
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

@app.get("/api/config")
def get_frontend_config():
    return {
        "supabase_url": settings.SUPABASE_URL,
        "supabase_key": settings.SUPABASE_ANON_KEY
    }

@app.get("/api/health")
def health_check():
    return {"status": "online"}

@app.head("/")
def root_head(): return Response(status_code=200)

@app.get("/items")
def get_all_items_endpoint():
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