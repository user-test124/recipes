#!/usr/bin/env python3
"""Build the recipe site from a folder of Obsidian-style markdown notes.

The notes are read exactly as they are written in the vault:

    > [source](https://...)            -> source link (other quote text = intro)
    | Portions | Preparation | ... |   -> servings / prep / cook time
    ![[photo.jpg|500]]                 -> hero photo (found anywhere in the folder)
    ### Ingredients / ### Steps / ### Tricks / ### History
    #tag  [[tag]]  [[Other recipe]]    -> tags and links between recipes

Front matter (--- yaml ---) is optional and overrides anything above:
title, credit, servings, prep, cook, image, tags, description, source, draft.

Usage:
    python build.py                                   # reads ./content, writes ./_site
    python build.py --content path/to/notes --serve
    python build.py dates <notes_dir> > dates.json    # stdlib only, used by CI
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Settings — change freely
# --------------------------------------------------------------------------
SITE_TITLE = "pesce mignon"
# Languages of the site's own words (menus, headings, buttons). The recipes
# themselves stay as written. Visitors switch with the EN / FR / IT buttons;
# the first visit follows the browser's language.
LANGUAGES = ["en", "fr", "it"]
SITE_TAGLINE = {
    "en": "Recipes from family, friends and travels, written down so they don't get lost.",
    "fr": "Des recettes de famille, d'amis et de voyages, notées pour ne pas les perdre.",
    "it": "Ricette di famiglia, di amici e di viaggi, scritte per non perderle.",
}
SITE_URL = "https://user-test124.github.io/recipes"  # public address (share previews, 404 page)

# Categories come from the folders: the first level is a tab, the second a chip.
# A folder is shown under its own name ("boissons" -> "Boissons") in every
# language until it gets names here. Missing languages also fall back to the
# folder's own name, so a new folder always shows up, translated or not.
LABELS: dict[str, dict[str, str]] = {
    "savoury":      {"en": "Savoury",       "fr": "Salé",              "it": "Salato"},
    "sweet":        {"en": "Sweet",         "fr": "Sucré",             "it": "Dolce"},
    "drinks":       {"en": "Drinks",        "fr": "Boissons",          "it": "Bevande"},
    "fermentation": {"en": "Fermentation",  "fr": "Fermentation",      "it": "Fermentazione"},
    "aperitivo":    {"en": "Aperitivo",     "fr": "Apéritif",          "it": "Aperitivo"},
    "baked":        {"en": "Baked",         "fr": "Au four",           "it": "Al forno"},
    "chicken":      {"en": "Chicken",       "fr": "Poulet",            "it": "Pollo"},
    "crepe":        {"en": "Crêpes",        "fr": "Crêpes",            "it": "Crêpes"},
    "dip":          {"en": "Dips",          "fr": "Dips",              "it": "Salse e dip"},
    "fish":         {"en": "Fish",          "fr": "Poisson",           "it": "Pesce"},
    "galettes":     {"en": "Galettes",      "fr": "Galettes",          "it": "Gallette"},
    "grain":        {"en": "Grains",        "fr": "Céréales",          "it": "Cereali"},
    "pasta":        {"en": "Pasta",         "fr": "Pâtes",             "it": "Pasta"},
    "rice":         {"en": "Rice",          "fr": "Riz",               "it": "Riso"},
    "salad":        {"en": "Salads",        "fr": "Salades",           "it": "Insalate"},
    "sauce":        {"en": "Sauces",        "fr": "Sauces",            "it": "Salse"},
    "shrimp":       {"en": "Shrimp",        "fr": "Crevettes",         "it": "Gamberi"},
    "terracotta":   {"en": "Terracotta",    "fr": "Terre cuite",       "it": "Terracotta"},
    "vegi":         {"en": "Vegetables",    "fr": "Légumes",           "it": "Verdure"},
    "biscuits":     {"en": "Biscuits",      "fr": "Biscuits",          "it": "Biscotti"},
    "cakes":        {"en": "Cakes",         "fr": "Gâteaux",           "it": "Torte"},
    "light":        {"en": "Lighter bakes", "fr": "Desserts légers",   "it": "Dolci leggeri"},
    "pates":        {"en": "Pastry",        "fr": "Pâtes à tarte",     "it": "Basi per torte"},
    "pudding":      {"en": "Puddings",      "fr": "Puddings",          "it": "Budini"},
    "tarte":        {"en": "Tarts",         "fr": "Tartes",            "it": "Crostate"},
}
IGNORED_DIRS = {"ressource", "resources", "attachments", "assets", "templates", ".obsidian"}
IGNORED_TAGS = {"recipe", "recipes", "recette"}

# Section headings, in any of the languages the notes use.
SECTION_WORDS = {
    "ingredients": ["ingredients", "ingredient", "ingrédients", "ingrédient", "ingredienti", "ingredientes", "zutaten"],
    "steps": ["steps", "step", "method", "instructions", "directions", "étapes", "etapes", "procedimento",
              "preparazione", "pasos", "zubereitung"],
    "tricks": ["tricks", "trick", "tips", "tip", "astuces", "astuce", "trucchi", "consigli", "notes"],
    "history": ["history", "histoire", "storia", "story"],
}
SECTION_TITLES = {"ingredients": "Ingredients", "steps": "Method", "tricks": "Tips", "history": "The story"}

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
IMAGE_WIDTHS = (480, 960, 1600)

HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------
# Dates (stdlib only: CI runs this in the vault before copying notes)
# --------------------------------------------------------------------------
def git_added_dates(notes_dir: Path) -> dict[str, int]:
    """Map 'sub/dir/Note.md' -> unix time the file was first committed."""
    notes_dir = notes_dir.resolve()
    try:
        top = subprocess.run(["git", "-C", str(notes_dir), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        out = subprocess.run(
            ["git", "-C", top, "-c", "core.quotepath=off", "log", "--diff-filter=A", "--name-only",
             "--format=@%at", "--", str(notes_dir)],
            capture_output=True, text=True, check=True, encoding="utf-8").stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    prefix = os.path.relpath(notes_dir, top).replace(os.sep, "/").rstrip("/") + "/"
    if prefix == "./":
        prefix = ""
    dates: dict[str, int] = {}
    stamp = 0
    for line in out.splitlines():
        if line.startswith("@"):
            stamp = int(line[1:])
        elif line.strip():
            path = unicodedata.normalize("NFC", line.strip())
            if path.startswith(prefix):
                dates[path[len(prefix):]] = stamp  # log is newest-first: last write = oldest
    return dates


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "recipe"


def fold(text: str) -> str:
    """Lowercase, accent-free text for search and matching."""
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def label(folder: str, lang: str | None = None) -> str:
    """Name of a folder in `lang`, or the folder's own name if it has none."""
    own = folder.replace("_", " ").replace("-", " ")
    own = own[:1].upper() + own[1:]
    names = LABELS.get(folder.lower()) or {}
    if isinstance(names, str):          # a single name for every language
        return names
    return names.get(lang or LANGUAGES[0]) or own


