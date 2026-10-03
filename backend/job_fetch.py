# backend/job_fetch.py
"""
Descarga el texto visible de una oferta de trabajo a partir de su URL.

Anti-SSRF: solo http/https, y cada host (incluido cada salto de redirect) se
resuelve y se rechaza si alguna IP no es pública. Timeout 10 s, tope 2 MB.
"""
import asyncio
import ipaddress
import logging
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

MAX_BYTES = 2 * 1024 * 1024
TIMEOUT_S = 10.0
MAX_REDIRECTS = 3
MIN_CHARS = 200
_USER_AGENT = "Mozilla/5.0 (compatible; AureaBot/1.0; +https://aurea.pablolerner.dev)"


class JobFetchError(Exception):
    """No se pudo obtener un texto de oferta utilizable desde la URL."""


def is_url(text: str) -> bool:
    s = text.strip()
    return s.lower().startswith(("http://", "https://")) and not any(c.isspace() for c in s)


async def _check_url(url: str) -> None:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise JobFetchError("Unsupported URL")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        infos = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, port)
    except (ValueError, UnicodeError, socket.gaierror) as exc:
        raise JobFetchError("Invalid URL or host not found") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise JobFetchError("Blocked address")
    # ponytail: la IP se valida acá pero httpx vuelve a resolver al conectar (ventana de
    # DNS rebinding). Si pasa a importar, conectar directo a la IP ya validada.


class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "template", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth and data.strip():
            self.parts.append(data.strip())


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return "\n".join(parser.parts)


async def fetch_job_text(url: str, transport: httpx.AsyncBaseTransport | None = None) -> str:
    url = url.strip()
    async with httpx.AsyncClient(
        timeout=TIMEOUT_S,
        follow_redirects=False,
        headers={"User-Agent": _USER_AGENT, "Accept-Encoding": "identity"},
        transport=transport,
    ) as client:
        try:
            async with asyncio.timeout(TIMEOUT_S):
                for _ in range(MAX_REDIRECTS + 1):
                    await _check_url(url)
                    try:
                        async with client.stream("GET", url) as resp:
                            if resp.is_redirect:
                                url = urljoin(url, resp.headers.get("location", ""))
                                continue
                            if resp.headers.get("content-encoding", "identity").lower() != "identity":
                                raise JobFetchError("Unsupported content encoding")
                            if resp.status_code >= 400:
                                raise JobFetchError(f"HTTP {resp.status_code}")
                            body = bytearray()
                            async for chunk in resp.aiter_bytes():  # sin Content-Encoding (rechazado): no descomprime
                                body.extend(chunk)
                                if len(body) > MAX_BYTES:
                                    raise JobFetchError("Page too large")
                            html = body.decode(resp.encoding or "utf-8", errors="replace")
                    except (httpx.HTTPError, httpx.InvalidURL) as exc:
                        raise JobFetchError(f"Request failed: {exc}") from exc

                    text = html_to_text(html)
                    if len(text) < MIN_CHARS:
                        raise JobFetchError("Not enough text on the page")
                    logger.info("[job_fetch] Fetched %d chars from %s", len(text), urlparse(url).hostname)
                    return text
        except TimeoutError as exc:
            raise JobFetchError("Timed out") from exc

    raise JobFetchError("Too many redirects")
