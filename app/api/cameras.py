from fastapi import APIRouter, HTTPException, status, Response
from typing import List, Dict, Any
from app.models.event_models import (
    CameraConfig,
    CameraListResponse,
    HealthResponse
)
from app.services.video_worker import camera_manager
from app.services.retention import retention_service
from app.services.retention_scheduler import retention_scheduler
from app.core.redis_client import redis_client
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["cameras"])


@router.post("/cameras", status_code=status.HTTP_201_CREATED)
async def register_cameras(cameras: List[CameraConfig]) -> dict:
    """
    Register and start processing one or more camera streams.
    
    Args:
        cameras: List of camera configurations
        
    Returns:
        Status message with results
    """
    results = {
        "success": [],
        "failed": []
    }

    for camera in cameras:
        try:
            if camera_manager.add_camera(camera):
                results["success"].append({
                    "camera_id": camera.camera_id,
                    "camera_name": camera.camera_name
                })
                logger.info(f"Successfully registered camera: {camera.camera_id} ({camera.camera_name})")
            else:
                results["failed"].append({
                    "camera_id": camera.camera_id,
                    "camera_name": camera.camera_name,
                    "reason": "Camera already exists or failed to start"
                })
                logger.warning(f"Failed to register camera: {camera.camera_id} ({camera.camera_name})")
        except Exception as e:
            results["failed"].append({
                "camera_id": camera.camera_id,
                "camera_name": camera.camera_name,
                "reason": str(e)
            })
            logger.error(f"Error registering camera {camera.camera_id} ({camera.camera_name}): {e}")
    
    return {
        "message": f"Processed {len(cameras)} camera(s)",
        "results": results
    }


@router.get("/cameras", response_model=CameraListResponse)
async def list_cameras(response: Response) -> CameraListResponse:
    """
    List all active cameras.
    
    Returns:
        List of active camera configurations
    """
    # Prevent caching to ensure fresh data
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    cameras_dict = camera_manager.list_cameras()
    cameras_list = list(cameras_dict.values())
    
    logger.info(f"Listing cameras: found {len(cameras_list)} cameras")
    
    return CameraListResponse(
        cameras=cameras_list,
        count=len(cameras_list)
    )


@router.get("/cameras/{camera_id}", response_model=CameraConfig)
async def get_camera(camera_id: str, response: Response) -> CameraConfig:
    """
    Get configuration for a specific camera.
    
    Args:
        camera_id: Camera identifier
        
    Returns:
        Camera configuration
        
    Raises:
        HTTPException: If camera not found
    """
    # Prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    
    camera = camera_manager.get_camera(camera_id)
    
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} not found"
        )
    
    return camera


