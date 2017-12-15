from telegram.ext import CallbackQueryHandler, ConversationHandler, RegexHandler
from telegram import KeyboardButton
from db_utils import Database, FileFormat
from cron_job_manager import CronJobManager
import logging
import utilities as utils
import os

class BookDownloadHandler(ConversationHandler):

    num_states = 1

    def __init__(self, download_path, lang, initial_state):
        self.db_manager = Database.get_instance()
        self.scheduler = CronJobManager.get_instance()
        self.logger = logging.getLogger(__name__)
        self.download_path = utils.get_abs_path(download_path)
        self.lang = lang
        self.initial_state = initial_state
        self.PROCESS_PASSWORD = range(
            initial_state, initial_state + BookDownloadHandler.num_states
        )
        self.entry_points = [CallbackQueryHandler(
            self.request_download_book, pass_user_data=True
        )]
        self.states = {
            self.PROCESS_PASSWORD: [RegexHandler(
                '.*', self.process_password, pass_user_data=True
            )]
        }
        self.fallbacks=[RegexHandler('3248BC7547CE97B2A197B2A06CF7283D',
            self.cancel)]
        ConversationHandler.__init__(
            self,
            entry_points=self.entry_points,
            states=self.states,
            fallbacks=self.fallbacks,
            per_chat=False
        )

    def request_download_book(self, bot, update, user_data):
        query = update.callback_query
        book_id = query.data
        user_id = query.from_user.id
        session = self.db_manager.create_session()
        user = self.db_manager.get_user(session, user_id)
        book = self.db_manager.get_volume_by_id(session, book_id)
        book_path = utils.get_book_download_path(self.download_path, book)
        book_images = utils.get_book_page_num_list(book_path)
        missing_images = utils.book_missing_pages(1, book.pages, book_images)
        self.logger.info('User %s requested to download book %s',
            user.id, book.id)
        self.logger.info('Removing download button of inline query of ' \
            + 'book %s for user %s', book.id, user.id)
        bot.editMessageReplyMarkup(
            chat_id = None,
            inline_message_id = query.inline_message_id,
            reply_markup=None
        )
        if not missing_images:
            self.logger.info('All the book %s pages are available in local ' \
                + 'storage', book.id)
            if user.file_format == FileFormat.pdf:
                preferred_format = FileFormat(FileFormat.pdf).name
            elif user.file_format == FileFormat.epub:
                preferred_format = FileFormat(FileFormat.epub).name
            format_file_path = utils.get_book_by_format(
                book_path, '.{}'.format(preferred_format.lower())
            )
            if format_file_path:
                self.logger.info('Sending %s book transmission start message ' \
                    + 'to user %s', book.id, user.id)
                bot.send_message(
                    chat_id=user.id,
                    text=self.lang[user.language_code]['sending_book'] \
                        .format(book.title)
                )
            else:
                self.logger.info('%s book not available in %s format', book.id,
                    preferred_format)
                self.scheduler.subscribe_to_book_conversion(book, book_path, \
                    user, bot, from_download=False)
            return ConversationHandler.END
        else:
            if not user.save_credentials:
                user_data['book'] = book
                user_data['book_path'] = book_path
                user_data['missing_images'] = missing_images
                user_data['user'] = user
                self.logger.info('sending user %s password request message.',
                    user.id)
                bot.send_message(
                    user.id, self.lang[user.language_code]['request_password']
                )
                return self.PROCESS_PASSWORD
            else:
                self.download_pages(
                    bot, update, book_path, missing_images, book, user
                )
                return ConversationHandler.END

        self.db_manager.remove_session()

    def process_password(self, bot, update, user_data):
        password = update.message.text
        self.download_pages(bot, update, user_data['book_path'], 
            user_data['missing_images'], user_data['book'], user_data['user'],
            password=password
        )
        return ConversationHandler.END

    def download_pages(self, bot, update, book_path, missing_images, book, user,
        password=None):
        
        if book.now_downloading:
            self.scheduler.subcribe_to_book_download(
                book, user, bot, update, password=password
            )
        else:
            self.scheduler.download_book_pages(
                book_path, missing_images, book, user, bot, update, 
                password=password
            )

    def cancel(self):
        pass