import logging
import os
import pickle
import random
import struct
import socket
import yaml
from PIL import Image
import settings
from orm import db

connections = {}


def db_list_images():
    """ List images in database """
    return db.select('images')


def db_insert_image(filename):
    """ Insert an image into the database """
    imagename, file_extension = os.path.splitext(filename)
    filename = "%s.jpg" % ''.join(random.choice('0123456789abcdef') for
                                  i in range(16))

    imageid = db.insert('images', filename=filename,
                        imagename=imagename, folder="")
    logging.info(imageid)


def write_settings(data):
    """Write the previous image to settings file"""
    logging.info("Writing settings...")
    logging.info(data)
    with open('uisettings.yml', 'w') as outfile:
        outfile.write(yaml.dump(data, default_flow_style=True))


def read_settings():
    """ Read settings from YAML file"""
    logging.info("Read settings...")
    try:
        return yaml.load(open("uisettings.yml"))
    except (IOError, yaml.composer.ComposerError):
        logging.exception("Could not read settings")
        return None


def rename_image(filename):
    """ Rename files with random string to ensure there are no clashes """
    randomstring = random.getrandbits(16)
    filename = filename[:-4] + '_' + str(randomstring) + filename[-4:]
    logging.info(filename)


def make_thumbnail(imagepath):
    """ Make thumnail for given image """
    # if thumbnail doesn't exist
    if os.path.exists(os.path.join(settings.THUMBDIR, imagepath)):
        logging.info("Thumbnail for %s exists \n" % imagepath)
        return

    logging.info("PIL - File to open is: %s" % imagepath)
    try:
        # open and convert to RGB
        img = Image.open(imagepath).convert('RGB')

        # find ratio of new height to old height
        hpercent = (float(settings.HEIGHT) / float(img.size[1]))
        # apply ratio to create new width
        wsize = int(float(img.size[0]) * hpercent)
        # resize image with antialiasing
        img = img.resize((int(wsize), int(settings.HEIGHT)), Image.ANTIALIAS)
        # save with quality of 80, optimise setting caused crash
        img.save(imagepath, format='JPEG', quality=90)
        logging.info("Sucessfully resized: %s \n" % imagepath)
    except IOError:
        logging.info(
            "IO Error. %s will be deleted and "
            "downloaded properly next sync"
            % imagepath)
        os.remove(imagepath)


def list_files(directory, reverse=False):
    """ Return list of files of specified type """
    output = [f for f in os.listdir(directory) if
              os.path.isfile(os.path.join(directory, f)) and
              f.endswith(('.jpg', '.jpeg', '.png'))]

    if reverse:
        # Sort newFileList by date added(?)
        output.sort(key=lambda x: os.stat(os.path.join(directory, x)).st_mtime)
        output.reverse()  # reverse image list so new files are first

    return output


SETTINGS = read_settings()
print(SETTINGS)
PROJECTRS = SETTINGS["projectors"]


def connect_display(display):
    """ Try and connect to a display
    This is a bit of a clusterfuck
    should probably re-engineer this """
    # Make a new socket
    logging.info("Connections: " % connections)
    try:
        logging.info("Remove display socket from connections")
        del connections[display]
    except KeyError as e:
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
            except:
                logging.info("Something went wrong")
                # delete socket from dict, because it doesn't work
                del connections[display]
                # increment attempts
                attempts += 1


def recv_msg(sock):
    # Read message length and unpack it into an integer
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    # Read the message data
    return recvall(sock, msglen)


def recvall(sock, n):
    """Helper function to recv n bytes or return None if EOF is hit"""
    data = ''

    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet

    return data


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
                check = recv_msg(connections[display])
                logging.info("Already connected to %s" % display)
            except:
                logging.info("Connection appears to be dead")
                connect_display(display)
    logging.info("Connections: %s" % connections)
