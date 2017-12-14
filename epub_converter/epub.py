#!/usr/bin/env python

"""
Create Epub files.
This code was designed to provide a very simple and straight-forward API for
creating epub files, by sacrificing most of the versatility of the format.

"""

###############################################################################
# Module Imports
###############################################################################

import arrow
import collections
import itertools
import logging
import lxml.etree
import lxml.html
import os
import pathlib
import pkgutil
import tempfile
import uuid
import zipfile

###############################################################################

log = logging.getLogger(__name__)

###############################################################################

BASE = os.path.dirname(os.path.abspath(__file__))

###############################################################################

class ETreeWrapper:
    """Convinience wrapper around xml trees."""

    def __init__(self, *args, namespaces, **kwargs):
        self.tree = lxml.etree.ElementTree(*args, **kwargs)
        self.namespaces = namespaces

    def __call__(self, tag='*', **kwargs):
        path = './/{}'.format(tag)
        for key, value in kwargs.items():
            path += '[@{}="{}"]'.format(key, value)
        return self.tree.find(path, namespaces=self.namespaces)

    def __getattr__(self, name):
        return getattr(self.tree, name)

    def __str__(self):
        return str(lxml.etree.tostring(self.tree))

    def write(self, path):
        self.tree.write(str(path), xml_declaration=True,
                        encoding='UTF-8', pretty_print=True)


def template(name):
    """Get file template."""
    with open(name) as file:
        template = file.read()
    return ETreeWrapper(
        lxml.etree.fromstring(
            template.encode('utf-8'),
            lxml.etree.XMLParser(encoding='utf-8', remove_blank_text=True)),
        namespaces=dict(
            opf='http://www.idpf.org/2007/opf',
            dc='http://purl.org/dc/elements/1.1/',
            xhtml='http://www.w3.org/1999/xhtml'))


def flatten(tree):
    for item in tree:
        yield item
        yield from flatten(item.children)

###############################################################################

Page = collections.namedtuple('Page', 'uid title children')
Image = collections.namedtuple('Image', 'name type')


class Book:
    """Wrapper around a epub archive."""

    def __init__(self, **kwargs):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = []
        self.images = []
        self.uid_generator = map('{:04}'.format, itertools.count(1))

        self.path = pathlib.Path(self.tempdir.name).resolve()
        (self.path / 'pages').mkdir()
        (self.path / 'images').mkdir()

        self.title = kwargs.get('title', 'Untitled')
        self.language = kwargs.get('language', 'en')
        self.author = kwargs.get('author', 'Unknown Author')
        with open(os.path.join(BASE, 'stylesheet.css')) as file:
            self.add_stylesheet(file.read())

    def add_page(self, title, content, parent=None):
        """Add a new page/chapter to the root of the book."""
        page = Page(next(self.uid_generator), title, [])
        self.root.append(page) if not parent else parent.children.append(page)

        file = template(os.path.join(BASE, 'page.xhtml'))
        file('xhtml:title').text = title
        file('xhtml:body').append(lxml.html.fromstring(content))
        file.write(self.path / 'pages' / (page.uid + '.xhtml'))
        return page

    def add_image_page(self, name, data, parent=None):
        self.add_image(name, data)
        """Add a new page/chapter to the root of the book."""
        page = Page(next(self.uid_generator), name, [])
        self.root.append(page) if not parent else parent.children.append(page)
        file = template(os.path.join(BASE, 'page.xhtml'))
        file('xhtml:title').text = self.title
        file('xhtml:body').set('class', 'album') 
        file('xhtml:body').append(lxml.html.fromstring(
            '<div><img src="../images/{}" class="albumimg" alt="{}"/></div>' \
                .format(name, name))
        )
        file.write(self.path / 'pages' / (page.uid + '.xhtml'))
        return page

    def add_image(self, name, data):
        if name.endswith('.jpg'):
            media_type = 'image/jpeg'
        if name.endswith('.png'):
            media_type = 'image/png'
        self.images.append(Image(name, media_type))
        with open(str(self.path / 'images' / name), 'wb') as file:
            file.write(data)

    def add_cover(self, data):
        with open(str(self.path / 'cover.png'), 'wb') as file:
            file.write(data)

    def add_stylesheet(self, data):
        with open(str(self.path / 'stylesheet.css'), 'w') as file:
            file.write(data)

    def save(self, filename):
        self._write_spine()
        self._write_container()
        self._write_toc()
        with open(str(self.path / 'mimetype'), 'w') as file:
            file.write('application/epub+zip')
        with zipfile.ZipFile(filename, 'w') as archive:
            archive.write(
                str(self.path / 'mimetype'), 'mimetype',
                compress_type=zipfile.ZIP_STORED)
            for file in self.path.rglob('*.*'):
                archive.write(
                    str(file), str(file.relative_to(self.path)),
                    compress_type=zipfile.ZIP_DEFLATED)
        log.info('Book saved: {}'.format(self.title))

    def _write_spine(self):
        spine = template(os.path.join(BASE, 'content.opf'))
        now = arrow.utcnow().format('YYYY-MM-DDTHH:mm:ss')
        spine(property='dcterms:modified').text = now + 'Z'
        spine('dc:date').text = now
        spine('dc:title').text = self.title
        spine('dc:creator').text = self.author
        spine('dc:language').text = self.language
        spine(id='pub-id').text = str(uuid.uuid4())

        for index, page in enumerate(flatten(self.root)):
            lxml.etree.SubElement(
                spine('opf:manifest'), 'item',
                href='pages/{}.xhtml'.format(page.uid),
                id='page{}'.format(page.uid),
                **{'media-type': 'application/xhtml+xml'})
            if index % 2:
                properties = 'page-spread-right'
            else:
                properties = 'page-spread-left'

            lxml.etree.SubElement(
                spine('opf:spine'),
                'itemref',
                idref='page{}'.format(page.uid),
                properties=properties
            )

        for uid, image in enumerate(self.images):
            lxml.etree.SubElement(
                spine('opf:manifest'),
                'item',
                href='images/' + image.name,
                id='img{:03d}'.format(uid + 1),
                **{'media-type': image.type})

        spine.write(self.path / 'content.opf')

    def _write_container(self):
        container = template(os.path.join(BASE, 'container.xml'))
        meta_inf = self.path / 'META-INF'
        meta_inf.mkdir()
        container.write(meta_inf / 'container.xml')

    def _write_toc(self):
        toc = template(os.path.join(BASE, 'toc.xhtml'))
        toc.write(self.path / 'toc.xhtml')

    def _page_to_toc(self, page, node):
        navpoint = lxml.etree.SubElement(
            node, 'navPoint', id=page.uid, playOrder=page.uid.lstrip('0'))
        navlabel = lxml.etree.SubElement(navpoint, 'navLabel')
        lxml.etree.SubElement(navlabel, 'text').text = page.title
        lxml.etree.SubElement(
            navpoint, 'content', src='pages/{}.xhtml'.format(page.uid))
        for child in page.children:
            self._page_to_toc(child, navpoint)