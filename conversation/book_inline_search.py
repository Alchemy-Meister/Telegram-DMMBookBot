from uuid import uuid4
import re

from telegram.utils.helpers import escape_markdown
from telegram import (InlineQueryResultArticle, ParseMode,
    InputTextMessageContent, InlineKeyboardButton,
    InlineKeyboardMarkup)
from telegram.ext import (InlineQueryHandler, CallbackQueryHandler,
    ChosenInlineResultHandler)
from db_utils import Database, MangaSeries

import utilities as utils

class BookSearchHandler(InlineQueryHandler):

    series_regex = r'^series ([0-9]+):(.*)'

    def __init__(self, lang):
        self.lang = lang
        self.db_manager = Database.get_instance()
        InlineQueryHandler.__init__(self, self.inline_query)

    def inline_query(self, bot, update):
        results = []
        user_id = update.inline_query.from_user.id
        query = update.inline_query.query
        print(update.inline_query)
        session = self.db_manager.create_session()
        user = self.db_manager.get_user(session, user_id)
        language_code = user.language_code
        match = re.match(BookSearchHandler.series_regex, query)
        if match:
            result = self.db_manager.get_user_volumes_from_serie(
                session, user_id, match.group(1), match.group(2)
            )
        else:
            result = self.db_manager.get_user_library_by_title(
                session, user_id, query
            )
        for book in result:
            if isinstance(book, MangaSeries):
                buttons = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton(
                            self.lang[language_code]['search_volume'], 
                            switch_inline_query_current_chat='series {}: ' \
                                .format(book.id)
                        )]
                    ]
                )
            else:
                buttons = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton(
                            self.lang[language_code]['download'], 
                            callback_data='asd'
                        )]
                    ]
                )
            results.append(
                InlineQueryResultArticle(
                    id=uuid4(),
                    title=book.title,
                    description='ウタウタイ’の使命は、世界の秩序を守ること…。裏切り者の姉・ゼロを倒すべく旅を続けるワン、トウ、スリイ、フォウ、ファイブの仲良し姉妹。‘ウタのチカラ’を操り、砂の国の領主・ベイスに天誅を下し、教会都市へ向かったが、他の領主が差し向けた刺客・バルタスの巨大な力の前に大苦戦！！ オカマ口調の変なドラゴンも現れ、てんやわんやの第1巻！！！',
                    thumb_url=book.thumbnail_dmm,
                    input_message_content=InputTextMessageContent(
                        book.title
                    ),
                    reply_markup=buttons
                )
            )
        update.inline_query.answer(results)
        self.db_manager.remove_session()

