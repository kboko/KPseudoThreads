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

""" 
 * This small class implements skeleton for applications that has multiple inputs from many file descriptors
 * has timers or implement some state machine. 

 * The core is infinitive loop that process the queued events (pseudo threads) in user defined function.
 
 * We have 4 types of threads: read, write, execute and timer.
 *  - Read threads are registerd on a file descriptor, any incomming data will cause the thread to execute
 *  - Timer threads are executed when the timer has to be fired
 *  - Write threads are used from the caller to write to a file descriptor. For example the implemented protocol has to send data.
 *  - Execute threads are functions that has to be executed. May think of them as read threads with 0 timer.
 For all threads there is a separate Queue. 
 * Here is all this in short. See also the example.py

 * MainLoop for ever:
 *    check if there are any read event on registerd FDs queue, if any execute the hook function
 *    check if there is some write threads in the write queue, if any execute the hook function
 *    check if any timer from timer queues has expired, if any, execute the hook function
 *    check if any execute threads exist in the execute queue, if any execute the hook function
 *    

 *
"""
import datetime
import select
import os
import time
import threading
from multiprocessing import Pipe
from systemd import journal

# those are the log levels
LOG_CRIT=0
LOG_ERR=1
LOG_INFO=2
LOG_DBG=3

# where to log
LOG_NOLOG=0
LOG_CONSOLE=1
LOG_SYSLOG =2

'''
'''
class Logging():

	def __init__(self, log_name, log_level = LOG_ERR, log_facility = LOG_SYSLOG):
		self.name = log_name
		self.level = log_level
		self.facility = log_facility	

	def Log(self, prio, msg):
		if self.facility == LOG_NOLOG: 
			return
		if prio > self.level:
			return 
		if self.facility & LOG_CONSOLE:
			print ("{}.{}:{}".format (self.name, self.level, msg))
		if self.facility & LOG_SYSLOG:
			journal.send("{}.{}:{}".format (self.name, self.level, msg))
			

class MyPseudoThread():
	def __init__(self, thread_name, socket, function, args, time = None):
		self.thread_name = thread_name
		self.socket = socket
		self.args = args
		self.time = time
		self.function = function
		self.to_delete = False
	
