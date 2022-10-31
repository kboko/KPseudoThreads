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
import sys
sys.path.append('..')
from kpseudothreads import *
import traceback
import random 
import time
from datetime import datetime
"""
	This Test starts a lot of timer threads and display the times when the thread should have been 
	stated and the time it actually was fired.
	- Threads are scheduled in random range between 1-5000 ms. /thread_min_time thread_max_time
	- After each thread is fired predefined count times, it is no longer rescheduled
	- Threads count/Number to be executed each thread is specified at the class creation
	- DISPLAY=false is to disable printing on the console

	User can check the performance of the threads code with many timer threads. Depending on the machine the delays may be different
	
"""
DISPLAY=True
class TimerThreadTest_1(KPseudoThreads):
	
	def __init__(self, count_threads, max_count):
		KPseudoThreads.__init__(self, "SimpleStateMachineApp")
		self.max_delay = 0
		self.max_count = max_count
		self.count_threads = count_threads
		self.thread_min_time = 100
		self.thread_max_time = 5000
		self.all_threads_executed = 0

	def init_threads(self):
		for a in range(self.count_threads):
			execute_after_ms = random.randint(self.thread_min_time, self.thread_max_time)
			thread = self.add_timer_thread("Timer_{}".format (a), execute_after_ms, self.timer_fire, None)
			thread.count = 1

		
	def timer_fire(self, thread, arg):
		now = time.time_ns()
		self.all_threads_executed = self.all_threads_executed + 1
		if DISPLAY: print (datetime.now(), thread.thread_name, "FIRE count=", thread.count, "Delayed = ", (now - thread.time)/1000000, "ms")
		# record the max time
		if (now - thread.time) > self.max_delay:
			self.max_delay = now - thread.time

		execute_after_ms = random.randint(self.thread_min_time, self.thread_max_time)
		if thread.count < self.max_count:
			if DISPLAY: print (datetime.now(), thread.thread_name, "Schedule", execute_after_ms)
			new_thread = self.add_timer_thread(thread.thread_name, execute_after_ms, self.timer_fire, None)
			new_thread.count = thread.count + 1


def main():
	# MAIN
	something = TimerThreadTest_1( 5000, 10)
	try:
		print ("Starting")
		something.init_threads()
		something.threads_run();
		print ("Max Delayed Thread= {} ms. All threads executed count {} should be {}".format(something.max_delay/1000000, something.all_threads_executed, something.max_count * something.count_threads))
		print("All threads done. Stop")              
	except KeyboardInterrupt:
		traceback.print_exc()
		exit (1)
	except:
		traceback.print_exc()
	
if __name__ == "__main__":
	main()    
