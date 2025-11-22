"""
Scheduled cleanup task for event retention.
"""
import asyncio
import threading
import time
from datetime import datetime, timedelta
from typing import Dict

from app.services.retention import retention_service
from app.services.video_worker import camera_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RetentionScheduler:
    """Scheduler for running retention cleanup tasks."""
    
    def __init__(self, cleanup_interval_hours: int = 24):
        """
        Initialize retention scheduler.
        
        Args:
            cleanup_interval_hours: Hours between cleanup runs (default: 24)
        """
        self.cleanup_interval_hours = cleanup_interval_hours
        self.cleanup_interval_seconds = cleanup_interval_hours * 3600
        self.running = False
        self.thread = None
        self.last_cleanup = None
        
        logger.info(f"RetentionScheduler initialized with {cleanup_interval_hours}h interval")
    
    def start(self):
        """Start the retention scheduler."""
        if self.running:
            logger.warning("RetentionScheduler is already running")
            return
        
        logger.info("Starting RetentionScheduler")
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        logger.info("RetentionScheduler started successfully")
    
    def stop(self):
        """Stop the retention scheduler."""
        if not self.running:
            logger.debug("RetentionScheduler is not running")
            return
        
        logger.info("Stopping RetentionScheduler")
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                logger.warning("RetentionScheduler thread did not stop within timeout")
            else:
                logger.info("RetentionScheduler stopped successfully")
    
    def _run_scheduler(self):
        """Main scheduler loop."""
        logger.info("RetentionScheduler thread started")
        
        # Run initial cleanup after a short delay
        time.sleep(30)  # Wait 30 seconds for system to stabilize
        
        while self.running:
            try:
                # Check if it's time for cleanup
                if self._should_run_cleanup():
                    logger.info("Starting scheduled retention cleanup")
                    self._run_cleanup()
                    self.last_cleanup = datetime.utcnow()
                    logger.info("Scheduled retention cleanup completed")
                
                # Sleep for a shorter interval to check more frequently
                time.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in retention scheduler: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute before retrying
        
        logger.info("RetentionScheduler thread stopped")
    
    def _should_run_cleanup(self) -> bool:
        """
        Check if cleanup should run based on interval.
        
        Returns:
            True if cleanup should run, False otherwise
        """
        if self.last_cleanup is None:
            return True
        
        time_since_last = datetime.utcnow() - self.last_cleanup
        return time_since_last.total_seconds() >= self.cleanup_interval_seconds
    
    def _run_cleanup(self):
        """Run the retention cleanup process."""
        try:
            # Get current camera configurations
            camera_configs = camera_manager.list_cameras()
            
            if not camera_configs:
                logger.info("No cameras configured, skipping retention cleanup")
                return
            
            logger.info(f"Running retention cleanup for {len(camera_configs)} cameras")
            
            # Run cleanup for all cameras
            results = retention_service.cleanup_all_cameras(camera_configs)
            
            # Log summary
            total_deleted_events = sum(result.get("deleted_events", 0) for result in results.values())
            total_deleted_snapshots = sum(result.get("deleted_snapshots", 0) for result in results.values())
            
            logger.info(f"Retention cleanup summary: {total_deleted_events} events, {total_deleted_snapshots} snapshots deleted")
            
            # Log per-camera results
            for camera_id, result in results.items():
                if "error" in result:
                    logger.error(f"Camera {camera_id}: {result['error']}")
                else:
                    logger.info(f"Camera {camera_id}: {result['deleted_events']} events, {result['deleted_snapshots']} snapshots deleted")
            
        except Exception as e:
            logger.error(f"Error during retention cleanup: {e}", exc_info=True)
    
    def run_cleanup_now(self) -> Dict:
        """
        Manually trigger cleanup process.
        
        Returns:
            Dictionary with cleanup results
        """
        logger.info("Manual retention cleanup triggered")
        
        try:
            camera_configs = camera_manager.list_cameras()
            
            if not camera_configs:
                return {"message": "No cameras configured", "results": {}}
            
            # Run cleanup
            results = retention_service.cleanup_all_cameras(camera_configs)
            
            # Calculate totals
            total_deleted_events = sum(result.get("deleted_events", 0) for result in results.values())
            total_deleted_snapshots = sum(result.get("deleted_snapshots", 0) for result in results.values())
            
            self.last_cleanup = datetime.utcnow()
            
            return {
                "message": "Manual cleanup completed",
                "results": results,
                "summary": {
                    "total_deleted_events": total_deleted_events,
                    "total_deleted_snapshots": total_deleted_snapshots,
                    "cameras_processed": len(camera_configs)
                }
            }
            
        except Exception as e:
            logger.error(f"Error during manual cleanup: {e}", exc_info=True)
            return {"error": str(e)}
    
    def get_status(self) -> Dict:
        """
        Get scheduler status information.
        
        Returns:
            Dictionary with scheduler status
        """
        return {
            "running": self.running,
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "last_cleanup": self.last_cleanup.isoformat() if self.last_cleanup else None,
            "next_cleanup": self._get_next_cleanup_time(),
            "thread_alive": self.thread.is_alive() if self.thread else False
        }
    
    def _get_next_cleanup_time(self) -> str:
        """
        Get next scheduled cleanup time.
        
        Returns:
            ISO format string of next cleanup time
        """
        if self.last_cleanup is None:
            return datetime.utcnow().isoformat()
        
        next_cleanup = self.last_cleanup + timedelta(seconds=self.cleanup_interval_seconds)
        return next_cleanup.isoformat()


# Global retention scheduler instance
retention_scheduler = RetentionScheduler()
