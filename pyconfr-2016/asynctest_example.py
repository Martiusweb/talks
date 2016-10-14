import asyncio
import collections
import urllib.parse
import warnings

import asynctest


class ResourceDownloader:
    """
    Tool that downloads a resource on an HTTP(S) server.

    :param url: URL of the resource.
    """

    def __init__(self, url):
        #: URL of the resource, set during object initialiation.
        self.url = url
        #: Resource data, populated once the resource is downloaded.
        self.data = None
        #: Refresh period.
        self.refresh_period = None

        # Handle to the next scheduled refresh call.
        self._refresh_handle = None

    def __repr__(self):
        return "ResourceDownloader({})".format(self.url)

    def __del__(self):
        if self._refresh_handle:
            self._refresh_handle.cancel()
            self._refresh_handle = None
            warnings.warn("{!r} refresh not disabled before object "
                          "deletion".format(self))

    def get_parsed_url(self):
        """
        Return a tuple ``host, port, query, ssl`` where ``host`` and ``port``
        are the ports on which the connection must be established, ``query``
        the full query path to the resource, and ``ssl`` a boolean value set to
        ``True`` if the scheme is ``https``.

        If :attr:`url` is not an absolute URL (scheme and hostname are
        required) or is invalid according to RFC3986, :exc:ValueError is
        raised.
        """
        scheme, netloc, *query = urllib.parse.urlparse(self.url)

        if not (scheme and netloc):
            raise ValueError('Invalid url {}'.format(self.url))

        if '[' in netloc:
            # ipv6
            bracket_position = netloc.find(']')
            host = netloc[1:bracket_position]
            # anything after "]:"
            port = netloc[bracket_position + 2:]
        elif ':' in netloc:
            host, port = netloc.split(':', 1)
        else:
            host = netloc
            port = None

        scheme = scheme.lower()

        if port:
            port = int(port)
        else:
            if scheme == 'http':
                port = 80
            elif scheme == 'https':
                port = 443
            else:
                raise ValueError("Unsupported protocol {}".format(scheme))

        query = urllib.parse.urlunparse(("", "", *query))
        return host, port, query or '/', scheme == 'https'

    async def download(self):
        """
        Download the resource and updates :attr:`data`.

        The value of :attr:`data` is returned.

        When the resource URL is invalid, :exc:`ValueError` is raised.
        When the response from the server can not be parsed or is not usable,
        :exc:`RuntimeError` is raised.

        Other standard exceptions may be raised (:exc:`OSError`, etc).
        """
        host, port, query, ssl = self.get_parsed_url()
        reader, writer = await asyncio.open_connection(host, port, ssl=ssl)

        try:
            writer.write(self._build_request(host, query))
            response_headers = await reader.readuntil(b"/r/n/r/n")
            code, payload_size = self._parse_response_headers(response_headers)

            if code != 200:
                raise RuntimeError(
                    "Server answered with unsupported code {}".format(code))

            self.data = await reader.read(payload_size)
        finally:
            writer.close()

        return self.data

    def _build_request(self, host, query):
        """
        Return a simple HTTP/1.1 GET request for the resource as
        a :class:`bytes` string.
        """
        return (
            "GET {query} HTTP/1.1\r\n"
            "Hostname: {host}\r\n"
            "Connection: close\r\n"
            "\r\n").format(host=host, query=query).encode('utf-8')

    def _parse_response_headers(self, response_headers):
        """
        Return a pair of integer values ``code, payload_size`` where ``code``
        is the HTTP response code and ``payload_size`` the expected size of the
        body of the response.

        If the payload should be retrieved until the connection is closed
        (because the payload size is unknown), the value of ``payload_size`` is
        set to ``-1``.

        A chunked body is not supported and raise an exception.
        Parsing errors raise a :exc:`RuntimeError`.

        :param response_headers: bytes string containing the headers of the
            HTTP response
        """
        if not response_headers:
            raise RuntimeError("Empty response headers")

        try:
            if response_headers.endswith(b"\r\n\r\n"):
                response_headers = response_headers.strip(b"\r\n")
            else:
                raise RuntimeError("Incomplete or invalid response headers")

            first_line, *headers = response_headers.split(b"\r\n")
            http_version, code, message = first_line.split()
            code = int(code)

            payload_size = -1  # until EOF
            for header in headers:
                key, value = map(bytes.strip, header.split(b":", 1))
                if key.startswith(b"transfer-encoding"):
                    if "chunked" in value.strip().split(b","):
                        raise RuntimeError("chunked body not supported")
                elif key.startswith(b"content-length"):
                    payload_size = int(value.strip())
        except (IndexError, ValueError):
            raise RuntimeError("Invalid response headers")
        else:
            return code, payload_size

    def refresh(self, period, loop=None):
        """
        Refresh the resource data (re-download it) every ``period`` seconds.

        If period is ``None``, disable the automatic refresh, if a refresh is
        in progress asynchronously, it will finish.

        :attr period: refresh period in seconds, disable auto refresh if
            ``None``
        :attr loop: optional loop on which the callbacks are scheduled, if
            unspecified or ``None``, the default loop is used.
        """
        self.refresh_period = period

        if period is None:
            if self._refresh_handle:
                self._refresh_handle.cancel()
                self._refresh_handle = None
            return

        loop = loop or asyncio.get_event_loop()
        self._refresh_handle = loop.call_later(
            period, self._create_refresh_task, loop)

    def _create_refresh_task(self, loop):
        loop.create_task(self._do_refresh(loop))

    async def _do_refresh(self, loop):
        try:
            await self.download()
        except Exception as e:
            # The exception can never be retrieved by the caller, let the loop
            # choose how to handle the exception.
            loop.call_exception_handler({
                'message': "Exception during resource refresh {}: {}".format(
                    self.url, e),
                'exception': e,
            })

        if self.refresh_period:
            self._refresh_handle = loop.call_later(
                self.refresh_period, self._create_refresh_task, loop)


