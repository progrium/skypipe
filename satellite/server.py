import collections
import os
import sys
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

pipe_clients = collections.defaultdict(list)
pipe_buffers = collections.defaultdict(list)

print "Serving on {}...".format(port)
while True:
    sys.stdout.flush()
    msg = router.recv_multipart()
    client = msg.pop(0)
    client_display = hex(abs(hash(client)))[-6:]
    header = str(msg.pop(0))
    command = str(msg.pop(0))
    if command == SP_CMD_HELLO:
        router.send_multipart([client, SP_HEADER, SP_CMD_HELLO])
    elif command == SP_CMD_LISTEN:
        pipe_name = msg.pop(0)
        pipe_clients[pipe_name].append(client)
        if len(pipe_clients[pipe_name]) == 1:
            while len(pipe_buffers[pipe_name]) > 0:
                data = pipe_buffers[pipe_name].pop(0)
                router.send_multipart([client,
                    SP_HEADER, SP_CMD_DATA, pipe_name, data])
                if data == SP_DATA_EOF:
                    break
    elif command == SP_CMD_UNLISTEN:
        pipe_name = msg.pop(0)
        if client in pipe_clients[pipe_name]:
            pipe_clients[pipe_name].remove(client)
    elif command == SP_CMD_DATA:
        pipe_name = msg.pop(0)
        data = msg.pop(0)
        if not pipe_clients[pipe_name]:
            pipe_buffers[pipe_name].append(data)
        else:
            for listener in pipe_clients[pipe_name]:
                router.send_multipart([listener,
                    SP_HEADER, SP_CMD_DATA, pipe_name, data])
    else:
        print client_display, "Unknown command:", command
        continue
    print client_display, command
