#! /usr/bin/env python
""" Web interface for the projector """
import logging
import os
import random
import socket
from flask import Flask, render_template, request, redirect
from flask.views import MethodView
from PIL import Image
import settings
import services
from orm import db


logging.basicConfig(
    filename="server.log",
    level=logging.INFO,
    format='%(asctime)s %(thread)s %(levelname)-6s %(funcName)s:%(lineno)-5d %(message)s',
)


app = Flask(__name__)


class Index(MethodView):
    def get(self, display="local"):
        current_image = None

        # Check if the display exists
        if display not in [f for f in services.PROJECTRS]:
            logging.info("Display %s not found" % (display))
            return render_template("displaynotfound.html",
                                   pagetitle="Display %s Not Found" % display,
                                   displays=services.PROJECTRS,
                                   message="")

        # Ask screen what is currently displayed
        message = {"action": "whatsplaying"}
        services.send_msg_to_display(display, message)

        # Wait for reply
        try:
            current_image = services.recv_msg(services.connections[display])
            logging.info("Received TCP data: %s from %s" %
                         (current_image, services.connections[display]))
        except socket.timeout:
            logging.info("No reply, socket timed out")
        except KeyError as e:
            logging.info("Display not found")

        images = services.db_list_images()
        imagelist = [(x["filename"], x["imagename"]) for x in images]

        if current_image is None:
            return render_template(
                "index.html",
                imagelist=imagelist,
                pagetitle="Display - %s" % services.PROJECTRS[display]["name"],
                current_image=current_image,
                displays=services.PROJECTRS,
                message="")

        return render_template(
            "index.html",
            imagelist=imagelist,
            pagetitle="Display - %s" % services.PROJECTRS[display]["name"],
            current_image=current_image[14:],
            displays=services.PROJECTRS,
            message="")

    def post(self, display="local"):
        action = request.form["action"]
        if action == "project":
            prop1 = request.form["prop1"]  # THE IMAGE
            prop2 = request.form["prop2"]
            logging.info("action: %s, prop1: %s, prop2: %s" % (action, prop1, prop2))
            message = {"action": "project",
                       "images": [os.path.join(settings.IMAGEDIR, prop1)]}
            services.send_msg_to_display(display, message)
            logging.info("Image to be projected is %s" % prop1)
            services.PROJECTRS[display]["current"] = prop1
            return True
        elif action == "slideshow":
            # TODO: This doesn't work at all
            imagelist = [v for k, v in request.args.iteritems() if k != "action"]
            message = {"action": "slideshow", "images": imagelist}
            services.send_msg_to_display(display, message)
            return redirect('/')
        else:
            logging.info("Unknown Action %s" % action)
app.add_url_rule('/', view_func=Index.as_view('index'))
app.add_url_rule('/display/<string:display>', view_func=Index.as_view('display'))


class initNetwork(MethodView):
    def get(self):
        services.init_network()
        return redirect('/')
app.add_url_rule('/initnetwork', view_func=initNetwork.as_view('initnetwork'))


class Settings(MethodView):
    def get(self):
        settingsdict = services.read_settings()
        return render_template("settings.html",
                               pagetitle="Settings",
                               settingsdict=settingsdict,
                               displays=services.PROJECTRS,
                               message="")

    def post(self):
        settings = services.read_settings()
        settings["slideshow"]["delay"] = int(request.args["slideshowlength"])
        services.write_settings(settings)
        return redirect('/')
app.add_url_rule('/settings', view_func=Settings.as_view('settings'))


class Delete(MethodView):
    def get(self):
        image = request.args["image"]
        return render_template("delete.html",
                               pagetitle="Delete",
                               displays=services.PROJECTRS,
                               image=image)

    def post(self):
        image = request.args["image"]
        try:
            os.remove(os.path.join(settings.IMAGEDIR, image))
            logging.info("%s deleted" % image)
        except OSError as e:
            logging.exception("Deleting %s failed" % image)
        db.delete('images', where="filename=$image", vars=locals())
        return redirect('/')
app.add_url_rule('/delete', view_func=Delete.as_view('delete'))


class Rename(MethodView):
    def get(self):
        image = request.args["image"]
        imagename = db.select('images', where="filename=$image",
                              vars=locals())[0]["imagename"]
        return render_template("rename.html",
                               pagetitle="Rename",
                               image=image,
                               displays=services.PROJECTRS,
                               message=imagename)

    def post(self):
        image = request.form["image"]
        newname = request.form["newname"]
        db.update('images', where="filename=$image",
                  imagename=newname, vars=locals())
        return redirect('/')