class MyPseudoThreads(Logging): 
	def __init__(self, name, log_level, log_facility):
		self.THIS_MODULE = name
		self.stop=False
		self.threads_read=[]
		self.threads_write=[]
		self.threads_error=[]
		self.threads_timer=[]
		self.threads_exec=[]
		Logging.__init__(self, name, log_level, log_facility)

		self.Log(LOG_DBG, "Create threads {}".format(hex(id(self)))) 
	
	def add_read_thread(self, name, socket, function, args):
		
		for item in self.threads_read:
			if item.socket == socket and item.to_delete != True:
				self.Log(LOG_DBG,"Thread Exists")
				return None
		new_thread = MyPseudoThread(name, socket, function, args)
		self.threads_read.append(new_thread)
		self.Log(LOG_DBG, "Adding r-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(hex(id(new_thread)),socket.fileno(), name, function.__name__, args, hex(id(self))))
		return new_thread
	
	def add_write_thread(self,name, socket, function, args):
		
		for item in self.threads_write:
			if item.socket == socket and item.to_delete != True:
				self.Log(LOG_DBG,"Thread Exists")
				return None
		new_thread = MyPseudoThread(name, socket, function, args)
		self.threads_write.append(new_thread)
		self.Log(LOG_DBG,"Adding w-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(hex(id(new_thread)), socket.fileno(), name, function.__name__, args, hex(id(self))))
		return new_thread
		
	def add_error_thread(self,name, socket, function, args):
		
		for item in self.threads_error :
			if item.socket == socket and item.to_delete != True :
				self.Log(LOG_DBG,"Thread Exists")
				return None
		new_thread = MyPseudoThread(name, socket, function, args)
		self.Log(LOG_DBG,"Adding e-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(hex(id(new_thread)),socket.fileno(), name, function.__name__, args, hex(id(self))))
		self.threads_error.append(new_thread)
		return new_thread
	
	def add_timer_thread(self, name, after_ms, function, args):
		#return None
		when = int(round(time.time() * 1000)) + after_ms
		
		new_thread = MyPseudoThread(name, None, function, args, when)
		self.threads_timer.append(new_thread)
		sorted(self.threads_timer, key=lambda t: t.time, reverse=True) 
		self.Log(LOG_DBG,"Adding t-thread {} AFTER=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(hex(id(new_thread)),after_ms, name, function.__name__, args, hex(id(self))))
		return new_thread
		
	def add_execute_thread(self, name, function, args):
		
		new_thread = MyPseudoThread(name, None, function, args)
		self.threads_exec.append(new_thread)
		self.Log(LOG_DBG,"Adding ex-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(hex(id(new_thread)), name, function.__name__, args, hex(id(self))))
		return new_thread
	
	def cancel_thread(self, thread):
		thread.to_delete = True
		self.Log(LOG_DBG,"Cancel r-thread {} \"{}\" FUNC=\"{}\" TASK=\"{}\"".format(hex(id(thread)), thread.thread_name, thread.function.__name__, hex(id(self))))
		return
			
	def cancel_thread_by_sock(self, sock):
		for e in self.threads_read:
			if e.socket == sock:
				e.to_delete = True
				self.Log(LOG_DBG,"Cancel r-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(hex(id(e)),e.thread_name, e.function.__name__, e.args, hex(id(self))))
				
		for e in self.threads_write:
			if e.socket == sock:
				e.to_delete = True
				self.Log(LOG_DBG,"Cancel w-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(hex(id(e)),e.thread_name, e.function.__name__, e.args, hex(id(self))))
				
		for e in self.threads_error:
			if e.socket == sock:
				e.to_delete = True
				self.Log(LOG_DBG,"Cancel er-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(hex(id(e)),e.thread_name, e.function.__name__, e.args, hex(id(self))))
				
		
	def threads_stop(self):
		self.stop=True    
	
	def threads_dump(self, msg):
		self.Log(LOG_DBG,"DUMP Threads " + msg)
		for e in self.threads_write:
			if hasattr(e.socket, 'closed'):
				self.Log(LOG_DBG,"W {} Sock {} closed {} func {} todel {}".format (hex(id(e)), e.socket, e.socket.closed ,   e.function.__name__, e.to_delete))
		  
		for e in self.threads_read:
			if hasattr(e.socket, 'closed'):
				self.Log(LOG_DBG,"R {} Sock {} closed {} func {} todel {}".format (hex(id(e)), e.socket, e.socket.closed ,    e.function.__name__, e.to_delete))
			
		for e in self.threads_error:
			if hasattr(e.socket, 'closed'):
				self.Log(LOG_DBG,"E {} Sock {} closed {} func {} todel {}".format (hex(id(e)), e.socket, e.socket.closed ,   e.function.__name__, e.to_delete))
		for e in self.threads_timer:    
			if hasattr(e.socket, 'closed'):
				self.Log(LOG_DBG, "T {} Sock {} closed {} time {} func {} todel {}".format (hex(id(e)), e.socket, e.socket.closed ,  e.time , e.function.__name__, e.to_delete))
		self.Log(LOG_DBG, "DUMP Threads END")    
		
		
	def threads_run(self):
		self.Log(LOG_DBG, "RUN threads for {}".format (hex(id(self))))
		while self.stop != True:
			outputs = []
			inputs = []
			timeout = 1
			events=[]
			if True:
				now = int(round(time.time() * 1000)) 
				"""self.Log(LOG_DBG,"DUMP START R{} W{} E{} TIMER {}".format ([t.socket.fileno() for t in self.threads_read] , [t.socket.fileno() for t in self.threads_write], [t.socket.fileno() for t in self.threads_exec], [t.time-now for t in self.threads_timer]))"""
			
			# handle events
			for e in self.threads_exec:
				self.Log(LOG_DBG,"Run exec-thr {} {}".format(e.function.__name__, hex(id(e))))
				e.function(e.args)
			self.threads_exec=[]
			
			# soeckt events
			for e in self.threads_write:
				outputs.append(e.socket)    
			
			for e in self.threads_read:
				inputs.append(e.socket)    
			
			for e in self.threads_error:
				events.append(e.socket)   
			
			if len(self.threads_timer) == 0 and len(inputs) == 0 and len(outputs) == 0 and len(events) == 0:
				self.Log(LOG_DBG,"No threads to add - exiting")
				break
			if (len(self.threads_timer)):
				now = int(round(time.time() * 1000)) 
				e_time = self.threads_timer[-1].time
				time_out = float((e_time - now))/1000
				if time_out < 0:
					time_out = 0
				""" self.Log(LOG_DBG,"SELECT {} {} {} TIME {}".format ([t.fileno() for t in inputs], [t.fileno() for t in outputs], [t.fileno() for t in events], (e_time - now)/1000))"""
				try:
					readable, writable, exceptional = select.select(inputs, outputs, events, time_out)
				except Exception as msg:
					self.Log(LOG_ERR, str(msg))
					pass

			else:
				""" self.Log(LOG_DBG,"SELECT {} {} {} ".format ([t.fileno() for t in inputs], [t.fileno() for t in outputs], [t.fileno() for t in events]))"""
				try:
					readable, writable, exceptional = select.select(inputs, outputs, events)
				except Exception as msg:
					self.Log(LOG_ERR, str(msg))
					pass
				""" self.Log(LOG_DBG,"SELECT_AFTER {} {} {}".format ([t.fileno() for t in readable], [t.fileno() for t in writable], [t.fileno() for t in exceptional]))
				"""
				
			#now write threads - make copy and interate
			if len (writable):
				for fd in writable:
					for e in self.threads_write:
						if e.socket == fd and e.to_delete != True:
							self.Log(LOG_DBG,"Run w-thr {} {}".format(e.function.__name__, hex(id(e))))
							e.to_delete = True
							e.function(e.args)
							self.Log(LOG_DBG,"After w-thr {} {} TODEL".format(e.function.__name__, hex(id(e))))
							"""in case the thread add new read thread for same socket
							we make cancel as we do not want read thread to be executed twice
							"""
							break
			if len (readable):
				#now read threads
				for fd in readable:
					for e in self.threads_read:
						if e.socket == fd and e.to_delete != True:
							self.Log(LOG_DBG,"Run r-thr {} {}".format(e.function.__name__,  hex(id(e))))
							e.to_delete = True
							e.function(e.args)
							self.Log(LOG_DBG,"After Run r-thr {} {} TODEL".format(e.function.__name__,  hex(id(e))))
							break
			if len (exceptional):            
				#now error threads
				for fd in exceptional:
					for e in self.threads_error:
						if e.socket == fd and e.to_delete != True:
							self.Log(LOG_DBG,"Run e-thr {} {}".format(e.function.__name__,  hex(id(e))))
							e.to_delete = True
							e.function(e.args)
							self.Log(LOG_DBG,"After e-thr {} {} DEL".format(e.function.__name__,  hex(id(e))))
							break

			# handle timer threads
			now = int(round(time.time() * 1000)) 
			# handle late threads
			for e in self.threads_timer:
				if (now >= e.time ) and e.to_delete != True:
					self.Log(LOG_DBG,"Run t-thr {} {}".format( e.function.__name__,  hex(id(e))))
					e.to_delete = True
					e.function(e.args)
	  
			self.threads_read  = [item for item in self.threads_read  if item.to_delete != True]
			self.threads_write = [item for item in self.threads_write if item.to_delete != True]
			self.threads_error = [item for item in self.threads_error if item.to_delete != True]
			self.threads_timer = [item for item in self.threads_timer if item.to_delete != True]
			"""
			if True:
				now = int(round(time.time() * 1000)) 
				self.Log(LOG_DBG,"DUMP END R{} W{} E{} TIMER {}".format ([hex(id(t)) for t in self.threads_read] , [t.socket.fileno() for t in self.threads_write], [t.socket.fileno() for t in self.threads_exec], [t.time-now for t in self.threads_timer]))"""
