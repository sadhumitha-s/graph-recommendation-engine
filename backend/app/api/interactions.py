from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.db import crud, session
from app.core.recommender import get_engine
from app.core.security import get_current_user_id  # ← USE THIS
from app.utils.redis import redis_client

router = APIRouter()

class InteractionRequest(BaseModel):
    user_id: int
    item_id: int

@router.post("/", summary="Log a user-item interaction (Like)")
def log_interaction(
    data: InteractionRequest, 
    db: Session = Depends(session.get_db),
    current_user_id: int = Depends(get_current_user_id)  # ← PROPER VERIFICATION
):
    # Verify ownership
    if current_user_id != data.user_id:
        raise HTTPException(status_code=403, detail="You can only modify your own interactions.")
    
    # Save to DB
    interaction = crud.create_interaction(db, data.user_id, data.item_id)
    
    # Update C++ Engine
    engine = get_engine()
    if hasattr(engine, "add_interaction"):
        engine.add_interaction(data.user_id, data.item_id, interaction.timestamp) 
    
    # Wipe Cache
    if redis_client:
        try:
            for key in redis_client.scan_iter(f"rec:{data.user_id}:*"):
                redis_client.delete(key)
        except Exception as e:
            print(f"⚠️ Redis Delete Error: {e}")
    
    return {"status": "success", "msg": "Interaction logged"}

@router.delete("/", summary="Remove an interaction (Unlike)")
def delete_interaction(
    data: InteractionRequest,
    db: Session = Depends(session.get_db),
    current_user_id: int = Depends(get_current_user_id)  # ← PROPER VERIFICATION
):
    # Verify ownership
    if current_user_id != data.user_id:
        raise HTTPException(status_code=403, detail="You can only modify your own interactions.")

    crud.delete_interaction(db, data.user_id, data.item_id)
    
    engine = get_engine()
    if hasattr(engine, "remove_interaction"):
        engine.remove_interaction(data.user_id, data.item_id)

    # Wipe Cache
    if redis_client:
        try:
            for key in redis_client.scan_iter(f"rec:{data.user_id}:*"):
                redis_client.delete(key)
        except Exception as e:
            print(f"⚠️ Redis Delete Error: {e}")

    return {"status": "success", "msg": "Interaction removed"}

@router.get("/{user_id}", response_model=List[int])
def get_user_interactions(user_id: int, db: Session = Depends(session.get_db)):
    """PUBLIC READ: Anyone can view any user's likes"""
    return list(crud.get_user_interacted_ids(db, user_id))