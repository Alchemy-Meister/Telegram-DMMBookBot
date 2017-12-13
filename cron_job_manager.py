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
import os

class CronJobManager:
    
    __instance = None
    time_zone = pytz.timezone('Asia/Tokyo')
    start_hour = 3
    start_min = 0
    download_path = utils.get_abs_path('./downloads')
    jobs = {}
    book_job = {}
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
                        serie = MangaSeries(
                            title=book['name'],
                            url=book['url'], 
                            thumbnail_dmm=book['thumbnail']
                        )
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
                            volume_details = dmm.get_book_details(
                                session, volume['details_url']
                            )
                            db_volume = Manga(
                                title=volume['name'],
                                url=volume['url'],
                                thumbnail_dmm=volume['thumbnail'],
                                description=volume_details['description'],
                                pages=volume_details['pages'],
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
                        book_details = dmm.get_book_details(
                            session, book['details_url']
                        )
                        book = Manga(
                            title=book['name'],
                            url=book['url'],
                            thumbnail_dmm=book['thumbnail'], 
                            description=book_details['description'],
                            pages=book_details['pages'],
                            serie=serie
                        )
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

    def subcribe_to_book_download(self, book, user, bot, update, password=None):
        if book.id not in CronJobManager.book_job:
            CronJobManager.logger.info('Registering the download request of ' \
                + 'book %s', book.id)
            CronJobManager.book_job[book.id] = []
        if not any(job['user'].id == user.id \
            for job in CronJobManager.book_job[book.id]):
            CronJobManager.logger.info('Subscribing user %s to download job ' \
                + 'of book %s', user.id, book.id)
            CronJobManager.book_job[book.id].append(
                {'user': user, 'password': password, 'bot': bot, 'chat': update}
            )

    def download_book_pages(self, book_path, missing_images, book, user,
        bot, update, password=None):
        self.subcribe_to_book_download(
            book, user, bot, update, password=password
        )
        self.scheduler.add_job(
            CronJobManager.__instance.download_book_pages_job,
            args=[book_path, missing_images, book]
        )

    @staticmethod
    def get_dmm_session_for_book_download(book):
        dmm_session = None
        for index, subcriber in enumerate(CronJobManager.book_job[book.id]):
            user = subcriber['user']
            if subcriber['password']:
                password = subcriber['password']
            else:
                password = user.password
            try:
                CronJobManager.logger.info('Obtaining a new DMM session for ' \
                    + 'subcriber %s', user.id)
                dmm_session = dmm.get_session(user.email, password, False)
                break
            except Exception as e:
                CronJobManager.logger.info('Unable to login to the DMM ' \
                    + 'account of subscriber %s. Attempt %s out of %s', 
                    user.id, index + 1, len(CronJobManager.book_job[book.id])
                )
        return dmm_session

    @staticmethod
    def download_book_pages_job(book_path, missing_images, book):
        db_manager = Database.get_instance()
        db_session = db_manager.create_session()
        dmm_session = None
        CronJobManager.logger.info('Starting download job of book %s', book.id)
        db_manager.set_volume_now_downloading(db_session, book.id, True)
        dmm_session = CronJobManager.get_dmm_session_for_book_download(book)

        if dmm_session:
            for page_num in missing_images:
                for subcriber in CronJobManager.book_job[book.id]:
                    if 'message' not in subcriber:
                        subcriber['message'] = subcriber['bot'].send_message(
                            chat_id = subcriber['user'].id,
                            text = 'DOWNLOADING!\nPAGE {} out of {}' \
                                .format(page_num, book.pages)
                        )
                    else:
                        subcriber['bot'].edit_message_text(
                            'DOWNLOADING!\nPAGE {} out of {}' \
                                .format(page_num, book.pages),
                            chat_id=subcriber['user'].id,
                            message_id=subcriber['message'].message_id
                        )
                book_vars = dmm.get_book_vars(dmm_session, book)
                page_url = dmm.get_page_download_url(book_vars, page_num)
                dmm.download_image(
                    page_url, os.path.join(book_path, '{}.jpg'.format(page_num))
                )
            CronJobManager.logger.info('Download of book %s has finished',
                book.id)
            for subcriber in CronJobManager.book_job[book.id]:
                subcriber['bot'].send_message(
                    chat_id=subcriber['user'].id,
                    text='DOWNLOAD FINISHED! Converting to PDF'
                )
            pdf_path = utils.convert_book2pdf(book_path, book)
            for subcriber in CronJobManager.book_job[book.id]:
                bot = subcriber['bot']
                bot.send_message(
                    chat_id=subcriber['user'].id,
                    text='Conversion to PDF finished! Now sending.'
                )
                bot.send_document(
                    chat_id=subcriber['user'].id,
                    document=open(pdf_path, 'rb'),
                    timeout=60
                )
        else:
            CronJobManager.logger.info('Unable to start the download of ' \
                + 'book %s', book.id)
            for subcriber in CronJobManager.book_job[book.id]:
                user = subcriber['user']
                CronJobManager.logger.info('Sending download error message ' \
                    + 'to subscriber %s', user.id)
                subcriber['bot'].send_message(
                    chat_id = user.id,
                    text = 'UNABLE TO FUCKING DOWNLOAD THE BOOK!'
                )
        db_manager.set_volume_now_downloading(db_session, book.id, False)
        CronJobManager.logger.info('Removing the registration of download ' \
            + 'job for book %s', book.id)
        del CronJobManager.book_job[book.id]

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
