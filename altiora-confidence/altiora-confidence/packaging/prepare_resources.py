"""Gather what the packaged app needs to work offline: AI models + OCR language files.
Run once before PyInstaller (the build script does it for you). Needs internet."""
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "packaging" / "resources"
MODELS = ["fr_core_news_md", "en_core_web_sm"]
TESSDATA_URL = "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/{}.traineddata"


def main():
    import spacy

    (OUT / "models").mkdir(parents=True, exist_ok=True)
    for name in MODELS:
        dest = OUT / "models" / name
        if dest.exists():
            print(f"[ok] model {name} already prepared")
            continue
        try:
            nlp = spacy.load(name)
        except OSError:
            print(f"[..] downloading model {name}")
            from spacy.cli import download
            download(name)
            import importlib
            importlib.invalidate_caches()
            nlp = spacy.load(name)
        nlp.to_disk(dest)
        print(f"[ok] model {name} saved")

    td = OUT / "tessdata"
    td.mkdir(parents=True, exist_ok=True)
    for lang in ("fra", "eng"):
        f = td / f"{lang}.traineddata"
        if f.exists() and f.stat().st_size > 100_000:
            print(f"[ok] OCR {lang} already prepared")
            continue
        print(f"[..] downloading OCR language {lang}")
        try:
            with urllib.request.urlopen(TESSDATA_URL.format(lang), timeout=120) as r, open(f, "wb") as out:
                shutil.copyfileobj(r, out)
            print(f"[ok] OCR {lang}")
        except Exception as e:
            print(f"[!!] could not download OCR {lang} ({e}). Scanned PDFs will not be readable; everything else works.")
            f.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