def label_translations(folders) -> dict[str, dict[str, str]]:
    """{folder: {lang: name}} for every folder on the site (used by the language switch)."""
    return {f: {lang: label(f, lang) for lang in LANGUAGES} for f in sorted(set(folders)) if f}


def is_blank_md(md: str) -> bool:
    """True when a section holds nothing but empty bullets / numbers."""
    stripped = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", md, flags=re.M)
    return not re.sub(r"[\s​]+", "", stripped)


@dataclass
class Section:
    kind: str           # ingredients | steps | tricks | history | body
    md: str
    html: str = ""


@dataclass
class Group:
    title: str          # "" for the main recipe, or e.g. "Modo 1"
    title_html: str
    sections: list[Section] = field(default_factory=list)


@dataclass
class Recipe:
    path: Path
    rel: str
    slug: str
    title: str
    category: str
    subcategory: str
    credit: str = ""
    intro_html: str = ""
    description: str = ""
    sources: list[tuple[str, str]] = field(default_factory=list)
    servings: str = ""
    prep: str = ""
    cook: str = ""
    image: Path | None = None
    tags: list[str] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    added: int = 0
    ingredients_text: str = ""
    links: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
SECTION_LOOKUP = {fold(w): kind for kind, words in SECTION_WORDS.items() for w in words}
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
EMBED_RE = re.compile(r"!\[\[([^\]|]*)(?:\|([^\]]*))?\]\]")
MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]*)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")
TAG_RE = re.compile(r"(?<![\w&/#=?])#([^\s#\d.,;:!?()\[\]{}'\"][^\s#.,;:!?()\[\]{}'\"]*)")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
BARE_URL_RE = re.compile(r"^<?(https?://\S+?)>?$")


