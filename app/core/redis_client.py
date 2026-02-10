import redis
import json
from typing import Dict, Any
from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class RedisClient:
    """Redis client wrapper for Pub/Sub operations."""
    
    def __init__(self):
        self._client = None
        self._connected = False
    
    def _ensure_connected(self):
        """Ensure Redis connection is established (lazy initialization)."""
        if self._client is None or not self._connected:
            self._connect()
    
    def _connect(self):
        """Establish connection to Redis."""
        try:
            connection_kwargs = {
                "host": settings.redis_host,
                "port": settings.redis_port,
                "db": settings.redis_db,
                "decode_responses": True,
                "socket_connect_timeout": 5,
                "socket_timeout": 5
            }
            # Add password if configured
            if settings.redis_password:
                connection_kwargs["password"] = settings.redis_password
            
            self._client = redis.Redis(**connection_kwargs)
            self._client.ping()
            self._connected = True
            logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            self._connected = False
            logger.error(f"Failed to connect to Redis: {e}")
            # Don't raise - allow app to start without Redis
            raise
    
    def publish_event(self, event_data: Dict[str, Any]) -> int:
        """
        Publish event to Redis Pub/Sub channel.
        
        Args:
            event_data: Event data dictionary to publish
            
        Returns:
            Number of subscribers that received the message
        """
        try:
            self._ensure_connected()
            num_subscribers = self._client.publish(
                settings.redis_channel_name,
                json.dumps(event_data)
            )
            logger.info(f"Published event to channel '{settings.redis_channel_name}': {event_data.get('event_type')} (subscribers: {num_subscribers})")
            return num_subscribers
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            self._connected = False  # Mark as disconnected for retry
            raise
    
    def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            self._ensure_connected()
            return self._client.ping()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            self._connected = False
            return False
    
    def close(self):
        """Close Redis connection."""
        if self._client:
            self._client.close()
            logger.info("Redis connection closed")


# Global Redis client instance (lazy initialization - connects on first use)
redis_client = RedisClient()

