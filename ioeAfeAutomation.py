import requests
from datetime import datetime
import time
import mysql.connector
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from pymodbus.client.tcp import ModbusTcpClient
import socket
import logging

logging.basicConfig(
    filename='afeAutomation.log',  # Specify the log file name
    level=logging.DEBUG,     # Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

host = '121.242.232.211'

API_mapping = {
    '1': f'http://{host}:8009/ioesinglestr',
    '2': f'http://{host}:8009/ioedoublestr',
    '3': f'http://{host}:8009/ioetriplestr',
    '4': f'http://{host}:8009/ioefourstr',
    '5': f'http://{host}:8009/ioefivestr',
}

str_reply = {
    '1':f'http://{host}:5008/ioest1reply',
    '2':f'http://{host}:5008/ioest2reply',
    '3':f'http://{host}:5008/ioest3reply',
    '4':f'http://{host}:5008/ioest4reply',
    '5':f'http://{host}:5008/ioest5reply'
}

while True:
    curdate = datetime.now()
    curntime = int(str(curdate)[11:13])

    print(curdate)
    logger.info(curdate)

    if (curntime >= 6 and curntime <= 12) or (curntime >= 18 and curntime <= 21):
        print("Discharge")
        dchgLi = []
        MainLi = []
        voltLi = []
        PreLi = []
        try:
            emsdb = mysql.connector.connect(
                    host="121.242.232.211",
                    user="emsroot",
                    password="22@teneT",
                    database='EMS',
                    port=3306
                )
            
            emscur = emsdb.cursor()
        except Exception as ex:
            print(ex)
            continue
        curtime = datetime.now()
        if (curntime >= 6 and curntime <= 12):
            sqldate = str(datetime.now())[0:11]+"06:00:00"
        elif (curntime >= 18 and curntime <= 21):
            sqldate = str(datetime.now())[0:11]+"18:00:00"
        
        emscur.execute(f"select polledTime,onReason,offReason from EMS.ioeOnOff where polledTime >= '{sqldate}' order by polledTime desc limit 1;")
        sts = None
        fchk = emscur.fetchall()
        if len(fchk) > 0:
            curntime = int(str(fchk[0][0])[11:13])
            if (curntime >= 8 and curntime <= 12) or (curntime >= 18 and curntime <= 21):
                if fchk[0][2]:
                    sts = "NO"
            else:
                sts = "OK"
        else:
            sts = "OK"
        print(sts)
        logger.info(f"{curtime} | {sts}")
        
        if sts == "OK":
            emscur.execute("""SELECT batteryVoltage,mainContactorStatus,prechargeContactorStatus,batteryStatus,recordTimestamp 
                            FROM EMS.ioeBatteryData WHERE strings = 1 AND recordTimestamp >= current_date()
                            ORDER BY recordId DESC LIMIT 1;""")
            curtime = datetime.now()
            current_date = curtime.replace(hour=0, minute=0, second=0, microsecond=0)

            str1Res = emscur.fetchall()

            if len(str1Res) > 0:
                try:
                    if str1Res[0][1] != 'FAULT':
                        str1Time = str1Res[0][4]
                        voltLi.append(str1Res[0][0])
                        dchgLi.append(str1Res[0][3])
                        MainLi.append(str1Res[0][1])
                        PreLi.append(str1Res[0][2])
                    else:
                        str1Time = current_date
                except Exception as ex:
                        print(ex)
                        time.sleep(1)
                        continue
            else:
                str1Time = current_date

            emscur.execute("""SELECT batteryVoltage,mainContactorStatus,prechargeContactorStatus,batteryStatus,recordTimestamp 
                            FROM EMS.ioeBatteryData WHERE strings = 2 AND recordTimestamp >= current_date()
                            ORDER BY recordId DESC LIMIT 1;""")
            
            str2Res = emscur.fetchall()

            if len(str2Res) > 0:
                try:
                    str2Time = str2Res[0][4]
                    voltLi.append(str2Res[0][0])
                    dchgLi.append(str2Res[0][3])
                    MainLi.append(str2Res[0][1])
                    PreLi.append(str2Res[0][2])
                except Exception as ex:
                        print(ex)
                        time.sleep(1)
                        continue
            else:
                str2Time = current_date

            emscur.execute("""SELECT batteryVoltage,mainContactorStatus,prechargeContactorStatus,batteryStatus,recordTimestamp 
                            FROM EMS.ioeBatteryData WHERE strings = 3 AND recordTimestamp >= current_date()
                            ORDER BY recordId DESC LIMIT 1;""")
            
            str3Res = emscur.fetchall()

            if len(str3Res) > 0:
                try:
                    str3Time = str3Res[0][4]
                    voltLi.append(str3Res[0][0])
                    dchgLi.append(str3Res[0][3])
                    MainLi.append(str3Res[0][1])
                    PreLi.append(str3Res[0][2])
                except Exception as ex:
                        print(ex)
                        time.sleep(1)
                        continue
            else:
                str3Time = current_date

            emscur.execute("""SELECT batteryVoltage,mainContactorStatus,prechargeContactorStatus,batteryStatus,recordTimestamp 
                            FROM EMS.ioeBatteryData WHERE strings = 4 AND recordTimestamp >= current_date()
                            ORDER BY recordId DESC LIMIT 1;""")
            
            str4Res = emscur.fetchall()

            if len(str4Res) > 0:
                try:
                    str4Time = str4Res[0][4]
                    voltLi.append(str4Res[0][0])
                    dchgLi.append(str4Res[0][3])
                    MainLi.append(str4Res[0][1])
                    PreLi.append(str4Res[0][2])
                except Exception as ex:
                        print(ex)
                        time.sleep(1)
                        continue
            else:
                str4Time = current_date

            emscur.execute("""SELECT batteryVoltage,mainContactorStatus,prechargeContactorStatus,batteryStatus,recordTimestamp 
                            FROM EMS.ioeBatteryData WHERE strings = 5 AND recordTimestamp >= current_date()
                            ORDER BY recordId DESC LIMIT 1;""")
            
            str5Res = emscur.fetchall()

            if len(str5Res) > 0:
                try:
                    print(str5Res[0][4])
                    str5Time = str5Res[0][4]
                    voltLi.append(str5Res[0][0])
                    dchgLi.append(str5Res[0][3])
                    MainLi.append(str5Res[0][1])
                    PreLi.append(str5Res[0][2])
                except Exception as ex:
                        print(ex)
                        time.sleep(1)
                        continue
            else:
                str5Time = current_date
            
            if len(voltLi) > 0:
                volt = sum(voltLi)/len(voltLi)
            else:
                continue

            print(dchgLi)
            print(MainLi)
            print(voltLi)
            print(str1Time,str2Time,str3Time,str4Time,str5Time)
            logger.info(f"{curtime} | {dchgLi} | {MainLi}")

            volt = 0
            count = 0

            for i in voltLi:
                if i != None and i > 0:
                    volt += i
                    count += 1

            if volt != 0:
                avgVolt = volt/count
            
            print('Average Voltage :', avgVolt)

            if len(dchgLi) > 0 and len(MainLi) > 0:
                
                if 'FAULT' not in MainLi and 'DCHG' not in dchgLi and 'ON' not in MainLi and avgVolt > 680:
                    print(dchgLi,MainLi)

                    str1lag = (curtime - str1Time).total_seconds()
                    str2lag = (curtime - str2Time).total_seconds()
                    str3lag = (curtime - str3Time).total_seconds()
                    str4lag = (curtime - str4Time).total_seconds()
                    str5lag = (curtime - str5Time).total_seconds()

                    def GetCloseVoltage(dictionary):
                        close_pairs = []
                        keys = list(dictionary.keys())
                        for i in range(len(keys)):
                            for j in range(i + 1, len(keys)):
                                key1 = keys[i]
                                key2 = keys[j]
                                diff = abs(dictionary[key1] - dictionary[key2])
                                if diff <= 10:
                                    close_pairs.append((key1, key2))
                        return close_pairs

                    strtime = {}

                    if str1lag <= 500:
                        strtime['str1'] = str1Res[0][0]
                    if str2lag <= 500:
                        strtime['str2'] = str2Res[0][0]
                    if str3lag <= 500:
                        strtime['str3'] = str3Res[0][0]
                    if str4lag <= 500:
                        strtime['str4'] = str4Res[0][0]
                    if str5lag <= 500:
                        strtime['str5'] = str5Res[0][0]
                    
                    print(strtime)

                    finalStr = GetCloseVoltage(strtime)

                    all_strings = [item for sublist in finalStr for item in sublist]

                    unique_strings = set(all_strings)

                    print(unique_strings)

                    strings = ','.join(t for t in unique_strings)

                    strings = strings+',DCHG'

                    print(strings)

                    li = strings.split(',')

                    if len(li) >= 2:
                        apiNo = str(len(li)-1)

                        ApiUrl = API_mapping[apiNo]
                    else:
                        time.sleep(3)
                        continue

                    crate = '0.1'

                    ApiUrl = ApiUrl+f'?strings={strings}&crate={crate}'
                    print(ApiUrl)

                    ONurl = requests.get(ApiUrl)

                    resJson = ONurl.json()

                if 'FAULT' in MainLi or 'FAULT' in PreLi:
                    ApiUrl = f"http://{host}:8009/ioeprocessoff"    
                    OFFurl = requests.get(ApiUrl)
                    resJson = OFFurl.json()

                    print("Discharge/Charge OFF due to Fault")

                    time.sleep(800)


                if ("CHG" in dchgLi) and ("ON" in MainLi) and avgVolt > 680:
                    print(dchgLi,MainLi)

                    ApiUrl = f"http://{host}:8009/ioeprocessoff"    
                    OFFurl = requests.get(ApiUrl)
                    resJson = OFFurl.json()

                    print("Charge OFF")

                    time.sleep(800)

                    str1lag = (curtime - str1Time).total_seconds()
                    str2lag = (curtime - str2Time).total_seconds()
                    str3lag = (curtime - str3Time).total_seconds()
                    str4lag = (curtime - str4Time).total_seconds()
                    str5lag = (curtime - str5Time).total_seconds()

                    def GetCloseVoltage(dictionary):
                        close_pairs = []
                        keys = list(dictionary.keys())
                        for i in range(len(keys)):
                            for j in range(i + 1, len(keys)):
                                key1 = keys[i]
                                key2 = keys[j]
                                diff = abs(dictionary[key1] - dictionary[key2])
                                if diff <= 10:
                                    close_pairs.append((key1, key2))
                        return close_pairs

                    strtime = {}

                    try:
                        if str1lag <= 500:
                            strtime['str1'] = str1Res[0][0]
                        if str2lag <= 500:
                            strtime['str2'] = str2Res[0][0]
                        if str3lag <= 500:
                            strtime['str3'] = str3Res[0][0]
                        if str4lag <= 500:
                            strtime['str4'] = str4Res[0][0]
                        if str5lag <= 500:
                            strtime['str5'] = str5Res[0][0]
                    except Exception as ex:
                        print(ex)
                        time.sleep(3)
                        continue
                    
                    print(strtime)

                    finalStr = GetCloseVoltage(strtime)

                    print(finalStr)

                    all_strings = [item for sublist in finalStr for item in sublist]

                    unique_strings = set(all_strings)

                    strings = ','.join(t for t in unique_strings)

                    strings = strings+',DCHG'

                    print(strings)

                    li = strings.split(',')

                    if len(li) >= 2:
                        apiNo = str(len(li)-1)

                        ApiUrl = API_mapping[apiNo]
                    else:
                        time.sleep(2)
                        continue

                    crate = '0.1'

                    ApiUrl = ApiUrl+f'?strings={strings}&crate={crate}'
                    print(ApiUrl)
                    if volt >= 680:
                        ONurl = requests.get(ApiUrl)

                        print(ONurl.json())
                    else:
                        print("Discharged!")


                if all(x == "IDLE" for x in dchgLi) and ("ON" in MainLi) and avgVolt > 680:
                    print(dchgLi,MainLi)

                    str1lag = (curtime - str1Time).total_seconds()
                    str2lag = (curtime - str2Time).total_seconds()
                    str3lag = (curtime - str3Time).total_seconds()
                    str4lag = (curtime - str4Time).total_seconds()
                    str5lag = (curtime - str5Time).total_seconds()

                    def GetCloseVoltage(dictionary):
                        close_pairs = []
                        keys = list(dictionary.keys())
                        for i in range(len(keys)):
                            for j in range(i + 1, len(keys)):
                                key1 = keys[i]
                                key2 = keys[j]
                                diff = abs(dictionary[key1] - dictionary[key2])
                                if diff <= 10:
                                    close_pairs.append((key1, key2))
                        return close_pairs

                    strtime = {}

                    if str1lag <= 500:
                        strtime['str1'] = str1Res[0][0]
                    if str2lag <= 500:
                        strtime['str2'] = str2Res[0][0]
                    if str3lag <= 500:
                        strtime['str3'] = str3Res[0][0]
                    if str4lag <= 500:
                        strtime['str4'] = str4Res[0][0]
                    if str5lag <= 500:
                        strtime['str5'] = str5Res[0][0]
                    
                    print(strtime)

                    finalStr = GetCloseVoltage(strtime)

                    all_strings = [item for sublist in finalStr for item in sublist]

                    unique_strings = set(all_strings)

                    print(unique_strings)

                    strings = ','.join(t for t in unique_strings)

                    strings = strings+',DCHG'

                    print(strings)

                    li = strings.split(',')

                    crate = '0.1'

                    ApiUrl = f'http://{host}:8009/convertoron'+f'?strings={strings}&crate={crate}'
                    print(ApiUrl)

                    ONurl = requests.get(ApiUrl)

                    resJson = ONurl.json()
                
                if ("IDLE" in dchgLi) and ("ON" in MainLi) and avgVolt < 678:
                    print(dchgLi,MainLi)
                    
                    ApiUrl = f"http://{host}:8009/ioeprocessoff"    
                    OFFurl = requests.get(ApiUrl)
                    resJson = OFFurl.json()

                    print("Discharge OFF")



    if (curntime >= 22 or curntime <= 5) or (curntime >= 13 and curntime <= 17):
        chgLi = []
        MainLi = []
        voltLi = []
        PreLi = []
        try:
            emsdb = mysql.connector.connect(
                    host="121.242.232.211",
                    user="emsroot",
                    password="22@teneT",
                    database='EMS',
                    port=3306
                )
            
            emscur = emsdb.cursor()
        except Exception as ex:
            print(ex)
            continue

        curtime = datetime.now()

        current_date = curtime.replace(hour=0, minute=0, second=0, microsecond=0)

        if (curntime >= 22 or curntime <= 5):
            if curntime >= 22:
                sqldate = str(datetime.now())[0:11]+"22:00:00"
            if curntime <= 5:
                sqldate = str(datetime.now())[0:11]+"00:00:00"

        elif (curntime >= 13 and curntime <= 17):
            sqldate = str(datetime.now())[0:11]+"13:00:00"

        emscur.execute(f"select polledTime,onReason,offReason from EMS.ioeOnOff where polledTime >= '{sqldate}' order by polledTime desc limit 1;")
        sts = None
        fchk = emscur.fetchall()
        if len(fchk) > 0:
            curntime = int(str(fchk[0][0])[11:13])
            if (curntime >= 22 or curntime <= 3) or (curntime >= 11 and curntime <= 18):
               if fchk[0][2]:
                    sts = "NO"
            else:
                sts = "OK"
        else:
            sts = "OK"

        print("Status",sts)
        logger.info(f"{curtime} | {sts}")


        if sts == "OK":
            emscur.execute("""SELECT batteryVoltage,mainContactorStatus,prechargeContactorStatus,batteryStatus,recordTimestamp 
                            FROM EMS.ioeBatteryData WHERE strings = 1 AND recordTimestamp >= current_date()
                            ORDER BY recordId DESC LIMIT 1;""")
            
            str1Res = emscur.fetchall()

            if len(str1Res) > 0:
                try:
                    str1Time = str1Res[0][4]
                    voltLi.append(str1Res[0][0])
                    chgLi.append(str1Res[0][3])
                    MainLi.append(str1Res[0][1])
                    PreLi.append(str1Res[0][2])
                except Exception as ex:
                        print(ex)
                        time.sleep(1)
                        continue
            else:
                str1Time = current_date

            emscur.execute("""SELECT batteryVoltage,mainContactorStatus,prechargeContactorStatus,batteryStatus,recordTimestamp 
                            FROM EMS.ioeBatteryData WHERE strings = 2 AND recordTimestamp >= current_date()
                            ORDER BY recordId DESC LIMIT 1;""")
            
            str2Res = emscur.fetchall()

            if len(str2Res) > 0:
                try:
                    str2Time = str2Res[0][4]
                    voltLi.append(str2Res[0][0])
                    chgLi.append(str2Res[0][3])
                    MainLi.append(str2Res[0][1])
                    PreLi.append(str2Res[0][2])
                except Exception as ex:
                        print(ex)
                        time.sleep(1)
                        continue
            else:
                str2Time = current_date

            emscur.execute("""SELECT batteryVoltage,mainContactorStatus,prechargeContactorStatus,batteryStatus,recordTimestamp 
                            FROM EMS.ioeBatteryData WHERE strings = 3 AND recordTimestamp >= current_date()
                            ORDER BY recordId DESC LIMIT 1;""")
            
            str3Res = emscur.fetchall()

            if len(str3Res) > 0:
                try:
                    str3Time = str3Res[0][4]
                    voltLi.append(str3Res[0][0])
                    chgLi.append(str3Res[0][3])
                    MainLi.append(str3Res[0][1])
                    PreLi.append(str3Res[0][2])
                except Exception as ex:
                        print(ex)
                        time.sleep(1)
                        continue
            else:
                str3Time = current_date

            emscur.execute("""SELECT batteryVoltage,mainContactorStatus,prechargeContactorStatus,batteryStatus,recordTimestamp 
                            FROM EMS.ioeBatteryData WHERE strings = 4 AND recordTimestamp >= current_date()
                            ORDER BY recordId DESC LIMIT 1;""")
            
            str4Res = emscur.fetchall()

            if len(str4Res) > 0:
                try:
                    str4Time = str4Res[0][4]
                    voltLi.append(str4Res[0][0])
                    chgLi.append(str4Res[0][3])
                    MainLi.append(str4Res[0][1])
                    PreLi.append(str4Res[0][2])
                except Exception as ex:
                        print(ex)
                        time.sleep(1)
                        continue
            else:
                str4Time = current_date

            emscur.execute("""SELECT batteryVoltage,mainContactorStatus,prechargeContactorStatus,batteryStatus,recordTimestamp 
                            FROM EMS.ioeBatteryData WHERE strings = 5 AND recordTimestamp >= current_date()
                            ORDER BY recordId DESC LIMIT 1;""")
            
            str5Res = emscur.fetchall()

            if len(str5Res) > 0:
                try:
                    str5Time = str5Res[0][4]
                    voltLi.append(str5Res[0][0])
                    chgLi.append(str5Res[0][3])
                    MainLi.append(str5Res[0][1])
                    PreLi.append(str5Res[0][2])
                except Exception as ex:
                        print(ex)
                        time.sleep(1)
                        continue
            else:
                str5Time = current_date
            
            if len(voltLi) > 0:
                volt = sum(voltLi)/len(voltLi)
            else:
                continue

            volt = 0
            count = 0

            for i in voltLi:
                if i != None and i > 0:
                    volt += i
                    count += 1

            if volt != 0:
                avgVolt = volt/count
            
            print('Average Voltage :', avgVolt)
            print(chgLi,MainLi)
            logger.info(f"{curtime} | {chgLi} | {MainLi}")

            if 'FAULT' in MainLi or 'FAULT' in PreLi:
                    ApiUrl = f"http://{host}:8009/ioeprocessoff"    
                    OFFurl = requests.get(ApiUrl)
                    resJson = OFFurl.json()

                    print("Discharge/Charge OFF due to Fault")

                    time.sleep(800)
            
            if len(chgLi) > 0 and len(MainLi) > 0:
                if ("DCHG" in chgLi) and ("ON" in MainLi) and avgVolt < 770:
                    ApiUrl = f"http://{host}:8009/ioeprocessoff"    
                    OFFurl = requests.get(ApiUrl)
                    resJson = OFFurl.json()

                    print("Discharge OFF")

                    time.sleep(800)

                    str1lag = (curtime - str1Time).total_seconds()
                    str2lag = (curtime - str2Time).total_seconds()
                    str3lag = (curtime - str3Time).total_seconds()
                    str4lag = (curtime - str4Time).total_seconds()
                    str5lag = (curtime - str5Time).total_seconds()

                    def GetCloseVoltage(dictionary):
                        close_pairs = []
                        keys = list(dictionary.keys())
                        for i in range(len(keys)):
                            for j in range(i + 1, len(keys)):
                                key1 = keys[i]
                                key2 = keys[j]
                                diff = abs(dictionary[key1] - dictionary[key2])
                                if diff <= 10:
                                    close_pairs.append((key1, key2))
                        return close_pairs

                    strtime = {}

                    try:
                        if str1lag <= 500:
                            strtime['str1'] = str1Res[0][0]
                        if str2lag <= 500:
                            strtime['str2'] = str2Res[0][0]
                        if str3lag <= 500:
                            strtime['str3'] = str3Res[0][0]
                        if str4lag <= 500:
                            strtime['str4'] = str4Res[0][0]
                        if str5lag <= 500:
                            strtime['str5'] = str5Res[0][0]
                    except Exception as ex:
                        print(ex)
                        time.sleep(3)
                        continue
                    
                    print(strtime)

                    finalStr = GetCloseVoltage(strtime)

                    print(finalStr)

                    all_strings = [item for sublist in finalStr for item in sublist]

                    unique_strings = set(all_strings)

                    strings = ','.join(t for t in unique_strings)

                    strings = strings+',CHG'

                    print(strings)

                    li = strings.split(',')

                    if len(li) >= 2:
                        apiNo = str(len(li)-1)

                        ApiUrl = API_mapping[apiNo]
                    else:
                        time.sleep(2)
                        continue

                    crate = '0.1'

                    ApiUrl = ApiUrl+f'?strings={strings}&crate={crate}'
                    print(ApiUrl)
                    if avgVolt <= 770:
                        ONurl = requests.get(ApiUrl)

                        print(ONurl.json())
                    else:
                        print("Charged!")

                if 'FAULT' not in MainLi and 'CHG' not in chgLi and 'ON' not in MainLi:
                    str1lag = (curtime - str1Time).total_seconds()
                    str2lag = (curtime - str2Time).total_seconds()
                    str3lag = (curtime - str3Time).total_seconds()
                    str4lag = (curtime - str4Time).total_seconds()
                    str5lag = (curtime - str5Time).total_seconds()

                    def GetCloseVoltage(dictionary):
                        close_pairs = []
                        keys = list(dictionary.keys())
                        for i in range(len(keys)):
                            for j in range(i + 1, len(keys)):
                                key1 = keys[i]
                                key2 = keys[j]
                                diff = abs(dictionary[key1] - dictionary[key2])
                                if diff <= 10:
                                    close_pairs.append((key1, key2))
                        return close_pairs

                    strtime = {}

                    try:
                        if str1lag <= 500:
                            strtime['str1'] = str1Res[0][0]
                        if str2lag <= 500:
                            strtime['str2'] = str2Res[0][0]
                        if str3lag <= 500:
                            strtime['str3'] = str3Res[0][0]
                        if str4lag <= 500:
                            strtime['str4'] = str4Res[0][0]
                        if str5lag <= 500:
                            strtime['str5'] = str5Res[0][0]
                    except Exception as ex:
                        print(ex)
                        time.sleep(3)
                        continue
                    
                    print(strtime)

                    finalStr = GetCloseVoltage(strtime)

                    print(finalStr)

                    all_strings = [item for sublist in finalStr for item in sublist]

                    unique_strings = set(all_strings)

                    strings = ','.join(t for t in unique_strings)

                    strings = strings+',CHG'

                    print(strings)

                    li = strings.split(',')

                    if len(li) >= 2:
                        apiNo = str(len(li)-1)

                        ApiUrl = API_mapping[apiNo]
                    else:
                        time.sleep(2)
                        continue

                    crate = '0.1'

                    ApiUrl = ApiUrl+f'?strings={strings}&crate={crate}'
                    print(ApiUrl)
                    if avgVolt < 770:
                        ONurl = requests.get(ApiUrl)

                        print(ONurl.json())
                    else:
                        print("Charged!")

                if ("IDLE" in chgLi) and ("ON" in MainLi) and avgVolt < 770:
                    print(chgLi,MainLi)

                    str1lag = (curtime - str1Time).total_seconds()
                    str2lag = (curtime - str2Time).total_seconds()
                    str3lag = (curtime - str3Time).total_seconds()
                    str4lag = (curtime - str4Time).total_seconds()
                    str5lag = (curtime - str5Time).total_seconds()

                    def GetCloseVoltage(dictionary):
                        close_pairs = []
                        keys = list(dictionary.keys())
                        for i in range(len(keys)):
                            for j in range(i + 1, len(keys)):
                                key1 = keys[i]
                                key2 = keys[j]
                                diff = abs(dictionary[key1] - dictionary[key2])
                                if diff <= 10:
                                    close_pairs.append((key1, key2))
                        return close_pairs

                    strtime = {}

                    if str1lag <= 500:
                        strtime['str1'] = str1Res[0][0]
                    if str2lag <= 500:
                        strtime['str2'] = str2Res[0][0]
                    if str3lag <= 500:
                        strtime['str3'] = str3Res[0][0]
                    if str4lag <= 500:
                        strtime['str4'] = str4Res[0][0]
                    if str5lag <= 500:
                        strtime['str5'] = str5Res[0][0]
                    
                    print(strtime)

                    finalStr = GetCloseVoltage(strtime)

                    all_strings = [item for sublist in finalStr for item in sublist]

                    unique_strings = set(all_strings)

                    print(unique_strings)

                    strings = ','.join(t for t in unique_strings)

                    strings = strings+',CHG'

                    print(strings)

                    li = strings.split(',')

                    crate = '0.1'

                    ApiUrl = f'http://{host}:8009/convertoron'+f'?strings={strings}&crate={crate}'
                    print(ApiUrl)

                    ONurl = requests.get(ApiUrl)

                    resJson = ONurl.json()
                
                if (x == "IDLE" for x in chgLi) and ("ON" in MainLi) and avgVolt > 770:
                    print(dchgLi,MainLi)
                    
                    ApiUrl = f"http://{host}:8009/ioeprocessoff"    
                    OFFurl = requests.get(ApiUrl)
                    resJson = OFFurl.json()

                    print("Charge OFF")

        emscur.close()

    time.sleep(20)
