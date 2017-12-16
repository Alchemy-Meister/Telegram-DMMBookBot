#!/usr/bin/python

# Copyright (c) 2016, Daniel Nunes
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
# disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following
# disclaimer in the documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
# THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function
from builtins import str
import requests
from warnings import warn


__version__ = "1.0.1"


def uploadfile(file_path, name="", random_name=False, retries=3):
    """Return the file url if the file at the given path
    was successfully uploaded. Returns an empty string otherwise.

    :param string file_path: File path relative to the script.
    :param string name: Custom name you wish to give to the file. Don't forget the extension!
    :param bool random_name: Whether you wish the file to have a random name assigned to it.
    :param int retries: How many retries you wish to go through when there is a connection error or a timeout.
    :rtype: string

    """
    url = "https://uguu.se/api.php?d=upload"
    
    file_format = file_path.rsplit('.', 1)[1]
    if file_format == 'pdf':
        content_type = 'application/pdf'
    elif file_path == 'epub':
        content_type = 'application/epub+zip'

    multi_part_form_data = {
        "file": (file_path.rsplit('/', 1)[1], open(file_path, 'rb')),
        "MAX_FILE_SIZE": "150000000",
        'name': name
    }

    if random_name:
        if name != "":
            warn("Only one of the optional arguments should be used. In this case, the custom name will be overwritten.")
        multi_part_form_data['randomname'] = 'on'

    print(multi_part_form_data)

    if retries < 0:
        retries = 1

    while retries > 0:
        try:
            response = requests.post(url, files=multi_part_form_data)
            print(response.text)
            if response.status_code != requests.codes.ok:
                raise response.raise_for_status()

            return response.text

        except (requests.ConnectionError, requests.Timeout) as e:
            print (str(e))
            retries -= 1
            if not retries:
                return ""
            else:
                print("Retrying...")

        except requests.HTTPError as e:
            print(str(e))
            return ""
