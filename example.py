#!/usr/bin/python3

from mypseudothreads import *
import traceback

class SimpleStateMachine(MyPseudoThreads):
	
	def __init__(self):
		MyPseudoThreads.__init__(self, "SimpleStateMachineApp", LOG_DBG, LOG_CONSOLE)
	
	def init_threads(self):
		self.add_timer_thread("Timer_1", 5000, self.timer_1_fire, None)
		
	def timer_1_fire(self, arg):
		self.add_timer_thread("Timer_1", 5000, self.timer_1_fire, None)

def main():
	# MAIN
	something = SimpleStateMachine()
	try:
		something.Log(LOG_INFO, "Starting")
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
