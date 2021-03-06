#!/usr/bin/python
# -*-coding:utf-8 -*-

import cv2
import fitz
import img2pdf
import locale
import logging
import os
import string
import sys
import random
import re
import dmm_ripper as dmm
import zipfile
from constants import FileFormat
from datetime import datetime
from epub_converter import Book
from io import BytesIO
from PIL import Image
from pytz import timezone, utc
from tesserocr import PyTessBaseAPI, RIL

logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CWD = os.getcwd()
locale.setlocale(locale.LC_ALL, "C")

def random_string(length):
    return ''.join(random.SystemRandom().choice( \
        string.ascii_uppercase + string.digits) for _ in range(length)
    )

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

def get_book_image_paths(path):
    book_images = []
    for file in os.listdir(path):
        if file.endswith('.jpg') and file != 'thumbnail.jpg':
            book_images.append(os.path.join(path, file))
    return sorted(book_images, key=lambda x: \
        int(x.rsplit('/', 1)[1].split('.jpg')[0])
    )

def get_book_page_num_list(path):
    book_images = []
    for file in os.listdir(path):
        if file.endswith('.jpg') and file != 'thumbnail.jpg':
            page_num = int(file.split('.jpg')[0])
            book_images.append(page_num)
    book_images.sort()
    return book_images

def book_missing_pages(start_page, end_page, page_list):
    return sorted(set(range(start_page, end_page + 1)).difference(page_list))

def get_book_download_path(base_path, book):
    if book.serie_id:
        return '{}/{}-{}/{}-{}'.format(
            base_path, book.serie.title, book.serie_id, book.title, book.id
        )
    else:
        return '{}/{}-{}'.format(base_path, book.title, book.id)

def download_progress_bar(
    current_page, total_pages, is_toc_missing, start_toc_missing=True
):
    if start_toc_missing:
        if is_toc_missing:
            i = current_page / (total_pages + 1)
        else:
            i = (current_page + 1) / (total_pages + 1)
    else:
        i = current_page / total_pages
    j = 1 - i
    return '[{}{}] {:d}%'.format('='*int(15*i), '　'*int(15*j), int(100*i))

def convert_book(user_format, path, book):
    return {
        FileFormat.pdf: convert_book2pdf,
        FileFormat.epub: convert_book2epub,
        FileFormat.zip: convert_book2jpg_zip
    }[user_format](path, book)

def convert_book2jpg_zip(path, book):
    logger.info('Creating jpg zip from %s book\'s images', book.id)
    book_pages = get_book_image_paths(path)
    zip_path = os.path.join(path, '{}.zip'.format(book.title))
    zip_file = zipfile.ZipFile(zip_path, 'w')
    for page in book_pages:
        zip_file.write(page, os.path.basename(page))
    zip_file.close()
    return zip_path

def convert_book2pdf(path, book):
    logger.info('Creating pdf from %s book\'s images', book.id)
    book_pages = get_book_image_paths(path)
    pdf_path = os.path.join(path, '{}.pdf'.format(book.title))
    with open(pdf_path, 'wb') as f:
        f.write(img2pdf.convert(book_pages))
    generate_pdf_toc(path, pdf_path)
    return pdf_path

def convert_book2epub(path, book):
    logger.info('Creating epub from %s book\'s images', book.id)
    book_pages = get_book_image_paths(path)
    epub_path = os.path.join(path, '{}.epub'.format(book.title))
    book = Book(title=book.title)
    for index, page in enumerate(book_pages):
        if not index:
            temp_cover = BytesIO()
            with Image.open(page) as img:
                img.save(temp_cover, format="png")
            temp_cover.name = page.rsplit('/', 1)[1]
            temp_cover.seek(0)
            book.add_cover(temp_cover.read())
        else:
            with open(page, 'br') as file:
                book.add_image_page(page.rsplit('/', 1)[1], file.read())
    book.save(epub_path)
    return epub_path

def generate_pdf_toc(base_path, pdf_path):
    toc_path = os.path.join(base_path, 'toc.txt')
    if dir_exists(toc_path) and os.stat(toc_path).st_size != 0:
        pdf_doc = fitz.open(pdf_path)
        toc_list = []
        with open(toc_path, 'r') as toc_file:
            for toc_entry in toc_file:
                title, page = toc_entry.split('\t', 1)
                page = int(page.rstrip())
                toc_list.append([1, title, page])
        pdf_doc.setToC(toc_list)
        pdf_doc.save(pdf_path, incremental=True)
        pdf_doc.close()

def get_component_images(path):

    image = Image.open(path)
    with PyTessBaseAPI(lang='jpn') as api:
        api.SetImage(image)
        print(api.GetUTF8Text())
        boxes = api.GetComponentImages(RIL.TEXTLINE, True)
        print('Found {} textline image components.'.format(len(boxes)))
        for i, (im, box, _, _) in enumerate(boxes):
            # im is a PIL image object
            # box is a dict with x, y, w and h keys
            api.SetRectangle(box['x'], box['y'], box['w'], box['h'])
            ocrResult = api.GetUTF8Text()
            conf = api.MeanTextConf()
            print((u"Box[{0}]: x={x}, y={y}, w={w}, h={h}, confidence: {1}, text: {2}").format(i, conf, ocrResult, **box))

def get_book_by_format(path, format_name):
    for file in os.listdir(path):
        if file.endswith(format_name):
            return os.path.join(path, file)
    return None

def logging_tz(*args):
    utc_dt = utc.localize(datetime.utcnow())
    my_tz = timezone('Asia/Tokyo')
    converted = utc_dt.astimezone(my_tz)
    return converted.timetuple()