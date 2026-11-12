"""Print-quality PDF export for Crema.

The report mirrors the journal's warm editorial palette: cream paper, ink,
clay accents, Fraunces headings and Inter body text.
"""

import io
import math
import os
import re
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

PAGE_W, PAGE_H = A4
MARGIN_L = MARGIN_R = 17 * mm
MARGIN_T = 21 * mm
MARGIN_B = 19 * mm
CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R

PDF_FOOTER = os.environ.get("CREMA_PDF_FOOTER", "Made at home · Crema")

CREAM = HexColor("#F5EEE3")
CREAM_DEEP = HexColor("#EDE2D1")
PAPER = HexColor("#FFFCF7")
INK = HexColor("#2B1B12")
INK_SOFT = HexColor("#584536")
MUTED = HexColor("#7C6B5C")
LINE = HexColor("#E2D8C9")
LINE_STRONG = HexColor("#CDBFAC")
CLAY = HexColor("#B1552F")
CLAY_DEEP = HexColor("#8F3F1E")
CLAY_WASH = HexColor("#F5E3D8")

INK_HEX = "#2B1B12"
MUTED_HEX = "#7C6B5C"
CLAY_HEX = "#B1552F"
CREAM_HEX = "#F5EEE3"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTHS_LONG = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "fonts")
_FONT_LOCK = threading.Lock()
_FONTS = None


def _register_fonts():
    global _FONTS
    with _FONT_LOCK:
        if _FONTS is not None:
            return _FONTS
        wanted = {
            "serif": ("CremaSerif", "Fraunces-Medium.ttf"),
            "serif_bold": ("CremaSerif-Bold", "Fraunces-Semibold.ttf"),
            "sans": ("CremaSans", "Inter-Regular.ttf"),
            "sans_bold": ("CremaSans-Bold", "Inter-Semibold.ttf"),
        }
        if all(os.path.isfile(os.path.join(FONT_DIR, file_name))
               for _, file_name in wanted.values()):
            for name, file_name in wanted.values():
                if name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIR, file_name)))
            pdfmetrics.registerFontFamily(
                "CremaSans", normal="CremaSans", bold="CremaSans-Bold",
                italic="CremaSans", boldItalic="CremaSans-Bold",
            )
            pdfmetrics.registerFontFamily(
                "CremaSerif", normal="CremaSerif", bold="CremaSerif-Bold",
                italic="CremaSerif", boldItalic="CremaSerif-Bold",
            )
            _FONTS = {key: value[0] for key, value in wanted.items()}
        else:
            _FONTS = {
                "serif": "Times-Roman",
                "serif_bold": "Times-Bold",
                "sans": "Helvetica",
                "sans_bold": "Helvetica-Bold",
            }
        return _FONTS


def _clean(value):
    text = "" if value is None else str(value)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return escape(text).replace("\n", "<br/>")


def _num(value, digits=1):
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    text = f"{number:.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _grams(value):
    return "—" if value is None else _num(value, 1) + "g"


def _shot_time(value):
    if value is None:
        return "—"
    seconds = float(value)
    if seconds < 60:
        return _num(seconds, 1) + "s"
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def _ratio(shot):
    dose = shot.get("dose_g")
    yield_g = shot.get("yield_g")
    if not dose or not yield_g:
        return ""
    value = float(yield_g) / float(dose)
    return "1:" + (str(round(value)) if value >= 10 else f"{value:.1f}")


