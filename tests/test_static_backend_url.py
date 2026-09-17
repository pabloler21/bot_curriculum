# tests/test_static_backend_url.py
"""El frontend siempre lo sirve esta misma app (main.py monta StaticFiles en "/").

Por eso BACKEND_URL tiene que ser relativo. Cuando no lo era, adapt.js y pricing.js
apuntaban al deploy viejo de Render desde el dominio de producción: el browser
bloqueaba el fetch por CORS, /config nunca resolvía, el cliente de Supabase nunca
se construía y era imposible loguearse.
"""
import pathlib

import pytest

STATIC_DIR = pathlib.Path(__file__).parent.parent / "src" / "static"
JS_FILES = sorted(STATIC_DIR.glob("*.js"))


def test_hay_archivos_js_para_revisar():
    assert JS_FILES, "no se encontró ningún .js en src/static"


@pytest.mark.parametrize("js", JS_FILES, ids=lambda p: p.name)
def test_no_apunta_al_deploy_viejo_de_render(js):
    contenido = js.read_text(encoding="utf-8")
    assert "onrender.com" not in contenido, (
        f"{js.name} apunta a un host externo. El frontend lo sirve esta misma app, "
        "así que BACKEND_URL debe ser relativo o el browser bloquea el fetch por CORS."
    )


@pytest.mark.parametrize("js", JS_FILES, ids=lambda p: p.name)
def test_backend_url_es_relativo(js):
    contenido = js.read_text(encoding="utf-8")
    if "BACKEND_URL" not in contenido:
        pytest.skip("no define BACKEND_URL")
    assert "const BACKEND_URL = '';" in contenido, (
        f"{js.name} debe definir BACKEND_URL como cadena vacía (mismo origen)."
    )