@router.delete("/cameras/{camera_id}", status_code=status.HTTP_200_OK)
async def delete_camera(camera_id: str, response: Response) -> dict:
    """
    Stop processing and remove a camera.
    
    Args:
        camera_id: Camera identifier
        
    Returns:
        Status message
        
    Raises:
        HTTPException: If camera not found
    """
    # Prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    
    logger.info(f"Delete camera endpoint called for: {camera_id}")
    
    # Get list of cameras before deletion for logging
    cameras_before = list(camera_manager.list_cameras().keys())
    logger.info(f"Cameras before deletion: {cameras_before}")
    
    if camera_manager.remove_camera(camera_id):
        # Get list of cameras after deletion for logging
        cameras_after = list(camera_manager.list_cameras().keys())
        logger.info(f"Successfully deleted camera: {camera_id}")
        logger.info(f"Cameras after deletion: {cameras_after}")
        
        return {
            "message": f"Camera {camera_id} stopped and removed successfully",
            "remaining_cameras": cameras_after
        }
    else:
        logger.error(f"Failed to delete camera: {camera_id} - camera not found")
        logger.info(f"Available cameras: {cameras_before}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} not found"
        )


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns:
        Health status of the service
    """
    redis_connected = redis_client.health_check()
    active_cameras = len(camera_manager.list_cameras())
    
    service_status = "healthy" if redis_connected else "degraded"
    
    return HealthResponse(
        status=service_status,
        redis_connected=redis_connected,
        active_cameras=active_cameras
    )


# Retention Management Endpoints

@router.get("/retention/stats")
async def get_retention_stats(response: Response) -> Dict[str, Any]:
    """
    Get retention statistics for all cameras.
    
    Returns:
        Dictionary with retention statistics per camera
    """
    # Prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    
    try:
        camera_configs = camera_manager.list_cameras()
        stats = retention_service.get_retention_stats(camera_configs)
        
        logger.info(f"Retrieved retention stats for {len(stats)} cameras")
        return {
            "message": "Retention statistics retrieved successfully",
            "stats": stats,
            "total_cameras": len(stats)
        }
    except Exception as e:
        logger.error(f"Error getting retention stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get retention stats: {str(e)}"
        )


@router.post("/retention/cleanup")
async def trigger_retention_cleanup(response: Response) -> Dict[str, Any]:
    """
    Manually trigger retention cleanup for all cameras.
    
    Returns:
        Dictionary with cleanup results
    """
    # Prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    
    try:
        logger.info("Manual retention cleanup triggered via API")
        results = retention_scheduler.run_cleanup_now()
        
        if "error" in results:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=results["error"]
            )
        
        logger.info("Manual retention cleanup completed successfully")
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during manual cleanup: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run cleanup: {str(e)}"
        )


@router.post("/retention/cleanup/{camera_id}")
async def trigger_camera_cleanup(camera_id: str, response: Response) -> Dict[str, Any]:
    """
    Manually trigger retention cleanup for a specific camera.
    
    Args:
        camera_id: Camera identifier
        
    Returns:
        Dictionary with cleanup results for the camera
        
    Raises:
        HTTPException: If camera not found
    """
    # Prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    
    try:
        # Check if camera exists
        camera = camera_manager.get_camera(camera_id)
        if not camera:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera {camera_id} not found"
            )
        
        logger.info(f"Manual retention cleanup triggered for camera {camera_id}")
        
        # Run cleanup for specific camera
        deleted_events, deleted_snapshots = retention_service.cleanup_events_for_camera(
            camera_id, 
            camera.parameters.retention_days
        )
        
        logger.info(f"Manual cleanup completed for camera {camera_id}: {deleted_events} events, {deleted_snapshots} snapshots deleted")
        
        return {
            "message": f"Cleanup completed for camera {camera_id}",
            "camera_id": camera_id,
            "retention_days": camera.parameters.retention_days,
            "deleted_events": deleted_events,
            "deleted_snapshots": deleted_snapshots
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during camera cleanup for {camera_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run cleanup for camera {camera_id}: {str(e)}"
        )


@router.get("/retention/scheduler/status")
async def get_scheduler_status(response: Response) -> Dict[str, Any]:
    """
    Get retention scheduler status.
    
    Returns:
        Dictionary with scheduler status information
    """
    # Prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    
    try:
        status_info = retention_scheduler.get_status()
        return {
            "message": "Scheduler status retrieved successfully",
            "scheduler": status_info
        }
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scheduler status: {str(e)}"
        )


@router.post("/retention/scheduler/start")
async def start_retention_scheduler(response: Response) -> Dict[str, Any]:
    """
    Start the retention scheduler.
    
    Returns:
        Status message
    """
    # Prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    
    try:
        retention_scheduler.start()
        logger.info("Retention scheduler started via API")
        
        return {
            "message": "Retention scheduler started successfully",
            "status": "started"
        }
    except Exception as e:
        logger.error(f"Error starting retention scheduler: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start scheduler: {str(e)}"
        )


@router.post("/retention/scheduler/stop")
async def stop_retention_scheduler(response: Response) -> Dict[str, Any]:
    """
    Stop the retention scheduler.
    
    Returns:
        Status message
    """
    # Prevent caching
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    
    try:
        retention_scheduler.stop()
        logger.info("Retention scheduler stopped via API")
        
        return {
            "message": "Retention scheduler stopped successfully",
            "status": "stopped"
        }
    except Exception as e:
        logger.error(f"Error stopping retention scheduler: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop scheduler: {str(e)}"
        )

