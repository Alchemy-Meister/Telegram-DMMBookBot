from sqlalchemy import (Table, Column, ForeignKey, PrimaryKeyConstraint, 
    Integer, BigInteger, Boolean, TIMESTAMP, String, Enum, func)
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, contains_eager
from sqlalchemy import create_engine

from datetime import datetime

import utilities
import config
import enum
import os
import sys
 
Base = declarative_base()

class FileFormat(enum.Enum):
    jpg = 0
    pdf = 1
    epub = 2

user_manga_table = Table('user_manga', Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id')),
    Column('manga_volume_id', Integer, ForeignKey('manga_volume.id')),
    PrimaryKeyConstraint('user_id', 'manga_volume_id')
)

class User(Base):
    __tablename__ = 'user'
    id = Column(BigInteger, primary_key=True)
    language_code = Column(String(2))
    email = Column(String(50))
    password = Column(String(50))
    save_credentials = Column(Boolean(create_constraint=False))
    file_format = Column(Enum(FileFormat), default=FileFormat.pdf)
    cache_expire_date = Column(
        TIMESTAMP(timezone=False),
        default=datetime.now()
    )
    now_caching = Column(Boolean(create_constraint=False), default=False)
    cache_built = Column(Boolean(create_constraint=False), default=False)
    book_collection = relationship('Manga',
                    secondary=user_manga_table,
                    backref='owners', lazy='dynamic')

class MangaSeries(Base):
    __tablename__ = 'manga_serie'
    # Here we define columns for the table address.
    # Notice that each column is also a normal Python instance attribute.
    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    url = Column(String(500), unique=True)
    thumbnail = Column(String(300), unique=True)
    volumes = relationship('Manga', backref='serie', lazy='dynamic')

class Author(Base):
    __tablename__ = 'author'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    mangas = relationship('Manga', lazy='dynamic')

class Manga(Base):
    __tablename__ = 'manga_volume'
    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    url = Column(String(500), unique=True)
    thumbnail = Column(String(300), unique=True)
    pages = Column(Integer)
    author_id = Column(Integer, ForeignKey('author.id'))
    serie_id = Column(Integer, ForeignKey('manga_serie.id'))

class Database():

    db_schema_name = config.Config.DATABASE
    __instance = None

    def __init__(self):
        if Database.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            self.engine = create_engine('sqlite:///{}' \
                .format(Database.db_schema_name),
                connect_args={'check_same_thread':False},
                poolclass=StaticPool)

            if not Database.db_exists():
                self.create_schema()
            Base.metadata.bind = self.engine
            self.session = sessionmaker(bind=self.engine)()
            Database.__instance = self

    @staticmethod
    def get_instance():
        if Database.__instance == None:
            Database()
        return Database.__instance

    @staticmethod
    def db_exists():
        return utilities.dir_exists(Database.db_schema_name)

    def create_schema(self):
        Base.metadata.create_all(self.engine)

    def get_user(self, user_id):
        return self.session.query(User).filter(User.id == user_id).first()

    def user_owns_serie(self, user_id, url):
        return self.session.query(MangaSeries) \
            .join(Manga, MangaSeries.volumes, User.book_collection) \
            .filter(MangaSeries.url == url).filter(User.id == user_id).first()

    def get_user_library(self, user_id):
        books = self.session.query(Manga).join(User.book_collection) \
            .filter(User.id == user_id).filter(Manga.serie_id == None).all()

        series = self.session.query(MangaSeries).join(User.book_collection) \
            .filter(User.id == user_id).all()

        library = books + series
        library.sort(key=lambda x: x.title)
        return library

        # newlist = sorted(list_to_be_sorted, key=lambda k: k['name']) 

    def get_credentialed_users(self):
        return self.session.query(User).filter(User.password != None) \
            .filter(User.save_credentials == True).filter(User.email != None) \
            .all()

    def insert_user(self, user_id):
        self.session.add(User(id=user_id))
        self.session.commit()

        return self.get_user(user_id)

    def insert_book_serie(self, title, url):
        self.session.add(MangaSeries(title=title, url=url))
        self.session.commit()

    def set_user_language(self, user_id, language_code):
        self.session.query(User).filter_by(id=user_id) \
            .update({'language_code': language_code})
        self.session.commit()

    def set_user_email(self, user_id, email):
        self.session.query(User).filter_by(id=user_id).update({'email': email})
        self.session.commit()

    def set_save_credentials(self, user_id, save_credentials):
        self.session.query(User).filter_by(id=user_id) \
            .update({'save_credentials': save_credentials})
        self.session.commit()

    def set_user_password(self, user_id, password):
        self.session.query(User).filter_by(id=user_id) \
            .update({'password': password})
        self.session.commit()

    def set_user_file_format(self, user_id, file_format):
        self.session.query(User).filter_by(id=user_id) \
            .update({'file_format': file_format})
        self.session.commit()

    def set_user_cache_expire_date(self, user_id, cache_expire_date):
        self.session.query(User).filter_by(id=user_id) \
            .update({'cache_expire_date': cache_expire_date})
        self.session.commit()

    def set_user_now_caching(self, user_id, now_caching):
        self.session.query(User).filter_by(id=user_id) \
            .update({'now_caching': now_caching})
        self.session.commit()

    def set_user_cache_built(self, user_id, cache_built):
        self.session.query(User).filter_by(id=user_id) \
            .update({'cache_built': cache_built})
        self.session.commit()

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def flush(self):
        self.session.flush()

    def get_manga_serie(self, url):
        return self.session.query(MangaSeries).filter(MangaSeries.url == url) \
            .first()

if __name__ == '__main__':
    create_schema()