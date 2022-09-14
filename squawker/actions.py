#!/usr/bin/env python3
"""    
Defines a map of positions on the 2.22 sec timescale where specific actions happen
and then calls the BodyController functions to perform those actions.

The map defines both the start and the endpoints of each action, and the functions
determine whether it's faster to run through the desired action forward or in reverse.

Fir example, if the body is currently at 50, then it's faster to reverse the motor 
for 30ms and run wingshake in reverse than it is to move 140ms forward.  

The whole thing is a little wonky since the motor takes time to spin up/down
and there's slop in the gears. It works for a few motions, but needs to
baseline at zero after a few.

"""

from time import sleep
from random import choice

actionmap = {
    # If the motor is moving forward from a closed switch position
    # these actions start at the start time and end at the end time
    "wingshake": {"start": 190, "end": 20},
    "headbob": {"start": 102, "end": 190},
    "lookup": {"start": 15, "end": 65},
    "shuffle": {"start": 65, "end": 190}
}

def shortestpath(body,action):
    """Shortest amount of time from current to the desired time position

    Args:
        body (MotorKit): Motor driving the body
        action (str): named action for the body to make

    Returns:
        int: the int representing the desired time position
    """
    current = body.timeposition
    atime = actionmap.get(action)
    timelist = [atime.get("start"), atime.get("end")]
    return min(timelist,
          key = lambda x: abs(x-current))

def run_action(body, action):
    """Moves the motor to the selected action's nearest time position 
    and then moves through the action in the appropriate direction.

    Args:
        body (MotorKit): Motor driving the body
        action (str): named action for the body to make
    """
    dst = shortestpath(body, action)
    actiontimes = actionmap.get(action)
    body.setbodyPosition(dst)
    sleep(0.3)
    whichside = [i for i in actiontimes if actiontimes[i] == dst ][0]
    otherside = [i for i in actiontimes if i is not whichside][0]
    body.setbodyPosition(actiontimes.get(otherside))
    
def rnd_action(body):
    """Randomly selects and performs an action from the actionmap

    Args:
        body (MotorKit): Motor driving the body
    """
    action = choice([x for x in actionmap.keys()])
    print(f"Running randomly selected action: {action}")
    run_action(body,action)
