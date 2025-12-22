"""
FastAPI Dependencies Module
Provides authentication and authorization dependencies for endpoints
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

import auth
import projects

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependency to get the current authenticated user from JWT token.
    Raises 401 if token is invalid or user not found.
    """
    token = credentials.credentials

    token_data = auth.decode_access_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth.get_user_by_id(token_data.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated",
        )

    # Remove password hash from user dict
    user.pop("password_hash", None)
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[dict]:
    """
    Dependency to optionally get the current user.
    Returns None if no token provided or token is invalid.
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        token_data = auth.decode_access_token(token)
        if token_data is None:
            return None

        user = auth.get_user_by_id(token_data.user_id)
        if user:
            user.pop("password_hash", None)
        return user
    except:
        return None


class ProjectAccessChecker:
    """
    Dependency class to check project access with a minimum role.
    Usage: Depends(ProjectAccessChecker("write"))
    """

    def __init__(self, min_role: str = "read"):
        self.min_role = min_role

    async def __call__(
        self, project_id: int, current_user: dict = Depends(get_current_user)
    ) -> dict:
        """
        Check if the current user has access to the project with the required role.
        Returns a dict with user info and their role in the project.
        """
        # Check project exists
        project = projects.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )

        # Check user has access
        user_role = projects.get_user_role(project_id, current_user["id"])
        if not user_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this project",
            )

        # Check role level
        if not projects.user_has_access(project_id, current_user["id"], self.min_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires '{self.min_role}' access or higher",
            )

        return {"user": current_user, "project": project, "role": user_role}


# Pre-configured access checkers for common role levels
require_read_access = ProjectAccessChecker("read")
require_write_access = ProjectAccessChecker("write")
require_admin_access = ProjectAccessChecker("admin")
