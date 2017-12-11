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
        self.callback_handler = CallbackQueryHandler(self.request_download_book)

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
        bot.editMessageReplyMarkup(
            chat_id = None,
            inline_message_id = query.inline_message_id,
            reply_markup=None
        )
        self.logger.info('User %s requested to download book %s',
            user.id, book.id)
        if not missing_images:
            if user.file_format == FileFormat.pdf:
                pdf_path = utils.get_book_by_format(book_path, '.pdf')
                if not pdf_path:
                    bot.send_message(
                        chat_id=user.id,
                        text='Converting images to PDF.'
                    )
                    try:
                        pdf_path = utils.convert_book2pdf(book_path, book)
                        bot.send_message(
                            chat_id=user.id,
                            text='Conversion to PDF finished! Now sending.',
                        )
                    except Exception as e:
                        print(e)
                        pass   #Conversion error, but this shouldn't happend.
                bot.send_document(
                    chat_id=user.id,
                    document=open(pdf_path, 'rb')
                )

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
