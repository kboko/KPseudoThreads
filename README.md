# KPseudoThreads
Overwivew
This module provides a framework for writing Python applications with pseudo threads. Those Threads
never work in paralell, that's why no synchronisation between them is needed. This makes implementing event based applications easier. 

It is released under a free software license, see LICENSE for more details.

Copyright (C) 2022 Kaloyan Stoilov <stoilov.kaloyan(at)gmail.com>

Other Pages (Online)

project Page on GitHub


Requirements
For now testet on Python 3.10, works on python2.7 too

Instalation
ToDo

Short introduction


The core of the framework is waiting on events on a select() syscall. If any event occur the select() exits
and process the events. Then the loop starts again until no more registered events exists.

The module implements a base class "KPseudoThreads" that needs to be inheritet.

The threads must be registered first, as we specify the hook functions to be executed and their arguments.

There are 4 types of threads. 
- Read - these threads waits on an read event from any file descriptor (may be Socket, Pipe, actually everything that can be put in select() ). If read or error event occur - the fd has received any data
to read, the hook function is called. This function must read the incomming data from the fd and eventually register new read thread.

- write - these threads waits are eecuted when a socket is ready for writing. When an application wants to 
send some data on an fd, calling of he hook function of this thread can actually send the data. The select
garantee that some data may be written on this fd.

- timer - these threads are executed after some timeout specified in the register function.

- execute - same as timer threads with timeout 0

There is another class "MyTask" which starts "KPseudoThreads" in a real Thread process. See detailed documentation.


Example2:
This code starts thread timer with timeout 2 sec:

from kpseudothreads import KPseudoThreads 
class SimpleTimerClass(KPseudoThreads):
	def __init__(self):
		KPseudoThreads.__init__(self, "Thread", KPseudoThreads.LOG_DBG, KPseudoThreads.LOG_CONSOLE)
		
	def timer_1_fire(self, thr, arg):
		self.Log(KPseudoThreads.LOG_INFO, "Thread Fired")

something = SimpleTimerClass()
something.add_timer_thread("Timer_1", 2000, something.timer_1_fire, None)
# the big loop starts here:
something.threads_run();


Read/Write Threads:
we start 2 Threads - read and write. As we can write on the pipe
the write thread is executed immediately, and it writes somthing on the pipe.
As there is something to read, the read thread is also executed.

from kpseudothreads import KPseudoThreads 
import os
class SimpleTimerClass(KPseudoThreads):
	
	def __init__(self):
		KPseudoThreads.__init__(self, "Thread", KPseudoThreads.LOG_DBG, KPseudoThreads.LOG_CONSOLE, debug=False)
		
	def read_thread_hook(self, thr, r_pipe):
		data = os.read(r_pipe, 100)
		print ("Received", data)

	def write_thread_hook(self, thr, w_pipe):
		print ("Sending..")
		os.write(w_pipe, b"Something")


r_pipe,w_pipe = os.pipe()
something = SimpleTimerClass()
something.add_read_thread("Read", r_pipe, something.read_thread_hook, r_pipe)
something.add_write_thread("Write", w_pipe, something.write_thread_hook, w_pipe)
something.threads_run();
os.close(r_pipe)
os.close(w_pipe)

Now a little bit more complicated:
We start 3 Threads: read, write and timer. 
The new here is the read thread reschedule itself and starts also one more time the write thread.
This loops sending and receiving. Also we add one timer thread to be executed after 100ms. It will
cancel the read/write threads and this ends the app.


from kpseudothreads import KPseudoThreads 
import os
class SimpleTimerClass(KPseudoThreads):
	
	def __init__(self):
		KPseudoThreads.__init__(self, "Thread", KPseudoThreads.LOG_DBG, KPseudoThreads.LOG_CONSOLE, debug=False)
		
	def read_thread_hook(self, thr, w_pipe):
		data = os.read(thr.socket, 100)
		print ("Received", data)
		self.add_read_thread("Read", thr.socket, something.read_thread_hook, w_pipe)
		self.add_write_thread("Write", w_pipe, something.write_thread_hook, thr.socket)

	def write_thread_hook(self, thr, r_pipe):
		print ("Sending..")
		os.write(thr.socket, b"Something")

	def timer_thread_hook(self, thr, arg):
		r_pipe,w_pipe = arg
		print ("Stop")
		self.cancel_thread_by_sock(r_pipe)
		self.cancel_thread_by_sock(w_pipe)

