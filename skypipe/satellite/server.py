import collections
import sys
import os
import zmq

SP_HEADER = "SKYPIPE/0.1"
SP_CMD_HELLO = "HELLO"
SP_CMD_DATA = "DATA"
SP_CMD_LISTEN = "LISTEN"
SP_CMD_UNLISTEN = "UNLISTEN"
SP_DATA_EOF = ""

context = zmq.Context()
port = os.environ.get("PORT_ZMQ", 9000)

router = context.socket(zmq.ROUTER)
router.bind("tcp://0.0.0.0:{}".format(port))

pipe_clients = collections.defaultdict(list) # connected skypipe clients
pipe_buffers = collections.defaultdict(list) # any buffered data for pipes

print "Serving on {}...".format(port)

checker = {
        SP_CMD_LISTEN :cmd_lis_func,
        SP_CMD_UNLISTEN: cmd_unlis_func,
        SP_CMD_DATA: cmd_data_func,
        }

def cmd_lis_func():
    pipe_clients[pipe_name].append(client)
    if len(pipe_clients[pipe_name]) == 1:
        # if only client after adding, then previously there were
        # no clients and it was buffering, so spit out buffered data
        while len(pipe_buffers[pipe_name]) > 0:
            data = pipe_buffers[pipe_name].pop(0)
            router.send_multipart([client,
                SP_HEADER, SP_CMD_DATA, pipe_name, data])
            if data == SP_DATA_EOF:
                # remember this kicks the client, so stop
                # sending data until the next one listens
                break

def cmd_unlis_func():
    if client in pipe_clients[pipe_name]:
        pipe_clients[pipe_name].remove(client)
 
def cmd_data_func():
    data = msg.pop(0)
    if not pipe_clients[pipe_name]:
        pipe_buffers[pipe_name].append(data)
    else:
        for listener in pipe_clients[pipe_name]:
            router.send_multipart([listener,
                SP_HEADER, SP_CMD_DATA, pipe_name, data])
 

while True:
    sys.stdout.flush()
    
    msg = router.recv_multipart()
    client = msg.pop(0)
    header = str(msg.pop(0))
    command = str(msg.pop(0))
    
    # Human-friendlier version of client UUID
    client_display = hex(abs(hash(client)))[-6:]

    if SP_CMD_HELLO == command:
        router.send_multipart([client, SP_HEADER, SP_CMD_HELLO])
    
    else:
        pipe_name = msg.pop(0)
        try:
            checker[command]()
        except KeyError:
            print client_display, "Unknown command:", command


    print client_display, command
