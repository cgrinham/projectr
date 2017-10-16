#! /usr/bin/env python
""" Web interface for the projector """

from __future__ import absolute_import, division, print_function, unicode_literals

import web
import os
from datetime import datetime
from PIL import Image
import random
import yaml
import sys
import dbus
# Networking
import socket
import pickle
import struct

# Set up UDP socket port 5005

TCP_PORT = 5006

# This should be moved out to a YAML file
PROJECTRS = {
    "local": {
              "ip": "127.0.0.1",
              "enabled": True,
              "name": "Centre",
              "current": ""
              },
    "pizero1": {
                "ip": "192.168.43.36",
                "enabled": False,
                "name": "Left",
                "current": ""
                },
    "pizero2": {
                "ip": "192.168.43.45",
                "enabled": False,
                "name": "Right",
                "current": ""
                }
    }

connections = {}

# Set up URLS

urls = (
    '/', 'Index',
    '/upload', 'Upload',
    '/settings', 'Settings',
    '/delete', 'Delete',
    '/shutdown', 'Shutdown',
    '/rename', 'Rename',
    '/videos', 'Videos',
    '/displays', 'Displays',
    '/display/(.+)', 'Index',
    '/initnetwork', 'initNetwork'
)

# Directories
IMAGEDIR = 'static/images/'
VIDEODIR = 'static/videos'
THUMBDIR = 'static/images/thumbs'


# Set up web.py app
app = web.application(urls, globals())

# Template Renderer
render = web.template.render('templates/', base="layout")

db = web.database(dbn="sqlite", db="images.db")
# CREATE TABLE images(Id INTEGER PRIMARY KEY, filename TEXT, imagename TEXT, folder TEXT);


# Image size maximums
WIDTH = 1920
HEIGHT = 1080

""" Functions """


# Use class for settings?
def db_list_images():
    """ List images in database """
    output = db.select('images')

    return output


def db_insert_image(filename):
    """ Insert an image into the database """
    imagename, file_extension = os.path.splitext(filename)
    filename = "%s.jpg" % ''.join(random.choice('0123456789abcdef') for i in range(16))

    imageid = db.insert('images', filename=filename,
                        imagename=imagename, folder="")
    print(imageid)


def write_settings(data):
    """Write the previous image to settings file"""
    print("Writing settings...")
    print(data)
    with open('settings.yml', 'w') as outfile:
        outfile.write(yaml.dump(data, default_flow_style=True))


def read_settings():
    """ Read settings from YAML file"""
    print("Read settings...")
    try:
        return yaml.load(open("settings.yml"))
    except:
        print("Could not read settings")
        return None


def write_log(logdata, process=""):
    """ Write to the log """
    if process == "":
        with open("server.log", "a") as myfile:
            myfile.write("%s : %s" % (datetime.now().strftime('%Y/%m/%d %H:%M'), logdata))
            print("%s : %s" % (datetime.now().strftime('%Y/%m/%d %H:%M'), logdata))

    else:
        with open("server.log", "a") as myfile:
            myfile.write("%s : %s : %s" % (datetime.now().strftime('%Y/%m/%d %H:%M'), process, logdata))
            print("%s : %s : %s" % (datetime.now().strftime('%Y/%m/%d %H:%M'),
                                    process, logdata))


def rename_image(filename):
    """ Rename files with random string to ensure there are no clashes """
    randomstring = random.getrandbits(16)
    filename = filename[:-4] + '_' + str(randomstring) + filename[-4:]
    print(filename)


def make_thumbnail(image):
    """ Make thumnail for given image """
    # if thumbnail doesn't exist
    if not os.path.exists(os.path.join(thumbdir, image)):
        imagepath = image
        print(get_logtime("%s: PIL - File to open is: %s" % (cur_process,
                                                             imagepath)))
        try:
            # open and convert to RGB
            img = Image.open(imagepath).convert('RGB')

            # find ratio of new height to old height
            hpercent = (float(HEIGHT) / float(img.size[1]))
            # apply ratio to create new width
            wsize = int(float(img.size[0]) * hpercent)
            # resize image with antialiasing
            img = img.resize((int(wsize), int(HEIGHT)), Image.ANTIALIAS)
            # save with quality of 80, optimise setting caused crash
            img.save(imagepath, format='JPEG', quality=90)
            write_log("Sucessfully resized: %s \n" % image)
        except IOError:
            write_log(
                "IO Error. %s will be deleted and downloaded properly next sync"
                 % imagepath)
            os.remove(imagepath)
    else:
        write_log("Thumbnail for %s exists \n" % image)


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


