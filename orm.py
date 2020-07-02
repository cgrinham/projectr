from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# CREATE TABLE images(Id INTEGER PRIMARY KEY, filename TEXT, imagename TEXT, folder TEXT);
class Image(db.Model):
    Id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String())
    imagename = db.Column(db.String())
    folder = db.Column(db.String())
