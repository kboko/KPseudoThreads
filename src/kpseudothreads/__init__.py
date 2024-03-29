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
import heapq
import collections
import datetime
import select
import os
import time
import fcntl
from threading import Thread
from multiprocessing import Process
from multiprocessing import Pipe

try:
    from systemd import journal
    g_journal = True
except:
    g_journal = False

try:
    from time import time_ns
    g_has_time_ns = True
except:
    g_has_time_ns = False

""" This class stores the thread's data
    socket is only for read and write relevanr
    time only for timer threads
    to_delete has special meaning - if a thread is
    inactive and schedulet for deletion - this var is true
"""
class KPseudoThread():
    READ = 0
    WRITE = 1
    EXEC = 2
    TIMER = 3
    def __init__(self, parent, thread_name, thread_type, socket, function, args, time = None):
        self.thread_name = thread_name
        self.thread_type = thread_type
        self.socket = socket
        self.args = args
        self.time = time
        self.function = function
        self.to_delete = False
        self.parent = parent
    def __cmp__(self, b):
        return self.time - b.time
    def __lt__(self, b):
        return self.time < b.time

"""
    Main class used for threads - the user of the module
    inherits this class and may override some of the functions
    Has lists for the 4 types of threads (KPseudoThread objects) 
    and some variables for optimisation purposes
"""    
class KPseudoThreads(): 
    # those are the log levels
    LOG_CRIT=0
    LOG_ERR=1
    LOG_INFO=2
    LOG_DBG=3

    # where to log
    LOG_NOLOG=0
    LOG_CONSOLE=1
    LOG_SYSLOG =2

    def __init__(self, name="", log_level=LOG_ERR, log_facility=LOG_NOLOG, debug=None):
        
        self.mpt_name = name
        self.mpt_level = log_level
        self.mpt_facility = log_facility  
        self.mpt_debug = debug

        
        self.threads_stop_loop=False
        self.threads_read=[]
        self.threads_write=[]
        self.threads_timer=[]
        # optimisations - keep count of deleted threads
        self.deleted_read_threads = 0
        self.deleted_write_threads = 0
        # exec threads are executed in sorted order - we use deque
        # we need to have 
        self.threads_exec = collections.deque()

        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG, "Create threads {}".format(hex(id(self)))) 
    """ Used for logging, 
    prio is the priority, msg is the message"""
    def Log(self, prio, msg):
        if self.mpt_facility == KPseudoThreads.LOG_NOLOG: 
            return
        if prio > self.mpt_level:
            return 
        if self.mpt_facility & KPseudoThreads.LOG_CONSOLE:
            print ("{}.{}:{}".format (self.mpt_name, self.mpt_level, msg))
        if g_journal and self.mpt_facility & KPseudoThreads.LOG_SYSLOG:
            journal.send("{}.{}:{}".format (self.mpt_name, self.mpt_level, msg))
    """ this function registers a read thread
        name - the name of the thread
        socket - the file descriptor or socket on witch read is expected
        function - hook function to be executed if on the FD is ready for reading
        args - arguments passed to the hook function

        Returns an object of KPseudoThread

        If there is already Thread object marked to deletion, this function will reuse it
    """
    def add_read_thread(self, name, socket, function, args):
        
        for item in self.threads_read:
            if item.socket == socket:
                if item.to_delete != True:
                    if self.mpt_debug: self.Log(KPseudoThreads.LOG_ERR,"{}: Read Thread exists for this fd {}".format(self.mpt_name, socket))
                    return None
                else:# reuse
                    item.thread_name = name
                    item.function = function
                    item.args = args
                    item.to_delete = False
                    self.deleted_read_threads = self.deleted_read_threads - 1
                    if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG, "{}: Reuse r-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(item)),socket, name, function.__name__, args, hex(id(self))))
                    return item
        new_thread = KPseudoThread(self, name, KPseudoThread.READ, socket, function, args)
        self.threads_read.append(new_thread)
        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG, "{}: Adding r-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),socket, name, function.__name__, args, hex(id(self))))
        return new_thread
    """ This function registers a write thread
        name - the name of the thread
        socket - the file descriptor or socket on witch write is expected
        function - hook function to be executed if on the FD is ready for writing
        args - arguments passed to the hook function

        Returns an object of KPseudoThread

        If there is already Thread object marked to deletion, this function will reuse it
    """
    def add_write_thread(self,name, socket, function, args):
        
        for item in self.threads_write:
            if item.socket == socket:
                if item.to_delete != True:
                    if self.mpt_debug: self.Log(KPseudoThreads.LOG_ERR,"{}: Write Thread exists for this fd {}".format(self.mpt_name, socket))
                    return None
                else:
                    item.thread_name = name
                    item.function = function
                    item.args = args
                    item.to_delete = False
                    self.deleted_write_threads = self.deleted_write_threads - 1
                    if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Reuse w-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(item)), socket, name, function.__name__, args, hex(id(self))))
                    return item
        new_thread = KPseudoThread(self, name, KPseudoThread.WRITE, socket, function, args)
        self.threads_write.append(new_thread)
        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Adding w-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)), socket, name, function.__name__, args, hex(id(self))))
        return new_thread
    """  
        Register timer thread
        name - the name of the thread
        after_ms - when the thread should be executed - in ms
        function - hook function to be executed when the timeout elaps
        args - arguments passed to the hook function

        Returns an object of KPseudoThread
    """
    def add_timer_thread(self, name, after_ms, function, args):
        #return None
        if g_has_time_ns:
            when = time.time_ns() + after_ms * 1000000
        else:
            when = time.time()*1000000000 + after_ms * 1000000
        
        new_thread = KPseudoThread(self, name, KPseudoThread.TIMER, None, function, args, when)

        heapq.heappush(self.threads_timer, new_thread)

        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Adding t-thread {} AFTER=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),after_ms, name, function.__name__, args, hex(id(self))))
        return new_thread
    """  
        Register exec thread - functionality is same as thread with timeout 0
        However those threads are executed first.

        name - the name of the thread
        function - hook function to be executed when the timeout elaps
        args - arguments passed to the hook function
        
        Returns an object of KPseudoThread
    """   
    def add_execute_thread(self, name, function, args):
        
        new_thread = KPseudoThread(self, name, KPseudoThread.EXEC,  None, function, args)
        self.threads_exec.append(new_thread)
        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Adding ex-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)), name, function.__name__, args, hex(id(self))))
        return new_thread
    """ Cancels already scheduled thread
        Returns: None
    """
    def cancel_thread(self, thread):
        if thread.to_delete == True:
            return
        if thread.thread_type == KPseudoThread.READ:
            self.deleted_read_threads = self.deleted_read_threads + 1
        if thread.thread_type == KPseudoThread.WRITE:
            self.deleted_write_threads = self.deleted_write_threads + 1
        thread.to_delete = True
        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Cancel thread {} \"{}\" FUNC=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(thread)), thread.thread_name, thread.function.__name__, hex(id(self))))
        return
    """ 
        Cancels already scheduled threads for particular socket
        Returns: None
    """      
    def cancel_thread_by_sock(self, sock):
        for e in self.threads_read:
            if e.socket == sock:
                if e.to_delete == True:
                    break
                self.deleted_read_threads = self.deleted_read_threads + 1
                e.to_delete = True
                if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Cancel r-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(e)),e.thread_name, e.function.__name__, e.args, hex(id(self))))
                break                
        for e in self.threads_write:
            if e.socket == sock:
                if e.to_delete == True:
                    break
                self.deleted_write_threads = self.deleted_write_threads + 1
                e.to_delete = True
                if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Cancel w-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(e)),e.thread_name, e.function.__name__, e.args, hex(id(self))))
                break
    """
        This function cancels the infinity loop and causes return from threads_run() function.
    """       
        
    def threads_stop(self):
        self.threads_stop_loop=True    
    
    """
        Used for debugging
    """
    def threads_dump(self, msg):
        self.Log(KPseudoThreads.LOG_DBG,"DUMP Threads " + msg)
        for e in self.threads_write:
            self.Log(KPseudoThreads.LOG_DBG,"{}: W {} Sock {} closed {} func {} todel {}".format (self.mpt_name,hex(id(e)), e.socket, e.socket.closed ,   e.function.__name__, e.to_delete))
          
        for e in self.threads_read:
            self.Log(KPseudoThreads.LOG_DBG,"{}: R {} Sock {} closed {} func {} todel {}".format (self.mpt_name, hex(id(e)), e.socket, e.socket.closed ,    e.function.__name__, e.to_delete))
            
        for e in self.threads_timer:    
            self.Log(KPseudoThreads.LOG_DBG, "{}: T {} Sock {} closed {} time {} func {} todel {}".format (self.mpt_name, hex(id(e)), e.socket, e.socket.closed ,  e.time , e.function.__name__, e.to_delete))
        self.Log(KPseudoThreads.LOG_DBG, "DUMP Threads END")    
        
    """
        Main function of the module
        Implements infinity loop and process the events.   
        See comments inside
    """
    def threads_run(self):
        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG, "{}: RUN threads for {}".format (self.mpt_name, hex(id(self))))
        while self.threads_stop_loop != True:
            outputs = []
            inputs = []  

            """ handle events
                We pop the first element, execute it until all current elements are executed.
                If thread is inactive - do nothing.
                As in exec function may be added new exec thread - we do not execute the new one
                they will be executed on next iteration
            """
            i = 0
            max_len = len (self.threads_exec)
            while i < max_len:  
                try:
                    e = self.threads_exec.popleft()
                except:
                    break
                if e.to_delete == True:
                    continue
                if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Run exec-thr {} {}".format(self.mpt_name, e.function.__name__, hex(id(e))))
                e.function(e, e.args)

            # Fill the select writes
            for e in self.threads_write:
                if e.to_delete == False:
                    outputs.append(e.socket)    
            # Fill the select reads
            for e in self.threads_read:
                if e.to_delete == False:
                    inputs.append(e.socket)    

            # check if we have reach time to say goodbye
            if not self.threads_timer and not inputs and not outputs and not self.threads_exec:
                if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: No threads to add - exiting".format (self.mpt_name))
                break
            
            # process timers to calculate select timeout            
            # this is the first timer that should fire
            time_out = None        
            while self.threads_timer:
                # check if we have invalid timer at begining and remove them
                if self.threads_timer[0].to_delete == True:
                    heapq.heappop(self.threads_timer)
                    continue
                else:
                    if g_has_time_ns:
                        now = time.time_ns()
                    else:
                        now = int(time.time()*1000000000)
                    e_time = self.threads_timer[0].time
                    time_out = (e_time - now)/1000000000 
                    if time_out < 0:
                        time_out = 0
                    break
                    

            # now Main Part - do select
            try:
                readable, writable, exceptional = select.select(inputs, outputs, [], time_out)
            except Exception as msg:
                self.Log(KPseudoThreads.LOG_ERR, str(msg))
                raise

            #Check if we have some thint to WRITE
            if writable:
                for fd in writable:
                    llen = len(self.threads_write) 
                    i = 0 
                    """ we interate only untill the initial count of sockets
                        Inside the Hook is possible that a new socket is added - we do not want to process them
                    """
                    while i < llen:  
                        e = self.threads_write[i]
                        i = i + 1
                        if e.socket == fd and e.to_delete != True:
                            if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Run w-thr {} {}".format(self.mpt_name,e.function.__name__, hex(id(e))))
                            e.to_delete = True
                            e.function(e, e.args)
                            if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: After w-thr {} {} todel {}".format(self.mpt_name, e.function.__name__, hex(id(e)), e.to_delete))
                            
                            break

            #Check if we have some thint to READ
            if readable:
                #now read threads
                for fd in readable:
                    llen = len(self.threads_read)  
                    i = 0
                    """ we interate only untill the initial count of sockets
                        Inside the Hook is possible that a new socket is added - we do not want to process them
                    """
                    while i < llen:  
                        e = self.threads_read[i]
                        i = i + 1
                        if e.socket == fd and e.to_delete != True:
                            if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Run r-thr {} {}".format(self.mpt_name, e.function.__name__,  hex(id(e))))
                            e.to_delete = True
                            e.function(e, e.args)
                            if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: After Run r-thr {} {} todel {}".format(self.mpt_name, e.function.__name__,  hex(id(e)), e.to_delete))
                            break

            # we need always to check the timers
            now = None
            while self.threads_timer:
                e = self.threads_timer[0]
                # if any timer was canceld - we erase it
                if e.to_delete == True:
                    heapq.heappop(self.threads_timer)
                    continue
                # get the now time if not exist or update it in case
                # we reached in the loop a thread that must not be executed now, but later. 
                # since execution of the previous threads consume time - we update "now"
                if now == None or now < e.time:
                    if g_has_time_ns:
                        now = time.time_ns()
                    else:
                        now = int(time.time()*1000000000)
                # if thread is to be executed, else break
                if (now >= e.time ):
                    if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Run t-thr {} {}".format(self.mpt_name, e.function.__name__,  hex(id(e))))
                    heapq.heappop(self.threads_timer)
                    e.function(e, e.args)
                else:
                    break

            # carbage colector
            if self.deleted_read_threads:
                self.threads_read  = [item for item in self.threads_read  if item.to_delete != True]
                self.deleted_read_threads = 0
            if self.deleted_write_threads:
                self.threads_write = [item for item in self.threads_write if item.to_delete != True]
                self.deleted_write_threads = 0
            """
            if True:
                if g_has_time_ns:
                    now = time.time_ns()
                else:
                    now = time.time()*1000000000
                self.Log(KPseudoThreads.LOG_DBG,"DUMP END R{} W{} E{} TIMER {}".format ([hex(id(t)) for t in self.threads_read] , [t.socket. for t in self.threads_write], [t.socket.for t in self.threads_exec], [t.time-now for t in self.threads_timer]))"""


