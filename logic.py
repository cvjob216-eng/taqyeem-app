# -*- coding: utf-8 -*-
"""التخزين (ملف JSON مستقل لكل قسم) + الحساب الإحصائي + النسخ الاحتياطي"""
import io
import json
import os
import re
import uuid
import zipfile
from pathlib import Path

import pandas as pd
from data import CRITERIA, DEFAULT_MAX, DIAGNOSTIC

ROOT = Path(os.environ.get("TAQYEEM_DATA", "data"))
INDEX, SETTINGS, CLS_DIR = ROOT / "classes.json", ROOT / "settings.json", ROOT / "classes"
DEGREES = ["الدرجة الثانية", "الدرجة الثالثة"]
YEARS = {3: "السنة الثالثة", 4: "السنة الرابعة", 5: "السنة الخامسة", 6: "السنة السادسة"}
NAME = "الاسم واللقب"
MIN_SUM, TOTAL = "مجموع المعايير الدنيا", "المجموع العام /20"


def default_degree(year):
    return DEGREES[0] if year <= 4 else DEGREES[1]


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- الإعدادات العامة ----------
def settings():
    return {"school": "", "teacher": "", "year": "2026-2027", **_read(SETTINGS, {})}


def save_settings(s):
    _write(SETTINGS, s)


# ---------- الأقسام ----------
def list_classes():
    return _read(INDEX, [])


def add_class(name, year, degree):
    cid, cl = uuid.uuid4().hex[:8], list_classes()
    cl.append({"id": cid, "name": name, "year": year, "degree": degree})
    _write(INDEX, cl)
    return cid


def update_class(cid, **kw):
    cl = list_classes()
    for c in cl:
        if c["id"] == cid:
            c.update(kw)
    _write(INDEX, cl)


def delete_class(cid):
    _write(INDEX, [c for c in list_classes() if c["id"] != cid])
    (CLS_DIR / f"{cid}.json").unlink(missing_ok=True)


def load(cid):
    return _read(CLS_DIR / f"{cid}.json", {})


def save(cid, data):
    _write(CLS_DIR / f"{cid}.json", data)


def subject(data, s):
    """معطيات مادة داخل قسم (تُنشأ بقيم افتراضية عند أول استعمال)"""
    d = data.setdefault(s, {})
    d.setdefault("maxes", {k: float(v) for k, v in DEFAULT_MAX[s].items()})
    d.setdefault("threshold", 0.5)
    d.setdefault("alert", 50)
    d.setdefault("students", [])
    d.setdefault("remedies", {})
    return d


# ---------- الجداول ----------
def to_df(recs, s, blank=True):
    cols = [NAME] + [c["name"] for c in CRITERIA[s]]
    df = pd.DataFrame(recs, columns=cols) if recs else pd.DataFrame(columns=cols)
    if blank and df.empty:
        df = pd.DataFrame({NAME: [""] * 5, **{c: [None] * 5 for c in cols[1:]}})
    df[NAME] = df[NAME].fillna("").astype(str)
    for c in cols[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def clean(df, s):
    df = to_df(df.to_dict("records"), s, blank=False)
    return df[df[NAME].str.strip() != ""].reset_index(drop=True)


def to_records(df):
    return json.loads(df.to_json(orient="records", force_ascii=False))


def compute(df, s):
    crit, out = CRITERIA[s], df.copy()
    mn = [c["name"] for c in crit if not c["excellence"] and not c.get("mental")]
    out[MIN_SUM] = out[mn].sum(axis=1, min_count=1)
    parts = ([c["name"] for c in crit if c.get("mental")] + [MIN_SUM]
             + [c["name"] for c in crit if c["excellence"]])
    out[TOTAL] = out[parts].sum(axis=1, min_count=1)
    return out


def stats(res, s, maxes, thr):
    crit, n = CRITERIA[s], len(res)
    mx, cnt, pct = {}, {}, {}

    def add(col, m):
        ok = int((res[col] >= thr * m).sum()) if m else 0
        mx[col], cnt[col], pct[col] = m, ok, round(100 * ok / n, 1) if n else 0.0

    for c in crit:
        add(c["name"], maxes[c["id"]])
    add(MIN_SUM, sum(maxes[c["id"]] for c in crit if not c["excellence"] and not c.get("mental")))
    add(TOTAL, sum(maxes.values()))
    return pd.DataFrame({"التملك الأقصى بالمعيار": mx, "عدد الذين حققوا التملك الأدنى": cnt,
                         "النسبة المئوية (%)": pct}).T


def analyse(s, sd):
    """(res, stats) لمادة داخل قسم، أو None إن لم يوجد تلاميذ"""
    if not sd["students"]:
        return None
    res = compute(to_df(sd["students"], s, blank=False), s)
    return res, stats(res, s, sd["maxes"], sd["threshold"])


def weak(res, c, sd):
    return res.loc[res[c["name"]] < sd["threshold"] * sd["maxes"][c["id"]], NAME].tolist()


def remedy_presets(s):
    return list(dict.fromkeys(r for d in DIAGNOSTIC[s].values() for r in d["remedy"]))


def remedies(sd, s, name):
    return sd["remedies"].get(name, DIAGNOSTIC[s].get(name, {}).get("remedy", []))


# ---------- النسخ الاحتياطي ----------
def backup_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in ROOT.rglob("*.json"):
            z.write(p, p.relative_to(ROOT).as_posix())
    return buf.getvalue()


def restore_zip(raw):
    ok = re.compile(r"^(classes\.json|settings\.json|classes/[0-9a-f]{8}\.json)$")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        files = {n: z.read(n) for n in z.namelist() if ok.match(n)}
        for b in files.values():
            json.loads(b)  # تحقق من سلامة الملفات قبل الكتابة
        for n, b in files.items():
            (ROOT / n).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / n).write_bytes(b)
    return len(files)
