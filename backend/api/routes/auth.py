from datetime import timedelta
from typing import Any, Dict

from api.models.auth import Token, UserCreate, UserLogin, UserResponse
from core.config import settings
from core.database import supabase
from core.security import SecurityManager, get_current_user, rate_limit_dependency
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter()
security_manager = SecurityManager()


@router.post(
    "/register", response_model=Token, dependencies=[Depends(rate_limit_dependency)]
)
async def register(user_data: UserCreate) -> Token:
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = (
            supabase.table("users").select("*").eq("email", user_data.email).execute()
        )
        if existing_user.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Hash password
        hashed_password = security_manager.hash_password(user_data.password)

        # Create user in database
        user_record = {
            "email": user_data.email,
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "role": user_data.role,
            "password_hash": hashed_password,
            "is_active": True,
        }

        result = supabase.table("users").insert(user_record).execute()
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user",
            )

        created_user = result.data[0]
        user_response = UserResponse(**created_user)

        # Create access token
        token_data = {
            "user_id": created_user["id"],
            "email": created_user["email"],
            "role": created_user["role"],
        }

        access_token = security_manager.create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=settings.jwt_expire_minutes),
        )

        return Token(
            access_token=access_token,
            expires_in=settings.jwt_expire_minutes * 60,
            user=user_response,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}",
        )


@router.post(
    "/login", response_model=Token, dependencies=[Depends(rate_limit_dependency)]
)
async def login(credentials: UserLogin) -> Token:
    """Login user"""
    try:
        # Get user from database
        user_result = (
            supabase.table("users").select("*").eq("email", credentials.email).execute()
        )

        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        user = user_result.data[0]

        # Verify password
        if not security_manager.verify_password(
            credentials.password, user["password_hash"]
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Check if user is active
        if not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled"
            )

        user_response = UserResponse(**user)

        # Create access token
        token_data = {
            "user_id": user["id"],
            "email": user["email"],
            "role": user["role"],
        }

        access_token = security_manager.create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=settings.jwt_expire_minutes),
        )

        return Token(
            access_token=access_token,
            expires_in=settings.jwt_expire_minutes * 60,
            user=user_response,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> UserResponse:
    """Get current user information"""
    try:
        user_result = (
            supabase.table("users")
            .select("*")
            .eq("id", current_user["user_id"])
            .execute()
        )

        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return UserResponse(**user_result.data[0])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {str(e)}",
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Token:
    """Refresh access token"""
    try:
        # Get updated user info
        user_result = (
            supabase.table("users")
            .select("*")
            .eq("id", current_user["user_id"])
            .execute()
        )

        if not user_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        user = user_result.data[0]
        user_response = UserResponse(**user)

        # Create new access token
        token_data = {
            "user_id": user["id"],
            "email": user["email"],
            "role": user["role"],
        }

        access_token = security_manager.create_access_token(
            data=token_data,
            expires_delta=timedelta(minutes=settings.jwt_expire_minutes),
        )

        return Token(
            access_token=access_token,
            expires_in=settings.jwt_expire_minutes * 60,
            user=user_response,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}",
        )
