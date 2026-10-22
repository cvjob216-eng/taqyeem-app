# -*- coding: utf-8 -*-
"""تصدير تقرير القسم إلى docx (اتجاه من اليمين إلى اليسار)"""
import io

import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm

VERSION = 3
FONT = "Arial"


def _el(tag, **attrs):
    e = OxmlElement(f"w:{tag}")
    for k, v in attrs.items():
        e.set(qn(f"w:{k}"), v)
    return e


def _par(container, text, size=11, bold=False, first=None, color=None):
    p = first if first is not None else container.add_paragraph()
    p._p.get_or_add_pPr().append(_el("bidi"))
    r = p.add_run(str(text))
    rPr = r._r.get_or_add_rPr()
    rPr.append(_el("rFonts", ascii=FONT, hAnsi=FONT, cs=FONT))
    if bold:
        rPr.extend([_el("b"), _el("bCs")])
    if color:
        rPr.append(_el("color", val=color))
    rPr.extend([_el("sz", val=str(size * 2)), _el("szCs", val=str(size * 2)), _el("rtl")])
    return p


def _fmt(v):
    if isinstance(v, float):
        return "" if pd.isna(v) else f"{v:g}"
    return "" if v is None else v


def _table(doc, header, rows, size=9, fill="D9E2F3", color=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t._tbl.tblPr.find(qn("w:tblStyle")).addnext(_el("bidiVisual"))
    for cell, h in zip(t.rows[0].cells, header):
        cell._tc.get_or_add_tcPr().append(_el("shd", val="clear", color="auto", fill=fill))
        _par(cell, h, size, True, first=cell.paragraphs[0], color=color)
    for row in rows:
        cells = t.add_row().cells
        for cell, v in zip(cells, row):
            bold = isinstance(v, tuple)
            v = v[0] if bold else v
            items = v if isinstance(v, list) else [v]
            for i, it in enumerate(items):
                txt = f"• {it}" if isinstance(v, list) else _fmt(it)
                _par(cell, txt, size, bold, first=cell.paragraphs[0] if i == 0 else None)
            if not items:
                _par(cell, "", size, first=cell.paragraphs[0])
    return t


def _dotted(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    bdr = _el("pBdr")
    bdr.append(_el("bottom", val="dotted", sz="6", space="1", color="auto"))
    bdr.append(_el("between", val="dotted", sz="6", space="1", color="auto"))
    pPr.extend([bdr, _el("bidi"), _el("spacing", before="280", after="0")])
    p.add_run(" ")


def _page(doc, subject, pg):
    """صفحة «الكفايات والأداء المنتظر»"""
    doc.add_page_break()
    _par(doc, "الكفايات والأداء المنتظر.", 16, True, color="2F5597")
    _par(doc, "")
    _table(doc, ["المادة", "كفاية المجال", "كفاية المادة", "نوع التقييم"],
           [[(subject,), pg["domain"], pg["subject"], pg["assessment"]]],
           size=12, fill="1F1F7F", color="FFFFFF")
    _par(doc, "")
    _par(doc, "الأداء المنتظر:", 13, True)
    lines = [ln for ln in pg["performance"].splitlines() if ln.strip()]
    for ln in lines:
        _par(doc, ln, 12)
    if not lines:
        for _ in range(6):
            _dotted(doc)


def build_docx(meta, items):
    """meta: school, teacher, year, class_name, level, degree
    items: [{subject, res, st_df, diag:[{name, pct, weak, errors, causes, remedies}]}]"""
    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Cm(1.5))

    _par(doc, "دفتر التقييم والمتابعة", 20, True)
    _par(doc, f"المؤسسة: {meta['school']}    المربي: {meta['teacher']}    السنة الدراسية: {meta['year']}")
    _par(doc, f"القسم: {meta['class_name']}    المستوى: {meta['level']}    {meta['degree']}")

    for it in items:
        doc.add_page_break()
        _par(doc, f"مادة {it['subject']}", 16, True)
        res, st_df = it["res"], it["st_df"]
        _par(doc, "الجدول الإجمالي للنتائج", 13, True)
        _table(doc, ["الرقم"] + list(res.columns),
               [[i + 1] + [_fmt(v) for v in r] for i, r in enumerate(res.values.tolist())])
        _par(doc, "")
        _par(doc, "الصفوف الإحصائية", 13, True)
        _table(doc, [""] + list(st_df.columns),
               [[idx] + [_fmt(v) for v in r] for idx, r in zip(st_df.index, st_df.values.tolist())])
        _par(doc, "")
        _par(doc, "التشخيص والمعالجة", 13, True)
        _table(doc, ["المعيار", "نسبة التملك %", "التلاميذ المعنيون بالخطة العلاجية", "الأخطاء المرصودة",
                     "تأويل الخطأ والأسباب", "الجهاز العلاجي"],
               [[d["name"], d["pct"], (d["weak"] or "—"), d["errors"], d["causes"], d["remedies"]]
                for d in it["diag"]])
        _page(doc, it["subject"], it["page"])

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
