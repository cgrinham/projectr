#!/usr/bin/python
"""
Projectr - Projector Process
Works in tandem with Server Process

"""
from __future__ import absolute_import, division, print_function, unicode_literals

import pi3d
# General
import os
import logging
import time
import argparse
import multiprocessing
import yaml

# Networking
import thread
import socket
import pickle

from . import networking

logging.basicConfig(
    filename="projector.log",
    level=logging.INFO,
    format='%(asctime)s %(thread)s %(levelname)-6s %(funcName)s:%(lineno)-5d %(message)s',
)

IMAGEDIR = 'static/images/'
ALPHA_STEP = 0.025


# Use class for settings?
def write_settings(process, data):
    """Write the previous image to settings file"""
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


def fit_image(input_texture, display):
    """ Fit image to screen """
    # Ripped this from demo, think I understand it
    # Pretty sure this bit resizes textureture to display size
    # Get ratio of display to textureture
    x_ratio = display.width/input_texture.ix
    y_ratio = display.height/input_texture.iy
    if y_ratio < x_ratio:  # if y ratio is smaller than x ratio
        x_ratio = y_ratio  # make the ratios the same
    width, height = input_texture.ix * x_ratio, input_texture.iy * x_ratio
    # width, height = tex.ix, tex.iy
    x_position = (display.width - width)/2
    y_position = (display.height - height)/2

    return width, height, x_position, y_position


def list_files(directory, reverse=False):
    """ Return list of files of specified type """
    output = [f for f in os.listdir(directory) if
              os.path.isfile(os.path.join(directory, f)) and
              f.endswith(('.jpg', '.jpeg', '.png'))]

    if reverse is True:
        output.sort(key=lambda x: os.stat(os.path.join(directory, x)).st_mtime)
        output.reverse()  # reverse image list so new files are first
    return output


""" PROCESSES """


def slideshow(imagelist, cur_queue, killslideshowq):
    """ run slideshow """
    process = "Slideshow Process"

    settings = read_settings(process)
    logging.info("Starting slideshow...")
    working = True
    while working:
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
    # Is there a slideshow running?
    slideshowon = False
    killslideshowq = multiprocessing.Queue()
    logging.info("Connected to Master")
    while True:
        # buffer size is 1024 bytes
        data = networking.recv_msg(connection)

        if data == "alive":
            logging.info("Alive?")
            networking.send_msg(connection, "alive")
        else:
            try:
                data = pickle.loads(data)
                logging.debug(data)
            except TypeError as e:
                logging.exception("Failed to unpickle data")

            logging.info("Received TCP data: %s from %s" % (data, client_address))

            if slideshowon:
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
                networking.send_msg(connection, settings["lastimage"])
            else:
                logging.info("Unkown action: %s", data["action"])


def tcp_receiver(cur_queue, connections):
    """ Receive images via TCP """
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



class Carousel(object):
    """ The main object """

    def __init__(self, display):
        self.imagedict = {}
        self.process = "Carousel"
        self.shader = pi3d.Shader("2d_flat")
        self.display = display
        # Load the last image used
        try:
            # If there is a settings file, load most recent image
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

        self.set_up_image(starting_image, 1, 0.1)
        self.focus = starting_image

    def set_up_image(self, image, alpha, z_position):
        texture = pi3d.Texture(image, blend=True, mipmap=True)
        canvas = pi3d.Canvas()
        canvas.set_texture(texture)
        width, height, x_position, y_position = fit_image(texture, self.display)
        canvas.set_2d_size(w=width, h=height, x=x_position, y=y_position)
        canvas.set_alpha(alpha)
        canvas.set_shader(self.shader)
        canvas.positionZ(z_position)
        self.imagedict[image] = {
            "canvas": canvas, "visible": True, "fading": True}

    def pick(self, new_image):
        """ Pick an image by URL """
        if self.focus == new_image:
            logging.warning("Image already projected")
            return

        # Check to see if image already in dictionary
        # Might be worth pre-preparing
        # a dictionary with null canvas objects?

        # If image is already loaded, make it visible
        if new_image in self.imagedict:
            # New focus image is visible
            # New focus image is the active fader
            self.imagedict[new_image]["visible"] = True
            self.imagedict[new_image]["fading"] = True
        else:
            self.set_up_image(new_image, 0, 0.1)

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

    def update(self):
        """ Update image alphas """
        for image, detail in self.imagedict.iteritems():
            alpha = detail["canvas"].alpha()
            if detail["fading"] and alpha < 1:
                alpha += ALPHA_STEP
                detail["canvas"].set_alpha(alpha)
            elif not detail["fading"] and alpha > 0:
                alpha -= ALPHA_STEP
                detail["canvas"].set_alpha(alpha)
            else:
                if alpha <= 0:
                    detail["visible"] = False

    def draw(self):
        """ Draw the images on the screen """
        # Draw fading image first
        first_image = None
        second_image = None

        for image, detail in self.imagedict.iteritems():
            if detail["visible"] and detail["fading"]:
                first_image = detail["canvas"]
            elif detail["visible"]:
                second_image = detail["canvas"]

        first_image.draw()
        # If second image exists (fixes start up)
        if second_image:
            second_image.draw()


def main(test):
    # Set up image queue
    IMAGEQ = multiprocessing.Queue()
    connections = multiprocessing.Manager().dict()

    logging.info("Start TCP Receiver")
    tcpprocess = multiprocessing.Process(target=tcp_receiver,
                                         args=(IMAGEQ, connections))
    tcpprocess.start()

    logging.info("Start Projector process")
    if test:
        display = pi3d.Display.create(background=(0.0, 0.0, 0.0, 1.0),
                                      frames_per_second=20, w=800, h=600)
    else:
        display = pi3d.Display.create(background=(0.0, 0.0, 0.0, 1.0),
                                      frames_per_second=20)
    crsl = Carousel()

    # Set up camera
    CAMERA = pi3d.Camera.instance()
    CAMERA.was_moved = False
    KEYBOARD = pi3d.Keyboard()

    while display.loop_running():
        crsl.update()
        crsl.draw()

        k = KEYBOARD.read()
        if k > -1:
            if k == 27:
                KEYBOARD.close()
                display.stop()
                if len(connections) > 0:
                    for connection in connections:
                        logging.info("Close connnection %s" % connection)
                        connection.shutdown(socket.SHUT_RDWR)
                        connection.close()
                tcpprocess.terminate()

        # Check if there is a new image to be displayed
        if not IMAGEQ.empty():
            new_image = IMAGEQ.get()
            logging.info("New image is: %s", new_image)
            crsl.pick(new_image)


if __name__ == "__main__":
    logging.info("Christie's Projector")
    parser = argparse.ArgumentParser(description='Project images.')
    parser.add_argument("-t", "--test",
                        help="Run projector in a window for testing",
                        action="store_true")
    args = parser.parse_args()
    main(args.test)
