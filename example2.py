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

from mypseudothreads import MyPseudoThreads 
import os
class SimpleTimerClass(MyPseudoThreads):
	
	def __init__(self):
		MyPseudoThreads.__init__(self)
		
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