def section_kind(heading: str) -> str | None:
    words = fold(re.sub(r"[*_`:]", "", heading)).strip()
    return SECTION_LOOKUP.get(words)


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw, rest = text[4:end], text[end + 4:]
    try:
        import yaml  # optional
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            return {}, text
    except Exception:
        data = {}
        for line in raw.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip().strip("\"'")
    return {str(k).lower(): v for k, v in data.items()}, rest.lstrip("\n")


def title_from_filename(stem: str) -> tuple[str, str]:
    """'Cake aux Olives - Marraine Odile' -> ('Cake aux Olives', 'Marraine Odile')."""
    name = stem.strip()
    credit = ""
    m = re.match(r"^(.+?)\s+-\s+((?:[A-ZÀ-ÝÑ][\w'À-ÿ-]*)(?:\s+[A-ZÀ-ÝÑ][\w'À-ÿ-]*){0,2})$", name)
    if m:
        name, credit = m.group(1), m.group(2)
    else:
        m = re.match(r"^([A-Z]{2,4})\s+-\s+(.+)$", name)
        if m:
            credit, name = m.group(1), m.group(2)
    if "_" in name and name == name.lower():
        name = name.replace("_", " ")
    if name == name.lower():
        name = name[:1].upper() + name[1:]
    return name.strip(), credit


class ImageIndex:
    """Resolve Obsidian embeds by file name, wherever the image lives."""

    def __init__(self, root: Path):
        self.by_name: dict[str, Path] = {}
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in IMAGE_EXT:
                self.by_name.setdefault(unicodedata.normalize("NFC", p.name).lower(), p)

    def find(self, ref: str, note_dir: Path) -> Path | None:
        ref = unicodedata.normalize("NFC", ref.strip())
        if not ref:
            return None
        from urllib.parse import unquote
        candidate = (note_dir / unquote(ref)).resolve()
        if candidate.is_file():
            return candidate
        return self.by_name.get(Path(unquote(ref)).name.lower())


