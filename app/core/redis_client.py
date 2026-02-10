import redis
import json
from typing import Dict, Any
from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RedisClient:
    """
    Redis client wrapper for Pub/Sub operations.
    Uses redis-py's built-in connection pooling and retry logic.
    """
    
    def __init__(self):
        self._client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize the Redis client with robust connection settings."""
        try:
            connection_kwargs = {
                "host": settings.redis_host,
                "port": settings.redis_port,
                "db": settings.redis_db,
                "decode_responses": True,
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
                "retry_on_timeout": True,       # Retry on timeout
                "health_check_interval": 30,    # Active health check
                "socket_keepalive": True        # TCP keepalive
            }
            # Add password if configured
            if settings.redis_password:
                connection_kwargs["password"] = settings.redis_password
            
            # redis.Redis is lazy; it won't connect until a command is executed
            self._client = redis.Redis(**connection_kwargs)
            logger.info(f"Initialized Redis client for {settings.redis_host}:{settings.redis_port}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            # We don't raise here to allow app startup, but subsequent calls will fail if _client is None
    
    def publish_event(self, event_data: Dict[str, Any]) -> int:
        """
        Publish event to Redis Pub/Sub channel.
        
        Args:
            event_data: Event data dictionary to publish
            
        Returns:
            Number of subscribers that received the message
        """
        try:
            if self._client is None:
                self._init_client()
                
            if self._client:
                num_subscribers = self._client.publish(
                    settings.redis_channel_name,
                    json.dumps(event_data)
                )
                logger.debug(f"Published event to '{settings.redis_channel_name}': {event_data.get('event_type')}")
                return num_subscribers
            else:
                logger.error("Redis client not initialized, cannot publish event")
                return 0
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            # We rely on redis-py's retry logic for timeouts. 
            # If it still fails (e.g. connection refused), we just log it.
            return 0
    
    def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            if self._client is None:
                self._init_client()
                
            if self._client:
                return self._client.ping()
            return False
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            logger.info("Redis connection closed")


# Global Redis client instance
redis_client = RedisClient()

