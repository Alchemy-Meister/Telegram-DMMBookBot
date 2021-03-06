from uuid import uuid4
import re

from telegram.utils.helpers import escape_markdown
from telegram import (InlineQueryResultArticle, ParseMode,
    InputTextMessageContent, InlineKeyboardButton,
    InlineKeyboardMarkup)
from telegram.ext import (InlineQueryHandler, CallbackQueryHandler,
    ChosenInlineResultHandler)
from constants import CallbackCommand
from db_utils import Database, MangaSeries

import utilities as utils

class BookSearchHandler(InlineQueryHandler):

    series_regex = r'^serie ([0-9]+):(.*)'

    def __init__(self, lang):
        self.lang = lang
        self.db_manager = Database.get_instance()
        InlineQueryHandler.__init__(self, self.inline_query, pass_chat_data=True)

    def inline_query(self, bot, update, chat_data):
        results = []
        user_id = update.inline_query.from_user.id
        query = update.inline_query.query
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
                description = book.volumes[0].description
                buttons = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton(
                            self.lang[language_code]['search_volume'], 
                            switch_inline_query_current_chat='serie {}: ' \
                                .format(book.id)
                        )]
                    ]
                )
            else:
                description = book.description
                buttons = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton(
                            self.lang[language_code]['download'], 
                            callback_data=str({
                                'cmd': CallbackCommand.download.value,
                                'book': book.id
                            })
                        )]
                    ]
                )
            results.append(
                InlineQueryResultArticle(
                    id=uuid4(),
                    title=book.title,
                    description=description,
                    thumb_url=book.thumbnail_dmm,
                    input_message_content=InputTextMessageContent(
                        book.title
                    ),
                    reply_markup=buttons
                )
            )
        self.db_manager.remove_session()
        update.inline_query.answer(results, is_personal=True)
