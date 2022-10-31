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
from kpseudothreads import *
import traceback
import random 
import time
import socket
from datetime import datetime
"""
    This is the minimaliscit example - Server - Client
    Server have one open socket. client connectes and sends data, the 
    server reply.

    Starts client or server and send data
    Server:
        python3 Test2_ServerClient.py server
    client:
        python3 Test2_ServerClient.py 
    DISPLAY - show read/write thread executions
    Threads debug can be enabled - see KPseudoThreads constructor
    DATA_PORTION - this sets the data to be send, make it not so big, Use Test3 for bigger chunks

"""
DISPLAY=False

PORT=34455
DATA_PORTION = 1024
class Server(MyTask):
    
    def __init__(self):
        self.msg_size = DATA_PORTION
        self.conn = None
        self.addr = None
        MyTask.__init__(self, "ServerTask", KPseudoThreads.LOG_DBG, KPseudoThreads.LOG_CONSOLE, False)
        
    def task_pre_run_hook(self):
        for res in socket.getaddrinfo("127.0.0.1", PORT , socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
            af, socktype, proto, canonname, sa = res
            self.s = socket.socket(af, socktype, proto)
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.s.bind(sa)
            self.s.listen(1)
            self.s.setblocking(0)
            self.add_read_thread ("accept_client", self.s, self.accept_client, None)
            
    def accept_client(self, thread, arg):
        con, addr = self.s.accept()
        if self.conn and self.addr:
            con.send("Second Connection to 13000 is not allowed\n>")
            con.close()
            self.add_read_thread ("accept_client", self.s, self.accept_client, None)
            return
        self.conn = con
        self.addr = addr
        self.counter_read_all = 0
        self.counter_send_all = 0
        print ('Command thread connected by {}'.format (self.addr))

        
        self.write_buffer = bytearray(DATA_PORTION)
        for b in range(0, DATA_PORTION):
            self.write_buffer[b] = b%256
        self.timestamp = time.time_ns()
        self.add_read_thread ("read_from_client", self.conn, self.read_from_client, None)
        self.timer_thr = self.add_timer_thread("Print_statistic", 5000, self.timer_print_stat, None)
        return True
    
    def timer_print_stat(self, thread, arg):
        now = time.time_ns()
        diff = (now-self.timestamp)/1000000000
        print ("So far: {} bytes Reads, {} bytes Writes, Rate Read {:.2f} bytes/sec, Rate Write {:.2f} bytes/sec ".format(self.counter_read_all, self.counter_send_all, self.counter_read_all/diff, self.counter_send_all/diff))
        self.counter_read_all = 0
        self.counter_send_all = 0
        self.timestamp = now
        self.timer_thr = self.add_timer_thread("Print_statistic", 5000, self.timer_print_stat, None)


    def read_from_client(self, thread, arg):
        try:
            read_bytes = self.conn.recv(self.msg_size)
            if DISPLAY: print ("Read", len(read_bytes))
        except:
            read_bytes = None
        # peer closed the connection or error
        if read_bytes == None:
            print ('{} disonnected'.format (self.addr))
            # cancel all threads
            self.cancel_thread_by_sock(self.conn)
            self.cancel_thread(self.timer_thr)
            # close the socket
            self.conn.close() 
            self.conn=None 
            # now start accepting again
            self.add_read_thread ("accept_client", self.s, self.accept_client, None)
            return
        self.counter_read_all = self.counter_read_all + len (read_bytes)
        
        self.add_write_thread ("write_to_client", self.conn, self.write_to_client, None)
        self.add_read_thread ("read_from_client", self.conn, self.read_from_client, None)
    
    def write_to_client(self, thread, arg):
        try:
            sent = self.conn.send(self.write_buffer)
            if DISPLAY: print ("Write", sent)
        except:
            self.cancel_thread_by_sock(self.conn)
            # close the socket
            self.conn.close() 
            self.conn=None 
            exit(1)
        self.counter_send_all = self.counter_send_all + sent




class Client(MyTask):
    
    def __init__(self):
        self.msg_size = DATA_PORTION
        self.write_buffer = bytearray(DATA_PORTION)
        for b in range(0, DATA_PORTION):
            self.write_buffer[b] = b%256
        MyTask.__init__(self, "ClientTask", KPseudoThreads.LOG_DBG, KPseudoThreads.LOG_CONSOLE, False)
        
    def task_pre_run_hook(self):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
        self.conn.connect(("127.0.0.1", PORT));
        self.add_write_thread ("send_to_server", self.conn, self.send_to_server, None)
        self.add_read_thread ("read_from_server", self.conn, self.read_from_server, None)   
    
    def read_from_server(self, thread, arg):
        try:
            read_bytes = self.conn.recv(self.msg_size)
            if DISPLAY: print ("Read", len(read_bytes))
        except:
            read_bytes = None
        # peer closed the connection or error
        if read_bytes == None:
            print ("Server Closed")
            # cancel all threads
            self.cancel_thread_by_sock(self.conn)
            # close the socket
            self.conn.close() 
            self.conn=None 
            # now start accepting again
            return
        # reply
        self.add_write_thread ("send_to_server", self.conn, self.send_to_server, None)
        # more on read 
        self.add_read_thread ("read_from_server", self.conn, self.read_from_server, None)

    def send_to_server(self, thread, arg):
        try:
            sent = self.conn.send(self.write_buffer)
            if DISPLAY: print ("Write", sent)
        except:
            self.cancel_thread_by_sock(self.conn)
            # close the socket
            self.conn.close() 
            self.conn=None 
            exit(1)
        


def main():
    print ("Starting server")
    # MAIN
    something = Server()
    something.start();
    time.sleep(3)
    print ("Starting Client")
    something = Client()
    something.start();
    while True:
        time.sleep(1)
if __name__ == "__main__":
    main()    