def parse_note(path: Path, root: Path, images: ImageIndex, warnings: list[str]) -> Recipe | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("﻿", "").replace(" ", " ")
    meta, body = split_frontmatter(text)
    if str(meta.get("draft", "")).lower() in {"true", "yes", "1"} or str(meta.get("publish", "")).lower() in {"false", "no", "0"}:
        return None

    rel = path.relative_to(root).as_posix()
    parts = [p for p in path.relative_to(root).parent.parts if p.lower() not in IGNORED_DIRS]
    category = parts[0].lower() if parts else "other"
    subcategory = parts[1].lower() if len(parts) > 1 else ""
    title, credit = title_from_filename(path.stem)
    r = Recipe(path=path, rel=rel, slug="", title=title, category=category, subcategory=subcategory, credit=credit)

    lines = body.split("\n")

    # H1 title (first non-empty line, if it isn't a section name)
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) == 1 and not section_kind(m.group(2)):
            r.title = m.group(2).strip()
            lines[i] = ""
        break

    # Tags (#tag outside headings, code and URLs)
    tags: list[str] = []
    in_code = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
        if in_code or HEADING_RE.match(line):
            continue
        found = TAG_RE.findall(re.sub(r"\(https?://[^)]*\)|https?://\S+", "", line))
        if found:
            tags += found
            lines[i] = TAG_RE.sub("", line).rstrip()
    body = "\n".join(lines)

    # Intro blockquote before the first heading: sources + description
    rest_parts = re.split(r"(?m)^(?=#{1,6}\s)", body, maxsplit=1)
    pre = rest_parts[0]
    after = rest_parts[1] if len(rest_parts) > 1 else ""

    sources: list[tuple[str, str]] = []
    intro_lines: list[str] = []
    keep_pre: list[str] = []
    for line in pre.split("\n"):
        s = line.strip()
        quoted = s.startswith(">")
        content = s.lstrip(">").strip() if quoted else s
        links = LINK_RE.findall(content)
        bare = BARE_URL_RE.match(content)
        if bare:
            sources.append(("", bare.group(1)))
            continue
        if links and (quoted or all(fold(t) in {"source", "recette", "recipe", "fonte"} for t, _ in links)
                      or re.fullmatch(r"(?:\s*\[[^\]]+\]\([^)]+\)\s*)+", content)):
            for t, u in links:
                sources.append(("" if fold(t) in {"source", "fonte", "lien", "link"} else t, u))
            leftover = LINK_RE.sub("", content).strip(" :-–—,.")
            if len(leftover.split()) >= 3:
                (intro_lines if quoted else keep_pre).append(leftover)
            continue
        if quoted:
            if content:
                intro_lines.append(content)
            continue
        keep_pre.append(line)
    pre = "\n".join(keep_pre)

    # Metadata table (Portions | Preparation | Dont cuisson)
    def take_table(md: str) -> str:
        m = re.search(r"(?m)^\|([^\n]*)\|\s*\n\|[\s:|-]+\|\s*\n((?:\|[^\n]*\|\s*\n?)*)", md)
        if not m:
            return md
        heads = [fold(h.strip()) for h in m.group(1).split("|")]
        if not any(h.startswith(("portion", "prep", "serv", "cuisson", "cook", "dose")) for h in heads):
            return md
        rows = [row for row in m.group(2).strip().split("\n") if row.strip()]
        cells = [c.strip() for c in rows[0].strip().strip("|").split("|")] if rows else []
        for h, v in zip(heads, cells):
            if not v:
                continue
            if h.startswith(("portion", "serv", "dose")):
                r.servings = v
            elif "cuisson" in h or h.startswith("cook"):
                r.cook = v
            elif h.startswith("prep"):
                r.prep = v
        return md[:m.start()] + md[m.end():]

    pre = take_table(pre)

    # Hero image: first embed before the first section heading (or anywhere if none)
    def first_image(md: str) -> tuple[str, Path | None]:
        for m in list(EMBED_RE.finditer(md)) + list(MD_IMAGE_RE.finditer(md)):
            ref = m.group(1) if m.re is EMBED_RE else m.group(2)
            if not ref.strip():
                continue
            found = images.find(ref, path.parent)
            if found:
                return md[:m.start()] + md[m.end():], found
            warnings.append(f"{rel}: image not found: {ref}")
            return md[:m.start()] + md[m.end():], None
        return md, None

    pre, r.image = first_image(pre)
    body = pre + ("\n" if after else "") + after
    body = re.sub(r"!\[\[\s*(\|[^\]]*)?\]\]", "", body)          # empty ![[]]
    body = re.sub(r"(?<!!)\[\[\s*\]\]", "", body)                # empty [[]]

    # Wikilinks: other recipes become links; tag-only lines become tags
    r.links = []
    out_lines = []
    for line in body.split("\n"):
        if WIKILINK_RE.search(line) and not WIKILINK_RE.sub("", line).strip(" ,-"):
            for target, alias in WIKILINK_RE.findall(line):
                if target.strip():
                    r.links.append(target.strip())
                    tags.append("@" + target.strip())  # resolved later (recipe link or tag)
            continue
        out_lines.append(line)
    body = "\n".join(out_lines)
    body = re.sub(r"(?m)^\s*(?:-{3,}|\*{3,}|_{3,})\s*$\n?(?=\s*\Z)", "", body.rstrip())  # trailing ---

    if "image" in meta and meta["image"]:
        r.image = images.find(str(meta["image"]), path.parent) or r.image

    r._raw_body = body  # parsed into groups after all recipes are known (for links)
    r._tags_raw = tags
    r.intro_md = "\n".join(intro_lines).strip()

    for key, attr in (("title", "title"), ("credit", "credit"), ("author", "credit"), ("from", "credit"),
                      ("by", "credit"), ("servings", "servings"), ("portions", "servings"),
                      ("prep", "prep"), ("cook", "cook"), ("description", "intro_md")):
        if meta.get(key):
            setattr(r, attr, str(meta[key]))
    if meta.get("source"):
        srcs = meta["source"] if isinstance(meta["source"], list) else [meta["source"]]
        sources = [("", str(s)) for s in srcs] + sources
    if meta.get("tags"):
        t = meta["tags"]
        r._tags_raw += t if isinstance(t, list) else re.split(r"[,\s]+", str(t))
    r.sources = sources
    return r


