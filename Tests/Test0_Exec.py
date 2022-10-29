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

DISPLAY=True
class Test_0(KPseudoThreads):
	
	def __init__(self, count_threads):
		self.count_threads = count_threads
		KPseudoThreads.__init__(self, "SimpleStateMachineApp", LOG_DBG, LOG_CONSOLE)
		

	def init_threads(self):
		for a in range(self.count_threads):
			thread = self.add_execute_thread("Exec_{}".format (a), self.exec_thread_fire, a)
			thread.count = 1

		
	def exec_thread_fire(self, thread, a):
		time.sleep(1)
		print (datetime.now(), "FIRE {}".format (a))
		#new_thread = self.add_execute_thread("Exec_{}".format (a), self.exec_thread_fire, a)
		

def main():
	# MAIN
	something = Test_0(10)
	try:
		something.Log(LOG_INFO, "Starting",)
		something.init_threads()
		something.threads_run();
		something.Log(LOG_INFO, "All threads done. Stop")              
	except KeyboardInterrupt:
		traceback.print_exc()
		exit (1)
	except:
		traceback.print_exc()
	
if __name__ == "__main__":
	main()  