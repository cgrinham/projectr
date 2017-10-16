import socket

UDP_IP = "127.0.0.1"
UDP_PORT = 5005


SOCK = socket.socket(socket.AF_INET, # Internet
				socket.SOCK_DGRAM) # UDP

#print "starting at: %d" % count

print "Input filename of image to show:"
IMAGE = raw_input("> ")

# send image name to projector
SOCK.sendto(IMAGE, (UDP_IP, UDP_PORT))
