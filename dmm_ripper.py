#!/usr/bin/python
# -*-coding:utf-8 -*-

from bs4 import BeautifulSoup
from pyvirtualdisplay import Display
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
# from selenium.webdriver.chrome.options import Options
# from selenium.webdriver.support.ui import WebDriverWait
import logging
import os
import re
import requests
import sys
import utilities

book_url = 'https://book.dmm.com'
library_url = book_url + '/library/'
var_ids = ['server', 'book_id', 'license', 'title', 'author', 'pages']
session_cookies = ['login_session_id', 'login_secure_id', 'INT_SESID']

logger = logging.getLogger(__name__)

def get_login_url(fast):
    login_url = 'https://www.dmm.com/my/-/login/' \
            + '=/path=DRVESRUMTh1aCl5THVILWk8GWVsf/channel=book'

    if fast:
        return login_url
    else:
        response = requests.get(book_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        try:
            return soup.find('a', attrs={'class': 'hd-btn--login'}).get('href')
        except:
            return login_url

def get_session(email, password, fast=False):
    login_url = get_login_url(fast)
    #options = Options()
    #options.add_argument('--no-sandbox')
    # Disable various background network services, including extension updating,
    #   safe browsing service, upgrade detector, translate, UMA
    #options.add_argument('--disable-background-networking')
    # Disable installation of default apps on first run
    #options.add_argument('--disable-default-apps')
    # Disable all chrome extensions entirely
    #options.add_argument('--disable-extensions')
    # Disable the GPU hardware acceleration
    #options.add_argument('--disable-gpu')
    # Disable syncing to a Google account
    #options.add_argument('--disable-sync')
    # Disable built-in Google Translate service
    #options.add_argument('--disable-translate')
    # Run in headless mode
    #options.add_argument('--headless')
    # Hide scrollbars on generated images/PDFs
    #options.add_argument('--hide-scrollbars')
    # Disable reporting to UMA, but allows for collection
    #options.add_argument('--metrics-recording-only')
    # Mute audio
    #options.add_argument('--mute-audio')
    # Skip first run wizards
    #options.add_argument('--no-first-run')
    # Expose port 9222 for remote debugging
    #options.add_argument('--remote-debugging-port=9222')
    # Disable fetching safebrowsing lists, likely redundant due to 
    #   disable-background-networking
    #options.add_argument('--safebrowsing-disable-auto-update')
    #options.binary_location = os.environ['CHROME_BIN']
    
    #driver = webdriver.Chrome(chrome_options=options)
    try:
        display = Display(visible=0, size=(1024, 768))
        display.start()
        
        driver = webdriver.Firefox()
        driver.get(login_url)

        inputElement = driver.find_element_by_id('login_id')
        inputElement.send_keys(email)
        inputElement = driver.find_element_by_id('password')
        inputElement.send_keys(password)

        login_button = driver.find_element_by_xpath( \
            '//*[@id="loginbutton_script_on"]/span/input' )
        login_button.submit()

        cookies = driver.get_cookies()

        driver.close()
        driver.quit()
        display.close()

        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        
        valid_session = False
        for cookie in session_cookies:
            if cookie in session.cookies:
                valid_session = True
                break

        if not valid_session:
            raise Exception('Invalid session: wrong DMM email or password')

        return session
    except Exception as e:
        print(e)

def get_books_list(soup):
    books = []

    try:
        book_list = soup.find('ul', {'class': \
            'm-boxListBookProductLarge__list'})

        book_divs = book_list.findChildren(attrs={'class': \
            'm-boxListBookProductBlock__wrap'})

        for book_div in book_divs:
            try:
                book_link = book_div.findChild(attrs={'class': \
                    'm-boxListBookProductBlock__item'}).findChild()['href']
                title_div = book_div.findChild(attrs={'class': \
                    'm-boxListBookProductBlock__main__info__ttl'})
                book_details_url = title_div.findChild()['href']
                title = title_div.findChild().contents[0]

                thumbnail = book_div.findChild(
                    attrs={'class': 'm-boxListBookProductBlock__main__tmb'}
                ).findChild('img')['src']

                url = book_url + book_link

                books.append({
                    'name': title,
                    'url': url,
                    'details_url': book_details_url,
                    'thumbnail': thumbnail
                })
            except Exception as e:
                pass # Book not purchased if book_link missing.
    except Exception as e:
        raise Exception('No book found.')

    return books

def get_purchased_books(session, max_attempts=5):
    books = []
    library_end = False
    page = 1
    error = False
    attempt_num = 0

    while not library_end:
        while (not attempt_num) or (error and attempt_num < max_attempts):
            response = requests.get(library_url,
                params={'page': page},
                cookies=session.cookies.get_dict()
            )
            if response.status_code == 200:
                logger.info('Successfully requested page %d of purchased books',
                    page)
                try:
                    books.extend(get_books_list(
                        BeautifulSoup(response.text, 'html.parser'))
                    )
                    page += 1
                    error = False
                    attempt_num = 0
                except:
                    logger.info('Purchased book library ended')
                    library_end = True
                    break
            else:
                logger.info('Failed to obtain response for page {} of ' \
                    + 'purchased books, attempt {} out of {}'.format(
                        page, attempt_num + 1, max_attempts
                    )
                )
                error = True
                attempt_num += 1

    if error:
        raise Exception('Unable to obtain all the purchased books')
        
    for book in books:
        book['series'] = False
        if 'series' in book['url']:
            book['series'] = True
    
    return books

def get_book_volumes(session, book, max_attempts=5):
    volumes = []
    if 'series' not in book:
        volumes.append(dict(book))
        del volumes[0]['series']
    else:
        last_page = False
        page = 1
        error = False
        attempt_num = 0
        while not last_page:
            while (not attempt_num) or (error and attempt_num < max_attempts):
                response = requests.get(book['url'],
                    params={'page': page},
                    cookies=session.cookies.get_dict()
                )
                if response.status_code == 200:
                    logger.info('Successfully requested page %d of volumes ' \
                        + 'of series', page)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    try:
                        pagination = soup.find('ul', 
                            {'class': 'm-boxPagenation__list'}
                        )
                        last_soup_page = pagination.findChildren('li',
                            {'class': 'm-boxPagenation__list__item'}
                        )[-1]
                        try:
                            volumes.extend(get_books_list(soup))
                        except Exception:
                            raise Exception('Unable to obtain all the ' \
                                + 'volumes in series')
                        try:
                            #if not last page it should contain a link.
                            last_soup_page.findChild()['href']
                            page += 1
                            error = False
                            attempt_num = 0
                        except:
                            last_page = True
                            break
                    except:
                        logger.exception('Pagination system incompatible.')
                else:
                    logger.info('Failed to obtain response for page {} of ' \
                        + 'volumes of series, attempt {} out of {}'.format(
                            page, attempt_num + 1, max_attempts
                        )
                    )
                    error = True
                    attempt_num += 1

        if error:
            raise Exception('Unable to obtain all the volumes in series')

    return list(reversed(volumes))

def get_book_details(session, details_url):
    details = None
    try:
        response = requests.get(details_url, cookies=session.cookies.get_dict())
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            description = soup.find(
                'div', {'class': 'm-boxDetailProduct__info__story'}
            ).contents[0].strip()
            product_info = soup.find('div', {'class': 'm-boxDetailProductInfo'})
            pages = re.match(
                r'^([0-9]+)ページ', 
                product_info.findChildren(
                    'dd', {'class': 'm-boxDetailProductInfo__list__description'}
                )[2].contents[0].strip()
            ).group(1) 
            details = {'description': description, 'pages': pages}
    except Exception as e:
        print(e)
    return details

def get_book_vars(session, book):
    response = requests.get(book.url, cookies=session.cookies.get_dict())
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        pattern = re.compile(r'\w+\ *= \"?(.*?)\"?;$', re.MULTILINE | re.DOTALL)
        script = soup.find("script", text=pattern)

        book_var_values = []
        var_ids_size = len(var_ids)

        for index, match in enumerate(pattern.findall(script.text)):
            if index >= var_ids_size:
                break
            book_var_values.append(match.encode().decode('unicode-escape'))

        return dict(zip(var_ids, book_var_values))
    return None


def get_page_download_url(book_vars, page):
    url_template = '{}/{}/{}-{}.jpg?uid={}'
    return url_template.format(book_vars[var_ids[0]], \
        book_vars[var_ids[1]], book_vars[var_ids[1]], str(page).zfill(4), \
        book_vars[var_ids[2]])

def get_image_path(path, book_vars, page):
    filename_template = '{}/{}-{}.jpg'
    return filename_template.format(path, book_vars[var_ids[1]], page)

def download_image(url, path):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)

def download_book(session, book, path):
    response = requests.get(book['url'], cookies=session.cookies.get_dict())
    if response.status_code == 200:
        book_vars = get_book_vars(response.text)
        num_pages = book_vars[var_ids[5]]
        for page in range(1, int(num_pages) + 1):
            page_url = get_page_download_url(book_vars, page)

            response = requests.get(page_url, stream=True)
            if response.status_code == 200:
                with open(get_image_path(path, book_vars, page), \
                    'wb') as f:
                    
                    for chunk in response.iter_content(1024):
                        if chunk:
                            f.write(chunk)

def main(argv):
    DMM_EMAIL = argv[0] 
    DMM_PASSWORD = argv[1]
    
    session = get_session(DMM_EMAIL, DMM_PASSWORD)
    books = get_purchased_books(session)
    print(books)
    volumes = get_book_volumes(session, books[0])
    print(volumes)
    serie_title = books[0]['name']
    for volume in volumes:
        volume_path = 'temp/{}/{}'.format(serie_title, volume['name'])
        utilities.create_dir(volume_path)
        download_book(session, volume, volume_path)

if __name__ == '__main__':
    main(sys.argv[1:])
