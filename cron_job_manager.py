import pytz
from datetime import datetime, timedelta

from db_utils import Database, User, Manga, MangaSeries
import dmm_ripper as dmm
import utilities as utils

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ProcessPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED

class CronJobManager:
    
    __instance = None
    time_zone = pytz.timezone('Asia/Tokyo')
    start_hour = 3
    start_min = 0
    download_path = utils.get_abs_path('./downloads')

    def __init__(self):

        if CronJobManager.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            self.update_cron_start_time()
            self.db_manager = Database.get_instance()
            self.jobs = {}

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
        self.scheduler.add_job(
            CronJobManager.__instance.cache_user_library,
            args=[user],
            kwargs={'session': session, 'password': password}
        )

    def remove_scheduled_user_cache(self, user_id):
        if user_id in self.jobs:
            self.jobs[user_id].remove()
            del self.jobs[user_id]

    def schedule_user_cache(self, user):
        self.remove_scheduled_user_cache(user.id)

        job = self.scheduler.add_job(
            self.cache_user_library,
            'interval',
            args=[user],
            days=1,
            start_date=self.update_cron_start_time()
        )
        self.jobs[user.id] = job

    def add_user_cache_scheduler(self, user, session=None):
        self.update_user_library(user, session)
        self.schedule_user_cache(user)

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
    def thumbnail(db_object, db_manager, parent=None):
        db_manager.flush()
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
                dmm.download_image(db_object.thumbnail, thumbnail_path)
                db_object.thumbnail = thumbnail_path
                try:
                    db_manager.commit()
                except Exception as e:
                    db_manager.rollback()

    @staticmethod
    def cache_user_library(user, session=None, password=None, fast=False):
        db_manager = Database.get_instance()
        db_manager.set_user_now_caching(user.id, True)
        print('{} user\'s cache running'.format(user.id))

        try:
            if session == None:
                if user.save_credentials:
                    password = user.password
                session = dmm.get_session(user.email, password, fast)
            books = dmm.get_purchased_books(session)

            for book in books:
                if book['series']:
                    serie = MangaSeries(title=book['name'], url=book['url'], 
                        thumbnail=book['thumbnail'])

                    volumes = dmm.get_book_volumes(session, book)
                    for volume in volumes:
                        db_volume = Manga(
                            title=volume['name'],
                            url=volume['url'],
                            thumbnail=volume['thumbnail'],
                            serie=serie
                        )
                        try:
                            user.book_collection.append(db_volume)
                            db_manager.commit()
                            CronJobManager.thumbnail(
                                db_volume, db_manager, parent=serie
                            )
                        except Exception as e:
                            db_manager.rollback()

                    CronJobManager.thumbnail(serie, db_manager)
                else:
                    book = Manga(title=book['name'], url=book['url'])
                    try:
                        user.book_collection.append(book)
                        db_manager.commit()
                    except:
                        db_manager.rollback()

            db_manager.set_user_cache_expire_date(
                user.id, CronJobManager.get_cache_expire_date()
            )
        except Exception as e:
            print(e)
        print('{} user\'s cache ended'.format(user.id))
        db_manager.set_user_now_caching(user.id, False)
        db_manager.set_user_cache_built(user.id, True)

    @staticmethod
    def get_instance():
        if CronJobManager.__instance == None:
            CronJobManager()

            for user in CronJobManager.__instance.db_manager \
                .get_credentialed_users():
                
                if user.cache_expire_date <= datetime.now():
                    print('execute last unprocessed job.')
                    CronJobManager.__instance.update_user_library(user)

                CronJobManager.__instance.schedule_user_cache(user)

        return CronJobManager.__instance 


        