def connect_display(display):
    process = "connect_display"
    """ Try and connect to a display
    This is a bit of a clusterfuck
    should probably re-engineer this """
    # Make a new socket
    write_log("Connections: " % connections, process)
    try:
        write_log("Remove display socket from connections", process)
        del connections[display]
    except KeyError, e:
        write_log("Display doesn't exist in connections", process)

    # Get display address
    display_address = (PROJECTRS[display]["ip"], TCP_PORT)
    # Make new socket it and add to connections dict
    connections[display] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    write_log("Socket made", process)
    # Set connections timeout low
    connections[display].settimeout(1)

    try:
        # try connecting to socket
        connections[display].connect(display_address)
        write_log("Connected to %s" % display, process)
        # set socket timeout high
        connections[display].settimeout(20)
        return True
    except:
        write_log("No displays found", process)
        # delete socket from dict, because it doesn't work
        del connections[display]
        # increment attempts
        return False


def send_msg_display(display, msg):
    process = "Send Message To Display"
    """ Send a message to a display """
    write_log("Send message: %s" % msg, process)
    x = 0
    attempts = 1
    while x == 0 and attempts < 4:
        try:
            sock = connections[display]
            x = 1
        except:
            e = sys.exc_info()[0]
            write_log("Display %s doesn't exist: %s" % (display, e), process)

            write_log("Reattach display, attempt %d" % attempts, process)
            attempt = connect_display(display)

            if attempt is True:
                write_log("Successfully reconnected display", process)
            else:
                write_log("Could not reattach display", process)
                attempts += 1

    if display in connections:
        # Prefix each message with a 4-byte length (network byte order)
        msg = struct.pack('>I', len(msg)) + msg

        # Try sending message, if broken pipe
        # Try creating new socket
        x = 0
        attempts = 0

        while x < 1 and attempts < 3:
            try:
                write_log("Attempting to send message", process)
                sock.sendall(msg)
                write_log("Sent message %s" % msg)
                # success, quit loop
                x = 1
            except socket.error, e:
                write_log("Socket error: %s" % e, process)
                write_log("Attempting to reconnect to display %s" % sock,
                          process)
                write_log(connections)

                # Make a new socket
                del connections[display]
                # Get display address
                display_address = (PROJECTRS[display]["ip"], TCP_PORT)
                # Make new socket it and add to connections dict
                connections[display] = socket.socket(socket.AF_INET,
                                                     socket.SOCK_STREAM)
                write_log("Socket made", process)
                # Set connections timeout low
                connections[display].settimeout(1)

                try:
                    # try connecting to socket
                    connections[display].connect(display_address)
                    write_log("Connected to %s" % display, process)
                    # set socket timeout high
                    connections[display].settimeout(20)
                except:
                    write_log("Something fucked up", process)
                    # delete socket from dict, because it doesn't work
                    del connections[display]
                    # increment attempts
                    attempts += 1
    else:
        write_log("Could not send message, could not communicate with display",
                  process)


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


def init_network(connections):
    process = "Network Initialisation"
    write_log("Check display connections", process)
    for display in PROJECTRS:
        if PROJECTRS[display]["enabled"] is True:
            if display not in connections:
                write_log("Display not in existing connections", process)
                write_log("Connecting to display %s" % display, process)
                display_address = (PROJECTRS[display]["ip"], TCP_PORT)
                connections[display] = socket.socket(socket.AF_INET,
                                                     socket.SOCK_STREAM)
                write_log("Socket made", process)
                connections[display].settimeout(1)

                try:
                    connections[display].connect(display_address)
                    write_log("Connected to %s" % display, process)
                    connections[display].settimeout(20)
                except:
                    write_log("Something fucked up", process)
                    del connections[display]
            else:
                send_msg_display(display, "alive")
                try:
                    check = recv_msg(connections[display])
                    write_log("Already connected to %s" % display, process)
                except:
                    write_log("Connection appears to be dead", process)
                    del connections[display]
                    write_log("Connecting to display %s" % display, process)
                    display_address = (PROJECTRS[display]["ip"], TCP_PORT)
                    connections[display] = socket.socket(socket.AF_INET,
                                                         socket.SOCK_STREAM)
                    write_log("Socket made", process)
                    connections[display].settimeout(1)

                    try:
                        connections[display].connect(display_address)
                        write_log("Connected to %s" % display, process)
                        connections[display].settimeout(20)
                    except:
                        write_log("Something fucked up", process)
                        del connections[display]
    write_log("Connections: %s" % connections, process)


