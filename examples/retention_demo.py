#!/usr/bin/env python3
"""
Example script demonstrating event retention functionality.
"""
import requests
import json
import time
from datetime import datetime, timedelta

# Configuration
API_BASE_URL = "http://localhost:8069/api"

def print_response(title, response):
    """Print formatted API response."""
    print(f"\n{'='*50}")
    print(f"{title}")
    print(f"{'='*50}")
    print(json.dumps(response, indent=2))

def get_retention_stats():
    """Get retention statistics for all cameras."""
    try:
        response = requests.get(f"{API_BASE_URL}/retention/stats")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting retention stats: {e}")
        return None

def get_scheduler_status():
    """Get retention scheduler status."""
    try:
        response = requests.get(f"{API_BASE_URL}/retention/scheduler/status")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting scheduler status: {e}")
        return None

def trigger_cleanup_all():
    """Trigger cleanup for all cameras."""
    try:
        response = requests.post(f"{API_BASE_URL}/retention/cleanup")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error triggering cleanup: {e}")
        return None

def trigger_cleanup_camera(camera_id):
    """Trigger cleanup for specific camera."""
    try:
        response = requests.post(f"{API_BASE_URL}/retention/cleanup/{camera_id}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error triggering cleanup for camera {camera_id}: {e}")
        return None

def start_scheduler():
    """Start the retention scheduler."""
    try:
        response = requests.post(f"{API_BASE_URL}/retention/scheduler/start")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error starting scheduler: {e}")
        return None

def stop_scheduler():
    """Stop the retention scheduler."""
    try:
        response = requests.post(f"{API_BASE_URL}/retention/scheduler/stop")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error stopping scheduler: {e}")
        return None

def main():
    """Main demonstration function."""
    print("Event Retention Feature Demonstration")
    print("====================================")
    
    # 1. Check scheduler status
    print("\n1. Checking Retention Scheduler Status...")
    status = get_scheduler_status()
    if status:
        print_response("Scheduler Status", status)
    
    # 2. Get retention statistics
    print("\n2. Getting Retention Statistics...")
    stats = get_retention_stats()
    if stats:
        print_response("Retention Statistics", stats)
        
        # Show summary
        if "stats" in stats:
            print(f"\nSummary:")
            for camera_id, camera_stats in stats["stats"].items():
                if "error" not in camera_stats:
                    print(f"  Camera {camera_id}:")
                    print(f"    Retention Period: {camera_stats['retention_days']} days")
                    print(f"    Total Events: {camera_stats['total_events']}")
                    print(f"    Events Within Retention: {camera_stats['events_within_retention']}")
                    print(f"    Events Outside Retention: {camera_stats['events_outside_retention']}")
                    if camera_stats['events_outside_retention'] > 0:
                        print(f"    ⚠️  {camera_stats['events_outside_retention']} events can be cleaned up")
                    else:
                        print(f"    ✅ No events need cleanup")
    
    # 3. Demonstrate manual cleanup (if there are events to clean)
    print("\n3. Manual Cleanup Demonstration...")
    
    # Check if there are events to clean up
    if stats and "stats" in stats:
        cameras_with_cleanup = [
            camera_id for camera_id, camera_stats in stats["stats"].items()
            if "error" not in camera_stats and camera_stats.get("events_outside_retention", 0) > 0
        ]
        
        if cameras_with_cleanup:
            print(f"Found {len(cameras_with_cleanup)} cameras with events to clean up")
            
            # Clean up first camera as example
            camera_id = cameras_with_cleanup[0]
            print(f"Cleaning up camera: {camera_id}")
            
            cleanup_result = trigger_cleanup_camera(camera_id)
            if cleanup_result:
                print_response(f"Cleanup Result for {camera_id}", cleanup_result)
        else:
            print("No cameras have events that need cleanup")
    
    # 4. Demonstrate scheduler control
    print("\n4. Scheduler Control Demonstration...")
    
    # Stop scheduler
    print("Stopping scheduler...")
    stop_result = stop_scheduler()
    if stop_result:
        print_response("Stop Scheduler Result", stop_result)
    
    time.sleep(2)
    
    # Start scheduler
    print("Starting scheduler...")
    start_result = start_scheduler()
    if start_result:
        print_response("Start Scheduler Result", start_result)
    
    # 5. Final status check
    print("\n5. Final Status Check...")
    final_status = get_scheduler_status()
    if final_status:
        print_response("Final Scheduler Status", final_status)

if __name__ == "__main__":
    main()
