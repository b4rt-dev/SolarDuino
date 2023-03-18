import serial
import time
from datetime import datetime

arduinoPort = "/dev/ttyUSB0"
baud = 115200
outFolder = "output/"
outFile = "-solarDuino.csv"

ser = serial.Serial(arduinoPort, baud)

while True:
    rawData = ser.readline()
    data = rawData.decode('utf-8')
    data = "{:.2f}, ".format(time.time()) + data

    currenDay = datetime.today().strftime('%Y-%m-%d')
    with open(outFolder+currenDay+outFile, 'a') as f:
        f.write(data)
