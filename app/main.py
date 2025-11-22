from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.cameras import router as cameras_router
from app.api.events import router as events_router
from app.core.config import get_settings
from app.core.database import init_db, check_db_connection
from app.services.video_worker import camera_manager
from app.services.retention_scheduler import retention_scheduler
from app.core.redis_client import redis_client
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting Analytics Service")
    logger.info(f"Redis: {settings.redis_host}:{settings.redis_port}")
    logger.info(f"Database: {settings.database_url.split('@')[1] if '@' in settings.database_url else settings.database_url}")
    logger.info(f"YOLO Model: {settings.yolo_model}")
    logger.info(f"Garbage Model: {settings.garbage_model}")
    logger.info(f"Snapshots Directory: {settings.snapshots_dir}")
    
    # Verify Redis connection
    if redis_client.health_check():
        logger.info("Redis connection verified")
    else:
        logger.error("Failed to connect to Redis")
    
    # Initialize database
    try:
        if check_db_connection():
            logger.info("Database connection verified")
            init_db()
        else:
            logger.error("Failed to connect to database")
    except Exception as e:
        logger.error(f"Database initialization error: {e}", exc_info=True)
    
    # Start retention scheduler
    try:
        retention_scheduler.start()
        logger.info("Retention scheduler started")
    except Exception as e:
        logger.error(f"Failed to start retention scheduler: {e}", exc_info=True)
    
    yield
    
    # Shutdown
    logger.info("Shutting down Analytics Service")
    camera_manager.stop_all()
    retention_scheduler.stop()
    redis_client.close()
    logger.info("Analytics Service stopped")


# Create FastAPI application
app = FastAPI(
    title="Video Analytics Service",
    description="Standalone analytics service for video processing with object detection, motion detection, and ANPR",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cameras_router)
app.include_router(events_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Video Analytics Service",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level.lower()
    )

