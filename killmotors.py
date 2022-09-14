#!/usr/bin/env python3

#Quick shutdown of motors. If the main app crashes while the throttle is 
#up, they GPIO remains high and they'll keep running.

from adafruit_motorkit import MotorKit
import RPi.GPIO as GPIO

kit = MotorKit()
kit.motor1.throttle = 0
kit.motor2.throttle = 0
GPIO.cleanup()
