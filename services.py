import logging
import os
import random

import json
from PIL import Image
import settings


def db_get_image(db, filename):
    return db.select(
        'images',
        where="filename=$filename",
        vars=locals())


def db_delete_image(db, filename):
    db.delete('images', where="filename=$filename", vars=locals())


def db_list_images(db, filename):
    """ List images in database """
    return db.select('images')


def rename_image(filename):
    """ Rename files with random string to ensure there are no clashes """
    randomstring = random.getrandbits(16)
    filename = filename[:-4] + '_' + str(randomstring) + filename[-4:]
    logging.info(filename)
    return filename


def write_settings(data, settings_file='uisettings.json'):
    """Write the previous image to settings file"""
    logging.info("Writing settings...")
    logging.info(data)
    with open(settings_file, 'w') as outfile:
        json.dump(data, outfile)


def read_settings(settings_file='uisettings.json', default_settings=None):
    """ Read settings from YAML file"""
    logging.info("Read settings...")
    try:
        with open(settings_file) as infile:
            data = json.load(infile)
        return data
    except IOError:
        logging.exception("Could not read settings")
        if default_settings:
            logging.info("Writing default settings file")
            with open(settings_file, 'w') as outfile:
                json.dump(default_settings, outfile)
            return default_settings
    except ValueError:
        logging.exception("Could not read settings")
        return None


def update_setting(setting_name, value, file_name='uisettings.json'):
    settings = read_settings(settings_file=file_name)
    settings[setting_name] = value
    write_settings(settings, settings_file=file_name)


def get_setting(setting_name, file_name='uisettings.json'):
    settings = read_settings(settings_file=file_name)
    return settings[setting_name]


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


def list_files(directory, reverse=False, video=False):
    """ Return list of files of specified type """
    filetypes = ('.mp4', '.webm') if video else ('.jpg', '.jpeg', '.png')
    output = [f for f in os.listdir(directory) if
              os.path.isfile(os.path.join(directory, f)) and
              f.endswith(filetypes)]

    if reverse:
        # Sort newFileList by date added(?)
        output.sort(key=lambda x: os.stat(os.path.join(directory, x)).st_mtime)
        output.reverse()  # reverse image list so new files are first

    return output
