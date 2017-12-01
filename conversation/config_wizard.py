from telegram.ext import (ConversationHandler, CommandHandler, RegexHandler)
from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove)

from cron_job_manager import CronJobManager
from db_utils import Database, FileFormat
import utilities as utils

class ConfigWizard(ConversationHandler):

    num_stages = 9

    def __init__(self, lang, language_codes, initial_stage):

        self.db_manager = Database.get_instance()
        self.scheduler = CronJobManager.get_instance()
        self.lang = lang
        self.language_codes = language_codes
        self.initial_stage = initial_stage

        self.CONFIG, self.PROCESS_LANGUAGE, self.PROCESS_ACCOUNT, \
        self.PROCESS_LIBRARY, self.PROCESS_EMAIL, self.PROCESS_PASSWORD, \
        self.PROCESS_CREDENTIALS, self.PROCESS_UPDATE_LIBRARY_PASSWORD, \
        self.PROCESS_FILE_FORMAT = range(
            initial_stage, initial_stage + ConfigWizard.num_stages
        )

        self.entry_points = [CommandHandler(
            'config', self.request_config_menu)]
        self.states = {
            self.CONFIG: [RegexHandler(
                self.mc_ml_regex(['language','account', 'library', 'exit']),
                self.config_menu
            )],
            self.PROCESS_LANGUAGE: [RegexHandler(
                '.*',
                self.process_language
            )],
            self.PROCESS_ACCOUNT: [RegexHandler(
                self.mc_ml_regex(
                    [
                        'email',
                        'password',
                        'save_credentials',
                        'back'
                    ]
                ), self.account
            )],
            self.PROCESS_LIBRARY: [RegexHandler(
                self.mc_ml_regex(
                    [
                        'update_library',
                        'file_format',
                        'back'
                    ]
                ), self.process_library
            )],
            self.PROCESS_EMAIL: [RegexHandler(
                '.*', self.process_email
            )],
            self.PROCESS_PASSWORD: [RegexHandler(
                '.*', self.process_password
            )],
            self.PROCESS_CREDENTIALS: [RegexHandler(
                self.mc_ml_regex(['yes', 'no']), 
                self.process_save_credentials
            )],
            self.PROCESS_UPDATE_LIBRARY_PASSWORD: [RegexHandler('.*',
                self.process_password_update_library
            )],
            self.PROCESS_FILE_FORMAT: [RegexHandler(
                '^(' + self.lang['common']['jpg'] + '|' \
                + self.lang['common']['pdf'] + '|' \
                + self.lang['common']['epub'] + ')$',
                self.process_file_format
            )]
        }
        self.fallbacks=[RegexHandler('3248BC7547CE97B2A197B2A06CF7283D',
            self.cancel)]

        ConversationHandler.__init__(self,
            entry_points=self.entry_points,
            states=self.states,
            fallbacks=self.fallbacks
        )

    def get_final_stage_num(self):
        return self.initial_stage + ConfigWizard.num_stages

    def request_config_menu(self, bot, update, concat_message=None):
        user_id = update.message.from_user.id
        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        if concat_message == None:
            message = self.lang[language_code]['config_menu_request']
        else:
            message = '{}\n\n{}'.format(
                self.lang[language_code][concat_message],
                self.lang[language_code]['config_menu_request']
            )

        self.keyboard_request(
            update,
            message,
            [
                [self.lang[language_code]['language']],
                [self.lang[language_code]['account']],
                [self.lang[language_code]['library']],
                [self.lang[language_code]['exit']]
            ]
        )

        return self.CONFIG

    def config_menu(self, bot, update):
        user_id = update.message.from_user.id
        reply_menu = update.message.text

        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        if reply_menu == self.lang[language_code]['language']:
            self.keyboard_request(
                update,
                self.lang[language_code]['select_language'],
                [
                    [self.lang[language_code]['english']],
                    [self.lang[language_code]['japanese']]
                ]
            )
            return self.PROCESS_LANGUAGE
        elif reply_menu == self.lang[language_code]['account']:
            self.request_account(update, user)
            return self.PROCESS_ACCOUNT
        elif reply_menu == self.lang[language_code]['library']:
            self.request_library(update, user)
            return self.PROCESS_LIBRARY
        elif reply_menu == self.lang[language_code]['exit']:
            self.send_message(
                update,
                language_code,
                ['ok'],
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

    def process_language(self, bot, update):
        user_id = update.message.from_user.id
        reply_language = update.message.text
        language_code = self.db_manager.get_user(user_id).language_code
        reply_language_code = utils.get_key_with_value(
            self.language_codes, reply_language.lower()
        )

        if reply_language_code == None:
            self.keyboard_request(
                update,
                self.lang[language_code]['invalid_language'],
                [
                    self.lang[language_code]['english'],
                    self.lang[language_code]['japanese']
                ]
            )

            return self.PROCESS_LANGUAGE

        else:
            self.db_manager.set_user_language(user_id, reply_language_code)
            self.request_config_menu(
                bot, update, concat_message='short_selected_language'
            )
            return self.CONFIG
        
    def request_account(self, update, user, concat_message=None):
        language_code = user.language_code

        buttons = [
            [self.lang[language_code]['email']],
            [self.lang[language_code]['save_credentials']],
            [self.lang[language_code]['back']]
        ]

        if user.save_credentials == True:
            buttons[1:1] = [[self.lang[language_code]['password']]]

        if concat_message != None:
            message = '{}\n\n{}'.format(
                self.lang[language_code][concat_message], 
                self.lang[language_code]['config_menu_request']
            )
        else:
            message = self.lang[language_code]['config_menu_request']

        self.keyboard_request(
            update,
            message,
            buttons
        )

    def request_library(self, update, user, concat_message=None):
        language_code = user.language_code

        buttons = [
            [self.lang[language_code]['update_library']],
            [self.lang[language_code]['file_format']],
            [self.lang[language_code]['back']]
        ]

        if concat_message != None:
            message = '{}\n\n{}'.format(
                self.lang[language_code][concat_message], 
                self.lang[language_code]['config_menu_request']
            )
        else:
            message = self.lang[language_code]['config_menu_request']

        self.keyboard_request(
            update,
            message,
            buttons
        )

    def account(self, bot, update):
        user_id = update.message.from_user.id
        reply_menu = update.message.text

        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        if reply_menu == self.lang[language_code]['email']:
            self.send_message(
                update,
                language_code,
                ['request_email'],
                reply_markup=ReplyKeyboardRemove()
            )
            return self.PROCESS_EMAIL
        elif (user.save_credentials == True) \
            and (reply_menu == self.lang[language_code]['password']):
            
            self.send_message(
                update,
                language_code,
                ['request_password'],
                reply_markup=ReplyKeyboardRemove()
            )
            return self.PROCESS_PASSWORD
        elif reply_menu == self.lang[language_code]['save_credentials']:
            self.keyboard_request(
                update,
                self.lang[language_code]['save_pass_confirm'],
                [
                    [self.lang[language_code]['yes']],
                    [self.lang[language_code]['no']]
                ]
            )
            return self.PROCESS_CREDENTIALS
        elif reply_menu == self.lang[language_code]['back']:
            self.request_config_menu(bot, update)

            return self.CONFIG

    def process_email(self, bot, update):
        user_id = update.message.from_user.id
        reply_email = update.message.text
        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        if utils.is_valid_email(reply_email):
            self.db_manager.set_user_email(user_id, reply_email)
            self.scheduler.schedule_user_cache(user)
            self.request_account(update, user, concat_message='email_changed')
            return self.PROCESS_ACCOUNT
        else:    
            self.send_message(update, language_code, ['invalid_email'])
            return self.PROCESS_EMAIL

    def process_password(self, bot, update):
        user_id = update.message.from_user.id
        reply_password = update.message.text
        user = self.db_manager.get_user(user_id)

        self.db_manager.set_user_password(user_id, reply_password)
        self.scheduler.schedule_user_cache(user)
        self.request_account(update, user, concat_message='password_changed')
        return self.PROCESS_ACCOUNT

    def process_save_credentials(self, bot, update):
        user_id = update.message.from_user.id
        reply_confirm = update.message.text
        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        if reply_confirm == self.lang[language_code]['yes']:
            self.db_manager.set_save_credentials(user_id, True)
            if user.password == None:
                self.send_message(
                    update,
                    language_code,
                    ['credentials_enabled', 'request_password'],
                    reply_markup=ReplyKeyboardRemove()
                )
                return self.PROCESS_PASSWORD
            else:
                self.request_account(
                    update,
                    user,
                    concat_message='credentials_enabled'
                )
                return self.PROCESS_ACCOUNT

        else:
            self.scheduler.remove_scheduled_user_cache(user_id)
            self.db_manager.set_save_credentials(user_id, False)
            self.db_manager.set_user_password(user_id, None)
            self.request_account(
                update,
                user,
                concat_message='credentials_disabled'
            )
            return self.PROCESS_ACCOUNT

    def process_library(self, bot, update, concat_message=None):
        user_id = update.message.from_user.id
        reply_menu = update.message.text

        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        if reply_menu == self.lang[language_code]['update_library']:
            if user.save_credentials:
                if not user.now_caching:
                    self.scheduler.update_user_library(user)
                self.request_library(
                    update, user, concat_message='updating_library'
                )
                return self.PROCESS_LIBRARY
            else:
                self.send_message(
                    update,
                    language_code,
                    ['request_password'],
                    reply_markup=ReplyKeyboardRemove()
                )
                return self.PROCESS_UPDATE_LIBRARY_PASSWORD

        if reply_menu == self.lang[language_code]['file_format']:
            if concat_message != None:
                message = '{}\n\n{}'.format(
                    self.lang[language_code][concat_message], 
                    self.lang[language_code]['request_format']
                )
            else:
                message = self.lang[language_code]['request_format']

            self.keyboard_request(
                update,
                message,
                [
                    [self.lang['common']['jpg']],
                    [self.lang['common']['pdf']],
                    [self.lang['common']['epub']]
                ]
            )

            return self.PROCESS_FILE_FORMAT
        elif reply_menu == self.lang[language_code]['back']:
            self.request_config_menu(bot, update)
            return self.CONFIG

    def process_password_update_library(self, bot, update):
        user_id = update.message.from_user.id
        reply_password = update.message.text
        user = self.db_manager.get_user(user_id)
        self.scheduler.update_user_library(user, password=reply_password)
        self.request_library(
            update, user, concat_message='updating_library'
        )
        return self.PROCESS_LIBRARY

    def process_file_format(self, bot, update):
        user_id = update.message.from_user.id
        reply_format = update.message.text

        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        if reply_format == self.lang['common']['jpg']:
            self.db_manager.set_user_file_format(user_id, FileFormat.jpg)
        elif reply_format == self.lang['common']['pdf']:
            self.db_manager.set_user_file_format(user_id, FileFormat.pdf)
        elif reply_format == self.lang['common']['epub']:
            self.db_manager.set_user_file_format(user_id, FileFormat.epub)

        self.request_library(
            update, user, concat_message='file_format_selected'
        )
        return self.PROCESS_LIBRARY

    def cancel(self, bot, update):
        pass

    def send_message(self, update, language_code, message_codes, 
        reply_markup=None):
        
        text = self.lang[language_code][message_codes.pop(0)]
        for message_code in message_codes:
            text += '\n\n' + self.lang[language_code][message_code]
        update.message.reply_text(text, reply_markup=reply_markup)

    def keyboard_request(self, update, message, button_list):
        reply_markup = ReplyKeyboardMarkup(button_list, one_time_keyboard=True,
            resize_keyboard=True)
        update.message.reply_text(message, reply_markup=reply_markup)

    def multi_language_regex(self, message_code):
        return '^(' + self.lang['en'][message_code] \
            + '|' + utils.lower_case_first(self.lang['en'][message_code]) \
            + '|' + self.lang['ja'][message_code] + ')$'

    def mc_ml_regex(self, message_codes):
        text = '(' + self.multi_language_regex(message_codes.pop(0)) + ')'
        for message_code in message_codes:
            text += '|(' + self.multi_language_regex(message_code) + ')'
        return text