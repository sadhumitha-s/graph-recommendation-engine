from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON, BigInteger, LargeBinary, TIMESTAMP, DateTime
from datetime import datetime, timezone
from sqlalchemy.sql import func
from .session import Base

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True)  # Supabase UUID
    user_id = Column(Integer, unique=True, index=True)  # Graph ID
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Interaction(Base):
    __tablename__ = "interactions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    item_id = Column(Integer, index=True)
    timestamp = Column(BigInteger)

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    category = Column(String(100))

class UserPreference(Base):
    __tablename__ = "user_preferences"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    genre_id = Column(Integer)

class GraphSnapshot(Base):
    __tablename__ = "graph_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    binary_data = Column(LargeBinary)  # Stores graph.bin file content
    created_at = Column(DateTime(timezone=True), server_default=func.now())