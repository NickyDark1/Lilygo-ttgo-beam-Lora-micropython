# Lilygo-ttgo-beam-Lora-micropython


![image](https://github.com/user-attachments/assets/03d7b4d4-de62-42f7-8585-d4bdc85728c9)

A long-range wireless communication system based on LoRa technology using TTGO T-Beam devices with ESP32 and SX1276 modules. Optimized for long-range communication with low power consumption.



## 🚀 Features

- Bidirectional communication between LoRa nodes
- Optimized implementation for TTGO T-Beam devices
- Structured message format using JSON
- Low power mode support
- LED indicators for visual diagnostics
- Message acknowledgment system (ACK)
- Integrated battery monitoring
- Complete documentation

## 📋 Requirements

### Hardware
- 2+ TTGO T-Beam devices (preferably v1.0 or higher)
- 18650 batteries (optional, also works with USB power)
- Micro USB cables for programming

### Software
- MicroPython for ESP32 (v1.18 or higher)
- Tool for uploading files (Thonny, ampy, rshell, etc.)

## 🔧 Installation

### 1. Flash MicroPython

If your devices don't have MicroPython yet:

```bash
# Erase flash
esptool.py --port /dev/ttyUSB0 erase_flash

# Write firmware
esptool.py --port /dev/ttyUSB0 --baud 460800 write_flash -z 0x1000 esp32-20220117-v1.18.bin
```

### 2. Upload Libraries

Upload the base libraries to both devices:

```bash
# Using ampy (adjust the port according to your system)
ampy --port /dev/ttyUSB0 put lora_optimized.py
ampy --port /dev/ttyUSB0 put tbeam_optimized.py
```

### 3. Configure Nodes

For **Node 1** (sender):
```bash
# Adjust the file according to your configuration if necessary
ampy --port /dev/ttyUSB0 put node1_main.py main.py
```

For **Node 2** (receiver):
```bash
# Adjust the file according to your configuration if necessary
ampy --port /dev/ttyUSB0 put node2_main.py main.py
```

## 📊 Project Structure

```
ttgo-tbeam-lora/
├── lora_optimized.py         # Optimized LoRa library
├── tbeam_optimized.py        # T-Beam controller
├── node1_main.py             # Main program for sender node
├── node2_main.py             # Main program for receiver node
```

## 🖥️ Usage

### Basic Configuration

Before uploading the code, you can adjust the configuration in the main files:

**For node1_main.py:**
```python
NODE_ID = "NODE1"              # Unique identifier
DESTINATION_ID = "NODE2"       # Target node
FREQUENCY = 868.0              # Frequency in MHz
SEND_INTERVAL = 10000          # Send interval (ms)
```

**For node2_main.py:**
```python
NODE_ID = "NODE2"              # Unique identifier
PEER_NODE = "NODE1"            # Sender node
FREQUENCY = 868.0              # Frequency in MHz
STATS_INTERVAL = 30000         # Statistics interval (ms)
```

### Messages

The system uses JSON messages with the following structure:

```json
{
  "type": "DATA",               // Message type (DATA, PING, PONG, ACK...)
  "src": "NODE1",               // Source node
  "dst": "NODE2",               // Destination node
  "id": "NODE1_42",             // Unique message ID
  "content": {                  // Message content
    "temp": 21.5,
    "humidity": 65,
    "pressure": 1013,
    "battery": 3.8,
    "uptime": 3600
  }
}
```

### Monitoring

To monitor messages, connect the device via USB and use a serial terminal tool:

```bash
# On Linux/Mac
screen /dev/ttyUSB0 115200

# On Windows with PuTTY, connect to the corresponding COM port at 115200 baud
```

## 📡 LoRa Parameters

The library allows adjusting various LoRa parameters to suit your needs:

| Parameter | Common Values | Effect |
|-----------|---------------|--------|
| Frequency | 433, 868, 915 MHz | Based on regional regulations |
| Spreading Factor | 7-12 | Higher SF = longer range but lower speed |
| Bandwidth | 125, 250, 500 kHz | Lower BW = higher sensitivity |
| TX Power | 2-20 dBm | Higher power = longer range but more consumption |
| Coding Rate | 5-8 | Higher CR = more redundancy but lower speed |

Example adjustment:
```python
# For long range
tbeam.set_lora_param("spreading_factor", 12)
tbeam.set_lora_param("bandwidth", 125000)
tbeam.set_lora_param("coding_rate", 8)

# For speed
tbeam.set_lora_param("spreading_factor", 7)
tbeam.set_lora_param("bandwidth", 500000)
tbeam.set_lora_param("coding_rate", 5)
```

## 🔄 Communication Cycle

1. Node 1 sends data periodically
2. Node 2 receives, processes, and responds
3. Node 1 confirms receipt of the response
4. Both nodes can send PINGs to verify connectivity

![image](https://github.com/user-attachments/assets/9268cf8b-2bd6-402f-b1fe-b1369db691c8)

## 🔋 Power Management

To maximize battery life:

```python
# Low power mode between transmissions
tbeam.standby()
time.sleep_ms(5000)
tbeam.wake()

# For deep sleep (will restart upon waking)
tbeam.sleep(duration_ms=3600000)  # Sleep for 1 hour
```

## 🛠️ Troubleshooting

| Problem | Possible solution |
|---------|-------------------|
| No communication | Check frequency and LoRa parameters |
| Initialization errors | Check battery voltage and restart |
| Limited range | Increase SF, reduce BW, increase TX power |
| LED not blinking | Check PIN_LED1 in tbeam_optimized.py |
| Corrupted messages | Enable CRC, adjust coding_rate |

## 🔭 Example Projects

- **Weather Station**: Connect a BME280 to Node 1 and send climate data
- **GPS Tracking**: Enable GPS and periodically send coordinates
- **Remote Control**: Control relays or actuators from another node
- **Mesh Network**: Implement message forwarding to create a sensor network
