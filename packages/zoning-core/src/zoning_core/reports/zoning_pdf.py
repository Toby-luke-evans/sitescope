"""Stripped PDF report generator for zoning summaries.

Generates a clean 4-page report from zoning data (no proforma, no 3D, no unit mix).

Page 1 — Header + Parcel Info + Zoning Classification Card
Page 2 — Overlay Summary (Height, Lot Coverage, Parking Zone)
Page 3 — Development Standards (Setbacks, Angular Planes, Bylaw Refs)
Page 4 — Disclaimer + Notes + Map reference
"""

import io
import json
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PAGE_W, PAGE_H = letter

# ── Color palette (matches SiteScope dark identity) ──
DARK = colors.HexColor("#090907")
BROWN = colors.HexColor("#b18255")
CREAM = colors.HexColor("#efe7dc")
MUTED = colors.HexColor("#91887c")
FADED = colors.HexColor("#615a52")
WHITE = colors.HexColor("#ffffff")
GREEN = colors.HexColor("#89b482")


def _header_style() -> ParagraphStyle:
    return ParagraphStyle(
        "Header",
        fontName="Helvetica-Bold",
        fontSize=22,
        textColor=WHITE,
        spaceAfter=4,
    )


def _subheader_style() -> ParagraphStyle:
    return ParagraphStyle(
        "SubHeader",
        fontName="Helvetica-Oblique",
        fontSize=9,
        textColor=MUTED,
        spaceAfter=2,
    )


def _section_style() -> ParagraphStyle:
    return ParagraphStyle(
        "Section",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=WHITE,
        spaceAfter=6,
        spaceBefore=14,
    )


def _body_style() -> ParagraphStyle:
    return ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=10,
        textColor=CREAM,
        spaceAfter=4,
        leading=14,
    )


def _label_style() -> ParagraphStyle:
    return ParagraphStyle(
        "Label",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=MUTED,
        spaceAfter=2,
    )


def _value_style(size: int = 16) -> ParagraphStyle:
    return ParagraphStyle(
        "Value",
        fontName="Helvetica-Bold",
        fontSize=size,
        textColor=WHITE,
        spaceAfter=2,
    )


def _small_style() -> ParagraphStyle:
    return ParagraphStyle(
        "Small",
        fontName="Helvetica",
        fontSize=8,
        textColor=FADED,
        spaceAfter=2,
    )


def _fmt_num(v) -> str:
    """Format a number value for display."""
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def _fmt_pct(v) -> str:
    if v is None:
        return "—"
    return f"{v:.1f}%"


def _labelize(key: str) -> str:
    return key.replace("_", " ").title()


def _fmt_value(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False, separators=(", ", ": "))
    return str(v)


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _append_full_development_standards(story: list, dev: dict | None) -> None:
    """Append all categorized standards to the PDF story."""
    if not dev:
        return

    story.append(Spacer(1, 24))
    story.append(Paragraph("Full Zoning Analysis", _section_style()))
    defaults = dev.get("defaults_used") or []
    if defaults:
        story.append(_p("Assumptions / data gaps", _label_style()))
        for item in defaults:
            story.append(_p(f"• {item}", _small_style()))
        story.append(Spacer(1, 8))

    for category in dev.get("categories") or []:
        story.append(Paragraph(f"{escape(str(category.get('category_id', '')))}. {escape(str(category.get('category_name', '')))}", _section_style()))
        rows = [["Standard", "Value", "Bylaw / Notes"]]
        for key, standard in (category.get("standards") or {}).items():
            value = standard.get("value") if isinstance(standard, dict) else standard
            unit = standard.get("unit") if isinstance(standard, dict) else None
            bylaw = standard.get("bylaw_ref") if isinstance(standard, dict) else None
            note = standard.get("note") if isinstance(standard, dict) else None
            is_default = standard.get("is_default") if isinstance(standard, dict) else False
            value_text = _fmt_value(value)
            if unit:
                value_text = f"{value_text} {unit}"
            notes = []
            if bylaw:
                notes.append(f"§{bylaw}")
            if note:
                notes.append(str(note))
            if is_default:
                notes.append("default/assumption")
            rows.append([_labelize(key), value_text, "; ".join(notes) or "—"])

        table = Table(rows, colWidths=[1.65 * inch, 2.0 * inch, 1.85 * inch], hAlign="LEFT", repeatRows=1)
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("TEXTCOLOR", (0, 0), (-1, 0), CREAM),
            ("BACKGROUND", (0, 0), (-1, 0), FADED),
            ("TEXTCOLOR", (0, 1), (-1, -1), CREAM),
            ("BACKGROUND", (0, 1), (-1, -1), DARK),
            ("GRID", (0, 0), (-1, -1), 0.35, FADED),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(Spacer(1, 10))


