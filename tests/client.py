import socket
import time
import fcntl
import struct


PORT = 50000
MAGIC = "sdf876sd" #to make sure we don't confuse or get confused by other programs

foundclients = False

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #create UDP socket
s.bind(('', 0))
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1) #this is a broadcast socket

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

my_ip = get_ip_address('wlan0')

while 1:
    data = MAGIC+my_ip
    s.sendto(data, ('<broadcast>', PORT))
    print "sent service announcement, waiting for reply"

    # wait for reply, timeout after 1 minute
    data, addr = s.recvfrom(1024)
    print data

    # when receive reply, break loop and continue with IP
    if data == "hello":
        print "Received acknowledgement from server"
        break

print "Escaped successfully"


    