r_pipe,w_pipe = os.pipe()
something = SimpleTimerClass()
something.add_read_thread("Read", r_pipe, something.read_thread_hook, w_pipe)
something.add_write_thread("Write", w_pipe, something.write_thread_hook, r_pipe)
something.add_timer_thread("Timer", 100, something.timer_thread_hook, (r_pipe,w_pipe))
something.threads_run();
os.close(r_pipe)
os.close(w_pipe)


The next examples demonstrate the use of the MyTask class. It allows starting pseudo threads inside real threads:


from kpseudothreads import MyTask 
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

$ ps afx | grep example
  21638 pts/0    S+     0:00  |   \_ python3 ./example4.py
  21639 pts/0    S+     0:00  |       \_ python3 ./example4.py



This is server/client inside real threads:

from kpseudothreads import MyTask 
from kpseudothreads import KPseudoThreads 
import os
import time

class Client(MyTask):
    def __init__(self, pipes):
        self.pipes = pipes
        MyTask.__init__(self)
        
    def task_pre_run_hook(self):
        self.pipe = self.pipes[1]
        os.close(self.pipes[0])
        self.add_write_thread("Write", self.pipe, self.client_write_hook, None)

    def client_write_hook(self, thr, arg):
        print ("Sending on ..", thr.socket)
        try:
            s = os.write(thr.socket, b"Something")
        except:
            s = None
        if not s:
            print ("Client close", thr.socket) 
            os.close(thr.socket)
            self.child_close_read_thread_from_parent()
            return
        self.add_write_thread("Write", thr.socket, self.client_write_hook, None)

class Server(MyTask):
    def __init__(self, pipes):
        self.pipes = pipes
        MyTask.__init__(self, log_facility=KPseudoThreads.LOG_CONSOLE, debug=True)
        
    def task_pre_run_hook(self):
        self.pipe = self.pipes[0]
        os.close(self.pipes[1])
        self.add_read_thread("Read", self.pipe, self.server_read_hook, None)
        self.add_timer_thread("Timer", 10, self.timer_thread_hook, self.pipe)
    
    def server_read_hook(self, thr, arg):
        data = os.read(thr.socket, 100)
        print ("Received", data)
        self.add_read_thread("Read", thr.socket, self.server_read_hook, None)

    def timer_thread_hook(self, thr, pipe):
        self.cancel_thread_by_sock(pipe)
        self.child_close_read_thread_from_parent()
        print ("Server close", pipe)
        os.close(pipe)

r_pipe,w_pipe = os.pipe()
print("Create Pipes", r_pipe,w_pipe )
print ("Starting server")
server = Server((r_pipe,w_pipe))
server.start();

print ("Starting Client")
client = Client((r_pipe,w_pipe))
client.start();

# close the pipes - they are duplicated when the threads are spawned
os.close(r_pipe)
os.close(w_pipe)

print ("Started. Now wait the clients to stop")
print (os.read(server.pipe_parent_from_child, 1024))
print (os.read(client.pipe_parent_from_child, 1024))


server.task_stop()
client.task_stop()


Api:

KPseudoThreads(name="", log_level=LOG_ERR, log_facility=LOG_NOLOG, debug=None)

Log(self, prio, msg):
add_read_thread(self, name, socket, function, args):
add_read_thread(self, name, socket, function, args):
add_timer_thread(self, name, after_ms, function, args):
add_execute_thread(self, name, function, args):
cancel_thread(self, thread):
cancel_thread_by_sock(self, sock):
threads_stop(self):
threads_dump(self, msg):
threads_run(self):



MyTask(self, task_name="", log_level=KPseudoThreads.LOG_ERR, log_facility=KPseudoThreads.LOG_NOLOG, debug=None):
def send_msg_2_child(self, msg):
def task_stop(self):
def add_hook_for_msgs_from_child_(self, parent, function): 


def child_close_read_thread_from_parent(self):
def task_pre_run_hook(self):
def child_pre_stop_hook(self):
def child_process_msg_from_parent_hook(self, msg):
def child_send_msg_to_parent(self, msg=""):


Internals:

KPseudoThreads - 
MyTask


![alt text](http://url/to/img.png)