""" 
This Class starts PseudoThreads in real Thread
Note the functions are called in the Context of the Parent or the Child

Parent Uses:

- Create new Task
task = MyTask()

- sending messages to the Child Process 
task.send_msg_2_child(msg)

- ask the Child to stop
task.task_stop()

- add function to be called then a new message from the client is received.
task.add_hook_for_msgs_from_child_() 
This function is only used if the Parent is KPseudoThreads. If not the Parent 
must imprement processing the messages from the pipe "pipe_parent_from_child" or close
this pipe

The Child:

add_hook_for_msgs_from_parent - add hook for processing the messages from the parent

Implements the follwing functions

child_started_hook - here is init work done - user may add read/timer/write threads, open sockets etc.
child_send_msg_to_parent - send messages to the Parent
child_pre_stop_hook - called when no threads exists and the client is going to stop


To switch between Thread or Process ()
 see --> Use threading and uncommend the one and commenct the other
"""
# --> Use Threading: 
#class MyTask (KPseudoThreads, Thread):           
class MyTask (KPseudoThreads, Process):
    # Client is ending
    MY_C_END = b"\x01" 
    # Parent asks the child to stop
    MY_T_STOP = b"\x02"
    # User defined messages
    MY_T_USER = b"\x03"

    # INIT functions:
    def __init__(self, task_name="", log_level=KPseudoThreads.LOG_ERR, log_facility=KPseudoThreads.LOG_NOLOG, debug=None):
        # --> Use Threading: 
        #Thread.__init__(self)
        Process.__init__(self)
        KPseudoThreads.__init__(self, task_name, log_level, log_facility, debug)
        
        self.task_name = task_name
        self.mpt_debug = debug

        self.from_child_hook = None
        self.from_parent_hook = None

        #two pipes for communication
        self.pipe_child_from_parent, self.pipe_parent_to_child = os.pipe()
        self.pipe_parent_from_child, self.pipe_child_to_parent = os.pipe()

        if self.mpt_debug: 
            self.Log(KPseudoThreads.LOG_DBG, "{}: Created:{}. Pipes Parent{}->Child{} Child{}->Parent{}".format(self.task_name, hex(id(self)) ,self.pipe_parent_to_child, \
                        self.pipe_child_from_parent, self.pipe_child_to_parent, self.pipe_parent_from_child))
    """
        This funciton starts spawning - we are still in parent context
        We close the unised pipes (those are used from child - in childs context )
    """
    def start(self):
        super(MyTask, self).start()
        os.close(self.pipe_child_to_parent)
        os.close(self.pipe_child_from_parent)

    # FUNCTIONS CALLED FROM PARENT CONTEXT
    def __internal_msg_from_child(self, thread, parent):
        msg = None
        try:
            msg = os.read (self.pipe_parent_from_child, 1024)
        except:
            pass

        if not msg or msg == MyTask.MY_C_END:
            self.join()
            if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG, "{}: Child Ended. Close {} {}".format (self.task_name, self.pipe_parent_to_child, self.pipe_parent_from_child))
            os.close(self.pipe_parent_to_child)
            os.close(self.pipe_parent_from_child)
        
        if msg and self.from_child_hook:
            self.from_child_hook(msg[1:])
        
        if msg and msg != MyTask.MY_C_END:
            # add read thread again
            parent.add_read_thread (self.task_name, self.pipe_parent_from_child, self.__internal_msg_from_child, parent)

    # PARENT may USE whose:
    
    """ Used from Parent to send data to the child"""
    def send_msg_2_child(self, msg):
        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG, "{}: {} msg_to_child {}".format (self.task_name, hex(id(self)), msg))
        return os.write(self.pipe_parent_to_child, MyTask.MY_T_USER + msg)
    
    """ Send notification to the child to stop
        This function will actually send something, then the child will avake and process MY_T_STOP
        this breaks the infinity loop and child ends
    """
    def task_stop(self):
        try:
            self.send_msg_2_child(MyTask.MY_T_STOP)
        except:
            if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG, "{}: {} The child already finished".format (self.task_name, hex(id(self))))
            pass
    
    """ If Parent implements KPseudoThreads 
        this function will add thread to process msgs from child
    """
    def add_hook_for_msgs_from_child_(self, parent, function): 
        self.from_child_hook = function
        parent.add_read_thread (self.task_name, self.pipe_parent_from_child, self.__internal_msg_from_child, parent)
        pass


    # FUNCTIONS CALLED INSIDE CHILD CONTEXT
    """
        Used to cancel the thread that reads 
        messages from the parent. Note the client should close it before leave
    """
    def child_cancel_read_thread_from_parent(self):
        self.cancel_thread (self.msg_from_parent_thread)
    """
        This function is called in Child context
        It calls task_pre_run_hook hook()
        Then run the infinity loop
        If all done - calls child_pre_stop_hook()
        Sends message to the parent, that it will end 
        and do cleanup
    """
    def run(self):
        
        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: Started {}".format(self.task_name,  hex(id(self))))
        # this thread is for messages from the Parent
        self.msg_from_parent_thread = self.add_read_thread (self.task_name, self.pipe_child_from_parent, self.__child_internal_msg_from_parent, self)
        
        self.task_pre_run_hook()
        self.threads_run();
        self.child_pre_stop_hook()
        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG, "{}: {} closing {} {}".format(self.task_name, hex(id(self)), self.pipe_child_to_parent, self.pipe_child_from_parent))

        # send the MSG and close
        os.write(self.pipe_child_to_parent, MyTask.MY_C_END)
        
        os.close(self.pipe_child_to_parent)
        
        """No threads anymore"""
        os.close(self.pipe_child_from_parent)

        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG, "{}: {} ended".format(self.task_name, hex(id(self))))
    """ Internal function """
    def __child_internal_msg_from_parent(self, thread, arg):
        msg = os.read(self.pipe_child_from_parent,1024)
        # call child funciton
        if (self.from_parent_hook and self.from_parent_hook (msg[1:]) == MyTask.MY_T_STOP) or msg == MyTask.MY_T_STOP:
            self.threads_stop()
            if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG, "{}: Stopping Child".format (self.task_name))
        else:
            # add read thread again
            self.add_read_thread ("pipe_child_from_parent", self.pipe_child_from_parent, self.__child_internal_msg_from_parent, self)
    
    def child_send_msg_to_parent(self, msg=""):
        return os.write(self.pipe_child_to_parent, MyTask.MY_T_USER + msg)

    # Virtual functons
    """ Function called inside child's contect
        Used basicaly for adding some read/write/... threads before the infinity loop starts
    """
    def task_pre_run_hook(self):
        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: child_started_hook - Implement me".format(self.task_name))
        pass   
    """
        Function called inside child's context - should be used for some sort of actions before the child disappear
    """    
    def child_pre_stop_hook(self):
        if self.mpt_debug: self.Log(KPseudoThreads.LOG_DBG,"{}: child_pre_stop_hook - Implement me".format(self.task_name))
        pass 
    """
        Hook used inside child's contect to process messages comming from the parent
    """
    def add_hook_for_msgs_from_parent(self, function): 
        self.from_parent_hook = function
    
    
    
        
