from sqlalchemy import (Table, Column, ForeignKey, PrimaryKeyConstraint, 
    Integer, BigInteger, Boolean, TIMESTAMP, String, Enum, func)
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (scoped_session, relationship, sessionmaker,
    contains_eager)
from sqlalchemy import create_engine
from sqlalchemy_utils import force_auto_coercion, EncryptedType
from constants import FileFormat
from datetime import datetime
from data.config import Config
import logging
import os
import sys
import utilities as utils

force_auto_coercion()

Base = declarative_base()

user_manga_table = Table('user_manga', Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id')),
    Column('manga_volume_id', Integer, ForeignKey('manga_volume.id')),
    PrimaryKeyConstraint('user_id', 'manga_volume_id')
)

class User(Base):
    __tablename__ = 'user'
    id = Column(BigInteger, primary_key=True)
    language_code = Column(String(2))
    email = Column(EncryptedType(String, Config.SECRET_KEY))
    password = Column(EncryptedType(String, Config.SECRET_KEY))
    save_credentials = Column(Boolean(create_constraint=False))
    file_format = Column(Enum(FileFormat), default=FileFormat.pdf)
    cache_expire_date = Column(
        TIMESTAMP(timezone=False), default=datetime.now()
    )
    now_caching = Column(Boolean(create_constraint=False), default=False)
    cache_built = Column(Boolean(create_constraint=False), default=False)
    login_error = Column(Boolean(create_constraint=False), default=False)
    book_collection = relationship(
        'Manga', secondary=lambda: user_manga_table
    )

class MangaSeries(Base):
    __tablename__ = 'manga_serie'
    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    url = Column(String(500), unique=True)
    thumbnail_dmm = Column(String(300), unique=True)
    thumbnail_local = Column(String(300), unique=True)
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
    thumbnail_dmm = Column(String(300), unique=True)
    thumbnail_local = Column(String(300), unique=True)
    description = Column(String(5000))
    pages = Column(Integer)
    author_id = Column(Integer, ForeignKey('author.id'))
    serie_id = Column(Integer, ForeignKey('manga_serie.id'))
    now_downloading = Column(Boolean(create_constraint=False), default=False)

