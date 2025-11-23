import cv2
import threading
import time
import os
from datetime import datetime
from typing import Dict, Optional
from app.models.event_models import CameraConfig, CameraStatus, Detection
from app.models.db_models import EventRecord
from app.services.detection import ObjectDetector
from app.services.motion import MotionDetector
from app.services.anpr import ANPRDetector
from app.services.garbage_detection import GarbageDetector
from app.services.event_filter import EventFilter
from app.core.redis_client import redis_client
from app.core.database import get_db_context
from app.utils.snapshot import snapshot_manager
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Set environment variable to force RTSP over TCP for better reliability
# This helps avoid UDP packet loss and timeout issues
os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS', 'rtsp_transport;tcp')


def save_and_publish_event(
    event_type: str,
    camera_id: str,
    timestamp: str,
    frame_number: int,
    snapshot_path: Optional[str],
    event_data: dict,
    camera_name: Optional[str] = None
) -> Optional[int]:
    """
    Save event to database and publish to Redis Pub/Sub.
    This ensures all events are persisted and available for real-time consumption.
    
    Args:
        event_type: Type of event (detection, motion, anpr, tracking)
        camera_id: Camera identifier
        timestamp: Event timestamp in ISO format
        frame_number: Frame number
        snapshot_path: Path to snapshot image (if available)
        event_data: Event-specific data as dictionary
        camera_name: Human-readable camera name (optional)
        
    Returns:
        Event ID from database if successful, None otherwise
    """
    try:
        # Save to database
        with get_db_context() as db:
            # Convert ISO timestamp to datetime
            timestamp_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            event_record = EventRecord(
                event_type=event_type,
                camera_id=camera_id,
                camera_name=camera_name,
                timestamp=timestamp_dt,
                frame_number=frame_number,
                snapshot_path=snapshot_path,
                event_data=event_data
            )
            db.add(event_record)
            db.commit()
            db.refresh(event_record)
            
            event_id = event_record.id
            logger.debug(f"Saved {event_type} event to database (ID: {event_id})")
            
            # Publish to Redis Pub/Sub
            try:
                redis_event_data = {
                    "id": event_id,
                    "event_type": event_type,
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "timestamp": timestamp,
                    "frame_number": frame_number,
                    "snapshot_path": snapshot_path,
                    "event_data": event_data,
                    "created_at": event_record.created_at.isoformat()
                }
                num_subscribers = redis_client.publish_event(redis_event_data)
                logger.debug(f"Published {event_type} event to Redis Pub/Sub (subscribers: {num_subscribers})")
            except Exception as redis_e:
                logger.error(f"Failed to publish {event_type} event to Redis: {redis_e}", exc_info=True)
            
            return event_id
            
    except Exception as e:
        logger.error(f"Failed to save and publish {event_type} event: {e}", exc_info=True)
        return None


