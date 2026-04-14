"""LoRa module - LoRa radio communication utilities.

This module provides LoRa radio communication utilities including:
- LoRaSender: Basic LoRa message sender
- LoRaSensorSender: Generic multi-sensor LoRa sender (BMP280, MPU6050)
- PingPong: LoRa ping-pong transceiver for testing
"""

# Core LoRa sender
from finalCode.lora.sender import LoRaSender, setup_gpio, teardown_gpio

# Multi-sensor LoRa sender (lazy import for optional sensor dependencies)
def get_sensor_sender():
    """
    Get the LoRaSensorSender class.
    
    Returns:
        LoRaSensorSender class
        
    Raises:
        ImportError: If sensor dependencies are missing
    """
    from finalCode.lora.sender_sensor import LoRaSensorSender
    return LoRaSensorSender


__all__ = [
    'LoRaSender',
    'setup_gpio',
    'teardown_gpio',
    'get_sensor_sender',
]
