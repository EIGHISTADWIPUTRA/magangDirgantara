"""
Bluetooth SPP Image Receiver for Raspberry Pi.

This module provides a Bluetooth Serial Port Profile (SPP) based receiver
for receiving target images from an Android device via /dev/rfcomm0.

Prerequisites (Raspberry Pi configuration):
    1. Enable -C flag on bluetoothd (compatibility mode)
    2. Add sdptool SP in dbus-org.bluez.service
    3. Configure rfcomm.service to run 'rfcomm watch hci0' at boot
    4. Bluetooth connection is automatically mapped to /dev/rfcomm0

Protocol:
    Image transfer uses a custom binary protocol:
    1. Header: "IMG:" (4 bytes)
    2. File size: 8 bytes (zero-padded decimal string)
    3. File extension: 10 bytes (space-padded string)
    4. Image data: variable length binary data
    5. Server response: "OK" or "FAIL"

    Command protocol:
    1. Header: "CMD:" (4 bytes)
    2. Command string terminated by newline '\\n'
    3. Server executes command and sends result back

    Supported commands:
    - HEALTH          : Run full health check on all sensors
    - HEALTH:<sensor> : Check specific sensor (bmp280, mpu6050, gy511, camera, lora)
    - LORA_SENSOR     : Send one round of sensor data via LoRa (all sensors)
    - LORA_SENSOR:<type> : Send specific sensor data (bmp280, mpu6050, gy511, all)
    
    Response format:
    - HEALTH_RESULT:<sensor>=<status>,...|<summary>\n
    - LORA_RESULT:OK|<message>\n  or  LORA_RESULT:FAIL|<error>\n
    - CMD_ERROR:<message>\n

Usage:
    python bluetooth_server.py [port] [save_folder]

    Examples:
        python bluetooth_server.py
        python bluetooth_server.py /dev/rfcomm1
        python bluetooth_server.py /dev/rfcomm0 my_images/

Configuration:
    - Port: /dev/rfcomm0
    - Baudrate: 115200
    - Save folder: received_images/

Dependencies:
    pip install pyserial
"""

import os
import sys

# Ensure the project root (parent of finalCode/) is on sys.path
# so 'from finalCode.xxx import yyy' works when running from any directory
_this_file = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_this_file))  # server/ -> finalCode/ -> MAGANG/
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import time
import serial
from datetime import datetime


