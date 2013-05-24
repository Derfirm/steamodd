"""
Core API code
Copyright (c) 2010-2013, Anthony Garcia <anthony@lagg.me>
Distributed under the ISC License (see LICENSE)
"""

import os, urllib2, urllib, re, json
from socket import timeout

class SteamError(Exception):
    """ For future expansion, considering that steamodd is already no
    longer *just* an API implementation """
    pass

class APIError(SteamError):
    """ Base API exception class """
    pass

class APIKeyMissingError(APIError):
    pass

class HTTPError(APIError):
    """ Raised for other HTTP codes or results """
    pass

class HTTPStale(HTTPError):
    """ Raised for HTTP code 304 """
    pass

class HTTPTimeoutError(HTTPError):
    """ Raised for timeouts (not necessarily from the http lib itself but the
    socket layer, but the effect and recovery is the same, this just makes it
    more convenient """
    pass

class HTTPFileNotFoundError(HTTPError):
    pass

class key(object):
    __api_key = None

    @classmethod
    def set(cls, value):
        cls.__api_key = str(value)

    @classmethod
    def get(cls):
        if cls.__api_key:
            return cls.__api_key
        else:
            raise APIKeyMissingError("API key not set")

class _interface_method(object):
    def __init__(self, iface, name):
        self._iface = iface
        self._name = name

    def __call__(self, method = "GET", version = 1, timeout = 5, since = None, **kwargs):
        kwargs["format"] = "json"
        kwargs["key"] = key.get()
        url = "http://api.steampowered.com/{0}/{1}/v{2}?{3}".format(self._iface,
                self._name, version, urllib.urlencode(kwargs))

        return method_result(url, last_modified = since, timeout = timeout)

class interface(object):
    def __init__(self, iface):
        self._iface = iface

    def __getattr__(self, name):
        return _interface_method(self._iface, name)

class http_downloader(object):
    def __init__(self, url, last_modified = None, timeout = 5):
        self._user_agent = "Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; Valve Steam Client/1366845241; ) AppleWebKit/535.15 (KHTML, like Gecko) Chrome/18.0.989.0 Safari/535.11"
        self._url = url
        self._timeout = timeout
        self._last_modified = last_modified

    def _build_headers(self):
        head = {}

        if self._last_modified:
            head["If-Modified-Since"] = str(self._last_modified)

        if self._user_agent:
            head["User-Agent"] = str(self._user_agent)

        return head

    def download(self):
        head = self._build_headers()
        status_code = -1
        body = ''

        try:
            req = urllib2.urlopen(urllib2.Request(self._url, headers = head), timeout = self._timeout)
            status_code = req.code
            body = req.read()
        except urllib2.HTTPError as E:
            code = E.getcode()
            if code == 404:
                raise HTTPFileNotFoundError("File not found")
            else:
                raise HTTPError("Server connection failed: {0.reason} ({1})".format(E, code))
        except timeout:
            raise HTTPTimeoutError("Server took too long to respond")

        lm = req.headers.get("last-modified")

        if status_code == 304:
            raise HTTPStale(str(lm))
        elif status_code != 200:
            raise HTTPError(str(status_code))
        else:
            self._last_modified = lm

        return body

    @property
    def last_modified(self):
        return self._last_modified

    @property
    def url(self):
        return self._url

class method_result(dict):
    """ Holds a deserialized JSON object obtained from fetching the given URL """

    __replace_exp = re.compile('[' + re.escape(''.join(
        map(unichr, range(0,32) + range(127,160)))) + ']')

    def __init__(self, *args, **kwargs):
        super(method_result, self).__init__()
        self._fetched = False
        self._downloader = http_downloader(*args, **kwargs)

    def __getitem__(self, key):
        if not self._fetched:
            self._call_method()

        return super(method_result, self).__getitem__(key)

    def _call_method(self):
        """ Download the URL using last-modified timestamp if given """
        self.update(json.loads(self._strip_control_chars(self._downloader.download()).decode("utf-8", errors = "replace")))
        self._fetched = True

    def _strip_control_chars(self, s):
        return method_result.__replace_exp.sub('', s)

    def get(self, key, default = None):
        if not self._fetched:
            self._call_method()

        return super(method_result, self).get(key, default)
