import mysql.connector
import time
from collections import defaultdict

emsdb = mysql.connector.connect(
    host="121.242.232.211",
    user="emsroot",
    password="22@teneT",
    database="EMS",
    port=3306
)


def process_station(cursor, table, st_prefix):
    cursor.execute(f"""
        SELECT batteryStatus,
               chargingEnergy,
               dischargingEnergy,
               packUsableSOC,
               recordTimestamp
        FROM {table}
        WHERE date(recordTimestamp) >= '2025-10-31'
        AND date(recordTimestamp) <= '2025-11-03'
    """)

    results = cursor.fetchall()

    chgdict = defaultdict(float)
    dchgdict = defaultdict(float)

    chgmin = defaultdict(list)
    dchgmin = defaultdict(list)

    packdict = defaultdict(list)

    chglist = []
    dchglist = []

    # -------------------------
    # build minute level data
    # -------------------------
    for status, chg, dchg, soc, ts in results:

        minute = str(ts)[0:17] + "00"
        hour = str(ts)[0:14] + "00:00"

        if status == "CHG" and chg is not None:
            chgmin[minute].append(chg)

        elif status == "DCHG" and dchg is not None:
            dchgmin[minute].append(dchg)

        if soc is not None and soc <= 100:
            packdict[hour].append(soc)

    # -------------------------
    # cumulative lists
    # -------------------------
    for k in sorted(chgmin.keys()):
        chglist.append([k, max(chgmin[k])])

    for k in sorted(dchgmin.keys()):
        dchglist.append([k, max(dchgmin[k])])

    # -------------------------
    # hourly charge
    # -------------------------
    for i in range(1, len(chglist)):
        diff = chglist[i][1] - chglist[i - 1][1]

        if 0 < abs(diff) < 1000:
            hour = chglist[i][0][0:14] + "00:00"
            chgdict[hour] += diff / 1000

    # -------------------------
    # hourly discharge
    # -------------------------
    for i in range(1, len(dchglist)):
        diff = dchglist[i][1] - dchglist[i - 1][1]

        if 0 < abs(diff) < 1000:
            hour = dchglist[i][0][0:14] + "00:00"
            dchgdict[hour] += diff / 1000

    # -------------------------
    # INSERT CHARGING
    # -------------------------
    for ts, val in chgdict.items():

        sql = f"""
        INSERT INTO IOEbatteryHourly
        (polledTime,{st_prefix}chargingEnergy)
        VALUES(%s,%s)
        """

        try:
            cursor.execute(sql, (ts, abs(val)))
            emsdb.commit()

        except mysql.connector.errors.IntegrityError:
            sql = f"""
            UPDATE IOEbatteryHourly
            SET {st_prefix}chargingEnergy=%s
            WHERE polledTime=%s
            """
            cursor.execute(sql, (abs(val), ts))
            emsdb.commit()

    # -------------------------
    # INSERT SOC
    # -------------------------
    for ts, vals in packdict.items():

        sql = f"""
        INSERT INTO IOEbatteryHourly
        (polledTime,{st_prefix}packsoc)
        VALUES(%s,%s)
        """

        try:
            cursor.execute(sql, (ts, max(vals)))
            emsdb.commit()

        except mysql.connector.errors.IntegrityError:
            sql = f"""
            UPDATE IOEbatteryHourly
            SET {st_prefix}packsoc=%s
            WHERE polledTime=%s
            """
            cursor.execute(sql, (max(vals), ts))
            emsdb.commit()

    # -------------------------
    # INSERT DISCHARGING
    # -------------------------
    for ts, val in dchgdict.items():

        sql = f"""
        INSERT INTO IOEbatteryHourly
        (polledTime,{st_prefix}dischargingEnergy)
        VALUES(%s,%s)
        """

        try:
            cursor.execute(sql, (ts, -abs(val)))
            emsdb.commit()

        except mysql.connector.errors.IntegrityError:
            sql = f"""
            UPDATE IOEbatteryHourly
            SET {st_prefix}dischargingEnergy=%s
            WHERE polledTime=%s
            """
            cursor.execute(sql, (-abs(val), ts))
            emsdb.commit()


# =====================================================
# MAIN LOOP
# =====================================================

while True:
    cursor = emsdb.cursor()

    process_station(cursor, "ioeSt1BatteryData", "st1")
    process_station(cursor, "ioeSt2BatteryData", "st2")
    process_station(cursor, "ioeSt3BatteryData", "st3")
    process_station(cursor, "ioeSt4BatteryData", "st4")
    process_station(cursor, "ioeSt5BatteryData", "st5")

    cursor.close()

    print("Completed cycle")
    time.sleep(300)
