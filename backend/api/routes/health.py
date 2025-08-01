import time
from typing import Any, Dict

from core.database import db_manager, get_redis
from core.security import rate_limit_dependency
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/health", include_in_schema=False)
async def health_check():
    """Basic health check"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "Med-Analyst NL2SQL Engine",
    }


@router.get(
    "/health/detailed",
    dependencies=[Depends(rate_limit_dependency)],
    include_in_schema=False,
)
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check including database and Redis connectivity"""
    health_status = {"status": "healthy", "timestamp": time.time(), "services": {}}

    # Check database connectivity
    try:
        async with db_manager.get_connection() as conn:
            result = await conn.fetchval("SELECT 1")
            health_status["services"]["database"] = {
                "status": "healthy" if result == 1 else "unhealthy",
                "response_time": time.time(),
            }
    except Exception as e:
        health_status["services"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"

    # Check Redis connectivity
    try:
        redis_client = await get_redis()
        start_time = time.time()
        await redis_client.ping()
        response_time = time.time() - start_time

        health_status["services"]["redis"] = {
            "status": "healthy",
            "response_time": response_time,
        }
    except Exception as e:
        health_status["services"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"

    return health_status


@router.get("/health/readiness", include_in_schema=False)
async def readiness_check():
    """Kubernetes readiness probe"""
    try:
        # Quick database check
        async with db_manager.get_connection() as conn:
            await conn.fetchval("SELECT 1")

        return {"status": "ready"}
    except Exception:
        return {"status": "not ready"}, 503


@router.get("/health/liveness", include_in_schema=False)
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"status": "alive"}
