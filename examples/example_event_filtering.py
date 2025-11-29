#!/usr/bin/env python3
"""
Example script demonstrating event filtering effectiveness.
This simulates the difference between filtered and unfiltered events.
"""

import json
import time
import redis
from datetime import datetime

# Configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_PASSWORD = None  # Set to your Redis password if authentication is enabled
REDIS_CHANNEL = 'events'
MONITOR_DURATION = 30  # seconds


def format_event(event):
    """Format event for display."""
    event_type = event.get('event_type', 'unknown')
    camera_id = event.get('camera_id', 'unknown')
    timestamp = event.get('timestamp', '')
    event_data = event.get('event_data', {})
    
    if event_type == 'tracking':
        action = event_data.get('tracking_action', 'unknown')
        class_name = event_data.get('class_name', 'unknown')
        details = f"{action.upper()}: {class_name}"
    elif event_type == 'motion':
        intensity = event_data.get('motion_intensity', 0)
        area = event_data.get('affected_area_percentage', 0)
        details = f"Intensity: {intensity:.2f}, Area: {area:.2f}%"
    elif event_type == 'anpr':
        anpr_result = event_data.get('anpr_result', {})
        plate = anpr_result.get('license_plate', 'unknown')
        confidence = anpr_result.get('confidence', 0)
        details = f"Plate: {plate} (confidence: {confidence:.2f})"
    else:
        details = ""
    
    return f"[{timestamp}] {event_type.upper()} from {camera_id} - {details}"


def monitor_events():
    """Monitor and display events from Redis Pub/Sub."""
    try:
        connection_kwargs = {
            "host": REDIS_HOST,
            "port": REDIS_PORT,
            "decode_responses": True
        }
        if REDIS_PASSWORD:
            connection_kwargs["password"] = REDIS_PASSWORD
        
        r = redis.Redis(**connection_kwargs)
        r.ping()
        print(f"✅ Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        print(f"❌ Failed to connect to Redis: {e}")
        print(f"   Make sure Redis is running at {REDIS_HOST}:{REDIS_PORT}")
        return
    
    print(f"\n📊 Monitoring events from channel '{REDIS_CHANNEL}' for {MONITOR_DURATION} seconds...")
    print("=" * 80)
    
    # Subscribe to Pub/Sub channel
    try:
        pubsub = r.pubsub()
        pubsub.subscribe(REDIS_CHANNEL)
        
        start_time = time.time()
        event_count = 0
        event_types = {'tracking': 0, 'motion': 0, 'anpr': 0}
        
        while time.time() - start_time < MONITOR_DURATION:
            try:
                # Listen for messages with timeout
                message = pubsub.get_message(timeout=1.0)
                
                if message and message['type'] == 'message':
                    event_count += 1
                    
                    # Parse and display event
                    try:
                        event_obj = json.loads(message['data'])
                        event_type = event_obj.get('event_type', 'unknown')
                        event_types[event_type] = event_types.get(event_type, 0) + 1
                        print(format_event(event_obj))
                    except Exception as e:
                        print(f"Error parsing event: {e}")
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error reading from Pub/Sub: {e}")
                time.sleep(1)
        
        # Print summary
        elapsed = time.time() - start_time
        print("\n" + "=" * 80)
        print(f"📈 SUMMARY (monitoring for {elapsed:.1f} seconds)")
        print("=" * 80)
        print(f"Total events received: {event_count}")
        print(f"Events per second: {event_count / elapsed:.2f}")
        print(f"\nBreakdown by type:")
        for event_type, count in event_types.items():
            if count > 0:
                print(f"  - {event_type}: {count} events")
        
        print("\n💡 TIPS:")
        if event_count / elapsed > 10:
            print("  ⚠️  High event rate detected!")
            print("  Consider increasing cooldown periods:")
            print("     - motion_cooldown_seconds: 5.0 (for motion events)")
            print("     - anpr_cooldown_seconds: 5.0 (for ANPR events)")
        elif event_count / elapsed < 0.5:
            print("  ✅ Event rate looks good!")
            print("  Event filtering and tracking are working effectively.")
        else:
            print("  ✅ Event rate is reasonable.")
            print("  Monitor for a longer period to verify consistency.")
        
    except Exception as e:
        print(f"Error monitoring events: {e}")


def show_comparison():
    """Show a comparison table of filtered vs unfiltered events."""
    print("\n" + "=" * 80)
    print("EVENT FILTERING COMPARISON")
    print("=" * 80)
    
    scenarios = [
        {
            "scenario": "Person standing for 30 seconds",
            "without_filter": "900 events (30 FPS × 30 sec)",
            "with_filter": "2-3 events (appear, maybe move, leave)"
        },
        {
            "scenario": "Car parked for 5 minutes",
            "without_filter": "9,000 events (30 FPS × 300 sec)",
            "with_filter": "1-2 events (arrive, depart)"
        },
        {
            "scenario": "3 people walking through (10 sec each)",
            "without_filter": "900 events (30 people-sec × 30 FPS)",
            "with_filter": "6-9 events (each person: enter, exit, maybe middle)"
        },
        {
            "scenario": "License plate passing by (3 seconds)",
            "without_filter": "90 ANPR events (30 FPS × 3 sec)",
            "with_filter": "1 ANPR event (first detection)"
        },
    ]
    
    print(f"\n{'Scenario':<40} {'Without Filter':<30} {'With Filter':<30}")
    print("-" * 100)
    for item in scenarios:
        print(f"{item['scenario']:<40} {item['without_filter']:<30} {item['with_filter']:<30}")
    
    print("\n💡 Event filtering typically reduces events by 95-99%!")
    print("=" * 80)


def main():
    """Main function."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       EVENT FILTERING DEMONSTRATION                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

This script monitors events from the analytics service to demonstrate 
event filtering effectiveness.

SETUP:
1. Make sure the analytics service is running
2. Ensure Redis is accessible at localhost:6379
3. Add a camera with object detection enabled

USAGE:
  python example_event_filtering.py
""")
    
    # Show comparison first
    show_comparison()
    
    # Ask user if they want to monitor
    try:
        response = input("\n📡 Would you like to monitor live events? (y/n): ").strip().lower()
        if response == 'y':
            monitor_events()
        else:
            print("\n👋 Goodbye!")
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")


if __name__ == "__main__":
    main()

