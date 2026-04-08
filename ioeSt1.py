import socket
import time
from datetime import datetime
import mysql.connector
import logging
import os

log_dir = "/home/tenet/ems/logs/ioeBattery"
os.makedirs(log_dir, exist_ok=True)  # Create directory if it doesn't exist

log_file = os.path.join(log_dir, "ioeBatteryString1.log")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

server_ip = "10.9.244.8"
server_port = 502

class ConnectionPool:
    def __init__(self, server_ip, server_port, pool_size):
        self.server_ip = server_ip
        self.server_port = server_port
        self.pool_size = pool_size
        self.connections = []

        for _ in range(pool_size):
            self.connections.append(self._create_connection())

    def _create_connection(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.server_ip, self.server_port))
        logging.info(f"Created new socket connection to {self.server_ip}:{self.server_port}")
        return client_socket

    def get_connection(self):
        if not self.connections:
            return self._create_connection()
        else:
            return self.connections.pop()

    def release_connection(self, connection):
        self.connections.append(connection)

    def close_all_connections(self):
        for connection in self.connections:
            connection.close()

li = []

if __name__ == "__main__":
    pool_size = 1
    connection_pool = ConnectionPool(server_ip, server_port, pool_size)

    while True:
        batteryStsDict = {}
        batteryli = []
        chgstsli = []

        try:
            unprocesseddb = mysql.connector.connect(
                host="121.242.232.211",
                user="emsroot",
                password="22@teneT",
                database='EMS',
                port=3306
            )
            ltocur = unprocesseddb.cursor()
        except Exception as ex:
            logging.error(f"Database connection failed: {ex}")
            time.sleep(10)
            continue

        def ltoBattery(li, rectime):
            logging.debug(f"Raw packet list: {li}")
            print(li)
            clean_li = []
            clean_li1 = []
            for item in li:
                if item[2] == '03':
                    clean_li = item[5:]
                elif item[2] == '13':
                    clean_li1 = item[5:]

            try:
                batteryVolt = clean_li[1] + clean_li[0]
                batteryVolt = int(batteryVolt, 16) / 10
            except Exception as ex:
                batteryVolt = None
                logging.error(f"batteryVolt error: {ex}")

            try:
                batteryCurent = clean_li[3] + clean_li[2]
                batteryCurent = int(batteryCurent, 16) / 100
            except Exception as ex:
                batteryCurent = None
                logging.error(f"batteryCurent error: {ex}")

            try:
                mainConsSts = clean_li[4][1]
                preConSts = clean_li[4][0]
            except Exception as ex:
                mainConsSts = None
                preConSts = None
                logging.error(f"Contactor status parse error: {ex}")

            try:
                batterySts = clean_li[5][1]
                if batterySts == '2':
                    batterySts = 'IDLE'
                elif batterySts == '3':
                    batterySts = 'CHG' if batteryCurent > 3 else 'IDLE'
                elif batterySts == '4':
                    batterySts = 'DCHG' if batteryCurent > 3 else 'IDLE'
                elif batterySts == '5':
                    batterySts = 'FAULT'
            except Exception as ex:
                batterySts = None
                logging.error(f"batterySts parse error: {ex}")

            try:
                packSoc = int(clean_li[6], 16)
            except Exception as ex:
                packSoc = None
                logging.error(f"packSoc error: {ex}")

            try:
                usableSoc = int(clean_li[7], 16)
            except Exception as ex:
                usableSoc = None
                logging.error(f"usableSoc error: {ex}")

            batteryStsDict.update({
                'batteryVolt': batteryVolt,
                'batteryCurent': batteryCurent,
                'mainConsSts': mainConsSts,
                'preConSts': preConSts,
                'batterySts': batterySts,
                'packSoc': packSoc,
                'usableSoc': usableSoc,
                'stringNo': 1
            })

            try:
                sec = int(rectime[17:])
                if sec < 15:
                    batteryStsDict['rectime'] = rectime[0:17] + "00"
                elif sec < 30:
                    batteryStsDict['rectime'] = rectime[0:17] + "15"
                elif sec < 45:
                    batteryStsDict['rectime'] = rectime[0:17] + "30"
                else:
                    batteryStsDict['rectime'] = rectime[0:17] + "45"
            except Exception as ex:
                batteryStsDict['rectime'] = rectime
                logging.error(f"rectime error: {ex}")

            try:
                chargingEnergy = int(clean_li1[1] + clean_li1[0], 16)
            except:
                chargingEnergy = None

            try:
                dischargingEnergy = int(clean_li1[3] + clean_li1[2], 16)
            except:
                dischargingEnergy = None

            try:
                availableEnergy = int(clean_li1[5] + clean_li1[4], 16)
            except:
                availableEnergy = None

            chgstsli.extend([chargingEnergy, dischargingEnergy, availableEnergy])

            batteryStsDict.update({
                'chargingEnergy': chargingEnergy,
                'dischargingEnergy': dischargingEnergy,
                'availableEnergy': availableEnergy
            })

            logging.info(f"Parsed battery data: {batteryStsDict}")

        def string1(hex_string):
            logging.info(f"Received hex string: {hex_string}")
            print(f"Received hex string: {hex_string}")
            if hex_string.startswith('88 18 13 11'):
                if not any(item.startswith('88 18 13 11') for item in li):
                    li.append(hex_string)
            elif hex_string.startswith('88 18 03 11'):
                if not any(item.startswith('88 18 03 11') for item in li):
                    li.append(hex_string)

            if len(li) == 2:
                list_of_lists = [item.split() for item in li]
                now = str(datetime.now())[:-7]
                ltoBattery(list_of_lists, now)
                li.clear()

        client_socket = connection_pool.get_connection()

        try:
            response = client_socket.recv(10240)
            hex_string = ' '.join(f"{byte:02X}" for byte in response)
            string1(hex_string)
        except Exception as ex:
            logging.error(f"Socket recv error: {ex}")
            print(f"Socket recv error: {ex}")
            time.sleep(10)
            continue
        finally:
            connection_pool.release_connection(client_socket)

        if batteryStsDict:
            try:
                logging.info(f"Final batteryStsDict: {batteryStsDict}")
                print(batteryStsDict)
                val = (
                    batteryStsDict['stringNo'], batteryStsDict['batteryVolt'], batteryStsDict['batteryCurent'],
                    batteryStsDict['mainConsSts'], batteryStsDict['preConSts'], batteryStsDict['batterySts'],
                    batteryStsDict['packSoc'], batteryStsDict['usableSoc'], batteryStsDict['chargingEnergy'],
                    batteryStsDict['dischargingEnergy'], batteryStsDict['availableEnergy'], batteryStsDict['rectime']
                )

                sql = """INSERT INTO ioeBatteryData(strings, batteryVoltage, batteryCurrent, mainContactorStatus,
                          prechargeContactorStatus, batteryStatus, packSOC, packUsableSOC, chargingEnergy,
                          dischargingEnergy, availableEnergy, recordTimestamp) 
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

                logging.debug(f"Inserting values: {val}")
                ltocur.execute(sql, val)
                unprocesseddb.commit()
                logging.info("Battery data String-1 inserted into database")
                print("Battery data String-1 inserted into database")
                ltocur.close()
                unprocesseddb.close()
                print("Sleep for 15 secs")
                logging.info("Sleep for 15 secs")
                time.sleep(15)

            except Exception as ex:
                logging.error(f"Database insert error: {ex}")
                ltocur.close()
                unprocesseddb.close()
                continue
