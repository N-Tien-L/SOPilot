import hmac

import jwt
from fastapi import Request, HTTPException, status
from pydantic import BaseModel
from uuid import UUID
from typing import Optional

from ...config.settings import settings


class UserContext(BaseModel):
    user_id: UUID
    role: str
    department_id: Optional[UUID] = None
    workspace_id: Optional[UUID] = None

    class Config:
        from_attributes = True


def get_user_context(request: Request) -> UserContext:
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256", "HS384", "HS512"],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "iss", "sub", "role", "status"]},
        )
        if claims["status"] != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active",
            )
        department_id = claims.get("department")
        workspace_id_header = request.headers.get("X-Workspace-Id")
        workspace_id = None
        if workspace_id_header:
            try:
                workspace_id = UUID(workspace_id_header)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid X-Workspace-Id header format",
                )
        return UserContext(
            user_id=UUID(claims["sub"]),
            role=claims["role"],
            department_id=UUID(department_id) if department_id else None,
            workspace_id=workspace_id,
        )
    except HTTPException:
        raise
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired bearer token",
        ) from None


def verify_internal_api_key(request: Request) -> bool:
    api_key = request.headers.get("X-Internal-Api-Key", "")
    if not hmac.compare_digest(api_key, settings.internal_api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid internal API key"
        )
    return True
