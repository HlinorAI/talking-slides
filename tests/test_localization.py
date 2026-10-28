# Локализация: полнота словарей и паритет переводов (офлайн).

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_STR_LINE = re.compile(r'"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;')


def _parse_strings(path):
    pairs = {}
    for raw in open(path, encoding="utf-8").read().splitlines():
        m = _STR_LINE.search(raw)
        if m:
            key, value = m.group(1), m.group(2)
            pairs[key.replace('\\"', '"').replace("\\n", "\n")] = \
                value.replace('\\"', '"').replace("\\n", "\n")
    return pairs


def test_util_strings_complete():
    from util import STRINGS
    assert STRINGS, "словарь пуст"
    for key, entry in STRINGS.items():
        for lang in ("en", "ru"):
            assert entry.get(lang), f"{key}: нет перевода {lang}"
            assert "{unknown_param" not in entry[lang]


def test_lproj_parity():
    en = _parse_strings(os.path.join(ROOT, "app-sources/en.lproj/Localizable.strings"))
    ru = _parse_strings(os.path.join(ROOT, "app-sources/ru.lproj/Localizable.strings"))
    assert en and ru
    assert set(en) == set(ru), (
        f"разница ключей en/ru: {set(en) ^ set(ru)}")
    for key in en:
        assert en[key] and ru[key], f"пустое значение: {key}"


def test_swift_keys_covered():
    swift = open(os.path.join(ROOT, "app-sources/main.swift"),
                 encoding="utf-8").read()
    literal = re.compile(r'(?:L|LF)\("((?:[^"\\]|\\.)*)"', re.UNICODE)
    keys = set(m.group(1).replace('\\"', '"') for m in literal.finditer(swift))
    keys |= set(re.findall(r'"(stage\.\w+)"', swift))
    keys = {k.replace("\\n", "\n") for k in keys}
    assert keys, "не найдено локализуемых ключей в main.swift"
    en = _parse_strings(os.path.join(ROOT, "app-sources/en.lproj/Localizable.strings"))
    missing = keys - set(en)
    assert not missing, f"ключей нет в Localizable.strings: {sorted(missing)}"


def test_percent_formats_consistent():
    """В ключах и значениях совпадают спецификаторы формата (%@, %ld)."""
    en = _parse_strings(os.path.join(ROOT, "app-sources/en.lproj/Localizable.strings"))
    ru = _parse_strings(os.path.join(ROOT, "app-sources/ru.lproj/Localizable.strings"))
    def specs(text):
        text = re.sub(r"%(\d+)\$", "%", text)
        return sorted(re.findall(r"%(?:ld|[@d%])", text))

    for key, en_value in en.items():
        assert specs(key) == specs(en_value), key
        assert specs(key) == specs(ru[key]), key
