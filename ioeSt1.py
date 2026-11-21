"""
IOE Battery — All Strings monitor.

Reads Modbus-TCP style packets for N battery strings from a single BMS
device, over a SINGLE shared TCP connection, and inserts one record per
string into MySQL every INSERT_INTERVAL_SEC seconds.

Why one shared connection instead of one process per string:
The device appears to only tolerate a single client connection at a time.
Running five separate processes (ioeBatteryString1..5.py), each opening
its own socket to the same IP:port, causes the device to accept a new
connection and then immediately close it — because it's already committed
to a different client. That shows up as "Socket closed by peer" storms.
Consolidating into one process with one connection removes that
contention entirely.

Each string is identified by the last hex digit of the packet's 4th byte:
    88 18 03 1N  -> function code 03 (telemetry) for string N
    88 18 13 1N  -> function code 13 (energy)     for string N
and has its own reset command:
    85 18 (0x20+N) (0x10+N) 0C 00 00 01 FF FF FF 00 00

Architecture:
  - BmsSocket    : thread-safe TCP socket with automatic reconnect/backoff.
  - BatteryParser: pure parsing logic, no I/O side effects except sending
                    the safety "reset" command for whichever string
                    triggered it.
  - LatestReadings: shared, lock-protected holder of {string_no: record}.
  - reader_loop() runs in a background thread: recv -> identify string ->
                    parse -> update LatestReadings. Never blocks inserts.
  - main()        runs a drift-corrected 15s loop that inserts whatever is
                    currently held for EACH string, using a single
                    persistent DB connection with reconnect-on-failure.
"""

import os
import time
import socket
import logging
import threading
from datetime import datetime

import mysql.connector

# --------------------------------------------------------------------------
# Configuration (env-overridable; avoid hardcoding secrets in source control)
# --------------------------------------------------------------------------
SERVER_IP = os.getenv("BMS_SERVER_IP", "")
SERVER_PORT = int(os.getenv("BMS_SERVER_PORT", ""))

DB_CONFIG = {
    "host": os.getenv("EMS_DB_HOST", ""),
    "user": os.getenv("EMS_DB_USER", ""),
    "password": os.getenv("EMS_DB_PASSWORD",""),
    "database": os.getenv("EMS_DB_NAME", ""),
    "port": int(os.getenv("EMS_DB_PORT", "")),
}

INSERT_INTERVAL_SEC = 15
NUM_STRINGS = int(os.getenv("BMS_NUM_STRINGS", "5"))

LOG_DIR = "/home/tenet/ems/logs/ioeBattery"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "ioeBatteryAllStrings.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("ioeBatteryAllStrings")


def build_string_configs(num_strings: int) -> dict:
    """Builds per-string prefix/reset-command config from the observed
    pattern: byte4 = 0x10+N in packet prefixes, and in the reset command
    byte3 = 0x20+N, byte4 = 0x10+N."""
    configs = {}
    for n in range(1, num_strings + 1):
        configs[n] = {
            "no": n,
            "prefix_03": f"88 18 03 1{n}",
            "prefix_13": f"88 18 13 1{n}",
            "reset_command": bytes.fromhex(
                f"8518{0x20 + n:02X}{0x10 + n:02X}0C000001FFFFFF0000"
            ),
        }
    return configs


STRINGS = build_string_configs(NUM_STRINGS)


