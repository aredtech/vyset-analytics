import cv2
import threading
import queue
import time
import os
import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
import urllib.request
import json
from ultralytics import YOLO
from app.models.event_models import CameraConfig, CameraStatus, Detection, BoundingBox
from app.models.db_models import EventRecord
from app.services.detection import ObjectDetector
from app.services.motion import MotionDetector
from app.services.anpr import ANPRDetector
from app.services.garbage_detection import GarbageDetector, GARBAGE_CLASS_NAMES
from app.services.event_filter import EventFilter
from app.services.violation_detection import ViolationDetector
from app.core.redis_client import redis_client, RedisClient
from app.core.database import get_db_context
from app.utils.snapshot import snapshot_manager
from app.utils.logger import get_logger

from app.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()

class ModelManager:
    """
    Singleton manager for loading and sharing heavy AI models across threads.
    This prevents each camera thread from loading its own copy of models,
    significantly reducing memory usage.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ModelManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.yolo_model = None
        self.helmet_model = None
        self.tripling_model = None
        self.seatbelt_model = None
        self.garbage_model = None
        self._initialized = True
        logger.info("ModelManager initialized")

    def get_yolo_model(self):
        """Get or load shared YOLO object detection model."""
        with self._lock:
            if self.yolo_model is None:
                model_path = settings.yolo_model
                logger.info(f"ModelManager: Loading shared YOLO model from {model_path}")
                try:
                    self.yolo_model = YOLO(model_path)
                    logger.info("ModelManager: Shared YOLO model loaded")
                except Exception as e:
                    logger.error(f"ModelManager: Failed to load YOLO model: {e}")
            return self.yolo_model

    def get_violation_models(self):
        """Get or load shared violation detection models (helmet, tripling, seatbelt)."""
        with self._lock:
            if self.helmet_model is None and os.path.exists(settings.helmet_model):
                logger.info(f"ModelManager: Loading shared Helmet model from {settings.helmet_model}")
                try:
                    self.helmet_model = YOLO(settings.helmet_model)
                except Exception as e:
                    logger.error(f"ModelManager: Failed to load Helmet model: {e}")
            
            if self.tripling_model is None and os.path.exists(settings.tripling_model):
                logger.info(f"ModelManager: Loading shared Tripling model from {settings.tripling_model}")
                try:
                    self.tripling_model = YOLO(settings.tripling_model)
                except Exception as e:
                    logger.error(f"ModelManager: Failed to load Tripling model: {e}")
            
            if self.seatbelt_model is None and os.path.exists(settings.seatbelt_model):
                logger.info(f"ModelManager: Loading shared Seatbelt model from {settings.seatbelt_model}")
                try:
                    self.seatbelt_model = YOLO(settings.seatbelt_model)
                except Exception as e:
                    logger.error(f"ModelManager: Failed to load Seatbelt model: {e}")
                    
            return self.helmet_model, self.tripling_model, self.seatbelt_model

# Global model manager
model_manager = ModelManager()

# Set environment variable to force RTSP over TCP for better reliability
# This helps avoid UDP packet loss and timeout issues
os.environ.setdefault('OPENCV_FFMPEG_CAPTURE_OPTIONS', 'rtsp_transport;tcp')

# Vehicle classes that should trigger ANPR detection
VEHICLE_CLASSES = {'car', 'truck', 'bus', 'motorcycle', 'bicycle', 'van', 'suv'}


@dataclass
class EventTask:
    """Data class for event processing tasks."""
    event_type: str
    camera_id: str
    timestamp: str
    frame_number: int
    snapshot_path: Optional[str]
    event_data: dict
    camera_name: Optional[str] = None
    geofence_context: Optional[dict] = None


class BackgroundEventProcessor(threading.Thread):
    """Background worker for processing events asynchronously."""
    
    def __init__(self, queue_size: int = 1000):
        super().__init__(daemon=True)
        self.queue = queue.Queue(maxsize=queue_size)
        self.running = True
        self.name = "BackgroundEventProcessor"
        logger.info(f"Initialized BackgroundEventProcessor with queue size {queue_size}")
        
    def add_event(self, task: EventTask) -> bool:
        """Add event to processing queue."""
        try:
            self.queue.put(task, block=False)
            return True
        except queue.Full:
            logger.warning(f"Event queue full! Dropping event {task.event_type} for camera {task.camera_id}")
            return False
            
    def run(self):
        """Main processing loop."""
        print(f"DEBUG: BackgroundEventProcessor thread started in PID {os.getpid()}")
        logger.info("BackgroundEventProcessor started")
        while self.running:
            try:
                # Get task with timeout to allow checking self.running
                try:
                    task = self.queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Process the task
                self._process_task(task)
                
                # Mark task as done
                self.queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in BackgroundEventProcessor loop: {e}", exc_info=True)
                
        logger.info("BackgroundEventProcessor stopped")
        
    def stop(self):
        """Stop the processor."""
        self.running = False
        
    def _process_task(self, task: EventTask):
        """Process a single event task."""
        try:
            # We use the internal sync function to do the actual work
            _save_and_publish_event_sync(
                event_type=task.event_type,
                camera_id=task.camera_id,
                timestamp=task.timestamp,
                frame_number=task.frame_number,
                snapshot_path=task.snapshot_path,
                event_data=task.event_data,
                camera_name=task.camera_name,
                geofence_context=task.geofence_context
            )
        except Exception as e:
            logger.error(f"Failed to process event task: {e}", exc_info=True)


# Global event processor instance
event_processor = BackgroundEventProcessor()
event_processor.start()


def _save_and_publish_event_sync(
    event_type: str,
    camera_id: str,
    timestamp: str,
    frame_number: int,
    snapshot_path: Optional[str],
    event_data: dict,
    camera_name: Optional[str] = None,
    geofence_context: Optional[dict] = None
) -> Optional[int]:
    """
    Internal synchronous implementation of saving event to database and publishing to Redis.
    This contains the original logic of save_and_publish_event.
    """
    try:
        # Fetch latest GPS data only when location fetch base URL is configured
        location_base_url = os.environ.get("LOCATION_FETCH_BASE_URL", "").strip()
        if location_base_url:
            try:
                url = f"{location_base_url.rstrip('/')}/api/v1/ExtTrans/GetGpsDataByCamera"
                headers = {
                    'tenant': '624011100',
                    'Content-Type': 'application/json'
                }
                # Format timestamp to IST (UTC+5:30)
                timestamp_payload = timestamp
                try:
                    # Parse timestamp (handling Z for UTC)
                    if isinstance(timestamp, str):
                        ts_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        
                        # Define IST timezone
                        ist_tz = timezone(timedelta(hours=5, minutes=30))
                        
                        # Convert to IST
                        ts_ist = ts_dt.astimezone(ist_tz)
                        timestamp_payload = ts_ist.isoformat()
                except Exception as e:
                    logger.warning(f"Failed to format timestamp for GPS API: {e}")
                    
                payload = {
                    "CameraId": camera_id,  # "cameraid is our camera id"
                    "TimeStamp": timestamp_payload  # Using event timestamp in IST
                }
                
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(url, data=data, headers=headers, method='POST')
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        response_body = response.read().decode('utf-8')
                        gps_data = json.loads(response_body)
                        if "Latitude" in gps_data and "Longitude" in gps_data:
                            # Found GPS data - update existing geofence context or create new one
                            if geofence_context is None:
                                geofence_context = {
                                    "signal_id": None
                                }
                            
                            geofence_context["latitude"] = gps_data["Latitude"]
                            geofence_context["longitude"] = gps_data["Longitude"]
                            
                            # Ensure signal_id is set if we have geofence_signal_id from backend
                            if "geofence_signal_id" in geofence_context and "signal_id" not in geofence_context:
                                geofence_context["signal_id"] = geofence_context["geofence_signal_id"]
                                
                            logger.debug(f"Updated geofence context with GPS data for camera {camera_id}: Lat={gps_data['Latitude']}, Lon={gps_data['Longitude']}")
                    else:
                        logger.warning(f"Failed to fetch GPS data: Status {response.status}")
            except Exception as e:
                # If GPS fetch fails, we just keep the original geofence_context
                logger.error(f"Error fetching GPS data: {e}")

        if geofence_context:
            event_data["geofence_context"] = geofence_context
            # Add analytics_event_found metadata
            # If this is a mandatory capture (geofence_capture), analytics_event_found is False
            # Otherwise (real detection), it is True
            if event_type == "geofence_capture":
                event_data["geofence_context"]["analytics_event_found"] = False
            else:
                event_data["geofence_context"]["analytics_event_found"] = True
        
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
            logger.info(f"BackgroundWorker: Saved {event_type} event to database (ID: {event_id})")
            
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
                logger.info(f"BackgroundWorker: Published {event_type} event to Redis Pub/Sub (subscribers: {num_subscribers})")
            except Exception as redis_e:
                logger.error(f"Failed to publish {event_type} event to Redis: {redis_e}", exc_info=True)
            
            return event_id
            
    except Exception as e:
        logger.error(f"Failed to save and publish {event_type} event: {e}", exc_info=True)
        return None


def save_and_publish_event(
    event_type: str,
    camera_id: str,
    timestamp: str,
    frame_number: int,
    snapshot_path: Optional[str],
    event_data: dict,
    camera_name: Optional[str] = None,
    geofence_context: Optional[dict] = None
) -> Optional[int]:
    """
    Queue event for background processing.
    
    Returns:
        None (as processing is async), or 0 to indicate valid queuing if callers check for truthiness.
        However, original returned event_id. We can't return that anymore.
    """
    try:
        # Create a deep copy of event_data and geofence_context to prevent mutation issues
        # since these might be modified by the caller or the worker asynchronously
        event_data_copy = copy.deepcopy(event_data)
        geofence_context_copy = copy.deepcopy(geofence_context) if geofence_context else None
        
        task = EventTask(
            event_type=event_type,
            camera_id=camera_id,
            timestamp=timestamp,
            frame_number=frame_number,
            snapshot_path=snapshot_path,
            event_data=event_data_copy,
            camera_name=camera_name,
            geofence_context=geofence_context_copy
        )
        
        if event_processor.add_event(task):
            # Debug: check if thread is actually running
            if not event_processor.is_alive():
                msg = f"CRITICAL: Event processor thread is DEAD in PID {os.getpid()}! Events will not be processed."
                print(msg)
                logger.error(msg)
                # Try to restart it?
                try:
                    logger.warning("Attempting to restart event processor...")
                    event_processor.start()
                except Exception as e:
                    logger.error(f"Failed to restart event processor: {e}")

            logger.debug(f"Queued {event_type} event for camera {camera_id}")
            # Return a dummy ID so callers like 'if event_id:' still work
            # This is a bit of a lie, but sufficient for logging flow control
            return -1 
        else:
            return None
            
    except Exception as e:
        logger.error(f"Failed to queue {event_type} event: {e}", exc_info=True)
        return None


class CameraWorker(threading.Thread):
    """Worker thread for processing a single camera stream."""
    
    def __init__(self, config: CameraConfig):
        """
        Initialize camera worker.
        
        Args:
            config: Camera configuration
        """
        super().__init__(daemon=True)  # Initialize threading.Thread
        logger.debug(f"Initializing CameraWorker for camera {config.camera_id}")
        
        self.config = config
        
        # Replace localhost with mediamtx for dockerized environment
        if "localhost" in self.config.stream_url:
            old_url = self.config.stream_url
            self.config.stream_url = self.config.stream_url.replace("localhost", "mediamtx")
            logger.info(f"Camera {config.camera_id}: Replaced localhost with mediamtx in stream URL. Old: {old_url}, New: {self.config.stream_url}")
            
        self.camera_id = config.camera_id
        # Use threading Event for stopping
        self.stop_event = threading.Event()
        # self.process = None  # No longer used
        self.cap = None
        self.frame_count = 0
        self.mandatory_event_saved = False
        self.analytics_event_detected = False
        self.start_time = 0
        
        # Initialize event filter
        self.event_filter = EventFilter(
            camera_id=config.camera_id,
            detection_cooldown=0.0,
            motion_cooldown=config.parameters.motion_cooldown_seconds,
            anpr_cooldown=config.parameters.anpr_cooldown_seconds,
            change_threshold=0.0
        )
        
        # Detectors will be initialized in the process (lazy init)
        self.object_detector = None
        self.motion_detector = None
        self.anpr_detector = None
        self.garbage_detector = None
        self.violation_detector = None
        
    def _init_detectors(self):
        """Initialize detectors inside the process."""
        config = self.config
        
        logger.debug(f"Camera {self.camera_id}: Initializing detectors in process {os.getpid()} (object_detection={config.parameters.enable_object_detection}, motion_detection={config.parameters.enable_motion_detection}, garbage_detection={config.parameters.enable_garbage_detection}, anpr={config.parameters.enable_anpr})")
        
        if config.parameters.enable_object_detection:
            logger.debug(f"Camera {self.camera_id}: Creating ObjectDetector with tracking")
            # Get shared model instance
            shared_yolo = model_manager.get_yolo_model()
            
            self.object_detector = ObjectDetector(
                enable_tracking=config.parameters.enable_object_tracking,
                track_buffer_frames=config.parameters.track_buffer_frames,
                min_dwell_time_seconds=config.parameters.min_dwell_time_seconds,
                model_instance=shared_yolo
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
            logger.info(f"Camera {self.camera_id}: Creating ANPRDetector")
            try:
                self.anpr_detector = ANPRDetector()
                logger.info(f"Camera {self.camera_id}: ANPRDetector initialized successfully")
            except Exception as e:
                logger.error(f"Camera {self.camera_id}: Failed to initialize ANPRDetector: {e}")
                self.anpr_detector = None
        else:
            logger.info(f"Camera {self.camera_id}: ANPR is disabled (enable_anpr=False)")
            self.anpr_detector = None
        
            self.anpr_detector = None
            
        # Initialize ViolationDetector if there are any violation configs
        if config.parameters.violation_config:
            logger.info(f"Camera {self.camera_id}: Initializing ViolationDetector with config: {config.parameters.violation_config}")
            try:
                # Get shared violation models
                helmet_model, tripling_model, seatbelt_model = model_manager.get_violation_models()
                
                self.violation_detector = ViolationDetector(
                    helmet_model_instance=helmet_model,
                    tripling_model_instance=tripling_model,
                    seatbelt_model_instance=seatbelt_model
                )
                logger.info(f"Camera {self.camera_id}: ViolationDetector initialized successfully")
            except Exception as e:
                logger.error(f"Camera {self.camera_id}: Failed to initialize ViolationDetector: {e}")
                self.violation_detector = None
        
        logger.info(f"Camera {self.camera_id}: CameraWorker initialized successfully (stream_url={config.stream_url})")
    
    def start(self):
        """Start the camera processing thread."""
        logger.debug(f"Camera {self.camera_id}: start() called")
        
        if self.is_alive():
            logger.warning(f"Camera {self.camera_id} is already running")
            return
            
        # Reset stop event
        self.stop_event.clear()
        
        logger.info(f"Camera {self.camera_id}: Starting camera worker thread")
        super().start()  # Start the thread

    def stop(self):
        """Stop the camera processing thread."""
        logger.debug(f"Camera {self.camera_id}: stop() called")
        
        if not self.is_alive():
            logger.debug(f"Camera {self.camera_id}: Already stopped")
            return
        
        logger.info(f"Camera {self.camera_id}: Stopping camera worker...")
        self.stop_event.set()
        
        logger.debug(f"Camera {self.camera_id}: Waiting for thread to join (timeout=5s)")
        self.join(timeout=5)
        
        if self.is_alive():
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
    
    
    def run(self):
        """Main processing loop for camera stream."""
        # Note: We are now in a Thread, so we share global state with the main process.
        # No need to re-initialize Redis or EventProcessor.
        
        logger.info(f"Camera {self.camera_id}: Worker thread started")
        
        # Initialize detectors (now using shared models)
        self._init_detectors()
        
        # Retry connection every 10 seconds until successful
        logger.info(f"Camera {self.camera_id}: Attempting initial connection...")
        while not self.stop_event.is_set():
            if self._connect_to_stream():
                logger.info(f"Camera {self.camera_id}: Initial connection successful")
                break
            else:
                logger.warning(f"Camera {self.camera_id}: Initial connection failed, retrying in 10 seconds...")
                # Wait 10 seconds before retrying, but check stop_event periodically
                for _ in range(10):
                    if self.stop_event.is_set():
                        logger.info(f"Camera {self.camera_id}: Worker stopped during connection retry")
                        return
                    time.sleep(1)
        
        # If we exited the connection loop because stop_event is set, cleanup and return
        if self.stop_event.is_set():
            logger.info(f"Camera {self.camera_id}: Worker stopped before connection established")
            return
        
        frame_skip_counter = 0
        last_frame_time = time.time()
        target_frame_interval = 1.0 / self.config.parameters.max_fps
        
        self.start_time = time.time()
        logger.info(f"Camera {self.camera_id}: Starting frame processing loop (max_fps={self.config.parameters.max_fps}, frame_skip={self.config.parameters.frame_skip})")
        
        while not self.stop_event.is_set():
            try:
                # Check if stream is still open
                if self.cap is None or not self.cap.isOpened():
                    logger.warning(f"Camera {self.camera_id}: Stream connection lost, attempting to reconnect...")
                    if self.cap:
                        self.cap.release()
                    # Retry connection every 10 seconds
                    while not self.stop_event.is_set():
                        if self._connect_to_stream():
                            logger.info(f"Camera {self.camera_id}: Reconnected successfully")
                            break
                        else:
                            logger.warning(f"Camera {self.camera_id}: Reconnection failed, retrying in 10 seconds...")
                            # Wait 10 seconds before retrying, but check stop_event periodically
                            for _ in range(10):
                                if self.stop_event.is_set():
                                    logger.info(f"Camera {self.camera_id}: Worker stopped during reconnection retry")
                                    return
                                time.sleep(1)
                    
                    # If we exited the reconnection loop because stop_event is set, cleanup and return
                    if self.stop_event.is_set():
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
                    while not self.stop_event.is_set():
                        if self._connect_to_stream():
                            logger.info(f"Camera {self.camera_id}: Reconnected after frame read failure")
                            break
                        else:
                            logger.warning(f"Camera {self.camera_id}: Reconnection failed, retrying in 10 seconds...")
                            # Wait 10 seconds before retrying, but check stop_event periodically
                            for _ in range(10):
                                if self.stop_event.is_set():
                                    logger.info(f"Camera {self.camera_id}: Worker stopped during reconnection retry")
                                    return
                                time.sleep(1)
                    
                    # If we exited the reconnection loop because stop_event is set, cleanup and return
                    if self.stop_event.is_set():
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
                while not self.stop_event.is_set():
                    if self._connect_to_stream():
                        logger.info(f"Camera {self.camera_id}: Reconnected after exception")
                        break
                    else:
                        logger.warning(f"Camera {self.camera_id}: Reconnection failed after exception, retrying in 10 seconds...")
                        # Wait 10 seconds before retrying, but check stop_event periodically
                        for _ in range(10):
                            if self.stop_event.is_set():
                                logger.info(f"Camera {self.camera_id}: Worker stopped during reconnection retry after exception")
                                return
                            time.sleep(1)
                
                # If we exited the reconnection loop because stop_event is set, cleanup and return
                if self.stop_event.is_set():
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
        
        # We DO NOT stop the global event processor here because other threads might be using it.
        # The event processor is now shared.
    
    def _process_frame(self, frame):
        """
        Process a single frame with all enabled detectors.
        
        Args:
            frame: Video frame (numpy array)
        """
        logger.debug(f"Camera {self.camera_id}: Processing frame #{self.frame_count} (shape: {frame.shape})")
        start_time = time.time()
        
        # Mark analytics detected if not already
        if not self.analytics_event_detected:
            # Check if any detectors found something in this frame later in the code
            # We will update this flag when we find something
            pass

        # Check for mandatory one-time signal capture check (timeout based)
        if not self.mandatory_event_saved and not self.analytics_event_detected and self.config.geofence_context:
            signal = self.config.geofence_context.get("signal")
            if signal == "one_time_signal":
                try:
                    # Check timeout (e.g., 12 seconds to be safe before 30s backend cutoff)
                    elapsed = time.time() - self.start_time
                    if elapsed > 12:
                        logger.info(f"Camera {self.camera_id}: No analytics event found after 12s. Capturing mandatory event.")
                        
                        # Save generic snapshot
                        snapshot_path = snapshot_manager.save_detection_snapshot(
                            frame=frame,
                            camera_id=self.camera_id,
                            detections=[],
                            timestamp=datetime.utcnow()
                        )
                        
                        event_data = {
                            "type": "mandatory_capture",
                            "signal": "one_time_signal",
                            "geofence_context": self.config.geofence_context
                        }
                        
                        save_and_publish_event(
                            event_type="geofence_capture",
                            camera_id=self.camera_id,
                            timestamp=(datetime.utcnow().isoformat() + "Z"),
                            frame_number=self.frame_count,
                            snapshot_path=snapshot_path,
                            event_data=event_data,
                            camera_name=self.config.camera_name,
                            geofence_context=self.config.geofence_context
                        )
                        
                        self.mandatory_event_saved = True
                        logger.info(f"Camera {self.camera_id}: Mandatory one-time signal event saved")
                except Exception as e:
                    logger.error(f"Camera {self.camera_id}: Failed to save mandatory event: {e}", exc_info=True)
        
        # Track if any vehicles are detected in this frame (for ANPR)
        vehicles_detected = False
        tracking_events = []
        
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
            
            # Check if any vehicles are detected in tracking events (new entries)
            if tracking_events:
                for event in tracking_events:
                    if event.class_name.lower() in VEHICLE_CLASSES:
                        vehicles_detected = True
                        break
            
            # Also check active tracks for vehicles (vehicles already being tracked)
            if not vehicles_detected and hasattr(self.object_detector, 'active_tracks'):
                for track_id, tracked_obj in self.object_detector.active_tracks.items():
                    if tracked_obj.class_name.lower() in VEHICLE_CLASSES:
                        vehicles_detected = True
                        break
            
            # Save and publish all tracking events (entered/left) to database and Redis Pub/Sub
            if tracking_events:
                # Check skip_vehicle_event once for efficiency
                params = self.config.parameters
                skip_vehicle_event = getattr(params, 'skip_vehicle_event', False) if hasattr(params, 'skip_vehicle_event') else params.get('skip_vehicle_event', False) if isinstance(params, dict) else False
                logger.info(f"Camera {self.camera_id}: skip_vehicle_event={skip_vehicle_event}")
                
                for event in tracking_events:
                    # Apply tracking event filtering to prevent duplicates
                    if not self.event_filter.should_publish_tracking(event):
                        logger.debug(f"Camera {self.camera_id}: Tracking event filtered out for track_id={event.track_id}, action={event.tracking_action}")
                        continue
                    
                    # Skip vehicle tracking events if skip_vehicle_event is enabled
                    # Only violation events will be saved for vehicles
                    if skip_vehicle_event and event.class_name.lower() in VEHICLE_CLASSES:
                        logger.info(f"Camera {self.camera_id}: Skipping vehicle tracking event for {event.class_name} (track_id={event.track_id}) - skip_vehicle_event enabled")
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
                        camera_name=self.config.camera_name,
                        geofence_context=self.config.geofence_context
                    )
                    
                    
                    if event_id:
                        self.analytics_event_detected = True
                        logger.info(f"Camera {self.camera_id}: Saved and published tracking event '{event.tracking_action}' for {event.class_name} (track_id={event.track_id}, event_id={event_id}) in {detect_time:.3f}s")
                    else:
                        logger.error(f"Camera {self.camera_id}: Failed to save tracking event for track_id={event.track_id}")
            else:
                logger.debug(f"Camera {self.camera_id}: No tracking events in frame #{self.frame_count} ({detect_time:.3f}s)")
        
            # Check active tracks for VIOLATIONS (Helmet/Tripling)
            # We only check tracks that are currently active in this frame
            if self.violation_detector and self.object_detector and hasattr(self.object_detector, 'active_tracks'):
                violation_config = self.config.parameters.violation_config
                logger.info(f"Camera {self.camera_id}: Checking active tracks for violations")
                logger.info(f"Camera {self.camera_id}: Active tracks: {self.config.parameters.violation_config}")
                
                # Check each active track
                for track_id, tracked_obj in self.object_detector.active_tracks.items():
                    class_name = tracked_obj.class_name.lower()
                    
                    # Only proceed if we have config for this class
                    if class_name in violation_config: # e.g. "motorcycle"
                        needed_checks = violation_config[class_name] # e.g. ["helmet", "tripling"]
                        
                        # Only check periodically or on specific conditions to save compute?
                        # For now, check every 10th frame per object to avoid spamming inference? 
                        # Or better: check only if we haven't detected a violation for this object recently?
                        # Let's check every 5 frames for responsiveness.
                        if self.frame_count % 5 != 0:
                            continue
                            
                        # Get object crop
                        # Retrieve latest bbox from tracked_obj
                        if not tracked_obj.positions:
                            continue
                        
                        bbox = tracked_obj.positions[-1]
                        
                        # Convert bbox object to list [x, y, w, h]
                        bbox_list = [bbox.x, bbox.y, bbox.width, bbox.height]
                        
                        # Run checks
                        violations_found = []
                        
                        
                        # Seatbelt check (runs on cropped vehicle image)
                        if "seatbelt" in needed_checks:
                            # Create crop for seatbelt detection with padding (20%)
                            h, w = frame.shape[:2]
                            
                            pad_w = 0.2 * bbox.width
                            pad_h = 0.2 * bbox.height
                            
                            x1 = int(max(0, (bbox.x - pad_w) * w))
                            y1 = int(max(0, (bbox.y - pad_h) * h))
                            x2 = int(min(w, (bbox.x + bbox.width + pad_w) * w))
                            y2 = int(min(h, (bbox.y + bbox.height + pad_h) * h))
                            
                            # Safety check for valid crop
                            if x2 > x1 and y2 > y1:
                                vehicle_crop = frame[y1:y2, x1:x2]
                                if vehicle_crop.size > 0:
                                    # Pass crop to seatbelt detector with bbox=None (implies full crop is the vehicle)
                                    is_violation, conf, label = self.violation_detector.check_seatbelt(vehicle_crop, bbox=None)
                                    if is_violation:
                                        violations_found.append({
                                            "type": "no_seatbelt", 
                                            "confidence": conf
                                            # "crop": vehicle_crop  <-- Removed to force full frame snapshot
                                        })
                            
                        # Helmet check (runs on full frame)
                        if "helmet" in needed_checks:
                            is_violation, conf, label = self.violation_detector.check_helmet(frame, bbox_list)
                            if is_violation:
                                violations_found.append({"type": "no_helmet", "confidence": conf})
                                
                        # Tripling check (runs on full frame)
                        if "tripling" in needed_checks:
                            is_violation, conf, label = self.violation_detector.check_tripling(frame, bbox_list)
                            if is_violation:
                                violations_found.append({"type": "tripling", "confidence": conf})
                        
                        # If violations found, generate event
                        if violations_found:
                            # We need to rate limit this per track_id so we don't spam 30 events a second
                            # Using a simple cache in this loop isn't enough, we need state on the worker
                            # For simplicity, let's use the EventFilter but add a custom key for violations
                            
                            for v in violations_found:
                                v_type = v["type"]
                                
                                # Use track-based deduplication (only one event per violation type per track)
                                if self.event_filter.should_publish_violation(track_id, v_type):
                                    logger.info(f"Camera {self.camera_id}: Detected {v_type} on {class_name} (track_id={track_id})")
                                    
                                    # Create snapshot for violation
                                    # Check if we have a specific crop for this violation (Seatbelt)
                                    detection_frame = v.get("crop")
                                    
                                    if detection_frame is not None:
                                        # Use the crop as the snapshot
                                        # The detection box is the entire crop
                                        formatted_bbox = BoundingBox(x=0.0, y=0.0, width=1.0, height=1.0)
                                        snapshot_frame = detection_frame
                                    else:
                                        # Standard Logic: Use full frame and calculate padded bbox
                                        pad_x = bbox.width * 0.2
                                        pad_y = bbox.height * 0.2
                                        
                                        x1 = max(0.0, bbox.x - pad_x)
                                        y1 = max(0.0, bbox.y - pad_y)
                                        x2 = min(1.0, bbox.x + bbox.width + pad_x)
                                        y2 = min(1.0, bbox.y + bbox.height + pad_y)
                                        
                                        formatted_bbox = BoundingBox(
                                            x=x1,
                                            y=y1,
                                            width=x2 - x1,
                                            height=y2 - y1
                                        )
                                        snapshot_frame = frame

                                    # Create a Detection object for snapshot visualization
                                    violation_detection = Detection(
                                        class_name=f"{class_name} ({v_type})",
                                        confidence=v["confidence"],
                                        bounding_box=formatted_bbox,
                                        track_id=track_id
                                    )
                                    
                                    snapshot_path = snapshot_manager.save_detection_snapshot(
                                        frame=snapshot_frame,
                                        camera_id=self.camera_id,
                                        detections=[violation_detection],
                                        timestamp=datetime.utcnow()
                                    )
                                    
                                    event_data = {
                                        "violation_type": v_type,
                                        "class_name": class_name,
                                        "track_id": track_id,
                                        "confidence": v["confidence"],
                                        "bbox": bbox.dict()
                                    }
                                    
                                    save_and_publish_event(
                                        event_type=v_type,
                                        camera_id=self.camera_id,
                                        timestamp=datetime.utcnow().isoformat() + "Z",
                                        frame_number=self.frame_count,
                                        snapshot_path=snapshot_path,
                                        event_data=event_data,
                                        camera_name=self.config.camera_name,
                                        geofence_context=self.config.geofence_context
                                    )
        
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
                        camera_name=self.config.camera_name,
                        geofence_context=self.config.geofence_context
                    )
                    
                    if event_id:
                        logger.info(f"Camera {self.camera_id}: Saved and published motion event for frame #{self.frame_count} (motion_intensity: {motion_event.motion_intensity:.2f}, affected_area: {motion_event.affected_area_percentage:.2f}, event_id={event_id}) in {motion_time:.3f}s")
                    else:
                        logger.error(f"Camera {self.camera_id}: Failed to save motion event")
                else:
                    logger.debug(f"Camera {self.camera_id}: Motion event filtered (cooldown) for frame #{self.frame_count}")
            else:
                logger.debug(f"Camera {self.camera_id}: No motion detected in frame #{self.frame_count} ({motion_time:.3f}s)")
        
        
        # Check if any garbage class is in detection_classes
        is_garbage_enabled_in_classes = any(cls.lower() in [c.lower() for c in self.config.parameters.detection_classes] for cls in GARBAGE_CLASS_NAMES)

        # Garbage detection
        if self.garbage_detector and self.config.parameters.enable_garbage_detection and is_garbage_enabled_in_classes:
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
                            camera_name=self.config.camera_name,
                            geofence_context=self.config.geofence_context
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
                        camera_name=self.config.camera_name,
                        geofence_context=self.config.geofence_context
                    )
                    
                    
                    if event_id:
                        self.analytics_event_detected = True
                        detection_count = len(garbage_event.detections)
                        logger.info(f"Camera {self.camera_id}: Saved and published garbage detection event with {detection_count} detections (event_id={event_id}) in {garbage_time:.3f}s")
                    else:
                        logger.error(f"Camera {self.camera_id}: Failed to save garbage detection event")
            else:
                logger.debug(f"Camera {self.camera_id}: No garbage detected in frame #{self.frame_count} ({garbage_time:.3f}s)")
        
        # ANPR detection - only run if vehicles are detected
        if self.anpr_detector and self.config.parameters.enable_anpr:
            if vehicles_detected:
                anpr_start = time.time()
                try:
                    anpr_event = self.anpr_detector.detect(
                        frame=frame,
                        camera_id=self.camera_id,
                        frame_number=self.frame_count
                    )
                    anpr_time = time.time() - anpr_start
                except Exception as e:
                    logger.error(f"Camera {self.camera_id}: ANPR detection error on frame #{self.frame_count}: {e}", exc_info=True)
                    anpr_event = None
                    anpr_time = time.time() - anpr_start
            else:
                anpr_event = None
                anpr_time = 0.0
        else:
            anpr_event = None
            anpr_time = 0.0
        
        # Process ANPR event if detected (regardless of how we got here)
        if anpr_event:
            # Apply event filtering to prevent duplicate ANPR events
            if self.event_filter.should_publish_anpr(anpr_event):
                # Capture vehicle class from tracking events or active tracks
                vehicle_class = None
                if tracking_events:
                    # Find vehicle class from tracking events (prioritize "entered" events)
                    for event in tracking_events:
                        if event.class_name.lower() in VEHICLE_CLASSES:
                            vehicle_class = event.class_name
                            # Prefer "entered" events as they're more recent
                            if event.tracking_action == "entered":
                                break
                
                # If not found in tracking events, check active tracks
                if not vehicle_class and hasattr(self.object_detector, 'active_tracks'):
                    for track_id, tracked_obj in self.object_detector.active_tracks.items():
                        if tracked_obj.class_name.lower() in VEHICLE_CLASSES:
                            vehicle_class = tracked_obj.class_name
                            break
                
                # Update anpr_result with vehicle class
                if vehicle_class:
                    anpr_event.anpr_result.vehicle_class = vehicle_class
                
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
                    camera_name=self.config.camera_name,
                    geofence_context=self.config.geofence_context
                )
                
                if event_id:
                    vehicle_info = f", vehicle: {vehicle_class}" if vehicle_class else ""
                    logger.info(f"Camera {self.camera_id}: Saved and published ANPR event for frame #{self.frame_count}: {anpr_event.anpr_result.license_plate} (confidence: {anpr_event.anpr_result.confidence:.2f}{vehicle_info}, event_id={event_id}) in {anpr_time:.3f}s")
                else:
                    logger.error(f"Camera {self.camera_id}: Failed to save ANPR event")
            else:
                logger.debug(f"Camera {self.camera_id}: ANPR event filtered (duplicate plate in cooldown) for frame #{self.frame_count}: {anpr_event.anpr_result.license_plate}")
        
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
                logger.info(f"CameraManager: Camera {config.camera_id} already exists, restarting to apply new config")
                try:
                    old_worker = self.workers[config.camera_id]
                    old_worker.stop()
                    del self.workers[config.camera_id]
                except Exception as e:
                    logger.error(f"Failed to stop existing camera {config.camera_id}: {e}")
            
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

