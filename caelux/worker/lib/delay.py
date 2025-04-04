# Stereo multitap delay, designed for long, slow, and dramatic delays.

from pyo import *

class MultiTapDelay:
    def __init__(self, input, left_delays, right_delays, feedback=0.0, mul=1.0):
        self.input = input
        self.left_delays = [Delay(input, delay=dt, feedback=feedback, mul=mul) for dt in left_delays]
        self.right_delays = [Delay(input, delay=dt, feedback=feedback, mul=mul) for dt in right_delays]
        self.left = Mix(self.left_delays, voices=1)
        self.right = Mix(self.right_delays, voices=1)
        self.out = Mix([self.left, self.right], voices=2).out()

# Example usage:
s = Server().boot().start()

src = Sine(freq=220, mul=0.1)
delayer = MultiTapDelay(
    input=src,
    left_delays=[0.3, 0.6, 1.0],
    right_delays=[0.4, 0.7, 1.1],
    feedback=0.2,
    mul=0.5
)
