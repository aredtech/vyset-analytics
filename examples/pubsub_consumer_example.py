"""
Example Redis Pub/Sub consumer for receiving real-time events.

This example demonstrates how to subscribe to the Redis Pub/Sub channel
and receive events in real-time as they are published by the analytics service.

Events are still persisted in the database, but Pub/Sub allows you to
receive only the latest data without polling.
"""
import redis
import json
import signal
import sys
from datetime import datetime


class EventConsumer:
    """Redis Pub/Sub consumer for real-time events."""
    
    def __init__(self, host='localhost', port=6379, channel='events'):
        """
        Initialize the consumer.
        
        Args:
            host: Redis host
            port: Redis port
            channel: Pub/Sub channel name
        """
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=0,
            decode_responses=True
        )
        self.channel = channel
        self.pubsub = None
        self.running = False
    
    def start(self):
        """Start listening for events."""
        print(f"Connecting to Redis at {self.redis_client.connection_pool.connection_kwargs['host']}:{self.redis_client.connection_pool.connection_kwargs['port']}")
        print(f"Subscribing to channel: {self.channel}")
        
        # Create pubsub object and subscribe to channel
        self.pubsub = self.redis_client.pubsub()
        self.pubsub.subscribe(self.channel)
        
        print("✓ Successfully subscribed to Redis Pub/Sub")
        print("Waiting for events... (Press Ctrl+C to stop)\n")
        
        self.running = True
        
        # Listen for messages
        for message in self.pubsub.listen():
            if not self.running:
                break
                
            # Skip subscription confirmation messages
            if message['type'] == 'message':
                self.handle_event(message['data'])
    
    def handle_event(self, event_data_json):
        """
        Handle incoming event.
        
        Args:
            event_data_json: JSON string of event data
        """
        try:
            # Parse event data
            event = json.loads(event_data_json)
            
            # Extract common fields
            event_id = event.get('id')
            event_type = event.get('event_type')
            camera_id = event.get('camera_id')
            timestamp = event.get('timestamp')
            frame_number = event.get('frame_number')
            event_data = event.get('event_data', {})
            
            # Format timestamp for display
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = timestamp
            
            # Print event header
            print(f"{'='*70}")
            print(f"Event ID: {event_id}")
            print(f"Type: {event_type.upper()}")
            print(f"Camera: {camera_id}")
            print(f"Time: {time_str}")
            print(f"Frame: {frame_number}")
            
            # Print event-specific details
            if event_type == 'tracking':
                track_id = event_data.get('track_id')
                action = event_data.get('tracking_action')
                class_name = event_data.get('class_name')
                confidence = event_data.get('confidence')
                dwell_time = event_data.get('dwell_time_seconds')
                
                print(f"Action: {action.upper()}")
                print(f"Object: {class_name} (confidence: {confidence:.2f})")
                print(f"Track ID: {track_id}")
                if dwell_time:
                    print(f"Dwell Time: {dwell_time:.2f}s")
            
            elif event_type == 'motion':
                motion_intensity = event_data.get('motion_intensity')
                affected_area = event_data.get('affected_area_percentage')
                
                print(f"Motion Intensity: {motion_intensity:.2f}")
                print(f"Affected Area: {affected_area:.2f}%")
            
            elif event_type == 'anpr':
                anpr_result = event_data.get('anpr_result', {})
                license_plate = anpr_result.get('license_plate')
                confidence = anpr_result.get('confidence')
                region = anpr_result.get('region')
                
                print(f"License Plate: {license_plate}")
                print(f"Confidence: {confidence:.2f}")
                if region:
                    print(f"Region: {region}")
            
            print(f"{'='*70}\n")
            
        except json.JSONDecodeError as e:
            print(f"Error parsing event JSON: {e}")
        except Exception as e:
            print(f"Error handling event: {e}")
    
    def stop(self):
        """Stop listening for events."""
        print("\nStopping consumer...")
        self.running = False
        if self.pubsub:
            self.pubsub.unsubscribe()
            self.pubsub.close()
        self.redis_client.close()
        print("Consumer stopped")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\nReceived interrupt signal")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Configuration
    REDIS_HOST = 'localhost'
    REDIS_PORT = 6379
    CHANNEL_NAME = 'events'
    
    # Create and start consumer
    consumer = EventConsumer(
        host=REDIS_HOST,
        port=REDIS_PORT,
        channel=CHANNEL_NAME
    )
    
    try:
        consumer.start()
    except KeyboardInterrupt:
        consumer.stop()
    except Exception as e:
        print(f"Error: {e}")
        consumer.stop()
        sys.exit(1)

