import os
import json
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from .config import settings
from .db import session, models, crud
from .api import interactions, recommend, metrics
from .core.recommender import get_engine

BINARY_FILE = "graph.bin"

# --- HELPER: Load Data from SQL to C++ ---
def load_from_sql_rows(db, engine):
    """
    Reads Items and Interactions from Supabase and feeds them into the C++ Engine.
    """
    print("------------------------------------------------", flush=True)
    print("[Startup] 🛠️ REBUILDING GRAPH FROM SQL ROWS...", flush=True)
    
    # 1. Load Items into C++ 
    print("[Startup] ... Loading Items into Graph", flush=True)
    all_items = crud.get_items(db, limit=10000)
    
    count_items = 0
    for item in all_items:
        gid = crud.get_genre_id(item.category)
        if hasattr(engine, "set_item_genre"):
            engine.set_item_genre(item.id, gid)
        count_items += 1
    print(f"[Startup] ✅ Loaded {count_items} items into Graph.", flush=True)

    # 2. Load/Seed Interactions
    print("[Startup] ... Seeding/Loading Interactions", flush=True)
    # If interactions table is empty, create dummy data so graph isn't empty
    if hasattr(crud, "seed_interactions"):
        crud.seed_interactions(db)
    
    all_interactions = crud.get_all_interactions(db)
    count_int = 0
    for i in all_interactions:
        if hasattr(engine, "add_interaction"):
            engine.add_interaction(i.user_id, i.item_id, i.timestamp)
        count_int += 1
    print(f"[Startup] ✅ Loaded {count_int} interactions.", flush=True)
    print("------------------------------------------------", flush=True)

# --- LIFESPAN (Server Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Init Database Tables
    models.Base.metadata.create_all(bind=session.engine)
    db = session.SessionLocal()
    engine = get_engine()
    
    try:
        print("[Startup] Initializing...", flush=True)

        # --- A. ALWAYS ENSURE SQL HAS ITEMS ---
        # This fixes the "Undefined Movie" error on the Catalog page
        print("[Startup] Verifying Catalog Items in SQL...", flush=True)
        crud.seed_items(db)
        
        # --- B. TRY LOADING SNAPSHOT ---
        snapshot_bytes = crud.get_latest_snapshot(db)
        graph_loaded = False
        
        if snapshot_bytes and len(snapshot_bytes) > 0:
            print("[Startup] Found Snapshot in DB. Downloading...", flush=True)
            with open(BINARY_FILE, "wb") as f:
                f.write(snapshot_bytes)
            
            if hasattr(engine, "load_model"):
                try:
                    engine.load_model(BINARY_FILE)
                    
                    # VALIDATION: Only accept if it has nodes
                    item_count = engine.get_item_count() if hasattr(engine, "get_item_count") else 0
                    if item_count > 0:
                        print(f"[Startup] ✅ Graph loaded from Snapshot! ({item_count} items)", flush=True)
                        graph_loaded = True
                    else:
                        print("[Startup] ⚠️ Snapshot was empty (0 items). Discarding it.", flush=True)
                        graph_loaded = False
                        
                except Exception as e:
                    print(f"[Startup Error] Snapshot corrupted: {e}", flush=True)
                    graph_loaded = False

        # --- C. FALLBACK & CREATE INITIAL SNAPSHOT ---
        if not graph_loaded:
            print("[Startup] Snapshot missing or invalid. Rebuilding from SQL...", flush=True)
            load_from_sql_rows(db, engine)
            
            # REQ 1: "Create a snapshot if empty"
            # If we just built a valid graph from SQL, save it immediately 
            # so the next startup is fast.
            if hasattr(engine, "save_model") and hasattr(engine, "get_item_count"):
                if engine.get_item_count() > 0:
                    print("[Startup] Saving fresh Initial Snapshot to DB...", flush=True)
                    engine.save_model(BINARY_FILE)
                    with open(BINARY_FILE, "rb") as f:
                        crud.save_snapshot(db, f.read())
                    print("[Startup] ✅ Initial Snapshot created.", flush=True)

    except Exception as e:
        print(f"[Startup CRITICAL ERROR] {e}", flush=True)
        # Last ditch effort to ensure app runs
        load_from_sql_rows(db, engine)
    finally:
        db.close()
    
    # === APP RUNS HERE ===
    yield 
    # =====================
    
    # --- D. SHUTDOWN LOGIC (SAVE LATEST) ---
    print("------------------------------------------------", flush=True)
    print("[Shutdown] Saving Application State...", flush=True)
    
    # Open a new DB session for shutdown operations
    db_shutdown = session.SessionLocal()
    
    try:
        # REQ 2.1: "When the server is closed, save the latest snapshot"
        if hasattr(engine, "save_model") and hasattr(engine, "get_item_count"):
            count = engine.get_item_count()
            if count > 0:
                print(f"[Shutdown] Saving Graph ({count} items) to disk...", flush=True)
                engine.save_model(BINARY_FILE)
                
                print("[Shutdown] Uploading Snapshot to Supabase...", flush=True)
                with open(BINARY_FILE, "rb") as f:
                    binary_data = f.read()
                    crud.save_snapshot(db_shutdown, binary_data)
                print("[Shutdown] ✅ Snapshot successfully synced to DB.", flush=True)
            else:
                print("[Shutdown] Graph is empty. Skipping save.", flush=True)
    except Exception as e:
        print(f"[Shutdown Error] Failed to save snapshot: {e}", flush=True)
    finally:
        db_shutdown.close()
        # Give Docker a moment to capture the logs before killing the process
        time.sleep(1)

