import struct
import os
import socket
import logging
import pickle

import settings
import services


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


class Connection:
    def __init__(self):
        SETTINGS = services.read_settings(settings_file="settings.json")
        print(SETTINGS)
        if SETTINGS:
            self.PROJECTRS = SETTINGS["projectors"]
        else:
            self.PROJECTRS = []
        self.connections = {}

    @staticmethod
    def get_display_addr(display):
        return (display["ip"], display["port"])

    def init_network(self):
        logging.info("Check display connections")
        for display in self.PROJECTRS:
            if not self.PROJECTRS[display]["enabled"]:
                continue

            if display not in self.connections:
                logging.info("Display not in existing connections")
                self.connect_display(display)
            else:
                self.send_msg_to_display(display, "alive")
                try:
                    # Try to receive from connection to see if it is alive
                    recv_msg(self.connections[display])
                    logging.info("Already connected to %s" % display)
                except Exception:
                    logging.exception("Connection appears to be dead")
                    self.connect_display(display)
        logging.info("Connections: %s" % self.connections)

    def connect_display(self, display):
        """ Try and connect to a display
        This is a bit of a clusterfuck
        should probably re-engineer this """
        # Make a new socket
        logging.info("Connections: " % self.connections)
        try:
            logging.info("Remove display socket from connections")
            del self.connections[display]
        except KeyError:
            logging.info("Display doesn't exist in connections")

        # Make new socket it and add to connections dict
        self.connections[display] = socket.socket(socket.AF_INET,
                                             socket.SOCK_STREAM)
        logging.info("Socket made")
        # Set connections timeout low
        self.connections[display].settimeout(1)

        try:
            # try connecting to socket
            self.connections[display].connect(
                self.get_display_addr(self.PROJECTRS[display]))
            logging.info("Connected to %s" % display)
            # set socket timeout high
            self.connections[display].settimeout(20)
            return True
        except:
            logging.info("No displays found")
            # delete socket from dict, because it doesn't work
            del self.connections[display]
            # increment attempts
            return False

    def send_msg_to_display(self, display, msg):
        """ Send a message to a display """
        logging.info("Send message to display")
        msg = pickle.dumps(msg)
        logging.info(msg)
        sent = False
        attempts = 1
        while not sent and attempts < 4:
            try:
                sock = self.connections[display]
                sent = True
            except KeyError:
                logging.exception("Display %s doesn't exist" % display)
                logging.info("Reattach display, attempt %d" % attempts)
                display_connected = self.connect_display(display)

                if display_connected:
                    logging.info("Successfully reconnected display")
                else:
                    logging.info("Could not reattach display")
                    attempts += 1

        if display not in self.connections:
            logging.info("Could not send message, could not communicate with display")
            return
        # Prefix each message with a 4-byte length (network byte order)
        msg = struct.pack('>I', len(msg)) + msg

        # Try sending message, if broken pipe
        # Try creating new socket
        attempts = 0
        while attempts < 3:
            try:
                logging.info("Attempting to send message")
                sock.sendall(msg)
                logging.info("Sent message %s" % msg)
                break
            except socket.error as e:
                logging.info("Socket error: %s" % e)
                logging.info("Attempting to reconnect to display %s" % sock)
                logging.info(self.connections)
                connected = self.connect_display(display)
                if not connected:
                    attempts += 1

    def whatsplaying(self, display):
        message = {"action": "whatsplaying"}
        current_image = None
        self.send_msg_to_display(display, message)
        # Wait for reply
        try:
            current_image = recv_msg(self.connections[display])
            logging.info("Received TCP data: %s from %s" %
                         (current_image, self.connections[display]))
        except socket.timeout:
            logging.info("No reply, socket timed out")
        except KeyError:
            logging.info("Display not found")
        return current_image

    def project(self, display, image):
        message = {"action": "project",
                   "images": [os.path.join(settings.IMAGEDIR, image)]}
        self.send_msg_to_display(display, message)
        logging.info("Image to be projected is %s" % image)
        self.PROJECTRS[display]["current"] = image

    def slideshow(self, display, imagelist):
        message = {"action": "slideshow", "images": imagelist}
        self.send_msg_to_display(display, message)
