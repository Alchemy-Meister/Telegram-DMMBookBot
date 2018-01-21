FROM python:3.6.4-alpine3.7

COPY ./requirements.txt ./requirements.txt

RUN apk --no-cache add \
    # crytography dependency
    openssl-dev \
    # lxml dependency
    libxslt-dev \
    # Pillow dependencies
    jpeg-dev \
    zlib-dev \
    # freetype-dev \
    # lcms2-dev \
    # openjpeg-dev \
    # tiff-dev \
    # tk-dev \
    # tcl-dev \
    # harfbuzz-dev \
    # fribidi-dev \
    # selenium dependecies
    # xvfb \
    # firefox-esr \
    # PhantomJS dependency
    fontconfig \
    # build dependencies
    && apk --no-cache add --virtual .build-deps \
    curl \
    gcc \
    linux-headers \
    libffi-dev \
    musl-dev \
    # curl -L https://github.com/mozilla/geckodriver/releases/download/v0.18.0/geckodriver-v0.18.0-arm7hf.tar.gz | tar xz \
    # && mv ./geckodriver /usr/local/bin/ \
    # && chmod a+x /usr/local/bin/geckodriver \
    && mkdir -p /usr/share \
    && curl -L https://github.com/yangxuan8282/docker-image/releases/download/2.1.1/phantomjs-2.1.1-alpine-arm.tar.xz | tar xJ \
    && mv phantomjs /usr/share \
    && ln -s /usr/share/phantomjs/phantomjs /usr/bin/phantomjs \
    && pip install --no-cache-dir -r ./requirements.txt \
    && apk del .build-deps \
    && apk del --purge --force libc-utils \
    && rm -rf /var/cache/apk/* /tmp/*

WORKDIR /usr/src/app
COPY . .

CMD [ "python", "./dmmbookbot.py" ]