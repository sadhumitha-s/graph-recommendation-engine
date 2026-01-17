import os
from dotenv import load_dotenv

# 1. Load the .env file immediately
# This searches for a file named .env and loads the variables into the system
load_dotenv()

class Settings:
    PROJECT_NAME: str = "GraphRec API"
    PROJECT_VERSION: str = "2.0.0"

    # --- Private Secrets (Backend Only) ---
    # 2. Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./graphrec.db")

    # 3. Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # 4. Supabase JWT Secret
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

    # --- Public Config (Sent to Frontend) ---
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    
settings = Settings()