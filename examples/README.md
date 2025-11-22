# Examples

This directory contains example scripts and tools to help you understand and test the Video Analytics Service.

## Files

### `example_usage.sh`
**Quick API demonstration script**

A bash script that demonstrates basic API operations:
- Health check
- Camera registration
- Listing cameras
- Getting camera details
- Deleting cameras

**Usage:**
```bash
# Make sure the service is running first
cd examples
chmod +x example_usage.sh
./example_usage.sh
```

**Requirements:**
- `curl` (for API requests)
- `jq` (for JSON formatting, optional)

---

### `pubsub_consumer_example.py`
**Redis Pub/Sub consumer example**

Demonstrates how to consume real-time events from the analytics service using Redis Pub/Sub.

**Features:**
- Connects to Redis and subscribes to the `events` channel
- Receives and displays tracking, motion, and ANPR events in real-time
- Shows detailed event information including event ID, timestamps, and event-specific data
- Graceful shutdown with Ctrl+C
- Only receives the latest events (no historical data)

**Usage:**
```bash
# Make sure Redis is accessible at localhost:6379
cd examples
python pubsub_consumer_example.py
```

**Use Case:** Build your own real-time event consumer to integrate with other systems. Events are published as they occur and are also saved to the database for historical queries.

---

### `example_event_filtering.py`
**Event filtering demonstration**

An interactive script that demonstrates the effectiveness of event filtering by:
- Showing comparison between filtered vs unfiltered events
- Monitoring live events from the Redis stream
- Displaying event statistics and metrics
- Providing recommendations based on event rates

**Features:**
- Visual comparison table of filtering effectiveness
- Live event monitoring with formatted output
- Event rate analysis and recommendations
- Interactive prompts

**Usage:**
```bash
# Start the analytics service first
cd examples
python example_event_filtering.py
```

**What it shows:**
- How event filtering reduces events by 95-99%
- Real-world scenarios (person standing, car parked, etc.)
- Event rate per second and breakdown by type

---

### `compare_filtering_approaches.py`
**Time-based vs Tracking-based filtering comparison**

An educational script that demonstrates the differences between two filtering approaches:

1. **Time-based filtering** (legacy approach)
   - Uses cooldown periods and change thresholds
   - Can miss object swaps when counts remain the same

2. **Tracking-based filtering** (current approach)
   - Uses ByteTrack for object tracking
   - Detects entry/exit for each individual object
   - Provides accurate counting and dwell time

**Features:**
- Multiple interactive scenarios
- Side-by-side comparison of both approaches
- Detailed explanations of why tracking is better
- Visual output with emoji indicators

**Usage:**
```bash
cd examples
python compare_filtering_approaches.py
```

**Key Scenarios:**
- Person A leaves, Person B enters (same count)
- Parking lot with cars entering/leaving
- Person walks through and comes back
- Gradual crowd buildup

**Why it matters:**
This script explains why the service migrated from time-based to tracking-based filtering. Essential reading for understanding the tracking implementation.

---

## Quick Start

1. **Start the analytics service:**
   ```bash
   cd ..
   docker compose up -d
   ```

2. **Try the API example:**
   ```bash
   cd examples
   ./example_usage.sh
   ```

3. **Monitor real-time events:**
   ```bash
   python pubsub_consumer_example.py
   ```

4. **Learn about filtering:**
   ```bash
   python example_event_filtering.py
   ```

5. **Understand tracking:**
   ```bash
   python compare_filtering_approaches.py
   ```

## Dependencies

Most examples require:
- Python 3.8+
- Redis running at `localhost:6379`
- Analytics service running at `http://localhost:8069`

Python dependencies:
```bash
pip install redis
```

For the bash script:
```bash
# Install jq (optional, for pretty JSON output)
# macOS:
brew install jq

# Ubuntu/Debian:
sudo apt-get install jq
```

## See Also

- [Main README](../README.md) - Service overview and setup
- [OBJECT_TRACKING_PROPOSAL.md](../docs/OBJECT_TRACKING_PROPOSAL.md) - Technical details on tracking
- [API_REQUEST_RESPONSE.md](../docs/API_REQUEST_RESPONSE.md) - Complete API reference
- [TRACKING_IMPLEMENTATION_STATUS.md](../docs/TRACKING_IMPLEMENTATION_STATUS.md) - Implementation status

## Contributing

Feel free to add more examples! Good examples should:
- Be well-commented
- Include usage instructions
- Demonstrate a specific feature or use case
- Be runnable with minimal setup

