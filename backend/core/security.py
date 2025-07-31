import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Bearer token
security = HTTPBearer()

# Rate limiting storage
rate_limit_storage = defaultdict(list)


class SecurityManager:
    """Handles authentication, authorization, and security"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(
        data: Dict[str, Any], expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)

        to_encode.update({"exp": expire, "iat": datetime.utcnow()})

        encoded_jwt = jwt.encode(
            to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
        )

        return encoded_jwt

    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(
                token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
            )

            # Check if token is expired
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
                )

            return payload

        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}",
            )


class RateLimiter:
    """Rate limiting for API endpoints"""

    @staticmethod
    async def check_rate_limit(request: Request, max_requests: int = None) -> bool:
        """Check if request is within rate limit"""
        if max_requests is None:
            max_requests = settings.rate_limit_per_minute

        client_ip = request.client.host
        current_time = time.time()

        # Clean old entries
        rate_limit_storage[client_ip] = [
            timestamp
            for timestamp in rate_limit_storage[client_ip]
            if current_time - timestamp < 60  # 1 minute window
        ]

        # Check rate limit
        if len(rate_limit_storage[client_ip]) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

        # Add current request
        rate_limit_storage[client_ip].append(current_time)
        return True


class QueryValidator:
    """Validates SQL queries for security"""

    FORBIDDEN_KEYWORDS = [
        "DROP",
        "DELETE",
        "TRUNCATE",
        "ALTER",
        "CREATE",
        "INSERT",
        "UPDATE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
        "sp_",
        "xp_",
    ]

    SUSPICIOUS_PATTERNS = [
        "--",
        "/*",
        "*/",
        ";--",
        "union",
        "or 1=1",
        "or '1'='1'",
        'or "1"="1"',
    ]

    @classmethod
    def validate_query(cls, query: str) -> bool:
        """Validate SQL query for security issues"""
        query_upper = query.upper().strip()

        # Check for forbidden keywords
        for keyword in cls.FORBIDDEN_KEYWORDS:
            if keyword in query_upper:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Query contains forbidden keyword: {keyword}",
                )

        # Check for suspicious patterns
        query_lower = query.lower()
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if pattern in query_lower:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Query contains suspicious patterns",
                )

        # Query length check
        if len(query) > 10000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Query too long"
            )

        return True


# Dependency functions
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Get current authenticated user"""
    token = credentials.credentials
    return SecurityManager.verify_token(token)


async def rate_limit_dependency(request: Request) -> bool:
    """Rate limiting dependency"""
    return await RateLimiter.check_rate_limit(request)


# Optional authentication (for public endpoints)
async def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user if authenticated, None otherwise"""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]
        return SecurityManager.verify_token(token)
    except:
        return None


# Create security manager instance
security_manager = SecurityManager()
query_validator = QueryValidator()
