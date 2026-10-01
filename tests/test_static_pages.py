"""Cada página de la App se sirve y carga el shell compartido."""
import pytest

APP_PAGES: list[str] = ["index.html"]  # las tareas del frontend van agregando sus páginas


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
