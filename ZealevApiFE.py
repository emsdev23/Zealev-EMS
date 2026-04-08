from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
from fastapi.responses import JSONResponse
import math
import json
from datetime import datetime

app = FastAPI()

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

file_path = "/home/tenet/ems/py_script/db_creds.json"

with open(file_path, 'r') as file:
    data = json.load(file)

def get_emsdb():
    db = mysql.connector.connect(
        host=data['emsDB']['host'],
        user=data['emsDB']['user'],
        password=data['emsDB']['password'],
        database='EMS',
        port=data['emsDB']['port']
    )
    return db

def get_awsdb():
    db = mysql.connector.connect(
        host=data['awsDB']['host'],
        user=data['awsDB']['user'],
        password=data['awsDB']['password'],
        database='EMS',
        port=data['awsDB']['port']
    )
    return db

def get_meterdb():
    db=mysql.connector.connect(
        host=data['awsDB']['host'],
        user=data['awsDB']['user'],
        password=data['awsDB']['password'],
        database='meterdata',
        port=data['awsDB']['port']
    )
    return db


def custom_round(number):
    last_two_digits = number % 100
    if last_two_digits < 50:
        return (number // 100) * 100
    else:
        return ((number // 100) + 1) * 100

def process_energy_data(data):
    result = {}
    for entity, records in data.items():
        sorted_records = sorted(records, key=lambda x: x['polledTime'])
        total_energy = sum(record['Energy'] for record in sorted_records)

        result[entity] = sorted_records
        result[entity].append({'totalEnergy': total_energy})

    return result


@app.get("/zealev/convertor")
def get_convertor_status(db: mysql.connector.connect = Depends(get_emsdb)):

    try:
        ems_db = get_awsdb()
        emscur = ems_db.cursor(dictionary=True)

        # 🔋 Aggregated battery status (strings 1–5, today)
        emscur.execute("""
            SELECT
                CASE
                    WHEN SUM(batteryStatus = 'DCHG') > 0 THEN 'Inverter'
                    WHEN SUM(batteryStatus = 'CHG')  > 0 THEN 'Rectifier'
                    ELSE 'Idle'
                END AS systemMode,

                CASE
                    WHEN SUM(mainContactorStatus = 'ON') > 0 THEN 'ON'
                    ELSE 'OFF'
                END AS mainContactorStatus,

                SUM(batteryCurrent) AS totalBatteryCurrent,
                AVG(batteryVoltage) AS avgBatteryVoltage

            FROM (
                SELECT t.batteryCurrent,
                       t.batteryStatus,
                       t.mainContactorStatus,
                       t.batteryVoltage
                FROM ioeBatteryData t
                JOIN (
                    SELECT strings, MAX(recordId) AS max_id
                    FROM ioeBatteryData
                    WHERE recordTimestamp >= CURDATE()
                      AND strings IN (1,2,3,4,5)
                    GROUP BY strings
                ) latest
                ON t.recordId = latest.max_id
            ) latest_data;
        """)

        battery_data = emscur.fetchone()  # single aggregated row

        # ⚡ Latest converter data (today)
        emscur.execute("""
            select afeconvertordcvoltage/1000,afeconvertordccurrent/1000,afeconvertorvabvoltage/1000,
            afeconvertorvcavoltage/1000,afeconvertorvbcvoltage/1000,afeconvertoriacurrent/1000,
            afeconvertoribcurrent/1000,afeconvertoriccurrent/1000,afeconvertorapparentpower/1000,
            afeconvertoractivepower/1000,afeconvertorreactivepower/1000
            from zealev.afeconvertor100kw where afeconvertorpolledtime >= curdate() order by afeconvertorrecid desc limit 1;
        """)

        convertor_data = emscur.fetchone()

        emscur.execute("""select max((afeconvertordcvoltage/1000)*(afeconvertordccurrent/1000)) as maxdcpower
            from zealev.afeconvertor100kw where afeconvertorpolledtime >= curdate();""")
        
        maxpowerres = emscur.fetchone()

        # 🔥 Merge both dictionaries into ONE
        battery_row = battery_data if battery_data else {}
        convertor_row = convertor_data if convertor_data else {}
        maxpowerres = maxpowerres if convertor_data else {}

        merged = {**battery_row, **convertor_row, **maxpowerres}

        # ✨ Optional: clean float precision
        if "totalBatteryCurrent" in merged:
            merged["totalBatteryCurrent"] = round(merged["totalBatteryCurrent"], 2)

        if "avgBatteryVoltage" in merged:
            merged["avgBatteryVoltage"] = round(merged["avgBatteryVoltage"], 2)

        # 📦 Return as SINGLE JSON LIST
        return [merged]

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"MySQL error: {str(e)}"
        )

    finally:
        try:
            emscur.close()
            ems_db.close()
        except:
            pass



@app.get('/Dashboard/IoeHourly')
def peak_demand_date(db: mysql.connector.connect = Depends(get_emsdb)):
    ioe_list = []
    try:
        processed_db = get_emsdb()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": f"MySQL connection error: {str(e)}"})
    
    emscur = processed_db.cursor()

    emscur.execute("""SELECT polledTime,st1chargingEnergy,st2chargingEnergy,st3chargingEnergy,st4chargingEnergy,st5chargingEnergy,
        st1dischargingEnergy,st2dischargingEnergy,st3dischargingEnergy,st4dischargingEnergy,st5dischargingEnergy,
        st1packsoc,st2packsoc,st3packsoc,st4packsoc,st5packsoc,
        st1Availableenergy,st2Availableenergy,st3Availableenergy,st4Availableenergy,st5Availableenergy
        FROM EMS.IOEbatteryHourly where polledTime >= curdate();""")
    
    res = emscur.fetchall()

    if len(res) > 0:

        for i in res:
            if i[1] == None and i[2] == None and i[3] == None and i[4] == None and i[5] == None and i[6] == None and i[7] == None and i[8] == None and i[9] == None and i[10] == None:
                polledTime = str(i[0])[11:16]
                pli = [i[11],i[12],i[13],i[14],i[15]]
                pli = [item for item in pli if item is not None]
                pack = round(sum(pli)/len(pli))
                ioe_list.append({"polledTime":polledTime,"chg1":0,"chg2":0,"chg3":0,"chg4":0,"chg5":0,
                                 "dchg1":0,"dchg2":0,"dchg3":0,"dchg4":0,"dchg5":0,"idle":0.1,
                                 "pack1":i[11],"pack2":i[12],"pack3":i[13],"pack4":i[14],"pack5":i[15],
                                 "availEn1":i[16],"availEn2":i[17],"availEn3":i[18],"availEn4":i[19],"availEn5":i[20]
 				 ,"totalChg":0,"totalDchg":0,"totalIdle":0.1,'totalPack':pack})
                
            else:
                polledTime = str(i[0])[11:16]
                chgli = [i[1],i[2],i[3],i[4],i[5]]
                chgli = [item for item in chgli if item is not None]
                totalChg = round(sum(chgli),2)
                dchgli = [i[6],i[7],i[8],i[9],i[10]]
                dchgli = [item for item in dchgli if item is not None]
                totalDchg = round(sum(dchgli),2)
                pli = [i[11],i[12],i[13],i[14],i[15]]
                pli = [item for item in pli if item is not None]
                pack = round(sum(pli)/len(pli))
                ioe_list.append({"polledTime":polledTime,"chg1":i[1],"chg2":i[2],"chg3":i[3],"chg4":i[4],"chg5":i[5],
                                 "dchg1":i[6],"dchg2":i[7],"dchg3":i[8],"dchg4":i[9],"dchg5":i[10],"idle":0,
                                 "pack1":i[11],"pack2":i[12],"pack3":i[13],"pack4":i[14],"pack5":i[15],
                                 "availEn1":i[16],"availEn2":i[17],"availEn3":i[18],"availEn4":i[19],"availEn5":i[20]
 				 ,"totalChg":totalChg,"totalDchg":totalDchg,"totalIdle":0.1,'totalPack':pack})

    return ioe_list


            
            
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5003)
