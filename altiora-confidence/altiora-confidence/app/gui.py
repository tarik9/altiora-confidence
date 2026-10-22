"""Altiora Confidence - desktop interface (PySide6)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, QRectF, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCursor,
    QDesktopServices,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QToolTip,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import engine
from .engine import pymupdf
from .patterns import ALL_CATEGORIES, CATEGORY_NAMES, COLORS
from .settings import APP_NAME, Settings

VERSION = "1.0"

# --------------------------------------------------------------------------------------
# Look & feel
# --------------------------------------------------------------------------------------

ACCENT = "#2F4BD8"
ACCENT_DARK = "#2238A8"
INK = "#1D2433"
MUTED = "#667085"
LINE = "#E3E6EC"
BG = "#F4F5F8"

STYLE = f"""
* {{ color: {INK}; }}
QMainWindow, QWidget#Page {{ background: {BG}; }}
QWidget#Header {{ background: white; border-bottom: 1px solid {LINE}; }}
QLabel#AppTitle {{ font-size: 17px; font-weight: 700; }}
QLabel#Step {{ color: {MUTED}; font-size: 13px; padding: 4px 10px; border-radius: 12px; }}
QLabel#Step[active="true"] {{ color: white; background: {ACCENT}; font-weight: 600; }}
QLabel#Step[done="true"] {{ color: {ACCENT}; font-weight: 600; }}
QFrame#Card {{ background: white; border: 1px solid {LINE}; border-radius: 12px; }}
QLabel#CardTitle {{ font-size: 15px; font-weight: 700; }}
QLabel#H1 {{ font-size: 22px; font-weight: 700; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Small {{ color: {MUTED}; font-size: 12px; }}
QPushButton {{ background: white; border: 1px solid #CBD0DA; border-radius: 8px; padding: 7px 14px; font-size: 13px; }}
QPushButton:hover {{ background: #F0F2F7; }}
QPushButton:disabled {{ color: #A0A6B2; background: #F4F5F8; }}
QPushButton#Primary {{ background: {ACCENT}; border: none; color: white; font-weight: 600; padding: 10px 22px; font-size: 14px; }}
QPushButton#Primary:hover {{ background: {ACCENT_DARK}; }}
QPushButton#Primary:disabled {{ background: #AEB8E8; color: white; }}
QPushButton#Link {{ border: none; background: transparent; color: {ACCENT}; padding: 4px; }}
QPushButton#Link:hover {{ text-decoration: underline; }}
QPushButton#Tool {{ padding: 5px 9px; min-width: 18px; }}
QListWidget, QTreeWidget {{ background: white; border: 1px solid {LINE}; border-radius: 8px; padding: 4px; font-size: 13px; }}
QTreeWidget::item {{ padding: 3px 2px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: #E6EBFF; color: {INK}; }}
QLineEdit, QComboBox {{ background: white; border: 1px solid #CBD0DA; border-radius: 7px; padding: 6px 8px; font-size: 13px; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QCheckBox, QRadioButton {{ font-size: 13px; spacing: 8px; }}
QProgressBar {{ border: none; background: #E3E6EC; border-radius: 5px; height: 10px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 5px; }}
QScrollArea#PageScroll {{ background: #E9EBF0; border: none; }}
QFrame#Banner {{ border-radius: 8px; padding: 2px; }}
QFrame#Banner[kind="warn"] {{ background: #FFF6E0; border: 1px solid #F5D78E; }}
QFrame#Banner[kind="info"] {{ background: #EEF2FF; border: 1px solid #C9D3FF; }}
QFrame#Banner[kind="ok"] {{ background: #E9F8EF; border: 1px solid #A8E0BC; }}
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 8px; background: white; }}
"""


SINGULAR = {"name": "Nom", "date": "Date", "address": "Adresse", "signature": "Signature", "email": "Email",
            "phone": "Téléphone", "id": "Numéro", "org": "Société", "manual": "Ajout manuel"}


def qcolor(cat, alpha=255):
    r, g, b = COLORS.get(cat, (0.6, 0.6, 0.6))
    return QColor(int(r * 255), int(g * 255), int(b * 255), alpha)


def card(title=None):
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(10)
    if title:
        t = QLabel(title)
        t.setObjectName("CardTitle")
        lay.addWidget(t)
    return f, lay


def banner(kind, text):
    f = QFrame()
    f.setObjectName("Banner")
    f.setProperty("kind", kind)
    lay = QHBoxLayout(f)
    lay.setContentsMargins(12, 8, 12, 8)
    icon = {"warn": "⚠", "info": "ℹ", "ok": "✓"}[kind]
    lab = QLabel(f"{icon}  {text}")
    lab.setWordWrap(True)
    lay.addWidget(lab)
    return f


def dot(cat, size=10):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(qcolor(cat))
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.end()
    return QIcon(pm)


def open_path(path: Path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def reveal(path: Path):
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])
    else:
        open_path(path.parent)


def collect_pdfs(paths):
    out = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            out += sorted(x for x in p.glob("*.pdf") if not x.stem.endswith("_anonymise"))
        elif p.suffix.lower() == ".pdf" and p.exists():
            out.append(p)
    return out


# --------------------------------------------------------------------------------------
# Background workers
# --------------------------------------------------------------------------------------


class ModelLoader(QThread):
    """Loads the AI model while the user picks files, so analysis starts instantly."""

    def run(self):
        try:
            engine.load_nlp("fr")
        except Exception:
            pass


class AnalyzeWorker(QThread):
    progress = Signal(int, int, int, str)   # file index, step, total, message
    file_done = Signal(object)
    file_failed = Signal(str, str)
    all_done = Signal()

    def __init__(self, files, options):
        super().__init__()
        self.files, self.options, self._cancel = files, options, False

    def cancel(self):
        self._cancel = True

    def run(self):
        for i, f in enumerate(self.files):
            if self._cancel:
                break
            try:
                a = engine.analyze(f, self.options,
                                   progress=lambda s, t, m, i=i: self.progress.emit(i, s, t, m),
                                   cancel=lambda: self._cancel)
                self.file_done.emit(a)
            except engine.Cancelled:
                break
            except Exception as e:
                self.file_failed.emit(str(f), str(e))
        self.all_done.emit()


class ApplyWorker(QThread):
    done = Signal(list)   # list of (analysis, Result or error string)

    def __init__(self, jobs, style, report):
        super().__init__()
        self.jobs, self.style, self.report = jobs, style, report

    def run(self):
        results = []
        for analysis, out in self.jobs:
            try:
                results.append((analysis, engine.apply(analysis, out, style=self.style, report=self.report)))
            except PermissionError:
                results.append((analysis, f"Impossible d'écrire {out.name}. Est-il ouvert dans un autre programme ? Fermez-le et réessayez."))
            except Exception as e:
                results.append((analysis, str(e)))
        self.done.emit(results)


# --------------------------------------------------------------------------------------
# Screen 1 - choose files and options
# --------------------------------------------------------------------------------------


class DropZone(QFrame):
    files_dropped = Signal(list)
    clicked = Signal()

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setMinimumHeight(190)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)
        lay.setSpacing(6)
        icon = QLabel("📄")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 40px; background: transparent;")
        t = QLabel("Glissez vos PDF ici")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size: 17px; font-weight: 700; background: transparent;")
        s = QLabel("ou cliquez pour choisir des fichiers  ·  un dossier entier fonctionne aussi")
        s.setAlignment(Qt.AlignCenter)
        s.setStyleSheet(f"color: {MUTED}; background: transparent;")
        for w in (icon, t, s):
            lay.addWidget(w)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#EEF1FF") if self._hover else QColor("white"))
        pen = QPen(QColor(ACCENT if self._hover else "#B8C0D6"), 2, Qt.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 14, 14)

    def mouseReleaseEvent(self, e):
        self.clicked.emit()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._hover = True
            self.update()

    def dragLeaveEvent(self, e):
        self._hover = False
        self.update()

    def dropEvent(self, e):
        self._hover = False
        self.update()
        self.files_dropped.emit([u.toLocalFile() for u in e.mimeData().urls()])


class HomePage(QWidget):
    start = Signal(list)

    def __init__(self, settings: Settings):
        super().__init__()
        self.setObjectName("Page")
        self.settings = settings
        self.files: list[Path] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(20)

        # Left: files
        left = QVBoxLayout()
        left.setSpacing(12)
        title = QLabel("Quels documents voulez-vous anonymiser ?")
        title.setObjectName("H1")
        sub = QLabel("Tout se passe sur cet ordinateur : aucun fichier n'est envoyé sur internet.")
        sub.setObjectName("Muted")
        left.addWidget(title)
        left.addWidget(sub)
        left.addSpacing(6)
        self.drop = DropZone()
        self.drop.files_dropped.connect(self.add_files)
        self.drop.clicked.connect(self.browse)
        left.addWidget(self.drop)

        row = QHBoxLayout()
        self.count_label = QLabel("Aucun fichier sélectionné")
        self.count_label.setObjectName("Muted")
        row.addWidget(self.count_label)
        row.addStretch()
        self.btn_remove = QPushButton("Retirer")
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_clear = QPushButton("Tout retirer")
        self.btn_clear.clicked.connect(self.clear)
        row.addWidget(self.btn_remove)
        row.addWidget(self.btn_clear)
        left.addLayout(row)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        left.addWidget(self.list, 1)
        root.addLayout(left, 3)

        # Right: options
        right = QVBoxLayout()
        right.setSpacing(14)
        c, lay = card("Que faut-il masquer ?")
        self.cat_boxes = {}
        for cat in ALL_CATEGORIES:
            if cat == "manual":
                continue
            cb = QCheckBox(CATEGORY_NAMES[cat])
            cb.setIcon(dot(cat))
            cb.setChecked(cat in settings.categories)
            self.cat_boxes[cat] = cb
            lay.addWidget(cb)
        right.addWidget(c)

        c2, lay2 = card("Apparence des zones masquées")
        self.style_group = QButtonGroup(self)
        for key, label in [("black", "Rectangles noirs"), ("label", "Étiquettes grises  [NOM]  [DATE]…"), ("white", "Blanc (invisible)")]:
            rb = QRadioButton(label)
            rb.setProperty("key", key)
            rb.setChecked(settings.style == key)
            self.style_group.addButton(rb)
            lay2.addWidget(rb)
        right.addWidget(c2)

        c3, lay3 = card("Options")
        self.cb_images = QCheckBox("Supprimer toutes les images (logos et tampons aussi)")
        self.cb_images.setChecked(settings.remove_all_images)
        self.cb_report = QCheckBox("Créer un rapport CSV de ce qui a été masqué")
        self.cb_report.setChecked(settings.report)
        lay3.addWidget(self.cb_images)
        lay3.addWidget(self.cb_report)
        right.addWidget(c3)
        right.addStretch()

        self.btn_start = QPushButton("Analyser  →")
        self.btn_start.setObjectName("Primary")
        self.btn_start.setEnabled(False)
        self.btn_start.clicked.connect(self._start)
        right.addWidget(self.btn_start)
        root.addLayout(right, 2)

    # file list
    def browse(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choisir des PDF", str(Path.home()), "Documents PDF (*.pdf)")
        if files:
            self.add_files(files)

    def add_files(self, paths):
        new = collect_pdfs(paths)
        if not new and paths:
            QMessageBox.information(self, APP_NAME, "Aucun fichier PDF trouvé dans ce que vous avez déposé.")
        for p in new:
            if p not in self.files:
                self.files.append(p)
        self.refresh()

    def remove_selected(self):
        rows = sorted((self.list.row(i) for i in self.list.selectedItems()), reverse=True)
        for r in rows:
            del self.files[r]
        self.refresh()

    def clear(self):
        self.files.clear()
        self.refresh()

    def refresh(self):
        self.list.clear()
        for p in self.files:
            it = QListWidgetItem(f"📄  {p.name}")
            it.setToolTip(str(p))
            self.list.addItem(it)
        n = len(self.files)
        self.count_label.setText("Aucun fichier sélectionné" if n == 0 else f"{n} fichier{'s' if n > 1 else ''} sélectionné{'s' if n > 1 else ''}")
        self.btn_start.setEnabled(n > 0)
        self.btn_remove.setEnabled(n > 0)
        self.btn_clear.setEnabled(n > 0)

    def selected_categories(self):
        return {c for c, cb in self.cat_boxes.items() if cb.isChecked()}

    def style(self):
        b = self.style_group.checkedButton()
        return b.property("key") if b else "black"

    def _start(self):
        if not self.selected_categories():
            QMessageBox.information(self, APP_NAME, "Cochez au moins une chose à masquer.")
            return
        s = self.settings
        s.categories = sorted(self.selected_categories())
        s.style = self.style()
        s.report = self.cb_report.isChecked()
        s.remove_all_images = self.cb_images.isChecked()
        s.save()
        self.start.emit(list(self.files))


# --------------------------------------------------------------------------------------
# Screen 2 - analysis progress
# --------------------------------------------------------------------------------------


class AnalyzingPage(QWidget):
    cancel = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        c, lay = card()
        c.setFixedWidth(520)
        lay.setContentsMargins(32, 30, 32, 30)
        lay.setSpacing(12)
        self.title = QLabel("Analyse en cours…")
        self.title.setObjectName("H1")
        self.file = QLabel("")
        self.file.setObjectName("Muted")
        self.bar = QProgressBar()
        self.bar.setFixedHeight(10)
        self.msg = QLabel("")
        self.msg.setObjectName("Small")
        btn = QPushButton("Annuler")
        btn.clicked.connect(self.cancel.emit)
        lay.addWidget(self.title)
        lay.addWidget(self.file)
        lay.addSpacing(8)
        lay.addWidget(self.bar)
        lay.addWidget(self.msg)
        lay.addSpacing(8)
        lay.addWidget(btn, 0, Qt.AlignRight)
        outer.addWidget(c, 0, Qt.AlignCenter)

    def set_progress(self, file_idx, n_files, name, step, total, msg):
        self.file.setText(f"Fichier {file_idx + 1} sur {n_files} : {name}")
        overall = (file_idx + step / max(total, 1)) / n_files
        self.bar.setValue(int(overall * 100))
        self.msg.setText(msg)


# --------------------------------------------------------------------------------------
# Screen 3 - review
# --------------------------------------------------------------------------------------


class PageCanvas(QWidget):
    """Shows one PDF page with coloured overlays. Click = hide/keep, drag = draw a zone."""

    changed = Signal()

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.analysis = None
        self.page = 0
        self.zoom = 1.3
        self.pixmap = None
        self.selected_key = None
        self._press = None
        self._drag = None
        self._doc = None

    def set_document(self, analysis):
        if self._doc is not None:
            self._doc.close()
        self.analysis = analysis
        self._doc = pymupdf.open(analysis.path)
        self.page = 0
        self.render()

    def set_page(self, page):
        if self.analysis and 0 <= page < self.analysis.page_count:
            self.page = page
            self.render()

    def set_zoom(self, z):
        self.zoom = max(0.4, min(4.0, z))
        self.render()

    def page_size(self):
        r = self._doc[self.page].rect
        return r.width, r.height

    def render(self):
        if not self._doc:
            return
        dpr = self.devicePixelRatioF()
        pg = self._doc[self.page]
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(self.zoom * dpr, self.zoom * dpr), alpha=False)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        img.setDevicePixelRatio(dpr)
        self.pixmap = QPixmap.fromImage(img)
        self.setFixedSize(int(pg.rect.width * self.zoom), int(pg.rect.height * self.zoom))
        self.update()

    def page_hits(self):
        return [h for h in self.analysis.hits if h.page == self.page] if self.analysis else []

    def to_pdf(self, pt):
        return pt.x() / self.zoom, pt.y() / self.zoom

    def to_screen(self, r):
        x0, y0, x1, y1 = r
        z = self.zoom
        return QRectF(x0 * z, y0 * z, (x1 - x0) * z, (y1 - y0) * z)

    def hit_at(self, pos):
        x, y = self.to_pdf(pos)
        # smallest matching box first (a word inside a big signature zone wins)
        cands = []
        for h in self.page_hits():
            for r in h.rects:
                if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
                    cands.append(((r[2] - r[0]) * (r[3] - r[1]), h))
        return min(cands, key=lambda c: c[0])[1] if cands else None

    def paintEvent(self, e):
        if not self.pixmap:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(0, 0, self.pixmap)
        for h in self.page_hits():
            sel = self.selected_key is not None and h.key == self.selected_key
            for r in h.rects:
                rr = self.to_screen(r)
                if h.enabled:
                    p.setBrush(qcolor(h.category, 95))
                    p.setPen(QPen(qcolor(h.category, 255), 2.5 if sel else 1.2))
                else:
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(QColor(120, 120, 120, 200), 1.2, Qt.DashLine))
                p.drawRoundedRect(rr.adjusted(-1, -1, 1, 1), 3, 3)
                if sel:
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(QColor(ACCENT), 2))
                    p.drawRoundedRect(rr.adjusted(-4, -4, 4, 4), 4, 4)
        if self._drag:
            p.setBrush(qcolor("manual", 70))
            p.setPen(QPen(qcolor("manual"), 1.5, Qt.DashLine))
            p.drawRect(self._drag)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.position().toPoint()

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._press is not None and (pos - self._press).manhattanLength() > 6:
            self._drag = QRect(self._press, pos).normalized()
            self.update()
            return
        if not self.analysis:
            return
        h = self.hit_at(pos)
        x, y = self.to_pdf(pos)
        if h:
            state = "masqué" if h.enabled else "gardé visible"
            QToolTip.showText(e.globalPosition().toPoint(),
                              f"<b>{CATEGORY_NAMES.get(h.category, h.category)}</b> · {state}<br>{h.text}<br>"
                              f"<span style='color:gray'>Cliquez pour {'le garder visible' if h.enabled else 'le masquer'}</span>", self)
            self.setCursor(Qt.PointingHandCursor)
        elif engine.find_word_at(self.analysis, self.page, x, y):
            QToolTip.showText(e.globalPosition().toPoint(), "Cliquez pour masquer ce mot", self)
            self.setCursor(Qt.PointingHandCursor)
        else:
            QToolTip.hideText()
            self.setCursor(Qt.CrossCursor)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.analysis:
            return
        if self._drag and self._drag.width() > 4 and self._drag.height() > 4:
            r = self._drag
            z = self.zoom
            engine.add_zone_hit(self.analysis, self.page, (r.left() / z, r.top() / z, r.right() / z, r.bottom() / z))
            self._drag = None
            self._press = None
            self.changed.emit()
            self.update()
            return
        self._drag = None
        pos = e.position().toPoint()
        self._press = None
        h = self.hit_at(pos)
        if h:
            if h.source == "manual" and h.enabled:
                self.analysis.hits.remove(h)
            else:
                h.enabled = not h.enabled
        else:
            x, y = self.to_pdf(pos)
            w = engine.find_word_at(self.analysis, self.page, x, y)
            if not w:
                self.update()
                return
            engine.add_word_hit(self.analysis, self.page, w)
        self.changed.emit()
        self.update()


class ReviewPage(QWidget):
    back = Signal()
    proceed = Signal()

    def __init__(self, settings: Settings):
        super().__init__()
        self.setObjectName("Page")
        self.settings = settings
        self.analyses: list = []
        self.current = None
        self._building = False
        self._cycle = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(14)

        # ---- left: document viewer
        left = QVBoxLayout()
        left.setSpacing(8)
        bar = QHBoxLayout()
        self.file_combo = QComboBox()
        self.file_combo.setMinimumWidth(240)
        self.file_combo.currentIndexChanged.connect(self.show_file)
        bar.addWidget(self.file_combo)
        bar.addStretch()
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setObjectName("Tool")
        self.btn_next = QPushButton("▶")
        self.btn_next.setObjectName("Tool")
        self.page_label = QLabel("Page 1 / 1")
        self.page_label.setMinimumWidth(90)
        self.page_label.setAlignment(Qt.AlignCenter)
        self.btn_prev.clicked.connect(lambda: self.goto_page(self.canvas.page - 1))
        self.btn_next.clicked.connect(lambda: self.goto_page(self.canvas.page + 1))
        bar.addWidget(self.btn_prev)
        bar.addWidget(self.page_label)
        bar.addWidget(self.btn_next)
        bar.addSpacing(14)
        for txt, fn in [("−", lambda: self.canvas.set_zoom(self.canvas.zoom / 1.2)),
                        ("+", lambda: self.canvas.set_zoom(self.canvas.zoom * 1.2)),
                        ("Ajuster", self.fit_width)]:
            b = QPushButton(txt)
            b.setObjectName("Tool")
            b.clicked.connect(fn)
            bar.addWidget(b)
        left.addLayout(bar)

        self.banners = QVBoxLayout()
        self.banners.setSpacing(6)
        left.addLayout(self.banners)

        self.canvas = PageCanvas()
        self.canvas.changed.connect(self.on_hits_changed)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("PageScroll")
        self.scroll.setWidget(self.canvas)
        self.scroll.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.scroll.setWidgetResizable(False)
        left.addWidget(self.scroll, 1)

        hint = QLabel("Cliquez sur une zone colorée pour la garder visible  ·  cliquez sur un mot pour le masquer  ·  "
                      "faites glisser pour masquer une zone (signature, tampon…)")
        hint.setObjectName("Small")
        hint.setWordWrap(True)
        left.addWidget(hint)
        root.addLayout(left, 3)

        # ---- right: list + actions
        side = QVBoxLayout()
        side.setSpacing(10)
        self.summary = QLabel("")
        self.summary.setObjectName("CardTitle")
        self.summary_sub = QLabel("")
        self.summary_sub.setObjectName("Small")
        side.addWidget(self.summary)
        side.addWidget(self.summary_sub)

        add_card, add_lay = card("Un élément a été oublié ?")
        add_lay.setSpacing(8)
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText("Tapez un nom, un mot ou un numéro…")
        self.add_edit.returnPressed.connect(self.add_text)
        add_lay.addWidget(self.add_edit)
        row = QHBoxLayout()
        self.add_cat = QComboBox()
        for c in ["name", "address", "date", "id", "org", "manual"]:
            self.add_cat.addItem(dot(c), CATEGORY_NAMES[c].split(" (")[0], c)
        row.addWidget(self.add_cat, 1)
        b = QPushButton("Masquer partout")
        b.clicked.connect(self.add_text)
        row.addWidget(b)
        add_lay.addLayout(row)
        self.cb_always = QCheckBox("Le masquer aussi dans les prochains documents")
        add_lay.addWidget(self.cb_always)
        side.addWidget(add_card)

        lst = QLabel("Éléments détectés")
        lst.setObjectName("CardTitle")
        side.addWidget(lst)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(2)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.itemChanged.connect(self.on_item_changed)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.tree_menu)
        side.addWidget(self.tree, 1)
        tip = QLabel("Décochez ce qui doit rester visible. Clic droit pour « ne jamais masquer ».")
        tip.setObjectName("Small")
        tip.setWordWrap(True)
        side.addWidget(tip)

        btns = QHBoxLayout()
        b_back = QPushButton("←  Retour")
        b_back.clicked.connect(self.back.emit)
        self.btn_go = QPushButton("Anonymiser")
        self.btn_go.setObjectName("Primary")
        self.btn_go.clicked.connect(self.proceed.emit)
        btns.addWidget(b_back)
        btns.addStretch()
        btns.addWidget(self.btn_go)
        side.addLayout(btns)

        side_w = QWidget()
        side_w.setLayout(side)
        side_w.setFixedWidth(370)
        root.addWidget(side_w)

    # ---- data
    def load(self, analyses):
        self.analyses = analyses
        self.file_combo.blockSignals(True)
        self.file_combo.clear()
        for i, a in enumerate(analyses):
            self.file_combo.addItem(f"{a.path.name}" if len(analyses) == 1 else f"{i + 1}/{len(analyses)} · {a.path.name}")
        self.file_combo.blockSignals(False)
        self.file_combo.setVisible(True)
        n = len(analyses)
        self.btn_go.setText("Anonymiser  →" if n == 1 else f"Anonymiser les {n} fichiers  →")
        self.show_file(0)

    def show_file(self, idx):
        if idx < 0 or idx >= len(self.analyses):
            return
        self.current = self.analyses[idx]
        self.canvas.set_document(self.current)
        QTimer.singleShot(0, self.fit_width)
        self.update_banners()
        self.rebuild_tree()
        self.update_page_label()

    def update_banners(self):
        while self.banners.count():
            w = self.banners.takeAt(0).widget()
            if w:
                w.deleteLater()
        a = self.current
        if not a.ai_available:
            self.banners.addWidget(banner("warn", "Le modèle IA n'a pas pu être chargé : les noms sont détectés uniquement via « M. / Mme » et vos listes. Vérifiez bien."))
        if a.unreadable_pages:
            pages = ", ".join(str(p + 1) for p in a.unreadable_pages)
            self.banners.addWidget(banner("warn", f"Page(s) {pages} : aucun texte lisible (image ou scan). Vérifiez-les et dessinez des zones si besoin."))
        if a.scanned_pages:
            pages = ", ".join(str(p + 1) for p in a.scanned_pages)
            self.banners.addWidget(banner("info", f"Page(s) {pages} scannée(s), lue(s) par reconnaissance de texte : vérifiez avec attention."))

    def goto_page(self, p):
        self.canvas.set_page(p)
        self.update_page_label()

    def update_page_label(self):
        if self.current:
            self.page_label.setText(f"Page {self.canvas.page + 1} / {self.current.page_count}")
            self.btn_prev.setEnabled(self.canvas.page > 0)
            self.btn_next.setEnabled(self.canvas.page < self.current.page_count - 1)

    def fit_width(self):
        if not self.current:
            return
        w, _ = self.canvas.page_size()
        avail = self.scroll.viewport().width() - 30
        self.canvas.set_zoom(max(0.5, min(2.5, avail / w)))

    # ---- list
    def groups(self):
        g = {}
        for h in self.current.hits:
            g.setdefault(h.category, {}).setdefault(h.key, []).append(h)
        return g

    def rebuild_tree(self):
        self._building = True
        self.tree.clear()
        groups = self.groups()
        for cat in ALL_CATEGORIES:
            if cat not in groups:
                continue
            items = groups[cat]
            total = sum(len(v) for v in items.values())
            parent = QTreeWidgetItem([f"{CATEGORY_NAMES[cat]}", f"{total}"])
            parent.setIcon(0, dot(cat, 11))
            parent.setFlags(parent.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsAutoTristate)
            f = parent.font(0)
            f.setBold(True)
            parent.setFont(0, f)
            parent.setData(0, Qt.UserRole, ("cat", cat))
            self.tree.addTopLevelItem(parent)
            for key, hits in sorted(items.items(), key=lambda kv: (min(h.page for h in kv[1]), kv[0][1])):
                text = hits[0].text
                label = text if len(text) <= 38 else text[:36] + "…"
                child = QTreeWidgetItem([label, f"×{len(hits)}" if len(hits) > 1 else ""])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                n_on = sum(h.enabled for h in hits)
                child.setCheckState(0, Qt.Checked if n_on == len(hits) else Qt.Unchecked if n_on == 0 else Qt.PartiallyChecked)
                pages = sorted({h.page + 1 for h in hits})
                child.setToolTip(0, f"{text}\nPage{'s' if len(pages) > 1 else ''} {', '.join(map(str, pages))}")
                child.setData(0, Qt.UserRole, ("grp", key))
                parent.addChild(child)
            parent.setExpanded(True)
        self.tree.resizeColumnToContents(1)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, self.tree.header().ResizeMode.Stretch)
        self._building = False
        self.update_summary()

    def update_summary(self):
        all_hits = [h for a in self.analyses for h in a.hits]
        on = sum(h.enabled for h in all_hits)
        off = len(all_hits) - on
        self.summary.setText(f"{on} élément{'s' if on != 1 else ''} à masquer")
        extra = f" · {off} gardé{'s' if off != 1 else ''} visible{'s' if off != 1 else ''}" if off else ""
        files = f" dans {len(self.analyses)} fichiers" if len(self.analyses) > 1 else ""
        self.summary_sub.setText(f"Vérifiez la sélection{files}{extra}")

    def hits_for_key(self, key):
        return [h for h in self.current.hits if h.key == key]

    def on_item_changed(self, item, col):
        if self._building or col != 0:
            return
        data = item.data(0, Qt.UserRole)
        if not data or data[0] != "grp":
            return
        state = item.checkState(0)
        if state == Qt.PartiallyChecked:
            return
        for h in self.hits_for_key(data[1]):
            h.enabled = state == Qt.Checked
        # drop manual hits that were unticked
        self.current.hits = [h for h in self.current.hits if h.enabled or h.source != "manual"]
        self.canvas.update()
        self.update_summary()

    def on_item_clicked(self, item, col):
        data = item.data(0, Qt.UserRole)
        if not data or data[0] != "grp":
            self.canvas.selected_key = None
            self.canvas.update()
            return
        hits = sorted(self.hits_for_key(data[1]), key=lambda h: (h.page, h.rects[0][1]))
        if not hits:
            return
        i = self._cycle.get(data[1], -1) + 1
        if i >= len(hits):
            i = 0
        self._cycle = {data[1]: i}
        h = hits[i]
        self.canvas.selected_key = data[1]
        if h.page != self.canvas.page:
            self.goto_page(h.page)
        r = self.canvas.to_screen(h.rects[0])
        self.scroll.ensureVisible(int(r.center().x()), int(r.center().y()), 80, 160)
        self.canvas.update()

    def on_hits_changed(self):
        self.rebuild_tree()
        self.canvas.update()

    def tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        data = item.data(0, Qt.UserRole)
        if not data or data[0] != "grp":
            return
        text = self.hits_for_key(data[1])[0].text
        m = QMenu(self)
        a1 = m.addAction(f"Ne jamais masquer « {text[:30]} »")
        a2 = m.addAction(f"Toujours masquer « {text[:30]} »")
        chosen = m.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == a1:
            self.settings.add_never(text)
            self.settings.save()
            for a in self.analyses:
                for h in a.hits:
                    if h.text.lower() == text.lower():
                        h.enabled = False
            self.on_hits_changed()
        elif chosen == a2:
            self.settings.add_always(text)
            self.settings.save()
            for a in self.analyses:
                engine.add_text_everywhere(a, text, "name")
                for h in a.hits:
                    if h.text.lower() == text.lower():
                        h.enabled = True
            self.on_hits_changed()

    def add_text(self):
        text = self.add_edit.text().strip()
        if not text:
            return
        cat = self.add_cat.currentData()
        total = 0
        for a in self.analyses:
            for h in a.hits:  # re-enable if it was unticked before
                if h.text.lower() == text.lower() and not h.enabled:
                    h.enabled = True
                    total += 1
            total += len(engine.add_text_everywhere(a, text, cat))
        if self.cb_always.isChecked():
            self.settings.add_always(text)
            self.settings.save()
        self.add_edit.clear()
        self.on_hits_changed()
        if total == 0:
            QMessageBox.information(self, APP_NAME, f"« {text} » n'a pas été trouvé dans le texte du document.\n\n"
                                    "S'il fait partie d'une image ou d'un scan, faites glisser la souris sur la page pour masquer la zone.")


# --------------------------------------------------------------------------------------
# Screen 4 - done
# --------------------------------------------------------------------------------------


class DonePage(QWidget):
    restart = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.box = QVBoxLayout()
        self.box.setSpacing(12)
        w = QWidget()
        w.setLayout(self.box)
        w.setMaximumWidth(760)
        w.setMinimumWidth(600)
        outer.addWidget(w, 1, Qt.AlignHCenter)

    def show_results(self, results):
        while self.box.count():
            it = self.box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        ok = [r for r in results if not isinstance(r[1], str)]
        failed = [r for r in results if isinstance(r[1], str)]
        icon = QLabel("✓" if ok and not failed else "!")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(64, 64)
        color = "#1F9D55" if not failed else "#D97706"
        icon.setStyleSheet(f"background: {color}; color: white; border-radius: 32px; font-size: 32px; font-weight: 700;")
        self.box.addWidget(icon, 0, Qt.AlignHCenter)
        n = len(ok)
        t = QLabel(f"{n} document{'s' if n != 1 else ''} anonymisé{'s' if n != 1 else ''}" if n else "Aucun document n'a pu être anonymisé")
        t.setObjectName("H1")
        t.setAlignment(Qt.AlignCenter)
        self.box.addWidget(t)
        s = QLabel("Les fichiers originaux n'ont pas été modifiés. Ouvrez le résultat pour un dernier coup d'œil avant de le partager.")
        s.setObjectName("Muted")
        s.setAlignment(Qt.AlignCenter)
        s.setWordWrap(True)
        self.box.addWidget(s)
        self.box.addSpacing(8)

        scroll_w = QWidget()
        lst = QVBoxLayout(scroll_w)
        lst.setContentsMargins(0, 0, 0, 0)
        lst.setSpacing(10)
        for analysis, res in results:
            c, lay = card()
            head = QHBoxLayout()
            name = QLabel(f"📄  {res.output.name}" if not isinstance(res, str) else f"📄  {analysis.path.name}")
            name.setStyleSheet("font-weight: 700; font-size: 14px;")
            head.addWidget(name, 1)
            if not isinstance(res, str):
                b1 = QPushButton("Ouvrir")
                b1.clicked.connect(lambda _=False, p=res.output: open_path(p))
                b2 = QPushButton("Afficher dans le Finder" if sys.platform == "darwin" else "Afficher dans le dossier")
                b2.clicked.connect(lambda _=False, p=res.output: reveal(p))
                head.addWidget(b1)
                head.addWidget(b2)
            lay.addLayout(head)
            if isinstance(res, str):
                lay.addWidget(banner("warn", res))
            else:
                parts = [f"{v} {(CATEGORY_NAMES[k] if v > 1 else SINGULAR[k]).split(' (')[0].lower()}"
                         for k, v in sorted(res.counts.items(), key=lambda kv: ALL_CATEGORIES.index(kv[0]))]
                det = QLabel(f"{res.hidden_count} élément{'s' if res.hidden_count != 1 else ''} masqué{'s' if res.hidden_count != 1 else ''} : " + ", ".join(parts))
                det.setObjectName("Muted")
                det.setWordWrap(True)
                lay.addWidget(det)
                if res.leaks:
                    lay.addWidget(banner("warn", "Encore présent dans le texte : " + ", ".join(res.leaks[:5]) + ". Vérifiez le document."))
                else:
                    lay.addWidget(banner("ok", "Vérifié : le texte masqué a bien été supprimé du fichier (impossible à copier ou rechercher)."))
                if res.report:
                    rl = QLabel(f"Rapport : {res.report.name}  — contient les valeurs d'origine, gardez-le privé.")
                    rl.setObjectName("Small")
                    lay.addWidget(rl)
            lst.addWidget(c)
        lst.addStretch()
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
        sc.setWidget(scroll_w)
        self.box.addWidget(sc, 1)

        row = QHBoxLayout()
        row.addStretch()
        b = QPushButton("Anonymiser d'autres documents")
        b.setObjectName("Primary")
        b.clicked.connect(self.restart.emit)
        row.addWidget(b)
        row.addStretch()
        self.box.addLayout(row)


# --------------------------------------------------------------------------------------
# Settings dialog
# --------------------------------------------------------------------------------------


class ListEditor(QWidget):
    def __init__(self, items, help_text, placeholder):
        super().__init__()
        lay = QVBoxLayout(self)
        h = QLabel(help_text)
        h.setWordWrap(True)
        h.setObjectName("Muted")
        lay.addWidget(h)
        row = QHBoxLayout()
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.returnPressed.connect(self.add)
        b = QPushButton("Ajouter")
        b.clicked.connect(self.add)
        row.addWidget(self.edit, 1)
        row.addWidget(b)
        lay.addLayout(row)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for i in items:
            self.list.addItem(i)
        lay.addWidget(self.list, 1)
        rm = QPushButton("Retirer la sélection")
        rm.clicked.connect(lambda: [self.list.takeItem(self.list.row(i)) for i in self.list.selectedItems()])
        lay.addWidget(rm, 0, Qt.AlignRight)

    def add(self):
        t = " ".join(self.edit.text().split())
        if t and not self.list.findItems(t, Qt.MatchFixedString):
            self.list.addItem(t)
        self.edit.clear()

    def items(self):
        return [self.list.item(i).text() for i in range(self.list.count())]


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Paramètres")
        self.resize(560, 520)
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        self.always = ListEditor(settings.always_hide,
                                 "Ces noms ou mots seront toujours masqués, même si l'IA ne les reconnaît pas (clients, collègues…).",
                                 "Ex. : Jean Dupont")
        self.never = ListEditor(settings.never_hide,
                                "Ces mots ne seront jamais masqués (nom de votre société, produits, villes à garder…).",
                                "Ex. : Salesforce")
        tabs.addTab(self.always, "Toujours masquer")
        tabs.addTab(self.never, "Ne jamais masquer")

        out = QWidget()
        ol = QVBoxLayout(out)
        self.rb_beside = QRadioButton("À côté du fichier original  (contrat.pdf → contrat_anonymise.pdf)")
        self.rb_folder = QRadioButton("Dans ce dossier :")
        (self.rb_folder if settings.output_mode == "folder" else self.rb_beside).setChecked(True)
        row = QHBoxLayout()
        self.folder_edit = QLineEdit(settings.output_folder)
        self.folder_edit.setReadOnly(True)
        b = QPushButton("Choisir…")
        b.clicked.connect(self.pick_folder)
        row.addWidget(self.folder_edit, 1)
        row.addWidget(b)
        ol.addWidget(self.rb_beside)
        ol.addWidget(self.rb_folder)
        ol.addLayout(row)
        ol.addStretch()
        about = QLabel(f"{APP_NAME} {VERSION} · fonctionne hors ligne, aucun fichier n'est envoyé sur internet.")
        about.setObjectName("Small")
        ol.addWidget(about)
        tabs.addTab(out, "Enregistrement")
        lay.addWidget(tabs)

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Enregistrer")
        bb.button(QDialogButtonBox.Cancel).setText("Annuler")
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Dossier d'enregistrement", self.folder_edit.text() or str(Path.home()))
        if d:
            self.folder_edit.setText(d)
            self.rb_folder.setChecked(True)

    def save(self):
        s = self.settings
        s.always_hide = self.always.items()
        s.never_hide = self.never.items()
        if self.rb_folder.isChecked() and self.folder_edit.text():
            s.output_mode, s.output_folder = "folder", self.folder_edit.text()
        else:
            s.output_mode = "beside"
        s.save()
        self.accept()


# --------------------------------------------------------------------------------------
# Main window
# --------------------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self, initial_files=None):
        super().__init__()
        self.settings = Settings.load()
        self.setWindowTitle(APP_NAME)
        icon_path = engine.resource_dir() / "app" / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1240, 820)
        self.setMinimumSize(980, 640)

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        header = QWidget()
        header.setObjectName("Header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(22, 12, 18, 12)
        t = QLabel("🛡  " + APP_NAME)
        t.setObjectName("AppTitle")
        hl.addWidget(t)
        tag = QLabel("Anonymisation de documents PDF")
        tag.setObjectName("Small")
        hl.addSpacing(8)
        hl.addWidget(tag)
        hl.addStretch()
        self.steps = []
        for i, name in enumerate(["1  Documents", "2  Vérification", "3  Terminé"]):
            lab = QLabel(name)
            lab.setObjectName("Step")
            self.steps.append(lab)
            hl.addWidget(lab)
            if i < 2:
                sep = QLabel("›")
                sep.setObjectName("Muted")
                hl.addWidget(sep)
        hl.addStretch()
        b = QPushButton("⚙  Paramètres")
        b.clicked.connect(self.open_settings)
        hl.addWidget(b)
        v.addWidget(header)

        self.stack = QStackedWidget()
        self.home = HomePage(self.settings)
        self.analyzing = AnalyzingPage()
        self.review = ReviewPage(self.settings)
        self.done = DonePage()
        for w in (self.home, self.analyzing, self.review, self.done):
            self.stack.addWidget(w)
        v.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.home.start.connect(self.start_analysis)
        self.analyzing.cancel.connect(self.cancel_analysis)
        self.review.back.connect(lambda: self.go(self.home))
        self.review.proceed.connect(self.run_apply)
        self.done.restart.connect(self.restart)

        self.setAcceptDrops(True)
        self.go(self.home)
        self.loader = ModelLoader()
        self.loader.start()
        if initial_files:
            self.home.add_files(initial_files)

    # navigation
    def go(self, page):
        self.stack.setCurrentWidget(page)
        idx = {self.home: 0, self.analyzing: 1, self.review: 1, self.done: 2}[page]
        for i, lab in enumerate(self.steps):
            lab.setProperty("active", "true" if i == idx else "false")
            lab.setProperty("done", "true" if i < idx else "false")
            lab.style().unpolish(lab)
            lab.style().polish(lab)

    def dragEnterEvent(self, e):
        if self.stack.currentWidget() is self.home and e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.home.add_files([u.toLocalFile() for u in e.mimeData().urls()])

    def open_settings(self):
        SettingsDialog(self.settings, self).exec()

    # analysis
    def start_analysis(self, files):
        s = self.settings
        opts = engine.Options(categories=set(s.categories), always_hide=list(s.always_hide),
                              never_hide=list(s.never_hide), remove_all_images=s.remove_all_images)
        self._files = files
        self._results = []
        self._failures = []
        self.analyzing.set_progress(0, len(files), files[0].name, 0, 1, "Préparation…")
        self.go(self.analyzing)
        self.worker = AnalyzeWorker(files, opts)
        self.worker.progress.connect(lambda i, s_, t, m: self.analyzing.set_progress(i, len(files), files[i].name, s_, t, m))
        self.worker.file_done.connect(self._results.append)
        self.worker.file_failed.connect(lambda f, e: self._failures.append((f, e)))
        self.worker.all_done.connect(self.analysis_finished)
        self.worker.start()

    def cancel_analysis(self):
        if getattr(self, "worker", None):
            self.worker.cancel()
            self._cancelled = True

    def analysis_finished(self):
        if getattr(self, "_cancelled", False):
            self._cancelled = False
            self.go(self.home)
            return
        if self._failures:
            msg = "\n".join(f"• {Path(f).name} : {e}" for f, e in self._failures)
            QMessageBox.warning(self, APP_NAME, f"Certains fichiers n'ont pas pu être lus :\n\n{msg}")
        if not self._results:
            self.go(self.home)
            return
        self.review.load(self._results)
        self.go(self.review)

    # apply
    def output_for(self, path: Path) -> Path:
        s = self.settings
        if s.output_mode == "folder" and s.output_folder:
            return Path(s.output_folder) / (path.stem + "_anonymise.pdf")
        return engine.default_output(path)

    def run_apply(self):
        jobs = [(a, self.output_for(a.path)) for a in self.review.analyses]
        self.review.btn_go.setEnabled(False)
        self.review.btn_go.setText("Anonymisation…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.apply_worker = ApplyWorker(jobs, self.settings.style, self.settings.report)
        self.apply_worker.done.connect(self.apply_finished)
        self.apply_worker.start()

    def apply_finished(self, results):
        QApplication.restoreOverrideCursor()
        self.review.btn_go.setEnabled(True)
        self.done.show_results(results)
        self.go(self.done)

    def restart(self):
        self.home.clear()
        self.go(self.home)


class App(QApplication):
    """On macOS, PDFs dropped on the Dock icon or opened with "Ouvrir avec" arrive as FileOpen events."""

    file_opened = Signal(str)

    def __init__(self, argv):
        super().__init__(argv)
        self.pending = []

    def event(self, e):
        if e.type() == QEvent.FileOpen:
            path = e.file()
            if getattr(self, "_window", None) is not None:
                self.file_opened.emit(path)
            else:
                self.pending.append(path)
            return True
        return super().event(e)


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = App(sys.argv)
    app.setApplicationName(APP_NAME)
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    # Always the light look: the design is light-only, so ignore Windows/macOS dark mode
    app.setPalette(app.style().standardPalette())
    app.setStyleSheet(STYLE)
    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    w = MainWindow(files)

    def open_file(path):
        # don't interrupt a review in progress: the file just waits in the list
        if w.stack.currentWidget() is w.done:
            w.restart()
        w.home.add_files([path])
        w.raise_()
        w.activateWindow()

    app.file_opened.connect(open_file)
    app._window = w
    for p in app.pending:
        open_file(p)
    app.pending.clear()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
