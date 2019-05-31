#!/usr/bin/python

from __future__ import absolute_import, division, print_function, unicode_literals

import pi3d
# General
import os
import logging
import time
import sys
from datetime import datetime
import argparse
import multiprocessing
import yaml

# Networking
import struct
import thread
import socket
import pickle

"""
Projectr - Projector Process
Works in tandem with Server Process

"""
logging.basicConfig(
    filename="projector.log",
    level=logging.INFO,
    format='%(asctime)s %(thread)s %(levelname)-6s %(funcName)s:%(lineno)-5d %(message)s',
)

IMAGEDIR = 'static/images/'

""" FUNCTIONS """

# Use class for settings?
def write_settings(process, data):
    """Write the previous image to settings file"""
    logging.info("Writing settings...")
    logging.info("Writing settings...")
    with open('settings.yml', 'w') as outfile:
        outfile.write(yaml.dump(data, default_flow_style=True))


def read_settings(process):
    logging.info("Read settings...")
    try:
        return yaml.load(open("settings.yml"))
    except:
        logging.exception("Could not read settings")
        logging.info("Writing default settings file")
        data = {
                'slideshow': {'delay': 20, 'loop': True},
                'fadeduration': 2,
                'lastimage': u'static/images/logo.jpg',
                'projectors': {
                    'local': {
                        'ip': '127.0.0.1',
                        'port': 5006,
                        'enabled': True,
                        'name': 'Main',
                        'current': '',
                    }
                }
                }
        with open('settings.yml', 'w') as outfile:
            outfile.write(yaml.dump(data, default_flow_style=True))
        return data


def fit_image(input_texture):
    """ Fit image to screen """
    # Ripped this from demo, think I understand it
    # Pretty sure this bit resizes textureture to display size
    # Get ratio of display to textureture
    x_ratio = DISPLAY.width/input_texture.ix
    y_ratio = DISPLAY.height/input_texture.iy
    if y_ratio < x_ratio:  # if y ratio is smaller than x ratio
        x_ratio = y_ratio  # make the ratios the same
    width, height = input_texture.ix * x_ratio, input_texture.iy * x_ratio
    # width, height = tex.ix, tex.iy
    x_position = (DISPLAY.width - width)/2
    y_position = (DISPLAY.height - height)/2

    return width, height, x_position, y_position


def list_files(directory, reverse=False):
    """ Return list of files of specified type """
    output = [f for f in os.listdir(directory) if
              os.path.isfile(os.path.join(directory, f)) and
              f.endswith(('.jpg', '.jpeg', '.png'))]

    if reverse is True:
        # Sort newFileList by date added(?)
        output.sort(key=lambda x: os.stat(os.path.join(directory, x)).st_mtime)
        output.reverse()  # reverse image list so new files are first
    else:
        pass

    return output


""" NETWORKING """


# SENDING AND RECEIVING
def send_msg(sock, msg):
    """ Prefix each message with a 4-byte length (network byte order) """
    msg = struct.pack('>I', len(msg)) + msg
    sock.sendall(msg)


def recv_msg(sock):
    """ Read message length and unpack it into an integer """
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    return recvall(sock, msglen)


def recvall(sock, n):
    """ Helper function to recv n bytes or return None if EOF is hit """
    data = ''

    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        print(packet)
        data += packet

    return data


""" PROCESSES """


def slideshow(imagelist, cur_queue, killslideshowq):
    """ run slideshow """
    process = "Slideshow Process"

    settings = read_settings(process)
    logging.info("Starting slideshow...")
    working = True
    while working is True:
        for image in imagelist:
            # Check to see if slideshow needs to die
            if not killslideshowq.empty():
                emptyq = killslideshowq.get()
                if emptyq == "die":
                    logging.info("Killing slideshow")
                    working = False  # Make sure while loop breaks
                    break  # break out of for loop
            logging.info("Slideshow: %s", image)
            cur_queue.put(image)
            time.sleep(settings["slideshow"]["delay"] + settings["fadeduration"])


