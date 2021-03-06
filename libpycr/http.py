"""
This module encapsulate the logic for querying an HTTP server.
"""

import base64
import getpass
import logging
import json
import requests

from libpycr.config import Config
from libpycr.exceptions import RequestError
from libpycr.utils.system import fail

from requests.auth import HTTPDigestAuth
from requests.exceptions import ConnectionError, RequestException

from urlparse import urlparse


# HTTP protocol method supported by this application
GET = 'GET'
POST = 'POST'
DELETE = 'DELETE'

# Response encoding
BASE64, JSON, PLAIN = range(3)

# To prevent against Cross Site Script Inclusion (XSSI) attacks, the JSON
# response body starts with a magic prefix line that must be stripped
GERRIT_MAGIC = ")]}'\n"


class RequestFactory(object):
    """A Request factory."""

    # Logger
    log = logging.getLogger(__name__)

    # The session object, to enable connection reuse
    _session = None

    @classmethod
    def set_auth_token(cls, username, password=None):
        """
        Set the authentication pair to use for HTTP requests.

        PARAMETERS
            username: the account username
            password: the account HTTP password
        """

        Config.set('gerrit.username', username)
        Config.set('gerrit.password', password)

    @classmethod
    def set_host(cls, host):
        """Set the Gerrit Code Review server host name.

        PARAMETERS
            host: the server's host
        """

        Config.set('gerrit.host', host)

    @classmethod
    def set_unsecure_connection(cls, unsecure):
        """If True, requests will be made over HTTP instead of HTTPS.

        Always use HTTPS by default.

        PARAMETERS
            unsecure: True to use HTTP
        """

        Config.set('gerrit.unsecure', unsecure)

    @classmethod
    def require_auth(cls):
        """
        Return True if authentication is required.
        Check whether cls.username is None.

        RETURNS
            True if auth required, False otherwise
        """

        return Config.get('gerrit.username') is not None

    @classmethod
    def get_http_digest_auth_token(cls):
        """
        Return the HTTPDigestAuth object to use for authentication.
        Prompt the user if the password is unknown.

        RETURNS
            requests.auth.HTTPDigestAuth
        """

        username = Config.get('gerrit.username')
        password = Config.get('gerrit.password')

        if password is None:
            password = getpass.getpass()

        return HTTPDigestAuth(username, password)

    @classmethod
    def get_remote_base_url(cls):
        """
        Return the Gerrit Code Review server base URL.

        RETURNS
            the Gerrit Code Review server base URL as a string
        """

        url = Config.get('gerrit.host')
        unsecure = Config.get('gerrit.unsecure', False)

        if url is None:
            fail('gerrit.host not set')

        # From Gerrit Code Review Documentation (section Authentication):
        # https://gerrit-review.googlesource.com/Documentation/rest-api.html
        #
        # Users (and programs) may authenticate using HTTP authentication by
        # supplying the HTTP password from the user's account settings page.
        # Gerrit by default uses HTTP digest authentication. To authenticate,
        # prefix the endpoint URL with /a/. For example to authenticate to
        # /projects/ request URL /a/projects/.

        if RequestFactory.require_auth():
            url = '%s/a' % url

        if not url.startswith('http://') or not url.startswith('https://'):
            return '%s://%s' % ('http' if unsecure else 'https', url)

        return url

    @classmethod
    def get_session(cls, **kwargs):
        """
        Return a requests.Session object.

        RETURNS
            requests.Session
        """

        if cls._session is None:
            cls._session = requests.Session()

            if cls.require_auth():
                cls._session.auth = RequestFactory.get_http_digest_auth_token()

            headers = kwargs['headers'] if 'headers' in kwargs else {}
            cls._session.headers.update(headers)

        return cls._session

    @classmethod
    def send(cls, endpoint, method=GET, encoding=JSON, **kwargs):
        """
        Return the result of a HTTP request.

        PARAMETERS
            endpoint: the endpoint to the request
            method: HTTP protocol method to use (either GET or POST)
            encoding: expected response format (JSON, base64 or plain text)
            **kwargs: any additional arguments to the underlying API call

        RETURNS
            a tuple of two elements: the raw response (stripped from magic for
                the JSON format) and the decoded object of that response, or
                None if expected_encoding is PLAIN. If response is no content
                (status code 204), returns a tuple of None values

        RAISES
            requests.exceptions.RequestException on error
        """

        cls.log.debug('Query URL: %s' % endpoint)

        try:
            response = cls.get_session().request(method, endpoint, **kwargs)

            if response.status_code == 204:
                # No content
                return None, None

            if response.status_code != 200:
                response.raise_for_status()

        except ConnectionError as why:
            fail('Unable to connect to %s' % urlparse(endpoint).netloc)

        except RequestException as why:
            raise RequestError(
                response.status_code, response,
                'HTTP %s request failed: %s' % (method, endpoint), why)

        if encoding == BASE64:
            encoded = response.text

            cls.log.debug('%d bytes to decode', len(encoded))

            pad = -len(encoded) % 4
            if pad == 3:
                b64response = encoded[:-1]
            else:
                b64response = encoded + b'=' * pad

            cls.log.debug('%d padded bytes to decode', len(b64response))
            cls.log.debug(b64response)

            try:
                decoded = base64.decodestring(b64response)
            except TypeError:
                # TypeError: incorrect padding
                cls.log.exception('cannot decode base64 stream')
                fail('invalid response stream (could not decode base64)')

        elif encoding == JSON:
            if not response.text.startswith(GERRIT_MAGIC):
                fail('invalid response stream (magic prefix not found)')

            json_response = response.text[len(GERRIT_MAGIC):]
            decoded = json.loads(json_response)

        else:
            decoded = None

        return response.text, decoded

    @classmethod
    def get(cls, endpoint, **kwargs):
        """
        Return the result of a HTTP GET request.

        PARAMETERS
            endpoint: the endpoint to GET
            **kwargs: any additional arguments to the underlying GET call

        RETURNS
            a tuple of two elements: the raw response (stripped from magic) and
                the json object of that response

        RAISES
            requests.exceptions.RequestException on error
        """

        return cls.send(endpoint, method=GET, **kwargs)

    @classmethod
    def post(cls, endpoint, **kwargs):
        """
        Return the result of a HTTP POST request.

        PARAMETERS
            endpoint: the endpoint to POST
            **kwargs: any additional arguments to the underlying POST call

        RETURNS
            a tuple of two elements: the raw response (stripped from magic) and
                the json object of that response

        RAISES
            requests.exceptions.RequestException on error
        """

        return cls.send(endpoint, method=POST, **kwargs)

    @classmethod
    def delete(cls, endpoint, **kwargs):
        """
        Return the result of a HTTP DELETE request.

        PARAMETERS
            endpoint: the endpoint to DELETE
            **kwargs: any additional arguments to the underlying DELETE call

        RAISES
            requests.exceptions.RequestException on error
        """

        cls.send(endpoint, method=DELETE, **kwargs)
