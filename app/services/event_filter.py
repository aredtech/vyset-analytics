"""
Event filtering service to prevent duplicate/repeated events.
Implements debouncing for motion, ANPR, and tracking events.

Note: Object detection now uses tracking-based filtering (ByteTrack) instead of time-based filtering.
"""

import time
from typing import Dict, Optional, Set
from app.models.event_models import MotionEvent, ANPREvent, TrackingEvent
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EventFilter:
    """
    Filters events to prevent flooding with duplicate detections.
    
    Implements:
    - Cooldown periods for motion events
    - Per-plate cooldown for ANPR events
    - Track ID deduplication for tracking events
    
    Note: Object detection filtering is now handled by tracking (see ObjectDetector with ByteTrack)
    """
    
    def __init__(
        self,
        camera_id: str,
        detection_cooldown: float = 0.0,  # Deprecated - kept for backward compatibility
        motion_cooldown: float = 2.0,
        anpr_cooldown: float = 3.0,
        change_threshold: float = 0.0  # Deprecated - kept for backward compatibility
    ):
        """
        Initialize event filter.
        
        Args:
            camera_id: Camera identifier
            detection_cooldown: (Deprecated) Not used - tracking handles detection filtering
            motion_cooldown: Seconds between motion events
            anpr_cooldown: Seconds between ANPR events for same plate
            change_threshold: (Deprecated) Not used - tracking handles detection filtering
        """
        self.camera_id = camera_id
        self.motion_cooldown = motion_cooldown
        self.anpr_cooldown = anpr_cooldown
        
        # Track last event times
        self.last_motion_time: float = 0
        self.last_anpr_times: Dict[str, float] = {}  # plate -> timestamp
        
        # Track ID deduplication - only emit events for track_id changes
        self.emitted_track_ids: Set[int] = set()  # Track IDs that have already emitted "entered" events
        
        # Generic manual cooldowns
        self.manual_cooldowns: Dict[str, float] = {}
        
        
        # Track violations per track_id to prevent duplicates for same vehicle
        self.active_track_violations: Dict[int, Set[str]] = {}
        
        logger.info(f"EventFilter initialized for camera {camera_id} (motion_cooldown={motion_cooldown}s, anpr_cooldown={anpr_cooldown}s)")
    
    def can_publish(self, key: str, cooldown: float) -> bool:
        """
        Generic rate limiter for arbitrary keys.
        
        Args:
            key: Unique identifier for the event
            cooldown: Cooldown in seconds
            
        Returns:
            True if allowed to publish, False otherwise
        """
        current_time = time.time()
        last_time = self.manual_cooldowns.get(key, 0)
        
        if current_time - last_time < cooldown:
            return False
            
        self.manual_cooldowns[key] = current_time
        
        # Periodic cleanup (simple check)
        if len(self.manual_cooldowns) > 1000:
            self._cleanup_manual_cooldowns(current_time)
            
        return True

    def _cleanup_manual_cooldowns(self, current_time: float, max_age: float = 300.0):
        """Remove old manual cooldown entries."""
        keys_to_remove = [k for k, t in self.manual_cooldowns.items() if current_time - t > max_age]
        for k in keys_to_remove:
            del self.manual_cooldowns[k]
    
    def should_publish_motion(self, event: MotionEvent) -> bool:
        """
        Determine if a motion event should be published.
        
        Args:
            event: Motion event to evaluate
            
        Returns:
            True if event should be published, False otherwise
        """
        current_time = time.time()
        time_since_last = current_time - self.last_motion_time
        
        # Check cooldown period
        if time_since_last < self.motion_cooldown:
            logger.debug(f"Camera {self.camera_id}: Motion in cooldown period ({time_since_last:.1f}s < {self.motion_cooldown}s)")
            return False
        
        logger.info(f"Camera {self.camera_id}: Motion event passed cooldown - publishing (intensity: {event.motion_intensity:.2f})")
        self.last_motion_time = current_time
        return True
    
    def should_publish_anpr(self, event: ANPREvent) -> bool:
        """
        Determine if an ANPR event should be published.
        
        Uses per-plate cooldown to avoid duplicate events for the same license plate.
        
        Args:
            event: ANPR event to evaluate
            
        Returns:
            True if event should be published, False otherwise
        """
        current_time = time.time()
        plate = event.anpr_result.license_plate
        
        # Check if we've seen this plate recently
        last_time = self.last_anpr_times.get(plate, 0)
        time_since_last = current_time - last_time
        
        # Check cooldown period
        if time_since_last < self.anpr_cooldown:
            logger.debug(f"Camera {self.camera_id}: ANPR for plate '{plate}' in cooldown period ({time_since_last:.1f}s < {self.anpr_cooldown}s)")
            return False
        
        logger.info(f"Camera {self.camera_id}: ANPR event for plate '{plate}' passed cooldown - publishing")
        self.last_anpr_times[plate] = current_time
        
        # Clean up old plates to prevent memory growth
        self._cleanup_old_anpr_entries(current_time)
        
        return True
    
    def should_publish_violation(self, track_id: int, violation_type: str) -> bool:
        """
        Determine if a violation should be published for a specific track.
        
        Ensures that a specific violation type is only published ONCE per track ID.
        
        Args:
            track_id: Tracking ID of the object
            violation_type: Type of violation (e.g. "no_helmet", "tripling")
            
        Returns:
            True if violation should be published, False otherwise
        """
        # Initialize set for this track if not exists
        if track_id not in self.active_track_violations:
            self.active_track_violations[track_id] = set()
            
        # Check if already published
        if violation_type in self.active_track_violations[track_id]:
            vehicle_violations = list(self.active_track_violations[track_id])
            logger.debug(f"Camera {self.camera_id}: Violation '{violation_type}' already published for track {track_id} (active: {vehicle_violations}) - skipping")
            return False
            
        # Add to set and allow publishing
        self.active_track_violations[track_id].add(violation_type)
        logger.info(f"Camera {self.camera_id}: New violation '{violation_type}' for track {track_id} - publishing")
        return True
    
    def should_publish_tracking(self, event: TrackingEvent) -> bool:
        """
        Determine if a tracking event should be published.
        
        Implements track_id deduplication to prevent duplicate events for the same object.
        Only allows "entered" events for new track_ids and "left" events for objects that have left.
        
        Args:
            event: Tracking event to evaluate
            
        Returns:
            True if event should be published, False otherwise
        """
        track_id = event.track_id
        action = event.tracking_action
        
        if action == "entered":
            # Only emit "entered" event if we haven't seen this track_id before
            if track_id in self.emitted_track_ids:
                logger.debug(f"Camera {self.camera_id}: Track ID {track_id} already emitted 'entered' event - skipping")
                return False
            
            # Mark this track_id as having emitted an "entered" event
            self.emitted_track_ids.add(track_id)
            logger.info(f"Camera {self.camera_id}: Tracking event 'entered' for {event.class_name} (track_id={track_id}) - publishing")
            return True
            
        elif action == "left":
            # Only emit "left" event if we've previously emitted an "entered" event for this track_id
            if track_id not in self.emitted_track_ids:
                logger.debug(f"Camera {self.camera_id}: Track ID {track_id} never emitted 'entered' event - skipping 'left' event")
                return False
            
            # Remove from emitted set since object has left
            self.emitted_track_ids.discard(track_id)
            
            # Clean up violation state for this track
            if track_id in self.active_track_violations:
                del self.active_track_violations[track_id]
                
            logger.info(f"Camera {self.camera_id}: Tracking event 'left' for {event.class_name} (track_id={track_id}) - publishing")
            return True
            
        elif action == "updated":
            # Skip "updated" events to reduce noise - only emit enter/leave events
            logger.debug(f"Camera {self.camera_id}: Skipping 'updated' event for track_id={track_id} to reduce noise")
            return False
            
        else:
            logger.warning(f"Camera {self.camera_id}: Unknown tracking action '{action}' for track_id={track_id}")
            return False
    
    def _cleanup_old_anpr_entries(self, current_time: float, max_age: float = 300.0):
        """
        Remove old ANPR entries to prevent memory growth.
        
        Args:
            current_time: Current timestamp
            max_age: Maximum age in seconds to keep entries (default 5 minutes)
        """
        plates_to_remove = [
            plate for plate, timestamp in self.last_anpr_times.items()
            if current_time - timestamp > max_age
        ]
        
        for plate in plates_to_remove:
            del self.last_anpr_times[plate]
        
        if plates_to_remove:
            logger.debug(f"Camera {self.camera_id}: Cleaned up {len(plates_to_remove)} old ANPR entries")
    
    def reset(self):
        """Reset all filter state."""
        self.last_motion_time = 0
        self.last_anpr_times.clear()
        self.last_anpr_times.clear()
        self.emitted_track_ids.clear()
        self.active_track_violations.clear()
        logger.info(f"Camera {self.camera_id}: Event filter reset")

