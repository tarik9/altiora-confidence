"""
Anonymisation engine (offline).

    analysis = analyze("contrat.pdf", Options())      # find everything to hide -> editable list of Hit
    ...the user reviews: hit.enabled = False / add_word() / add_zone()...
    result = apply(analysis, "contrat_anonymise.pdf", style="black")

Nothing here touches the network: the spaCy models and OCR language files are read from disk.
"""

from __future__ import annotations

import csv
import itertools
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pymupdf
except ImportError:  # older PyMuPDF
    import fitz as pymupdf

from .patterns import (
    ADDRESS_PATTERNS,
    ALL_CATEGORIES,
    DATE_PATTERNS,
    DEFAULT_CATEGORIES,
    EXTRA_PATTERNS,
    COMPANY_PATTERNS,
    COUNTRIES,
    JOB_TITLES,
    NAME_CONTEXT_PATTERNS,
    REGISTRATION_PATTERN,
    COMPANY_WORDS,
    DEMONYMS,
    FUNCTION_WORDS,
    HEADING_WORDS,
    LABELS,
    LEGAL_FORMS,
    NOT_NAMES,
    SIGNATURE_MARKERS,
    TITLE_PATTERN,
)

# --------------------------------------------------------------------------------------
# Where bundled resources live (works both from source and inside the packaged .exe)
# --------------------------------------------------------------------------------------


def resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def _setup_tessdata():
    """OCR language files: bundled 'tessdata' folder first, then a normal Tesseract install."""
    for bundled in (resource_dir() / "tessdata", resource_dir() / "packaging" / "resources" / "tessdata"):
        if bundled.is_dir() and any(bundled.glob("*.traineddata")):
            os.environ["TESSDATA_PREFIX"] = str(bundled)
            return
    if os.environ.get("TESSDATA_PREFIX"):
        return
    for d in [
        r"C:\Program Files\Tesseract-OCR\tessdata",
        r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tessdata"),
        "/opt/homebrew/share/tessdata",
        "/usr/local/share/tessdata",
        "/usr/share/tesseract-ocr/5/tessdata",
        "/usr/share/tesseract-ocr/4.00/tessdata",
        "/usr/share/tessdata",
    ]:
        if os.path.isdir(d):
            os.environ["TESSDATA_PREFIX"] = d
            return


_setup_tessdata()


def ocr_languages() -> str:
    """'fra+eng' if available, else whatever is installed."""
    d = os.environ.get("TESSDATA_PREFIX")
    have = {p.stem for p in Path(d).glob("*.traineddata")} if d and os.path.isdir(d) else set()
    langs = [l for l in ("fra", "eng") if l in have]
    return "+".join(langs) if langs else ""


# --------------------------------------------------------------------------------------
# AI model (spaCy) - loaded once, from disk
# --------------------------------------------------------------------------------------

_NLP: dict = {}
MODEL_NAMES = {
    "fr": ["fr_core_news_lg", "fr_core_news_md", "fr_core_news_sm"],
    "en": ["en_core_web_lg", "en_core_web_md", "en_core_web_sm"],
}


def load_nlp(lang: str):
    if lang in _NLP:
        return _NLP[lang]
    import spacy

    nlp = None
    models_dirs = [resource_dir() / "models", resource_dir() / "packaging" / "resources" / "models"]
    for name in MODEL_NAMES[lang]:
        try:
            local = next((d / name for d in models_dirs if (d / name).is_dir()), None)
            if local:
                nlp = spacy.load(local, disable=["lemmatizer"])
            else:
                nlp = spacy.load(name, disable=["lemmatizer"])
            break
        except (OSError, IOError):
            continue
    _NLP[lang] = nlp
    return nlp


def guess_language(text: str) -> str:
    words = re.findall(r"[a-zà-ÿ']+", text.lower())
    fr = sum(w in {"le", "la", "les", "des", "du", "et", "est", "pour", "dans", "une", "sur", "par", "au", "aux", "qui"} for w in words)
    en = sum(w in {"the", "and", "is", "for", "in", "of", "to", "with", "on", "by", "this", "that", "are", "be"} for w in words)
    return "fr" if fr >= en else "en"


