#!/usr/bin/python
# -*-coding:utf-8 -*-

import os
import sys
import re
import dmm_ripper as dmm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CWD = os.getcwd()

def dir_exists(dir_name):
    return os.path.exists(get_abs_path(dir_name))

def get_abs_path(path):
    if os.path.isabs(path):
        return path
    else:
        return os.path.join(CWD, path)

def create_dir(dir_name):
    dir_name = get_abs_path(dir_name)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

def callback_command(command):
    print('{{"command":"{0}"}}'.format(command))
    return '{{"command":"{0}"}}'.format(command)

def callback_string(command, value):
    return '{{"command":"{0}","value":"{1}"}}'.format(command, value)

def get_key_with_value(dictionary, value, default=None):
    for k, v in dictionary.items():
        for list_value in v:
            if list_value == value:
                return k
    return default

def is_valid_email(email):
    email_pattern = r'^(([^<>()\[\]\\.,;:\s@\"]+(\.[^<>()\[\]\\.,;:\s@\"]+)*)' \
        + r'|(\".+\"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])' \
        + r'|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$'
    return re.search(email_pattern, email) != None

def lower_case_first(string):
    if string:
        return string[:1].lower() + string[1:]
    else:
        return ''

def build_menu(buttons, n_cols=1, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu