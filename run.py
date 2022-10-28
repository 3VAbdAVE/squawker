#!/usr/bin/env python3

"""Primary runner app for the Squawker.
Requires a path to a directory full of 16bit wave files. 
Will probably crash on an empty directory."""

import argparse, os, sys, logging, asyncio
from functools import partial
from signal import signal, SIGINT, SIGTERM
from time import sleep
from random import randrange, choice
import RPi.GPIO as GPIO
import squawker
from squawker import motors, sound

def parseArgs():
    parser = argparse.ArgumentParser(
    description='Do animatronic stuff.')
    parser.add_argument('sounddir', type=str, help="Relative path to directory with wav files.")
    return parser.parse_args()

def handler(signal, frame, motors):
    # Handle any cleanup here
    print('SIGINT or CTRL-C detected. Shutting down.')
    motors[0].eye_beak_motor.throttle = 0
    motors[1].body_motor.throttle = 0
    GPIO.cleanup()
    exit(0)
    
def register_handler(motors):
    global handler
    handler = partial(handler, motors = motors)
    signal(SIGINT, handler)
    signal(SIGTERM, handler)

async def eyeblinking(beak, q: asyncio.Queue) -> None:
    """Coroutine which blinks the eyes on a randomized interval.
    suspends itself if the queue is not empty.

    Args:
        beak (MotorKit): Motor attached to the beak/eyes
        q (asyncio.Queue): Queue
    """
    slp = randrange(4,14)
    print(f'Blinking coro wait {str(slp)} seconds.')
    await asyncio.sleep(slp)
    while True:
        await q.join()
        beak.set_eyes('closed')
        await asyncio.sleep(0.1)
        beak.set_eyes('open')
        slp = randrange(4,14)
        print(f'Blinking again in {str(slp)} seconds.')
        await asyncio.sleep(slp)
            
async def ambientMotion(body, q: asyncio.Queue) -> None:
    """Coroutine which moves the body on a randomized interval.
    suspends itself if the queue is not empty.

    Args:
        body (MotorKit): Motor attached to the body
        q (asyncio.Queue): Queue
    """
    slp = randrange(10,40)
    print(f"Body coro wait {str(slp)} seconds.")
    await asyncio.sleep(slp)
    while True:
        await q.join()
        squawker.rnd_action(body)
        slp = randrange(10,40)
        print(f"Body movement in {str(slp)} seconds.")
        await asyncio.sleep(slp)
    
async def eventdirector(q):
    tasklist = []
    while not q.empty():
        task = await q.get()
        if "sound" in task or "rfid" in task:
            print('Received sound queue task.')
            cmd = task.get("sound").get("cmd")
            filename = task.get("sound").get("filename")
            cmd.run(filename)
            print('Releasing sound queue task.')
            q.task_done()
        else:
            print("Unrecognized task, releasing.")
            q.task_done()
           
async def sounds(directory, body, beak, q: asyncio.Queue) -> None:
    """Coroutine that activates a wav file routine on a random interval.
    Ambient motion functions suspend during these activations

    Args:
        directory (str): directory of wav files
        body (MotorKit): Motor attached to the body
        beak (MotorKit): Motor attached to the beak/eyes
        q (asyncio.Queue): Queue
    """
    files = [os.path.join(directory, file) for file in os.listdir(directory)]
    squawk = sound.Squawk(beak, body)
    slp = randrange(30,60)
    print(f'Sound coro wait {str(slp)}')
    await asyncio.sleep(slp)
    
    while True:
        slp = randrange(30,60)
        await q.join()
        filename = choice(files)
        print(f"\nEnqueuing file {filename}.")
        qitem = {"sound": {"cmd": squawk, "filename" :filename}}
        await q.put(qitem)
        while body.body_motor.throttle is not 0 or beak.eye_beak_motor.throttle is not 0:
            await asyncio.sleep(0)
        await eventdirector(q)
        await q.join()
        print(f'Next sound activation in {str(slp)}\n')
        await asyncio.sleep(slp)
        
async def rfidevent(body, beak, q: asyncio.Queue) -> None:
    """Simulate an RFID event by updating a file"""
    directory = '/home/dave/Code/squawker/specialsounds'
    tmpfile = '/tmp/rfid'
    files = [os.path.join(directory, file) for file in os.listdir(directory)]
    
    with open(tmpfile,'w+') as f:
        pass
        
    while True:
        f = open(tmpfile,'r')
        text = f.read()
        f.close()
        if 'rfid_event' in text:
            print("RFID Event detected")
            squawk = sound.Squawk(beak, body)
            filename = choice(files)
            qitem = {"sound": {"cmd": squawk, "filename": filename}}
            await q.put(qitem)
            while body.body_motor.throttle is not 0 or beak.eye_beak_motor.throttle is not 0:
                await asyncio.sleep(0)
            await eventdirector(q)
            await q.join()
            f = open(tmpfile, 'w')
            f.close()
            
        await asyncio.sleep(0)
    
async def main(body, beak, sounddir):
    q = asyncio.Queue()
    eye_task = asyncio.create_task(eyeblinking(beak, q))
    body_task = asyncio.create_task(ambientMotion(body, q))
    sound_task = asyncio.create_task(sounds(sounddir, body, beak, q))
    rfid_task = asyncio.create_task(rfidevent(body, beak, q))
    await asyncio.gather(eye_task, body_task, sound_task, rfid_task)

if __name__ == '__main__':
    args = parseArgs()
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(fmt="%(asctime)s %(name)s.%(levelname)s: %(message)s", datefmt="%Y.%m.%d %H:%M:%S")
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    sounddir = args.sounddir
    beak = motors.EyeBeakController()
    body = motors.BodyController()
    
    register_handler([beak, body])
    
    sleep(1)
    
    logger.info("Initialize motors to a known position")
    # print("Initialize motors to a known position")
    body.resetbody()
    beak.fullblink()
    sleep(1)
    
    asyncio.run(main(body, beak, sounddir))
        
    body.body_motor.throttle = 0
    beak.eye_beak_motor.throttle = 0