# --------------------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------------------

_ids = itertools.count(1)


@dataclass
class Hit:
    page: int                       # 0-based
    rects: list                     # list of (x0, y0, x1, y1) in PDF points
    category: str
    text: str
    source: str = "auto"            # auto | manual
    enabled: bool = True
    id: int = field(default_factory=lambda: next(_ids))

    @property
    def key(self):
        """Hits with the same key are grouped in the review list ("Dupont" x 4)."""
        return (self.category, " ".join(self.text.split()).lower())


@dataclass
class Options:
    categories: set = field(default_factory=lambda: set(DEFAULT_CATEGORIES))
    always_hide: list = field(default_factory=list)   # names that must always be hidden
    never_hide: list = field(default_factory=list)    # words that must never be hidden
    lang: str = "auto"                                # auto | fr | en
    use_ai: bool = True
    ocr: bool = True
    remove_all_images: bool = False


@dataclass
class Analysis:
    path: Path
    page_count: int
    lang: str
    hits: list
    page_words: list          # per page: list of (x0, y0, x1, y1, text, block, line, wordno)
    scanned_pages: list       # pages read with OCR (0-based)
    unreadable_pages: list    # pages with no text at all (0-based)
    ai_available: bool = True

    def enabled_hits(self):
        return [h for h in self.hits if h.enabled]


@dataclass
class Result:
    output: Path
    hidden_count: int
    counts: dict
    leaks: list               # texts still findable after redaction (should be empty)
    report: Path | None = None


class Cancelled(Exception):
    pass


# --------------------------------------------------------------------------------------
# Text extraction with word positions
# --------------------------------------------------------------------------------------


class PageText:
    def __init__(self, page, ocr=False):
        self.page = page
        self.ocr_used = False
        words = page.get_text("words", sort=True)
        if not words and ocr and ocr_languages() and page.get_images():
            try:
                tp = page.get_textpage_ocr(language=ocr_languages(), dpi=300, full=True)
                words = page.get_text("words", textpage=tp, sort=True)
                self.ocr_used = True
            except Exception:
                words = []
        self.words = [tuple(w) for w in words]
        parts, self.spans = [], []
        pos, prev = 0, None
        for w in self.words:
            key = (w[5], w[6])
            if prev is not None:
                parts.append(" " if key == prev else "\n")
                pos += 1
            self.spans.append((pos, pos + len(w[4])))
            parts.append(w[4])
            pos += len(w[4])
            prev = key
        self.text = "".join(parts)
        self._ents = None

    def rects_for(self, start, end):
        by_line = {}
        for (s, e), w in zip(self.spans, self.words):
            if e <= start or s >= end:
                continue
            r = pymupdf.Rect(w[:4])
            n = max(len(w[4]), 1)
            if s < start or e > end:
                a, b = max(s, start) - s, min(e, end) - s
                r = pymupdf.Rect(r.x0 + r.width * a / n, r.y0, r.x0 + r.width * b / n, r.y1)
            key = (w[5], w[6])
            by_line[key] = by_line[key] | r if key in by_line else r
        return list(by_line.values())


# --------------------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------------------

TITLE_PREFIX = re.compile(
    r"^(?:M\.|Mr\.?|Mrs\.?|Ms\.?|Mme\.?|Mlle\.?|Monsieur|Madame|Mademoiselle|Dr\.?|Docteur|Me\.?|Ma[iî]tre|Pr\.?)\s+"
)


def _find_patterns(text, patterns, category, found, flags=0):
    for p in patterns:
        for m in re.finditer(p, text, flags=flags):
            s, e = m.span()
            frag = text[s:e].split("\n")[0].rstrip(" .:;-,")
            e = s + len(frag)
            if e > s and frag.strip():
                found.append((s, e, category))


def _clean_name(ent_text):
    if "\n" in ent_text:
        return None
    t = ent_text.strip(" \n.,;:()'\"-")
    t = TITLE_PREFIX.sub("", t)
    tokens = [x for x in re.split(r"\s+", t) if x]
    if not tokens or not t[:1].isupper():
        return None
    if any(ch.isdigit() for ch in t) or len(t) < 3 or len(tokens) > 6:
        return None
    if all(tok.lower().strip(".,") in NOT_NAMES or tok.lower().strip(".,") in JOB_TITLES for tok in tokens):
        return None
    return t


