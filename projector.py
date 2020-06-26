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

# Networking
import threading
import socket
import pickle

import networking
import services

logging.basicConfig(
    filename="projector.log",
    level=logging.INFO,
    format='%(asctime)s %(thread)s %(levelname)-6s %(funcName)s:%(lineno)-5d %(message)s',
)
client_logger = logging.getLogger('client_handler')
projectr_logger = logging.getLogger('projectr')

IMAGEDIR = 'static/images/'
ALPHA_STEP = 0.025
# TCP config
TCP_IP = "127.0.0.1"  # local only
TCP_PORT = 5006


DEFAULT_SETTINGS = {
    'slideshow': {'delay': 20, 'loop': True},
    'fadeduration': 2,
    'lastimage': u'static/images/logo.jpg',
    'projectors': {
        'local': {
            'ip': TCP_IP,
            'port': TCP_PORT,
            'enabled': True,
            'name': 'Main',
            'current': '',
        }
    }
}


def fit_image(input_texture, display):
    """ Fit image to screen """
    # Ripped this from demo, think I understand it
    # Pretty sure this bit resizes textureture to display size
    # Get ratio of display to textureture
    x_ratio = display.width / input_texture.ix
    y_ratio = display.height / input_texture.iy
    if y_ratio < x_ratio:  # if y ratio is smaller than x ratio
        x_ratio = y_ratio  # make the ratios the same
    width, height = input_texture.ix * x_ratio, input_texture.iy * x_ratio
    # width, height = tex.ix, tex.iy
    x_position = (display.width - width) / 2
    y_position = (display.height - height) / 2

    return width, height, x_position, y_position


""" PROCESSES """


def slideshow(imagelist, cur_queue, killslideshowq):
    """ run slideshow """
    process = "Slideshow Process"

    settings = services.read_settings('settings.json', default_settings=DEFAULT_SETTINGS)
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
            except TypeError:
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
                ssproc = multiprocessing.Process(
                    target=slideshow, args=(data["images"],
                                            cur_queue,
                                            killslideshowq))
                ssproc.start()
                slideshowon = True
            elif data["action"] == "stopslideshow":
                ssproc.terminate()
            elif data["action"] == "sync":
                images = services.list_files(IMAGEDIR)
                print(images)
            elif data["action"] == "whatsplaying":
                settings = services.read_settings('settings.json', default_settings=DEFAULT_SETTINGS)
                networking.send_msg(connection, settings["lastimage"])
            else:
                logging.info("Unkown action: %s", data["action"])


def tcp_receiver(cur_queue, connections):
    """ Receive images via TCP """
    # Set up TCP
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logging.info('Starting up on %s port %s' % (TCP_IP, TCP_PORT))
    # bind server to address
    sock.bind((TCP_IP, TCP_PORT))
    sock.listen(1)

    cons = {}

    while True:
        logging.info("Waiting for a connection...")
        # Not sure if this is really necessary however,
        # It gives the connection a unique number
        # and adds it to the connections dictionary
        con_number = str(len(connections) + 1)
        logging.debug(con_number)
        cons[con_number], client_address = sock.accept()

        logging.info("Starting a new thread for client %s", str(client_address))
        threading.Thread(
            target=client_handler,
            args=(cons[con_number], client_address, cur_queue)
        )


class Carousel(object):
    """ The main object """
    display_settings = {
        "background": (0.0, 0.0, 0.0, 1.0), "frames_per_second": 20}

    def __init__(self, test=False):
        self.imagedict = {}
        self.process = "Carousel"
        if test:
            self.display = pi3d.Display.create(
                w=800, h=600, **self.display_settings)
        else:
            self.display = pi3d.Display.create(**self.display_settings)
        self.shader = pi3d.Shader("2d_flat")
        starting_image = self.get_starting_image()
        self.set_up_image(starting_image, 1, 0.1)
        self.focus = starting_image
        # Set up camera
        self.camera = pi3d.Camera.instance()
        self.camera.was_moved = False
        self.keyboard = pi3d.Keyboard()
        self.image_queue = multiprocessing.Queue()

    def get_starting_image(self):
        # Load the last image used
        # If there is a settings file, load most recent image
        settings = services.read_settings(
            settings_file='settings.json', default_settings=DEFAULT_SETTINGS)
        if not settings:
            services.write_settings(DEFAULT_SETTINGS, settings_file='settings.json')
            settings = services.read_settings(
                settings_file='settings.json', default_settings=DEFAULT_SETTINGS)
        logging.info("Last image: %s" % settings["lastimage"])
        return settings["lastimage"]

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
        services.update_setting('lastimage', new_image, file_name='settings.json')

    def update(self):
        """ Update image alphas """
        for image, detail in self.imagedict.items():
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

        for image, detail in self.imagedict.items():
            if detail["visible"] and detail["fading"]:
                first_image = detail["canvas"]
            elif detail["visible"]:
                second_image = detail["canvas"]

        first_image.draw()
        # If second image exists (fixes start up)
        if second_image:
            second_image.draw()

    def loop(self, tcpprocess, connections):
        logging.info("Start Projector process")
        while self.display.loop_running():
            self.update()
            self.draw()

            k = self.keyboard.read()
            if k > -1:
                if k == 27:
                    self.keyboard.close()
                    self.display.stop()
                    for connection in connections:
                        logging.info("Close connnection %s" % connection)
                        connection.shutdown(socket.SHUT_RDWR)
                        connection.close()
                    tcpprocess.terminate()

            # Check if there is a new image to be displayed
            if not self.image_queue.empty():
                new_image = self.image_queue.get()
                logging.info("New image is: %s", new_image)
                self.pick(new_image)


def main(test):
    # Set up image queue
    connections = multiprocessing.Manager().dict()

    crsl = Carousel(test)
    logging.info("Start TCP Receiver")
    tcpprocess = multiprocessing.Process(target=tcp_receiver,
                                         args=(crsl.image_queue, connections))
    tcpprocess.start()

    crsl.loop(tcpprocess, connections)


if __name__ == "__main__":
    logging.info("Christie's Projector")
    parser = argparse.ArgumentParser(description='Project images.')
    parser.add_argument("-t", "--test",
                        help="Run projector in a window for testing",
                        action="store_true")
    args = parser.parse_args()
    main(args.test)
