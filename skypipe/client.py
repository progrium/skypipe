import os
import sys
import zmq

from . import deploy

SP_HEADER = "SKYPIPE/0.1"
SP_CMD_HELLO = "HELLO"
SP_CMD_DATA = "DATA"
SP_CMD_LISTEN = "LISTEN"
SP_CMD_UNLISTEN = "UNLISTEN"
SP_DATA_EOF = ""

try:
    pipe_name = sys.argv[1]
except IndexError:
    pipe_name = ''

def run():
    context = zmq.Context()
    try:
        zmq_endpoint = os.environ.get("ZMQ_ENDPOINT")
        if not zmq_endpoint:
            zmq_endpoint = deploy.find_satellite(context)

        if os.isatty(0):
            # output mode
            socket = context.socket(zmq.DEALER)
            try:
                socket.connect(zmq_endpoint)
                socket.send_multipart([SP_HEADER, SP_CMD_LISTEN, pipe_name])

                while True:
                    msg = socket.recv_multipart()
                    header = str(msg.pop(0))
                    command = str(msg.pop(0))
                    pipe_name_ = str(msg.pop(0))
                    data = str(msg.pop(0))
                    if header != SP_HEADER:
                        continue
                    if pipe_name_ != pipe_name:
                        continue
                    if command != SP_CMD_DATA:
                        continue
                    if data == SP_DATA_EOF:
                        break
                    else:
                        sys.stdout.write(data)
                        sys.stdout.flush()
            except KeyboardInterrupt:
                pass
            finally:
                socket.send_multipart([SP_HEADER, SP_CMD_UNLISTEN, pipe_name])
                socket.close()
        else:
            # input mode
            socket = context.socket(zmq.DEALER)
            try:
                socket.connect(zmq_endpoint)

                # unbuffered stdin:
                stdin = os.fdopen(sys.stdin.fileno(), 'r', 0)
                while True:
                    line = stdin.readline()
                    if line:
                        socket.send_multipart([SP_HEADER, SP_CMD_DATA, pipe_name, line])
                    else:
                        break
            except KeyboardInterrupt:
                pass
            finally:
                socket.send_multipart([SP_HEADER, SP_CMD_DATA, pipe_name, SP_DATA_EOF])
                socket.close()
    finally:
        context.term()
