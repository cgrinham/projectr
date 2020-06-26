import struct
import socket
import logging
import pickle

import services

connections = {}


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


SETTINGS = services.read_settings(settings_file="settings.json")
print(SETTINGS)
if SETTINGS:
    PROJECTRS = SETTINGS["projectors"]
else:
    PROJECTRS = []


def connect_display(display):
    """ Try and connect to a display
    This is a bit of a clusterfuck
    should probably re-engineer this """
    # Make a new socket
    logging.info("Connections: " % connections)
    try:
        logging.info("Remove display socket from connections")
        del connections[display]
    except KeyError:
        logging.exception("Display doesn't exist in connections")

    # Get display address
    display_address = (PROJECTRS[display]["ip"], PROJECTRS[display]["port"])
    # Make new socket it and add to connections dict
    connections[display] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    logging.info("Socket made")
    # Set connections timeout low
    connections[display].settimeout(1)

    try:
        # try connecting to socket
        connections[display].connect(display_address)
        logging.info("Connected to %s" % display)
        # set socket timeout high
        connections[display].settimeout(20)
        return True
    except:
        logging.info("No displays found")
        # delete socket from dict, because it doesn't work
        del connections[display]
        # increment attempts
        return False


def send_msg_to_display(display, msg):
    """ Send a message to a display """
    logging.info("Send message to display")
    msg = pickle.dumps(msg)
    logging.info(msg)
    sent = False
    attempts = 1
    while not sent and attempts < 4:
        try:
            sock = connections[display]
            sent = True
        except KeyError:
            logging.exception("Display %s doesn't exist" % display)
            logging.info("Reattach display, attempt %d" % attempts)
            display_connected = connect_display(display)

            if display_connected:
                logging.info("Successfully reconnected display")
            else:
                logging.info("Could not reattach display")
                attempts += 1

    if display not in connections:
        logging.info("Could not send message, could not communicate with display")
        return
    # Prefix each message with a 4-byte length (network byte order)
    msg = struct.pack('>I', len(msg)) + msg

    # Try sending message, if broken pipe
    # Try creating new socket
    sent = False
    attempts = 0

    while not sent and attempts < 3:
        try:
            logging.info("Attempting to send message")
            sock.sendall(msg)
            logging.info("Sent message %s" % msg)
            # success, quit loop
            sent = True
        except socket.error as e:
            logging.info("Socket error: %s" % e)
            logging.info("Attempting to reconnect to display %s" % sock)
            logging.info(connections)

            # Make a new socket
            del connections[display]
            # Get display address
            display_address = (PROJECTRS[display]["ip"], PROJECTRS[display]["port"])
            # Make new socket it and add to connections dict
            connections[display] = socket.socket(socket.AF_INET,
                                                 socket.SOCK_STREAM)
            logging.info("Socket made")
            # Set connections timeout low
            connections[display].settimeout(1)

            try:
                # try connecting to socket
                connections[display].connect(display_address)
                logging.info("Connected to %s" % display)
                # set socket timeout high
                connections[display].settimeout(20)
            except Exception:
                logging.exception("Something went wrong")
                # delete socket from dict, because it doesn't work
                del connections[display]
                # increment attempts
                attempts += 1


def init_network():
    logging.info("Check display connections")
    for display in PROJECTRS:
        if not PROJECTRS[display]["enabled"]:
            continue

        if display not in connections:
            logging.info("Display not in existing connections")
            connect_display(display)
        else:
            send_msg_to_display(display, "alive")
            try:
                # Try to receive from connection to see if it is alive
                recv_msg(connections[display])
                logging.info("Already connected to %s" % display)
            except Exception:
                logging.exception("Connection appears to be dead")
                connect_display(display)
    logging.info("Connections: %s" % connections)
