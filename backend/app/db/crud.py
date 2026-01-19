from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from . import models
import time

# --- MAPPING CONFIG ---
GENRE_MAP = {
    "Action": 1, "Animation": 2, "Comedy": 3, "Crime": 4, 
    "Drama": 5, "Horror": 6, "Sci-Fi": 7, "Unknown": 0
}

def get_genre_id(category: str) -> int:
    return GENRE_MAP.get(category, 0)

# --- PROFILE CRUD ---

def get_profile_by_uuid(db: Session, uuid: str):
    return db.query(models.Profile).filter(models.Profile.uuid == uuid).first()

def get_profile_by_user_id(db: Session, user_id: int):
    return db.query(models.Profile).filter(models.Profile.user_id == user_id).first()

# --- STANDARD CRUD ---

def get_items(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Item).offset(skip).limit(limit).all()

def get_item_map(db: Session):
    items = db.query(models.Item).all()
    return {i.id: {"title": i.title, "category": i.category} for i in items}

def create_interaction(db: Session, user_id: int, item_id: int):
    existing = db.query(models.Interaction).filter(
        and_(models.Interaction.user_id == user_id, models.Interaction.item_id == item_id)
    ).first()
    
    if existing: return existing

    ts = int(time.time())
    db_interaction = models.Interaction(user_id=user_id, item_id=item_id, timestamp=ts)
    db.add(db_interaction)
    db.commit()
    db.refresh(db_interaction)
    return db_interaction

def delete_interaction(db: Session, user_id: int, item_id: int):
    db.query(models.Interaction).filter(
        and_(models.Interaction.user_id == user_id, models.Interaction.item_id == item_id)
    ).delete(synchronize_session=False)
    db.commit()

def get_all_interactions(db: Session):
    return db.query(models.Interaction).all()

def get_user_interacted_ids(db: Session, user_id: int):
    results = db.query(models.Interaction.item_id).filter(models.Interaction.user_id == user_id).all()
    return {r[0] for r in results}

# --- PREFERENCES ---

def set_user_preferences(db: Session, user_id: int, genre_names: list[str]):
    # Get current prefs
    existing = db.query(models.UserPreference).filter(models.UserPreference.user_id == user_id).all()
    existing_genres = {pref.genre_id for pref in existing}
    
    # Map new genre names to IDs
    new_genre_ids = {get_genre_id(name) for name in genre_names if get_genre_id(name) != 0}
    
    # Delete removed genres
    to_remove = existing_genres - new_genre_ids
    if to_remove:
        db.query(models.UserPreference).filter(
            models.UserPreference.user_id == user_id,
            models.UserPreference.genre_id.in_(to_remove)
        ).delete(synchronize_session=False)
    
    # Add new genres
    to_add = new_genre_ids - existing_genres
    for gid in to_add:
        db.add(models.UserPreference(user_id=user_id, genre_id=gid))
    
    db.commit()

def get_user_preference_ids(db: Session, user_id: int):
    results = db.query(models.UserPreference.genre_id).filter(models.UserPreference.user_id == user_id).all()
    return [r[0] for r in results]

# --- POPULARITY & DEFAULTS ---

def get_popular_item_ids(db: Session, limit: int = 10):
    """Get most interacted items (trending)"""
    results = db.query(models.Interaction.item_id, func.count(models.Interaction.id).label("count")) \
        .group_by(models.Interaction.item_id) \
        .order_by(desc("count")) \
        .limit(limit).all()
    return [r[0] for r in results]

def get_default_items(db: Session, limit: int = 10):
    """Get items in order (catalog fallback)"""
    results = db.query(models.Item.id).order_by(models.Item.id).limit(limit).all()
    return [r[0] for r in results]

# --- SNAPSHOTS ---

def save_snapshot(db: Session, binary_content: bytes):
    db.query(models.GraphSnapshot).delete()
    snapshot = models.GraphSnapshot(binary_data=binary_content)
    db.add(snapshot)
    db.commit()

def get_latest_snapshot(db: Session):
    snapshot = db.query(models.GraphSnapshot).order_by(desc(models.GraphSnapshot.created_at)).first()
    return snapshot.binary_data if snapshot else None

# --- SEEDING ---

def seed_items(db: Session):
    """
    Ensures the Movie Catalog exists in SQL. 
    """
    catalog = [
        {"id": 101, "title": "The Matrix", "category": "Sci-Fi"},
        {"id": 102, "title": "Inception", "category": "Sci-Fi"},
        {"id": 103, "title": "The Godfather", "category": "Crime"},
        {"id": 104, "title": "Toy Story", "category": "Animation"},
        {"id": 105, "title": "Pulp Fiction", "category": "Crime"},
        {"id": 106, "title": "Interstellar", "category": "Sci-Fi"},
        {"id": 107, "title": "Finding Nemo", "category": "Animation"},
        {"id": 108, "title": "Spirited Away", "category": "Animation"},
        {"id": 109, "title": "The Dark Knight", "category": "Action"},
        {"id": 110, "title": "Avengers: Endgame", "category": "Action"},
        {"id": 111, "title": "Mad Max: Fury Road", "category": "Action"},
        {"id": 112, "title": "John Wick", "category": "Action"},
        {"id": 113, "title": "Get Out", "category": "Horror"},
        {"id": 114, "title": "The Shining", "category": "Horror"},
        {"id": 115, "title": "Superbad", "category": "Comedy"},
        {"id": 116, "title": "The Hangover", "category": "Comedy"},
        {"id": 117, "title": "Forrest Gump", "category": "Drama"},
        {"id": 118, "title": "Parasite", "category": "Drama"},
        {"id": 119, "title": "Coco", "category": "Animation"},
        {"id": 120, "title": "Dune", "category": "Sci-Fi"},
        {"id": 121, "title": "Oppenheimer", "category": "Drama"},
        {"id": 122, "title": "Barbie", "category": "Comedy"},
        {"id": 123, "title": "Killers of the Flower Moon", "category": "Crime"},
        {"id": 124, "title": "Insidious", "category": "Horror"},
    ]    
    
    for item_data in catalog:
        exists = db.query(models.Item).filter(models.Item.id == item_data["id"]).first()
        if not exists:
            db.add(models.Item(**item_data))
    db.commit()
    return db.query(models.Item).all()

def seed_interactions(db: Session):
    # Intentionally empty to respect existing data in DB/Snapshot
    pass