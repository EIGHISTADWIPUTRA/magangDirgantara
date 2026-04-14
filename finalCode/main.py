"""
Unified entry point for the finalCode package.

This module provides a command-line interface for all package functionality
including object detection (ORB), server operations (WiFi/Bluetooth),
LoRa communication, and system health checks.

Usage:
    python -m finalCode.main detect       # ORB detection with camera
    python -m finalCode.main server wifi  # Start WiFi server
    python -m finalCode.main server bt    # Start Bluetooth server
    python -m finalCode.main lora send    # LoRa basic sender
    python -m finalCode.main lora send sikap  # LoRa sikap payload sender
    python -m finalCode.main lora sensor --sensor gpsm6n  # LoRa + GPSM6N sender
    python -m finalCode.main lora ping    # LoRa ping-pong test
    python -m finalCode.main health       # Run health check on all sensors

Can also be run directly:
    python finalCode/main.py <command>
"""

import os
import sys

# Ensure the parent directory of finalCode is on sys.path
# so 'from finalCode.xxx import yyy' works when running from any directory
_package_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_package_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import argparse
import time


# ─── Banner ───────────────────────────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║                     FINAL CODE SYSTEM                        ║
║          Vision • LoRa • Sensors • Communication             ║
╚══════════════════════════════════════════════════════════════╝
"""


def print_banner():
    """Print the application banner."""
    print(BANNER)


# ─── Command Handlers ─────────────────────────────────────────────────────────

def cmd_detect(args):
    """Run ORB feature detection with camera."""
    import cv2
    from finalCode.config import RECEIVED_IMAGES_DIR, MIN_GOOD_MATCHES
    from finalCode.camera.stream import WebcamStream
    from finalCode.detection.orb_matcher import ORBMatcher

    print_banner()
    print("[*] Starting ORB Feature Detection...")
    print("-" * 50)

    camera = None
    try:
        # Initialize camera
        print("[*] Initializing camera...")
        camera = WebcamStream()
        
        if not camera.is_ready():
            print("[x] Failed to initialize camera")
            return 1

        # Initialize ORB matcher and load targets
        print("[*] Initializing ORB matcher...")
        matcher = ORBMatcher()
        
        num_targets = matcher.load_targets(RECEIVED_IMAGES_DIR)
        if num_targets == 0:
            print(f"[!] No target images found in '{RECEIVED_IMAGES_DIR}/'")
            print("[!] Running in preview mode only")

        print("-" * 50)
        print("[*] Detection running. Press 'q' to quit.")
        print("-" * 50)

        prev_time = time.time()

        while True:
            ret, frame = camera.get_frame()
            if not ret or frame is None:
                print("[!] Failed to capture frame")
                continue

            # Calculate FPS
            curr_time = time.time()
            fps = 1.0 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
            prev_time = curr_time

            # Match frame against targets
            if num_targets > 0:
                match_info = matcher.match_frame(frame)
                
                if match_info:
                    # Draw match visualization
                    viz = matcher.draw_matches(
                        frame,
                        match_info['frame_keypoints'],
                        match_info,
                        fps=fps
                    )
                    
                    if viz is not None:
                        cv2.imshow('ORB Detection', viz)
                        
                        # Print detection status
                        if match_info['count'] >= MIN_GOOD_MATCHES:
                            print(f"\r[DETECTED] {match_info['name']} - {match_info['count']} matches", end='', flush=True)
                    else:
                        cv2.imshow('ORB Detection', frame)
                else:
                    # No match, show raw frame with FPS
                    cv2.putText(frame, f"FPS: {int(fps)}", (frame.shape[1] - 120, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    cv2.imshow('ORB Detection', frame)
            else:
                # No targets loaded, show raw frame
                cv2.putText(frame, f"FPS: {int(fps)}", (frame.shape[1] - 120, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                cv2.putText(frame, "No targets loaded", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                cv2.imshow('ORB Detection', frame)

            # Check for quit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\n[*] Quit requested")
                break

    except KeyboardInterrupt:
        print("\n[*] Interrupted by user")
    except Exception as e:
        print(f"\n[x] Error: {e}")
        return 1
    finally:
        print("[*] Cleaning up...")
        if camera is not None:
            camera.stop()
        cv2.destroyAllWindows()
        print("[V] ORB Detection stopped")

    return 0


def cmd_server_wifi(args):
    """Run WiFi/HTTP image receiver server."""
    from finalCode.config import WIFI_SERVER_HOST, WIFI_SERVER_PORT
    from finalCode.server.wifi_server import app

    print_banner()
    print("[*] Starting WiFi/HTTP Image Receiver Server...")
    print("-" * 50)
    print(f"    Host: {WIFI_SERVER_HOST}")
    print(f"    Port: {WIFI_SERVER_PORT}")
    print(f"    Endpoint: POST /upload_target")
    print("-" * 50)

    try:
        app.run(host=WIFI_SERVER_HOST, port=WIFI_SERVER_PORT)
    except KeyboardInterrupt:
        print("\n[*] Server stopped by user")
    except Exception as e:
        print(f"[x] Server error: {e}")
        return 1

    return 0


def cmd_server_bt(args):
    """Run Bluetooth SPP image receiver."""
    from finalCode.config import BLUETOOTH_PORT, BLUETOOTH_BAUDRATE, RECEIVED_IMAGES_DIR
    from finalCode.server.bluetooth_server import BluetoothImageReceiver

    print_banner()
    print("[*] Starting Bluetooth Image Receiver...")
    print("-" * 50)

    try:
        receiver = BluetoothImageReceiver(
            port=BLUETOOTH_PORT,
            baudrate=BLUETOOTH_BAUDRATE,
            save_folder=RECEIVED_IMAGES_DIR
        )
        receiver.run()
    except KeyboardInterrupt:
        print("\n[*] Receiver stopped by user")
    except Exception as e:
        print(f"[x] Bluetooth error: {e}")
        return 1

    return 0


def cmd_lora_send(args):
    """Run LoRa basic sender."""
    if getattr(args, 'send_mode', 'basic') == 'sikap':
        from finalCode.lora.sender_sensor import LoRaSensorSender

        print_banner()
        print("[*] Starting LoRa SIKAP Sender...")
        print(f"    Interval: {args.interval}s")
        print("    Payload: timestamp, pitch, roll, yaw, pressure, altitude")
        print("-" * 50)

        sender = None
        try:
            sender = LoRaSensorSender(sensors='sikap')
            sender.run(interval=args.interval)
        except KeyboardInterrupt:
            print("\n[*] Stopped by user")
        except ImportError as e:
            print(f"[x] Import error: {e}")
            return 1
        except Exception as e:
            print(f"[x] Error: {e}")
            return 1
        finally:
            print("[*] Cleaning up...")
            if sender is not None:
                sender.cleanup()
            print("[V] LoRa SIKAP Sender stopped")

        return 0

    import RPi.GPIO as GPIO
    from SX127x.LoRa import MODE
    from SX127x.board_config import BOARD
    from finalCode.lora.sender import LoRaSender

    print_banner()
    print("[*] Starting LoRa Sender...")
    print("-" * 50)

    try:
        # Setup GPIO
        GPIO.setwarnings(False)
        GPIO.cleanup()
        GPIO.setmode(GPIO.BCM)
        BOARD.setup()

        # Initialize and configure LoRa
        lora = LoRaSender(verbose=False)
        lora.configure()

        counter = 1
        print("[V] LoRa Sender ready!")
        print("-" * 50)

        while True:
            message = f"counter:{counter} | {time.strftime('%H:%M:%S')}"
            print(f"Sending: {message}")
            
            success = lora.kirim(message)
            
            if success:
                print("Status: Sent!")
            else:
                print("Status: Failed (timeout)")
            
            print("-" * 40)
            counter += 1
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n[*] Stopped by user")
    except Exception as e:
        print(f"[x] LoRa error: {e}")
        return 1
    finally:
        print("[*] Cleaning up GPIO...")
        try:
            lora.set_mode(MODE.SLEEP)
            BOARD.teardown()
        except:
            pass
        print("[V] LoRa Sender stopped")

    return 0


def cmd_lora_sensor(args):
    """Run LoRa sender with sensor data."""
    from finalCode.lora.sender import setup_gpio, teardown_gpio
    from finalCode.lora.sender_sensor import LoRaSensorSender

    print_banner()
    print("[*] Starting LoRa Sensor Sender...")
    print(f"    Sensors: {args.sensor}")
    print(f"    Interval: {args.interval}s")
    print("-" * 50)

    sender = None
    try:
        # Setup GPIO
        setup_gpio()

        # Initialize LoRa sensor sender
        sender = LoRaSensorSender(sensors=args.sensor)

        # Run main loop
        sender.run(interval=args.interval)

    except KeyboardInterrupt:
        print("\n[*] Stopped by user")
    except ImportError as e:
        print(f"[x] Import error: {e}")
        return 1
    except Exception as e:
        print(f"[x] Error: {e}")
        return 1
    finally:
        print("[*] Cleaning up...")
        if sender is not None:
            sender.cleanup()
        print("[V] LoRa Sensor Sender stopped")

    return 0


def cmd_lora_ping(args):
    """Run LoRa ping-pong test."""
    import RPi.GPIO as GPIO
    from SX127x.LoRa import MODE
    from SX127x.board_config import BOARD
    from finalCode.lora.ping_pong import LoRaPingPong

    print_banner()
    print("[*] Starting LoRa Ping-Pong Test...")
    print("-" * 50)

    try:
        # Setup GPIO
        GPIO.setwarnings(False)
        GPIO.cleanup()
        BOARD.setup()

        # Initialize LoRa ping-pong
        lora = LoRaPingPong(verbose=False)
        lora.configure()

        print("[V] LoRa Ping-Pong ready!")
        print("-" * 50)

        lora.start()

    except KeyboardInterrupt:
        print("\n[*] Stopped by user")
    except Exception as e:
        print(f"[x] LoRa error: {e}")
        return 1
    finally:
        print("[*] Cleaning up GPIO...")
        try:
            lora.set_mode(MODE.SLEEP)
            BOARD.teardown()
        except:
            pass
        print("[V] LoRa Ping-Pong stopped")

    return 0


def cmd_health(args):
    """Run system health check on all sensors."""
    from finalCode.sensor.health_check import HealthChecker

    print_banner()
    
    try:
        checker = HealthChecker()
        all_healthy = checker.run_all_checks()
        
        return 0 if all_healthy else 1

    except KeyboardInterrupt:
        print("\n[*] Health check interrupted")
        return 1
    except Exception as e:
        print(f"[x] Health check error: {e}")
        return 1


# ─── Argument Parser ──────────────────────────────────────────────────────────

def create_parser():
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog='finalCode',
        description='Unified entry point for the finalCode package',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m finalCode.main detect         # ORB detection with camera
  python -m finalCode.main server wifi    # Start WiFi server
  python -m finalCode.main server bt      # Start Bluetooth server
  python -m finalCode.main lora send      # LoRa basic sender
    python -m finalCode.main lora send sikap # LoRa sikap payload sender
  python -m finalCode.main lora sensor    # LoRa + sensor sender
    python -m finalCode.main lora sensor --sensor gpsm6n # LoRa + GPSM6N sender
  python -m finalCode.main lora ping      # LoRa ping-pong test
  python -m finalCode.main health         # Run health check
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # detect command
    parser_detect = subparsers.add_parser('detect', help='Run ORB feature detection with camera')
    parser_detect.set_defaults(func=cmd_detect)

    # server command with subcommands
    parser_server = subparsers.add_parser('server', help='Server operations')
    server_subparsers = parser_server.add_subparsers(dest='server_type', help='Server type')

    parser_server_wifi = server_subparsers.add_parser('wifi', help='Start WiFi/HTTP image server')
    parser_server_wifi.set_defaults(func=cmd_server_wifi)

    parser_server_bt = server_subparsers.add_parser('bt', help='Start Bluetooth image receiver')
    parser_server_bt.set_defaults(func=cmd_server_bt)

    # lora command with subcommands
    parser_lora = subparsers.add_parser('lora', help='LoRa communication')
    lora_subparsers = parser_lora.add_subparsers(dest='lora_type', help='LoRa mode')

    parser_lora_send = lora_subparsers.add_parser('send', help='LoRa basic sender or sikap payload sender')
    parser_lora_send.add_argument('send_mode', nargs='?', choices=['basic', 'sikap'], default='basic',
                                  help='Send mode (default: basic)')
    parser_lora_send.add_argument('--interval', type=float, default=0.5,
                                  help='Seconds between transmissions (default: 0.5)')
    parser_lora_send.set_defaults(func=cmd_lora_send)

    parser_lora_sensor = lora_subparsers.add_parser('sensor', help='LoRa + sensor data sender')
    parser_lora_sensor.add_argument('--sensor', choices=['bmp280', 'mpu6050', 'gy511', 'gpsm6n', 'all'],
                                    default='all', help='Which sensor(s) to use (default: all)')
    parser_lora_sensor.add_argument('--interval', type=float, default=0.2,
                                    help='Seconds between transmissions (default: 1)')
    parser_lora_sensor.set_defaults(func=cmd_lora_sensor)

    parser_lora_ping = lora_subparsers.add_parser('ping', help='LoRa ping-pong test')
    parser_lora_ping.set_defaults(func=cmd_lora_ping)

    # health command
    parser_health = subparsers.add_parser('health', help='Run health check on all sensors')
    parser_health.set_defaults(func=cmd_health)

    return parser


# ─── Main Entry Point ─────────────────────────────────────────────────────────

def main():
    """Main entry point for the finalCode package."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    # Handle server subcommand
    if args.command == 'server' and not hasattr(args, 'func'):
        print("[x] Please specify server type: wifi or bt")
        print("    Example: python -m finalCode.main server wifi")
        return 1

    # Handle lora subcommand
    if args.command == 'lora' and not hasattr(args, 'func'):
        print("[x] Please specify LoRa mode: send, sensor, or ping")
        print("    Example: python -m finalCode.main lora send")
        return 1

    # Execute the command
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