def _line_bounds(text, pos):
    s = text.rfind("\n", 0, pos) + 1
    e = text.find("\n", pos)
    return s, (len(text) if e == -1 else e)


def _clean_company(t):
    """Trim function/heading words at the edges; None if nothing company-like remains."""
    toks = t.split()
    while toks and (toks[0].lower() in FUNCTION_WORDS or toks[0].lower() in HEADING_WORDS
                    or toks[0].lower() in ("la", "le", "société", "societe", "entreprise", "cabinet", "groupe")):
        toks = toks[1:]
    while toks and toks[-1].lower() in FUNCTION_WORDS:
        toks = toks[:-1]
    if not toks:
        return None
    # at least one distinctive word (not just "SOLUTIONS", "Conseil"...)
    if all(x.lower().strip(",.") in COMPANY_WORDS or x.lower() in NOT_NAMES or re.fullmatch(LEGAL_FORMS, x) for x in toks):
        return None
    return " ".join(toks)


def _find_companies(text):
    out = []
    for p in COMPANY_PATTERNS:
        for m in re.finditer(p, text):
            frag = m.group(1)
            if "\n" in frag:
                frag = frag.split("\n")[0]
            c = _clean_company(frag)
            if c:
                st = m.start(1) + frag.find(c)
                out.append((st, st + len(c)))
    # ALL-CAPS names containing a company word: "QUALISERO IT SOLUTIONS", "ALTIORA SOLUTIONS"
    for m in re.finditer(r"\b[A-ZÀ-Ý][A-ZÀ-Ý0-9&'\-]+(?:[ \t]+[A-ZÀ-Ý0-9&'\-]{2,}){1,4}\b", text):
        toks = m.group(0).split()
        low = [t.lower() for t in toks]
        if any(t in FUNCTION_WORDS for t in low) or low[0] in HEADING_WORDS:
            continue
        if not any(t in COMPANY_WORDS for t in low):
            continue
        c = _clean_company(m.group(0))
        if c:
            st = m.start() + m.group(0).find(c)
            out.append((st, st + len(c)))
    return out


def _company_variants(found_texts):
    """'QUALISERO IT SOLUTIONS' -> also catch 'QUALISERO' and 'ALTIORA SOLUTION' style variants elsewhere."""
    keys = set()
    for t in found_texts:
        for tok in t.split():
            tl = tok.lower().strip(",.")
            if len(tl) >= 3 and tl not in COMPANY_WORDS and tl not in NOT_NAMES and tl not in FUNCTION_WORDS \
                    and not re.fullmatch(LEGAL_FORMS, tok):
                keys.add(tok.strip(",."))
    tail = r"(?:\s+(?:" + "|".join(sorted(COMPANY_WORDS, key=len, reverse=True)) + r"|" + LEGAL_FORMS + r"))*"
    return [re.compile(r"(?<![\wÀ-ÿ])" + re.escape(k) + r"(?i:" + tail + r")(?![\wÀ-ÿ])", re.IGNORECASE) for k in keys]


