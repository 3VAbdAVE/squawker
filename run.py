#!/usr/bin/env python3

"""Primary runner app for the Squawker.
Requires a path to a directory full of 16bit wave files. 
Will probably crash on an empty directory."""

import argparse
import os
from functools import partial
from signal import signal, SIGINT, SIGTERM
from time import sleep
from random import randrange, choice
import squawker
from squawker import motors, sound
import asyncio
import RPi.GPIO as GPIO

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
        filename = choice(files)
        print(f"\nEnqueuing file {filename}.")
        qitem = {"sound":filename}
        await q.put(qitem)
        while body.body_motor.throttle is not 0 or beak.eye_beak_motor.throttle is not 0:
            continue
        await q.get()
        squawk.run(filename)
        print('Releasing queue.')
        q.task_done()
        print(f'Sound activation in {str(slp)}\n')
        await asyncio.sleep(slp)
        
if __name__ == '__main__':
    args = parseArgs()
    sounddir = args.sounddir
    beak = motors.EyeBeakController()
    body = motors.BodyController()
    squawk = sound.Squawk(beak, body)
    
    register_handler([beak, body])
      
    sleep(1)
    
    print("Initialize motors to a known position")
    body.resetbody()
    beak.fullblink()
    sleep(1)
    
    # Run the above functions simultaneously.
    q = asyncio.Queue()
    loop = asyncio.get_event_loop()
    async_tasks = asyncio.gather(
        eyeblinking(beak, q), 
        ambientMotion(body, q), 
        sounds(sounddir, body, beak, q)
        )
    loop.run_until_complete(async_tasks)
    
    body.body_motor.throttle = 0
    beak.eye_beak_motor.throttle = 0