class BluetoothImageReceiver:
    """
    Receives images via Bluetooth SPP through /dev/rfcomm0.
    
    The Bluetooth connection is handled by the system (rfcomm.service).
    This class reads image data from the serial port and saves it to disk.
    
    Attributes:
        port: Serial port path (default: /dev/rfcomm0).
        baudrate: Serial communication speed (default: 115200).
        save_folder: Directory to save received images.
        serial_conn: Active serial connection or None.
    """

    def __init__(self, port: str = '/dev/rfcomm0', baudrate: int = 115200,
                 save_folder: str = 'received_images'):
        """
        Initialize the Bluetooth image receiver.

        Args:
            port: Serial port path for Bluetooth connection.
            baudrate: Serial communication baudrate.
            save_folder: Directory path to save received images.
        """
        self.port = port
        self.baudrate = baudrate
        self.save_folder = save_folder
        self.serial_conn = None

        # Create save folder if it doesn't exist
        if not os.path.exists(self.save_folder):
            os.makedirs(self.save_folder)
            print(f"[INFO] Folder '{self.save_folder}' created")

    def wait_for_connection(self, timeout: float = None) -> bool:
        """
        Wait for Bluetooth connection to become available.

        Polls for the existence of the serial port and attempts to open it.

        Args:
            timeout: Maximum time to wait in seconds. None for infinite wait.

        Returns:
            True if connection established, False if timeout reached.
        """
        print(f"[INFO] Waiting for Bluetooth connection at {self.port}...")

        start_time = time.time()
        while True:
            if os.path.exists(self.port):
                try:
                    self.serial_conn = serial.Serial(
                        port=self.port,
                        baudrate=self.baudrate,
                        timeout=5
                    )
                    print(f"[INFO] Connected to {self.port}")
                    return True
                except serial.SerialException as e:
                    print(f"[WARNING] Failed to open port: {e}")
                    time.sleep(1)
            else:
                if timeout and (time.time() - start_time) > timeout:
                    print("[ERROR] Timeout waiting for connection")
                    return False
                time.sleep(0.5)

    def receive_image(self) -> str:
        """
        Receive an image from the connected Android client.

        Protocol:
            1. Client sends header "IMG:" (4 bytes)
            2. Client sends file size (8 bytes, zero-padded decimal)
            3. Client sends file extension (10 bytes, space-padded)
            4. Client sends image data
            5. Server sends "OK" or "FAIL"

        Returns:
            Path to saved image file, or None on failure.
        """
        try:
            # Wait for header "IMG:"
            header = self.serial_conn.read(4)
            if not header:
                return None

            if header != b'IMG:':
                # Not image data, might be telemetry
                print(f"[DEBUG] Data received (not image): {header}")
                return None

            # Read file size (8 bytes)
            size_data = self.serial_conn.read(8)
            if not size_data or len(size_data) < 8:
                print("[ERROR] Failed to read file size")
                return None

            file_size = int(size_data.decode().strip())
            print(f"[INFO] File size: {file_size} bytes")

            # Read file extension (10 bytes)
            ext_data = self.serial_conn.read(10)
            if not ext_data or len(ext_data) < 10:
                print("[ERROR] Failed to read file extension")
                return None

            extension = ext_data.decode().strip()
            print(f"[INFO] File extension: {extension}")

            # Receive image data
            received_data = b''
            while len(received_data) < file_size:
                remaining = file_size - len(received_data)
                chunk = self.serial_conn.read(min(4096, remaining))
                if not chunk:
                    break
                received_data += chunk
                progress = (len(received_data) / file_size) * 100
                print(f"\r[INFO] Progress: {progress:.1f}%", end='', flush=True)

            print()  # Newline after progress

            if len(received_data) == file_size:
                # Save image
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"bt_image_{timestamp}.{extension}"
                filepath = os.path.join(self.save_folder, filename)

                with open(filepath, 'wb') as f:
                    f.write(received_data)

                print(f"[INFO] Image saved: {filepath}")

                # Send confirmation to client
                self.serial_conn.write(b"OK")
                self.serial_conn.flush()
                return filepath
            else:
                print(f"[ERROR] Incomplete data: {len(received_data)}/{file_size}")
                self.serial_conn.write(b"FAIL")
                self.serial_conn.flush()
                return None

        except Exception as e:
            print(f"[ERROR] Failed to receive image: {e}")
            return None

    def read_telemetry(self) -> str:
        """
        Read telemetry data (non-image data) from the connection.

        Returns:
            Decoded telemetry string, or None if no data available.
        """
        try:
            if self.serial_conn and self.serial_conn.in_waiting > 0:
                data = self.serial_conn.readline()
                if data:
                    return data.decode().strip()
        except Exception as e:
            print(f"[ERROR] Failed to read telemetry: {e}")
        return None

    def send_data(self, data) -> bool:
        """
        Send data to the connected Android device.

        Args:
            data: String or bytes to send.

        Returns:
            True if data sent successfully, False otherwise.
        """
        try:
            if self.serial_conn:
                if isinstance(data, str):
                    data = data.encode()
                self.serial_conn.write(data)
                self.serial_conn.flush()
                return True
        except Exception as e:
            print(f"[ERROR] Failed to send data: {e}")
        return False

    def close(self):
        """Close the serial connection."""
        if self.serial_conn:
            try:
                self.serial_conn.close()
                self.serial_conn = None
                print("[INFO] Connection closed")
            except Exception:
                pass

    def is_connected(self) -> bool:
        """
        Check if the connection is still active.

        Returns:
            True if connected, False otherwise.
        """
        return self.serial_conn is not None and self.serial_conn.is_open

    def run(self):
        """
        Run the receiver in a continuous loop.

        Continuously monitors for incoming data and processes images
        or telemetry accordingly. Automatically reconnects on disconnection.
        """
        print("=" * 50)
        print("  BLUETOOTH IMAGE RECEIVER (SPP)")
        print("=" * 50)
        print(f"Port: {self.port}")
        print(f"Save folder: {self.save_folder}")
        print("-" * 50)

        try:
            while True:
                # Wait for connection
                if not self.is_connected():
                    if not self.wait_for_connection():
                        time.sleep(2)
                        continue

                try:
                    # Check if data is available
                    if self.serial_conn.in_waiting > 0:
                        # Peek header to determine data type
                        peek = self.serial_conn.read(4)

                        if peek == b'IMG:':
                            # Image data - process with _process_image_after_header
                            self._process_image_after_header()
                        elif peek == b'CMD:':
                            # Command data - process command
                            self._process_command()
                        else:
                            # Read rest of line and combine with peek
                            remaining = self.serial_conn.readline()
                            full_data = (peek + remaining).decode().strip()
                            
                            # Check if it's a plain text command (no CMD: prefix)
                            if self._is_known_command(full_data):
                                print(f"[CMD] Received command: {full_data}")
                                self._execute_command(full_data)
                            else:
                                print(f"[TELEMETRY] {full_data}")
                    else:
                        time.sleep(0.1)

                except serial.SerialException as e:
                    print(f"[WARNING] Connection lost: {e}")
                    self.close()
                    print("[INFO] Waiting for reconnection...")

        except KeyboardInterrupt:
            print("\n[INFO] Stopped by user")
        finally:
            self.close()

    def _process_image_after_header(self) -> str:
        """
        Process image data after the IMG: header has been read.

        This is called internally when the run() loop detects an image header.

        Returns:
            Path to saved image file, or None on failure.
        """
        try:
            # Read file size (8 bytes)
            size_data = self.serial_conn.read(8)
            if not size_data or len(size_data) < 8:
                print("[ERROR] Failed to read file size")
                return None

            file_size = int(size_data.decode().strip())
            print(f"[INFO] Receiving image - Size: {file_size} bytes")

            # Read file extension (10 bytes)
            ext_data = self.serial_conn.read(10)
            extension = ext_data.decode().strip()
            print(f"[INFO] Extension: {extension}")

            # Receive image data
            received_data = b''
            while len(received_data) < file_size:
                remaining = file_size - len(received_data)
                chunk = self.serial_conn.read(min(4096, remaining))
                if not chunk:
                    break
                received_data += chunk
                progress = (len(received_data) / file_size) * 100
                print(f"\r[INFO] Progress: {progress:.1f}%", end='', flush=True)

            print()

            if len(received_data) == file_size:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"bt_image_{timestamp}.{extension}"
                filepath = os.path.join(self.save_folder, filename)

                with open(filepath, 'wb') as f:
                    f.write(received_data)

                print(f"[INFO] Image saved: {filepath}")
                self.serial_conn.write(b"OK")
                self.serial_conn.flush()
                return filepath
            else:
                print(f"[ERROR] Incomplete data: {len(received_data)}/{file_size}")
                self.serial_conn.write(b"FAIL")
                self.serial_conn.flush()
                return None

        except Exception as e:
            print(f"[ERROR] Failed to receive image: {e}")
            return None

    def _process_command(self):
        """
        Read and execute a command received via Bluetooth.
        
        Command format: CMD:<command_string>\\n
        The CMD: header has already been read by the run() loop.
        """
        try:
            # Read until newline to get the command string
            cmd_line = self.serial_conn.readline().decode().strip()
            print(f"[CMD] Received command: {cmd_line}")
            self._execute_command(cmd_line)
        except Exception as e:
            response = f"CMD_ERROR:Failed to process command - {e}\n"
            self.send_data(response)
            print(f"[CMD] Error: {e}")

    def _is_known_command(self, text: str) -> bool:
        """
        Check if the given text is a known command.
        
        Args:
            text: The text to check.
            
        Returns:
            True if the text starts with a known command keyword.
        """
        known_commands = ('HEALTH', 'LORA_SENSOR')
        return any(text.startswith(cmd) for cmd in known_commands)

    def _execute_command(self, cmd_line: str):
        """
        Execute a command string and send the result back.
        
        This is called by both _process_command() (for CMD: prefixed commands)
        and the plain text command path in run().
        
        Args:
            cmd_line: The command string (e.g., "HEALTH" or "LORA_SENSOR:bmp280")
        """
        try:
            if cmd_line.startswith('HEALTH'):
                self._handle_health_command(cmd_line)
            elif cmd_line.startswith('LORA_SENSOR'):
                self._handle_lora_sensor_command(cmd_line)
            else:
                response = f"CMD_ERROR:Unknown command '{cmd_line}'\n"
                self.send_data(response)
                print(f"[CMD] Error: Unknown command")
        except Exception as e:
            response = f"CMD_ERROR:Failed to execute command - {e}\n"
            self.send_data(response)
            print(f"[CMD] Error: {e}")

    def _handle_health_command(self, cmd_line):
        """
        Execute health check and send results back.
        
        Supports:
        - HEALTH: Run all checks
        - HEALTH:<sensor>: Check specific sensor (bmp280, mpu6050, gy511, camera, lora)
        
        Args:
            cmd_line: The command string (e.g., "HEALTH" or "HEALTH:bmp280")
        """
        try:
            # Dynamic import to avoid dependency issues
            from finalCode.sensor.health_check import HealthChecker
            
            checker = HealthChecker()
            
            if cmd_line == 'HEALTH':
                # Run all checks
                print("[CMD] Running full health check...")
                checker.run_all_checks()
                results = checker.get_results()
                
                # Format results as compact string
                parts = []
                for sensor in ['bmp280', 'mpu6050', 'gy511', 'camera', 'lora']:
                    if sensor in results:
                        status = results[sensor].get('status', 'UNKNOWN')
                        parts.append(f"{sensor.upper()}={status}")
                
                # Determine summary
                statuses = [results.get(s, {}).get('status', 'UNKNOWN') 
                           for s in ['bmp280', 'mpu6050', 'gy511', 'camera', 'lora']]
                if all(s == 'SEHAT' for s in statuses):
                    summary = 'ALL_OK'
                elif any(s == 'SEHAT' for s in statuses):
                    summary = 'PARTIAL'
                else:
                    summary = 'ALL_FAIL'
                
                response = f"HEALTH_RESULT:{','.join(parts)}|{summary}\n"
                self.send_data(response)
                print(f"[CMD] Health check complete: {summary}")
                
            elif ':' in cmd_line:
                # Check specific sensor
                _, sensor_name = cmd_line.split(':', 1)
                sensor_name = sensor_name.lower().strip()
                
                sensor_methods = {
                    'bmp280': checker.check_bmp280,
                    'bmp': checker.check_bmp280,
                    'mpu6050': checker.check_mpu6050,
                    'mpu': checker.check_mpu6050,
                    'gy511': checker.check_gy511,
                    'gy': checker.check_gy511,
                    'camera': checker.check_camera,
                    'cam': checker.check_camera,
                    'lora': checker.check_lora
                }
                
                if sensor_name in sensor_methods:
                    print(f"[CMD] Checking sensor: {sensor_name}")
                    sensor_methods[sensor_name]()
                    results = checker.get_results()
                    
                    # Get the canonical sensor name
                    canonical = sensor_name
                    if sensor_name in ['bmp']:
                        canonical = 'bmp280'
                    elif sensor_name in ['mpu']:
                        canonical = 'mpu6050'
                    elif sensor_name in ['gy']:
                        canonical = 'gy511'
                    elif sensor_name in ['cam']:
                        canonical = 'camera'
                    
                    if canonical in results:
                        status = results[canonical].get('status', 'UNKNOWN')
                        response = f"HEALTH_RESULT:{canonical.upper()}={status}|SINGLE\n"
                    else:
                        response = f"HEALTH_RESULT:{sensor_name.upper()}=UNKNOWN|SINGLE\n"
                    
                    self.send_data(response)
                    print(f"[CMD] Sensor check complete: {sensor_name}")
                else:
                    response = f"CMD_ERROR:Unknown sensor '{sensor_name}'\n"
                    self.send_data(response)
            else:
                response = f"CMD_ERROR:Invalid HEALTH command format\n"
                self.send_data(response)
                
        except ImportError as e:
            response = f"CMD_ERROR:Health check not available - {e}\n"
            self.send_data(response)
            print(f"[CMD] Error: HealthChecker import failed - {e}")
        except Exception as e:
            response = f"CMD_ERROR:Health check failed - {e}\n"
            self.send_data(response)
            print(f"[CMD] Error: {e}")

    def _handle_lora_sensor_command(self, cmd_line):
        """
        Execute LoRa sensor send and return result.
        
        Supports:
        - LORA_SENSOR: Send all sensor data
        - LORA_SENSOR:<type>: Send specific sensor data (bmp280, mpu6050, gy511, all)
        
        Args:
            cmd_line: The command string (e.g., "LORA_SENSOR" or "LORA_SENSOR:bmp280")
        """
        sender = None
        try:
            # Dynamic imports
            from finalCode.lora.sender_sensor import LoRaSensorSender

            # Determine which sensor(s) to use
            if ':' in cmd_line:
                _, sensor_type = cmd_line.split(':', 1)
                sensor_type = sensor_type.lower().strip()
            else:
                sensor_type = 'all'

            print(f"[CMD] Sending LoRa sensor data: {sensor_type}")

            # Initialize sender — GPIO setup and validation are encapsulated inside
            sender = LoRaSensorSender(sensors=sensor_type, verbose=False)
            
            # Send one round of data
            counter = 1
            success, message = sender.kirim_data(counter)
            
            if success:
                response = f"LORA_RESULT:OK|{message}\n"
                print(f"[CMD] LoRa send success: {message}")
            else:
                response = f"LORA_RESULT:FAIL|Timeout sending message\n"
                print(f"[CMD] LoRa send failed: timeout")
            
            self.send_data(response)
            
        except ImportError as e:
            response = f"LORA_RESULT:FAIL|LoRa module not available - {e}\n"
            self.send_data(response)
            print(f"[CMD] Error: LoRa import failed - {e}")
        except ValueError as e:
            response = f"LORA_RESULT:FAIL|Invalid configuration - {e}\n"
            self.send_data(response)
            print(f"[CMD] Error: {e}")
        except Exception as e:
            response = f"LORA_RESULT:FAIL|{e}\n"
            self.send_data(response)
            print(f"[CMD] Error: {e}")
        finally:
            # Cleanup LoRa resources
            if sender is not None:
                try:
                    sender.cleanup()
                except Exception:
                    pass


if __name__ == "__main__":
    # Default settings
    port = '/dev/rfcomm0'
    save_folder = 'received_images'

    # Parse command line arguments
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        save_folder = sys.argv[2]

    receiver = BluetoothImageReceiver(
        port=port,
        save_folder=save_folder
    )
    receiver.run()
