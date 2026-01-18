from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.orm import Session
from app.config import settings
from app.db import session, crud

security = HTTPBearer()

def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(session.get_db)
) -> int:
    """
    Verifies JWT token from Supabase using the secret from .env
    Returns the user's graph ID (user_id from profiles table).
    """
    token = credentials.credentials
    
    try:
        # Verify JWT signature using the secret from .env
        payload = jwt.decode(
            token, 
            settings.SUPABASE_JWT_SECRET, 
            algorithms=["HS256"],
            options={"verify_aud": False}  # Supabase aud varies
        )
        
        uuid = payload.get("sub")
        if not uuid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, 
                detail="Invalid token: missing subject"
            )

        # Lookup user's profile to get their graph ID
        profile = crud.get_profile_by_uuid(db, uuid)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User profile not found. Please register first."
            )
        
        # Return the user's graph ID (not the DB primary key)
        return profile.user_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token has expired"
        )
    except jwt.InvalidSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid token signature"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid token"
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Auth] Verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Authentication failed"
        )