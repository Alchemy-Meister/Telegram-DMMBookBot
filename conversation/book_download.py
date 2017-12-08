from telegram.ext import CallbackQueryHandler
from db_utils import Database, FileFormat
import utilities as utils
import os

class BookDownloadHandler(CallbackQueryHandler):

    def __init__(self, download_path):
        self.db_manager = Database.get_instance()
        self.download_path = utils.get_abs_path(download_path)
        self.download_format = {
            FileFormat.jpg: self.download_images,
            FileFormat.pdf: self.download_pdf,
            FileFormat.epub: self.download_epub
        }
        CallbackQueryHandler.__init__(self, self.download_book)

    def download_book(self, bot, update):
        query = update.callback_query
        book_id = query.data
        user_id = query.from_user.id
        session = self.db_manager.create_session()
        user = self.db_manager.get_user(session, user_id)
        book = self.db_manager.get_volume_by_id(session, book_id)
        book_path = utils.get_book_download_path(self.download_path, book)
        book_images = utils.get_book_images(book_path)
        missing_images = utils.book_missing_pages(1, book.pages, book_images)
        print(missing_images)
        self.db_manager.remove_session()
        self.download_format[user.file_format](user, book)

    def download_images(self, user, book):
        print(user, book)

    def download_pdf(self, user, book):
        print(user, book)

    def download_epub(self, user, book):
        print(user, book)