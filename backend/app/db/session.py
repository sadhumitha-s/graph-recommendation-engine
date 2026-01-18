from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

# Optimized for Supabase Transaction Pooler (Port 6543)
engine = create_engine(
    settings.DATABASE_URL,
    # 1. Check connection health before use (Fixes "Closed unexpectedly")
    pool_pre_ping=True, 
    # 2. Refresh connections frequently
    pool_recycle=300, 
    # 3. Aggressive timeouts & Disable Prepared Statements
    connect_args={
        "connect_timeout": 20, 
        "keepalives": 1,
        "keepalives_idle": 5,
        "keepalives_interval": 2,
        "keepalives_count": 5,
        # CRITICAL: Disable prepared statements for PGBouncer/Supabase Pooler
        # If this is missing, the connection hangs and times out.
        "prepare_threshold": None 
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()