# --- APP DEFINITION ---
app = FastAPI(title=settings.PROJECT_NAME, version=settings.PROJECT_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ROUTERS ---
app.include_router(interactions.router, prefix="/interaction", tags=["Interactions"])
app.include_router(recommend.router, prefix="/recommend", tags=["Recommendations"])
app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])

# --- NEW: Configuration Endpoint ---
@app.get("/api/config")
def get_frontend_config():
    """
    Returns the public Supabase keys so the frontend can connect.
    This allows us to change keys in .env without rebuilding the frontend code.
    """
    return {
        "supabase_url": settings.SUPABASE_URL,
        "supabase_key": settings.SUPABASE_ANON_KEY
    }

# --- HEALTH CHECK ---
@app.get("/api/health")
def health_check():
    engine = get_engine()
    node_count = engine.get_item_count() if hasattr(engine, "get_item_count") else 0
    return {
        "status": "online", 
        "graph_nodes": node_count,
        "db": "Connected"
    }

# --- CATALOG ENDPOINT ---
@app.get("/items")
def get_all_items_endpoint():
    """
    Returns a LIST of items for the catalog page.
    Format: [{"id": 101, "title": "Matrix", ...}, ...]
    """
    db = session.SessionLocal()
    items = crud.get_items(db, limit=5000)
    db.close()
    
    # Return list directly (fixes "undefined" error on frontend)
    return [
        {"id": i.id, "title": i.title, "category": i.category} 
        for i in items
    ]

# --- STATIC FILES ---
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
    # Fallback to current directory to prevent crash, though UI won't load
    print("Warning: Frontend directory not found.", flush=True)
    FRONTEND_DIR = backend_dir

if os.path.exists(os.path.join(FRONTEND_DIR, "css")):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
if os.path.exists(os.path.join(FRONTEND_DIR, "js")):
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    # Pass through API calls if they slipped through routers
    if full_path.startswith(("api", "interaction", "recommend/", "metrics", "items", "docs", "openapi")):
        return {"error": "Not Found"}
    
    # Explicitly handle login route
    if full_path == "login":
        full_path = "login.html"
    
    target_file = os.path.join(FRONTEND_DIR, full_path)
    if os.path.exists(target_file) and os.path.isfile(target_file):
        return FileResponse(target_file)
    
    # Default: Serve index.html (SPA-like behavior)
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"error": "Frontend not found"}