def _detect(pt, cats, lang, known_names, never_hide, use_ai, known_orgs=None):
    text = pt.text
    found, names, orgs = [], set(), set()

    # "en qualité de Dirigeant", "agissant en tant que Gérant": never a person
    role_spans = [m.span(1) for m in re.finditer(
        r"(?i:en\s+(?:sa\s+)?qualit[ée]\s+de|en\s+tant\s+que|agissant\s+comme|as\s+(?:its|the))\s+([^,.;:\n()]{1,60})", text)]

    def in_role(st):
        return any(a <= st < b for a, b in role_spans)

    if "name" in cats:
        for m in re.finditer(TITLE_PATTERN, text):
            s, e = m.span(2)
            n = _clean_name(m.group(2))
            if n:
                found.append((s, s + len(n), "name"))
                names.add(n)
        for p in NAME_CONTEXT_PATTERNS:
            for m in re.finditer(p, text):
                frag = m.group(1)
                n = _clean_name(frag)
                if n and not in_role(m.start(1)):
                    st = m.start(1) + frag.find(n)
                    found.append((st, st + len(n), "name"))
                    names.add(n)

    # Address patterns first: the AI's places are only "addresses" when they sit on an address line
    addr_hits = []
    if "address" in cats or "place" in cats:
        _find_patterns(text, ADDRESS_PATTERNS, "address", addr_hits)
    addr_lines = {_line_bounds(text, s) for s, _, _ in addr_hits}

    def on_address_line(start):
        ls, le = _line_bounds(text, start)
        if (ls, le) in addr_lines:
            return True
        # a person's place of birth / residence: "né le 14/03/1985 à Lyon", "domicilié à Rabat", "born in Leeds"
        if re.search(r"(?i)\b(n[ée]e?s?|domicili[ée]e?s?|demeurant|r[ée]sidant|born|living)\b[^\n]{0,40}$", text[ls:start]):
            return True
        # "…, 93800 Épinay-sur-Seine,\nFRANCE, représentée par…": first word of the next line
        prev = _line_bounds(text, ls - 1) if ls > 0 else None
        return prev in addr_lines and not text[ls:start].strip(" ,•-–")

    if any(c in cats for c in ("name", "org", "address", "place")):
        nlp = load_nlp(lang) if use_ai else None
        if nlp is not None and text.strip():
            if getattr(pt, "_ents", None) is None:  # run the AI once per page, reuse on the 2nd pass
                pt._ents = [(e.label_, e.text, e.start_char, any(t.pos_ == "PROPN" for t in e)) for e in nlp(text).ents]
            for label, ent_text, ent_start, has_propn in pt._ents:
                if in_role(ent_start):
                    continue
                if label in ("PER", "PERSON"):
                    cat = "name"
                elif label == "ORG":
                    cat = "org"
                elif label in ("LOC", "GPE"):
                    cat = "address" if on_address_line(ent_start) else "place"
                else:
                    continue
                if cat not in cats:
                    continue
                # Places and companies must contain a real proper noun: drops "Fournir", "Prestation", "Conseil"
                if cat in ("org", "address", "place") and not has_propn:
                    continue
                n = _clean_name(ent_text)
                if not n:
                    continue
                if cat in ("address", "place") and n.lower() in DEMONYMS:
                    continue
                if cat == "org":
                    if n.lower() in COUNTRIES:
                        continue
                    n = _clean_company(n)
                    if not n:
                        continue
                s = ent_start + ent_text.find(n)
                found.append((s, s + len(n), cat))
                if cat == "name":
                    names.add(n)
                elif cat == "org":
                    orgs.add(n)
        if "name" in cats:
            for n in known_names:
                for m in re.finditer(r"(?<![\wÀ-ÿ])" + re.escape(n) + r"(?![\wÀ-ÿ])", text, flags=re.IGNORECASE):
                    found.append((m.start(), m.end(), "name"))

    if "org" in cats:
        for s, e in _find_companies(text):
            found.append((s, e, "org"))
            orgs.add(text[s:e])
        for rx in known_orgs or []:
            for m in rx.finditer(text):
                found.append((m.start(), m.end(), "org"))

    if "date" in cats:
        _find_patterns(text, DATE_PATTERNS, "date", found, re.IGNORECASE)
    if "address" in cats:
        found += addr_hits
    for cat in ("email", "phone", "id"):
        if cat in cats:
            _find_patterns(text, EXTRA_PATTERNS[cat], cat, found, re.IGNORECASE if cat == "email" else 0)
    if "id" in cats:
        for m in re.finditer(REGISTRATION_PATTERN, text):
            frag = m.group(1).split("\n")[0].rstrip(" .-")
            if sum(ch.isdigit() for ch in frag) >= 6:
                found.append((m.start(1), m.start(1) + len(frag), "id"))

    if never_hide:
        keep = {k.lower() for k in never_hide}
        found = [f for f in found if text[f[0]:f[1]].strip().lower() not in keep]
    pt._orgs = orgs
    return found, names