Case = collections.namedtuple('Case', 'url expected')


@asynctest.lenient
class Test_ResourceDownloader_get_parsed_url(asynctest.TestCase):
    def test_get_parsed_url(self):
        cases = {
            "simple url": Case(
                url='http://piedpiper.com/',
                expected=('piedpiper.com', 80, '/', False)),
            "simple HTTPS url": Case(
                url='https://piedpiper.com/',
                expected=('piedpiper.com', 443, '/', True)),
            "url without path": Case(
                url='http://piedpiper.com/',
                expected=('piedpiper.com', 80, '/', False)),
            "url with uppercased scheme": Case(
                url='HTTP://piedpiper.com/',
                expected=('piedpiper.com', 80, '/', False)),
            "url with mixed case scheme": Case(
                url='HTtps://piedpiper.com/',
                expected=('piedpiper.com', 443, '/', True)),
            "url with path": Case(
                url='http://piedpieper.com/foo',
                expected=('piedpieper.com', 80, '/foo', False)),
            "url with custom port": Case(
                url='http://piedpieper.com:8080/foo',
                expected=('piedpieper.com', 8080, '/foo', False)),
            "url with query string": Case(
                url='http://piedpieper.com:8080/foo?bar',
                expected=('piedpieper.com', 8080, '/foo?bar', False)),
            "url with IPv4": Case(
                url='http://127.0.0.1/',
                expected=('127.0.0.1', 80, '/', False)),
            "url with IPv4 and port": Case(
                url='http://127.0.0.1:8080/',
                expected=('127.0.0.1', 8080, '/', False)),
            "url with IPv6": Case(
                url='http://[::1]/',
                expected=('::1', 80, '/', False)),
            "url with IPv6 and port": Case(
                url='http://[::1]:8080/',
                expected=('::1', 8080, '/', False)),
        }

        for name, case in cases.items():
            with self.subTest(name):
                result = ResourceDownloader(case.url).get_parsed_url()
                self.assertEqual(result, case.expected)

    def test_get_parsed_url_errors(self):
        cases = {
            "path only": Case(
                url="/foo", expected=ValueError),
            "missing scheme": Case(
                url="://piedpiper.com/middle/out", expected=ValueError),
            "unsupported protocol": Case(
                url="gopher://piedpiper.com/foo", expected=ValueError),
            "invalid port spectification": Case(
                url="http://piedpiper.com:80:90/", expected=ValueError),
            "invalid port spectification": Case(
                url="http://[::1]:80:90/", expected=ValueError),
            "IPv6 without brackets": Case(
                url="http://::1/", expected=ValueError),
        }

        for name, case in cases.items():
            with self.subTest(name, url=case.url):
                with self.assertRaises(case.expected):
                    ResourceDownloader(case.url).get_parsed_url()


