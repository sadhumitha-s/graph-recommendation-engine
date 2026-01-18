import os
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
        # Even if snapshot loaded, we sync to ensure fresh data
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
    if full_path.startswith(("api", "interaction", "recommend/", "metrics", "items")):
        return {"error": "Not Found"}
    
    target_file = os.path.join(FRONTEND_DIR, full_path)
    if os.path.exists(target_file) and os.path.isfile(target_file):
        return FileResponse(target_file)
    
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"error": "Frontend not found"}