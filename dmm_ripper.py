#!/usr/bin/python
# -*-coding:utf-8 -*-

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
import re
import requests
import sys
import utilities

debug = False
book_url = 'https://book.dmm.com'
library_url = book_url + '/library/'
var_ids = ['server', 'book_id', 'license', 'title', 'author', 'pages']

session_cookies = ['login_session_id', 'login_secure_id', 'INT_SESID']

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

    if debug:
        driver = webdriver.Chrome()
    else:
        driver = webdriver.PhantomJS()
    
    driver.get(login_url)

    inputElement = driver.find_element_by_id('login_id')
    inputElement.send_keys(email)
    inputElement = driver.find_element_by_id('password')
    inputElement.send_keys(password)

    login_button = driver.find_element_by_xpath( \
        '//*[@id="loginbutton_script_on"]/span/input' )
    login_button.submit()

    cookies = driver.get_cookies()

    driver.quit()

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

def get_books_list(html, is_volume_list):
    books = []
    soup = BeautifulSoup(html, 'html.parser')

    book_list = soup.find('ul', {'class': \
        'm-boxListBookProductLarge__list'})

    book_divs = book_list.findChildren(attrs={'class': \
        'm-boxListBookProductBlock__wrap'})

    for book_div in book_divs:
        try:
            book_link = book_div.findChild(attrs={'class': \
                'm-boxListBookProductBlock__item'}).findChild()['href']

            title = book_div.findChild(attrs={'class': \
                'm-boxListBookProductBlock__main__info__ttl'}).findChild() \
                .contents[0]

            url = book_url + book_link

            thumbnail = book_div.findChild(attrs={'class': \
                'm-boxListBookProductBlock__main__tmb'}).findChild('img')['src']

            books.append({'name': title, 'url': url, 'thumbnail': thumbnail})
        except:
            pass

    return books

def get_purchased_books(session):
    books = []
    response = requests.get(library_url, cookies=session.cookies.get_dict())
    if response.status_code == 200:
        books = get_books_list(response.text, False)
        
        for book in books:
            book['series'] = False
            if 'series' in book['url']:
                book['series'] = True
    
    return books

def get_book_volumes(session, book):
    volumes = []
    if 'series' not in book:
        volumes.append(dict(book))
        del volumes[0]['series']
    else:
        response = requests.get(book['url'], cookies=session.cookies.get_dict())
        if response.status_code == 200:
            volumes = list(reversed(get_books_list(response.text, True)))

    return volumes

def get_book_vars(html):
    soup = BeautifulSoup(html, 'html.parser')

    pattern = re.compile(r'\w+\ *= \"?(.*?)\"?;$', re.MULTILINE | re.DOTALL)
    script = soup.find("script", text=pattern)

    book_var_values = []
    var_ids_size = len(var_ids)

    for index, match in enumerate(pattern.findall(script.text)):
        if index >= var_ids_size:
            break
        book_var_values.append(match.encode().decode('unicode-escape'))

    return dict(zip(var_ids, book_var_values))

def get_image_download_url(book_vars, page):
    url_template = '{}/{}/{}-{}.jpg?uid={}'
    return url_template.format(book_vars[var_ids[0]], \
        book_vars[var_ids[1]], book_vars[var_ids[1]], str(page).zfill(4), \
        book_vars[var_ids[2]])

def get_image_path(path, book_vars, page):
    filename_template = '{}/{}-{}.jpg'
    return filename_template.format(path, book_vars[var_ids[1]], page)

    return filename_template.format(book_vars[var_ids[1], str(page).zfill(4)])

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
            page_url = get_image_download_url(book_vars, page)

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
