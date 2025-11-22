from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Redis configuration
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0
    redis_channel_name: str = "events"  # Pub/Sub channel name
    
    # Database configuration
    database_url: str = "postgresql://vms_admin:AIvan0987@db:5432/vms_analytics_db"
    
    # YOLO configuration
    yolo_model: str = "/app/weights/general/yolov8m.pt"
    garbage_model: str = "/app/weights/garbage_detection/best.pt"
    
    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8069
    
    # Snapshot configuration
    snapshots_dir: str = "/app/snapshots"
    enable_snapshots: bool = True
    
    # Logging
    log_level: str = "INFO"
    
    # Docker configuration
    docker_namespace: str = "dockared"
    version: str = "latest"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