def client_handler(connection, client_address, cur_queue):
    process = "Client Handler - %s" % os.urandom(8).encode('base_64')
    logging.debug(connections)
    # Is there a slideshow running?
    slideshowon = False
    killslideshowq = multiprocessing.Queue()
    logging.info("Connected to Master")
    while True:

        # buffer size is 1024 bytes
        data = recv_msg(connection)

        if data != "alive":
            try:
                data = pickle.loads(data)
                logging.debug(data)
            except TypeError, e:
                logging.exception("Failed to unpickle data")

            logging.info("Received TCP data: %s from %s" % (data, client_address))

            if slideshowon is True:
                # If slideshow is running, kill it
                logging.info("Tell Slideshow process to die")
                # Tell slideshow to die
                killslideshowq.put("die")
                slideshowon = False

            if data["action"] == "project":
                if "images" in data:
                    cur_queue.put(data["images"][0])
                    slideshowon = False
                elif "video" in data:
                    logging.info("Video to project is %s", data["video"])
                else:
                    logging.info("Nothing to project")
            elif data["action"] == "slideshow":
                logging.info("Start Slideshow Process")
                ssproc = multiprocessing.Process(target=slideshow,
                                                 args=(data["images"],
                                                       cur_queue,
                                                       killslideshowq))
                ssproc.start()
                slideshowon = True
            elif data["action"] == "stopslideshow":
                ssproc.terminate()
            elif data["action"] == "sync":
                images = list_files(IMAGEDIR)
                print(images)
            elif data["action"] == "whatsplaying":
                settings = read_settings(process)
                send_msg(connection, settings["lastimage"])
            else:
                logging.info("Unkown action: %s", data["action"])
        else:
            logging.info("Alive?")
            send_msg(connection, "alive")


def tcp_receiver(cur_queue, connections):
    """ Receive images via TCP """
    process = "TCP Receiver"

    # TCP config
    tcp_ip = "127.0.0.1"  # local only
    tcp_port = 5006

    # Set up TCP
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    logging.info('Starting up on %s port %s' % (tcp_ip, tcp_port))

    # bind server to address
    sock.bind((tcp_ip, tcp_port))
    sock.listen(1)

    cons = {}

    while True:
        logging.info("Waiting for a connection...")
        # Not sure if this is really necessary however,
        # It gives the connection a unique number
        # and adds it to the connactions dictionary
        con_number = str(len(connections) + 1)
        logging.debug(con_number)
        cons[con_number], client_address = sock.accept()

        logging.info("Starting a new thread for client %s", str(client_address))
        thread.start_new_thread(client_handler, (cons[con_number],
                                client_address, cur_queue))


""" pi3d """


