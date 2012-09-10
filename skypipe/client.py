"""Skypipe client

This contains the client implementation for skypipe, which operates in
two modes:

1. Input mode: STDIN -> Skypipe satellite
2. Output mode: Skypipe satellite -> STDOUT

The satellite is a server managed by the cloud module. They use ZeroMQ
to message with each other. They use a simple protocol on top of ZeroMQ
using multipart messages. The first part is the header, which identifies
the name and version of the protocol being used. The second part is
always a command. Depending on the command there may be more parts.
There are only four commands as of 0.1:

1. HELLO: Used to ping the server. Server should HELLO back.
2. DATA <pipe> <data>: Send/recv one piece of data (usually a line) for pipe
3. LISTEN <pipe>: Start listening for data on a pipe
4. UNLISTEN <pipe>: Stop listening for data on a pipe

The pipe parameter is the name of the pipe. It can by an empty string to
represent the default pipe. 

EOF is an important concept for skypipe. We represent it with a DATA
command using an empty string for the data.
"""
import os
import sys
import time

import zmq

ctx = zmq.Context.instance()

SP_HEADER = "SKYPIPE/0.1"
SP_CMD_HELLO = "HELLO"
SP_CMD_DATA = "DATA"
SP_CMD_LISTEN = "LISTEN"
SP_CMD_UNLISTEN = "UNLISTEN"
SP_DATA_EOF = ""

def sp_msg(cmd, pipe=None, data=None):
    """Produces skypipe protocol multipart message"""
    msg = [SP_HEADER, cmd]
    if pipe is not None:
        msg.append(pipe)
    if data is not None:
        msg.append(data)
    return msg

def check_skypipe_endpoint(endpoint, timeout=10):
    """Skypipe endpoint checker -- pings endpoint

    Returns True if endpoint replies with valid header,
    Returns False if endpoint replies with invalid header,
    Returns None if endpoint does not reply within timeout
    """
    socket = ctx.socket(zmq.DEALER)
    socket.linger = 0
    socket.connect(endpoint)
    socket.send_multipart(sp_msg(SP_CMD_HELLO))
    timeout_time = time.time() + timeout
    while time.time() < timeout_time:
        reply = None
        try:
            reply = socket.recv_multipart(zmq.NOBLOCK)
            break
        except zmq.ZMQError:
            time.sleep(0.1)
    socket.close()
    if reply:
        return str(reply.pop(0)) == SP_HEADER


def stream_skypipe_output(endpoint, name=None):
    """Generator for reading skypipe data"""
    name = name or ''
    socket = ctx.socket(zmq.DEALER)
    socket.connect(endpoint)
    try:
        socket.send_multipart(sp_msg(SP_CMD_LISTEN, name))

        while True:
            msg = socket.recv_multipart()
            try:
                data = parse_skypipe_data_stream(msg, name)
                if data:
                    yield data
            except EOFError:
                raise StopIteration()

    finally:
        socket.send_multipart(sp_msg(SP_CMD_UNLISTEN, name))
        socket.close()

def parse_skypipe_data_stream(msg, for_pipe):
    """May return data from skypipe message or raises EOFError"""
    header = str(msg.pop(0))
    command = str(msg.pop(0))
    pipe_name = str(msg.pop(0))
    data = str(msg.pop(0))
    if header != SP_HEADER: return
    if pipe_name != for_pipe: return
    if command != SP_CMD_DATA: return
    if data == SP_DATA_EOF:
        raise EOFError()
    else:
        return data

def skypipe_input_stream(endpoint, name=None):
    """Returns a context manager for streaming data into skypipe"""
    name = name or ''
    class context_manager(object):
        def __enter__(self):
            self.socket = ctx.socket(zmq.DEALER)
            self.socket.connect(endpoint)
            return self

        def send(self, data):
            data_msg = sp_msg(SP_CMD_DATA, name, data)
            self.socket.send_multipart(data_msg)

        def __exit__(self, *args, **kwargs):
            eof_msg = sp_msg(SP_CMD_DATA, name, SP_DATA_EOF)
            self.socket.send_multipart(eof_msg)
            self.socket.close()

    return context_manager()

def stream_stdin_lines():
    """Generator for unbuffered line reading from STDIN"""
    stdin = os.fdopen(sys.stdin.fileno(), 'r', 0)
    while True:
        line = stdin.readline()
        if line:
            yield line
        else:
            break

def run(endpoint, name=None):
    """Runs the skypipe client"""
    try:
        if os.isatty(0):
            # output mode
            for data in stream_skypipe_output(endpoint, name):
                sys.stdout.write(data)
                sys.stdout.flush()

        else:
            # input mode
            with skypipe_input_stream(endpoint, name) as stream:
                for line in stream_stdin_lines():
                    stream.send(line)

    except KeyboardInterrupt:
        pass
