# -*- coding: utf-8 -*-
"""دفتر التقييم والمتابعة — الرياضيات والإيقاظ العلمي
تشغيل:  pip install -r requirements.txt  ثم  streamlit run app.py
"""
import io
import numbers
import os
import zlib

import pandas as pd
import streamlit as st

import ai as _ai
import logic as L
from data import CRITERIA, DIAGNOSTIC, INDICATORS
import report as _report

st.set_page_config(page_title="دفتر التقييم والمتابعة", page_icon="📒", layout="wide")
# ---------- تحقق من تطابق إصدارات الملفات على الخادم ----------
import importlib

NEED = 8
_MODS = (("logic.py", L), ("report.py", _report), ("ai.py", _ai))
for _n, _m in _MODS:
    if getattr(_m, "VERSION", 0) < NEED:
        importlib.reload(_m)  # قد تكون الوحدة قديمة في الذاكرة فقط
_old = [n for n, m in _MODS if getattr(m, "VERSION", 0) < NEED]
if _old:
    st.error("هذه الملفات على الخادم أقدم من app.py: " + "، ".join(_old) + ". ارفع النسخ الجديدة إلى GitHub "
             "(في نفس مجلد app.py وبنفس الأسماء) ثم Manage app ← Reboot app.")
    st.stop()

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');
html, body, .stApp {font-family:'Cairo',sans-serif}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], .stMarkdown, label, p,
h1, h2, h3, h4, input, textarea, [data-baseweb], [data-testid="stExpander"], .stTabs,
[data-testid="stCaptionContainer"], [data-testid="stFileUploader"] {direction:rtl; text-align:right}
[data-testid="stDataFrame"], [data-testid="stDataEditor"], [data-testid="stSlider"] {direction:ltr}
</style>""", unsafe_allow_html=True)

# ---------- كلمة سر اختيارية (مهمة عند النشر العمومي) ----------
try:
    _pw = st.secrets.get("APP_PASSWORD")
except Exception:
    _pw = os.environ.get("APP_PASSWORD")
if _pw and not st.session_state.get("auth"):
    st.title("📒 دفتر التقييم والمتابعة")
    if st.text_input("كلمة السر", type="password") == _pw:
        st.session_state.auth = True
        st.rerun()
    st.stop()

st.title("📒 دفتر التقييم والمتابعة")

# ---------- بيانات المؤسسة ----------
cfg = L.settings()
with st.expander("🏢 بيانات المؤسسة"):
    a, b, c = st.columns(3)
    new_cfg = {"school": a.text_input("المؤسسة", cfg["school"]),
               "teacher": b.text_input("المربي", cfg["teacher"]),
               "year": c.text_input("السنة الدراسية", cfg["year"])}
    if new_cfg != cfg:
        L.save_settings(new_cfg)
        cfg = new_cfg

# ---------- الأقسام ----------
def _add():
    nm, yr = st.session_state.new_nm.strip(), st.session_state.new_yr
    if nm and yr is not None:
        st.session_state.cid = L.add_class(nm, yr, st.session_state[f"new_dg_{yr}"])
        st.session_state.new_nm, st.session_state.new_yr = "", None


def _level_changed(cid):
    """عند تغيير مستوى قسم تُقترح درجته المناسبة (ويمكنك تعديلها بعدها)"""
    st.session_state[f"ed_{cid}"] = L.default_degree(st.session_state[f"ey_{cid}"])


def _delete(cid):
    L.delete_class(cid)
    st.session_state.pop("cid", None)


classes = L.list_classes()
if classes:
    ids = [c["id"] for c in classes]
    if st.session_state.get("cid") not in ids:
        st.session_state.cid = ids[0]
    st.selectbox("🏫 القسم", ids, key="cid",
                 format_func=lambda i: next(f"{c['name']} — {L.YEARS[c['year']]} — {c['degree']}"
                                            for c in classes if c["id"] == i))

with st.expander("➕ إدارة الأقسام", expanded=not classes):
    st.markdown("**إضافة قسم جديد**")
    a, b, c, d = st.columns([3, 2, 2, 1])
    a.text_input("اسم القسم", placeholder="مثال: السادسة أ", key="new_nm")
    yr = b.selectbox("المستوى", list(L.YEARS), index=None, placeholder="اختر المستوى", format_func=L.YEARS.get,
                     key="new_yr")
    c.selectbox("الدرجة التي ينتمي إليها", L.DEGREES, index=L.DEGREES.index(L.default_degree(yr or 6)),
                key=f"new_dg_{yr}", disabled=yr is None)
    d.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
    d.button("إضافة", on_click=_add, type="primary", disabled=yr is None)
    if classes:
        cur = next(c for c in classes if c["id"] == st.session_state.cid)
        st.divider()
        st.markdown(f"**تعديل القسم الحالي: {cur['name']}**")
        a, b, c, d = st.columns([3, 2, 2, 2])
        nn = a.text_input("الاسم", cur["name"], key=f"en_{cur['id']}")
        ny = b.selectbox("المستوى", list(L.YEARS), index=list(L.YEARS).index(cur["year"]),
                         format_func=L.YEARS.get, key=f"ey_{cur['id']}",
                         on_change=_level_changed, args=(cur["id"],))
        nd = c.selectbox("الدرجة", L.DEGREES, index=L.DEGREES.index(cur["degree"]), key=f"ed_{cur['id']}")
        if (nn.strip(), ny, nd) != (cur["name"], cur["year"], cur["degree"]) and nn.strip():
            L.update_class(cur["id"], name=nn.strip(), year=ny, degree=nd)
            st.rerun()
        if d.checkbox("تأكيد الحذف النهائي لهذا القسم وبياناته", key=f"cf_{cur['id']}"):
            d.button("🗑️ حذف القسم", on_click=_delete, args=(cur["id"],))

if not classes:
    st.info("أضف قسماً للبدء.")
    st.stop()

cid = st.session_state.cid
cls = next(c for c in classes if c["id"] == cid)
data = L.load(cid)  # معطيات هذا القسم فقط (ملف مستقل)
subj = st.radio("المادة", list(CRITERIA), horizontal=True, key=f"subj_{cid}")
sd = L.subject(data, subj)
crit = CRITERIA[subj]
st.caption(f"{cfg['school']} — المربي: {cfg['teacher']} — {cfg['year']} — "
           f"{cls['name']} ({L.YEARS[cls['year']]}، {cls['degree']})")

t0, t1, t2, t3, t4 = st.tabs(["👥 قائمة التلاميذ", "📝 إدخال النقاط", "📊 النتائج", "🩺 التشخيص والعلاج", "📄 التصدير والنسخ"])

# ---------- 0) قائمة التلاميذ (تُدخل مرة واحدة للسنة) ----------
def _roster_reset(rk, names):
    st.session_state[rk] = pd.DataFrame({L.NAME: names})
    st.session_state[rk + "_p"] = dict(enumerate(names))
    st.session_state[rk + "_v"] = st.session_state.get(rk + "_v", 0) + 1


with t0:
    rk = f"rost_{cid}"
    if rk not in st.session_state:
        st.session_state[rk] = pd.DataFrame({L.NAME: data["roster"]})
        st.session_state[rk + "_p"] = dict(enumerate(data["roster"]))
    rver = st.session_state.get(rk + "_v", 0)
    st.markdown(f"**قائمة تلاميذ {cls['name']}** — تُدخل مرة واحدة وتظهر تلقائياً في كل المواد والتقييمات.")
    ed = st.data_editor(st.session_state[rk], num_rows="dynamic", use_container_width=True,
                        key=f"rosted_{cid}_{rver}")
    prev, cur, new_roster, renames, dups = st.session_state[rk + "_p"], {}, [], {}, []
    for idx, val in ed[L.NAME].items():
        name = "" if pd.isna(val) else str(val).strip()
        cur[idx] = name
        if not name:
            continue
        if name in new_roster:
            dups.append(name)
            continue
        old = prev.get(idx) if isinstance(idx, numbers.Integral) else None
        if old and old != name:
            renames[old] = name
        new_roster.append(name)
    st.session_state[rk + "_p"] = cur
    if dups:
        st.warning("أسماء مكررة تم تجاهلها: " + "، ".join(dups))
    if new_roster != data["roster"]:
        L.set_roster(data, new_roster, renames)
        L.refresh(data, sd)
        L.save(cid, data)
    st.caption(f"عدد التلاميذ: {len(data['roster'])} · ✅ يُحفظ تلقائياً · تصحيح اسم يحافظ على نقاطه")
    with st.expander("➕ لصق قائمة أسماء أو استيراد من ملف"):
        txt = st.text_area("الصق الأسماء (اسم في كل سطر)", height=140, key=f"paste_{cid}_{rver}")
        up = st.file_uploader("أو ملف Excel / CSV (عمود «الاسم واللقب» أو العمود الأول)", type=["xlsx", "csv"],
                              key=f"upr_{cid}_{rver}")
        mode = st.radio("الطريقة", ["إضافة إلى القائمة الحالية", "استبدال القائمة"], horizontal=True,
                        key=f"mode_{cid}")
        if st.button("تطبيق", key=f"apply_{cid}"):
            names = [x.strip() for x in txt.splitlines() if x.strip()]
            if up is not None:
                src = (pd.read_csv(up, encoding="utf-8-sig") if up.name.endswith(".csv")
                       else pd.read_excel(up))
                col = L.NAME if L.NAME in src else src.columns[0]
                names += [str(x).strip() for x in src[col].dropna() if str(x).strip()]
            merged = list(dict.fromkeys(([] if mode == "استبدال القائمة" else data["roster"]) + names))
            L.set_roster(data, merged)
            L.save(cid, data)
            _roster_reset(rk, merged)
            st.rerun()

# ---------- 1) الإدخال ----------
with t1:
    st.markdown("**سلّم التنقيط** (التوزيع الافتراضي اقتراح قابل للتعديل)")
    cols = st.columns(len(crit))
    maxes = {c["id"]: col.number_input(c["name"], 0.0, 20.0, float(sd["maxes"].get(c["id"], 0)), 0.25,
                                       format="%.2f", key=f"mx_{cid}_{subj}_{c['id']}")
             for col, c in zip(cols, crit)}
    if abs(sum(maxes.values()) - 20) > 1e-9:
        st.warning(f"مجموع الدرجات القصوى = {sum(maxes.values()):g} (المطلوب 20).")
    a, b = st.columns(2)
    thr = a.slider("عتبة التملك (من أقصى درجة المعيار)", 0.3, 1.0, float(sd["threshold"]), 0.05,
                   key=f"th_{cid}_{subj}")
    alert = b.slider("نسبة التملك الدنيا قبل التنبيه للمعالجة (%)", 10, 100, int(sd["alert"]), 5,
                     key=f"al_{cid}_{subj}")

    roster = data["roster"]
    new = {"maxes": maxes, "threshold": thr, "alert": alert}
    if not roster:
        st.info("👥 أدخل قائمة تلاميذ القسم أولاً من تبويب «قائمة التلاميذ» — مرة واحدة فقط للسنة كاملة.")
    else:
        rv = zlib.crc32("\n".join(roster).encode())
        bk = f"base_{cid}_{subj}_{rv}"
        if bk not in st.session_state:
            st.session_state[bk] = L.to_df(sd["students"], subj, blank=False)
        cfgs = {c["name"]: st.column_config.NumberColumn(c["name"], min_value=0.0, max_value=maxes[c["id"]],
                                                        step=0.01, format="%.2f") for c in crit}
        edited = st.data_editor(st.session_state[bk], use_container_width=True, hide_index=True,
                                disabled=[L.NAME], column_config=cfgs, key=f"ed_{cid}_{subj}_{rv}")
        df = L.to_df(edited.to_dict("records"), subj, blank=False)
        bad = [(r[L.NAME], c["name"]) for _, r in df.iterrows() for c in crit
               if pd.notna(r[c["name"]]) and not 0 <= r[c["name"]] <= maxes[c["id"]]]
        if bad:
            st.error("نقاط خارج المجال المسموح: " + "، ".join(f"{a} ({b})" for a, b in bad))
        sc = dict(sd["scores"])
        for _, r in df.iterrows():
            sc[r[L.NAME]] = {c["name"]: (None if pd.isna(r[c["name"]]) else float(r[c["name"]])) for c in crit}
        new["scores"] = sc
    if any(sd[k] != v for k, v in new.items()):
        sd.update(new)
        L.refresh(data, sd)
        L.save(cid, data)
        st.caption("✅ تم الحفظ تلقائياً في بيانات هذا القسم")

an = L.analyse(subj, sd)

# ---------- 2) النتائج ----------
with t2:
    if an is None:
        st.info("أضف تلميذاً واحداً على الأقل لعرض النتائج.")
    else:
        res, st_df = an
        show = res.copy()
        show.insert(0, "الرقم", range(1, len(show) + 1))
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.markdown("**الصفوف الإحصائية**")
        st.dataframe(st_df, use_container_width=True)
        st.caption("التملك = الحصول على العتبة أو أكثر من أقصى درجة المعيار (الخانة الفارغة تُحسب غير متملكة) · "
                   "النسبة = عدد المتملكين ÷ عدد التلاميذ × 100")

# ---------- 3) الأداء المنتظر والأخطاء والخطة العلاجية ----------
def _insert_cat(pk, cat, name):
    e = next(x for x in cat if x["label"] == name)
    body = [e["intro"]] + [f"• {x}" for x, alt in e["items"] if not alt]
    st.session_state[f"plt_{pk}"] = "\n".join(body)
    st.session_state[f"plb_{pk}"] = e["label"]


def _lines(s):
    return [x.strip() for x in s.splitlines() if x.strip()]


with t3:
    gk = f"aigen_{cid}_{subj}"  # يتغيّر بعد التوليد لتتحدّث الخانات بالقيم الجديدة
    gen = st.session_state.get(gk, 0)
    pl, pk = sd["plan"], f"{cid}_{subj}"
    st.markdown("#### 🎯 الأداء المنتظر لهذا التقييم")
    st.caption("الصق نص الأداء المنتظر كما هو (فترة أو ثلاثي). تفكّكه المنصة إلى مكوّنات وتنظّمها في الجدول "
               "وتتعامل معه كمعلم يشخّص الأخطاء ويقترح العلاج.")
    cat = L.catalog(cls["year"], subj)
    if cat:
        with st.expander("📚 إدراج نص جاهز من القوائم (اختياري — يمكنك تعديله بعد الإدراج)"):
            ch = st.selectbox("الفترة / الوحدة", [e["label"] for e in cat], key=f"plc_{pk}")
            st.button("إدراج في الخانة", key=f"pli_{pk}", on_click=_insert_cat, args=(pk, cat, ch))
    st.session_state.setdefault(f"plb_{pk}", pl["label"])
    st.session_state.setdefault(f"plt_{pk}", pl["text"])
    label = st.text_input("عنوان الفترة / الوحدة (مثال: الفترة الثالثة)", key=f"plb_{pk}")
    text = st.text_area("نص الأداء المنتظر", height=170, key=f"plt_{pk}",
                        placeholder="أن يحل المتعلم وضعيات مشكل دالة بـ:\n• ...\n• ...")
    intro, parts = L.parse_perf(text)
    keep = {x: v for x, v in pl["items"].items() if x in parts}
    if (label, text) != (pl["label"], pl["text"]) or keep != pl["items"]:
        pl.update(label=label, text=text, items=keep)
        L.save(cid, data)
    if parts:
        st.markdown("**المكوّنات المستخرجة:**\n\n" + "\n".join(f"{n}. {x}" for n, x in enumerate(parts, 1)))

    st.markdown("#### ✨ الأخطاء المرصودة والخطة العلاجية")
    if not parts:
        st.info("الصق نص الأداء المنتظر أولاً.")
    elif an is None:
        st.info("أدخل نقاط التلاميذ أولاً (تُستعمل نسب التملك في التشخيص).")
    elif not _ai.available():
        st.info("لتفعيل التوليد أضف مفتاحاً في Secrets (Manage app ← Settings ← Secrets): "
                "GROQ_API_KEY (مجاني بلا بطاقة) أو GEMINI_API_KEY (مجاني) أو ANTHROPIC_API_KEY. "
                "وفي الأثناء يمكنك كتابة الأخطاء والعلاج يدوياً في الخانات أدناه.")
    else:
        st.caption("يُرسَل إلى النموذج: المستوى والمادة ونص الأداء المنتظر ونسب التملك المجمّعة — دون أسماء ودون "
                   "نقاط فردية. الأخطاء المقترحة هي الأرجح عند هذا المستوى وليست مأخوذة من أوراق التلاميذ، "
                   "فراجعها وعدّلها.")
        st.caption("المزوّدون المفعّلون (بترتيب التجربة): " + " ← ".join(_ai.providers()))
        if pl.get("date"):
            st.caption(f"آخر توليد: {pl['date']}")
        if st.button("✨ ولّد الأخطاء والخطة العلاجية", type="primary", key=f"aib_{pk}"):
            try:
                with st.spinner("جارٍ تحليل الأداء المنتظر وإعداد الخطة العلاجية..."):
                    payload, ids = L.ai_payload(cls, subj, sd, an[0], an[1], intro, parts)
                    L.apply_ai(sd, subj, ids, _ai.generate_plan(payload))
                    L.save(cid, data)
                st.session_state[gk] = gen + 1
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"تعذّر التوليد: {e}")
    if parts:
        crit_names = [c["name"] for c in crit]
        new_items = {}
        for n, x in enumerate(parts, 1):
            it, kk = pl["items"].get(x, {}), f"{pk}_{zlib.crc32(x.encode())}_{gen}"
            with st.expander(f"{n}. {x if len(x) < 90 else x[:87] + '…'}",
                             expanded=any(it.get(f) for f in ("errors", "causes", "remedies"))):
                crs = st.multiselect("المعايير المرتبطة (لتحديد التلاميذ المعنيين)", crit_names,
                                     default=[c for c in it.get("criteria", []) if c in crit_names], key=f"pc_{kk}")
                err = st.text_area("الأخطاء المرصودة (سطر لكل خطأ)", "\n".join(it.get("errors", [])),
                                   height=110, key=f"pe_{kk}")
                cau = st.text_area("تأويل الخطأ والأسباب (سطر لكل سبب)", "\n".join(it.get("causes", [])),
                                   height=90, key=f"pa_{kk}")
                rem = st.text_area("الجهاز العلاجي (سطر لكل نشاط)", "\n".join(it.get("remedies", [])),
                                   height=110, key=f"pr_{kk}")
                new_items[x] = {"criteria": crs, "errors": _lines(err), "causes": _lines(cau), "remedies": _lines(rem)}
                if an is not None:
                    ws = L.students_for(an[0], sd, subj, crs)
                    st.markdown("**التلاميذ المعنيون بالعلاج:** " + ("، ".join(ws) if ws else "لا أحد ✅"))
        if new_items != pl["items"]:
            pl["items"] = new_items
            L.save(cid, data)
    if an is not None:
        with st.expander("📊 نظرة على المعايير (نسبة التملك والتلاميذ تحت العتبة)"):
            st.dataframe(pd.DataFrame([{"المعيار": r["name"], "التملك %": r["pct"],
                                        "التلاميذ تحت العتبة": "، ".join(r["weak"]) or "—"}
                                       for r in L.crit_rows(subj, sd, an[0], an[1])]),
                         use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### 📑 صفحة الكفايات")
    pg, k = sd["page"], f"{cid}_{subj}"
    a, b = st.columns(2)
    dom = a.text_input("كفاية المجال", pg["domain"], key=f"pgd_{k}")
    sub_c = b.text_input("كفاية المادة", pg["subject"], key=f"pgs_{k}")
    opts = L.assess_options(subj)
    cur = pg["assessment"]
    ch = st.selectbox("نوع التقييم", opts, index=opts.index(cur) if cur in opts else len(opts) - 1, key=f"pga_{k}")
    assess = st.text_input("نص نوع التقييم", cur if cur not in opts else "", key=f"pgc_{k}") \
        if ch == opts[-1] else ch
    newpg = {**pg, "domain": dom, "subject": sub_c, "assessment": assess}
    if newpg != pg:
        sd["page"] = newpg
        L.save(cid, data)

# ---------- 4) التصدير والنسخ ----------
with t4:
    st.markdown("**التقارير منفصلة لكل مادة** — ملف مستقل للرياضيات وآخر للإيقاظ العلمي.")
    found = False
    for s in CRITERIA:
        sx = L.subject(data, s)
        r = L.analyse(s, sx)
        if r is None:
            continue
        found = True
        res_s, st_s = r
        meta = {**cfg, "class_name": cls["name"], "level": L.YEARS[cls["year"]], "degree": cls["degree"]}
        item = {"subject": s, "res": res_s, "st_df": st_s, "page": sx["page"], "plan": L.plan_view(sx, s, res_s),
                "crit_rows": L.crit_rows(s, sx, res_s, st_s)}
        st.markdown(f"##### مادة {s}")
        a, b = st.columns(2)
        a.download_button(f"📄 تقرير {s} (Word)", _report.build_docx(meta, [item]),
                          f"taqyeem_{cls['name']}_{s}.docx",
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                          type="primary", key=f"dw_{cid}_{s}")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            res_s.to_excel(w, sheet_name="نتائج", index=False)
            st_s.to_excel(w, sheet_name="إحصائيات")
            for ws_ in w.book.worksheets:
                ws_.sheet_view.rightToLeft = True
        b.download_button(f"📊 {s} (Excel)", buf.getvalue(), f"taqyeem_{cls['name']}_{s}.xlsx",
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dx_{cid}_{s}")
    if not found:
        st.info("لا توجد نتائج لتصديرها في هذا القسم بعد.")
    st.divider()
    st.markdown("**نسخة احتياطية لكل الأقسام** — احتفظ بها دورياً: ملفات الخادم قد تُمسح عند إعادة تشغيل التطبيق.")
    st.download_button("💾 تنزيل النسخة الاحتياطية (zip)", L.backup_zip(), "taqyeem_backup.zip", "application/zip")
    bz = st.file_uploader("استرجاع نسخة احتياطية", type=["zip"], key="restore")
    if bz is not None and st.button("استرجاع"):
        try:
            n = L.restore_zip(bz.getvalue())
            for k in [k for k in st.session_state if k.startswith(("base_", "rm_", "rost_"))]:
                del st.session_state[k]
            st.success(f"تم استرجاع {n} ملفات. أعد تحميل الصفحة.")
        except Exception as e:
            st.error(f"ملف غير صالح: {e}")