app.add_url_rule('/rename', view_func=Rename.as_view('rename'))


class Upload(MethodView):
    def get(self):
        return render_template("upload.html",
                               pagetitle="Upload",
                               displays=services.PROJECTRS,
                               message="")

    def post(self):

        if 'newimage' not in request.files:
            return

        newimage = request.files["newimage"]
        # replaces the windows-style slashes with linux ones.
        filepath = newimage.filename.replace('\\', '/')
        # splits the path and chooses the last part (the filename with extension)
        imagename = filepath.split('/')[-1]
        imagename, file_extension = os.path.splitext(imagename)

        filename = "%s.jpg" % ''.join(random.choice('0123456789abcdef') for
                                      i in range(16))

        newimagepath = os.path.join(settings.IMAGEDIR, filename)
        newimage.save(newimagepath)

        logging.info("%s uploaded successfully" % imagename)
        logging.info("Resizing %s" % imagename)

        imageid = db.insert('images', filename=filename,
                            imagename=imagename, folder="")
        logging.info("Added %s to the database as ID %d" % (imagename, imageid))

        try:
            # open and convert to RGB
            img = Image.open(newimagepath).convert('RGB')

            # find ratio of new height to old height
            hpercent = (float(settings.HEIGHT) / float(img.size[1]))
            # apply ratio to create new width
            wsize = int(float(img.size[0]) * hpercent)
            # resize image with antialiasing
            img = img.resize((int(wsize), int(settings.HEIGHT)), Image.ANTIALIAS)
            # save with quality of 80, optimise setting caused crash
            # Delete original (in case it is a different filetype)
            # This needs to be changed!
            os.remove(newimagepath)
            newimagepath = os.path.splitext(newimagepath)[0] + ".jpg"
            img.save(newimagepath, format='JPEG', quality=90)
            logging.info("Sucessfully resized: %s \n" % newimagepath)
        except IOError:
            logging.info("IO Error. %s will be deleted and downloaded properly next sync" % newimagepath)
            os.remove(newimagepath)

        return redirect('/')
app.add_url_rule('/upload', view_func=Upload.as_view('upload'))


class Displays(MethodView):
    def get(self):
        logging.info(services.connections)
        alive = [f for f in services.connections]

        return render_template("displays.html",
                               pagetitle="Displays",
                               displays=services.PROJECTRS,
                               alive=alive,
                               message="")

    def post(self):
        display = request.args["prop1"]
        message = {"action": "sync"}
        services.send_msg_to_display(display, message)
        logging.info("sync %s" % display)
app.add_url_rule('/displays', view_func=Displays.as_view('displays'))


class Shutdown(MethodView):
    def get(self):
        return render_template("shutdown.html",
                               pagetitle="Shutdown?",
                               displays=services.PROJECTRS,
                               message="")

    def post(self):
        shutdown = request.form["shutdown"]
        logging.info(shutdown)

        if shutdown == "true":
            logging.info("Shutdown")
            message = {"action": "project",
                       "images": ['static/img/shutdown.jpg']}
            # Should probably cycle through display and switch them off
            services.send_msg_to_display("local", message)
            os.system("poweroff")
        else:
            logging.info("Don't shutdown")
            return redirect('/')
app.add_url_rule('/shutdown', view_func=Shutdown.as_view('shutdown'))


class Videos(MethodView):
    def get(self):
        videolist = [f for f in os.listdir(settings.VIDEODIR) if
                     os.path.isfile(os.path.join(settings.VIDEODIR, f)) and
                     f.endswith(('.mp4', '.webm'))]

        logging.info("User accessed index")
        return render_template("videos.html",
                               videolist=videolist,
                               pagetitle="Home",
                               displays=services.PROJECTRS,
                               message="")

    def post(self, display="local"):
        # Check the action
        action = request.args["action"]

        # If project, project video
        if action == "project":
            prop1 = request.args["prop1"]  # THE video
            prop2 = request.args["prop2"]
            logging.info("action: %s, prop1: %s, prop2: %s" % (action, prop1, prop2))
            message = {"action": "project",
                       "video": [os.path.join(settings.VIDEODIR, prop1)]}
            services.send_msg_to_display(display, message)
            logging.info("video to be projected is %s" % prop1)
            return True
        else:
            logging.info("Unknown Action %s" % action)
app.add_url_rule('/videos', view_func=Videos.as_view('videos'))


if __name__ == "__main__":
    services.init_network()
    app.run(host="localhost", port=8000)
