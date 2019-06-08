import web

db = web.database(dbn="sqlite", db="images.db")
# CREATE TABLE images(Id INTEGER PRIMARY KEY, filename TEXT, imagename TEXT, folder TEXT);
