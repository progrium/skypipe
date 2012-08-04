#!/usr/bin/env ruby

require 'rubygems'
require 'ffi-rzmq'

SP_HEADER = "SKYPIPE/0.1"
SP_DATA = "DATA"
SP_LISTEN = "LISTEN"
SP_UNLISTEN = "UNLISTEN"
SP_EOF = ""

zmq_endpoint = "tcp://0.0.0.0:9000"
pipe_name = ARGV.first || ""

context = ZMQ::Context.new
begin
  if STDIN.tty? # output mode
    socket = context.socket(ZMQ::DEALER)
    begin
      socket.connect(zmq_endpoint)
      socket.send_strings([SP_HEADER, SP_LISTEN, pipe_name])
      
      loop do
        msg = []
        socket.recv_strings msg
        header, type, name, data = msg
        raise "Invalid message" unless header == SP_HEADER
        next if name != pipe_name
        next if type != SP_DATA
        if data == SP_EOF
          break
        else
          STDOUT.write data
          STDOUT.flush
        end
      end
    rescue Interrupt
    ensure
      socket.send_strings([SP_HEADER, SP_UNLISTEN, pipe_name])
      socket.close
    end

  else # input mode
    socket = context.socket(ZMQ::DEALER)
    begin
      socket.connect(zmq_endpoint)

      STDIN.each do |line|
        socket.send_strings([SP_HEADER, SP_DATA, pipe_name, line])
      end
    rescue Interrupt
    ensure
      socket.send_strings([SP_HEADER, SP_DATA, pipe_name, SP_EOF])
      socket.close
    end
  end
ensure
  context.terminate
end
