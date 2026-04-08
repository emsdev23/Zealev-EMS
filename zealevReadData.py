import mysql.connector
import socket
import logging
import time
from datetime import datetime
import json
from typing import Optional, Tuple, Dict, Any

# Configuration could be moved to a separate config file
CONFIG = {
    "device": {
        "ip": "10.3.3.70",
        "port": 20001
    },
    "database": {
        "host": "121.242.232.211",
        "user": "emsroot",
        "password": "22@teneT",
        "database": "zealev",
        "port": 3306
    },
    "logging": {
        "file": "afe100kW.log",
        "level": logging.DEBUG
    },
    "retry": {
        "count": 5,
        "delay": 0.2
    },
    "loop": {
        "sleep": 15
    }
}

# Command definitions
COMMANDS = {
    "VABvoltage": "8802A500F83001000000000000",
    "VBCvoltage": "8802A500F83002000000000000",
    "VCAvoltage": "8802A500F83003000000000000",
    "DCvoltage": "8802A500F83004000000000000",
    "DCpower": "8802A500F83012000000000000",
    "APpower": "8802A500F8300F000000000000",
    "ACTpower": "8802A500F83010000000000000",
    "RACTpower": "8802A500F83011000000000000",
    "DCcurrent": "8802A500F83008000000000000",
    "LAcurrent": "8802A500F83005000000000000",
    "LBcurrent": "8802A500F83006000000000000",
    "LCcurrent": "8802A500F83007000000000000",
    "Temperature": "8802A500F83009000000000000"
}

