"""Cada página de la App se sirve y carga el shell compartido."""
import pytest

APP_PAGES: list[str] = []  # las tareas del frontend van agregando sus páginas


@pytest.mark.parametrize("page", APP_PAGES)
def test_page_loads_shell(client, page):
    res = client.get(f"/{page}")
    assert res.status_code == 200
    for asset in ('src="i18n.js"', 'src="shell.js"', 'href="app.css"'):
        assert asset in res.text, f"{page} no carga {asset}"
