"""
Events API endpoints for fetching event data and snapshots.
"""
from fastapi import APIRouter, HTTPException, status, Query, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, cast, String, func, text
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from app.models.db_models import EventRecord
from app.core.database import get_db
from app.utils.snapshot import snapshot_manager
from app.utils.logger import get_logger
from app.core.redis_client import redis_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


# Response models
class EventResponse(BaseModel):
    """Event response model."""
    model_config = {"protected_namespaces": (), "from_attributes": True}
    
    id: int
    event_type: str
    camera_id: str
    camera_name: Optional[str] = None
    timestamp: datetime
    frame_number: int
    snapshot_path: Optional[str]
    event_data: dict
    created_at: datetime


class EventListResponse(BaseModel):
    """Event list response with pagination."""
    model_config = {"protected_namespaces": ()}
    
    events: List[EventResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class EventStatsResponse(BaseModel):
    """Event statistics response."""
    model_config = {"protected_namespaces": ()}
    
    total_events: int
    events_by_type: dict
    events_by_camera: dict
    date_range: dict


def convert_event_record_to_response(event_record: EventRecord) -> EventResponse:
    """
    Convert EventRecord database model to EventResponse format.
    
    Args:
        event_record: EventRecord from database
        
    Returns:
        EventResponse object
    """
    return EventResponse.model_validate(event_record)


@router.get("", response_model=EventListResponse)
async def list_events(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type (detection, motion, anpr, tracking)"),
    object_class: Optional[str] = Query(None, description="Filter by object class (e.g., person, car, truck, garbage)"),
    license_plate: Optional[str] = Query(None, description="Filter by license plate (supports regex pattern)"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold (0.0-1.0). Works for tracking and ANPR events. For detection events, checks if any detection meets the threshold."),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (ISO format)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Items per page"),
    db: Session = Depends(get_db)
) -> EventListResponse:
    """
    List events with filtering and pagination.
    
    Args:
        camera_id: Filter by camera ID
        event_type: Filter by event type
        object_class: Filter by object class (e.g., person, car, truck, garbage)
        license_plate: Filter by license plate using regex pattern (searches in event_data->anpr_result->license_plate)
        min_confidence: Minimum confidence threshold (0.0-1.0). For tracking events, filters by event_data->>'confidence'. 
                       For ANPR events, filters by event_data->'anpr_result'->>'confidence'. 
                       For detection events, checks if any detection in the detections array has confidence >= threshold.
        start_time: Start timestamp for filtering
        end_time: End timestamp for filtering
        page: Page number (1-indexed)
        page_size: Number of items per page
        db: Database session
        
    Returns:
        Paginated list of events
    """
    try:
        # Build query
        query = db.query(EventRecord)
        
        # Apply filters
        filters = []
        if camera_id:
            filters.append(EventRecord.camera_id == camera_id)
        if event_type:
            filters.append(EventRecord.event_type == event_type)
        if object_class:
            # Filter by class_name in the event_data JSON field (case-insensitive using ILIKE)
            logger.info(f"Adding object_class filter: '{object_class}'")
            filters.append(text("LOWER(event_data->>'class_name') = LOWER(:object_class)").bindparams(object_class=object_class))
        if license_plate:
            # Complex regex-based search for license plates
            # This searches in event_data->anpr_result->license_plate using PostgreSQL regex matching
            # Supports partial matches and regex patterns
            logger.info(f"Adding license_plate filter with pattern: '{license_plate}'")
            # Use ~* for case-insensitive regex match in PostgreSQL
            # Handle null anpr_result gracefully
            filters.append(
                text("event_data->'anpr_result'->>'license_plate' IS NOT NULL AND event_data->'anpr_result'->>'license_plate' ~* :license_pattern")
                .bindparams(license_pattern=license_plate)
            )
        if min_confidence is not None:
            # Confidence filtering works differently for different event types:
            # - Tracking: event_data->>'confidence' >= min_confidence
            # - ANPR: event_data->'anpr_result'->>'confidence' >= min_confidence
            # - Detection: Check if any detection in event_data->'detections' array has confidence >= min_confidence
            # - Motion: No confidence field, so exclude motion events when confidence filter is applied
            logger.info(f"Adding min_confidence filter: {min_confidence}")
            confidence_filter = text("""
                (
                    -- For tracking events: check direct confidence field
                    (event_type = 'tracking' AND (event_data->>'confidence')::float >= :min_conf)
                    OR
                    -- For ANPR events: check nested confidence in anpr_result
                    (event_type = 'anpr' AND (event_data->'anpr_result'->>'confidence')::float >= :min_conf)
                    OR
                    -- For detection events: check if any detection has confidence >= threshold
                    (event_type = 'detection' AND EXISTS (
                        SELECT 1 FROM jsonb_array_elements(event_data->'detections') AS det
                        WHERE (det->>'confidence')::float >= :min_conf
                    ))
                )
            """).bindparams(min_conf=min_confidence)
            filters.append(confidence_filter)
        if start_time:
            filters.append(EventRecord.timestamp >= start_time)
        if end_time:
            filters.append(EventRecord.timestamp <= end_time)
        
        if filters:
            logger.info(f"Applying {len(filters)} filters to query")
            query = query.filter(and_(*filters))
        
        # Get total count
        logger.info(f"Executing query with filters: {[str(f) for f in filters]}")
        total = query.count()
        
        # Apply pagination and ordering
        offset = (page - 1) * page_size
        events = query.order_by(desc(EventRecord.timestamp)).offset(offset).limit(page_size).all()
        
        # Check if there are more pages
        has_more = (offset + page_size) < total
        
        return EventListResponse(
            events=[EventResponse.model_validate(event) for event in events],
            total=total,
            page=page,
            page_size=page_size,
            has_more=has_more
        )
    except Exception as e:
        logger.error(f"Error fetching events: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch events: {str(e)}"
        )


@router.get("/stats", response_model=EventStatsResponse)
async def get_event_stats(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    object_class: Optional[str] = Query(None, description="Filter by object class (e.g., person, car, truck, garbage)"),
    start_time: Optional[datetime] = Query(None, description="Start timestamp (ISO format)"),
    end_time: Optional[datetime] = Query(None, description="End timestamp (ISO format)"),
    db: Session = Depends(get_db)
) -> EventStatsResponse:
    """
    Get event statistics.
    
    Args:
        camera_id: Filter by camera ID
        object_class: Filter by object class (e.g., person, car, truck, garbage)
        start_time: Start timestamp for filtering
        end_time: End timestamp for filtering
        db: Database session
        
    Returns:
        Event statistics
    """
    try:
        # Build query
        query = db.query(EventRecord)
        
        # Apply filters
        filters = []
        if camera_id:
            filters.append(EventRecord.camera_id == camera_id)
        if object_class:
            # Filter by class_name in the event_data JSON field (case-insensitive using ILIKE)
            logger.info(f"Adding object_class filter: '{object_class}'")
            filters.append(text("LOWER(event_data->>'class_name') = LOWER(:object_class)").bindparams(object_class=object_class))
        if start_time:
            filters.append(EventRecord.timestamp >= start_time)
        if end_time:
            filters.append(EventRecord.timestamp <= end_time)
        
        if filters:
            query = query.filter(and_(*filters))
        
        # Get total count
        total_events = query.count()
        
        # Get events by type
        events_by_type = {}
        for event_type in ["detection", "motion", "anpr", "tracking"]:
            count = query.filter(EventRecord.event_type == event_type).count()
            events_by_type[event_type] = count
        
        # Get events by camera
        events_by_camera = {}
        # Group by camera_id and get the most recent camera_name for each camera
        camera_data = db.query(
            EventRecord.camera_id,
            EventRecord.camera_name
        ).distinct().all()
        
        # Create a mapping of camera_id to the most appropriate camera_name
        camera_name_map = {}
        for (cam_id, cam_name) in camera_data:
            if cam_id not in camera_name_map:
                # Prefer non-null camera names, but keep track of all options
                camera_name_map[cam_id] = cam_name
            elif cam_name and not camera_name_map[cam_id]:
                # Update to non-null name if we had null before
                camera_name_map[cam_id] = cam_name
        
        # Count events for each camera using the mapped names
        for cam_id in camera_name_map.keys():
            if camera_id is None or cam_id == camera_id:
                count = query.filter(EventRecord.camera_id == cam_id).count()
                # Use camera name if available, otherwise fall back to camera ID
                display_name = camera_name_map[cam_id] if camera_name_map[cam_id] else cam_id
                events_by_camera[display_name] = count
        
        # Get date range
        first_event = query.order_by(EventRecord.timestamp.asc()).first()
        last_event = query.order_by(EventRecord.timestamp.desc()).first()
        
        date_range = {}
        if first_event and last_event:
            date_range = {
                "first_event": first_event.timestamp.isoformat(),
                "last_event": last_event.timestamp.isoformat()
            }
        
        return EventStatsResponse(
            total_events=total_events,
            events_by_type=events_by_type,
            events_by_camera=events_by_camera,
            date_range=date_range
        )
    except Exception as e:
        logger.error(f"Error fetching event stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch event stats: {str(e)}"
        )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    db: Session = Depends(get_db)
) -> EventResponse:
    """
    Get a specific event by ID.
    
    Args:
        event_id: Event ID
        db: Database session
        
    Returns:
        Event details
        
    Raises:
        HTTPException: If event not found
    """
    try:
        event = db.query(EventRecord).filter(EventRecord.id == event_id).first()
        
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event {event_id} not found"
            )
        
        return EventResponse.model_validate(event)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching event {event_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch event: {str(e)}"
        )


