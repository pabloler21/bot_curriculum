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


def test_pages_stay_hidden_until_the_shell_is_in():
    """El fondo y el nav los inserta shell.js, al final del body. Si el navegador pinta antes, el
    contenido sale 67px más arriba y salta al llegar el nav: el temblor al cambiar de página."""
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    rule = re.search(r"body:not\(:has\(> \.ambient-bg\)\) \{([^}]*)\}", css)
    assert rule and "visibility: hidden" in rule.group(1)


def test_landing_nav_height_does_not_wait_for_auth():
    """shell.js muestra Login/Sign up recién cuando responde Supabase. Si el nav no reserva su
    alto, crece 12px en ese momento y toda la página baja: el "temblor" al cargar."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    rule = re.search(r"\.landing-actions \{([^}]*)\}", css)
    assert rule and "min-height" in rule.group(1)


FEATURE_PAGES = ["features-evaluator.html", "features-adapter.html", "features-jobs.html"]


@pytest.mark.parametrize("page", FEATURE_PAGES)
def test_feature_page_shows_the_glass_tile(client, page):
    html = client.get(f"/{page}").text
    assert '<div class="fv-tile">' in html and '<svg class="fv-glyph"' in html
    assert '<script src="feature-visual.js"></script>' in html
    assert client.get("/feature-visual.js").status_code == 200


@pytest.mark.parametrize("page", FEATURE_PAGES)
def test_feature_page_opens_with_its_title(client, page):
    """Sin el kicker "Features": la página ya dice qué feature es en el título."""
    assert "section-kicker" not in client.get(f"/{page}").text


@pytest.mark.parametrize("page", FEATURE_PAGES)
def test_feature_try_it_uses_the_brand_gradient(client, page):
    """"Try it" lleva el gradiente tornasolado de Aurea, el mismo del CTA de Pricing."""
    assert re.search(r'<a [^>]*class="btn-gradient"[^>]*data-i18n="landing.try_it"', client.get(f"/{page}").text)
    assert ".btn-gradient {" in (STATIC / "app.css").read_text(encoding="utf-8")


def test_feature_try_it_keeps_its_distance_from_the_text():
    """El aire sobre "Try it" lo ponía el margen de la lista; el Job board no tiene lista y el
    botón quedaba pegado al párrafo."""
    rule = re.search(r"\.feature \.btn-gradient \{([^}]*)\}", (STATIC / "app.css").read_text(encoding="utf-8"))
    assert rule and "margin-top" in rule.group(1)


def test_feature_title_sits_at_the_same_height_on_every_page():
    """El texto va arriba, a la altura del tile: centrado, el título del Job board (texto más
    corto) caía más abajo que en las otras dos páginas."""
    rule = re.search(r"\.feature \{([^}]*)\}", (STATIC / "app.css").read_text(encoding="utf-8"))
    assert rule and "align-items: start" in rule.group(1)


def test_feature_visuals_need_no_webgl():
    """El 3D con three.js no encajaba con el sitio y en mobile bloqueaba ~2 s: el tile es HTML/CSS."""
    for f in STATIC.iterdir():
        if f.suffix in (".html", ".js"):
            assert "three@" not in f.read_text(encoding="utf-8"), f"{f.name} carga three.js"


def test_home_cta_goes_to_evaluator(client):
    assert 'href="evaluator.html"' in client.get("/").text


def _home_entrance_css() -> str:
    """Bloque de app.css con la entrada animada de la home: solo corre sin reduced-motion."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    start = css.find("@media (prefers-reduced-motion: no-preference) {")
    assert start != -1, "la entrada de la home no está bajo prefers-reduced-motion: no-preference"
    depth, i = 0, css.index("{", start)
    for i in range(i, len(css)):
        depth += {"{": 1, "}": -1}.get(css[i], 0)
        if depth == 0:
            break
    return css[start:i]


def test_home_entrance_starts_once_the_shell_is_in():
    """El body está oculto hasta que shell.js inserta el fondo: si la entrada arrancara antes,
    correría sin verse y la home aparecería con la animación por la mitad."""
    hero_rules = re.findall(r"^\s*([^{}@]*\.hero[^{]*)\{", _home_entrance_css(), re.M)
    assert hero_rules, "la entrada no anima la hero"
    for selector in hero_rules:
        assert "body:has(> .ambient-bg)" in selector, f"{selector.strip()} arranca con el body oculto"


def test_home_accent_is_iridescent():
    """"for every job." lleva el tornasol de la marca (coral → ámbar → aqua), no el coral liso."""
    rule = re.search(r"\.hero-title em \{([^}]*)\}", (STATIC / "app.css").read_text(encoding="utf-8"))
    assert rule and "background-clip: text" in rule.group(1) and "var(--aqua)" in rule.group(1)


def _app_css_rule(selector: str) -> str:
    rule = re.search(re.escape(selector) + r" \{([^}]*)\}", (STATIC / "app.css").read_text(encoding="utf-8"))
    return rule.group(1) if rule else ""


def test_ctas_wear_the_brand_gradient():
    """"Improve my CV" va relleno con el tornasol y "Sign up" lleva el borde tornasolado."""
    assert "--gradient-brand:" in (STATIC / "style.css").read_text(encoding="utf-8")
    assert "var(--gradient-brand)" in _app_css_rule(".hero-cta")
    assert "var(--gradient-brand)" in _app_css_rule('[data-open-auth="signup"].btn-primary::after')


def test_hero_cta_keeps_its_gradient_on_hover():
    """El hover de .btn-primary pone fondo de vidrio: sin un hover propio, el CTA se vuelve gris."""
    assert "var(--gradient-brand)" in _app_css_rule(".hero-cta:hover:not(:disabled)")


def test_ctas_do_not_blink():
    """"Improve my CV" y "Sign up" quedan con el tornasol fijo: se sacó el encendido cada 7 s (4.12)."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert "cta-glow" not in css
    cta_rule = r'([^{}]*(?:\.hero-cta|data-open-auth="signup")[^{}]*)\{([^}]*)\}'
    for selector, body in re.findall(cta_rule, css.replace(_home_entrance_css(), "")):
        assert "animation" not in body, f"{selector.strip()} sigue animado"


def _evaluator_html() -> str:
    return (STATIC / "evaluator.html").read_text(encoding="utf-8")


def test_evaluator_adapter_and_jobs_sit_beside_the_improvements():
    """El adapter es el gancho para pagar: va en la columna lateral, a la vista, no debajo de todo."""
    side = re.search(r'<aside class="ev-side">(.*?)</aside>', _evaluator_html(), re.S)
    assert side, "falta la columna lateral de resultados"
    assert 'id="ev-job"' in side.group(1) and 'id="ev-jobs"' in side.group(1)


def test_evaluator_strengths_and_weaknesses_are_tabs():
    """4.22: fortalezas y debilidades son pestañas del panel de mejoras; desplegarlas estiraba la página."""
    html = _evaluator_html()
    assert "<details" not in html
    assert 'role="tablist"' in html and html.count('role="tab"') == 3
    order = ['id="ev-pane-fix"', 'id="ev-recs"', 'id="ev-pane-strengths"', 'id="ev-strengths"',
             'id="ev-pane-weak"', 'id="ev-weaknesses"', 'id="ev-formatting"']
    assert [html.index(x) for x in order] == sorted(html.index(x) for x in order)


def test_evaluator_tabs_work_with_the_keyboard():
    js = (STATIC / "evaluator.js").read_text(encoding="utf-8")
    assert "ArrowRight" in js and "ArrowLeft" in js


def test_evaluator_tabs_are_as_big_as_the_panel_titles():
    """Las pestañas reemplazan al título "What to fix": miden como "Tailor it to a job" (24 px), no 14."""
    assert "font-size: 1.5rem" in _app_css_rule('.ev-tabs [role="tab"]')


def test_evaluator_panel_takes_the_height_of_the_adapter_column():
    """En escritorio no hay scroll: el adapter y los jobs fijan el alto, y el panel de mejoras scrollea adentro."""
    assert "contain: size" in _app_css_rule(".ev-grid > .ev-fix")
    assert "overflow-y: auto" in _app_css_rule(".ev-pane")


def test_evaluator_spacing_is_the_same_everywhere():
    """La oferta, los paneles y el borde de abajo quedan a 20 px, como entre paneles (arriba eran 28)."""
    rule = _app_css_rule('body[data-page="evaluator"] .app-main')
    assert "padding-top: 20px" in rule and "padding-bottom: 20px" in rule
    assert "gap: 20px" in _app_css_rule(".ev-grid")


def test_evaluator_apply_sits_under_the_recommendations():
    """Al lado de pestañas de 24 px no entraba: "Apply to my CV" va al pie de "What to fix", con "Show all"."""
    foot = re.search(r'<div id="ev-fix-foot"[^>]*>(.*?)</div>', _evaluator_html(), re.S)
    assert foot and 'id="ev-apply"' in foot.group(1) and 'id="ev-recs-more"' in foot.group(1)


def test_evaluator_shows_four_recommendations_before_show_all():
    """Con texto de 16 px entran 4 sin scroll en 1920×945; el resto queda detrás de "Show all"."""
    assert "const RECS_SHOWN = 4;" in (STATIC / "evaluator.js").read_text(encoding="utf-8")


def test_evaluator_keywords_are_written_as_they_come():
    """En mayúsculas de 11 px no se leían: van a 13 px y como las escribe el evaluator."""
    rule = _app_css_rule(".ev-kw")
    assert "text-transform: none" in rule and "font-size: 13px" in rule


def test_evaluator_asks_for_the_analysis_in_the_page_language():
    js = (STATIC / "evaluator.js").read_text(encoding="utf-8")
    evaluate = re.search(r"async function evaluate\(.*?\n\}", js, re.S).group(0)
    assert "output_language" in evaluate and "aurea.lang" in evaluate


def test_evaluator_translates_an_analysis_saved_in_another_language():
    assert "/evaluate/translate" in (STATIC / "evaluator.js").read_text(encoding="utf-8")


def test_sign_out_forgets_the_translated_analysis_too():
    assert "'aurea_last_evaluation_alt'" in (STATIC / "shell.js").read_text(encoding="utf-8")


def test_evaluator_missing_keywords_lead_the_improvements():
    html = _evaluator_html()
    assert 'id="ev-keywords"' in html, "faltan las keywords como chips"
    assert html.index('id="ev-keywords"') < html.index('id="ev-recs"')


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


def _shell_function(name: str) -> str:
    shell = (STATIC / "shell.js").read_text(encoding="utf-8")
    body = shell[shell.index(f"function {name}("):]
    return body[:body.index("\n  }\n")]


def test_guest_app_pages_show_the_site_nav():
    """Al tocar "Try it" el visitante pasaba del nav del sitio a un evaluator sin menú: sin forma
    de volver ni de ver las otras herramientas. En la app ve el mismo nav que en la landing."""
    chrome = _shell_function("renderAppChrome")
    assert "landingNavHtml()" in chrome
    assert "topbarHtml() + sidebarHtml()" in chrome


def test_app_nav_follows_the_session():
    init = _shell_function("init")
    after_auth = init[init.index("await initSupabase()"):]
    assert "renderAppChrome(!!aurea.session)" in after_auth


def test_app_nav_is_chosen_before_supabase_answers():
    """Esperar a Supabase para elegir el nav lo hacía saltar: con sesión, el nav del sitio se
    cambiaba por el topbar y el contenido se corría 184px al llegar el sidebar."""
    init = _shell_function("init")
    before_auth = init[:init.index("await initSupabase()")]
    assert "renderAppChrome(requiresAuth || hasStoredSession())" in before_auth


def test_stored_session_hint_uses_the_supabase_key():
    """supabase-js 2 guarda la sesión en localStorage como sb-<proyecto>-auth-token."""
    hint = _shell_function("hasStoredSession")
    assert "localStorage" in hint
    assert "-auth-token" in hint


@pytest.mark.parametrize("path", ["/", "/about.html", "/shell.js", "/app.css"])
def test_static_files_are_revalidated(client, path):
    """Sin esto el navegador mezcla un HTML viejo con un shell.js nuevo tras cada deploy."""
    assert client.get(path).headers.get("cache-control") == "no-cache"


def test_adapt_redirects_to_tailor(client):
    html = client.get("/adapt.html").text
    assert "url=tailor.html" in html
    assert "<script" not in html  # sin JS viejo colgando


@pytest.mark.parametrize("gone", ["adapt.js", "app.js", "pricing.js", "feature-3d.js"])
def test_old_scripts_removed(client, gone):
    assert client.get(f"/{gone}").status_code == 404


def test_evaluator_keywords_are_not_red():
    # El color queda para los botones pagos: las keywords faltantes ya no van en rojo.
    assert "tag missing" not in (STATIC / "evaluator.js").read_text(encoding="utf-8")
    assert ".tag.missing" not in (STATIC / "style.css").read_text(encoding="utf-8")


def test_evaluator_draws_priority_bars_with_a_legend():
    js = (STATIC / "evaluator.js").read_text(encoding="utf-8")
    assert "keywords_missing_priority" in js and "recommendations_priority" in js
    html = _evaluator_html()
    for key in ("ev.prio_essential", "ev.prio_important", "ev.prio_optional"):
        assert f'data-i18n="{key}"' in html


def test_evaluator_priority_bars_are_announced_to_screen_readers():
    # Un aria-label en un <span> genérico lo ignoran muchos lectores: sin role="img" la prioridad no se oye.
    assert 'class="bars l${bars}" role="img"' in (STATIC / "evaluator.js").read_text(encoding="utf-8")


def test_evaluator_job_cards_do_not_grow_with_the_match_score():
    """Con un CV subido los jobs vienen con "% match": una línea más por tarjeta llevaba la página a 961 px
    en 945. En el evaluator no se muestra (está en la página de jobs) y las tarjetas no cambian de alto."""
    assert "display: none" in _app_css_rule(".ev-side .job-mini-score")


def test_evaluator_results_take_the_window_height():
    """4.23: el alto era el de la columna del adapter (657 px): entraba en 945 px de ventana, pero en
    911 la página scrolleaba 30 px. Ahora la página mide lo que la ventana y no scrollea."""
    rule = _app_css_rule('body[data-page="evaluator"]:has(.ev-results:not(.hidden))')
    assert "height: 100dvh" in rule and "overflow: hidden" in rule


def test_evaluator_adapter_keeps_its_height_and_jobs_take_the_rest():
    """Con la página atada a la ventana, el adapter no se achica y los jobs ocupan lo que queda,
    con scroll propio si no entran: así las dos columnas terminan juntas en cualquier alto."""
    assert "flex-shrink: 0" in _app_css_rule(".ev-side > .ev-adapter")
    assert "flex: 1" in _app_css_rule(".ev-results .ev-jobs-panel")
    assert "overflow-y: auto" in _app_css_rule(".ev-jobs-panel .job-row")


def test_evaluator_job_titles_take_one_line_in_short_windows():
    """En 911 px de alto la segunda fila de jobs quedaba cortada: con el título en una línea entran las 4."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    block = css[css.index("(max-height: 940px)"):]
    assert "-webkit-line-clamp: 1" in block[: block.index("}\n}") + 3]


def test_evaluator_shows_only_the_jobs_that_fit_whole():
    """Una tarjeta de job cortada a la mitad quedaba mal: se muestran las que entran enteras."""
    js = (STATIC / "evaluator.js").read_text(encoding="utf-8")
    assert "function fitJobs" in js and "observe(document.querySelector('.ev-jobs-panel .job-row'))" in js


def test_evaluator_short_windows_scroll_instead_of_cutting_jobs():
    """Con menos de 830 px de alto no entra ni una fila de jobs entera: ahí la página scrollea como antes."""
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert "(min-height: 830px)" in css and "(min-height: 780px)" not in css


def test_evaluator_fits_beside_the_sidebar():
    """Con sesión el main tiene el margen del sidebar: con width 100% se pasaba 144 px en 1280 de ancho."""
    rule = _app_css_rule('body.has-sidebar[data-page="evaluator"]:has(.ev-results:not(.hidden)) .app-main')
    assert "calc(100% - var(--sidebar-w))" in rule
