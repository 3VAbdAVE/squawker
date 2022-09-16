#squawker.py
# Classes for controlling the stupid bird robot's motors

from adafruit_motorkit import MotorKit
import RPi.GPIO as GPIO
from time import sleep
from signal import signal, SIGINT, SIGTERM

kit = MotorKit()
GPIO.setmode(GPIO.BCM) # BCM = Use logical pin numbering

class EyeBeakController:
    """The eyes and beak are controlled by the same motor running in opposite
    directions.
    Running forward opens the beak, running reverse blinks the eyes.
    There is a switch on each eye to track open or closed blinks.
    If the left switch is closed and the right switch is open, it indicates
    the eyes are open.
    If the left switch is open and the right switch is closed, it indicates the 
    eyes are closed.
    
    This class sets up the GPIO and motors to handle that, with some general 
    actions the bird can perform.
    """
    def __init__(self, reset = True, left_eye_switch = 12, 
                 right_eye_switch = 5, eye_beak_motor = kit.motor1):
        """The switches and motors are defaulted to where I happened to solder them onto the board.
        Motor1 is just coincidentally the one that's connected to the eyebeak."""
        self.left_eye_switch = left_eye_switch
        self.right_eye_switch = right_eye_switch
        self.eye_beak_motor = eye_beak_motor
        self.eye_beak_motor.FAST_DECAY = 0
        self.eye_beak_motor.SLOW_DECAY = 1
        self.eye_beak_motor.throttle = 0
        GPIO.setup(right_eye_switch, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(left_eye_switch, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
    def get_eye_state(self):
        """Returns whether eyes are open or closed based on the switch positions.

        Returns:
            str: open|closed|unknown
        """
        if GPIO.input(self.right_eye_switch) == 0 and GPIO.input(self.left_eye_switch) == 1:
            _eyestate = 'open'
        elif GPIO.input(self.right_eye_switch) == 1 and GPIO.input(self.left_eye_switch) == 0:
            _eyestate = 'closed'
        else:
            _eyestate = 'unknown'
        return _eyestate

    def fullblink(self):
        """Cycles one full blink to end in an open state

        Returns:
            str: Should always return open
        """
        print("Cycling one full blink.")
        self.eye_beak_motor.throttle = -1
        GPIO.wait_for_edge(self.left_eye_switch, GPIO.RISING)
        while GPIO.input(self.right_eye_switch) != 0 or GPIO.input(self.left_eye_switch) != 1:
           continue
        self.eye_beak_motor.throttle = 0
        return self.get_eye_state()

    def halfblink(self):
        """Runs the motor in reverse until the switches reverse position. 
        Usually about 0.1 sec.

        Returns:
            str: state of the eyes after the motor stops.
        """
        print("Toggling blink state.")
        _eyestate = self.get_eye_state()
        self.eye_beak_motor.throttle = -1

        if _eyestate == 'open' or _eyestate == 'unknown':
            GPIO.wait_for_edge(self.left_eye_switch, GPIO.RISING, bouncetime=50)
            while GPIO.input(self.left_eye_switch) != 0:
                continue
            self.eye_beak_motor.throttle = 0
        elif _eyestate == 'closed':
            GPIO.wait_for_edge(self.right_eye_switch, GPIO.RISING, bouncetime=50)
            while GPIO.input(self.right_eye_switch) != 0:
                continue
            self.eye_beak_motor.throttle = 0

        return self.get_eye_state()
    
    def set_eyes(self, state):
        """Sets eyes to a specific state.

        Args:
            state (str): open or closed

        Returns:
            str: state of the eyes after the motor stops.
        """
        while self.get_eye_state() is not state:
            self.halfblink()
        return self.get_eye_state()
            
    def open_beak(self):
        """Since eyes and beak can'e move simultaneously, this waits till any other 
        motor functions have stopped and then runs forward to open the beak.
        """
        while self.eye_beak_motor.throttle < 0:
            continue
        self.eye_beak_motor.throttle = 1
        
    def close_beak(self):
        """If the motor stops or runs backward, the beak closes."""
        self.eye_beak_motor.throttle = 0
        
    def kill_eye_beak_motor(self):
        """Just a method to guarantee we can stop this thing.
        """
        self.eye_beak_motor.throttle = 0
        
class BodyController():
    """The body is controlled by a single motor that drives it on a mechanical loop
    Average complete cycle between switch contacts is about 2.2s. 
    Moving the motor is done with float, so remember to / 100 where needed.
    
    This class sets up the GPIO and motors to handle that, with some general 
    actions the bird can perform.
    """
    def __init__(self, body_switch = 6, body_motor = kit.motor2):
        self.body_switch = body_switch
        self.body_motor = body_motor
        self.body_motor.FAST_DECAY = 0
        self.body_motor.SLOW_DECAY = 1
        self.body_motor.throttle = 0
        self.timeposition = 0
        GPIO.setup(body_switch, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
    def resetbody(self):
        """Runs the body motor forward until the cycle sensor switch closes.
        """
        self.body_motor.throttle = 1
        GPIO.wait_for_edge(self.body_switch, GPIO.RISING)
        while GPIO.input(self.body_switch) != 0:
            continue
        self.body_motor.throttle = 0
        self.timeposition = 0

    def _moveparams(self, current, dst, mx = 222):
        """A full cycle of the mechanical body takes approximately 2.22 seconds.
        Throughout that cycle, bounded at "position zero from the point where the 
        switch is closed and at 222 where the switch is open, different actions 
        can happen. For example, at position 0, the wings can flap by running the 
        motor in reverse .3 and then forward .3 back to position zero.
        
        This function returns the amount of time and the direction the motor should
        run in order to get from "current" to "dst". Direction is based on whether
        forward or reverse would be shorter. 
        
        The whole thing is a little wonky since the motor takes time to spin up/down
        and there's slop in the gears. It works for a few motions, but needs to
        baseline at zero pretty regularly.
        
        Inputs to this function should be int, based on "Hundredths of seconds * 100"
        
        Args:
            current (int): current time position
            dst (int): requested time position. Will default to zero if outside 0-222.
            mx (int): Maximum time bound. No reason this should ever not be 222.

        Returns:
            list: Current calculated time position. This is calculated, since the only position
            with a sensor is zero.
        """
        
        if dst not in range(mx):
            dst = 0
            
        fwd = mx - current + dst
        pmod = fwd % mx
        #print(f"Forward modulus is {pmod}")
        rev = dst - current - mx
        nmod = (rev * -1) % mx
        #print(f"Reverse Modulus is {nmod}")
        
        if pmod <= nmod:
            return [pmod, 1]
        
        return [nmod, -1]

    def setbodyPosition(self, dst = 0, d = None, mx = 222):
        """Run the body motor to a position relative to 0.0
        Value range is 0 - 2.22 ( / 100 ) seconds.
        This can be used to set up a specific movement
        for example, flapping the wings starts at position 190.
        
        The motors are slow and there's a lot of slop in the gears, so this
        isn't reliable over many actions without regular resets to zero. 

        Args:
            t (float): The time index to set the motor to
            d (int): The direction to run the motor.
        """   
        current = self.timeposition
        
        if dst == current:
            print("Body position matches request. Not moving.")
            pass
        
        else:
            action = self._moveparams(current, dst, mx)
            motortime = action[0] / 100
            if d == None:
                direction = action[1]
            else:
                direction = d
                
            if direction == 1:
                print(f"moving {motortime} forward to position {dst}")
            else:
                print(f"moving {motortime} reverse to position {dst}")
                
            # if motortime < 0.20:
            #     pass
            # else:
            self.body_motor.throttle = direction
            sleep(motortime)
            self.body_motor.throttle = 0
            #This new position is calculated, and unreliable because of motor and gear slop. 
            # Occasional resets to zero will help.
            self.timeposition = dst
            