class Test_ResourceDownloader_download(asynctest.TestCase):
    # Unfortunatly, this test relies on the implementation of
    # ResourceDownloader.download(), especially on how reader.read() and
    # reader.readuntil() will be called.
    # Asynctest should provide a StreamReader and SteamWriter "smart" mock.
    # We prefer an imperfect test, and more torough integration tests than no
    # test at all.

    def create_stream_mocks(self):
        self.reader = asynctest.mock.Mock(asyncio.StreamReader)
        self.writer = asynctest.mock.Mock(asyncio.StreamWriter)

    def set_response(self, payload, headers=None):
        def read(n=-1):
            return payload if n == -1 else payload[:n]

        self.reader.read.side_effect = read

        if not headers:
            headers = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Length: %d\r\n"
                b"Connection: close\r\n"
                b"\r\n"
            ) % len(payload)

        self.reader.readuntil.return_value = headers

    def setUp(self):
        self.downloader = ResourceDownloader("http://piedpiper.com/resource")
        self.create_stream_mocks()

        patch_open_connection = asynctest.mock.patch(
            'asyncio.open_connection',
            side_effect=lambda *a, **kw: (self.reader, self.writer),
            scope=asynctest.LIMITED
        )
        patch_open_connection.start()
        self.addCleanup(patch_open_connection.stop)

    async def test_download_resource(self):
        self.set_response(b"MiddleOut")
        payload = await self.downloader.download()
        self.assertEqual(payload, b"MiddleOut")

    async def test_writer_closed(self):
        self.set_response(b"-")
        await self.downloader.download()
        self.assertTrue(self.writer.close.called)

    async def test_writer_closed_on_error(self):
        self.set_response(b"-", b"Invalid: Header")
        with self.assertRaises(RuntimeError):
            await self.downloader.download()
        self.assertTrue(self.writer.close.called)


@asynctest.fail_on(active_handles=True)
class Test_ResourceDownloader_refresh(asynctest.ClockedTestCase):
    async def setUp(self):
        self.downloader = ResourceDownloader("http://piedpiper.com/")
        self.call_count = 0

        def set_data_value(*args, **kwargs):
            self.downloader.data = "Payload {}".format(self.call_count)
            self.call_count += 1

        patch = asynctest.mock.patch.object(
            self.downloader, "download", side_effect=set_data_value)
        patch.start()
        self.addCleanup(patch.stop)

        await self.downloader.download()

    async def tearDown(self):
        self.downloader.refresh(None)
        self.downloader = None

    async def test_refresh(self):
        self.assertEqual("Payload 0", self.downloader.data)
        self.downloader.refresh(5)
        await self.advance(1)
        # Too soon: must not have been refreshed.
        self.assertEqual("Payload 0", self.downloader.data)
        await self.advance(4)
        # 5 seconds after refresh(5) was set, data is updated
        self.assertEqual("Payload 1", self.downloader.data)
        await self.advance(10)
        # Updated two more times.
        self.assertEqual("Payload 3", self.downloader.data)

    async def test_refresh_cancelled(self):
        self.assertEqual("Payload 0", self.downloader.data)
        self.downloader.refresh(2)
        self.downloader.refresh(None)
        await self.advance(2)
        self.assertEqual("Payload 0", self.downloader.data)

    async def test_fail(self):
        with self.subTest("subtest"):
            with self.assertRaises(ValueError):
                pass
