"""Cada página de la App se sirve y carga el shell compartido."""
import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parent.parent / "src" / "static"

# Cada sección de la landing es su propia página (Excalidraw), no un ancla.
LANDING_PAGES: dict[str, str] = {
    "index.html": "home",
    "about.html": "about",
    "features-evaluator.html": "features-evaluator",
    "features-adapter.html": "features-adapter",
    "features-jobs.html": "features-jobs",
    "pricing.html": "pricing",
}

APP_PAGES: list[str] = [
    *LANDING_PAGES,
    "evaluator.html",
    "tailor.html",
    "cover.html",
    "jobs.html",
    "job-detail.html",
    "cv.html",
    "settings.html",
]


@pytest.mark.parametrize("page", APP_PAGES)
def test_page_loads_shell(client, page):
    res = client.get(f"/{page}")
    assert res.status_code == 200
    for asset in ('src="i18n.js"', 'src="shell.js"', 'href="app.css"'):
        assert asset in res.text, f"{page} no carga {asset}"


@pytest.mark.parametrize("page,section", LANDING_PAGES.items())
def test_landing_page_has_its_own_section(client, page, section):
    html = client.get(f"/{page}").text
    assert 'data-page="landing"' in html
    assert f'data-section="{section}"' in html
    assert 'class="landing-nav"' not in html, f"{page} repite el nav: lo pone shell.js"


def test_landing_nav_links_to_pages_not_anchors():
    shell = (STATIC / "shell.js").read_text(encoding="utf-8")
    for page in LANDING_PAGES:
        if page != "index.html":
            assert f'href="{page}"' in shell, f"el nav no linkea {page}"
    assert not re.search(r'href="/?#', shell), "el nav todavía usa anclas"


def test_home_cta_goes_to_evaluator(client):
    assert 'href="evaluator.html"' in client.get("/").text


def test_pricing_page_has_waitlist(client):
    html = client.get("/pricing.html").text
    assert 'id="waitlist-btn"' in html
    assert 'src="landing.js"' in html


def test_pricing_styles_live_only_in_app_css():
    """Un .pricing-grid viejo en style.css se sumaba al de app.css y descentraba las cards."""
    assert ".pricing-" not in (STATIC / "style.css").read_text(encoding="utf-8")


def test_pages_using_aurea_render_load_render_js():
    static = Path(__file__).resolve().parent.parent / "src" / "static"
    for html in static.glob("*.html"):
        srcs = re.findall(r'<script src="([\w.-]+\.js)"', html.read_text(encoding="utf-8"))
        for i, js in enumerate(srcs):
            f = static / js
            if js == "render.js" or not f.exists() or "aureaRender" not in f.read_text(encoding="utf-8"):
                continue
            assert "render.js" in srcs[:i], f"{html.name}: {js} usa aureaRender pero render.js no carga antes"


def test_ambient_background_lives_in_shell():
    """El fondo ambiental (orbs + grilla) lo pone shell.js; si una página lo repite, sale doble."""
    static = Path(__file__).resolve().parent.parent / "src" / "static"
    assert 'class="ambient-bg"' in (static / "shell.js").read_text(encoding="utf-8")
    for html in static.glob("*.html"):
        assert "ambient-bg" not in html.read_text(encoding="utf-8"), f"{html.name} repite el fondo ambiental"


@pytest.mark.parametrize("path", ["/", "/about.html", "/shell.js", "/app.css"])
def test_static_files_are_revalidated(client, path):
    """Sin esto el navegador mezcla un HTML viejo con un shell.js nuevo tras cada deploy."""
    assert client.get(path).headers.get("cache-control") == "no-cache"


def test_adapt_redirects_to_tailor(client):
    html = client.get("/adapt.html").text
    assert "url=tailor.html" in html
    assert "<script" not in html  # sin JS viejo colgando


@pytest.mark.parametrize("gone", ["adapt.js", "app.js", "pricing.js"])
def test_old_scripts_removed(client, gone):
    assert client.get(f"/{gone}").status_code == 404
