from fastapi import Depends, HTTPException, status
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
    """
    Security Middleware:
    1. Validates the JWT Token from Supabase.
    2. Maps the Auth UUID to your internal Integer ID.
    3. Returns the Integer ID to the API endpoint for permission checks.
    """
    token = credentials.credentials
    
    try:
        # Decode the JWT using the secret from .env
        payload = jwt.decode(
            token, 
            settings.SUPABASE_JWT_SECRET, 
            algorithms=["HS256"], 
            options={"verify_aud": False} # Supabase 'aud' can vary, signature is key
        )
        
        user_uuid = payload.get("sub")
        if not user_uuid: 
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid Token: No Subject"
            )

        # Lookup the Profile to get the Integer Graph ID
        profile = db.query(models.Profile).filter(models.Profile.uuid == user_uuid).first()
        
        if not profile:
            # Token is valid, but local DB profile is missing
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User profile not initialized in Graph Database"
            )
            
        return profile.id

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid authentication token"
        )
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Authentication failed"
        )