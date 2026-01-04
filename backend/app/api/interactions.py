from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import crud, session
from ..core.recommender import get_engine

router = APIRouter()

class InteractionRequest(BaseModel):
    user_id: int
    item_id: int

@router.post("/", summary="Log a user-item interaction (Like)")
def log_interaction(data: InteractionRequest, db: Session = Depends(session.get_db)):
    # 1. DB Save
    interaction = crud.create_interaction(db, data.user_id, data.item_id)
    
    # 2. Update Graph
    engine = get_engine()
    engine.add_interaction(interaction.user_id, interaction.item_id, interaction.timestamp)
    
    return {"status": "success", "msg": "Interaction logged"}

@router.delete("/", summary="Remove an interaction (Unlike)")
def delete_interaction(data: InteractionRequest, db: Session = Depends(session.get_db)):
    # 1. DB Delete
    crud.delete_interaction(db, data.user_id, data.item_id)
    
    # 2. Update Graph
    engine = get_engine()
    if hasattr(engine, "remove_interaction"):
        engine.remove_interaction(data.user_id, data.item_id)

    return {"status": "success", "msg": "Interaction removed"}

@router.get("/{user_id}", response_model=List[int], summary="Get all items liked by user")
def get_user_interactions(user_id: int, db: Session = Depends(session.get_db)):
    """
    Returns a list of item IDs that the specific user has interacted with.
    Used by frontend to highlight 'Liked' boxes on load.
    """
    # This was failing because crud.get_user_interacted_ids didn't exist in the previous step
    return list(crud.get_user_interacted_ids(db, user_id))