# Home Page
class Index(object):
    def GET(self, display="local"):

        current_display = display
        current_image = None

        # Check if the display exists
        if current_display in [f for f in PROJECTRS]:
            # Ask screen what is currently displayed
            message = pickle.dumps({"action": "whatsplaying"})
            send_msg_display(display, message)

            # Wait for reply
            try:
                current_image = recv_msg(connections[display])
                write_log("Received UDP data: %s from %s" %
                          (current_image, connections[display]))
            except socket.timeout:
                write_log("No reply, socket timed out")
            except KeyError, e:
                write_log("Display not found")

            images = db_list_images()
            imagelist = []

            for image in images:
                imagelist.append((image["filename"], image["imagename"]))

            if current_image is None:
                return render.index(imagelist, "Display - %s" %
                                    PROJECTRS[current_display]["name"],
                                    current_image, PROJECTRS, "")
            else:
                return render.index(imagelist, "Display - %s" %
                                    PROJECTRS[current_display]["name"],
                                    current_image[14:], PROJECTRS, "")
        else:
            write_log("Display %s not found" % (current_display))
            return render.displaynotfound("Display %s Not Found" %
                                          current_display, PROJECTRS, "")

    def POST(self, display="local"):
        print("Index POST")

        # Check the action
        action = web.input().action  # Project?

        # If project, project image
        if action == "project":
            prop1 = web.input().prop1  # THE IMAGE
            prop2 = web.input().prop2
            print("action: %s, prop1: %s, prop2: %s" % (action, prop1, prop2))
            message = pickle.dumps({"action": "project",
                                    "images": [os.path.join(IMAGEDIR, prop1)]})
            send_msg_display(display, message)
            print("Image to be projected is %s" % prop1)
            PROJECTRS[display]["current"] = prop1
            return True
        elif action == "slideshow":
            # Get contents of the input
            slideshow = web.input()

            imagelist = []

            # Get list of images
            for image in slideshow:
                if image != "action":
                    print(slideshow[image])
                    imagelist.append(slideshow[image])

            write_log(slideshow)

            message = pickle.dumps({"action": "slideshow", "images": "hello"})
            write_log(message)
            send_msg_display(display, message)
            raise web.seeother('/')
        else:
            print("Unknown Action %s" % action)


class Videos(object):
    def GET(self):
        # Get folders in users folders
        # imagelist = list_files(IMAGEDIR)

        videolist = [f for f in os.listdir(VIDEODIR) if
                     os.path.isfile(os.path.join(VIDEODIR, f)) and
                     f.endswith(('.mp4', '.webm'))]

        write_log("User accessed index")

        return render.videos(videolist, "Home", PROJECTRS, "")

    def POST(self):
        print("Index POST")

        # Check the action
        action = web.input().action  # Project?

        # If project, project video
        if action == "project":
            prop1 = web.input().prop1  # THE video
            prop2 = web.input().prop2
            print("action: %s, prop1: %s, prop2: %s" % (action, prop1, prop2))
            message = pickle.dumps({"action": "project",
                                    "video": [os.path.join(VIDEODIR, prop1)]})
            sock.sendto(message, (UDP_IP, UDP_PORT))
            print("video to be projected is %s" % prop1)
            return True
        else:
            print("Unknown Action %s" % action)


class initNetwork(object):
    def GET(self):
        init_network(connections)
        raise web.seeother('/')


class Settings(object):
    def GET(self):
        # Get settings
        settingsdict = read_settings()
        return render.settings("Settings", settingsdict, PROJECTRS, "")

    def POST(self):
        newsettings = web.input()
        # newsetting is <Storage {'slideshowlength': u'20'}>

        settings = read_settings()

        settings["slideshow"]["delay"] = int(newsettings["slideshowlength"])
        write_settings(settings)

        raise web.seeother('/')


