#! /usr/bin/env python
""" Web interface for the projector """
import logging
import os
from flask import Flask, render_template, request, redirect
from flask.views import MethodView
import settings
import services
import networking
import orm
db = orm.db
logging.basicConfig(
    filename="server.log",
    level=logging.INFO,
    format='%(asctime)s %(thread)s %(levelname)-6s %(funcName)s:%(lineno)-5d %(message)s',
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
db.init_app(app)

CONNECTION = networking.Connection()


class Index(MethodView):
    def get(self, display="local"):
        if display not in CONNECTION.PROJECTRS.keys():
            logging.info("Display %s not found" % (display))
            return render_template("displaynotfound.html",
                                   pagetitle="Display %s Not Found" % display,
                                   displays=CONNECTION.PROJECTRS,
                                   message="")

        # current_image = CONNECTION.whatsplaying("local")  # FIXME
        current_image = None
        images = orm.Image.query.all()
        imagelist = [(x.filename, x.imagename) for x in images]

        return render_template(
            "index.html",
            imagelist=imagelist,
            pagetitle="Display - %s" % CONNECTION.PROJECTRS[display]["name"],
            current_image=current_image[14:] if current_image else current_image,
            displays=CONNECTION.PROJECTRS,
            message="")

    def post(self, display="local"):
        action = request.form["action"]
        if action == "project":
            image = request.form["prop1"]
            logger.info(
                "action: %s, image: %s" % (action, image))
            CONNECTION.project("local", image)
            return True
        elif action == "slideshow":
            # TODO: Does this work?
            imagelist = [
                v for k, v in request.args.iteritems() if k != "action"]
            CONNECTION.slideshow("local", imagelist)
            return redirect('/')
        else:
            logger.info("Unknown Action %s" % action)
app.add_url_rule('/', view_func=Index.as_view('index'))
app.add_url_rule('/display/<string:display>', view_func=Index.as_view('display'))


class initNetwork(MethodView):
    def get(self):
        networking.init_network()
        return redirect('/')
app.add_url_rule('/initnetwork', view_func=initNetwork.as_view('initnetwork'))


class Settings(MethodView):
    def get(self):
        settingsdict = services.read_settings()
        return render_template("settings.html",
                               pagetitle="Settings",
                               settingsdict=settingsdict,
                               displays=networking.PROJECTRS,
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
                               displays=CONNECTION.PROJECTRS,
                               image=image)

    def post(self):
        print("---------")
        print(request.form)
        print("---------")
        image = request.form["image"]
        try:
            os.remove(os.path.join(settings.IMAGEDIR, image))
            logger.info("%s deleted" % image)
        except OSError:
            logger.exception("Deleting %s failed" % image)
        else:
            img = db.Image.query.filter_by(imagename=image).one_or_none()
            db.session.delete(img)
            db.session.commit()
        return redirect('/')
app.add_url_rule('/delete', view_func=Delete.as_view('delete'))


class Rename(MethodView):
    def get(self):
        filename = request.args["image"]
        imagename = services.db_get_image(filename)[0]["imagename"]
        return render_template("rename.html",
                               pagetitle="Rename",
                               image=filename,
                               displays=networking.PROJECTRS,
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
                               displays=CONNECTION.PROJECTRS,
                               message="")

    def post(self):
        if 'newimage' not in request.files:
            return

        newimage = request.files["newimage"]
        # replaces the windows-style slashes with linux ones.
        filepath = newimage.filename.replace('\\', '/')
        # splits the path and chooses the last part (the filename with extension)
        filename = filepath.split('/')[-1]
        imagename, file_extension = os.path.splitext(filename)
        filename = services.rename_image(filename)
        image = orm.Image(filename=filename, imagename=imagename)
        db.session.add(image)
        db.session.commit()

        newimagepath = os.path.join(settings.IMAGEDIR, filename)
        newimage.save(newimagepath)
        services.make_thumbnail(newimagepath)
        return redirect('/')
app.add_url_rule('/upload', view_func=Upload.as_view('upload'))


class Displays(MethodView):
    def get(self):
        logger.info(networking.connections)
        alive = [f for f in networking.connections]

        return render_template("displays.html",
                               pagetitle="Displays",
                               displays=networking.PROJECTRS,
                               alive=alive,
                               message="")

    def post(self):
        display = request.args["prop1"]
        message = {"action": "sync"}
        networking.send_msg_to_display(display, message)
        logger.info("sync %s" % display)
app.add_url_rule('/displays', view_func=Displays.as_view('displays'))


class Shutdown(MethodView):
    def get(self):
        return render_template("shutdown.html",
                               pagetitle="Shutdown?",
                               displays=networking.PROJECTRS,
                               message="")

    def post(self):
        shutdown = request.form["shutdown"]
        logger.info(shutdown)

        if shutdown == "true":
            logger.info("Shutdown")
            message = {"action": "project",
                       "images": ['static/img/shutdown.jpg']}
            # Should probably cycle through display and switch them off
            networking.send_msg_to_display("local", message)
            os.system("poweroff")
        else:
            logger.info("Don't shutdown")
            return redirect('/')
app.add_url_rule('/shutdown', view_func=Shutdown.as_view('shutdown'))


class Videos(MethodView):
    def get(self):
        videolist = services.list_files(settings.VIDEODIR, video=True)
        logger.info("User accessed index")
        return render_template("videos.html",
                               videolist=videolist,
                               pagetitle="Home",
                               displays=networking.PROJECTRS,
                               message="")

    def post(self, display="local"):
        # Check the action
        action = request.args["action"]

        # If project, project video
        if action == "project":
            prop1 = request.args["prop1"]  # THE video
            prop2 = request.args["prop2"]
            logger.info("action: %s, prop1: %s, prop2: %s" % (action, prop1, prop2))
            message = {"action": "project",
                       "video": [os.path.join(settings.VIDEODIR, prop1)]}
            networking.send_msg_to_display(display, message)
            logger.info("video to be projected is %s" % prop1)
            return True
        else:
            logger.info("Unknown Action %s" % action)
app.add_url_rule('/videos', view_func=Videos.as_view('videos'))


if __name__ == "__main__":
    CONNECTION.init_network()
    app.run(host="localhost", port=8000)
