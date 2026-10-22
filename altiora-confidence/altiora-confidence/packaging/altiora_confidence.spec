# PyInstaller recipe for Altiora Confidence.  Build with:  pyinstaller packaging/altiora_confidence.spec
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
RES = ROOT / "packaging" / "resources"

datas = [(str(ROOT / "app" / "assets"), "app/assets")]
if (RES / "models").exists():
    datas.append((str(RES / "models"), "models"))
if (RES / "tessdata").exists():
    datas.append((str(RES / "tessdata"), "tessdata"))
binaries, hiddenimports = [], []
for pkg in ["spacy", "thinc", "srsly", "catalogue", "confection", "cymem", "preshed", "murmurhash", "blis",
            "wasabi", "spacy_legacy", "spacy_loggers", "langcodes", "pymupdf"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        pass

# Only French + English language support from spaCy (the other ~70 languages are dead weight)
KEEP_LANGS = ("fr", "en", "xx")
def _keep(path_or_mod):
    s = str(path_or_mod).replace("\\", "/").replace(".", "/")
    if "spacy/lang/" in s:
        lang = s.split("spacy/lang/")[1].split("/")[0]
        return lang in KEEP_LANGS or lang.startswith("__") or lang in ("char_classes", "lex_attrs", "norm_exceptions",
                                                                         "punctuation", "tokenizer_exceptions", "py")
    return "spacy/tests" not in s
hiddenimports = [h for h in hiddenimports if _keep(h)]
datas = [d for d in datas if _keep(d[0])]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["cv2", "onnxruntime", "scipy", "pymupdf4llm", "pymupdf_layout", "tkinter", "matplotlib", "IPython", "jupyter", "torch", "tensorflow", "pandas",
              "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick",
              "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Altiora Confidence",
    icon=str(ROOT / "app" / "assets" / ("icon.icns" if sys.platform == "darwin" else "icon.ico")),
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Altiora Confidence")

# macOS: wrap everything in "Altiora Confidence.app"
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Altiora Confidence.app",
        icon=str(ROOT / "app" / "assets" / "icon.icns"),
        bundle_identifier="com.altiora.confidence",
        version="1.0",
        info_plist={
            "CFBundleDisplayName": "Altiora Confidence",
            "CFBundleShortVersionString": "1.0",
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": True,   # light look, like on Windows
            # lets people drop PDFs on the Dock icon / use "Ouvrir avec"
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "PDF",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["com.adobe.pdf"],
            }],
        },
    )
