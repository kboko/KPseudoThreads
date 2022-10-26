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
            
class MyPseudoEpollMirror():
    def __init__(self):
        self.epoll_bits_new = 0
        self.epoll_bits_old = 0


class MyPseudoThread():
    READ = 0
    WRITE = 1
    EXEC = 2
    TIMER = 3
    def __init__(self, thread_name, thread_type, fd, function, args, time = None):
        self.thread_type = thread_type
        self.thread_name = thread_name
        self.fd = fd
        self.args = args
        self.time = time
        self.function = function
        self.to_delete = False
        self.just_added = True
    def __cmp__(self, other):
        return self.time - b.time
    def __lt__(self, b):
        return self.time < b.time

    
class MyPseudoThreads(Logging): 

    def __init__(self, name, log_level, log_facility, debug=None):
        self.mpt_name = name
        self.stop=False

        # this is a list with MyPseudoEpollThread objects
        self.threads_read = {}
        self.threads_write = {}
        
        # for the timer threads is used heapq
        self.threads_timer=[]

        # exec threads are executed in sorted order - we use deque
        # we need to have 
        self.threads_exec = collections.deque()

        self.debug = debug
        self.epoll = select.epoll()
        self.epoll_mirror = {}
        Logging.__init__(self, name, log_level, log_facility)

        self.Log(LOG_DBG, "Create threads {}".format(hex(id(self)))) 
    
    def update_epoll_mirror(self, thread):
        if thread.fd in self.epoll_mirror:
            e = self.epoll_mirror[thread.fd] 
        else:
            e = MyPseudoEpollMirror()
            self.epoll_mirror[thread.fd] = e
        
        if thread.thread_type == MyPseudoThread.READ:
            if thread.to_delete == True:
                e.epoll_bits_new &= ~select.EPOLLIN
            else:
                e.epoll_bits_new |= select.EPOLLIN
        elif thread.thread_type == MyPseudoThread.WRITE:
            if thread.to_delete == True:
                e.epoll_bits_new &= ~select.EPOLLOUT
            else:
                e.epoll_bits_new |= select.EPOLLOUT
        if self.debug: self.Log(LOG_DBG,"{}: Epoll Flags for fd {}, thread {} type {} = {} to_del = {}".format(self.mpt_name, thread.fd, hex(id(thread)), "R" if thread.thread_type == MyPseudoThread.READ else "W", e.epoll_bits_new, thread.to_delete))
            

    def add_read_thread(self, name, socket, function, args):
        fd = socket.fileno()
        if fd in self.threads_read:
            e = self.threads_read[fd]
            if e.to_delete == False:
                if self.debug: self.Log(LOG_ERR,"{}: Read Thread exists for this fd {}".format(self.mpt_name, fd))
                return None
            else:# reuse
                e.function = function
                e.args = args
                e.name = name
                e.to_delete = False
                if self.debug: self.Log(LOG_ERR,"{}: Reuse {} Read Thread for fd {} {} to_del {}".format(self.mpt_name, hex(id(e)), fd, function.__name__, e.to_delete))
                self.update_epoll_mirror(e)
                return e
        e = MyPseudoThread(name, MyPseudoThread.READ, fd, function, args)
        self.threads_read[fd] = e
        if self.debug: self.Log(LOG_ERR,"{}: Add new {} Read Thread for fd {} {}".format(self.mpt_name, hex(id(e)), fd, function.__name__))
        self.update_epoll_mirror(e)
        return e
        
    def add_write_thread(self,name, socket, function, args):
        fd = socket.fileno()
        if fd in self.threads_write:
            e = self.threads_write[fd]
            if e.to_delete == False:
                if self.debug: self.Log(LOG_ERR,"{}: Write Thread exists for this fd {}".format(self.mpt_name, fd))
                return None
            else:# reuse
                e.function = function
                e.args = args
                e.name = name
                e.to_delete = False
                if self.debug: self.Log(LOG_ERR,"{}: Reuse Write Thread for fd {} {}".format(self.mpt_name, fd, function.__name__))
                self.update_epoll_mirror(e)
                return e
        if self.debug: self.Log(LOG_ERR,"{}: Add Write Thread for fd {} {}".format(self.mpt_name, fd, function.__name__))
        e = MyPseudoThread(name, MyPseudoThread.WRITE, fd, function, args)
        self.threads_write[fd] = e
        self.update_epoll_mirror(e)
        return e

    def add_timer_thread(self, name, after_ms, function, args):
        #return None
        when = time.time_ns() + after_ms * 1000000
        
        new_thread = MyPseudoThread(name, MyPseudoThread.TIMER, None, function, args, when)

        heapq.heappush(self.threads_timer, new_thread)

        if self.debug: self.Log(LOG_DBG,"{}: Adding t-thread {} AFTER=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),after_ms, name, function.__name__, args, hex(id(self))))
        return new_thread
    
    def add_execute_thread(self, name, function, args):
        
        new_thread = MyPseudoThread(name, MyPseudoThread.EXEC, None, function, args)

        self.threads_exec.append(new_thread)
        if self.debug: self.Log(LOG_DBG,"{}: Adding ex-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)), name, function.__name__, args, hex(id(self))))
        return new_thread
    
    """ Set the tread as pending delete, and set flad to update the lists
    """
    def cancel_thread(self, thread):
        if self.debug: self.Log(LOG_DBG,"{}: Cancel thread {} \"{}\" FUNC=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(thread)), thread.thread_name, thread.function.__name__, hex(id(self))))
        thread.to_delete = True
        self.update_epoll_mirror(thread)
        if thread.thread_type == MyPseudoThread.READ:
            del self.threads_read[thread.fd]
        if thread.thread_type == MyPseudoThread.WRITE:            
            del self.threads_write[thread.fd]
        
        return
    
    """This can cancel only read or write threads"""   
    def cancel_thread_by_sock(self, sock):
        
        if sock in self.threads_read:
            if self.debug: self.Log(LOG_DBG,"{}: Cancel thread {} \"{}\" FUNC=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(thread)), thread.thread_name, thread.function.__name__, hex(id(self))))
            e = self.threads_read[sock]
            e.to_delete = True
            self.update_epoll_mirror(e)
        
        if sock in self.threads_write:
            if self.debug: self.Log(LOG_DBG,"{}: Cancel thread {} \"{}\" FUNC=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(thread)), thread.thread_name, thread.function.__name__, hex(id(self))))
            e = self.threads_write[sock]
            e.to_delete = True
            self.update_epoll_mirror(e)
            

    def threads_stop(self):
        self.stop=True    
    
    def threads_dump(self, msg):
        
        self.Log(LOG_DBG,"DUMP Threads " + msg)
        
        for e in self.threads_read:
            if hasattr(e.fd, 'closed'):
                self.Log(LOG_DBG,"{}: R {} Sock {} func {} todel {}".format (self.mpt_name,hex(id(e)), e.fd, er.function.__name__, e.to_delete))
        
        for e in self.threads_write:
            if hasattr(e.fd, 'closed'):
                self.Log(LOG_DBG,"{}: W {} Sock {} func {} todel {}".format (self.mpt_name,hex(id(e)), e.fd, e.function.__name__, e.to_delete))
          
        for e in self.threads_timer:    
            if hasattr(e.fd, 'closed'):
                self.Log(LOG_DBG, "{}: T {} Sock {} time {} func {} todel {}".format (self.mpt_name, hex(id(e)), e.fd, e.time , e.function.__name__, e.to_delete))
        
        self.Log(LOG_DBG, "DUMP Threads END")    
        
        
    def threads_run(self):
        if self.debug: self.Log(LOG_DBG, "{}: RUN threads for {}".format (self.mpt_name, hex(id(self))))
        while self.stop != True:
            
            """ handle events
                We pop the first element, execute it untill all elements are executed.
                If thread is inactive - do nothing.
                as in exec function may be added new exec thread - we stop untill the first 
                such thread is seen
            """
            while True:
                try:
                    e = self.threads_exec.popleft()
                except:
                    break
                if e.to_delete == True:
                    continue
                # we reach thread that was just added from any other e.function() - so we stop executing them
                if e.just_added == True:
                    e.just_added = False
                else:
                    if self.debug: self.Log(LOG_DBG,"{}: Run exec-thr {} {}".format(self.mpt_name, e.function.__name__, hex(id(e))))
                    e.function(e.args)
            
            if not self.threads_timer and not self.threads_read and not self.threads_write:
                if self.debug: self.Log(LOG_DBG,"{}: No threads to add - exiting", self.mpt_name)
                break

            delete_list = []
            for sock, mirror in self.epoll_mirror.items():  
                try:
                    if mirror.epoll_bits_old == 0:
                        if self.debug: self.Log(LOG_ERR,"{}: Epoll Register fd={} Flags={}".format(self.mpt_name, sock, mirror.epoll_bits_new))
                        self.epoll.register(sock, mirror.epoll_bits_new)
                    elif mirror.epoll_bits_new == 0:
                        if self.debug: self.Log(LOG_ERR,"{}: Epoll UnRegister fd {} ".format(self.mpt_name, sock))
                        self.epoll.unregister(sock)
                        delete_list.append(sock)
                    else:
                        if self.debug: self.Log(LOG_ERR,"{}: Epoll Register fd={} Flags={}".format(self.mpt_name, sock, mirror.epoll_bits_new))
                        self.epoll.modify(sock, mirror.epoll_bits_new)
                except:
                    raise
                mirror.epoll_bits_old = mirror.epoll_bits_new
            for s in delete_list:
                if self.debug: self.Log(LOG_ERR,"{}: Epoll Delete EpollStruct fd {}".format(self.mpt_name, s))
                del self.epoll_mirror[s]

            time_out = None        
            # check if we have invalid timer at begining and remove them
            while self.threads_timer:
                if self.threads_timer[0].to_delete == True:
                    heapq.heappop(self.threads_timer)
                    continue
                else:
                    now = time.time_ns()
                    e_time = self.threads_timer[0].time
                    time_out = (e_time - now)/1000000000
                    if time_out < 0:
                        time_out = 0
                    break
                    """ self.Log(LOG_DBG,"SELECT {} {} {} TIME {}".format ([t.fileno() for t in inputs], [t.fileno() for t in outputs], (e_time - now)/1000))"""
            
            try:
                events = self.epoll.poll(time_out)
            except Exception as msg:
                self.Log(LOG_ERR, str(msg))
                raise
            for fd, event in events:
                if fd in self.threads_write:
                    e = self.threads_write[fd]
                    if e.to_delete == False and (event & (select.EPOLLOUT| select.EPOLLERR | select.EPOLLHUP)):
                        if self.debug: self.Log(LOG_DBG,"{}: Run w-thr {} {}".format(self.mpt_name, e.function.__name__, hex(id(e))))
                        e.to_delete = True
                        self.update_epoll_mirror(e)
                        e.function(e, e.args)
                        if e.to_delete == True:
                            if self.debug: self.Log(LOG_DBG,"{}: Delete w-thr {} {}".format(self.mpt_name, e.function.__name__, hex(id(e))))
                            del self.threads_write[e.fd]
                
                if fd in self.threads_read:
                    e = self.threads_read[fd]
                    if e.to_delete == False and (event & (select.EPOLLIN | select.EPOLLPRI | select.EPOLLERR | select.EPOLLHUP) ):
                        if self.debug: self.Log(LOG_DBG,"{}: Run r-thr {} {}".format(self.mpt_name, e.function.__name__, hex(id(e))))
                        e.to_delete = True
                        self.update_epoll_mirror(e)
                        e.function(e, e.args)
                        if e.to_delete == True:
                            if self.debug: self.Log(LOG_DBG,"{}: Delete r-thr {} {}".format(self.mpt_name, e.function.__name__, hex(id(e))))
                            del self.threads_read[e.fd]

            now = None
            # we need always to check those timers
            while self.threads_timer:
                e = self.threads_timer[0]
                # handle late threads
                if e.to_delete == True:
                    heapq.heappop(self.threads_timer)
                    continue
                #thread is in the future or now is not taken - update now   
                # the previour thread may have taken so much time, that the next is now to be executed
                if now == None or now < e.time:
                    now = time.time_ns()
                if (now >= e.time ):
                    if self.debug: self.Log(LOG_DBG,"{}: Run t-thr {} {}".format(self.mpt_name, e.function.__name__,  hex(id(e))))
                    heapq.heappop(self.threads_timer)
                    e.function(e, e.args)
                else:
                    break

            """
            if True:
                now = time.time_ns() * 1000 
                self.Log(LOG_DBG,"DUMP END R{} W{} E{} TIMER {}".format ([hex(id(t)) for t in self.threads_read] , [fd for t in self.threads_write], [fd for t in self.threads_exec], [t.time-now for t in self.threads_timer]))"""


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
This function is only used if the Parent is MyPseudoThreads. If not the Parent 
must imprement processing the messages from the pipe "pipe_parent_from_child" or close
this pipe

The Child:

Implements the follwing functions

child_started_hook - here is init work done - user may add read/timer/write threads, open sockets etc.
child_send_msg_to_parent - send messages to the Parent
child_pre_stop_hook - called when no threads exists and the client is going to stop
child_process_msg_from_parent_hook  messages from the parent are processed here


"""
           
class MyTask (MyPseudoThreads, threading.Thread):
    # Client is ending
    MY_C_END = b"\x01" 
    # Parent asks the child to stop
    MY_T_STOP = b"\x02"
    # User defined messages
    MY_T_USER = b"\x03"

    # INIT functions:
    def __init__(self, task_name, log_level, log_facility, debug=None):
        super(MyTask, self).__init__(thread_name, log_level, log_facility, debug)
        self.task_name = task_name
        self.debug = debug
        self.from_child_hook = None
        #two pipes for communication
        self.pipe_parent_to_child, self.pipe_child_from_parent = Pipe()
        self.pipe_child_to_parent, self.pipe_parent_from_child = Pipe()
        if self.debug: 
            self.Log(LOG_DBG, "{}: Created. Pipes Parent{}->Child{} Child{}->Parent{}".format(self.task_name, hex(id(self)) ,self.pipe_parent_to_child.fileno(), \
                        self.pipe_child_from_parent.fileno(), self.pipe_child_to_parent.fileno(), self.pipe_parent_from_child.fileno()))
        self.setDaemon(True)
    
    # FUNCTIONS CALLED FROM PARENT CONTEXT
    def _internal_msg_from_child(self, parent):
        msg = None
        try:
            msg = self.pipe_parent_from_child.recv()
        except:
            pass

        if not msg or msg == MyTask.MY_C_END:
            self.join()
            if self.debug: self.Log(LOG_DBG, "{}: Child Ended. Close {} {}".format (self.task_name, self.pipe_parent_to_child, self.pipe_parent_from_child))
            self.pipe_parent_to_child.close()
            self.pipe_parent_from_child.close()
        
        if msg and self.from_child_hook:
            self.from_child_hook(msg[1:s])
        
        if msg and msg != MyTask.MY_C_END:
            # add read thread again
            parent.add_read_thread (self.task_name, self.pipe_parent_from_child, self._int_msg_from_child, parent)

    # Parent use those below:        
    
    """ send_msg_2_child - The Parent can send data to the child"""
    def send_msg_2_child(self, msg):
        if self.debug: self.Log(LOG_DBG, "{}: {} msg_to_child {}".format (self.task_name, hex(id(self)), msg))
        return self.pipe_parent_to_child.send(MyTask.MY_T_USER + msg)
    
    """ send notification to the child to stop"""
    def task_stop(self):
        self.msg_to_child(MyTask.MY_T_STOP)
    
    # if Parent is MyPseudoThreads - add thread to process msgs from child
    def add_hook_for_msgs_from_child_(self, parent, function): 
        self.from_child_hook = function
        parent.add_read_thread (self.task_name, self.pipe_parent_from_child, self._internal_msg_from_child, parent)
        pass
    



    # FUNCTIONS CALLED INSIDE CHILD CONTEXT
    def run(self):
        if self.debug: 
            if self.debug: self.Log(LOG_DBG,"{}: Started".format(self.task_name,  hex(id(self))))
        
    def task_post_start(self):
        pass   

        # this thread is for messages from the Parent
        msg_from_parent_thread = self.add_read_thread ("{}: {}: MSG_from_parent", self.task_name, self.pipe_child_from_parent, self._internal_msg_from_parent, self)
        
        self.threads_run();

        self.child_pre_stop_hook()
        if self.debug: self.Log("{}: {} closing {} {}".format(self.task_name, hex(id(self)), self.pipe_child_to_parent.fileno(), self.pipe_child_from_parent.fileno()))

        # send the MSG and close
        self.msg_to_parent(MyTask.MY_C_END)
        self.pipe_child_to_parent.close()
        
        """No threads anymore"""
        self.cancel_thread (msg_from_parent_thread)
        self.pipe_child_from_parent.close()

        if self.debug: self.Log("{}: {} ended".format(self.task_name, hex(id(self))))

    def _internal_msg_from_parent(self, arg):
        stop = False
        msg = self.pipe_child_from_parent.recv()
        # call child funciton
        if self.child_process_msg_from_parent_hook (msg) == MyTask.MY_T_STOP or msg == MyTask.MY_T_STOP:
            self.threads_stop()
            if self.debug: self.Log("{}: Stopping Child", self.task_name,)
        else:
            # add read thread again
            self.add_read_thread ("pipe_child_from_parent", self.pipe_child_from_parent, self._internal_msg_from_parent, self)

    # Virtual functons
    def child_started_hook(self):
        if self.debug: self.Log(LOG_DBG,"{}: child_started_hook - Implement me".format(self.task_name))
        pass   
           
    def child_pre_stop_hook(self):
        if self.debug: self.Log(LOG_DBG,"{}: child_pre_stop_hook - Implement me".format(self.task_name))
        pass 
        
    def child_process_msg_from_parent_hook(self, msg):
        if self.debug: self.Log(LOG_DBG,"{}: child_process_msg_from_parent_hook- Implement me".format(self.task_name))
        pass       
    
    def child_send_msg_to_parent(self, msg):
        return self.pipe_child_to_parent.send( MY_T_USER + msg)