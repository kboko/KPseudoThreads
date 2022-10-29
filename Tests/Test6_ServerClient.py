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
from mypseudothreads import *
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
    Threads debug can be enabled - see MyPseudoThreads constructor
    DATA_PORTION - this sets the data to be send, make it not so big, Use Test3 for bigger chunks

"""
DISPLAY=False

PORT=34455
DATA_PORTION = 1024000
class ServerClient():
    def __init__(self, conn, addr, parent):
        self.parent = parent
        self.conn = conn
        self.addr = addr
        self.read_buffer = bytearray()
        self.write_buffer = bytearray(DATA_PORTION)
        for b in range(0, DATA_PORTION):
            self.write_buffer[b] = b%256
        self.write_index = 0
        
        
    
class Server(MyTask):
    
    def __init__(self):
        self.msg_size = DATA_PORTION
        self.conn = None
        self.addr = None
        self.counter_read_all = 0
        self.counter_send_all = 0
        self.clients = []
        MyTask.__init__(self, "Server", LOG_DBG, LOG_CONSOLE, False)
        self.timestamp = time.time_ns()
    
    def task_pre_run_hook(self):
        for res in socket.getaddrinfo("127.0.0.1", PORT , socket.AF_UNSPEC, socket.SOCK_STREAM, 0, socket.AI_PASSIVE):
            af, socktype, proto, canonname, sa = res
            self.s = socket.socket(af, socktype, proto)
            self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.s.bind(sa)
            self.s.listen(1)
            self.s.setblocking(0)
            self.add_read_thread ("accept_client", self.s, self.accept_client, None)
            self.timer_thr = self.add_timer_thread("Print_statistic", 5000, self.timer_print_stat, None)
            
    def accept_client(self, thread, arg):
        con, addr = self.s.accept()
        c = ServerClient(con, addr, self)
        print ('Command thread connected by {}'.format (addr))
        self.clients.append(c)
        # now start the client
        self.add_read_thread ("read_from_client", con, self.read_from_client, c)
        # accept more client
        self.add_read_thread ("accept_client", self.s, self.accept_client, None)
        return True
    
    def timer_print_stat(self, thread, arg):
        now = time.time_ns()
        diff = (now-self.timestamp)/1000000000
        print ("Server: {} bytes Reads, {} bytes Writes, Rate Read {:.2f} bytes/sec, Rate Write {:.2f} bytes/sec ".format(self.counter_read_all, self.counter_send_all, self.counter_read_all/diff, self.counter_send_all/diff))
        self.counter_read_all = 0
        self.counter_send_all = 0
        self.timestamp = now
        self.timer_thr = self.add_timer_thread("Print_statistic", 5000, self.timer_print_stat, None)


    def read_from_client(self, thread, client):
        try:
            read_bytes = client.conn.recv(self.msg_size)
            if DISPLAY: print ("Read", client.addr, len(read_bytes))
        except:
            read_bytes = None
        # peer closed the connection or error
        if read_bytes == None:
            print ('{} disonnected'.format (client.addr))
            # cancel all threads
            self.cancel_thread_by_sock(client.conn)
            
            # close the socket
            client.conn.close() 
            client.conn=None 
            return
        self.counter_read_all = self.counter_read_all + len (read_bytes)
        # add new bytes to our in buffer
        client.read_buffer = client.read_buffer + read_bytes
        # if we got whole message
        if len(client.read_buffer) >= self.msg_size: 
            in_data = client.read_buffer[:self.msg_size]
            client.read_buffer = client.read_buffer[self.msg_size:]
            #print ("Received {}, replying...".format(len(in_data)))
            self.add_write_thread ("write_to_client", client.conn, self.write_to_client, client)
        # more to read
        self.add_read_thread ("read_from_client", client.conn, self.read_from_client, client)
    
    def write_to_client(self, thread, client):
        try:
            sent = client.conn.send(client.write_buffer[client.write_index:])
            if DISPLAY: print ("Write", client.addr, sent)
        except:
            self.cancel_thread_by_sock(client.conn)
            # close the socket
            client.conn.close() 
            client.conn=None 
            exit(1)
        self.counter_send_all = self.counter_send_all + sent
        
        if sent != DATA_PORTION - client.write_index:
            print ("Sent Only {}. Schedule more to send", sent)
            client.write_index = client.write_index + sent
            # schedule thread to send the reset
            self.add_write_thread ("more_to_write_to_client", client.conn, self.write_to_client, client)





class Client(MyTask):
    
    def __init__(self, name):
        self.msg_size = DATA_PORTION
        self.write_buffer = bytearray(DATA_PORTION)
        for b in range(0, DATA_PORTION):
            self.write_buffer[b] = b%256
        self.counter_read_all = 0
        self.counter_send_all = 0
        MyTask.__init__(self, name, LOG_DBG, LOG_CONSOLE, False)
        
    def task_pre_run_hook(self):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
        self.conn.connect(("127.0.0.1", PORT));
        self.add_write_thread ("send_to_server", self.conn, self.send_to_server, None)
        self.add_read_thread ("read_from_server", self.conn, self.read_from_server, None)   
        self.timestamp = time.time_ns()
        self.timer_thr = self.add_timer_thread("Print_statistic", 5000, self.client_print_stat, None)

    def client_print_stat(self, thread, arg):
        now = time.time_ns()
        diff = (now-self.timestamp)/1000000000
        print ("{} bytes Reads, {} bytes Writes {} bytes Reads, Rate Read {:.2f} bytes/sec, Rate Write {:.2f} bytes/sec ".format(self.task_name, self.counter_read_all, self.counter_send_all, self.counter_read_all/diff, self.counter_send_all/diff))
        self.counter_read_all = 0
        self.counter_send_all = 0
        self.timestamp = now
        self.timer_thr = self.add_timer_thread("Print_statistic", 5000, self.client_print_stat, None)

    def read_from_server(self, thread, arg):
        try:
            read_bytes = self.conn.recv(self.msg_size)
            if DISPLAY: print ("Read", len(read_bytes))
            self.counter_read_all = self.counter_read_all + len(read_bytes)
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
            self.counter_send_all = self.counter_send_all + sent
        except:
            self.cancel_thread_by_sock(self.conn)
            # close the socket
            self.conn.close() 
            self.conn=None 
            exit(1)
        


def main():
    print ("Starting server")
    # MAIN
    server = Server()
    server.start();
    time.sleep(3)
    for a in range(0,10):
        print ("Starting Clients")
        something = Client("Client{}".format(a))
        something.start();
    # run 10 seconds 
    time.sleep(60)
    server.task_stop()
if __name__ == "__main__":
    main()    
