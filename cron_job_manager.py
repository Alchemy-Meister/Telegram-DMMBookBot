from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
#from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED
from datetime import datetime, timedelta
from db_utils import Database, User, Manga, MangaSeries
import dmm_ripper as dmm
import logging
import utilities as utils
import pytz

class CronJobManager:
    
    __instance = None
    time_zone = pytz.timezone('Asia/Tokyo')
    start_hour = 3
    start_min = 0
    download_path = utils.get_abs_path('./downloads')
    jobs = {}
    logger = logging.getLogger(__name__)

    def __init__(self):

        if CronJobManager.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            self.update_cron_start_time()
            self.db_manager = Database.get_instance()
            jobstores = {
                # 'alchemy': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite'),
                'default': MemoryJobStore()
            }
            executors = {
                'default': {'type': 'threadpool', 'max_workers': 20},
                'processpool': ProcessPoolExecutor(max_workers=5)
            }
            job_defaults = {
                'coalesce': False,
                'max_instances': 3
            }
            self.scheduler = BackgroundScheduler()
            self.scheduler.configure(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=CronJobManager.time_zone,
                daemon=False)
            self.scheduler.start()
            CronJobManager.__instance = self

    def set_download_path(self, path):
        CronJobManager.download_path = utils.get_abs_path(path)

    def update_cron_start_time(self):
        now = datetime.now(CronJobManager.time_zone)
        self.cron_start_time = now.replace(
            hour=CronJobManager.start_hour, minute=CronJobManager.start_min
        )
        tomorrow_start_time = self.cron_start_time + timedelta(days=1)
        if now >= self.cron_start_time:
            self.cron_start_time = tomorrow_start_time
        return self.cron_start_time

    def update_user_library(self, user, session=None, password=None):
        CronJobManager.logger.info('Executing library caching job for ' \
            + 'user %s', user.id)
        self.scheduler.add_job(
            CronJobManager.__instance.cache_user_library,
            args=[user],
            kwargs={'session': session, 'password': password}
        )

    def schedule_user_cache(self, user):
        self.remove_scheduled_user_cache(user.id)

        CronJobManager.logger.info('Scheduling library caching job for ' \
            + 'user %s', user.id)
        job = self.scheduler.add_job(
            self.cache_user_library,
            'interval',
            args=[user],
            days=1,
            start_date=self.update_cron_start_time()
        )
        CronJobManager.jobs[user.id] = job

    def add_user_cache_scheduler(self, user, session=None):
        self.update_user_library(user, session)
        self.schedule_user_cache(user)

    @staticmethod
    def remove_scheduled_user_cache(user_id):
        if user_id in CronJobManager.jobs:
            CronJobManager.logger.info('Removing scheduled library caching ' \
                + 'job for user %s', user_id)
            CronJobManager.jobs[user_id].remove()
            del CronJobManager.jobs[user_id]

    @staticmethod
    def get_cache_expire_date():
        now = datetime.now(CronJobManager.time_zone)
        cache_expire_date = now.replace(
            hour=CronJobManager.start_hour, minute=CronJobManager.start_min
        )
        tomorrow_start_time = cache_expire_date + timedelta(days=1)
        if now >= cache_expire_date:
            return tomorrow_start_time.replace(tzinfo=None)
        return cache_expire_date.replace(tzinfo=None)

    @staticmethod
    def thumbnail(session, db_object, db_manager, parent=None):
        db_manager.flush(session)
        if db_object.id:
            if parent:
                thumbnail_path = '{}/{}-{}/{}-{}/thumbnail.jpg'.format(
                    CronJobManager.download_path, 
                    parent.title,
                    parent.id, 
                    db_object.title,
                    db_object.id
                )
            else:
                thumbnail_path = '{}/{}-{}/thumbnail.jpg'.format(
                    CronJobManager.download_path, db_object.title, db_object.id
            )
            if not utils.dir_exists(thumbnail_path):
                utils.create_dir(thumbnail_path.rsplit('/', 1)[0])
                dmm.download_image(db_object.thumbnail_dmm, thumbnail_path)
                CronJobManager.logger.info('Storing thubnail in %s', 
                    thumbnail_path
                )
                db_object.thumbnail_local = thumbnail_path
                try:
                    db_manager.commit(session)
                except Exception as e:
                    CronJobManager.logger.exception('Error updating local ' \
                        + 'thubnail\'s path for: %s', db_object.title)
                    db_manager.rollback(session)

    @staticmethod
    def cache_user_library(user, session=None, password=None, fast=False):
        db_manager = Database.get_instance()
        db_session = db_manager.create_session()
        db_manager.set_user_now_caching(db_session, user.id, True)
        CronJobManager.logger.info('Caching %s user\'s library', user.id)

        try:
            if session == None:
                if user.save_credentials:
                    password = user.password
                session = dmm.get_session(user.email, password, fast)
                CronJobManager.logger.info('Obtaining a new DMM session for ' \
                    + 'user %s', user.id)
            books = dmm.get_purchased_books(session)
            db_session.add(user)
            for book in books:
                if book['series']:
                    serie = db_manager.get_manga_serie(db_session, book['url'])
                    if not serie:
                        serie = MangaSeries(title=book['name'], url=book['url'], 
                            thumbnail_dmm=book['thumbnail'])
                        db_session.add(serie)
                        CronJobManager.logger.info('Adding a new serie to DB: '
                            + '%s', serie.title)
                        CronJobManager.thumbnail(db_session, serie, db_manager)
                    volumes = dmm.get_book_volumes(session, book)
                    for volume in volumes:
                        db_volume = db_manager.get_manga_volume(
                            db_session, volume['url']
                        )
                        if not db_volume:
                            db_volume = Manga(
                                title=volume['name'],
                                url=volume['url'],
                                thumbnail_dmm=volume['thumbnail'],
                                serie=serie
                            )
                            db_session.add(db_volume)
                            CronJobManager.logger.info('Adding a new volume ' \
                                + ' to DB: %s', db_volume.title)
                            CronJobManager.thumbnail(db_session,
                                db_volume, db_manager, parent=serie
                            )
                        if not db_manager.user_owns_volume(db_session,
                            user.id, db_volume.url):
                            CronJobManager.logger.info('Adding volume to ' \
                                + 'user %s', user.id)
                            try:
                                user.book_collection.append(db_volume)
                                db_manager.commit(db_session)
                            except Exception as e:
                                CronJobManager.logger.exception('Error ' \
                                    + 'adding volume to user %s', user.id)
                                db_manager.rollback(db_session)
                else:
                    book = db_manager.get_manga_volume(db_session, book['url'])
                    if not book:
                        book = Manga(title=book['name'], url=book['url'],
                            thumbnail_dmm=book['thumbnail'])
                        db_session.add(book)
                        CronJobManager.logger.info('Adding a new non series ' \
                            + 'book to DB: %s', book.title)
                        CronJobManager.thumbnail(db_session, book, db_manager)
                    if not db_manager.user_owns_volume(db_session, user.id,
                        book.url):
                        CronJobManager.logger.info('Adding non series book ' \
                            + 'to user %s', user.id)
                        try:
                            user.book_collection.append(book)
                            db_manager.commit(session)
                        except:
                            CronJobManager.logger.exception('Error adding ' \
                                + 'non series book to user %s', user.id)
                            db_manager.rollback(session)


            db_manager.set_user_cache_expire_date(
                db_session, user.id, CronJobManager.get_cache_expire_date()
            )
            db_manager.set_user_cache_built(db_session, user.id, True)
            db_manager.set_user_login_error(db_session, user.id, False)
        except Exception as e:
            CronJobManager.logger.info('Unable to login to the DMM account ' \
                + 'of user %s', user.id)
            db_manager.set_user_login_error(db_session, user.id, True)
            CronJobManager.remove_scheduled_user_cache(user.id)
        finally:
            CronJobManager.logger.info(
                '%s user\'s library caching ended', user.id
            )
            db_manager.set_user_now_caching(db_session, user.id, False)
            db_manager.remove_session()

    @staticmethod
    def get_instance():
        if CronJobManager.__instance == None:
            CronJobManager()
            CronJobManager.logger.info('CronJobManager singleton instanciated')
            session = CronJobManager.__instance.db_manager.create_session()
            CronJobManager.logger.info('Executing unprocessed library ' \
                + 'caching jobs')
            for user in CronJobManager.__instance.db_manager \
                .get_credentialed_users(session):
                
                if not user.login_error:
                    if user.cache_expire_date <= datetime.now():
                        CronJobManager.__instance.update_user_library(user)

                    CronJobManager.__instance.schedule_user_cache(user)
            CronJobManager.__instance.db_manager.remove_session()

        return CronJobManager.__instance 