class Delete(object):
    def GET(self):
        image = web.input().image

        return render.delete("Delete", PROJECTRS, image)

    def POST(self):
        image = web.input().image
        try:
            os.remove(os.path.join(IMAGEDIR, image))
            write_log("%s deleted" % image)
        except OSError, e:
            write_log("Deleting %s failed" % image)
            write_log("Error: %s" % e)

        db.delete('images', where="filename=$image", vars=locals())

        raise web.seeother('/')


class Rename(object):
    def GET(self):
        image = web.input().image

        # Get image name from database
        imagename = db.select('images', where="filename=$image",
                              vars=locals())[0]["imagename"]

        return render.rename("Rename", image, PROJECTRS, imagename)

    def POST(self):
        image = web.input().image
        newname = web.input().newname

        # Update image in database with new name
        db.update('images', where="filename=$image",
                  imagename=newname, vars=locals())

        raise web.seeother('/')


class Upload(object):
    def GET(self):
        return render.upload("Upload", PROJECTRS, "")

    def POST(self):
        image = web.input(newimage={})

        if 'newimage' in image:  # to check if the file-object is created
            # replaces the windows-style slashes with linux ones.
            filepath = image.newimage.filename.replace('\\', '/')
            # splits the path and chooses the last part (the filename with extension)
            imagename = filepath.split('/')[-1]
            imagename, file_extension = os.path.splitext(imagename)
            imagename = imagename

            filename = "%s.jpg" % ''.join(random.choice('0123456789abcdef') for i in range(16))

            newimagepath = os.path.join(IMAGEDIR, filename)

            # creates the file where the uploaded file should be stored
            fout = open(newimagepath, 'w')
            # writes the uploaded file to the newly created file.
            fout.write(image.newimage.file.read())
            fout.close()  # closes the file, upload complete.
            write_log("%s uploaded successfully" % imagename)
            write_log("Resizing %s" % imagename)

            # Add image to database
            imageid = db.insert('images', filename=filename,
                                imagename=imagename, folder="")
            print("Added %s to the database as ID %d" % (imagename, imageid))

            try:
                # open and convert to RGB
                img = Image.open(newimagepath).convert('RGB')

                # find ratio of new height to old height
                hpercent = (float(HEIGHT) / float(img.size[1]))
                # apply ratio to create new width
                wsize = int(float(img.size[0]) * hpercent)
                # resize image with antialiasing
                img = img.resize((int(wsize), int(HEIGHT)), Image.ANTIALIAS)
                # save with quality of 80, optimise setting caused crash
                # Delete original (in case it is a different filetype)
                # This needs to be changed!
                os.remove(newimagepath)
                newimagepath = os.path.splitext(newimagepath)[0] + ".jpg"
                img.save(newimagepath, format='JPEG', quality=90)
                write_log("Sucessfully resized: %s \n" % newimagepath)
            except IOError:
                write_log("IO Error. %s will be deleted and downloaded properly next sync" % newimagepath)
                os.remove(newimagepath)

        raise web.seeother('/')


class Displays(object):
    def GET(self):
        displays = PROJECTRS
        print(connections)
        alive = [f for f in connections]

        return render.displays("Displays", PROJECTRS, alive, "")

    def POST(self):
        display = web.input().prop1
        message = pickle.dumps({"action": "sync"})
        sock.sendto(message, (PROJECTRS[display]["ip"], UDP_PORT))

        print("sync %s" % display)


class Shutdown(object):
    def GET(self):
        return render.shutdown("Shutdown?", PROJECTRS, "")

    def POST(self):
        shutdown = web.input().shutdown
        print(shutdown)

        if shutdown == "true":
            print("Shutdown")
            message = pickle.dumps({"action": "project",
                                    "images": ['static/img/shutdown.jpg']})
            # Should probably cycle through display and switch them off
            send_msg_display("local", message)
            os.system("poweroff")
        else:
            print("Don't shutdown")
            raise web.seeother('/')


if __name__ == "__main__":
    init_network(connections)
    app.run()