# --------------------------------------------------------------------------
# Socket layer (single shared connection for all strings)
# --------------------------------------------------------------------------
class BmsSocket:
    """Thread-safe TCP connection to the BMS with auto-reconnect/backoff."""

    FAST_FAILURE_THRESHOLD_SEC = 5.0

    def __init__(self, host: str, port: int, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock = None
        self._lock = threading.Lock()
        self._last_connect_time = 0.0
        self._consecutive_fast_failures = 0
        self._connect()
        self._last_connect_time = time.monotonic()

    def _connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((self.host, self.port))
        self._sock = sock
        logger.info(f"Connected to BMS at {self.host}:{self.port}")

    def _backoff_delay(self) -> float:
        if self._consecutive_fast_failures == 0:
            return 0.0
        return min(2 * (2 ** (self._consecutive_fast_failures - 1)), 30)

    def _reconnect(self):
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass

        alive_for = time.monotonic() - self._last_connect_time
        if alive_for < self.FAST_FAILURE_THRESHOLD_SEC:
            self._consecutive_fast_failures += 1
        else:
            self._consecutive_fast_failures = 0

        delay = self._backoff_delay()
        if delay:
            logger.warning(
                f"BMS connection lasted only {alive_for:.2f}s "
                f"({self._consecutive_fast_failures} consecutive fast failures); "
                f"backing off {delay}s before reconnecting"
            )
            time.sleep(delay)

        while True:
            try:
                self._connect()
                self._last_connect_time = time.monotonic()
                return
            except Exception as ex:
                self._consecutive_fast_failures += 1
                delay = self._backoff_delay()
                logger.error(f"BMS reconnect failed: {ex}; retrying in {delay}s")
                time.sleep(delay)

    def recv(self, bufsize: int = 10240) -> bytes:
        with self._lock:
            try:
                data = self._sock.recv(bufsize)
                if not data:
                    raise ConnectionError("Socket closed by peer")
                return data
            except Exception as ex:
                logger.error(f"recv error: {ex}; reconnecting")
                self._reconnect()
                return b""

    def send(self, data: bytes):
        with self._lock:
            try:
                self._sock.sendall(data)
            except Exception as ex:
                logger.error(f"send error: {ex}; reconnecting")
                self._reconnect()

    def close(self):
        try:
            self._sock.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Parsing (string-agnostic; string identity + reset command passed in)
# --------------------------------------------------------------------------
class BatteryParser:
    """Parses a pair of raw packets (function codes 03 and 13) into a dict
    for one specific battery string."""

    @staticmethod
    def round_to_15s(rectime: str) -> str:
        try:
            sec = int(rectime[17:])
            bucket = (sec // 15) * 15
            return f"{rectime[0:17]}{bucket:02d}"
        except Exception as ex:
            logger.error(f"rectime rounding error: {ex}")
            return rectime

    @staticmethod
    def parse(packets, rectime: str, bms_socket: "BmsSocket", string_no: int, reset_command: bytes):
        """
        packets: list of two token lists (space-split hex bytes) - one for
        function code '03', one for '13' - both belonging to `string_no`.
        Returns a battery status dict, or None if parsing failed / a BMS
        reset was triggered instead.
        """
        clean_03, clean_13 = [], []
        for pkt in packets:
            if len(pkt) > 2 and pkt[2] == "03":
                clean_03 = pkt[5:]
            elif len(pkt) > 2 and pkt[2] == "13":
                clean_13 = pkt[5:]

        if not clean_03:
            logger.warning(f"[String {string_no}] No fc-03 packet in pair; skipping")
            return None

        def hexpair(hi_idx, lo_idx, divisor=1):
            try:
                val = int(clean_03[hi_idx] + clean_03[lo_idx], 16)
                return val / divisor if divisor != 1 else val
            except Exception as ex:
                logger.error(f"[String {string_no}] hexpair({hi_idx},{lo_idx}) error: {ex}")
                return None

        battery_volt = hexpair(1, 0, 10)
        battery_current = hexpair(3, 2, 100)

        try:
            main_cons_sts = clean_03[4][1]
            pre_con_sts = clean_03[4][0]
        except Exception as ex:
            main_cons_sts = pre_con_sts = None
            logger.error(f"[String {string_no}] Contactor status parse error: {ex}")

        try:
            raw_sts = clean_03[5][1]
            status_map = {"2": "IDLE", "5": "FAULT"}
            if raw_sts in status_map:
                battery_sts = status_map[raw_sts]
            elif raw_sts == "3":
                battery_sts = "CHG" if (battery_current or 0) > 3 else "IDLE"
            elif raw_sts == "4":
                battery_sts = "DCHG" if (battery_current or 0) > 3 else "IDLE"
            else:
                battery_sts = None
        except Exception as ex:
            battery_sts = None
            logger.error(f"[String {string_no}] batterySts parse error: {ex}")

        # Safety interlock: main contactor open while current is still
        # flowing -> force a BMS reset for THIS string instead of
        # recording a reading.
        if main_cons_sts == "2" and (
            battery_sts in ("CHG", "DCHG") or (battery_current or 0) >= 4
        ):
            logger.warning(
                f"[String {string_no}] Reset condition met. preConSts={pre_con_sts}, "
                f"mainConsSts={main_cons_sts}, status={battery_sts}, "
                f"current={battery_current}"
            )
            bms_socket.send(reset_command)
            logger.info(f"[String {string_no}] BMS reset command sent.")
            return None

        try:
            pack_soc = int(clean_03[6], 16)
        except Exception as ex:
            pack_soc = None
            logger.error(f"[String {string_no}] packSoc error: {ex}")

        try:
            usable_soc = int(clean_03[7], 16)
        except Exception as ex:
            usable_soc = None
            logger.error(f"[String {string_no}] usableSoc error: {ex}")

        def energy(hi_idx, lo_idx):
            if not clean_13:
                return None
            try:
                return int(clean_13[hi_idx] + clean_13[lo_idx], 16)
            except Exception as ex:
                logger.error(f"[String {string_no}] energy({hi_idx},{lo_idx}) error: {ex}")
                return None

        result = {
            "stringNo": string_no,
            "batteryVolt": battery_volt,
            "batteryCurent": battery_current,
            "mainConsSts": main_cons_sts,
            "preConSts": pre_con_sts,
            "batterySts": battery_sts,
            "packSoc": pack_soc,
            "usableSoc": usable_soc,
            "chargingEnergy": energy(1, 0),
            "dischargingEnergy": energy(3, 2),
            "availableEnergy": energy(5, 4),
            "rectime": BatteryParser.round_to_15s(rectime),
        }
        logger.info(f"[String {string_no}] Parsed battery data: {result}")
        return result


# --------------------------------------------------------------------------
# Shared "latest reading per string" slot between reader thread and main
# --------------------------------------------------------------------------
class LatestReadings:
    def __init__(self, string_numbers):
        self._lock = threading.Lock()
        self._data = {n: None for n in string_numbers}

    def set(self, string_no: int, data: dict):
        with self._lock:
            self._data[string_no] = data

    def get_and_clear_all(self) -> dict:
        with self._lock:
            snapshot = self._data
            self._data = {n: None for n in snapshot}
            return snapshot


def identify_packet(hex_string: str):
    """Returns (string_no, function_code) for a recognized packet prefix,
    or (None, None) if it doesn't match any configured string."""
    for n, cfg in STRINGS.items():
        if hex_string.startswith(cfg["prefix_03"]):
            return n, "03"
        if hex_string.startswith(cfg["prefix_13"]):
            return n, "13"
    return None, None


def reader_loop(bms_socket: BmsSocket, latest: LatestReadings, stop_event: threading.Event):
    """Continuously reads packets for ALL strings on the shared connection
    and keeps `latest` up to date per string. Runs independently of the
    insert cadence."""
    # Each string accumulates its own pending fc-03 / fc-13 pair.
    pending = {n: [] for n in STRINGS}

    while not stop_event.is_set():
        raw = bms_socket.recv()
        if not raw:
            continue

        hex_string = " ".join(f"{b:02X}" for b in raw)
        logger.debug(f"Received hex string: {hex_string}")

        string_no, fc = identify_packet(hex_string)
        if string_no is None:
            logger.debug("Unrecognized packet prefix; ignoring")
            continue

        buf = pending[string_no]
        prefix = STRINGS[string_no]["prefix_03"] if fc == "03" else STRINGS[string_no]["prefix_13"]
        if not any(p.startswith(prefix) for p in buf):
            buf.append(hex_string)

        if len(buf) == 2:
            packets = [p.split() for p in buf]
            rectime = str(datetime.now())[:-7]
            parsed = BatteryParser.parse(
                packets, rectime, bms_socket, string_no, STRINGS[string_no]["reset_command"]
            )
            buf.clear()
            if parsed:
                latest.set(string_no, parsed)


# --------------------------------------------------------------------------
# Database layer
# --------------------------------------------------------------------------
class Database:
    INSERT_SQL = """INSERT INTO ioeBatteryData
        (strings, batteryVoltage, batteryCurrent, mainContactorStatus,
         prechargeContactorStatus, batteryStatus, packSOC, packUsableSOC,
         chargingEnergy, dischargingEnergy, availableEnergy, recordTimestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    def __init__(self, config: dict):
        self.config = config
        self.conn = None
        self._connect()

    def _connect(self):
        self.conn = mysql.connector.connect(**self.config)
        logger.info("Connected to EMS database")

    def insert(self, d: dict):
        values = (
            d["stringNo"], d["batteryVolt"], d["batteryCurent"], d["mainConsSts"],
            d["preConSts"], d["batterySts"], d["packSoc"], d["usableSoc"],
            d["chargingEnergy"], d["dischargingEnergy"], d["availableEnergy"],
            d["rectime"],
        )
        try:
            if not self.conn.is_connected():
                self._connect()
            cur = self.conn.cursor()
            cur.execute(self.INSERT_SQL, values)
            self.conn.commit()
            cur.close()
            logger.info(f"[String {d['stringNo']}] inserted into database")
        except mysql.connector.Error as ex:
            logger.error(f"[String {d['stringNo']}] Database insert error: {ex}; reconnecting")
            try:
                self.conn.close()
            except Exception:
                pass
            try:
                self._connect()
            except Exception as ex2:
                logger.error(f"Database reconnect failed: {ex2}")

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# Main: drift-corrected 15-second insert cadence, one insert per string
# --------------------------------------------------------------------------
def main():
    bms_socket = BmsSocket(SERVER_IP, SERVER_PORT)
    db = Database(DB_CONFIG)
    latest = LatestReadings(STRINGS.keys())
    stop_event = threading.Event()

    reader_thread = threading.Thread(
        target=reader_loop, args=(bms_socket, latest, stop_event), daemon=True
    )
    reader_thread.start()

    logger.info(
        f"Starting insert loop every {INSERT_INTERVAL_SEC}s for strings {sorted(STRINGS)}"
    )
    next_tick = time.monotonic()

    try:
        while True:
            next_tick += INSERT_INTERVAL_SEC

            snapshot = latest.get_and_clear_all()
            for string_no in sorted(snapshot):
                data = snapshot[string_no]
                if data:
                    db.insert(data)
                else:
                    logger.warning(
                        f"[String {string_no}] No new battery data this interval; skipping insert"
                    )

            sleep_time = next_tick - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                logger.warning(f"Insert loop running {-sleep_time:.2f}s behind; resyncing")
                next_tick = time.monotonic()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        stop_event.set()
        db.close()
        bms_socket.close()


if __name__ == "__main__":
    main()
