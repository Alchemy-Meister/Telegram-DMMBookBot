FROM python:3.6.4-alpine3.7
RUN apk --no-cache add \
        # crytography dependency
        openssl-dev \
        # lxml dependency
        libxslt-dev \
        # Pillow dependencies
        jpeg-dev \
        zlib-dev \
        freetype-dev \
        lcms2-dev \
        openjpeg-dev \
        tiff-dev \
        tk-dev \
        tcl-dev \
        harfbuzz-dev \
        fribidi-dev
RUN apk --no-cache add --virtual .fetch-deps \
        gcc \
        # cffi dependency
        linux-headers \
        libffi-dev \
        musl-dev
COPY ./requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r ./requirements.txt
RUN apk del .fetch-deps
WORKDIR /urs/src/app
COPY . .
CMD [ "python", "./dmmbookbot.py" ]