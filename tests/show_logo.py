import os
import pygame
import time
import socket
import sys

UDP_IP = "127.0.0.1"
UDP_PORT = 5005


# Set up UDP
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # UDP
sock.bind((UDP_IP, UDP_PORT))


# check if there is an X display
disp_no = os.getenv('DISPLAY')

if disp_no:
    print "I'm running under X display = {0}".format(disp_no)

# List of possible Framebuffer drivers, directfb is preferable
drivers = ['directfb', 'fbcon', 'svgalib']

found = False
# attempt to use each driver with pygame
for driver in drivers:
    if not os.getenv('SDL_VIDEODRIVER'):
        os.putenv('SDL_VIDEODRIVER', driver)
    print driver
    try:
        pygame.display.init()
    except pygame.error:
        print 'Driver: {0} failed.'.format(driver)
        continue
    found = True
    break

if not found:
   raise Exception('No suitable video driver found!')


size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
screen = pygame.display.set_mode(size, pygame.FULLSCREEN)

IMG = pygame.image.load("/home/pi/server/static/images/logo.png")

while True:
    events = pygame.event.get()
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            sys.exit()
    
    x = (size[0] / 2) - (IMG.get_rect().size[0] / 2)

    pygame.mouse.set_visible(False) 
    screen.fill((0,0,0))
    screen.blit(IMG, (x, 0))
    pygame.display.flip()    

    # Wait for udp
    DATA, ADDR = sock.recvfrom(1024) # buffer size is 1024 bytes
    try:
        IMG = pygame.image.load("/home/pi/server/static/images/%s" % DATA)
    except:
        print "ERROR! Could not load image %s" % DATA

    # Check if new image is bigger than screen
    if (IMG.get_rect().size[0] > size[0]) or IMG.get_rect().size[1] > size[1]:
        IMG = pygame.transform.smoothscale(IMG, (size[0], IMG.get_rect().size[1] / (IMG.get_rect().size[0] / size[0])))
        # Check if image is still too tall after being resized
        if IMG.get_rect().size[1] > size[1]:
            IMG = pygame.transform.smoothscale(IMG, (IMG.get_rect().size[0] / (IMG.get_rect().size[1] / size[1]), size[1]))
    else:
        pass
