#!/usr/bin/env python

import enum

class CallbackCommand(enum.Enum):
    download = 0
    remove_url = 1