def _draw_header(canvas, doc):
    """Draw dark header bar with title on every page."""
    canvas.saveState()
    # Background bar
    canvas.setFillColor(DARK)
    canvas.rect(0, PAGE_H - 60, PAGE_W, 60, fill=1, stroke=0)
    # Title
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawString(48, PAGE_H - 38, "Zoning Report")
    # Accent line
    canvas.setStrokeColor(BROWN)
    canvas.setLineWidth(2)
    canvas.line(48, PAGE_H - 44, PAGE_W - 48, PAGE_H - 44)
    # City badge
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    city_text = getattr(doc, "_city_label", "")
    if city_text:
        canvas.drawString(PAGE_W - 48 - canvas.stringWidth(city_text, "Helvetica", 8), PAGE_H - 38, city_text)
    # Footer
    canvas.setFillColor(FADED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(48, 24, f"Generated {datetime.now().strftime('%-d %b %Y')}")
    canvas.drawRightString(PAGE_W - 48, 24, f"Page {doc.page}")
    canvas.restoreState()


# ════════════════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════════════════

def build_zoning_pdf(data: dict) -> bytes:
    """Build a zoning PDF report from a zoning data dict.

    `data` follows the shape of our /zoning response:
    {
        "parcel": {"lat", "lng", "zone_code", "zn_string"},
        "zoning": {"zone_code", "zn_string", "max_fsi", "max_height_m", "storeys", "density", "lot_coverage", "stand_set"},
        "overlays": {"height", "lot_coverage", "parking_zone"},
        "standards": {"setbacks", "angular_planes", "bylaw_reference"},
        "city": "toronto",
    }
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=72,
        bottomMargin=48,
        leftMargin=48,
        rightMargin=48,
    )

    city = data.get("city", "Toronto").title()
    doc._city_label = city

    zoning = data.get("zoning", {})
    overlays = data.get("overlays", {})
    standards = data.get("standards", {})
    parcel = data.get("parcel", {})

    story = []

    # ════════════════════════════════════════════════════════════════
    # PAGE 1 — Zoning Classification
    # ════════════════════════════════════════════════════════════════

    story.append(Paragraph("Zoning Classification", _section_style()))
    story.append(Spacer(1, 8))

    # Zone code big + bold
    story.append(Paragraph(zoning.get("zone_code", "N/A"), _value_style(28)))
    story.append(Paragraph(zoning.get("zn_string", ""), _subheader_style()))
    story.append(Spacer(1, 16))

    # Key params table
    key_data = [
        ["Parameter", "Value", "Unit"],
        ["Max FSI / FAR", _fmt_num(zoning.get("max_fsi")), "×"],
        ["Max Height", _fmt_num(zoning.get("max_height_m")), "m"],
        ["Storeys (approx)", _fmt_num(zoning.get("storeys")), "storeys"],
        ["Density", _fmt_num(zoning.get("density")), "units/ha"],
        ["Lot Coverage", _fmt_pct(zoning.get("lot_coverage")), "%"],
        ["Standard Set", _fmt_num(zoning.get("stand_set")), "—"],
    ]

    t = Table(key_data, colWidths=[2.2 * inch, 1.8 * inch, 1.0 * inch], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, 0), CREAM),
        ("BACKGROUND", (0, 0), (-1, 0), FADED),
        ("TEXTCOLOR", (0, 1), (-1, -1), CREAM),
        ("BACKGROUND", (0, 1), (-1, -1), DARK),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("ALIGN", (2, 0), (2, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, FADED),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [FADED, None]),
    ]))
    story.append(t)

    story.append(Spacer(1, 16))
    # Parcel info
    lat = parcel.get("lat")
    lng = parcel.get("lng")
    if lat and lng:
        story.append(Paragraph("Parcel Location", _section_style()))
        story.append(Paragraph(f"Coordinates: {lat:.6f}, {lng:.6f} (WGS84)", _body_style()))

    story.append(Spacer(1, 24))
    story.append(Paragraph("<b>Overlay Summary</b>", _section_style()))
    story.append(Spacer(1, 8))

    # Overlay cards
    height_ov = overlays.get("height", {}) or {}
    coverage_ov = overlays.get("lot_coverage", {}) or {}
    parking_ov = overlays.get("parking_zone", {}) or {}

    ov_data = [
        ["Overlay", "Value", "Notes"],
        ["Height Overlay", f"{_fmt_num(height_ov.get('height_m'))} m", f"{_fmt_num(height_ov.get('storeys'))} storeys"],
        ["Lot Coverage", _fmt_pct(coverage_ov.get("coverage_pct")), "From overlay layer"],
        ["Parking Zone", parking_ov.get("zone", "—") or "—", "Toronto parking by-law"],
    ]

    t2 = Table(ov_data, colWidths=[2.0 * inch, 2.0 * inch, 1.0 * inch], hAlign="LEFT")
    t2.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, 0), CREAM),
        ("BACKGROUND", (0, 0), (-1, 0), FADED),
        ("TEXTCOLOR", (0, 1), (-1, -1), CREAM),
        ("BACKGROUND", (0, 1), (-1, -1), DARK),
        ("GRID", (0, 0), (-1, -1), 0.5, FADED),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t2)

    # ════════════════════════════════════════════════════════════════
    # PAGE 2 — Development Standards
    # ════════════════════════════════════════════════════════════════

    story.append(Spacer(1, 36))
    story.append(Paragraph("Development Standards", _section_style()))
    story.append(Spacer(1, 8))

    setbacks = standards.get("setbacks", {})
    setback_data = [
        ["Setback", "Required Distance"],
        ["Front Yard (minimum)", f"{setbacks.get('front_m') or '—'} m"],
        ["Rear Yard (minimum)", f"{setbacks.get('rear_m') or '—'} m"],
        ["Side Interior (minimum)", f"{setbacks.get('side_interior_m') or '—'} m"],
        ["Side Exterior (minimum)", f"{setbacks.get('side_exterior_m') or '—'} m"],
        ["Side Total (minimum)", f"{setbacks.get('side_total_m') or '—'} m"],
    ]

    t3 = Table(setback_data, colWidths=[2.5 * inch, 2.5 * inch], hAlign="LEFT")
    t3.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, 0), CREAM),
        ("BACKGROUND", (0, 0), (-1, 0), FADED),
        ("GRID", (0, 0), (-1, -1), 0.5, FADED),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t3)

    story.append(Spacer(1, 16))

    # Angular Planes
    ap = standards.get("angular_planes", {})
    if ap.get("applies"):
        story.append(Paragraph("Angular Planes", _section_style()))
        story.append(Paragraph(
            f"Applies: Yes — Angle: {ap.get('plane_angle_deg', '—')}° "
            f"from {ap.get('start_height_m', '—')} m height.",
            _body_style(),
        ))
    else:
        story.append(Paragraph("Angular Planes", _section_style()))
        story.append(Paragraph("Not applicable for this zone.", _body_style()))

    story.append(Spacer(1, 16))

    # Bylaw References
    refs = standards.get("bylaw_reference", [])
    if refs:
        story.append(Paragraph("Bylaw References", _section_style()))
        if isinstance(refs, list):
            for ref in refs:
                story.append(Paragraph(f"• {ref}", _body_style()))
        else:
            story.append(Paragraph(str(refs), _body_style()))

    _append_full_development_standards(
        story,
        data.get("development_standards") or standards.get("development_standards"),
    )

    # ════════════════════════════════════════════════════════════════
    # PAGE 3 — Disclaimer
    # ════════════════════════════════════════════════════════════════

    story.append(Spacer(1, 36))
    story.append(Paragraph("Disclaimer", _section_style()))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "This report is generated automatically from publicly available zoning data "
        "and bylaw information. While every effort is made to ensure accuracy, this "
        "report is for informational purposes only and does not constitute legal, "
        "planning, or engineering advice. Always verify with the municipality "
        f"({city}) and consult qualified professionals before making development decisions.",
        _body_style(),
    ))
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Data sources: Toronto Open Data (CKAN), Zoning By-law No. 569-2013, "
        "and City of Toronto Official Plan.",
        _small_style(),
    ))

    # Build PDF
    doc.build(story, onFirstPage=_draw_header, onLaterPages=_draw_header)
    buffer.seek(0)
    return buffer.read()


# Alias for use in reports router
build_pdf = build_zoning_pdf
