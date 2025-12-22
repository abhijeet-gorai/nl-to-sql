"""
Authentication Router
FastAPI router for user authentication endpoints
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field

import auth
from dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================
# Request/Response Models
# ============================================


class RegisterRequest(BaseModel):
    """User registration request"""

    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)


class RegisterResponse(BaseModel):
    """User registration response"""

    id: int
    username: str
    full_name: str
    email: str


class LoginRequest(BaseModel):
    """User login request"""

    username: str
    password: str


class LoginResponse(BaseModel):
    """User login response"""

    access_token: str
    token_type: str = "bearer"
    user: dict


class ChangePasswordRequest(BaseModel):
    """Password change request"""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)


class UserResponse(BaseModel):
    """User profile response"""

    id: int
    username: str
    full_name: str
    email: str
    is_active: bool


# ============================================
# Endpoints
# ============================================


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
async def register(request: RegisterRequest):
    """
    Register a new user account.

    - **username**: Unique username (3-50 characters)
    - **full_name**: User's full name
    - **email**: Valid email address (must be unique)
    - **password**: Password (minimum 8 characters)
    """
    try:
        user_id = auth.create_user(
            username=request.username,
            full_name=request.full_name,
            email=request.email,
            password=request.password,
        )

        return RegisterResponse(
            id=user_id,
            username=request.username,
            full_name=request.full_name,
            email=request.email,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return JWT token.

    - **username**: Username
    - **password**: Password
    """
    user = auth.authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = auth.create_access_token(user["id"])

    # Remove password hash before returning
    user_response = {
        "id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "email": user["email"],
    }

    return LoginResponse(access_token=access_token, user=user_response)


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout the current user.

    Note: JWT tokens are stateless, so this endpoint just confirms the logout.
    The client should discard the token.
    """
    return {"status": "success", "message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get the current authenticated user's profile.
    """
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        full_name=current_user["full_name"],
        email=current_user["email"],
        is_active=current_user.get("is_active", True),
    )


@router.put("/change-password")
async def change_password(
    request: ChangePasswordRequest, current_user: dict = Depends(get_current_user)
):
    """
    Change the current user's password.

    - **current_password**: Current password for verification
    - **new_password**: New password (minimum 8 characters)
    """
    try:
        success = auth.update_password(
            user_id=current_user["id"],
            old_password=request.current_password,
            new_password=request.new_password,
        )

        if success:
            return {"status": "success", "message": "Password updated successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password",
            )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/users/search")
async def search_users(
    q: str, limit: int = 10, current_user: dict = Depends(get_current_user)
):
    """
    Search for users by username, email, or full name.
    Useful for adding members to projects.

    - **q**: Search query
    - **limit**: Maximum number of results (default 10)
    """
    if len(q) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query must be at least 2 characters",
        )

    users = auth.search_users(q, limit=min(limit, 50))

    # Exclude current user from results
    users = [u for u in users if u["id"] != current_user["id"]]

    return users