def _parse_dt(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone()
    except (TypeError, ValueError):
        return None


def _title_case(value):
    text = str(value or "").strip()
    return text[:1].upper() + text[1:] if text else ""


def _initials(name):
    parts = str(name or "?").strip().split()
    return "".join(part[0].upper() for part in parts[:2]) or "?"


def _date_range(shots):
    dates = [d for d in (_parse_dt(shot.get("brewed_at")) for shot in shots) if d]
    if not dates:
        return "No shots logged yet"
    first, last = min(dates), max(dates)
    if first.date() == last.date():
        return f"{last.day} {MONTHS_LONG[last.month - 1]} {last.year}"
    if first.year == last.year and first.month == last.month:
        return f"{first.day}–{last.day} {MONTHS_LONG[last.month - 1]} {last.year}"
    if first.year == last.year:
        return f"{first.day} {MONTHS[first.month - 1]} – {last.day} {MONTHS[last.month - 1]} {last.year}"
    return f"{MONTHS[first.month - 1]} {first.year} – {MONTHS[last.month - 1]} {last.year}"


def _compute_stats(shots):
    # Café entries are part of the journal but not part of the brewing record.
    home = [shot for shot in shots if not shot.get("is_cafe")]
    rated = [shot for shot in home if shot.get("rating")]
    espresso = [shot for shot in home if (shot.get("method") or "").lower() == "espresso"]
    recipe_source = espresso or home

    def average(values):
        values = [float(value) for value in values if value not in (None, "")]
        return round(sum(values) / len(values), 1) if values else None

    tag_counts = Counter()
    for shot in home:
        for tag in shot.get("flavor_tags") or []:
            tag_counts[str(tag)] += 1

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    week_count = 0
    for shot in home:
        parsed = _parse_dt(shot.get("brewed_at"))
        if parsed and parsed.astimezone(timezone.utc) >= week_ago:
            week_count += 1

    beans = Counter(
        shot.get("bean_name") for shot in home if shot.get("bean_name")
    )
    best = max(rated, key=lambda shot: (shot.get("rating") or 0, shot.get("brewed_at") or ""), default=None)

    return {
        "total": len(home),
        "cafe": sum(1 for shot in shots if shot.get("is_cafe")),
        "rated": len(rated),
        "week": week_count,
        "avg_rating": round(sum(float(shot["rating"]) for shot in rated) / len(rated), 2) if rated else None,
        "avg_dose": average([shot.get("dose_g") for shot in recipe_source]),
        "avg_yield": average([shot.get("yield_g") for shot in recipe_source]),
        "avg_time": average([shot.get("time_s") for shot in recipe_source]),
        "top_tags": tag_counts.most_common(10),
        "most_brewed": beans.most_common(1)[0] if beans else None,
        "best": best,
    }


class HeroBand(Flowable):
    def __init__(self, eyebrow, headline, subline, fonts, styles):
        super().__init__()
        self.eyebrow = eyebrow
        self.headline = headline
        self.subline = subline
        self.fonts = fonts
        self.styles = styles
        self.height = 43 * mm

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        return avail_width, self.height

    def draw(self):
        canv = self.canv
        canv.saveState()
        canv.setFillColor(INK)
        canv.roundRect(0, 0, self.width, self.height, 8 * mm, fill=1, stroke=0)

        # Keep the ring motif inside the band instead of spilling over the
        # cover title and page header.
        clip = canv.beginPath()
        clip.roundRect(0, 0, self.width, self.height, 8 * mm)
        canv.clipPath(clip, stroke=0, fill=0)

        canv.setStrokeColor(HexColor("#594231"))
        canv.setLineWidth(0.7)
        canv.setStrokeAlpha(0.55)
        centre_x, centre_y = self.width - 18 * mm, self.height + 4 * mm
        for radius in (14, 24, 34, 44):
            canv.circle(centre_x, centre_y, radius * mm, stroke=1, fill=0)
        canv.setStrokeAlpha(1)

        canv.setFillColor(HexColor("#D9A882"))
        canv.setFont(self.fonts["sans_bold"], 6.6)
        canv.drawString(9 * mm, self.height - 10 * mm, self.eyebrow.upper())

        headline = Paragraph(self.headline, self.styles["hero_headline"])
        width, height = headline.wrap(self.width - 18 * mm, 18 * mm)
        headline.drawOn(canv, 9 * mm, self.height - 14 * mm - height)

        subline = Paragraph(self.subline, self.styles["hero_subline"])
        sub_width, sub_height = subline.wrap(self.width - 18 * mm, 12 * mm)
        subline.drawOn(canv, 9 * mm, self.height - 18 * mm - height - sub_height)
        canv.restoreState()


class StatTiles(Flowable):
    def __init__(self, items, fonts, styles):
        super().__init__()
        self.items = items
        self.fonts = fonts
        self.styles = styles
        self.height = 32 * mm

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        return avail_width, self.height

    def draw(self):
        canv = self.canv
        gap = 3 * mm
        tile_width = (self.width - 3 * gap) / 4
        for index, (label, value, meta) in enumerate(self.items):
            x = index * (tile_width + gap)
            canv.saveState()
            canv.setFillColor(PAPER)
            canv.setStrokeColor(LINE)
            canv.setLineWidth(0.6)
            canv.roundRect(x, 0, tile_width, self.height, 3 * mm, fill=1, stroke=1)
            canv.setFillColor(MUTED)
            canv.setFont(self.fonts["sans_bold"], 6.1)
            canv.drawString(x + 4 * mm, self.height - 7 * mm, label.upper())
            canv.setFillColor(INK)
            canv.setFont(self.fonts["serif"], 17)
            canv.drawString(x + 4 * mm, self.height - 16.5 * mm, value)
            meta_paragraph = Paragraph(meta, self.styles["tile_meta"])
            meta_width, meta_height = meta_paragraph.wrap(tile_width - 8 * mm, 9 * mm)
            meta_paragraph.drawOn(canv, x + 4 * mm, 3 * mm)
            canv.restoreState()


class Pills(Flowable):
    def __init__(self, items, fonts, size=6.8):
        super().__init__()
        self.items = [str(item) for item in items if str(item).strip()]
        self.fonts = fonts
        self.size = size
        self.gap = 1.8 * mm
        self.pad_x = 2.5 * mm
        self.pad_y = 1.5 * mm
        self.row_height = size * 1.25 + 2 * self.pad_y
        self.positions = []
        self.height = 0

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        x = 0
        y = 0
        self.positions = []
        for text in self.items:
            text_width = pdfmetrics.stringWidth(text, self.fonts["sans_bold"], self.size) + 2 * self.pad_x
            if x + text_width > avail_width and x > 0:
                x = 0
                y += self.row_height + self.gap
            self.positions.append((text, text_width, x, y))
            x += text_width + self.gap
        self.height = y + self.row_height
        return avail_width, self.height

    def draw(self):
        canv = self.canv
        for text, pill_width, x, y in self.positions:
            draw_y = self.height - y - self.row_height
            canv.saveState()
            canv.setFillColor(CLAY_WASH)
            canv.setStrokeColor(HexColor("#EAD3C3"))
            canv.setLineWidth(0.5)
            canv.roundRect(x, draw_y, pill_width, self.row_height, self.row_height / 2, fill=1, stroke=1)
            canv.setFillColor(CLAY_DEEP)
            canv.setFont(self.fonts["sans_bold"], self.size)
            canv.drawString(x + self.pad_x, draw_y + self.pad_y + 1, text)
            canv.restoreState()


class BestCup(Flowable):
    """A quiet pull-quote card for the highest-rated shot on the cover."""

    def __init__(self, shot, fonts, styles):
        super().__init__()
        self.shot = shot
        self.fonts = fonts
        self.styles = styles
        self.height = 42 * mm

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        return avail_width, self.height

    def draw(self):
        canv = self.canv
        shot = self.shot
        note = (shot.get("tasting_notes") or "The highest-rated cup in this journal.").strip()
        if len(note) > 165:
            note = note[:162].rsplit(" ", 1)[0] + "…"

        canv.saveState()
        canv.setFillColor(PAPER)
        canv.setStrokeColor(LINE)
        canv.setLineWidth(0.6)
        canv.roundRect(0, 0, self.width, self.height, 3 * mm, fill=1, stroke=1)
        canv.setFillColor(CLAY)
        canv.roundRect(0, 4 * mm, 1.4 * mm, self.height - 8 * mm, 0.7 * mm, fill=1, stroke=0)

        left = 8 * mm
        canv.setFillColor(CLAY)
        canv.setFont(self.fonts["sans_bold"], 6.6)
        canv.drawString(left, self.height - 9 * mm, "THE BEST CUP SO FAR")

        rating = shot.get("rating")
        if rating:
            stars = "★" * int(rating) + "☆" * (5 - int(rating))
            canv.setFont(self.fonts["sans_bold"], 9)
            canv.drawRightString(self.width - 8 * mm, self.height - 9.5 * mm, stars)

        quote = Paragraph(_clean(note), self.styles["quote"])
        quote_width, quote_height = quote.wrap(self.width - 16 * mm, 16 * mm)
        quote.drawOn(canv, left, self.height - 15 * mm - quote_height)

        dt = _parse_dt(shot.get("brewed_at"))
        bits = [shot.get("bean_name") or "Unnamed bean"]
        method = (shot.get("method") or "").strip()
        if method:
            bits.append(_title_case(method))
        if dt:
            bits.append(f"{dt.day} {MONTHS[dt.month - 1]}")
        meta = "  ·  ".join(part for part in bits if part)
        canv.setFillColor(MUTED)
        canv.setFont(self.fonts["sans"], 7.2)
        canv.drawString(left, 7 * mm, meta)
        canv.restoreState()


class MeterRows(Flowable):
    def __init__(self, rows, fonts):
        super().__init__()
        self.rows = rows
        self.fonts = fonts
        self.row_height = 5.1 * mm
        self.height = len(rows) * self.row_height

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        return avail_width, self.height

    def draw(self):
        canv = self.canv
        track_x = 23 * mm
        track_width = self.width - track_x - 9 * mm
        for index, (label, value) in enumerate(self.rows):
            y = self.height - (index + 1) * self.row_height + 1.1 * mm
            canv.setFillColor(MUTED)
            canv.setFont(self.fonts["sans"], 6.8)
            canv.drawString(0, y + 0.8 * mm, label)
            canv.setFillColor(CREAM_DEEP)
            canv.roundRect(track_x, y + 0.7 * mm, track_width, 2 * mm, 1 * mm, fill=1, stroke=0)
            canv.setFillColor(CLAY)
            canv.roundRect(track_x, y + 0.7 * mm, track_width * float(value) / 5.0, 2 * mm, 1 * mm, fill=1, stroke=0)
            canv.setFillColor(INK_SOFT)
            canv.setFont(self.fonts["sans_bold"], 6.5)
            canv.drawRightString(self.width, y + 0.7 * mm, str(value))


def _styles(fonts):
    return {
        "eyebrow": ParagraphStyle(
            "eyebrow", fontName=fonts["sans_bold"], fontSize=6.8, leading=9,
            textColor=CLAY, spaceAfter=3,
        ),
        "title": ParagraphStyle(
            "title", fontName=fonts["serif"], fontSize=31, leading=34,
            textColor=INK, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName=fonts["sans"], fontSize=9.4, leading=14,
            textColor=MUTED,
        ),
        "section": ParagraphStyle(
            "section", fontName=fonts["serif"], fontSize=19, leading=23,
            textColor=INK, spaceBefore=1, spaceAfter=2,
        ),
        "section_meta": ParagraphStyle(
            "section_meta", fontName=fonts["sans"], fontSize=7.4, leading=10,
            textColor=MUTED, alignment=TA_RIGHT,
        ),
        "hero_headline": ParagraphStyle(
            "hero_headline", fontName=fonts["serif"], fontSize=20, leading=23,
            textColor=CREAM,
        ),
        "hero_subline": ParagraphStyle(
            "hero_subline", fontName=fonts["sans"], fontSize=8.2, leading=12,
            textColor=HexColor("#D9C7B4"),
        ),
        "tile_meta": ParagraphStyle(
            "tile_meta", fontName=fonts["sans"], fontSize=6.5, leading=8.6,
            textColor=MUTED,
        ),
        "shot_title": ParagraphStyle(
            "shot_title", fontName=fonts["serif"], fontSize=12.5, leading=16,
            textColor=INK,
        ),
        "shot_date": ParagraphStyle(
            "shot_date", fontName=fonts["serif"], fontSize=16, leading=17,
            textColor=INK, alignment=TA_LEFT,
        ),
        "meta": ParagraphStyle(
            "meta", fontName=fonts["sans"], fontSize=7.6, leading=11,
            textColor=MUTED,
        ),
        "rating": ParagraphStyle(
            "rating", fontName=fonts["sans_bold"], fontSize=8, leading=11,
            textColor=CLAY, alignment=TA_RIGHT,
        ),
        "label": ParagraphStyle(
            "label", fontName=fonts["sans_bold"], fontSize=5.9, leading=8,
            textColor=MUTED,
        ),
        "value": ParagraphStyle(
            "value", fontName=fonts["sans"], fontSize=8.2, leading=11,
            textColor=INK,
        ),
        "note": ParagraphStyle(
            "note", fontName=fonts["sans"], fontSize=8.2, leading=12.4,
            textColor=INK_SOFT, backColor=PAPER, borderColor=LINE,
            borderWidth=0.5, borderPadding=5.5, spaceBefore=2.2 * mm,
        ),
        "small": ParagraphStyle(
            "small", fontName=fonts["sans"], fontSize=7.2, leading=10,
            textColor=MUTED,
        ),
        "quote": ParagraphStyle(
            "quote", fontName=fonts["serif"], fontSize=13.5, leading=18,
            textColor=INK,
        ),
        "quote_meta": ParagraphStyle(
            "quote_meta", fontName=fonts["sans"], fontSize=7.4, leading=11,
            textColor=MUTED,
        ),
        "bean_name": ParagraphStyle(
            "bean_name", fontName=fonts["serif"], fontSize=9.6, leading=12.5,
            textColor=INK,
        ),
        "bean_cell": ParagraphStyle(
            "bean_cell", fontName=fonts["sans"], fontSize=7.4, leading=10,
            textColor=INK_SOFT,
        ),
        "empty": ParagraphStyle(
            "empty", fontName=fonts["sans"], fontSize=9, leading=14,
            textColor=MUTED,
        ),
    }


def _section_header(kicker, title, meta, styles):
    table = Table(
        [
            [Paragraph(kicker, styles["eyebrow"]), Paragraph(meta, styles["section_meta"])],
            [Paragraph(title, styles["section"]), ""],
        ],
        colWidths=[CONTENT_W - 34 * mm, 34 * mm],
    )
    table.setStyle(TableStyle([
        ("SPAN", (0, 1), (-1, 1)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return [table, Spacer(1, 2.5 * mm), HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=5 * mm)]


def _photo_image(path, box=30 * mm):
    if not path or not os.path.isfile(path):
        return None
    try:
        width, height = ImageReader(path).getSize()
    except Exception:
        return None
    if not width or not height:
        return None
    scale = min(box / width, box / height)
    return Image(path, width=width * scale, height=height * scale)


def _detail_table(shot, styles):
    pairs = []

    def add(label, value):
        if value not in (None, "", "—"):
            pairs.append((label, value))

    add("Dose", _grams(shot.get("dose_g")) if shot.get("dose_g") else "")
    add("Yield", _grams(shot.get("yield_g")) if shot.get("yield_g") else "")
    add("Ratio", _ratio(shot))
    add("Time", _shot_time(shot.get("time_s")) if shot.get("time_s") else "")
    add("Grind", shot.get("grind"))
    add("Temperature", _num(shot.get("temp_c"), 1) + " °C" if shot.get("temp_c") else "")
    add("Pressure", _num(shot.get("pressure_bar"), 1) + " bar" if shot.get("pressure_bar") else "")
    add("Pre-infusion", _shot_time(shot.get("preinfusion_s")) if shot.get("preinfusion_s") else "")
    add("TDS", _num(shot.get("tds"), 2) + "%" if shot.get("tds") else "")
    add("Extraction", _num(shot.get("ey"), 1) + "%" if shot.get("ey") else "")
    add("Milk", (shot.get("milk_type") or "") + (" · " + _num(shot.get("milk_volume_ml"), 0) + " ml" if shot.get("milk_volume_ml") else ""))
    add("Machine", shot.get("machine"))
    add("Grinder", shot.get("grinder"))
    add("Basket", shot.get("basket"))

    if not pairs:
        return None

    columns = 4
    rows = [pairs[index:index + columns] for index in range(0, len(pairs), columns)]
    data = []
    for row in rows:
        cells = []
        for label, value in row:
            cells.append(Paragraph(
                f'<font name="{styles["label"].fontName}" size="5.9" color="{MUTED_HEX}">{_clean(label.upper())}</font><br/>'
                f'<font name="{styles["value"].fontName}" size="8.2" color="{INK_HEX}">{_clean(value)}</font>',
                styles["value"],
            ))
        while len(cells) < columns:
            cells.append("")
        data.append(cells)

    table = Table(data, colWidths=[CONTENT_W / columns] * columns)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PAPER),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("ROUNDEDCORNERS", [3, 3, 3, 3]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.7 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.9 * mm),
    ]))
    return table


