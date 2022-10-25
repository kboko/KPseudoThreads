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
import bisect
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
            
class MyPseudoEpollThread():
    EPOLL_ADD = 0
    EPOLL_MOD = 1
    EPOLL_DEL = 2
    EPOLL_USE = 3
    def __init__(self, socket):
        self.socket = socket
        self.epoll_flag = MyPseudoEpollThread.EPOLL_ADD
        self.r_thr = None
        self.w_thr = None
    def add_thread(self,)
    def del_thread(self,)


class MyPseudoThread():
    READ = 0
    WRITE = 0
    EXEC = 0
    TIMER = 0
    def __init__(self, thread_name, thread_type, socket, function, args, time = None):
        self.thread_type = thread_type
        self.thread_name = thread_name
        self.socket = socket
        self.args = args
        self.time = time
        self.function = function
        self.to_delete = False

    def __lt__(self, b):
        return self.time < b.time

    
class MyPseudoThreads(Logging): 

    def __init__(self, name, log_level, log_facility, debug=None):
        self.mpt_name = name
        self.stop=False
        self.threads_read_write=[]
        self.threads_read_write_changed = False

        self.threads_timer=[]
        self.threads_timer_changed=False

        self.threads_exec=[]
        self.threads_exec_changed=False


        self.debug = debug
        self.epoll = select.epoll()
        Logging.__init__(self, name, log_level, log_facility)

        self.Log(LOG_DBG, "Create threads {}".format(hex(id(self)))) 
    
    def add_read_thread(self, name, socket, function, args):
        
        for rw_thread in self.threads_read_write:
            if socket != rw_thread.socket:
                continue

            if rw_thread.r_thr:
                if r_thr.to_delete != True:
                    self.Log(LOG_DBG,"Thread Exists")
                    return None
                else:# reuse
                    r_thr.thread_name = name
                    r_thr.function = function
                    r_thr.args = args
                    r_thr.to_delete = False
                    # we need to add it to epoll
                    r_thr.epoll_flag = MyPseudoThreads.EPOLL_ADD
                    if self.debug: self.Log(LOG_DBG, "{}: Reuse r-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),socket.fileno(), name, function.__name__, args, hex(id(self))))
                    self.threads_read_write_changed = True
                    return r_thr
            else: # we have no r_thr - so create one
                new_thread = MyPseudoThread(name, MyPseudoThread.READ, socket, function, args)
                rw_threads[1] = new_thread
                if self.debug: self.Log(LOG_DBG, "{}: Adding r-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),socket.fileno(), name, function.__name__, args, hex(id(self))))
                self.threads_read_write_changed = True
                return new_thread           
        new_thread = MyPseudoThread(name, MyPseudoThread.READ, socket, function, args)
        self.threads_read.append([socket, new_thread, None])
        if self.debug: self.Log(LOG_DBG, "{}: Adding r-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),socket.fileno(), name, function.__name__, args, hex(id(self))))
        self.threads_read_write_changed = True
        return new_thread

    def update_read_thread(self, name, function, args):
        
        item.thread_name = name
        item.function = function
        item.args = args
        item.to_delete = False
        if self.debug: self.Log(LOG_DBG, "{}: Reuse r-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),socket.fileno(), name, function.__name__, args, hex(id(self))))
        return item
    
    def add_write_thread(self,name, socket, function, args):

        for rw_threads in self.threads_read_write:
            sock, r_thr, w_thr = rw_threads
            
            if sock != socket:
                continue

            if w_thr:
                if w_thr.to_delete != True:
                    self.Log(LOG_DBG,"Thread Exists")
                    return None
                else:# reuse
                    w_thr.thread_name = name
                    w_thr.function = function
                    w_thr.args = args
                    w_thr.to_delete = False
                    # we need to add it to epoll
                    w_thr.epoll_flag = MyPseudoThreads.EPOLL_ADD
                    if self.debug: self.Log(LOG_DBG, "{}: Reuse w-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),socket.fileno(), name, function.__name__, args, hex(id(self))))
                    self.threads_read_write_changed = True
                    return w_thr
            else: # we have no w_thr - so create one
                new_thread = MyPseudoThread(name, MyPseudoThread.WRITE, socket, function, args)
                rw_threads[2] = new_thread
                if self.debug: self.Log(LOG_DBG, "{}: Adding w-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),socket.fileno(), name, function.__name__, args, hex(id(self))))
                self.threads_read_write_changed = True
                return new_thread           
        new_thread = MyPseudoThread(name, MyPseudoThread.WRITE, socket, function, args)
        self.threads_read.append([socket, None, new_thread])
        if self.debug: self.Log(LOG_DBG, "{}: Adding w-thread {} FD=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),socket.fileno(), name, function.__name__, args, hex(id(self))))
        self.threads_read_write_changed = True
        return new_thread
        
    def add_timer_thread(self, name, after_ms, function, args):
        #return None
        when = time.time_ns() + after_ms * 1000000
        
        new_thread = MyPseudoThread(name, MyPseudoThread.TIMER, None, function, args, when)
        
        bisect.insort(self.threads_timer, new_thread) 

        #self.threads_timer.append(new_thread)
        #self.threads_timer = sorted(self.threads_timer, key=lambda t: t.time) 
        self.threads_timer_changed = True
        
        if self.debug: self.Log(LOG_DBG,"{}: Adding t-thread {} AFTER=\"{}\" \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)),after_ms, name, function.__name__, args, hex(id(self))))
        return new_thread
        
    def add_execute_thread(self, name, function, args):
        
        new_thread = MyPseudoThread(name, MyPseudoThread.EXEC, None, function, args)
        self.threads_exec.append(new_thread)
        if self.debug: self.Log(LOG_DBG,"{}: Adding ex-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(new_thread)), name, function.__name__, args, hex(id(self))))
        return new_thread
    
    def cancel_thread(self, thread):
        thread.to_delete = True
        thread.epoll_flag = MyPseudoThreads.EPOLL_DEL
        
        if thread == MyPseudoThread.READ or thread == MyPseudoThread.WRITE:
            self.threads_read_write_changed = True
        
        if thread == MyPseudoThread.TIMER:
            self.threads_timer_changed = True

        if thread == MyPseudoThread.TIMER:
            self.threads_exec_changed = True
        
        if self.debug: self.Log(LOG_DBG,"{}: Cancel r-thread {} \"{}\" FUNC=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(thread)), thread.thread_name, thread.function.__name__, hex(id(self))))
        return
            
    def cancel_thread_by_sock(self, sock):
        for rw_threads in self.threads_read_write:
            sock, r_thr, w_thr = rw_threads
            
            if sock != socket:
                continue
            if r_thr:
                r_thr.to_delete = True
                r_thr.epoll_flag = MyPseudoThreads.EPOLL_DEL
                if self.debug: self.Log(LOG_DBG,"{}: Cancel r-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(r_thr)),r_thr.thread_name, r_thre.function.__name__, r_thr.args, hex(id(self))))
                self.threads_read_write_changed = True
            if w_thr:
                w_thr.to_delete = True
                w_thr.epoll_flag = MyPseudoThreads.EPOLL_DEL
                if self.debug: self.Log(LOG_DBG,"{}: Cancel w-thread {} \"{}\" FUNC=\"{}\" ARGS=\"{}\" TASK=\"{}\"".format(self.mpt_name, hex(id(w_thr)),w_thr.thread_name, w_thr.function.__name__, w_thr.args, hex(id(self))))
                self.threads_read_write_changed = True
                
            
        
    def threads_stop(self):
        self.stop=True    
    
    def threads_dump(self, msg):
        self.Log(LOG_DBG,"DUMP Threads " + msg)
        for s,r,w in self.threads_read_write:
            if hasattr(e.socket, 'closed'):
                if r:
                    self.Log(LOG_DBG,"{}: W {} Sock {} closed {} func {} todel {}".format (self.mpt_name,hex(id(r)), r.socket, r.socket.closed ,   r.function.__name__, r.to_delete))
                if w:                    
                    self.Log(LOG_DBG,"{}: W {} Sock {} closed {} func {} todel {}".format (self.mpt_name,hex(id(w)), w.socket, w.socket.closed ,   w.function.__name__, w.to_delete))
          
        for e in self.threads_timer:    
            if hasattr(e.socket, 'closed'):
                self.Log(LOG_DBG, "{}: T {} Sock {} closed {} time {} func {} todel {}".format (self.mpt_name, hex(id(e)), e.socket, e.socket.closed ,  e.time , e.function.__name__, e.to_delete))
        self.Log(LOG_DBG, "DUMP Threads END")    
        
        
    def threads_run(self):
        if self.debug: self.Log(LOG_DBG, "{}: RUN threads for {}".format (self.mpt_name, hex(id(self))))
        while self.stop != True:
            
            # handle events
            for e in self.threads_exec:
                if self.debug: self.Log(LOG_DBG,"{}: Run exec-thr {} {}".format(self.mpt_name, e.function.__name__, hex(id(e))))
                e.function(e.args)
            self.threads_exec=[]
            
            # soeckt events
           
            
            for s, r, w in self.threads_read_write:
                flags = 0
                if r:
                    flags = flags | select.EPOLLIN
                if w:
                    flags = flags | select.EPOLLOUT
                if r.epoll_flag == MyPseudoThreads.EPOLL_ADD
                try:
                    self.epoll.register(e.socket, flags)
                except:
                    raise
            
            if len(self.threads_timer) == 0 and len(self.threads_write) == 0 and len(self.threads_read) == 0:
                if self.debug: self.Log(LOG_DBG,"{}: No threads to add - exiting".format (self.mpt_name))
                break
            
            if (len(self.threads_timer)):
                now = time.time_ns()
                e_time = self.threads_timer[0].time
                time_out = (e_time - now)/1000000000
                if time_out < 0:
                    time_out = 0
                """ self.Log(LOG_DBG,"SELECT {} {} {} TIME {}".format ([t.fileno() for t in inputs], [t.fileno() for t in outputs], (e_time - now)/1000))"""
            else:
                time_out = None

            try:
                events = self.epoll.poll(time_out)
            except Exception as msg:
                self.Log(LOG_ERR, str(msg))
                raise
            
            writable_changed = False               
            readable_changed = False
            timer_changed = False
            for socket, event in events:
                if event & (select.EPOLLOUT| select.EPOLLERR | select.EPOLLHUP):
                    for e in self.threads_write:
                        if e.socket == socket and e.to_delete != True:
                            if self.debug: self.Log(LOG_DBG,"{}: Run w-thr {} {}".format(self.mpt_name,e.function.__name__, hex(id(e))))
                            e.to_delete = True
                            writable_changed = True
                            e.function(e, e.args)
                            if self.debug: self.Log(LOG_DBG,"{}: After w-thr {} {} TODEL".format(self.mpt_name, e.function.__name__, hex(id(e))))
                            """in case the thread add new read thread for same socket
                            we make cancel as we do not want read thread to be executed twice
                            """
                            break
                if event & (select.EPOLLIN | select.EPOLLPRI | select.EPOLLERR | select.EPOLLHUP):
                    for e in self.threads_read:
                        if e.socket == socket and e.to_delete != True:
                            if self.debug: self.Log(LOG_DBG,"{}: Run r-thr {} {}".format(self.mpt_name, e.function.__name__,  hex(id(e))))
                            e.to_delete = True
                            readable_changed = True
                            e.function(e, e.args)
                            if self.debug: self.Log(LOG_DBG,"{}: After Run r-thr {} {} TODEL".format(self.mpt_name, e.function.__name__,  hex(id(e))))
                            break
            #always check for timers in case the read function took too much time and some timer may have fired
            timer_changed = False
            now = None
            if len (self.threads_timer):
                # handle late threads
                for e in self.threads_timer:
                    if e.to_delete == True:
                        continue
                    #thread is in the future or now is not taken - update now   
                    # the previour thread may have taken so much time, that the next is now to be executed
                    if now == None or now < e.time:
                        now = time.time_ns()
                    if (now >= e.time ):
                        if self.debug: self.Log(LOG_DBG,"{}: Run t-thr {} {}".format(self.mpt_name, e.function.__name__,  hex(id(e))))
                        e.to_delete = True
                        timer_changed = True
                        e.function(e, e.args)
                    else:
                        break

            if writable_changed:
                self.threads_read  = [item for item in self.threads_read  if item.to_delete != True]
            if readable_changed:
                self.threads_write = [item for item in self.threads_write if item.to_delete != True]
            if timer_changed:
                self.threads_timer = [item for item in self.threads_timer if item.to_delete != True]
            """
            if True:
                now = time.time_ns() * 1000 
                self.Log(LOG_DBG,"DUMP END R{} W{} E{} TIMER {}".format ([hex(id(t)) for t in self.threads_read] , [t.socket.fileno() for t in self.threads_write], [t.socket.fileno() for t in self.threads_exec], [t.time-now for t in self.threads_timer]))"""


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