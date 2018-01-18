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
    chromium \
    chromium-chromedriver \
    # build dependencies
    && apk --no-cache add --virtual .build-deps \
    gcc \
    linux-headers \
    libffi-dev \
    musl-dev \ 
    && pip install --no-cache-dir -r ./requirements.txt \
    && apk del .build-deps \
    && apk del --purge --force libc-utils \
    && rm -rf /var/cache/apk/* /tmp/*

WORKDIR /usr/src/app
COPY . .

ENV CHROME_BIN=/usr/bin/chromium-browser

CMD [ "python", "./dmmbookbot.py" ]