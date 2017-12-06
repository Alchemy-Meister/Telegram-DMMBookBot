from uuid import uuid4
import re

from telegram.utils.helpers import escape_markdown
from telegram import (InlineQueryResultArticle, ParseMode,
    InputTextMessageContent, InlineKeyboardButton,
    InlineKeyboardMarkup)
from telegram.ext import InlineQueryHandler
from db_utils import Database

import utilities as utils

class BookSearchHandler(InlineQueryHandler):

    def __init__(self):
        InlineQueryHandler.__init__(self, self.search_book)
        self.db_manager = Database.get_instance()

    def search_book(self, bot, update):
        results = []
        user_id = update.inline_query.from_user.id
        query = update.inline_query.query
        session = self.db_manager.create_session()
        collection = self.db_manager.get_user_library_by_title(session, user_id, query)
        for book in collection:
            results.append(
                InlineQueryResultArticle(
                    id=uuid4(),
                    title=book.title,
                    description='ウタウタイ’の使命は、世界の秩序を守ること…。裏切り者の姉・ゼロを倒すべく旅を続けるワン、トウ、スリイ、フォウ、ファイブの仲良し姉妹。‘ウタのチカラ’を操り、砂の国の領主・ベイスに天誅を下し、教会都市へ向かったが、他の領主が差し向けた刺客・バルタスの巨大な力の前に大苦戦！！ オカマ口調の変なドラゴンも現れ、てんやわんやの第1巻！！！',
                    thumb_url=book.thumbnail_dmm,
                    input_message_content=InputTextMessageContent(
                        book.title
                    ),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('download', callback_data='qwe')]])
                )
            )

        update.inline_query.answer(results)

