from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from . import models
import time

def create_interaction(db: Session, user_id: int, item_id: int):
    # Check if exists first to avoid duplicates (optional, but good for cleanliness)
    existing = db.query(models.Interaction).filter(
        and_(
            models.Interaction.user_id == user_id,
            models.Interaction.item_id == item_id
        )
    ).first()
    
    if existing:
        return existing

    ts = int(time.time())
    db_interaction = models.Interaction(
        user_id=user_id, 
        item_id=item_id, 
        timestamp=ts
    )
    db.add(db_interaction)
    db.commit()
    db.refresh(db_interaction)
    return db_interaction

def delete_interaction(db: Session, user_id: int, item_id: int):
    db.query(models.Interaction).filter(
        and_(
            models.Interaction.user_id == user_id,
            models.Interaction.item_id == item_id
        )
    ).delete(synchronize_session=False)
    db.commit()

def get_all_interactions(db: Session):
    return db.query(models.Interaction).all()

def get_item_map(db: Session):
    """Returns a dict {id: {title, category}} for fast lookup"""
    items = db.query(models.Item).all()
    return {i.id: {"title": i.title, "category": i.category} for i in items}

# --- HISTORY HELPERS (The Missing Piece) ---

def get_user_interacted_ids(db: Session, user_id: int):
    """Returns a SET of item_ids the user has already seen."""
    results = db.query(models.Interaction.item_id)\
                .filter(models.Interaction.user_id == user_id)\
                .all()
    # Return as a Python Set
    return {r[0] for r in results}

# --- FALLBACK / COLD START HELPERS ---

def get_popular_item_ids(db: Session, limit: int):
    results = db.query(models.Interaction.item_id)\
                .group_by(models.Interaction.item_id)\
                .order_by(func.count(models.Interaction.item_id).desc())\
                .limit(limit)\
                .all()
    return [r[0] for r in results]

def get_default_items(db: Session, limit: int):
    items = db.query(models.Item.id).limit(limit).all()
    return [i.id for i in items]

def seed_items(db: Session):
    if db.query(models.Item).count() == 0:
        initial_items = [
            models.Item(id=101, title="The Matrix", category="Sci-Fi"),
            models.Item(id=102, title="Inception", category="Sci-Fi"),
            models.Item(id=103, title="The Godfather", category="Crime"),
            models.Item(id=104, title="Toy Story", category="Animation"),
            models.Item(id=105, title="Pulp Fiction", category="Crime"),
            models.Item(id=106, title="Interstellar", category="Sci-Fi"),
            models.Item(id=107, title="Finding Nemo", category="Animation"),
            models.Item(id=108, title="Spirited Away", category="Animation"),
            models.Item(id=109, title="The Dark Knight", category="Action"),
        ]
        db.add_all(initial_items)
        db.commit()