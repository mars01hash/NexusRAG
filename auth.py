"""
JWT-based authentication for RAG AI Assistant.
Default credentials (change by editing data/users.json):
  admin / admin123  — role: admin
  user  / user123   — role: user
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import bcrypt as _bcrypt

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

USERS_FILE = Path("data/users.json")


def _hash(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def _default_users() -> Dict:
    return {
        "admin": {
            "username": "admin",
            "hashed_password": _hash("admin123"),
            "role": "admin",
        },
        "user": {
            "username": "user",
            "hashed_password": _hash("user123"),
            "role": "user",
        },
    }


def _load_users() -> Dict:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    defaults = _default_users()
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
    return defaults


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    users = _load_users()
    user = users.get(username)
    if not user or not _verify(password, user["hashed_password"]):
        return None
    return user


def create_access_token(username: str, role: str) -> str:
    exp = datetime.utcnow() + timedelta(hours=settings.jwt_expiry_hours)
    return jwt.encode(
        {"sub": username, "role": role, "exp": exp},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


class TokenUser(BaseModel):
    username: str
    role: str


def _decode_token(token: str) -> Optional[TokenUser]:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return TokenUser(username=payload["sub"], role=payload["role"])
    except JWTError:
        return None


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> TokenUser:
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _decode_token(creds.credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_admin(user: TokenUser = Depends(get_current_user)) -> TokenUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
