import serial
import serial.tools.list_ports
import time

class BetaBrite:
    # Control codes for BetaBrite protocol
    NULL = b'\x00'
    SOH = b'\x01'  # Start of Header
    STX = b'\x02'  # Start of Text
    EOT = b'\x04'  # End of Transmission
    ENQ = b'\x05'  # Enquiry
    ACK = b'\x06'  # Acknowledge
    BELL = b'\x07'
    CR = b'\x0D'   # Carriage Return
    ESC = b'\x1B'  # Escape

    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        """Initialize BetaBrite display connection"""
        self.serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        
    def write_message(self, message, mode="ROTATE"):
        """Write a message to the BetaBrite display
        
        Args:
            message (str): The message to display
            mode (str): Display mode (ROTATE, HOLD, FLASH, etc.)
        """
        # Convert message to bytes
        message_bytes = message.encode('ascii', 'ignore')
        
        # Construct command sequence
        command = (
            self.NULL * 5 +           # Padding
            self.SOH +                # Start of Header
            b'Z00' +                  # Sign address (Z00 = all signs)
            self.STX +                # Start of Text
            b'AA' +                   # Text File Label
            self.ESC +                # Escape
            mode.encode('ascii') +    # Display mode
            message_bytes +           # The actual message
            self.EOT                  # End of Transmission
        )
        
        # Send the command
        self.serial.write(command)
        time.sleep(0.1)  # Give the display time to process
        
    def close(self):
        """Close the serial connection"""
        if self.serial.is_open:
            self.serial.close()

def list_available_ports():
    """List all available serial ports"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found!")
        return
    
    print("\nAvailable serial ports:")
    for port in ports:
        print(f"- {port.device}")
        print(f"  Description: {port.description}")
        print(f"  Hardware ID: {port.hwid}\n")

def main():
    try:
        # List available ports first
        list_available_ports()
        
        # Create BetaBrite instance
        # Note: Change port if necessary (Windows might use 'COM1', etc.)
        display = BetaBrite(port='/dev/tty.usbserial-1')
        
        # Write a test message
        display.write_message("Hello World!")
        
        # Close the connection
        display.close()
        
    except serial.SerialException as e:
        print(f"Error: Could not connect to BetaBrite display: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
