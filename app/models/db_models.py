"""
Database models for event storage.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class EventRecord(Base):
    """
    Event record for storing all types of events (detection, motion, ANPR, tracking).
    """
    __tablename__ = "events"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Event metadata
    event_type = Column(String(50), nullable=False, index=True)  # detection, motion, anpr, tracking
    camera_id = Column(String(100), nullable=False, index=True)
    camera_name = Column(String(255), nullable=True)  # Human-readable camera name
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    frame_number = Column(Integer, nullable=False)
    
    # Snapshot path
    snapshot_path = Column(String(500), nullable=True)  # Path to saved snapshot image
    
    # Event-specific data stored as JSON
    # For detection: {detections: [...], model_info: {...}}
    # For motion: {motion_intensity: float, affected_area_percentage: float}
    # For ANPR: {anpr_result: {license_plate: str, confidence: float, region: str}}
    # For tracking: {track_id: int, tracking_action: str, class_name: str, confidence: float, bounding_box: {...}, dwell_time_seconds: float}
    event_data = Column(JSON, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, server_default=func.now())
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_camera_timestamp', 'camera_id', 'timestamp'),
        Index('idx_event_type_timestamp', 'event_type', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<EventRecord(id={self.id}, type={self.event_type}, camera={self.camera_id}, timestamp={self.timestamp})>"

