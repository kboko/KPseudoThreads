#!/usr/bin/python3
"""
MIT License

Copyright (c) 2022 Kaloyan Stoilov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE."""

from mypseudothreads import MyTask 
import os
import time
class Something(MyTask):
    def __init__(self):
        MyTask.__init__(self)
    
    def task_pre_run_hook(self):
        self.add_timer_thread("Timer_1", 2000, self.timer_1_fire, None)

    def timer_1_fire(self, thr, arg):
        print("Child is working")


something = Something()
something.start()
while True:
    print ("Parent sleeps tonight")
    time.sleep(1)