def split_groups(md: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Split a note body into groups of sections.

    Most notes are one group. A note with variants ("### Modo 1" ... "### Modo 2",
    each with its own Ingredients/Steps) becomes several titled groups.
    Returns [(group_title, [(kind, markdown), ...]), ...].
    """
    groups: list[list] = [["", []]]
    level_of_sections = None          # heading level used by the current group's sections
    in_code = False
    for line in md.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else HEADING_RE.match(line)
        if m:
            level, text = len(m.group(1)), m.group(2)
            kind = section_kind(text)
            title, secs = groups[-1]
            if kind:
                secs.append([kind, ""])
                level_of_sections = level
                continue
            if level_of_sections is None and not title and not any(k != "body" or not is_blank_md(t) for k, t in secs):
                groups[-1] = [text, []]                 # title for the first group
                continue
            if level_of_sections is None or level <= level_of_sections:
                groups.append([text, []])               # a new variant / part
                level_of_sections = None
                continue
            # deeper heading inside a section ("## Pancake" under "# Ingredients"): keep as text
        title, secs = groups[-1]
        if not secs:
            secs.append(["body", ""])
        secs[-1][1] += line + "\n"
    result = []
    for title, secs in groups:
        secs = [(k, t.strip("\n")) for k, t in secs if not is_blank_md(t)]
        if secs:
            result.append((title, secs))
    return result


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------
def make_markdown():
    from markdown_it import MarkdownIt
    md = MarkdownIt("commonmark", {"breaks": True, "html": True, "linkify": False, "typographer": True})
    md.enable(["table", "strikethrough"])
    return md


def tidy_lists(md: str) -> str:
    md = re.sub(r"(?m)^(\s*)(\d+[.)])\s+\d+[.)]\s+", r"\1\2 ", md)        # "1. 1. text"
    md = re.sub(r"(?m)^(\s*)([-*+])\s+[-*+]\s+(?=\S)", r"\1\2 ", md)       # "- - text"
    md = re.sub(r"(?m)^\s*(?:[-*+]|\d+[.)])\s*$\n?", "", md)                # empty bullets
    md = re.sub(r"\\\s*$", "", md, flags=re.M)                              # stray "\" at EOL
    # A label line right after a list item ("Cottura:") must not glue onto that item
    md = re.sub(r"(?m)^(\s*(?:[-*+]|\d+[.)])\s[^\n]*)\n(?=[^\s\-*+\d#>|][^\n]{0,60}:\s*\n)", r"\1\n\n", md)
    # A label line ("Impasto:", "**Cottura :**", "GARNISH") directly followed by a list
    md = re.sub(r"(?m)^([^\n#>|\-*+\d][^\n]{0,60})\n(?=\s*(?:[-*+]|\d+[.)])\s)", r"\1\n\n", md)
    return md


SUBLABEL_RE = re.compile(
    r"<p>((?:<strong>)?[^<\n]{1,60}?(?:</strong>)?)\s*</p>(?=\s*<[ou]l)", re.S)


def mark_sublabels(fragment: str) -> str:
    def repl(m):
        txt = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if not txt.endswith((".", "!", "?")) and len(txt.split()) <= 6:
            return f'<p class="sublabel">{html.escape(txt.rstrip(" :"))}</p>'
        return m.group(0)
    return SUBLABEL_RE.sub(repl, fragment)


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------
class ImageWriter:
    def __init__(self, out: Path, cache: Path):
        self.out, self.cache = out / "img", cache
        self.out.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.done: dict[Path, dict] = {}
        try:
            from PIL import Image, ImageOps  # noqa: F401
            self.pil = True
        except ImportError:
            self.pil = False
            print("! Pillow not installed: photos are copied without resizing", file=sys.stderr)

    def add(self, src: Path) -> dict:
        """Return {'src': url, 'srcset': str, 'w': int, 'h': int} relative to site root."""
        if src in self.done:
            return self.done[src]
        try:
            info = self._make(src)
        except Exception as e:  # unreadable file, e.g. a Git LFS pointer
            print(f"! could not read image {src.name}: {e}", file=sys.stderr)
            info = None
        self.done[src] = info
        return info

    def _make(self, src: Path) -> dict:
        digest = hashlib.sha1(src.read_bytes()).hexdigest()[:10]
        base = f"{slugify(src.stem)}-{digest}"
        info: dict
        if not self.pil or src.suffix.lower() == ".gif":
            name = base + src.suffix.lower()
            shutil.copy2(src, self.out / name)
            info = {"src": f"img/{name}", "srcset": "", "w": 0, "h": 0, "small": f"img/{name}"}
        else:
            from PIL import Image, ImageOps
            with Image.open(src) as im:
                im = ImageOps.exif_transpose(im)
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
                w, h = im.size
                variants = []
                for target in IMAGE_WIDTHS:
                    if target > w and variants:
                        break
                    tw = min(target, w)
                    name = f"{base}-{tw}.webp"
                    cached = self.cache / name
                    if not cached.exists():
                        im.resize((tw, round(h * tw / w)), Image.LANCZOS).save(cached, "WEBP", quality=80, method=5)
                    shutil.copy2(cached, self.out / name)
                    variants.append((tw, f"img/{name}"))
                info = {"src": variants[-1][1], "small": variants[0][1],
                        "srcset": ", ".join(f"{u} {tw}w" for tw, u in variants),
                        "w": w, "h": h}
        return info


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------
def build(content: Path, out: Path, dates_file: Path | None = None) -> list[str]:
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    t0 = time.time()
    warnings: list[str] = []
    content = content.resolve()
    if not content.is_dir():
        sys.exit(f"Notes folder not found: {content}")

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    images = ImageIndex(content)
    writer = ImageWriter(out, HERE / ".cache" / "img")
    md = make_markdown()

    # Dates: dates.json (CI) > git history > file mtime
    dates: dict[str, int] = {}
    for candidate in [dates_file, content / ".dates.json"]:
        if candidate and candidate.is_file():
            dates = json.loads(candidate.read_text(encoding="utf-8"))
            break
    if not dates:
        dates = git_added_dates(content)
    dates = {unicodedata.normalize("NFC", k): v for k, v in dates.items()}

    # 1. Parse
    recipes: list[Recipe] = []
    skipped: list[str] = []
    for path in sorted(content.rglob("*")):
        if not path.is_file() or any(p.startswith(".") or p.lower() in IGNORED_DIRS
                                     for p in path.relative_to(content).parts[:-1]):
            continue
        if path.suffix.lower() != ".md":
            if path.suffix == "" and not path.name.startswith("."):
                warnings.append(f"{path.relative_to(content)}: no .md extension, skipped")
            continue
        r = parse_note(path, content, images, warnings)
        if r is None:
            skipped.append(f"{path.relative_to(content)} (draft)")
            continue
        r._groups_raw = split_groups(tidy_lists(r._raw_body))
        if not r._groups_raw and not r.sources:
            skipped.append(f"{path.relative_to(content)} (empty)")
            continue
        r.added = dates.get(unicodedata.normalize("NFC", r.rel)) or int(path.stat().st_mtime)
        recipes.append(r)

    # Unique slugs
    seen: dict[str, int] = {}
    for r in recipes:
        s = slugify(r.title)
        if s in seen:
            s = f"{s}-{slugify(r.subcategory or r.category)}"
        seen[s] = seen.get(s, 0) + 1
        r.slug = s
    by_name = {}
    for r in recipes:
        by_name[fold(r.path.stem)] = r
        by_name.setdefault(fold(r.title), r)

    # 2. Resolve tags + links, render markdown
    def wikilink_sub(m):
        target, alias = m.group(1).strip(), (m.group(2) or "").strip()
        other = by_name.get(fold(target))
        text = alias or (other.title if other else target)
        return f"[{text}](../{other.slug}/)" if other else text

    def embed_sub(note_dir):
        def repl(m):
            ref, size = m.group(1), m.group(2) or ""
            p = images.find(ref, note_dir)
            if not p:
                warnings.append(f"image not found: {ref}")
                return ""
            info = writer.add(p)
            if not info:
                return ""
            return f'\n\n<figure><img src="../../{info["src"]}" srcset="{_prefix_srcset(info["srcset"])}" sizes="(min-width: 760px) 640px, 100vw" alt="" loading="lazy"></figure>\n\n'
        return repl

    for r in recipes:
        tags = []
        for t in r._tags_raw:
            if t.startswith("@"):
                name = t[1:]
                if fold(name) in by_name and by_name[fold(name)] is not r:
                    continue  # a link to another recipe, not a tag
                t = name
            t = slugify(t.replace("_", "-"))
            if t and t not in IGNORED_TAGS and t not in tags:
                tags.append(t)
        r.tags = tags
        r.related_links = [by_name[fold(n)] for n in r.links if fold(n) in by_name and by_name[fold(n)] is not r]

        groups = []
        ingredient_words = []
        for gtitle, secs in r._groups_raw:
            g = Group(title=gtitle, title_html=md.renderInline(WIKILINK_RE.sub(wikilink_sub, gtitle)))
            for kind, smd in secs:
                smd = EMBED_RE.sub(embed_sub(r.path.parent), smd)
                smd = MD_IMAGE_RE.sub(lambda m: m.group(0) if m.group(2).startswith("http")
                                      else embed_sub(r.path.parent)(EMBED_RE.match(f"![[{m.group(2)}]]")), smd)
                smd = WIKILINK_RE.sub(wikilink_sub, smd)
                rendered = md.render(smd)
                rendered = rendered.replace("<a href=\"http", "<a rel=\"noopener\" target=\"_blank\" href=\"http")
                if kind in ("ingredients", "steps"):
                    rendered = mark_sublabels(rendered)
                if kind == "ingredients":
                    ingredient_words.append(re.sub(r"<[^>]+>", " ", rendered))
                g.sections.append(Section(kind=kind, md=smd, html=rendered))
            groups.append(g)
        r.groups = groups
        r.ingredients_text = re.sub(r"\s+", " ", " ".join(ingredient_words))[:600]
        if r.intro_md:
            r.intro_html = md.render(WIKILINK_RE.sub(wikilink_sub, r.intro_md))
            r.description = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", r.intro_html)).strip()
        r.hero = writer.add(r.image) if r.image else None
        r.kinds = {s.kind for g in r.groups for s in g.sections}

    # 3. Categories
    cats: dict[str, dict] = {}
    for r in recipes:
        c = cats.setdefault(r.category, {"key": r.category, "label": label(r.category), "count": 0, "subs": {}})
        c["count"] += 1
        if r.subcategory:
            s = c["subs"].setdefault(r.subcategory, {"key": r.subcategory, "label": label(r.subcategory), "count": 0})
            s["count"] += 1
    categories = sorted(cats.values(), key=lambda c: (-c["count"], c["label"]))  # biggest first
    for c in categories:
        c["subs"] = sorted(c["subs"].values(), key=lambda s: s["label"])

    recipes.sort(key=lambda r: fold(r.title))
    latest = sorted([r for r in recipes if r.hero], key=lambda r: -r.added)[:4]
    tag_counts: dict[str, int] = {}
    for r in recipes:
        for t in r.tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1

    # 4. Render
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["domain"] = lambda u: re.sub(r"^www\.", "", re.sub(r"^https?://([^/]+).*$", r"\1", u))
    env.filters["label"] = label
    env.filters["fold"] = fold
    tagline = SITE_TAGLINE if isinstance(SITE_TAGLINE, dict) else {LANGUAGES[0]: SITE_TAGLINE}
    page_i18n = {"languages": LANGUAGES, "labels": label_translations([r.category for r in recipes] + [r.subcategory for r in recipes]),
                 "tagline": {lang: tagline.get(lang) or tagline[LANGUAGES[0]] for lang in LANGUAGES}}
    common = dict(site_title=SITE_TITLE, tagline=tagline.get(LANGUAGES[0]) or next(iter(tagline.values())),
                  languages=LANGUAGES, lang=LANGUAGES[0], page_i18n=json.dumps(page_i18n, ensure_ascii=False), site_url=SITE_URL.rstrip("/"),
                  categories=categories, year=time.strftime("%Y"), asset_version=str(int(t0)))

    for r in recipes:
        same = [o for o in recipes if o is not r and o.category == r.category and o.subcategory == r.subcategory]
        same.sort(key=lambda o: (o.hero is None, -o.added))
        more = (r.related_links + [o for o in same if o not in r.related_links])[:4]
        page = env.get_template("recipe.html").render(r=r, more=more, root="../../", **common)
        d = out / "recipes" / r.slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")

    search_index = [{"s": r.slug, "t": fold(" ".join([r.title, r.credit] + [label(f, l) for f in (r.category, r.subcategory) if f for l in LANGUAGES] + [
                                                         " ".join(r.tags), r.ingredients_text, r.path.stem]))}
                    for r in recipes]
    (out / "index.html").write_text(env.get_template("index.html").render(
        recipes=recipes, latest=latest, tags=sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0])),
        search_index=json.dumps(search_index, ensure_ascii=False), root="", **common), encoding="utf-8")
    (out / "404.html").write_text(env.get_template("404.html").render(root=(re.sub(r"^https?://[^/]+", "", SITE_URL).rstrip("/") + "/"), **common), encoding="utf-8")

    shutil.copytree(HERE / "static", out / "static")
    (out / ".nojekyll").write_text("")

    print(f"Built {len(recipes)} recipes, {sum(1 for v in writer.done.values() if v)} photos in {time.time() - t0:.1f}s -> {out}")
    if skipped:
        print("Skipped:\n  " + "\n  ".join(skipped))
    if warnings:
        print("Warnings:\n  " + "\n  ".join(sorted(set(warnings))))
    return warnings


def _prefix_srcset(srcset: str) -> str:
    return ", ".join("../../" + part.strip() for part in srcset.split(",")) if srcset else ""


def serve(out: Path, port: int):
    import functools
    import http.server
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
    print(f"Serving on http://localhost:{port}  (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "dates":
        if len(sys.argv) != 3:
            sys.exit("usage: build.py dates <notes_dir>")
        print(json.dumps(git_added_dates(Path(sys.argv[2])), ensure_ascii=False, indent=0))
        return
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--content", type=Path, default=HERE / "content", help="folder with the recipe notes")
    ap.add_argument("--out", type=Path, default=HERE / "_site")
    ap.add_argument("--dates", type=Path, help="json file mapping note paths to unix times")
    ap.add_argument("--serve", action="store_true", help="serve the site after building")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    build(args.content.expanduser(), args.out.expanduser(), args.dates)
    if args.serve:
        serve(args.out, args.port)


if __name__ == "__main__":
    main()
