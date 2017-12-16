from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
#from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED
from datetime import datetime, timedelta
from db_utils import Database, User, Manga, MangaSeries
from cloud.sendclient import upload
from constants import FileFormat
from telegram import ParseMode
from uguuAPI import uploadfile
import dmm_ripper as dmm
import logging
import utilities as utils
import pytz
from os import path

class CronJobManager:
    
    __instance = None
    time_zone = pytz.timezone('Asia/Tokyo')
    start_hour = 3
    start_min = 0
    download_path = utils.get_abs_path('./downloads')
    jobs = {}
    book_job = {}
    lang = None
    logger = logging.getLogger(__name__)
    max_upload_size = None

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

    def register_book_job(self, book):
        CronJobManager.logger.info('Registering the job request of ' \
                + 'for book %s', book.id)
        formats = [e for e in FileFormat]
        format_dict = dict(
            (format_id,[]) for format_id in formats
        )
        CronJobManager.book_job[book.id] = {
            'download': [],
            'conversion': format_dict
        }

    def subscribe_to_book_download(self, book, user, bot, update, password=None):
        if book.id not in CronJobManager.book_job:
            self.register_book_job(book)
        if not any(job['user'].id == user.id \
            for job in CronJobManager.book_job[book.id]['download']):
            CronJobManager.logger.info('Subscribing user %s to download job ' \
                + 'of book %s', user.id, book.id)
            CronJobManager.book_job[book.id]['download'].append(
                {'user': user, 'password': password, 'bot': bot}
            )

    def subscribe_to_book_conversion(self, book, book_path, user, bot,
        from_download=False):
        
        execute_job = False
        file_format = None
        if book.id not in CronJobManager.book_job:
            self.register_book_job(book)

        if not any(job['user'].id == user.id for job in \
            CronJobManager.book_job[book.id]['conversion'][user.file_format]):
            
            CronJobManager.logger.info('Subscribing user %s to %s conversion ' \
                + 'job of book %s', user.id, FileFormat(user.file_format).name,
                book.id
            )
            if not len(CronJobManager.book_job[book.id]['conversion'] \
                [user.file_format]):
                execute_job = True
                file_format = user.file_format
            CronJobManager.book_job[book.id]['conversion'][user.file_format] \
                .append({
                    'user': user,
                    'bot': bot
                }
            )
            if execute_job:
                self.scheduler.add_job(
                    CronJobManager.__instance.convert_book_job,
                    args=[book_path, book, file_format],
                    kwargs={'from_download': from_download}
                )   


    def download_book_pages(self, book_path, missing_images, book, user,
        bot, update, password=None):
        self.subscribe_to_book_download(
            book, user, bot, update, password=password
        )
        self.scheduler.add_job(
            CronJobManager.__instance.download_book_pages_job,
            args=[book_path, missing_images, book]
        )

    @staticmethod
    def get_dmm_session_for_book_download(book):
        dmm_session = None
        for index, subscriber in enumerate(
            CronJobManager.book_job[book.id]['download']):
            
            user = subscriber['user']
            if subscriber['password']:
                password = subscriber['password']
            else:
                password = user.password
            try:
                CronJobManager.logger.info('Obtaining a new DMM session for ' \
                    + 'subscriber %s', user.id)
                dmm_session = dmm.get_session(user.email, password, False)
                break
            except Exception as e:
                CronJobManager.logger.info('Unable to login to the DMM ' \
                    + 'account of subscriber %s. Attempt %s out of %s', 
                    user.id,
                    index + 1,
                    len(CronJobManager.book_job[book.id]['download'])
                )
        return dmm_session

    @staticmethod
    def download_book_pages_job(book_path, missing_images, book):
        db_manager = Database.get_instance()
        db_session = db_manager.create_session()
        dmm_session = None
        CronJobManager.logger.info('Starting download job of book %s', book.id)
        db_manager.set_volume_now_downloading(db_session, book.id, True)
        num_miss_imgs = len(missing_images)
        for subscriber in CronJobManager.book_job[book.id]['download']:
            user = subscriber['user']
            subscriber['message'] = subscriber['bot'].send_message(
                chat_id = user.id,
                text = CronJobManager.lang[user.language_code]['downloading'] \
                    .format(utils.download_progress_bar(
                        book.pages - num_miss_imgs,
                        book.pages
                    )
                ),
                parse_mode=ParseMode.HTML
            )
        dmm_session = CronJobManager.get_dmm_session_for_book_download(book)

        if dmm_session:
            for index, page_num in enumerate(missing_images):
                book_vars = dmm.get_book_vars(dmm_session, book)
                page_url = dmm.get_page_download_url(book_vars, page_num)
                dmm.download_image(
                    page_url, path.join(book_path, '{}.jpg'.format(page_num))
                )
                for subscriber in CronJobManager.book_job[book.id]['download']:
                    user = subscriber['user']
                    try:
                        subscriber['bot'].edit_message_text(
                            CronJobManager.lang[user.language_code] \
                            ['downloading'].format(
                                utils.download_progress_bar(
                                    book.pages - num_miss_imgs + index + 1,
                                    book.pages
                                )
                            ),
                            chat_id=user.id,
                            message_id=subscriber['message'].message_id,
                            parse_mode=ParseMode.HTML
                        )
                    except:
                        pass # Download percentage not modified
            CronJobManager.logger.info('Download of book %s has finished',
                book.id)
            for subscriber in CronJobManager.book_job[book.id]['download']:
                user = subscriber['user']
                subscriber['bot'].send_message(
                    chat_id=user.id,
                    text=CronJobManager.lang[user.language_code] \
                        ['download_finished'].format(
                            FileFormat(user.file_format).name.upper()
                        )
                )
                CronJobManager.__instance.subscribe_to_book_conversion( \
                    book, book_path, subscriber['user'], subscriber['bot'], \
                    from_download=True
                )
        else:
            CronJobManager.logger.info('Unable to start the download of ' \
                + 'book %s', book.id)
            for subscriber in CronJobManager.book_job[book.id]:
                user = subscriber['user']
                CronJobManager.logger.info('Sending download error message ' \
                    + 'to subscriber %s', user.id)
                subscriber['bot'].send_message(
                    chat_id = user.id,
                    text = CronJobManager.lang[user.language_code] \
                        ['download_error']
                )
        db_manager.set_volume_now_downloading(db_session, book.id, False)
        CronJobManager.logger.info('Removing the registration of download ' \
            + 'job for book %s', book.id)
        CronJobManager.book_job[book.id]['download'] = []

    @staticmethod
    def convert_book_job(book_path, book, file_format, from_download=None):
        preferred_format = FileFormat(file_format).name
        CronJobManager.logger.info('Starting conversion job of book ' \
            + '%s to %s', book.id, preferred_format)
        if not from_download:
            for subscriber in CronJobManager.book_job[book.id]['conversion'] \
                [file_format]:

                user = subscriber['user']
                CronJobManager.logger.info('Sending %s book conversion start ' \
                    + 'message to user %s', book.id, user.id)
                subscriber['bot'].send_message(
                    chat_id=user.id,
                    text=CronJobManager.lang[user.language_code] \
                    ['start_conversion'].format(
                        book.title, preferred_format.upper()
                    )
                )
        file_format_path = utils.convert_book(file_format, book_path, book)
        for subscriber in CronJobManager.book_job[book.id]['conversion'] \
            [file_format]:
            
            bot = subscriber['bot']
            user = subscriber['user']
            
            if path.getsize(file_format_path) >= CronJobManager.max_upload_size:
                url = uploadfile(file_format_path)
                bot.send_message(chat_id=user.id,
                    text=CronJobManager.lang[user.language_code]['generate_url']
                )
                CronJobManager.__instance.generante_storage_url(
                    file_format_path, preferred_format, bot, user
                )
            else:
                CronJobManager.logger.info('Sending %s book transmission start '
                    + 'message to user %s', book.id, user.id)
                bot.send_message(
                    chat_id=user.id,
                    text=CronJobManager.lang[user.language_code] \
                        ['conversion_and_send']
                )
                CronJobManager.logger.info('Sending book %s in %s format to ' \
                    + 'user %s', book.id, preferred_format, user.id)
                bot.send_document(
                    chat_id=user.id,
                    document=open(file_format_path, 'rb'),
                    timeout=60
                )
        CronJobManager.book_job[book.id]['conversion'][file_format] = []

    def generante_storage_url(self, file_path, preferred_format, bot, user):
        self.scheduler.add_job(
            CronJobManager.__instance.generante_storage_url_job,
            args=[file_path, preferred_format, bot, user]
        )
    
    @staticmethod
    def generante_storage_url_job(file_path, preferred_format, bot, user):
        secretUrl, delete_token = upload.send_file(
            'https://send.firefox.com/', open(file_path, 'rb'),
            ignoreVersion=False,
            fileName='{}.{}'.format(
                utils.random_string(32),
                preferred_format)
            )
        bot.send_message(chat_id=user.id,
            text=CronJobManager.lang[user.language_code]['url_send'] \
                .format(secretUrl),
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML
        )

    @staticmethod
    def get_instance(languages=None, max_upload_size=None):
        if CronJobManager.__instance == None:
            if languages:
                CronJobManager.lang = languages
            if max_upload_size:
                CronJobManager.max_upload_size = max_upload_size
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