@router.get("/{event_id}/snapshot")
async def get_event_snapshot(
    event_id: int,
    db: Session = Depends(get_db)
):
    """
    Get snapshot image for a specific event.
    
    Args:
        event_id: Event ID
        db: Database session
        
    Returns:
        PNG image file
        
    Raises:
        HTTPException: If event not found or no snapshot available
    """
    try:
        event = db.query(EventRecord).filter(EventRecord.id == event_id).first()
        
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event {event_id} not found"
            )
        
        if not event.snapshot_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No snapshot available for event {event_id}"
            )
        
        # Get full path to snapshot
        snapshot_full_path = snapshot_manager.get_snapshot_full_path(event.snapshot_path)
        
        if not snapshot_full_path.exists():
            logger.error(f"Snapshot file not found: {snapshot_full_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Snapshot file not found"
            )
        
        return FileResponse(
            path=str(snapshot_full_path),
            media_type="image/png",
            filename=f"event_{event_id}_snapshot.png"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching snapshot for event {event_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch snapshot: {str(e)}"
        )


@router.delete("/{event_id}", status_code=status.HTTP_200_OK)
async def delete_event(
    event_id: int,
    delete_snapshot: bool = Query(False, description="Also delete associated snapshot file"),
    db: Session = Depends(get_db)
) -> dict:
    """
    Delete a specific event.
    
    Args:
        event_id: Event ID
        delete_snapshot: Whether to also delete the snapshot file
        db: Database session
        
    Returns:
        Status message
        
    Raises:
        HTTPException: If event not found
    """
    try:
        event = db.query(EventRecord).filter(EventRecord.id == event_id).first()
        
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event {event_id} not found"
            )
        
        # Delete snapshot file if requested
        if delete_snapshot and event.snapshot_path:
            try:
                snapshot_full_path = snapshot_manager.get_snapshot_full_path(event.snapshot_path)
                if snapshot_full_path.exists():
                    snapshot_full_path.unlink()
                    logger.info(f"Deleted snapshot file: {snapshot_full_path}")
            except Exception as e:
                logger.error(f"Failed to delete snapshot file: {e}", exc_info=True)
        
        # Delete event from database
        db.delete(event)
        db.commit()
        
        logger.info(f"Deleted event {event_id}")
        return {
            "message": f"Event {event_id} deleted successfully",
            "snapshot_deleted": delete_snapshot and event.snapshot_path is not None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting event {event_id}: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete event: {str(e)}"
        )

