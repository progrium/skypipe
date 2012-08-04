require 'rubygems'
require 'ffi-rzmq'

SP_HEADER = "SKYPIPE/0.1"
SP_DATA = "DATA"
SP_LISTEN = "LISTEN"
SP_UNLISTEN = "UNLISTEN"
SP_EOF = ""

context = ZMQ::Context.new

router = context.socket(ZMQ::ROUTER)
router.bind('tcp://0.0.0.0:9000')

poller = ZMQ::Poller.new
poller.register(router, ZMQ::POLLIN)

pipe_clients = {}
pipe_buffers = {}

puts "Serving..."
loop do
  poller.poll(:blocking)
  poller.readables.each do |socket|
    if socket === router
      msg = []
      socket.recv_strings msg
      client, header, type, name, data = msg
      raise "Invalid message" unless header == SP_HEADER
      if type == SP_LISTEN
        pipe_clients[name] ||= []
        pipe_clients[name] << client
        if pipe_clients[name].length == 1
          pipe_buffers[name] ||= []
          while not pipe_buffers[name].empty?
            data = pipe_buffers[name].shift
            socket.send_strings [client, SP_HEADER, SP_DATA, name, data]
            break if data == SP_EOF
          end
        end
      elsif type == SP_UNLISTEN
        pipe_clients[name] ||= []
        pipe_clients[name].delete client
      elsif type == SP_DATA
        pipe_clients[name] ||= []
        if pipe_clients[name].empty?
          pipe_buffers[name] ||= []
          pipe_buffers[name] << data
        else
          pipe_clients[name].each do |client|
            socket.send_strings [client, SP_HEADER, SP_DATA, name, data]
          end
        end
      end
      puts msg
    end
  end
end