def _shot_flowables(shot, photo_path, styles, fonts):
    dt = _parse_dt(shot.get("brewed_at")) or datetime.now()
    date_paragraph = Paragraph(
        f'<font name="{fonts["serif"]}" size="16" color="{INK_HEX}">{dt.day}</font><br/>'
        f'<font name="{fonts["sans_bold"]}" size="5.8" color="{MUTED_HEX}">{MONTHS[dt.month - 1].upper()}</font>',
        styles["shot_date"],
    )

    bean = shot.get("bean_name") or "No bean recorded"
    if shot.get("is_cafe"):
        bean = shot.get("cafe_name") or "Out for coffee"
    title = (
        f'<font name="{fonts["serif"]}" size="12.5" color="{INK_HEX}">{_clean(bean)}</font>'
        f'  <font name="{fonts["sans_bold"]}" size="6.1" color="{CLAY_HEX}">{_clean(_title_case(shot.get("method") or "coffee").upper())}</font>'
    )
    if shot.get("is_cafe"):
        title += f'  <font name="{fonts["sans_bold"]}" size="6.1" color="{MUTED_HEX}">AT A CAFÉ</font>'
    if shot.get("favorite"):
        title += f'  <font name="{fonts["sans_bold"]}" size="6.1" color="{CLAY_HEX}">★ FAVOURITE</font>'
    title_paragraph = Paragraph(title, styles["shot_title"])

    meta_bits = []
    if shot.get("dose_g") or shot.get("yield_g"):
        meta_bits.append(f'{_grams(shot.get("dose_g"))} in → {_grams(shot.get("yield_g"))} out')
    if shot.get("time_s"):
        meta_bits.append(_shot_time(shot.get("time_s")))
    if _ratio(shot):
        meta_bits.append(_ratio(shot))
    if shot.get("grind"):
        meta_bits.append("grind " + _clean(shot["grind"]))
    if shot.get("temp_c"):
        meta_bits.append(_num(shot["temp_c"], 1) + " °C")
    if shot.get("pressure_bar"):
        meta_bits.append(_num(shot["pressure_bar"], 1) + " bar")
    meta_paragraph = Paragraph(" · ".join(meta_bits), styles["meta"])

    rating = shot.get("rating")
    if rating:
        stars = "★" * int(rating) + "☆" * (5 - int(rating))
        rating_paragraph = Paragraph(
            f'<font name="{fonts["sans_bold"]}" size="8.4" color="{CLAY_HEX}">{stars}</font><br/>'
            f'<font name="{fonts["sans"]}" size="6.4" color="{MUTED_HEX}">{int(rating)} / 5</font>',
            styles["rating"],
        )
    else:
        rating_paragraph = Paragraph(
            f'<font name="{fonts["sans"]}" size="6.4" color="{MUTED_HEX}">not rated</font>',
            styles["rating"],
        )

    photo = _photo_image(photo_path)
    text_width = CONTENT_W - 15 * mm - (38 * mm if photo else 0)
    inner = Table(
        [[title_paragraph, rating_paragraph], [meta_paragraph, ""]],
        colWidths=[text_width - 17 * mm, 17 * mm],
    )
    inner.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.4 * mm),
    ]))

    header_cells = [date_paragraph, inner]
    header_widths = [15 * mm, text_width]
    if photo:
        header_cells.append(photo)
        header_widths.append(38 * mm)
    header = Table([header_cells], colWidths=header_widths)
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("VALIGN", (1, 0), (1, 0), "TOP"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    before_grid = [header, Spacer(1, 3.5 * mm)]
    details = _detail_table(shot, styles)
    if details:
        before_grid.append(details)

    if shot.get("flavor_tags"):
        before_grid.append(Spacer(1, 2.8 * mm))
        before_grid.append(Paragraph("FLAVOUR", styles["eyebrow"]))
        before_grid.append(Pills(shot["flavor_tags"], fonts))

    flowables = list(before_grid)

    if shot.get("tasting_notes"):
        flowables.append(Paragraph(
            f'<font name="{fonts["sans_bold"]}" size="6" color="{MUTED_HEX}">TASTING NOTES</font><br/>'
            + _clean(shot["tasting_notes"]),
            styles["note"],
        ))
    if shot.get("notes"):
        flowables.append(Paragraph(
            f'<font name="{fonts["sans_bold"]}" size="6" color="{MUTED_HEX}">ALSO NOTED</font><br/>'
            + _clean(shot["notes"]),
            styles["note"],
        ))

    meters = [(label, shot.get(key)) for key, label in (
        ("acidity", "Acidity"), ("body", "Body"), ("sweetness", "Sweetness"),
        ("bitterness", "Bitterness"), ("aftertaste", "Aftertaste"),
    ) if shot.get(key)]
    if meters:
        flowables.append(Spacer(1, 3 * mm))
        flowables.append(Paragraph("BALANCE", styles["eyebrow"]))
        flowables.append(MeterRows(meters, fonts))

    return flowables


def _bean_table(beans, styles, fonts):
    header = [
        Paragraph("BAG", styles["label"]),
        Paragraph("ROASTER", styles["label"]),
        Paragraph("ORIGIN / PROCESS", styles["label"]),
        Paragraph("ROASTED", styles["label"]),
        Paragraph("NOTES", styles["label"]),
    ]
    data = [header]
    for bean in beans:
        origin = " · ".join(part for part in (bean.get("origin"), bean.get("process"), bean.get("varietal")) if part)
        data.append([
            Paragraph(_clean(bean.get("name") or "Untitled bag"), styles["bean_name"]),
            Paragraph(_clean(bean.get("roaster") or "—"), styles["bean_cell"]),
            Paragraph(_clean(origin or "—"), styles["bean_cell"]),
            Paragraph(_clean(bean.get("roast_date") or "—"), styles["bean_cell"]),
            Paragraph(_clean(bean.get("notes") or "—"), styles["bean_cell"]),
        ])
    table = Table(data, colWidths=[38 * mm, 28 * mm, 40 * mm, 23 * mm, CONTENT_W - 129 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CREAM_DEEP),
        ("BACKGROUND", (0, 1), (-1, -1), PAPER),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 2.4 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6 * mm),
    ]))
    return table


