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
        self._connect()
    
    def _connect(self):
        """Establish connection to Redis."""
        try:
            self._client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                decode_responses=True
            )
            self._client.ping()
            logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
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
            num_subscribers = self._client.publish(
                settings.redis_channel_name,
                json.dumps(event_data)
            )
            logger.info(f"Published event to channel '{settings.redis_channel_name}': {event_data.get('event_type')} (subscribers: {num_subscribers})")
            return num_subscribers
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise
    
    def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            return self._client.ping()
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

