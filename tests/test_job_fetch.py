"""backend/job_fetch.py — descarga de JDs por URL, con anti-SSRF."""
import asyncio
import socket
from unittest.mock import patch

import httpx
import pytest

from backend.job_fetch import JobFetchError, fetch_job_text, html_to_text, is_url

PUBLIC_IP = "93.184.216.34"
LONG_HTML = (
    "<html><body><h1>Senior Python Engineer</h1><p>" + ("We build APIs with FastAPI. " * 20) + "</p></body></html>"
)


def _resolve(mapping):
    """getaddrinfo falso: host -> ip."""
    def fake(host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (mapping[host], port))]
    return fake


def test_is_url():
    assert is_url("https://jobs.example.com/123")
    assert is_url("  http://x.io/a  ")
    assert not is_url("We need a Python developer")
    assert not is_url("https://x.io/a and more text")
    assert not is_url("ftp://x.io/file")


@pytest.mark.parametrize("url", ["ftp://example.com/x", "file:///etc/passwd", "javascript:alert(1)"])
async def test_rejects_non_http_schemes(url):
    with pytest.raises(JobFetchError):
        await fetch_job_text(url)


@pytest.mark.parametrize(
    "ip", ["127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1", "0.0.0.0", "::ffff:127.0.0.1"]
)
async def test_rejects_non_public_addresses(ip):
    with patch("backend.job_fetch.socket.getaddrinfo", _resolve({"evil.example": ip})):
        with pytest.raises(JobFetchError):
            await fetch_job_text("http://evil.example/job")


async def test_rejects_redirect_to_private_address():
    def handler(request):
        if request.url.host == "jobs.example":
            return httpx.Response(302, headers={"Location": "http://internal.example/admin"})
        return httpx.Response(200, text=LONG_HTML)

    resolver = _resolve({"jobs.example": PUBLIC_IP, "internal.example": "10.1.2.3"})
    with patch("backend.job_fetch.socket.getaddrinfo", resolver):
        with pytest.raises(JobFetchError):
            await fetch_job_text("https://jobs.example/1", transport=httpx.MockTransport(handler))


async def test_too_many_redirects():
    transport = httpx.MockTransport(lambda r: httpx.Response(302, headers={"Location": "/again"}))
    with patch("backend.job_fetch.socket.getaddrinfo", _resolve({"jobs.example": PUBLIC_IP})):
        with pytest.raises(JobFetchError):
            await fetch_job_text("https://jobs.example/1", transport=transport)


async def test_rejects_oversized_page():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b"a" * (3 * 1024 * 1024)))
    with patch("backend.job_fetch.socket.getaddrinfo", _resolve({"jobs.example": PUBLIC_IP})):
        with pytest.raises(JobFetchError):
            await fetch_job_text("https://jobs.example/1", transport=transport)


async def test_rejects_http_error_and_short_text():
    with patch("backend.job_fetch.socket.getaddrinfo", _resolve({"jobs.example": PUBLIC_IP})):
        with pytest.raises(JobFetchError):
            await fetch_job_text("https://jobs.example/1",
                                 transport=httpx.MockTransport(lambda r: httpx.Response(404, text=LONG_HTML)))
        with pytest.raises(JobFetchError):
            await fetch_job_text("https://jobs.example/1",
                                 transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<p>Log in</p>")))


async def test_follows_public_redirect_and_returns_text():
    def handler(request):
        if request.url.path == "/1":
            return httpx.Response(301, headers={"Location": "/job"})
        return httpx.Response(200, text=LONG_HTML)

    with patch("backend.job_fetch.socket.getaddrinfo", _resolve({"jobs.example": PUBLIC_IP})):
        text = await fetch_job_text("https://jobs.example/1", transport=httpx.MockTransport(handler))
    assert "Senior Python Engineer" in text


def test_html_to_text_drops_scripts_and_styles():
    html = (
        "<html><head><style>.a{}</style><script>var secret=1</script></head>"
        "<body><p>Hello</p><noscript>x</noscript></body></html>"
    )
    assert html_to_text(html) == "Hello"


@pytest.mark.parametrize("url", ["http://x.io:abc/", "http://[::1/", "http://" + "a" * 64 + ".example/"])
async def test_malformed_urls_raise_job_fetch_error(url):
    with pytest.raises(JobFetchError):
        await fetch_job_text(url)


async def test_rejects_compressed_responses():
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, headers={"Content-Encoding": "gzip"}, content=b"x")
    )
    with patch("backend.job_fetch.socket.getaddrinfo", _resolve({"jobs.example": PUBLIC_IP})):
        with pytest.raises(JobFetchError):
            await fetch_job_text("https://jobs.example/1", transport=transport)


async def test_overall_deadline(monkeypatch):
    monkeypatch.setattr("backend.job_fetch.TIMEOUT_S", 0.05)

    async def slow(request):
        await asyncio.sleep(1)
        return httpx.Response(200, text=LONG_HTML)

    with patch("backend.job_fetch.socket.getaddrinfo", _resolve({"jobs.example": PUBLIC_IP})):
        with pytest.raises(JobFetchError):
            await fetch_job_text("https://jobs.example/1", transport=httpx.MockTransport(slow))