def _draw_page(canv, doc, fonts):
    canv.saveState()
    canv.setFillColor(CREAM)
    canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    canv.setFillColor(INK)
    canv.setFont(fonts["serif_bold"], 10.5)
    canv.drawString(MARGIN_L, PAGE_H - 12 * mm, "Crema")
    canv.setFillColor(MUTED)
    canv.setFont(fonts["sans"], 6.6)
    canv.drawRightString(PAGE_W - MARGIN_R, PAGE_H - 11.6 * mm, "COFFEE JOURNAL")
    canv.setStrokeColor(LINE)
    canv.setLineWidth(0.6)
    canv.line(MARGIN_L, PAGE_H - 15 * mm, PAGE_W - MARGIN_R, PAGE_H - 15 * mm)
    canv.restoreState()


def _draw_footer(canv, total, fonts):
    canv.saveState()
    canv.setStrokeColor(LINE)
    canv.setLineWidth(0.6)
    canv.line(MARGIN_L, MARGIN_B - 4 * mm, PAGE_W - MARGIN_R, MARGIN_B - 4 * mm)
    canv.setFillColor(MUTED)
    canv.setFont(fonts["sans"], 6.4)
    canv.drawString(MARGIN_L, MARGIN_B - 8 * mm, PDF_FOOTER)
    canv.drawRightString(PAGE_W - MARGIN_R, MARGIN_B - 8 * mm, f"Page {canv.getPageNumber()} of {total}")
    canv.restoreState()


