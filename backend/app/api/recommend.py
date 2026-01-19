from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import time
import json

from app.db import session, crud
from app.core.recommender import get_engine
from app.utils.redis import redis_client

router = APIRouter()

# --- Response Models ---
class ItemResponse(BaseModel):
    id: int
    title: str
    category: str
    reason: str  # e.g., "Graph-Based", "Trending", "New Arrival"

class RecResponse(BaseModel):
    user_id: int
    recommendations: List[ItemResponse]
    latency_ms: float
    source: str = "Hybrid" # Changed from "Compute" to "Hybrid" since we mix sources

class PrefRequest(BaseModel):
    user_id: int
    genres: List[str]

# --- Endpoints ---

@router.post("/preferences")
def save_preferences(data: PrefRequest, db: Session = Depends(session.get_db)):
    crud.set_user_preferences(db, data.user_id, data.genres)
    
    # Invalidate Cache
    if redis_client:
        try:
            for key in redis_client.scan_iter(f"rec:{data.user_id}:*"):
                redis_client.delete(key)
        except Exception as e:
            print(f"⚠️ Redis Invalidation Error: {e}")

    return {"status": "success", "msg": "Preferences saved"}


@router.get("/preferences/{user_id}", response_model=List[str])
def get_user_preferences(user_id: int, db: Session = Depends(session.get_db)):
    """Get user's genre preferences as a list of genre names"""
    genre_ids = crud.get_user_preference_ids(db, user_id)
    # Map IDs back to names
    id_to_name = {v: k for k, v in crud.GENRE_MAP.items() if k != "Unknown"}
    return [id_to_name.get(gid, "Unknown") for gid in genre_ids if gid in id_to_name]


@router.get("/{user_id}", response_model=RecResponse)
def get_recommendations(
    user_id: int, 
    k: int = 5, 
    algo: str = Query("bfs", description="Algorithm: 'bfs' or 'ppr'"),
    db: Session = Depends(session.get_db)
):
    t0 = time.time()
    cache_key = f"rec:{user_id}:{algo}:{k}"

    # 1. CHECK CACHE (Only for BFS to allow PPR experiments)
    if algo == "bfs" and redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                results = json.loads(cached_data)
                t1 = time.time()
                return {
                    "user_id": user_id,
                    "recommendations": results,
                    "latency_ms": (t1 - t0) * 1000,
                    "source": "Redis Cache ⚡"
                }
        except Exception:
            pass

    # 2. PREPARE DATA
    engine = get_engine()
    seen_ids = crud.get_user_interacted_ids(db, user_id)
    pref_ids = crud.get_user_preference_ids(db, user_id)
    
    # We use a set to ensure we don't recommend the same item twice via different strategies
    recommended_ids = set() 
    final_items_meta = [] # List of dicts: {id, reason}

    # 3. STRATEGY A: THE GRAPH ENGINE (BFS / PPR)
    # We try to get as many as possible from here first.
    graph_candidates = []
    graph_strategy_name = "Graph-Based"

    if algo == "ppr" and hasattr(engine, "recommend_ppr"):
        graph_candidates = engine.recommend_ppr(user_id, k + 10, 10000, 2)
        graph_strategy_name = "PageRank"
    elif hasattr(engine, "recommend"):
        # Weighted BFS
        graph_candidates = engine.recommend(user_id, k, pref_ids)
        graph_strategy_name = "Graph BFS"

    # Filter Graph Results
    for pid in graph_candidates:
        # Handle if engine returns (id, score) tuple
        clean_id = pid[0] if isinstance(pid, (list, tuple)) else pid
        
        if clean_id not in seen_ids and clean_id not in recommended_ids:
            recommended_ids.add(clean_id)
            final_items_meta.append({"id": clean_id, "reason": graph_strategy_name})
            
            if len(final_items_meta) >= k:
                break

    # 4. STRATEGY B: FALLBACK TO POPULAR (Trending)
    # If graph didn't provide enough items (e.g. sparse graph), fill gaps with popular items.
    if len(final_items_meta) < k:
        needed = k - len(final_items_meta)
        # Fetch extra popular items to account for 'seen' overlap
        popular_candidates = crud.get_popular_item_ids(db, limit=needed + len(seen_ids) + 5)
        
        for pid in popular_candidates:
            if pid not in seen_ids and pid not in recommended_ids:
                recommended_ids.add(pid)
                final_items_meta.append({"id": pid, "reason": "Global Trending"})
                
                if len(final_items_meta) >= k:
                    break

    # 5. STRATEGY C: FALLBACK TO NEWEST (Catalog)
    # If still not enough (e.g. fresh DB with no interactions), just show items.
    if len(final_items_meta) < k:
        needed = k - len(final_items_meta)
        default_candidates = crud.get_default_items(db, limit=needed + len(seen_ids) + 10)
        
        for pid in default_candidates:
            if pid not in seen_ids and pid not in recommended_ids:
                recommended_ids.add(pid)
                final_items_meta.append({"id": pid, "reason": "New Arrival"})
                
                if len(final_items_meta) >= k:
                    break

    # 6. HYDRATE WITH TITLES
    item_map = crud.get_item_map(db)
    results = []
    
    for meta in final_items_meta:
        i_id = meta["id"]
        reason = meta["reason"]
        details = item_map.get(i_id, {"title": f"Item {i_id}", "category": "Unknown"})
        
        results.append({
            "id": i_id,
            "title": details["title"],
            "category": details["category"],
            "reason": reason
        })

    t1 = time.time()

    # 7. UPDATE CACHE
    if results and algo == "bfs" and redis_client:
        try:
            redis_client.setex(cache_key, 3600, json.dumps(results))
        except Exception as e:
            print(f"⚠️ Redis Write Error: {e}")

    return {
        "user_id": user_id,
        "recommendations": results,
        "latency_ms": (t1 - t0) * 1000,
        "source": "Hybrid (Graph + Fallback)"
    }