class Carousel(object):
    """ The main object """
    def __init__(self):
        # Start the image dictionary
        self.imagedict = {}
        self.process = "Carousel"

        # Load the last image used
        try:
            # If there is a settings file, load most recent image
            # Load the settings file

            settings = read_settings(self.process)
            # Add the image to the queue
            logging.info("Last image: %s" % settings["lastimage"])
            starting_image = settings["lastimage"]
        except:
            logging.exception("Failed to load settings file")
            logging.info("Loading default image")
            # Write new image to settings
            settings = read_settings(self.process)
            settings["lastimage"] = "static/images/logo.jpg"
            write_settings(self.process, settings)
            settings = read_settings(self.process)
            # Load default image into queue
            starting_image = settings["lastimage"]

        # Set up image one
        texture_one = pi3d.Texture(starting_image, blend=True, mipmap=True)
        image_one = pi3d.Canvas()
        image_one.set_texture(texture_one)

        width, height, x_position, y_position = fit_image(texture_one)

        image_one.set_2d_size(w=width, h=height, x=x_position, y=y_position)
        image_one.set_alpha(1)
        image_one.set_shader(SHADER)
        image_one.positionZ(0.1)

        self.imagedict[starting_image] = {"canvas": image_one, "visible": True,
                                          "fading": True}

        self.focus = starting_image

        # print(self.imagedict[self.focus]["canvas"].z())

    def pick(self, new_image):
        """ Pick an image by URL """

        if self.focus != new_image:
            # Check to see if image already in dictionary
            # Might be worth pre-preparing
            # a dictionary with null canvas objects?

            # If image is already loaded, make it visible
            if new_image in self.imagedict:
                # print("Image exists")
                # New focus image is visible
                self.imagedict[new_image]["visible"] = True

                # New focus image is the active fader
                self.imagedict[new_image]["fading"] = True

                # Otherwise load it as a new image
            else:
                # print("Load new image")

                new_canvas = pi3d.Canvas()

                # print("Pick an image: %s" % new_image)
                new_texture = pi3d.Texture(new_image, blend=True, mipmap=True)
                # print("Texture loaded")
                new_canvas.set_texture(new_texture)
                # print("Texture set")

                # Fit image
                width, height, x_position, y_position = fit_image(new_texture)

                new_canvas.set_2d_size(w=width, h=height,
                                       x=x_position, y=y_position)
                new_canvas.set_alpha(0)
                new_canvas.set_shader(SHADER)
                new_canvas.positionZ(0.2)
                # print("New image prepared")

                self.imagedict[new_image] = {"canvas": new_canvas,
                                             "visible": True, "fading": True}

            # Move old focused image back

            if self.imagedict[self.focus]["canvas"].z() > 0.1:
                self.imagedict[self.focus]["canvas"].positionZ(0.1)

            # Bring new focused image forward
            self.imagedict[new_image]["canvas"].positionZ(0.2)

            # Old focus image not the active fader
            self.imagedict[self.focus]["fading"] = False

            self.focus = new_image  # Change the focused image
            # Write new image to settings
            settings = read_settings(self.process)
            settings["lastimage"] = new_image
            write_settings(self.process, settings)
            settings = read_settings(self.process)
        else:
            logging.warning("Image already projected")

    def update(self):
        """ Update image alphas """
        for image in self.imagedict:
            alpha = self.imagedict[image]["canvas"].alpha()
            if self.imagedict[image]["fading"] is True and alpha < 1:
                # print("%s Increase alpha: %f" % (image, alpha))
                alpha += alpha_step
                self.imagedict[image]["canvas"].set_alpha(alpha)
            elif self.imagedict[image]["fading"] is False and alpha > 0:
                # print("%s Decrease alpha: %f" % (image, alpha))
                alpha -= alpha_step
                self.imagedict[image]["canvas"].set_alpha(alpha)
            else:
                if alpha <= 0:
                    self.imagedict[image]["visible"] = False

    def draw(self):
        """ Draw the images on the screen """
        # Draw fading image first
        first_image = None
        second_image = None

        for image in self.imagedict:
            if self.imagedict[image]["visible"] is True and self.imagedict[image]["fading"] is True:
                first_image = self.imagedict[image]["canvas"]
            elif self.imagedict[image]["visible"] is True:
                second_image = self.imagedict[image]["canvas"]

        first_image.draw()
        # If second image exists (fixes start up)
        if second_image:
            second_image.draw()


if __name__ == "__main__":
    process = "Main Process"
    logging.info("Christie's Projector")

    # parse command line arguments
    parser = argparse.ArgumentParser(description='Project images.')
    parser.add_argument("-t", "--test",
                        help="Run projector in a window for testing",
                        action="store_true")

    args = parser.parse_args()

    # Set up image queue
    IMAGEQ = multiprocessing.Queue()

    # Set up connections dict
    connections = multiprocessing.Manager().dict()

    logging.info("Start TCP Receiver")
    tcpprocess = multiprocessing.Process(target=tcp_receiver,
                                         args=(IMAGEQ, connections))
    tcpprocess.start()

    logging.info("Start Projector process")

    if args.test:
        # If testing, create a small display
        DISPLAY = pi3d.Display.create(background=(0.0, 0.0, 0.0, 1.0),
                                      frames_per_second=20, w=800, h=600)
    else:
        DISPLAY = pi3d.Display.create(background=(0.0, 0.0, 0.0, 1.0),
                                      frames_per_second=20)

    SHADER = pi3d.Shader("2d_flat")

    alpha_step = 0.025
    crsl = Carousel()

    # Set up camera
    CAMERA = pi3d.Camera.instance()
    CAMERA.was_moved = False

    # Keyboard
    KEYBOARD = pi3d.Keyboard()

    while DISPLAY.loop_running():
        crsl.update()
        crsl.draw()

        # Take keyboard events and check for quit
        k = KEYBOARD.read()
        if k > -1:
            if k == 27:
                KEYBOARD.close()
                DISPLAY.stop()
                if len(connections) > 0:
                    for connection in connections:
                        print("Close connnection %s" % connection)
                        connection.shutdown(socket.SHUT_RDWR)
                        connection.close()
                tcpprocess.terminate()

        # Check if there is a new image to be displayed
        if not IMAGEQ.empty():
            new_image = IMAGEQ.get()
            logging.info("New image is: %s", new_image)
            crsl.pick(new_image)
