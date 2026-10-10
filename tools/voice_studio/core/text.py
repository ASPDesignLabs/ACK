# SPDX-License-Identifier: GPL-3.0-or-later
"""The text catalog (plan decision D19): every visible sentence lives in data/text/<language>.json, named by a stable key, never typed into code.

It works the way ACK's own string resources do. A key is a name (`fetch.error.checksum.what`), a template holds `{name}` placeholders and
nothing else (no format specs, no attribute access, so a template can never run anything), a plural is `one`/`other` forms chosen by the
language's rule, and a key that is missing reads as itself so a gap shows instead of crashing. A language that lacks a key falls back to
English for that key, as Android does.

A failed step is told in three parts (D22), each its own key: `.what` happened, `.changed` (whether anything was changed) and `.next`.
Words that are only wanted under "Show details" live under a `.detail` key and are exempt from the plain-words check (tests/test_vs_text.py).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, FrozenSet, Mapping, Optional

from .diskbudget import size_parts

SCHEMA = 1
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "text"
PLACEHOLDER = re.compile(r"\{\{|\}\}|\{([a-z][a-z0-9_]*)\}")
LANGUAGE = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,8})?$")
PLURAL_FORMS = ("zero", "one", "two", "few", "many", "other")


class TextError(Exception):
    pass


def placeholders(template: str) -> FrozenSet[str]:
    """The names a template asks for. `{{` and `}}` are literal braces and ask for nothing."""
    return frozenset(m.group(1) for m in PLACEHOLDER.finditer(template) if m.group(1))


def render(template: str, args: Mapping[str, object], strict: bool = False) -> str:
    """Fill `{name}` from `args`. A value is only ever inserted, never itself read as a template, so a name or a path containing braces is safe.
    A placeholder with no value stays visible as `{name}` (or raises KeyError when `strict`)."""
    def fill(match):
        if match.group(0) == "{{":
            return "{"
        if match.group(0) == "}}":
            return "}"
        name = match.group(1)
        if name in args:
            return str(args[name])
        if strict:
            raise KeyError(name)
        return match.group(0)
    return PLACEHOLDER.sub(fill, template)


def plural_form(language: str, n: int) -> str:
    """The plural rule of each language that has a catalog. English: exactly one is "one"."""
    return "one" if n == 1 else "other"


@dataclass(frozen=True)
class Catalog:
    language: str
    strings: Mapping[str, str]
    plurals: Mapping[str, Mapping[str, str]]
    fallback: Optional["Catalog"] = None

    def is_plural(self, key: str) -> bool:
        return key in self.plurals or (self.fallback is not None and self.fallback.is_plural(key))

    def has(self, key: str) -> bool:
        return key in self.strings or key in self.plurals or (self.fallback is not None and self.fallback.has(key))

    def template(self, key: str) -> Optional[str]:
        if key in self.strings:
            return self.strings[key]
        return self.fallback.template(key) if self.fallback is not None else None

    def t(self, key: str, **args: object) -> str:
        """The sentence for `key`. A key that is not in the catalog reads as itself."""
        template = self.template(key)
        return key if template is None else render(template, args)

    def strict(self, key: str, **args: object) -> str:
        template = self.template(key)
        if template is None:
            raise KeyError(key)
        return render(template, args, strict=True)

    def count(self, key: str, n: int, **args: object) -> str:
        """A plural sentence: `{count}` is the number and the other arguments follow."""
        forms = self.plurals.get(key)
        if forms is None:
            return self.fallback.count(key, n, **args) if self.fallback is not None else key
        template = forms.get(plural_form(self.language, n)) or forms.get("other")
        return key if template is None else render(template, dict(args, count=n))


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TextError("cannot read %s: %s" % (path.name, exc))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("strings"), dict):
        raise TextError("%s is not a catalog this version understands" % path.name)
    return data


def parse_catalog(data: dict, language: str, fallback: Optional[Catalog] = None) -> Catalog:
    strings: Dict[str, str] = {}
    for key, value in data["strings"].items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TextError("%s: %r is not text" % (language, key))
        strings[key] = value
    plurals: Dict[str, Dict[str, str]] = {}
    for key, forms in (data.get("plurals") or {}).items():
        if not isinstance(forms, dict) or "other" not in forms or any(f not in PLURAL_FORMS or not isinstance(v, str) for f, v in forms.items()):
            raise TextError("%s: bad plural %r" % (language, key))
        plurals[key] = dict(forms)
    return Catalog(language, strings, plurals, fallback)


def available_languages(data_dir: Optional[Path] = None) -> list:
    return sorted(p.stem for p in (data_dir or DATA_DIR).glob("*.json") if LANGUAGE.match(p.stem))


def load_catalog(language: str = "en", data_dir: Optional[Path] = None) -> Catalog:
    """English is always loaded; another language covers what it has and English covers the rest."""
    folder = Path(data_dir) if data_dir else DATA_DIR
    english = parse_catalog(_read(folder / "en.json"), "en")
    if language == "en" or not LANGUAGE.match(language) or not (folder / (language + ".json")).exists():
        return english
    return parse_catalog(_read(folder / (language + ".json")), language, fallback=english)


def size_text(n: int) -> str:
    """A size as people read it, with the unit kept as the symbol drives use ("846 MB")."""
    number, unit = size_parts(n)
    return "%s %s" % (number, unit)
