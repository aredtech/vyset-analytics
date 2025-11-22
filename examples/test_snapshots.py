"""
Example script to test the snapshot and events API functionality.
"""
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8069"
SNAPSHOT_OUTPUT_DIR = Path("./downloaded_snapshots")


def test_events_api():
    """Test the events API endpoints."""
    print("=" * 80)
    print("Testing Analytics Snapshot & Events API")
    print("=" * 80)
    print()
    
    # Create output directory
    SNAPSHOT_OUTPUT_DIR.mkdir(exist_ok=True)
    print(f"✓ Created output directory: {SNAPSHOT_OUTPUT_DIR}")
    print()
    
    # 1. Test health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/health")
        response.raise_for_status()
        health = response.json()
        print(f"   ✓ Service Status: {health['status']}")
        print(f"   ✓ Redis Connected: {health['redis_connected']}")
        print(f"   ✓ Active Cameras: {health['active_cameras']}")
    except Exception as e:
        print(f"   ✗ Health check failed: {e}")
        return
    print()
    
    # 2. Test event statistics
    print("2. Testing event statistics...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/events/stats")
        response.raise_for_status()
        stats = response.json()
        print(f"   ✓ Total Events: {stats['total_events']}")
        print(f"   ✓ Events by Type:")
        for event_type, count in stats['events_by_type'].items():
            print(f"      - {event_type}: {count}")
        print(f"   ✓ Events by Camera:")
        for camera_id, count in stats['events_by_camera'].items():
            print(f"      - {camera_id}: {count}")
        
        if stats['date_range']:
            print(f"   ✓ Date Range:")
            print(f"      - First Event: {stats['date_range'].get('first_event', 'N/A')}")
            print(f"      - Last Event: {stats['date_range'].get('last_event', 'N/A')}")
    except Exception as e:
        print(f"   ✗ Stats request failed: {e}")
    print()
    
    # 3. Test listing events
    print("3. Testing event listing (last 10 events)...")
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/events",
            params={"page": 1, "page_size": 10}
        )
        response.raise_for_status()
        events_data = response.json()
        print(f"   ✓ Total Events: {events_data['total']}")
        print(f"   ✓ Page: {events_data['page']}/{(events_data['total'] - 1) // events_data['page_size'] + 1}")
        print(f"   ✓ Has More: {events_data['has_more']}")
        print()
        
        if events_data['events']:
            print("   Recent Events:")
            for i, event in enumerate(events_data['events'][:5], 1):
                print(f"   {i}. Event #{event['id']}")
                print(f"      - Type: {event['event_type']}")
                print(f"      - Camera: {event['camera_id']}")
                print(f"      - Timestamp: {event['timestamp']}")
                print(f"      - Frame: {event['frame_number']}")
                print(f"      - Has Snapshot: {'Yes' if event['snapshot_path'] else 'No'}")
                
                # Print event-specific data
                event_data = event['event_data']
                if event['event_type'] == 'tracking':
                    print(f"      - Track ID: {event_data.get('track_id')}")
                    print(f"      - Action: {event_data.get('tracking_action')}")
                    print(f"      - Class: {event_data.get('class_name')}")
                    print(f"      - Confidence: {event_data.get('confidence'):.2f}")
                elif event['event_type'] == 'motion':
                    print(f"      - Motion Intensity: {event_data.get('motion_intensity'):.2f}")
                    print(f"      - Affected Area: {event_data.get('affected_area_percentage'):.2%}")
                elif event['event_type'] == 'anpr':
                    anpr = event_data.get('anpr_result', {})
                    print(f"      - License Plate: {anpr.get('license_plate')}")
                    print(f"      - Confidence: {anpr.get('confidence'):.2f}")
                print()
            
            # Test downloading snapshots for first 3 events
            print("4. Testing snapshot download (first 3 events with snapshots)...")
            downloaded = 0
            for event in events_data['events']:
                if event['snapshot_path'] and downloaded < 3:
                    try:
                        print(f"   Downloading snapshot for Event #{event['id']}...")
                        response = requests.get(
                            f"{API_BASE_URL}/api/events/{event['id']}/snapshot"
                        )
                        response.raise_for_status()
                        
                        # Save snapshot
                        output_path = SNAPSHOT_OUTPUT_DIR / f"event_{event['id']}_snapshot.png"
                        output_path.write_bytes(response.content)
                        print(f"   ✓ Saved to: {output_path}")
                        downloaded += 1
                    except Exception as e:
                        print(f"   ✗ Failed to download snapshot: {e}")
            
            if downloaded == 0:
                print("   ℹ No snapshots available to download")
        else:
            print("   ℹ No events found")
    except Exception as e:
        print(f"   ✗ Event listing failed: {e}")
    print()
    
    # 4. Test filtering by event type
    print("5. Testing event filtering (motion events only)...")
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/events",
            params={"event_type": "motion", "page": 1, "page_size": 5}
        )
        response.raise_for_status()
        motion_events = response.json()
        print(f"   ✓ Motion Events Found: {motion_events['total']}")
        if motion_events['events']:
            print(f"   ✓ Latest Motion Event: {motion_events['events'][0]['timestamp']}")
    except Exception as e:
        print(f"   ✗ Motion events filtering failed: {e}")
    print()
    
    # 5. Test filtering by camera
    print("6. Testing camera-specific statistics...")
    try:
        # Get list of cameras from stats
        response = requests.get(f"{API_BASE_URL}/api/events/stats")
        response.raise_for_status()
        stats = response.json()
        
        for camera_id in list(stats['events_by_camera'].keys())[:2]:
            print(f"   Camera: {camera_id}")
            response = requests.get(
                f"{API_BASE_URL}/api/events/stats",
                params={"camera_id": camera_id}
            )
            response.raise_for_status()
            camera_stats = response.json()
            print(f"   ✓ Total Events: {camera_stats['total_events']}")
            for event_type, count in camera_stats['events_by_type'].items():
                if count > 0:
                    print(f"      - {event_type}: {count}")
            print()
    except Exception as e:
        print(f"   ✗ Camera filtering failed: {e}")
    print()
    
    # 6. Test date range filtering
    print("7. Testing date range filtering (last 24 hours)...")
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        response = requests.get(
            f"{API_BASE_URL}/api/events",
            params={
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "page": 1,
                "page_size": 5
            }
        )
        response.raise_for_status()
        recent_events = response.json()
        print(f"   ✓ Events in Last 24 Hours: {recent_events['total']}")
    except Exception as e:
        print(f"   ✗ Date range filtering failed: {e}")
    print()
    
    print("=" * 80)
    print("Testing Complete!")
    print(f"Downloaded snapshots saved to: {SNAPSHOT_OUTPUT_DIR.absolute()}")
    print("=" * 80)


if __name__ == "__main__":
    test_events_api()