def _merge(found):
    priority = {c: i for i, c in enumerate(["email", "id", "phone", "date", "name", "address", "org", "place", "signature"])}
    found = sorted(found, key=lambda f: (f[0], -(f[1] - f[0]), priority.get(f[2], 99)))
    merged = []
    for s, e, c in found:
        if merged and s < merged[-1][1]:
            ps, pe, pc = merged[-1]
            if e > pe:
                merged[-1] = (ps, e, pc)
            continue
        merged.append((s, e, c))
    return merged


def _signature_zones(pt, zone_w=230, zone_h=90):
    pr = pt.page.rect
    zones, lines = [], {}
    for w in pt.words:
        lines.setdefault((w[5], w[6]), []).append(w)
    for ws in lines.values():
        line_text = " ".join(w[4] for w in ws)
        for marker in SIGNATURE_MARKERS:
            if not re.search(r"(?<![\wÀ-ÿ])" + marker + r"(?![\wÀ-ÿ])", line_text, flags=re.IGNORECASE):
                continue
            if len(ws) > 5 and not line_text.rstrip().endswith(":"):
                break
            lr = pymupdf.Rect(ws[0][:4])
            for w in ws:
                lr |= pymupdf.Rect(w[:4])
            right = pymupdf.Rect(lr.x1 + 4, lr.y0 - 2, min(pr.x1, lr.x0 + zone_w), lr.y1 + 2)
            below = pymupdf.Rect(max(pr.x0, lr.x0 - 15), lr.y1 + 1, min(pr.x1, lr.x0 + zone_w), min(pr.y1, lr.y1 + zone_h))
            if right.width > 5:
                zones.append(right)
            zones.append(below)
            break
    return zones


def _image_and_drawing_rects(page):
    imgs = []
    for img in page.get_images(full=True):
        try:
            imgs += [pymupdf.Rect(r) for r in page.get_image_rects(img[0])]
        except Exception:
            pass
    draws = []
    for d in page.get_drawings():
        r = pymupdf.Rect(d["rect"])
        if len(d.get("items", [])) >= 4 and r.width > 15 and r.height > 5:
            draws.append(r)
    return imgs, draws


def _propagate(names, never_hide):
    """'M. Jean Dupont' found once -> also hide 'Jean Dupont' and 'Dupont' everywhere."""
    out = set()
    for n in names:
        out.add(n)
        for tok in re.split(r"\s+", n):
            tok = tok.strip(".,;:()")
            if len(tok) >= 3 and tok.lower() not in NOT_NAMES and tok.lower() not in JOB_TITLES and tok[:1].isupper() \
                    and not re.fullmatch(r"[A-Z]\.", tok):
                out.add(tok)
    keep = {k.lower() for k in never_hide}
    return sorted((n for n in out if n.lower() not in keep), key=len, reverse=True)


