from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.orm import Session
from app.config import settings
from app.db import session, models

security = HTTPBearer()

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(session.get_db)
) -> int:
    """Decodes JWT and returns the Graph User ID (Integer)"""
    token = credentials.credentials
    try:
        # Decode using the Legacy Secret
        payload = jwt.decode(
            token, 
            settings.SUPABASE_JWT_SECRET, 
            algorithms=["HS256"], 
            audience="authenticated",
            options={"verify_aud": False} # Sometimes audience varies in Supabase
        )
        user_uuid = payload.get("sub")
        
        if not user_uuid: raise HTTPException(401, "Invalid Token")

        # Map UUID -> Integer ID
        profile = db.query(models.Profile).filter(models.Profile.uuid == user_uuid).first()
        if not profile: raise HTTPException(404, "Profile not found in DB")
            
        return profile.id
    except Exception as e:
        print(f"Auth Failed: {e}")
        raise HTTPException(401, "Invalid Token")