# Set up logging
logging.basicConfig(
    filename=CONFIG["logging"]["file"],
    level=CONFIG["logging"]["level"],
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manages database connections and operations."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connection = None
        self.cursor = None
    
    def connect(self) -> bool:
        """Establish a database connection."""
        try:
            self.connection = mysql.connector.connect(**self.config)
            self.cursor = self.connection.cursor()
            logger.info("Database connection established")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close the database connection."""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
    
    def insert_data(self, data: Dict[str, Any]) -> bool:
        """Insert data into the database."""
        if not self.connection or not self.cursor:
            if not self.connect():
                return False
        
        sql = """
            INSERT INTO afeconvertor100kw (
                ateconvertordcvoltage,
                afeconvertordccurrent,
                afeconvertorvabvoltage,
                afeconvertorvcavoltage,
                afeconvertorvbcvoltage,
                afeconvertoriacurrent,
                afeconvertoribcurrent,
                afeconvertoriccurrent,
                afeconvertorapparentpower,
                afeconvertoractivepower,
                afeconvertorreactivepower,
                afeconvertormod1temperature,
                afeconvertormod2temperature,
                afeconvertormod3temperature,
                afeconvertorambienttemperature
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        values = (
            data['DCvoltage'],
            data['DCcurrent'],
            data['VABvoltage'],
            data['VBCvoltage'],
            data['VCAvoltage'],
            data['readLAcurrent'],
            data['readLBcurrent'],
            data['readLCcurrent'],
            data['APpower'],
            data['ACTpower'],
            data['RACTpower'],
            data['mod1T'],
            data['mod2T'],
            data['mod3T'],
            data['ambT']
        )
        
        try:
            self.cursor.execute(sql, values)
            self.connection.commit()
            logger.info("Data inserted successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to insert data: {e}")
            self.connection.rollback()
            return False


class DeviceConnection:
    """Manages TCP connection to the device and data reading."""
    
    def __init__(self, ip: str, port: int):
        self.ip = ip
        self.port = port
        self.socket = None
        self.connected = False
    
    def connect(self) -> bool:
        """Establish TCP connection to the device."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.ip, self.port))
            self.connected = True
            logger.info(f"Connected to device at {self.ip}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to device: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Close the TCP connection."""
        if self.socket:
            self.socket.close()
            self.connected = False
            logger.info("Device connection closed")
    
    def send_command(self, command: str) -> Optional[str]:
        """Send a command to the device and return the response."""
        if not self.connected:
            if not self.connect():
                return None
        
        try:
            hex_data = bytes.fromhex(command)
            current_time = datetime.now()
            
            self.socket.send(hex_data)
            logger.info(f"{current_time} | Sent command: {hex_data}")
            
            response = self.socket.recv(10240)
            hex_string = ''.join(f"{byte:02X}" for byte in response)
            logger.info(f"{current_time} | Received response: {hex_string}")
            
            # Verify the response matches the command
            if hex_string[10:14] != command[10:14]:
                logger.warning(f"Response verification failed for command: {command}")
                return None
            
            return hex_string
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            self.connected = False
            return None
    
    def read_value(self, command: str) -> Optional[int]:
        """Read a simple value from the device."""
        response = self.send_command(command)
        if response:
            try:
                return int(response[18:26], 16)
            except ValueError as e:
                logger.error(f"Error parsing value: {e}")
        return None
    
    def read_active_power(self, command: str) -> Optional[int]:
        """Read active power value from the device."""
        response = self.send_command(command)
        if response:
            try:
                if response[18] == "8":
                    return -abs(int(response[19:26], 16))
                else:
                    return int(response[18:26], 16)
            except ValueError as e:
                logger.error(f"Error parsing active power: {e}")
        return None
    
    def read_current(self, command: str) -> Optional[int]:
        """Read current value from the device."""
        response = self.send_command(command)
        if response:
            try:
                if response[18:20] == "80":
                    return -abs(int(response[20:26], 16))
                else:
                    return int(response[20:26], 16)
            except ValueError as e:
                logger.error(f"Error parsing current: {e}")
        return None
    
    def read_temperature(self, command: str) -> Optional[Tuple[int, int, int, int]]:
        """Read temperature values from the device."""
        response = self.send_command(command)
        if response:
            try:
                mod1 = int(response[18:20], 16)
                mod2 = int(response[20:22], 16)
                mod3 = int(response[22:24], 16)
                amb = int(response[24:26], 16)
                return mod1, mod2, mod3, amb
            except ValueError as e:
                logger.error(f"Error parsing temperature: {e}")
        return None


def retry_operation(func, *args, retries=CONFIG["retry"]["count"], delay=CONFIG["retry"]["delay"]):
    """Retry a function call with specified retries and delay."""
    for attempt in range(retries):
        try:
            result = func(*args)
            if result is not None:
                return result
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
        
        if attempt < retries - 1:
            time.sleep(delay)
    
    logger.warning(f"Operation failed after {retries} attempts")
    return None


def collect_device_data(device: DeviceConnection) -> Dict[str, Any]:
    """Collect all required data from the device."""
    data = {
        "DCvoltage": retry_operation(device.read_value, COMMANDS["DCvoltage"]),
        "VABvoltage": retry_operation(device.read_value, COMMANDS["VABvoltage"]),
        "VBCvoltage": retry_operation(device.read_value, COMMANDS["VBCvoltage"]),
        "VCAvoltage": retry_operation(device.read_value, COMMANDS["VCAvoltage"]),
        "DCpower": retry_operation(device.read_value, COMMANDS["DCpower"]),
        "APpower": retry_operation(device.read_value, COMMANDS["APpower"]),
        "RACTpower": retry_operation(device.read_value, COMMANDS["RACTpower"]),
        "ACTpower": retry_operation(device.read_active_power, COMMANDS["ACTpower"]),
        "DCcurrent": retry_operation(device.read_current, COMMANDS["DCcurrent"]),
        "readLAcurrent": retry_operation(device.read_current, COMMANDS["LAcurrent"]),
        "readLBcurrent": retry_operation(device.read_current, COMMANDS["LBcurrent"]),
        "readLCcurrent": retry_operation(device.read_current, COMMANDS["LCcurrent"]),
    }
    
    temps = retry_operation(device.read_temperature, COMMANDS["Temperature"])
    if temps:
        data["mod1T"], data["mod2T"], data["mod3T"], data["ambT"] = temps
    else:
        data["mod1T"] = data["mod2T"] = data["mod3T"] = data["ambT"] = None
    
    return data


def main():
    """Main function to run the data collection loop."""
    # Initialize connections
    device = DeviceConnection(CONFIG["device"]["ip"], CONFIG["device"]["port"])
    db = DatabaseConnection(CONFIG["database"])
    
    # Connect to the device
    if not device.connect():
        logger.error("Failed to connect to device. Exiting.")
        return
    
    logger.info("Starting data collection loop")
    
    try:
        while True:
            # Collect data from device
            data = collect_device_data(device)
            logger.debug(f"Collected data: {json.dumps(data)}")
            
            # Skip insert if any data is missing
            if any(v is None for v in data.values()):
                logger.warning("Skipping insert; some values failed even after retries.")
                time.sleep(CONFIG["loop"]["sleep"])
                continue
            
            # Insert data into database
            if not db.insert_data(data):
                logger.error("Failed to insert data into database")
            
            # Wait before next iteration
            time.sleep(CONFIG["loop"]["sleep"])
    
    except KeyboardInterrupt:
        logger.info("Data collection stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
    finally:
        # Clean up connections
        device.disconnect()
        db.disconnect()
        logger.info("Data collection stopped")


if __name__ == "__main__":
    main()