def analyze(path, options: Options | None = None, progress=None, cancel=None) -> Analysis:
    """Find everything to hide. progress(step, total, message) is called as pages are processed."""
    options = options or Options()
    path = Path(path)
    cats = set(options.categories)
    doc = pymupdf.open(path)
    if doc.needs_pass:
        doc.close()
        raise ValueError("Ce PDF est protégé par un mot de passe.")
    n = doc.page_count
    total_steps = n * 2 + 1

    def tick(i, msg):
        if cancel and cancel():
            raise Cancelled()
        if progress:
            progress(i, total_steps, msg)

    pages = []
    for i, p in enumerate(doc):
        tick(i, f"Lecture de la page {i + 1}/{n}")
        pages.append(PageText(p, ocr=options.ocr))

    lang = options.lang if options.lang != "auto" else guess_language("\n".join(p.text for p in pages))
    tick(n, "Chargement du modèle IA…")
    ai_ok = (load_nlp(lang) is not None) if options.use_ai else False

    names, orgs = set(options.always_hide), set()
    for pt in pages:
        _, found_names = _detect(pt, cats, lang, [], options.never_hide, options.use_ai)
        names |= found_names
        orgs |= getattr(pt, "_orgs", set())
    known = _propagate(names, options.never_hide)
    keep_l = {k.lower() for k in options.never_hide}
    known_orgs = _company_variants([o for o in orgs if o.lower() not in keep_l]) if "org" in cats else []

    hits = []
    for pt in pages:
        i = pt.page.number
        tick(n + 1 + i, f"Analyse de la page {i + 1}/{n}")
        page = pt.page
        found, _ = _detect(pt, cats, lang, known, options.never_hide, options.use_ai, known_orgs)
        pad = 1.5 if pt.ocr_used else 0.5
        for s, e, c in _merge(found):
            rects = [_pad(r, pad, page.rect) for r in pt.rects_for(s, e)]
            rects = [r for r in rects if r]
            if rects:
                hits.append(Hit(i, rects, c, " ".join(pt.text[s:e].split())))

        if "signature" in cats:
            imgs, draws = _image_and_drawing_rects(page)
            area, done = abs(page.rect), []
            for z in _signature_zones(pt):
                if pt.ocr_used:
                    hits.append(Hit(i, [tuple(z)], "signature", "Zone de signature (page scannée)"))
                    continue
                for r in imgs + draws:
                    if not r.intersects(z) or any(r == d for d in done):
                        continue
                    target = (r & z) if abs(r) > 0.25 * area else r
                    hits.append(Hit(i, [_pad(target, 1, page.rect)], "signature", "Signature"))
                    done.append(r)
        if options.remove_all_images:
            imgs, _ = _image_and_drawing_rects(page)
            for r in imgs:
                hits.append(Hit(i, [tuple(r & page.rect)], "signature", "Image"))

    analysis = Analysis(
        path=path,
        page_count=n,
        lang=lang,
        hits=hits,
        page_words=[pt.words for pt in pages],
        scanned_pages=[pt.page.number for pt in pages if pt.ocr_used],
        unreadable_pages=[pt.page.number for pt in pages if not pt.words],
        ai_available=ai_ok,
    )
    doc.close()
    if progress:
        progress(total_steps, total_steps, "Terminé")
    return analysis


def _pad(r, pad, page_rect):
    r = pymupdf.Rect(r)
    r = pymupdf.Rect(r.x0 - pad, r.y0 - pad, r.x1 + pad, r.y1 + pad) & page_rect
    return None if r.is_empty else tuple(r)


# --------------------------------------------------------------------------------------
# Manual edits made in the review screen
# --------------------------------------------------------------------------------------


def find_word_at(analysis: Analysis, page: int, x: float, y: float):
    """The word under a click (PDF coordinates), or None."""
    for w in analysis.page_words[page]:
        if w[0] - 1 <= x <= w[2] + 1 and w[1] - 1 <= y <= w[3] + 1:
            return w
    return None


def add_word_hit(analysis: Analysis, page: int, word) -> Hit:
    text = word[4].strip(".,;:()«»\"'")
    h = Hit(page, [_pad(word[:4], 0.5, pymupdf.Rect(-1e6, -1e6, 1e6, 1e6))], "manual", text or word[4], source="manual")
    analysis.hits.append(h)
    return h


def add_zone_hit(analysis: Analysis, page: int, rect) -> Hit:
    h = Hit(page, [tuple(rect)], "manual", "Zone dessinée", source="manual")
    analysis.hits.append(h)
    return h


def add_text_everywhere(analysis: Analysis, text: str, category: str = "name") -> list:
    """Hide every occurrence of `text` (case-insensitive) in the document. Returns new hits."""
    text = " ".join(text.split())
    if not text:
        return []
    new = []
    pat = re.compile(r"(?<![\wÀ-ÿ])" + re.escape(text).replace(r"\ ", r"\s+") + r"(?![\wÀ-ÿ])", re.IGNORECASE)
    for i, words in enumerate(analysis.page_words):
        if not words:
            continue
        # rebuild the page text with the same layout as PageText
        parts, spans, pos, prev = [], [], 0, None
        for w in words:
            key = (w[5], w[6])
            if prev is not None:
                parts.append(" " if key == prev else "\n")
                pos += 1
            spans.append((pos, pos + len(w[4])))
            parts.append(w[4])
            pos += len(w[4])
            prev = key
        page_text = "".join(parts)
        for m in pat.finditer(page_text):
            s, e = m.span()
            by_line = {}
            for (ws, we), w in zip(spans, words):
                if we <= s or ws >= e:
                    continue
                r = pymupdf.Rect(w[:4])
                nlen = max(len(w[4]), 1)
                if ws < s or we > e:
                    a, b = max(ws, s) - ws, min(we, e) - ws
                    r = pymupdf.Rect(r.x0 + r.width * a / nlen, r.y0, r.x0 + r.width * b / nlen, r.y1)
                k = (w[5], w[6])
                by_line[k] = by_line[k] | r if k in by_line else r
            rects = [tuple(pymupdf.Rect(r.x0 - 0.5, r.y0 - 0.5, r.x1 + 0.5, r.y1 + 0.5)) for r in by_line.values()]
            # skip if an enabled hit already covers this spot
            if any(h.page == i and h.enabled and _covers(h.rects, rects) for h in analysis.hits):
                continue
            h = Hit(i, rects, category, m.group(0), source="manual")
            analysis.hits.append(h)
            new.append(h)
    return new