class CameraWorker:
    """Worker thread for processing a single camera stream."""
    
    def __init__(self, config: CameraConfig):
        """
        Initialize camera worker.
        
        Args:
            config: Camera configuration
        """
        logger.debug(f"Initializing CameraWorker for camera {config.camera_id}")
        
        self.config = config
        
        # Replace localhost with mediamtx for dockerized environment
        if "localhost" in self.config.stream_url:
            old_url = self.config.stream_url
            self.config.stream_url = self.config.stream_url.replace("localhost", "mediamtx")
            logger.info(f"Camera {config.camera_id}: Replaced localhost with mediamtx in stream URL. Old: {old_url}, New: {self.config.stream_url}")
            
        self.camera_id = config.camera_id
        self.running = False
        self.thread = None
        self.cap = None
        self.frame_count = 0
        
        # Initialize event filter (only for motion and ANPR now)
        self.event_filter = EventFilter(
            camera_id=config.camera_id,
            detection_cooldown=0.0,  # Not used anymore
            motion_cooldown=config.parameters.motion_cooldown_seconds,
            anpr_cooldown=config.parameters.anpr_cooldown_seconds,
            change_threshold=0.0  # Not used anymore
        )
        
        # Initialize detectors
        self.object_detector = None
        self.motion_detector = None
        self.anpr_detector = None
        self.garbage_detector = None
        
        logger.debug(f"Camera {self.camera_id}: Initializing detectors (object_detection={config.parameters.enable_object_detection}, motion_detection={config.parameters.enable_motion_detection}, garbage_detection={config.parameters.enable_garbage_detection}, anpr={config.parameters.enable_anpr})")
        
        if config.parameters.enable_object_detection:
            logger.debug(f"Camera {self.camera_id}: Creating ObjectDetector with tracking")
            self.object_detector = ObjectDetector(
                enable_tracking=config.parameters.enable_object_tracking,
                track_buffer_frames=config.parameters.track_buffer_frames,
                min_dwell_time_seconds=config.parameters.min_dwell_time_seconds
            )
            logger.debug(f"Camera {self.camera_id}: ObjectDetector initialized with tracking={config.parameters.enable_object_tracking}")
        
        if config.parameters.enable_motion_detection:
            logger.debug(f"Camera {self.camera_id}: Creating MotionDetector")
            self.motion_detector = MotionDetector()
            logger.debug(f"Camera {self.camera_id}: MotionDetector initialized")
        
        if config.parameters.enable_garbage_detection:
            logger.debug(f"Camera {self.camera_id}: Creating GarbageDetector with tracking={config.parameters.enable_garbage_tracking}")
            self.garbage_detector = GarbageDetector(
                enable_tracking=config.parameters.enable_garbage_tracking,
                track_buffer_frames=config.parameters.garbage_track_buffer_frames,
                min_dwell_time_seconds=config.parameters.garbage_min_dwell_time_seconds,
                tracking_confidence_threshold=config.parameters.garbage_tracking_confidence_threshold
            )
            logger.debug(f"Camera {self.camera_id}: GarbageDetector initialized with tracking={config.parameters.enable_garbage_tracking}")
        
        if config.parameters.enable_anpr:
            logger.debug(f"Camera {self.camera_id}: Creating ANPRDetector")
            self.anpr_detector = ANPRDetector()
            logger.debug(f"Camera {self.camera_id}: ANPRDetector initialized")
        
        logger.info(f"Camera {self.camera_id}: CameraWorker initialized successfully (stream_url={config.stream_url})")
    
    def start(self):
        """Start the camera processing thread."""
        logger.debug(f"Camera {self.camera_id}: start() called")
        
        if self.running:
            logger.warning(f"Camera {self.camera_id} is already running")
            return
        
        logger.debug(f"Camera {self.camera_id}: Creating processing thread")
        self.running = True
        self.thread = threading.Thread(target=self._process_stream, daemon=True)
        self.thread.start()
        logger.info(f"Camera {self.camera_id}: Started camera worker thread (thread_id={self.thread.ident})")
    
    def stop(self):
        """Stop the camera processing thread."""
        logger.debug(f"Camera {self.camera_id}: stop() called")
        
        if not self.running:
            logger.debug(f"Camera {self.camera_id}: Already stopped")
            return
        
        logger.info(f"Camera {self.camera_id}: Stopping camera worker...")
        self.running = False
        
        if self.thread:
            logger.debug(f"Camera {self.camera_id}: Waiting for thread to join (timeout=5s)")
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                logger.warning(f"Camera {self.camera_id}: Thread did not stop within timeout")
            else:
                logger.debug(f"Camera {self.camera_id}: Thread stopped successfully")
        
        if self.cap:
            logger.debug(f"Camera {self.camera_id}: Releasing video capture")
            self.cap.release()
            logger.debug(f"Camera {self.camera_id}: Video capture released")
        
        logger.info(f"Camera {self.camera_id}: Camera worker stopped successfully")
    
    def _connect_to_stream(self) -> bool:
        """
        Connect to video stream.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info(f"Connecting to stream: {self.config.stream_url}")
            
            # For RTSP streams, use CAP_FFMPEG backend with specific options
            # Use TCP transport instead of UDP to avoid packet loss issues
            if self.config.stream_url.startswith('rtsp://'):
                logger.debug(f"Camera {self.camera_id}: Configuring RTSP stream with TCP transport")
                logger.debug(f"Camera {self.camera_id}: OPENCV_FFMPEG_CAPTURE_OPTIONS={os.environ.get('OPENCV_FFMPEG_CAPTURE_OPTIONS', 'not set')}")
                
                capture_start = time.time()
                self.cap = cv2.VideoCapture(self.config.stream_url, cv2.CAP_FFMPEG)
                capture_time = time.time() - capture_start
                logger.debug(f"Camera {self.camera_id}: VideoCapture object created in {capture_time:.3f}s")
                
                # Set properties before opening is not possible with OpenCV directly
                # So we set them after opening
                if not self.cap.isOpened():
                    logger.error(f"Camera {self.camera_id}: Failed to open stream (isOpened=False)")
                    return False
                
                logger.debug(f"Camera {self.camera_id}: Stream opened successfully (isOpened=True)")
                
                # Configure stream properties for better RTSP handling
                logger.debug(f"Camera {self.camera_id}: Setting buffer size to 3")
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)  # Small buffer to reduce latency
                logger.debug(f"Camera {self.camera_id}: Setting max FPS to {self.config.parameters.max_fps}")
                self.cap.set(cv2.CAP_PROP_FPS, self.config.parameters.max_fps)
                
                # Try to read first frame to verify stream is working
                logger.debug(f"Camera {self.camera_id}: Attempting to read first frame to verify stream...")
                test_frame_start = time.time()
                ret, test_frame = self.cap.read()
                test_frame_time = time.time() - test_frame_start
                
                if not ret or test_frame is None:
                    logger.error(f"Camera {self.camera_id}: Failed to read test frame from stream (ret={ret}, frame={'None' if test_frame is None else 'exists'}, time={test_frame_time:.3f}s)")
                    self.cap.release()
                    return False
                
                logger.debug(f"Camera {self.camera_id}: Successfully read test frame (shape: {test_frame.shape}, time: {test_frame_time:.3f}s)")
            else:
                # For non-RTSP streams (file, HTTP, etc.)
                logger.debug(f"Camera {self.camera_id}: Opening non-RTSP stream")
                capture_start = time.time()
                self.cap = cv2.VideoCapture(self.config.stream_url)
                capture_time = time.time() - capture_start
                logger.debug(f"Camera {self.camera_id}: VideoCapture object created in {capture_time:.3f}s")
                
                if not self.cap.isOpened():
                    logger.error(f"Camera {self.camera_id}: Failed to open stream (isOpened=False)")
                    return False
                
                logger.debug(f"Camera {self.camera_id}: Stream opened successfully (isOpened=True)")
                logger.debug(f"Camera {self.camera_id}: Setting buffer size to 1")
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            logger.info(f"Successfully connected to stream for camera {self.camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to stream for camera {self.camera_id}: {e}", exc_info=True)
            return False
    
    def _process_stream(self):
        """Main processing loop for camera stream."""
        # Retry connection every 10 seconds until successful
        logger.info(f"Camera {self.camera_id}: Attempting initial connection...")
        while self.running:
            if self._connect_to_stream():
                logger.info(f"Camera {self.camera_id}: Initial connection successful")
                break
            else:
                logger.warning(f"Camera {self.camera_id}: Initial connection failed, retrying in 10 seconds...")
                # Wait 10 seconds before retrying, but check self.running periodically
                for _ in range(10):
                    if not self.running:
                        logger.info(f"Camera {self.camera_id}: Worker stopped during connection retry")
                        return
                    time.sleep(1)
        
        # If we exited the connection loop because running is False, cleanup and return
        if not self.running:
            logger.info(f"Camera {self.camera_id}: Worker stopped before connection established")
            return
        
        frame_skip_counter = 0
        last_frame_time = time.time()
        target_frame_interval = 1.0 / self.config.parameters.max_fps
        
        logger.info(f"Camera {self.camera_id}: Starting frame processing loop (max_fps={self.config.parameters.max_fps}, frame_skip={self.config.parameters.frame_skip})")
        
        while self.running:
            try:
                # Check if stream is still open
                if self.cap is None or not self.cap.isOpened():
                    logger.warning(f"Camera {self.camera_id}: Stream connection lost, attempting to reconnect...")
                    if self.cap:
                        self.cap.release()
                    # Retry connection every 10 seconds
                    while self.running:
                        if self._connect_to_stream():
                            logger.info(f"Camera {self.camera_id}: Reconnected successfully")
                            break
                        else:
                            logger.warning(f"Camera {self.camera_id}: Reconnection failed, retrying in 10 seconds...")
                            # Wait 10 seconds before retrying, but check self.running periodically
                            for _ in range(10):
                                if not self.running:
                                    logger.info(f"Camera {self.camera_id}: Worker stopped during reconnection retry")
                                    return
                                time.sleep(1)
                    
                    # If we exited the reconnection loop because running is False, cleanup and return
                    if not self.running:
                        logger.info(f"Camera {self.camera_id}: Worker stopped during reconnection")
                        if self.cap:
                            self.cap.release()
                        return
                    
                    # Reset frame counter after reconnection
                    frame_skip_counter = 0
                    last_frame_time = time.time()
                    continue
                
                # Enforce max FPS
                current_time = time.time()
                elapsed = current_time - last_frame_time
                if elapsed < target_frame_interval:
                    time.sleep(target_frame_interval - elapsed)
                
                # Read frame
                logger.debug(f"Camera {self.camera_id}: Attempting to read frame #{self.frame_count + 1}")
                ret, frame = self.cap.read()
                
                if not ret or frame is None:
                    logger.warning(f"Camera {self.camera_id}: Failed to read frame, will reconnect...")
                    # Release current connection
                    if self.cap:
                        self.cap.release()
                    # Retry connection every 10 seconds
                    while self.running:
                        if self._connect_to_stream():
                            logger.info(f"Camera {self.camera_id}: Reconnected after frame read failure")
                            break
                        else:
                            logger.warning(f"Camera {self.camera_id}: Reconnection failed, retrying in 10 seconds...")
                            # Wait 10 seconds before retrying, but check self.running periodically
                            for _ in range(10):
                                if not self.running:
                                    logger.info(f"Camera {self.camera_id}: Worker stopped during reconnection retry")
                                    return
                                time.sleep(1)
                    
                    # If we exited the reconnection loop because running is False, cleanup and return
                    if not self.running:
                        logger.info(f"Camera {self.camera_id}: Worker stopped during reconnection")
                        if self.cap:
                            self.cap.release()
                        return
                    
                    # Reset frame counter after reconnection
                    frame_skip_counter = 0
                    last_frame_time = time.time()
                    continue
                
                # Successfully read frame
                self.frame_count += 1
                last_frame_time = time.time()
                
                if self.frame_count % 100 == 0:
                    logger.info(f"Camera {self.camera_id}: Successfully processed {self.frame_count} frames")
                
                # Apply frame skip
                frame_skip_counter += 1
                if frame_skip_counter < self.config.parameters.frame_skip:
                    logger.debug(f"Camera {self.camera_id}: Skipping frame #{self.frame_count} (skip {frame_skip_counter}/{self.config.parameters.frame_skip})")
                    continue
                frame_skip_counter = 0
                
                # Process frame
                self._process_frame(frame)
                
            except Exception as e:
                logger.error(f"Camera {self.camera_id}: Error in processing loop: {e}", exc_info=True)
                
                # On exception, try to reconnect
                if self.cap:
                    try:
                        self.cap.release()
                    except:
                        pass
                
                # Retry connection every 10 seconds
                while self.running:
                    if self._connect_to_stream():
                        logger.info(f"Camera {self.camera_id}: Reconnected after exception")
                        break
                    else:
                        logger.warning(f"Camera {self.camera_id}: Reconnection failed after exception, retrying in 10 seconds...")
                        # Wait 10 seconds before retrying, but check self.running periodically
                        for _ in range(10):
                            if not self.running:
                                logger.info(f"Camera {self.camera_id}: Worker stopped during reconnection retry after exception")
                                return
                            time.sleep(1)
                
                # If we exited the reconnection loop because running is False, cleanup and return
                if not self.running:
                    logger.info(f"Camera {self.camera_id}: Worker stopped during reconnection after exception")
                    if self.cap:
                        try:
                            self.cap.release()
                        except:
                            pass
                    return
                
                # Reset frame counter after reconnection
                frame_skip_counter = 0
                last_frame_time = time.time()
        
        # Cleanup
        logger.info(f"Camera {self.camera_id}: Exiting processing loop, cleaning up...")
        if self.cap:
            try:
                self.cap.release()
            except:
                pass
    
    def _process_frame(self, frame):
        """
        Process a single frame with all enabled detectors.
        
        Args:
            frame: Video frame (numpy array)
        """
        logger.debug(f"Camera {self.camera_id}: Processing frame #{self.frame_count} (shape: {frame.shape})")
        start_time = time.time()
        
        # Object detection with tracking
        if self.object_detector and self.config.parameters.enable_object_detection:
            logger.debug(f"Camera {self.camera_id}: Running object detection with tracking on frame #{self.frame_count}")
            detect_start = time.time()
            tracking_events = self.object_detector.detect(
                frame=frame,
                camera_id=self.camera_id,
                frame_number=self.frame_count,
                confidence_threshold=self.config.parameters.confidence_threshold,
                target_classes=self.config.parameters.detection_classes
            )
            detect_time = time.time() - detect_start
            
            # Save and publish all tracking events (entered/left) to database and Redis Pub/Sub
            if tracking_events:
                for event in tracking_events:
                    # Apply tracking event filtering to prevent duplicates
                    if not self.event_filter.should_publish_tracking(event):
                        logger.debug(f"Camera {self.camera_id}: Tracking event filtered out for track_id={event.track_id}, action={event.tracking_action}")
                        continue
                    
                    # Save snapshot (only for important events: entered and left)
                    snapshot_path = None
                    if event.tracking_action in ["entered", "left"]:
                        # Create a Detection object for snapshot
                        detection = Detection(
                            class_name=event.class_name,
                            confidence=event.confidence,
                            bounding_box=event.bounding_box,
                            track_id=event.track_id
                        )
                        snapshot_path = snapshot_manager.save_detection_snapshot(
                            frame=frame,
                            camera_id=self.camera_id,
                            detections=[detection],
                            timestamp=datetime.utcnow()
                        )
                    
                    # Prepare event data
                    event_data = {
                        "track_id": event.track_id,
                        "tracking_action": event.tracking_action,
                        "class_name": event.class_name,
                        "confidence": event.confidence,
                        "bounding_box": event.bounding_box.model_dump(),
                        "dwell_time_seconds": event.dwell_time_seconds,
                        "model_info": event.model_info.model_dump() if event.model_info else None
                    }
                    
                    # Save to database and publish to Redis Pub/Sub
                    event_id = save_and_publish_event(
                        event_type="tracking",
                        camera_id=self.camera_id,
                        timestamp=event.timestamp,
                        frame_number=self.frame_count,
                        snapshot_path=snapshot_path,
                        event_data=event_data,
                        camera_name=self.config.camera_name
                    )
                    
                    if event_id:
                        logger.info(f"Camera {self.camera_id}: Saved and published tracking event '{event.tracking_action}' for {event.class_name} (track_id={event.track_id}, event_id={event_id}) in {detect_time:.3f}s")
                    else:
                        logger.error(f"Camera {self.camera_id}: Failed to save tracking event for track_id={event.track_id}")
            else:
                logger.debug(f"Camera {self.camera_id}: No tracking events in frame #{self.frame_count} ({detect_time:.3f}s)")
        
        # Motion detection
        if self.motion_detector and self.config.parameters.enable_motion_detection:
            logger.debug(f"Camera {self.camera_id}: Running motion detection on frame #{self.frame_count}")
            motion_start = time.time()
            motion_event = self.motion_detector.detect(
                frame=frame,
                camera_id=self.camera_id,
                frame_number=self.frame_count,
                motion_threshold=self.config.parameters.motion_threshold
            )
            motion_time = time.time() - motion_start
            
            if motion_event:
                # Apply event filtering to prevent duplicate motion events
                if self.event_filter.should_publish_motion(motion_event):
                    # Save snapshot with motion mask
                    snapshot_path = snapshot_manager.save_motion_snapshot(
                        frame=frame,
                        camera_id=self.camera_id,
                        timestamp=datetime.utcnow(),
                        motion_mask=self.motion_detector.motion_mask
                    )
                    
                    # Prepare event data
                    event_data = {
                        "motion_intensity": motion_event.motion_intensity,
                        "affected_area_percentage": motion_event.affected_area_percentage
                    }
                    
                    # Save to database and publish to Redis Pub/Sub
                    event_id = save_and_publish_event(
                        event_type="motion",
                        camera_id=self.camera_id,
                        timestamp=motion_event.timestamp,
                        frame_number=self.frame_count,
                        snapshot_path=snapshot_path,
                        event_data=event_data,
                        camera_name=self.config.camera_name
                    )
                    
                    if event_id:
                        logger.info(f"Camera {self.camera_id}: Saved and published motion event for frame #{self.frame_count} (motion_intensity: {motion_event.motion_intensity:.2f}, affected_area: {motion_event.affected_area_percentage:.2f}, event_id={event_id}) in {motion_time:.3f}s")
                    else:
                        logger.error(f"Camera {self.camera_id}: Failed to save motion event")
                else:
                    logger.debug(f"Camera {self.camera_id}: Motion event filtered (cooldown) for frame #{self.frame_count}")
            else:
                logger.debug(f"Camera {self.camera_id}: No motion detected in frame #{self.frame_count} ({motion_time:.3f}s)")
        
        # Garbage detection
        if self.garbage_detector and self.config.parameters.enable_garbage_detection:
            logger.debug(f"Camera {self.camera_id}: Running garbage detection on frame #{self.frame_count}")
            garbage_start = time.time()
            garbage_result = self.garbage_detector.detect(
                frame=frame,
                camera_id=self.camera_id,
                frame_number=self.frame_count,
                confidence_threshold=self.config.parameters.garbage_confidence_threshold
            )
            garbage_time = time.time() - garbage_start
            
            # Handle both detection and tracking modes
            if garbage_result:
                if self.config.parameters.enable_garbage_tracking:
                    # Tracking mode: garbage_result is a list of TrackingEvent objects
                    tracking_events = garbage_result
                    
                    # Save and publish all tracking events (entered/left) to database and Redis Pub/Sub
                    for event in tracking_events:
                        # Save snapshot (only for important events: entered and left)
                        snapshot_path = None
                        if event.tracking_action in ["entered", "left"]:
                            # Create a Detection object for snapshot
                            detection = Detection(
                                class_name=event.class_name,
                                confidence=event.confidence,
                                bounding_box=event.bounding_box,
                                track_id=event.track_id
                            )
                            snapshot_path = snapshot_manager.save_detection_snapshot(
                                frame=frame,
                                camera_id=self.camera_id,
                                detections=[detection],
                                timestamp=datetime.utcnow()
                            )
                        
                        # Prepare event data
                        event_data = {
                            "track_id": event.track_id,
                            "tracking_action": event.tracking_action,
                            "class_name": event.class_name,
                            "confidence": event.confidence,
                            "bounding_box": event.bounding_box.model_dump(),
                            "dwell_time_seconds": event.dwell_time_seconds,
                            "model_info": event.model_info.model_dump() if event.model_info else None
                        }
                        
                        # Save to database and publish to Redis Pub/Sub
                        event_id = save_and_publish_event(
                            event_type="tracking",
                            camera_id=self.camera_id,
                            timestamp=event.timestamp,
                            frame_number=self.frame_count,
                            snapshot_path=snapshot_path,
                            event_data=event_data,
                            camera_name=self.config.camera_name
                        )
                        
                        if event_id:
                            logger.info(f"Camera {self.camera_id}: Saved and published garbage tracking event '{event.tracking_action}' for {event.class_name} (track_id={event.track_id}, event_id={event_id}) in {garbage_time:.3f}s")
                        else:
                            logger.error(f"Camera {self.camera_id}: Failed to save garbage tracking event for track_id={event.track_id}")
                else:
                    # Detection mode: garbage_result is a DetectionEvent object
                    garbage_event = garbage_result
                    
                    # Save snapshot for garbage detection
                    snapshot_path = snapshot_manager.save_detection_snapshot(
                        frame=frame,
                        camera_id=self.camera_id,
                        detections=garbage_event.detections,
                        timestamp=datetime.utcnow()
                    )
                    
                    # Prepare event data
                    event_data = {
                        "detections": [detection.model_dump() for detection in garbage_event.detections],
                        "model_info": garbage_event.model_info.model_dump() if garbage_event.model_info else None
                    }
                    
                    # Save to database and publish to Redis Pub/Sub
                    event_id = save_and_publish_event(
                        event_type="detection",
                        camera_id=self.camera_id,
                        timestamp=garbage_event.timestamp,
                        frame_number=self.frame_count,
                        snapshot_path=snapshot_path,
                        event_data=event_data,
                        camera_name=self.config.camera_name
                    )
                    
                    if event_id:
                        detection_count = len(garbage_event.detections)
                        logger.info(f"Camera {self.camera_id}: Saved and published garbage detection event with {detection_count} detections (event_id={event_id}) in {garbage_time:.3f}s")
                    else:
                        logger.error(f"Camera {self.camera_id}: Failed to save garbage detection event")
            else:
                logger.debug(f"Camera {self.camera_id}: No garbage detected in frame #{self.frame_count} ({garbage_time:.3f}s)")
        
        # ANPR detection
        if self.anpr_detector and self.config.parameters.enable_anpr:
            logger.debug(f"Camera {self.camera_id}: Running ANPR detection on frame #{self.frame_count}")
            anpr_start = time.time()
            anpr_event = self.anpr_detector.detect(
                frame=frame,
                camera_id=self.camera_id,
                frame_number=self.frame_count
            )
            anpr_time = time.time() - anpr_start
            
            if anpr_event:
                # Apply event filtering to prevent duplicate ANPR events
                if self.event_filter.should_publish_anpr(anpr_event):
                    # Save snapshot
                    snapshot_path = snapshot_manager.save_anpr_snapshot(
                        frame=frame,
                        camera_id=self.camera_id,
                        anpr_result=anpr_event.anpr_result,
                        timestamp=datetime.utcnow(),
                        bounding_box=None  # Can be enhanced to get bbox from OCR
                    )
                    
                    # Prepare event data
                    event_data = {
                        "anpr_result": anpr_event.anpr_result.model_dump()
                    }
                    
                    # Save to database and publish to Redis Pub/Sub
                    event_id = save_and_publish_event(
                        event_type="anpr",
                        camera_id=self.camera_id,
                        timestamp=anpr_event.timestamp,
                        frame_number=self.frame_count,
                        snapshot_path=snapshot_path,
                        event_data=event_data,
                        camera_name=self.config.camera_name
                    )
                    
                    if event_id:
                        logger.info(f"Camera {self.camera_id}: Saved and published ANPR event for frame #{self.frame_count}: {anpr_event.anpr_result.license_plate} (confidence: {anpr_event.anpr_result.confidence:.2f}, event_id={event_id}) in {anpr_time:.3f}s")
                    else:
                        logger.error(f"Camera {self.camera_id}: Failed to save ANPR event")
                else:
                    logger.debug(f"Camera {self.camera_id}: ANPR event filtered (duplicate plate in cooldown) for frame #{self.frame_count}")
            else:
                logger.debug(f"Camera {self.camera_id}: No license plates detected in frame #{self.frame_count} ({anpr_time:.3f}s)")
        
        total_time = time.time() - start_time
        logger.debug(f"Camera {self.camera_id}: Completed processing frame #{self.frame_count} in {total_time:.3f}s")


class CameraManager:
    """Manager for all camera workers."""
    
    def __init__(self):
        """Initialize camera manager."""
        logger.debug("Initializing CameraManager")
        self.workers: Dict[str, CameraWorker] = {}
        self.lock = threading.Lock()
        logger.info("CameraManager initialized successfully")
    
    def add_camera(self, config: CameraConfig) -> bool:
        """
        Add and start a new camera.
        
        Args:
            config: Camera configuration
            
        Returns:
            True if camera added successfully, False otherwise
        """
        logger.debug(f"CameraManager: add_camera() called for {config.camera_id}")
        
        with self.lock:
            if config.camera_id in self.workers:
                logger.warning(f"CameraManager: Camera {config.camera_id} already exists")
                return False
            
            try:
                logger.debug(f"CameraManager: Creating worker for camera {config.camera_id}")
                worker = CameraWorker(config)
                
                logger.debug(f"CameraManager: Starting worker for camera {config.camera_id}")
                worker.start()
                
                self.workers[config.camera_id] = worker
                logger.info(f"CameraManager: Successfully added camera {config.camera_id} (total cameras: {len(self.workers)})")
                return True
            except Exception as e:
                logger.error(f"CameraManager: Failed to add camera {config.camera_id}: {e}", exc_info=True)
                return False
    
    def remove_camera(self, camera_id: str) -> bool:
        """
        Stop and remove a camera.
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            True if camera removed successfully, False otherwise
        """
        logger.info(f"CameraManager: remove_camera() called for {camera_id}")
        logger.debug(f"CameraManager: Current workers before removal: {list(self.workers.keys())}")
        
        with self.lock:
            if camera_id not in self.workers:
                logger.warning(f"CameraManager: Camera {camera_id} not found in workers")
                logger.debug(f"CameraManager: Available cameras: {list(self.workers.keys())}")
                return False
            
            try:
                logger.info(f"CameraManager: Stopping worker for camera {camera_id}")
                worker = self.workers[camera_id]
                worker.stop()
                
                logger.info(f"CameraManager: Deleting camera {camera_id} from workers dictionary")
                del self.workers[camera_id]
                
                logger.info(f"CameraManager: Successfully removed camera {camera_id} (remaining cameras: {list(self.workers.keys())})")
                return True
            except Exception as e:
                logger.error(f"CameraManager: Failed to remove camera {camera_id}: {e}", exc_info=True)
                return False
    
    def get_camera(self, camera_id: str) -> Optional[CameraConfig]:
        """
        Get camera configuration.
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            Camera configuration if found, None otherwise
        """
        logger.debug(f"CameraManager: get_camera() called for {camera_id}")
        
        with self.lock:
            worker = self.workers.get(camera_id)
            if worker:
                logger.debug(f"CameraManager: Found camera {camera_id}")
                return worker.config
            else:
                logger.debug(f"CameraManager: Camera {camera_id} not found")
                return None
    
    def list_cameras(self) -> Dict[str, CameraConfig]:
        """
        List all active cameras.
        
        Returns:
            Dictionary of camera_id -> CameraConfig
        """
        logger.info(f"CameraManager: list_cameras() called")
        
        with self.lock:
            camera_list = {
                camera_id: worker.config
                for camera_id, worker in self.workers.items()
            }
            logger.info(f"CameraManager: Returning {len(camera_list)} cameras: {list(camera_list.keys())}")
            return camera_list
    
    def stop_all(self):
        """Stop all camera workers."""
        logger.info(f"CameraManager: stop_all() called ({len(self.workers)} cameras to stop)")
        
        with self.lock:
            camera_ids = list(self.workers.keys())
            logger.debug(f"CameraManager: Stopping cameras: {camera_ids}")
            
            for camera_id in camera_ids:
                logger.debug(f"CameraManager: Stopping camera {camera_id}")
                # Stop and remove without calling remove_camera to avoid deadlock
                try:
                    worker = self.workers.get(camera_id)
                    if worker:
                        worker.stop()
                        del self.workers[camera_id]
                        logger.info(f"CameraManager: Successfully stopped camera {camera_id}")
                except Exception as e:
                    logger.error(f"CameraManager: Failed to stop camera {camera_id}: {e}", exc_info=True)
            
            logger.info("CameraManager: All cameras stopped successfully")


# Global camera manager instance
logger.debug("Creating global camera_manager instance")
camera_manager = CameraManager()
logger.debug("Global camera_manager instance created")

