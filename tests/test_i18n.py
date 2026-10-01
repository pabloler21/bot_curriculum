"""Toda key data-i18n usada en el frontend tiene traducción en I18N_ES."""
import pathlib
import re

STATIC = pathlib.Path(__file__).parent.parent / "src" / "static"
_ATTR = re.compile(r'data-i18n(?:-placeholder)?="([^"$]+)"')
_KEY = re.compile(r"^\s*'([a-z0-9_.-]+)'\s*:", re.MULTILINE)


def _used_keys() -> dict[str, set[str]]:
    used: dict[str, set[str]] = {}
    for path in list(STATIC.glob("*.html")) + [STATIC / "shell.js"]:
        if path.exists():
            for key in _ATTR.findall(path.read_text(encoding="utf-8")):
                used.setdefault(key, set()).add(path.name)
    return used


def test_every_i18n_key_has_spanish_translation():
    defined = set(_KEY.findall((STATIC / "i18n.js").read_text(encoding="utf-8")))
    missing = {k: sorted(v) for k, v in _used_keys().items() if k not in defined}
    assert not missing, f"Keys sin traducción en I18N_ES: {missing}"


def test_dictionary_has_no_duplicate_keys():
    keys = _KEY.findall((STATIC / "i18n.js").read_text(encoding="utf-8"))
    dupes = {k for k in keys if keys.count(k) > 1}
    assert not dupes, f"Keys duplicadas: {dupes}"
