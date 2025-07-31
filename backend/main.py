import logging
import time
from contextlib import asynccontextmanager

from api.routes import auth, health, query
from api.websocket import websocket_router
from core.config import settings
from core.database import db_manager
from core.security import rate_limit_dependency
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting Med-Analyst NL2SQL Engine...")
    try:
        await db_manager.init_db()
        logger.info("Database connections initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Med-Analyst NL2SQL Engine...")
    await db_manager.close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Natural Language to SQL Engine for Medical Data Analysis",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.debug else ["localhost", "127.0.0.1"],
)


# Custom middleware for request logging and timing
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()

    # Log request
    logger.info(f"Request: {request.method} {request.url}")

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)

        # Log response
        logger.info(f"Response: {response.status_code} - {process_time:.4f}s")
        return response

    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request failed: {str(e)} - {process_time:.4f}s")
        raise


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": time.time(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error" if not settings.debug else str(exc),
            "status_code": 500,
            "timestamp": time.time(),
        },
    )


# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(query.router, prefix="/api/v1/query", tags=["query"])
app.include_router(websocket_router, prefix="/ws")


# Root endpoint
@app.get("/")
async def root():
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "status": "running",
        "docs": "/docs" if settings.debug else "disabled",
    }


# Health check with rate limiting
@app.get("/health", dependencies=[Depends(rate_limit_dependency)])
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": settings.api_version,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="info",
    )