class Database():

    db_schema_name = Config.DATABASE
    logger = logging.getLogger(__name__)
    __instance = None

    def __init__(self):
        if Database.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            self.engine = create_engine('sqlite:///{}' \
                .format(Database.db_schema_name)
            )
            if not Database.db_exists():
                self.create_schema()
            Base.metadata.bind = self.engine
            self.session_manager = scoped_session(
                sessionmaker(
                    bind=self.engine, 
                    expire_on_commit=False,
                    autoflush=True
                )
            )
            Database.__instance = self

    @staticmethod
    def get_instance():
        if Database.__instance == None:
            Database.logger.info('Database singleton instantiated')
            Database()
        return Database.__instance

    @staticmethod
    def db_exists():
        return utils.dir_exists(Database.db_schema_name)

    def create_schema(self):
        Base.metadata.create_all(self.engine)

    def create_session(self):
        return self.session_manager()

    def remove_session(self):
        self.session_manager.remove()

    def get_user(self, session, user_id):
        return session.query(User).filter(User.id == user_id).first()

    def get_user_library(self, session, user_id):
        books = session.query(Manga).join(User.book_collection) \
            .filter(User.id == user_id).filter(Manga.serie_id == None).all()

        series = session.query(MangaSeries).join(User.book_collection) \
            .filter(User.id == user_id).all()

        library = books + series
        library.sort(key=lambda x: x.title)
        return library

    def get_user_library_by_title(self, session, user_id, title):
        filters = [User.id == user_id, Manga.serie_id == None]
        if not title.isspace():
            filters.append(Manga.title.like('%{}%'.format(title)))
        books = session.query(Manga).join(User.book_collection) \
            .filter(*filters).all()
        filters = [User.id == user_id]
        if not title.isspace():
            filters.append(MangaSeries.title.like('%{}%'.format(title)))
        series = session.query(MangaSeries).join(User.book_collection) \
            .filter(*filters).all()
        library = books + series
        library.sort(key=lambda x: x.title)
        return library

    def get_user_volumes_from_serie(self, session, user_id, series_id, title):
        filters = [Manga.serie_id == series_id, User.id == user_id]
        if not title.isspace():
            filters.append(Manga.title.like('%{}%'.format(title)))
        return session.query(Manga).join(User.book_collection) \
            .filter(*filters).all()

    def get_credentialed_users(self, session):
        return session.query(User).filter(User.password != None) \
            .filter(User.save_credentials == True).filter(User.email != None) \
            .all()

    def insert_user(self, session, user_id):
        Database.logger.info('saving new user %s into DB', user_id)
        session.add(User(id=user_id))
        session.commit()

        return self.get_user(session, user_id)

    def insert_book_serie(self, session, title, url):
        session.add(MangaSeries(title=title, url=url))
        session.commit()

    def set_user_language(self, session, user_id, language_code):
        Database.logger.info('Updating the language for user %s', user_id)
        session.query(User).filter_by(id=user_id) \
            .update({'language_code': language_code})
        session.commit()

    def set_user_email(self, session, user_id, email):
        Database.logger.info('Updating the email for user %s', user_id)
        session.query(User).filter_by(id=user_id).update({'email': email})
        session.commit()

    def set_save_credentials(self, session, user_id, save_credentials):
        Database.logger.info('Updating the credential preference for user %s',
            user_id)
        session.query(User).filter_by(id=user_id) \
            .update({'save_credentials': save_credentials})
        session.commit()

    def set_user_password(self, session, user_id, password):
        Database.logger.info('Updating the password for user %s', user_id)
        session.query(User).filter_by(id=user_id) \
            .update({'password': password})
        session.commit()

    def set_user_file_format(self, session, user_id, file_format):
        Database.logger.info('Updating the file format preference for user %s',
            user_id)
        session.query(User).filter_by(id=user_id) \
            .update({'file_format': file_format})
        session.commit()

    def set_user_cache_expire_date(self, session, user_id, cache_expire_date):
        Database.logger.info('Updating the cache expiration date for user %s',
            user_id)
        session.query(User).filter_by(id=user_id) \
            .update({'cache_expire_date': cache_expire_date})
        session.commit()

    def set_user_now_caching(self, session, user_id, now_caching):
        Database.logger.info('Updating the now caching flag for user %s',
            user_id)
        session.query(User).filter_by(id=user_id) \
            .update({'now_caching': now_caching})
        session.commit()

    def set_user_cache_built(self, session, user_id, cache_built):
        Database.logger.info('Updating the cache built flag for user %s',
            user_id)
        session.query(User).filter_by(id=user_id) \
            .update({'cache_built': cache_built})
        session.commit()

    def set_user_login_error(self, session, user_id, login_error):
        Database.logger.info('Updating the logging error flag for user %s',
            user_id)
        session.query(User).filter_by(id=user_id) \
            .update({'login_error': login_error})
        session.commit()

    def user_owns_volume(self, session, user_id, url):
        return session.query(Manga).join(User.book_collection) \
            .filter(User.id == user_id).filter(Manga.url == url).first()

    def get_manga_serie(self, session, url):
        return session.query(MangaSeries).filter(MangaSeries.url == url) \
            .first()

    def get_manga_volume(self, session, url):
        return session.query(Manga).filter(Manga.url == url).first()

    def get_volume_by_id(self, session, volume_id):
        return session.query(Manga).filter(Manga.id == volume_id).first()

    def set_volume_now_downloading(self, session, volume_id, now_downloading):
        Database.logger.info(
            'Updating the now downloading flag for volume %s', volume_id
        )
        session.query(Manga).filter_by(id=volume_id) \
            .update({'now_downloading': now_downloading})
        session.commit()

    def commit(self, session):
        session.commit()

    def rollback(self, session):
        session.rollback()

    def flush(self, session):
        session.flush()

    def expunge(self, session, object):
        session.expunge(object)