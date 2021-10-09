#!/usr/bin/env python
from subprocess import Popen, PIPE, STDOUT
import RPi.GPIO as GPIO
import time
import smbus
import signal
from lib.daemon import *


def handler(signum, frame):
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(16, GPIO.OUT)
    GPIO.output(16, False)
    GPIO.cleanup()

signal.signal(signal.SIGHUP, handler)

class radiateur(Daemon):

    def __init__(self, pwm):
        self.pwm = pwm
        self.timing = 0

        self.pidfile = "/tmp/daemon-rad_python.pid"
        self.sysargv = sys.argv
        self.stderr = "/tmp/error.log"
        self.stdout = "/tmp/outrad.log"

        super().__init__(pidfile=self.pidfile, sysargv=self.sysargv, stderr=self.stderr, stdout=self.stdout)


    def check_sht35(self, bus, msg):
        # SHT3x hex adres
        SHT3x_ADDR		= 0x44
        SHT3x_SS		= 0x2C
        SHT3x_HIGH		= 0x06
        SHT3x_READ		= 0x00

        # MS to SL
        bus.write_i2c_block_data(SHT3x_ADDR,SHT3x_SS,[0x06])
        time.sleep(0.2)

        # Read out data
        dataT = bus.read_i2c_block_data(SHT3x_ADDR,SHT3x_READ,6)

        # Devide data into counts Temperature
        t_data = dataT[0] << 8 | dataT[1]

        # Devide data into counts Humidity
        h_data = dataT[3] << 8 | dataT[4]

        # Convert counts to Temperature/Humidity
        Humidity = 100.0*float(h_data)/65535.0
        Temperature = -45.0 + 175.0*float(t_data)/65535.0
        self.writetemp(round(Temperature,2), round(Humidity))
        print("{} Temp: {}  H: {}".format(msg, round(Temperature, 2), round(Humidity)))

        return Temperature, Humidity

    def writetemp(self, temp, hum):
        f = open("/home/pi/Python/radiateur/temp.log", "w")
        f.write("Temp: {} H: {}".format(temp, hum))
        f.close()

    def timingpwm(self):
        print("calcule par kwh pwm {}%".format(self.pwm))

        #calcule kwh to timing
        pwm = self.pwm
        calculepwm = (2300*pwm)/100
        kwh = calculepwm

        voltage = 230
        ampere = 10
        ah = (kwh/voltage)
        coulomb = ah*3600

        try:
            TA = (coulomb/ampere)
            Timing = round(3600/TA,2)
            print("timing par secondes :", round(3600/TA,2)) # result 3.5

        except ZeroDivisionError:
            TA = (coulomb/1)
            Timing = 0

        print("kwh :", calculepwm/1000)

        return Timing

    def updatetiming(self, value):
        self.pwm = value
        self.timing = self.timingpwm()

    def run(self):
        with open("stdout.txt","wb") as out, open("stderr.txt","wb") as err:
            self.x = Popen(['./home/pi/Python/radiateur/pwm'], stdout=out, stdin=PIPE, stderr=err, shell=True)

        self.timing = self.timingpwm()
        bus = smbus.SMBus(1)

        try:
            while self.x.poll() is None:
                temp, hum = self.check_sht35(bus, "temp1")
                if temp <= 100:

                    if self.pwm == 0:
                        self.x.stdin.write(b'pwm1 0\n')
                        self.x.stdin.flush()
                        time.sleep(1)
                    elif self.pwm != 100:
                        self.x.stdin.write(b'pwm1 99\n')
                        self.x.stdin.flush()
                        time.sleep(1)
                        self.x.stdin.write(b'pwm1 0\n')
                        self.x.stdin.flush()
                        time.sleep(self.timing)
                    else:
                        self.x.stdin.write(b'pwm1 99\n')
                        self.x.stdin.flush()
                        time.sleep(self.timing)

                else:
                    self.updatetiming(0)

            self.x.stdout.close()
            self.x.stdin.close()

        except KeyboardInterrupt:
            while self.x.poll() is None:
                self.x.stdin.write(b'stop\n')

                try:
                    self.x.stdin.write(b'stop\n')
                    self.x.stdin.flush()
                    self.exit()
                    break
                except BrokenPipeError:
                    continue

    def exit(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(16, GPIO.OUT)
        GPIO.output(16, False)
        GPIO.cleanup()

if __name__ == "__main__":
    rad = radiateur(3)
    #rad.run()
