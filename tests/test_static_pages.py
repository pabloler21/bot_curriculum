"""Cada página de la App se sirve y carga el shell compartido."""
import re
from pathlib import Path

import pytest

APP_PAGES: list[str] = [
    "index.html",
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


def test_landing_has_nav_anchors_and_cta(client):
    html = client.get("/").text
    for anchor in ('id="home"', 'id="about"', 'id="features-evaluator"', 'id="features-adapter"',
                   'id="features-jobs"', 'id="pricing"', 'href="evaluator.html"'):
        assert anchor in html


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


@pytest.mark.parametrize("page,target", [("adapt.html", "tailor.html"), ("pricing.html", "/#pricing")])
def test_old_pages_redirect(client, page, target):
    html = client.get(f"/{page}").text
    assert f"url={target}" in html
    assert "<script" not in html  # sin JS viejo colgando


@pytest.mark.parametrize("gone", ["adapt.js", "app.js", "pricing.js"])
def test_old_scripts_removed(client, gone):
    assert client.get(f"/{gone}").status_code == 404