def _covers(a_rects, b_rects):
    for b in b_rects:
        rb = pymupdf.Rect(b)
        if not any(pymupdf.Rect(a).contains(pymupdf.Rect(rb.x0 + 1, rb.y0 + 1, rb.x1 - 1, rb.y1 - 1)) for a in a_rects):
            return False
    return True


# --------------------------------------------------------------------------------------
# Applying the redactions
# --------------------------------------------------------------------------------------


def apply(analysis: Analysis, out_path, style: str = "black", report: bool = False) -> Result:
    """Permanently remove every enabled hit. style: black | label | white."""
    out_path = Path(out_path)
    doc = pymupdf.open(analysis.path)
    hits = analysis.enabled_hits()
    counts = {}
    for h in hits:
        counts[h.category] = counts.get(h.category, 0) + 1
        page = doc[h.page]
        for r in h.rects:
            r = pymupdf.Rect(r) & page.rect
            if r.is_empty:
                continue
            if style == "label":
                label = LABELS.get(h.category, "[MASQUÉ]")
                fs = max(4, min(9, r.height * 0.75, r.width / max(len(label), 1) * 1.9))
                page.add_redact_annot(r, text=label, fontname="helv", fontsize=fs, align=pymupdf.TEXT_ALIGN_CENTER,
                                      fill=(0.85, 0.85, 0.85), text_color=(0.15, 0.15, 0.15), cross_out=False)
            elif style == "white":
                page.add_redact_annot(r, fill=(1, 1, 1), cross_out=False)
            else:
                page.add_redact_annot(r, fill=(0, 0, 0), cross_out=False)
    for page in doc:
        page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                              graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED)
    doc.scrub(redactions=False)
    doc.set_metadata({})
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_path, garbage=4, deflate=True, clean=True)
    doc.close()

    # Check: none of the hidden texts can still be found in the output
    check = pymupdf.open(out_path)
    out_text = " ".join(" ".join(p.get_text().split()) for p in check).lower()
    check.close()
    # A lone city/country hidden inside an address may legitimately appear elsewhere ("(FRANCE)" in a title)
    texts = {h.text.lower() for h in hits
             if h.category not in ("signature", "place") and h.text != "Zone dessinée"
             and not (h.category == "address" and len(h.text.split()) == 1)}
    leaks = sorted(t for t in texts if len(t) >= 4 and re.search(r"(?<![\wà-ÿ])" + re.escape(t) + r"(?![\wà-ÿ])", out_text))
    # Words the user deliberately un-ticked elsewhere legitimately remain: ignore those
    kept = {h.text.lower() for h in analysis.hits if not h.enabled}
    leaks = [t for t in leaks if t not in kept]

    rep = None
    if report:
        rep = out_path.with_name(out_path.stem + "_rapport.csv")
        with open(rep, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["page", "categorie", "texte"])
            for h in sorted(hits, key=lambda h: (h.page, h.rects[0][1])):
                w.writerow([h.page + 1, h.category, h.text])
    return Result(out_path, len(hits), counts, leaks, rep)


def default_output(path) -> Path:
    path = Path(path)
    return path.with_name(path.stem + "_anonymise.pdf")
