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
            self.child_cancel_read_thread_from_parent()
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
        self.add_timer_thread("Timer", 1000, self.timer_thread_hook, self.pipe)
    
    def server_read_hook(self, thr, arg):
        data = os.read(thr.socket, 100)
        print ("Received", data)
        self.add_read_thread("Read", thr.socket, self.server_read_hook, None)

    def timer_thread_hook(self, thr, pipe):
        self.cancel_thread_by_sock(pipe)
        self.child_cancel_read_thread_from_parent()
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
