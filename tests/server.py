import socket

PORT = 50000
MAGIC = "sdf876sd" # make us unique


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #create UDP socket
s.bind(('', PORT))

clients = {}

while 1:
	print "Waiting for service announcement"
	data, addr = s.recvfrom(1024) # wait for a packet
	if data.startswith(MAGIC):
		clientip = data[len(MAGIC):]
		print clientip
		print "got service announcement from", data[len(MAGIC):]
		# Tell client we've heard
		print "Sending reply"
		s.sendto("hello", (clientip, PORT))