class _NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        self._fonts = kwargs.pop("crema_fonts")
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            _draw_footer(self, total, self._fonts)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)


def build_pdf(user, shots, beans, photo_paths=None, generated_at=None):
    """Return a complete PDF journal as bytes."""
    fonts = _register_fonts()
    styles = _styles(fonts)
    photo_paths = photo_paths or {}
    generated_at = generated_at or datetime.now()
    stats = _compute_stats(shots)

    story = []
    first_name = (user.get("name") or "Your").strip().split(" ")[0] or "Your"
    total = stats["total"]
    bag_count = len(beans)
    avg = stats["avg_rating"]

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("PERSONAL COFFEE JOURNAL", styles["eyebrow"]))
    story.append(Paragraph("Coffee, kept.", styles["title"]))
    story.append(Paragraph(
        f'{_clean(user.get("name") or "Coffee lover")}  ·  {_clean(_date_range(shots))}  ·  '
        f'exported {generated_at.strftime("%d %B %Y")}',
        styles["subtitle"],
    ))
    story.append(Spacer(1, 7 * mm))

    average_text = f"average {avg:.1f} / 5" if avg else "no scores yet"
    hero_subline = f"{total} shots · {bag_count} bags · {average_text}"
    if stats["most_brewed"]:
        hero_subline += f" · most brewed {stats['most_brewed'][0]}"
    story.append(HeroBand(
        "YOUR COFFEE, LATELY",
        f"{_clean(first_name)}, this is your coffee so far.",
        _clean(hero_subline),
        fonts,
        styles,
    ))
    story.append(Spacer(1, 5 * mm))

    typical = "—"
    typical_meta = "log an espresso shot to see this"
    if stats["avg_dose"]:
        typical = _num(stats["avg_dose"], 1) + "g"
        if stats["avg_yield"]:
            typical_meta = "→ " + _num(stats["avg_yield"], 1) + "g"
            if stats["avg_time"]:
                typical_meta += " · " + _shot_time(stats["avg_time"])

    story.append(StatTiles([
        ("Shots logged", str(total), f"{stats['week']} in the last seven days"),
        ("Average score", f"{avg:.1f}" if avg else "—", f"across {stats['rated']} rated shots"),
        ("Bags in the cellar", str(bag_count), stats["most_brewed"][0] if stats["most_brewed"] else "add a bag to get started"),
        ("Typical espresso", typical, typical_meta),
    ], fonts, styles))
    story.append(Spacer(1, 9 * mm))

    story.append(Paragraph("THE NOTES THAT KEEP RETURNING", styles["eyebrow"]))
    if stats["top_tags"]:
        story.append(Pills([f"{tag}  {count}" for tag, count in stats["top_tags"]], fonts))
    else:
        story.append(Paragraph("Flavour tags will collect here as shots are logged.", styles["small"]))

    highlights = []
    if stats["most_brewed"]:
        highlights.append(f"Most brewed: {_clean(stats['most_brewed'][0])}")
    if highlights:
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph("  ·  ".join(highlights), styles["small"]))

    if stats["best"]:
        story.append(Spacer(1, 7 * mm))
        story.append(BestCup(stats["best"], fonts, styles))

    story.append(PageBreak())
    story.extend(_section_header(
        "EVERY CUP, REMEMBERED", "Brewing history",
        f"{total} {'entry' if total == 1 else 'entries'}",
        styles,
    ))

    if not shots:
        story.append(Paragraph(
            "Nothing logged yet. The first entry is the beginning of a useful record.",
            styles["empty"],
        ))
    else:
        for index, shot in enumerate(shots):
            block = _shot_flowables(shot, photo_paths.get(shot.get("id")), styles, fonts)
            # Keep one shot's header, notes, and balance meters together so a
            # page can never end on an orphaned label or meter strip.
            story.append(KeepTogether(block))
            if index < len(shots) - 1:
                story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceBefore=1.5 * mm, spaceAfter=2.5 * mm))

    closing = [
        Spacer(1, 6 * mm),
        HRFlowable(width="100%", thickness=0.5, color=LINE, spaceAfter=4 * mm),
        Paragraph("Brewed, tasted, and remembered.  ·  Crema", styles["small"]),
    ]

    if beans:
        story.append(Spacer(1, 5 * mm))
        story.append(KeepTogether(
            _section_header(
                "ON THE SHELF", "The cellar",
                f"{bag_count} {'bag' if bag_count == 1 else 'bags'}",
                styles,
            )
            + [_bean_table(beans, styles, fonts)]
            + closing
        ))
    else:
        story.extend(closing)

    buffer = io.BytesIO()
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=MARGIN_T,
        bottomMargin=MARGIN_B,
        title="Crema — Coffee journal",
        author=user.get("name") or "Crema",
        subject="A personal coffee journal",
        creator="Crema",
    )
    frame = Frame(
        MARGIN_L, MARGIN_B, CONTENT_W, PAGE_H - MARGIN_T - MARGIN_B,
        id="body", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(
        id="journal", frames=[frame],
        onPage=lambda canv, doc: _draw_page(canv, doc, fonts),
    )])
    doc.build(story, canvasmaker=lambda *args, **kwargs: _NumberedCanvas(*args, crema_fonts=fonts, **kwargs))
    return buffer.getvalue()
