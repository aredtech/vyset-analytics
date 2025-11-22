"""
Event retention service for managing event cleanup based on camera retention policies.
"""
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.db_models import EventRecord
from app.models.event_models import CameraConfig
from app.core.database import get_db_context
from app.utils.logger import get_logger
from app.utils.snapshot import snapshot_manager

logger = get_logger(__name__)


class RetentionService:
    """Service for managing event retention and cleanup."""
    
    def __init__(self):
        """Initialize retention service."""
        logger.info("Initializing RetentionService")
    
    def cleanup_events_for_camera(self, camera_id: str, retention_days: int) -> Tuple[int, int]:
        """
        Clean up events for a specific camera based on retention policy.
        
        Args:
            camera_id: Camera identifier
            retention_days: Number of days to retain events
            
        Returns:
            Tuple of (deleted_events_count, deleted_snapshots_count)
        """
        logger.info(f"Starting cleanup for camera {camera_id} with retention_days={retention_days}")
        
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        deleted_events = 0
        deleted_snapshots = 0
        
        try:
            with get_db_context() as db:
                # Get events to be deleted
                events_to_delete = db.query(EventRecord).filter(
                    and_(
                        EventRecord.camera_id == camera_id,
                        EventRecord.timestamp < cutoff_date
                    )
                ).all()
                
                logger.info(f"Found {len(events_to_delete)} events to delete for camera {camera_id}")
                
                # Delete associated snapshot files first
                snapshot_paths = []
                for event in events_to_delete:
                    if event.snapshot_path:
                        snapshot_paths.append(event.snapshot_path)
                
                # Delete snapshot files
                for snapshot_path in snapshot_paths:
                    try:
                        if snapshot_manager.delete_snapshot(snapshot_path):
                            deleted_snapshots += 1
                        else:
                            logger.warning(f"Failed to delete snapshot: {snapshot_path}")
                    except Exception as e:
                        logger.error(f"Error deleting snapshot {snapshot_path}: {e}")
                
                # Delete events from database
                if events_to_delete:
                    event_ids = [event.id for event in events_to_delete]
                    deleted_count = db.query(EventRecord).filter(
                        EventRecord.id.in_(event_ids)
                    ).delete(synchronize_session=False)
                    
                    db.commit()
                    deleted_events = deleted_count
                    
                    logger.info(f"Deleted {deleted_events} events and {deleted_snapshots} snapshots for camera {camera_id}")
                else:
                    logger.info(f"No events to delete for camera {camera_id}")
                
                return deleted_events, deleted_snapshots
                
        except Exception as e:
            logger.error(f"Error during cleanup for camera {camera_id}: {e}", exc_info=True)
            return 0, 0
    
    def cleanup_all_cameras(self, camera_configs: Dict[str, CameraConfig]) -> Dict[str, Dict[str, int]]:
        """
        Clean up events for all cameras based on their individual retention policies.
        
        Args:
            camera_configs: Dictionary of camera_id -> CameraConfig
            
        Returns:
            Dictionary with cleanup results per camera
        """
        logger.info(f"Starting cleanup for {len(camera_configs)} cameras")
        
        results = {}
        total_deleted_events = 0
        total_deleted_snapshots = 0
        
        for camera_id, config in camera_configs.items():
            try:
                deleted_events, deleted_snapshots = self.cleanup_events_for_camera(
                    camera_id, 
                    config.parameters.retention_days
                )
                
                results[camera_id] = {
                    "deleted_events": deleted_events,
                    "deleted_snapshots": deleted_snapshots,
                    "retention_days": config.parameters.retention_days
                }
                
                total_deleted_events += deleted_events
                total_deleted_snapshots += deleted_snapshots
                
            except Exception as e:
                logger.error(f"Error cleaning up camera {camera_id}: {e}", exc_info=True)
                results[camera_id] = {
                    "deleted_events": 0,
                    "deleted_snapshots": 0,
                    "retention_days": config.parameters.retention_days,
                    "error": str(e)
                }
        
        logger.info(f"Cleanup completed: {total_deleted_events} events and {total_deleted_snapshots} snapshots deleted across all cameras")
        
        return results
    
    def get_retention_stats(self, camera_configs: Dict[str, CameraConfig]) -> Dict[str, Dict]:
        """
        Get retention statistics for all cameras.
        
        Args:
            camera_configs: Dictionary of camera_id -> CameraConfig
            
        Returns:
            Dictionary with retention statistics per camera
        """
        logger.info(f"Getting retention stats for {len(camera_configs)} cameras")
        
        stats = {}
        
        try:
            with get_db_context() as db:
                for camera_id, config in camera_configs.items():
                    try:
                        # Get total events count
                        total_events = db.query(EventRecord).filter(
                            EventRecord.camera_id == camera_id
                        ).count()
                        
                        # Get events within retention period
                        cutoff_date = datetime.utcnow() - timedelta(days=config.parameters.retention_days)
                        events_within_retention = db.query(EventRecord).filter(
                            and_(
                                EventRecord.camera_id == camera_id,
                                EventRecord.timestamp >= cutoff_date
                            )
                        ).count()
                        
                        # Get events outside retention period (would be deleted)
                        events_outside_retention = total_events - events_within_retention
                        
                        # Get oldest and newest event timestamps
                        oldest_event = db.query(EventRecord).filter(
                            EventRecord.camera_id == camera_id
                        ).order_by(EventRecord.timestamp.asc()).first()
                        
                        newest_event = db.query(EventRecord).filter(
                            EventRecord.camera_id == camera_id
                        ).order_by(EventRecord.timestamp.desc()).first()
                        
                        stats[camera_id] = {
                            "retention_days": config.parameters.retention_days,
                            "total_events": total_events,
                            "events_within_retention": events_within_retention,
                            "events_outside_retention": events_outside_retention,
                            "oldest_event": oldest_event.timestamp.isoformat() if oldest_event else None,
                            "newest_event": newest_event.timestamp.isoformat() if newest_event else None,
                            "cutoff_date": cutoff_date.isoformat()
                        }
                        
                    except Exception as e:
                        logger.error(f"Error getting stats for camera {camera_id}: {e}", exc_info=True)
                        stats[camera_id] = {
                            "retention_days": config.parameters.retention_days,
                            "error": str(e)
                        }
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting retention stats: {e}", exc_info=True)
            return {}
    


# Global retention service instance
retention_service = RetentionService()
