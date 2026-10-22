# -*- coding: utf-8 -*-
"""دفتر التقييم والمتابعة — الرياضيات والإيقاظ العلمي
تشغيل:  pip install -r requirements.txt  ثم  streamlit run app.py
"""
import io
import os

import pandas as pd
import streamlit as st

import logic as L
from data import CRITERIA, DIAGNOSTIC, INDICATORS
from report import build_docx

st.set_page_config(page_title="دفتر التقييم والمتابعة", page_icon="📒", layout="wide")
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
    if nm:
        st.session_state.cid = L.add_class(nm, yr, st.session_state[f"new_dg_{yr}"])
        st.session_state.new_nm = ""


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
    yr = b.selectbox("المستوى", list(L.YEARS), index=3, format_func=L.YEARS.get, key="new_yr")
    c.selectbox("الدرجة التي ينتمي إليها", L.DEGREES, index=L.DEGREES.index(L.default_degree(yr)),
                key=f"new_dg_{yr}")
    d.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
    d.button("إضافة", on_click=_add, type="primary")
    if classes:
        cur = next(c for c in classes if c["id"] == st.session_state.cid)
        st.divider()
        st.markdown(f"**تعديل القسم الحالي: {cur['name']}**")
        a, b, c, d = st.columns([3, 2, 2, 2])
        nn = a.text_input("الاسم", cur["name"], key=f"en_{cur['id']}")
        ny = b.selectbox("المستوى", list(L.YEARS), index=list(L.YEARS).index(cur["year"]),
                         format_func=L.YEARS.get, key=f"ey_{cur['id']}")
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

t1, t2, t3, t4 = st.tabs(["📝 إدخال النقاط", "📊 النتائج", "🩺 التشخيص والعلاج", "📄 التصدير والنسخ"])

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

    bk = f"base_{cid}_{subj}"
    if bk not in st.session_state:
        st.session_state[bk] = L.to_df(sd["students"], subj)
    ver = st.session_state.get(bk + "_v", 0)
    cfgs = {c["name"]: st.column_config.NumberColumn(c["name"], min_value=0.0,
                                                    max_value=maxes[c["id"]], step=0.01,
                                                    format="%.2f") for c in crit}
    edited = st.data_editor(st.session_state[bk], num_rows="dynamic", use_container_width=True,
                            column_config=cfgs, key=f"ed_{cid}_{subj}_{ver}")
    with st.expander("استيراد قائمة من Excel / CSV"):
        up = st.file_uploader("عمود «الاسم واللقب» + أعمدة المعايير", type=["xlsx", "csv"],
                              key=f"up_{cid}_{subj}_{ver}")
        if up is not None and st.button("استيراد (يعوّض الجدول الحالي)"):
            src = pd.read_csv(up) if up.name.endswith(".csv") else pd.read_excel(up)
            st.session_state[bk] = L.to_df(src.to_dict("records"), subj)
            st.session_state[bk + "_v"] = ver + 1
            st.rerun()

    df = L.clean(edited, subj)
    bad = [(r[L.NAME], c["name"]) for _, r in df.iterrows() for c in crit
           if pd.notna(r[c["name"]]) and not 0 <= r[c["name"]] <= maxes[c["id"]]]
    if bad:
        st.error("نقاط خارج المجال المسموح: " + "، ".join(f"{a} ({b})" for a, b in bad))
    new = {"maxes": maxes, "threshold": thr, "alert": alert, "students": L.to_records(df)}
    if any(sd[k] != v for k, v in new.items()):
        sd.update(new)
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
        st.caption("التملك الأقصى/الأدنى = أعلى/أقل نقطة نالها تلميذ في العمود · النسبة المئوية = عدد التلاميذ الذين "
                   "نالوا نصف الدرجة (العتبة) فأكثر ÷ عدد التلاميذ المنقَّطين × 100 (الخانات الفارغة لا تُحتسب)")

# ---------- 3) التشخيص والعلاج ----------
def _save_rem(name, key, nkey):
    sel, extra = list(st.session_state[key]), st.session_state[nkey].strip()
    if extra and extra not in sel:
        sel.append(extra)
    dt = L.load(cid)
    L.subject(dt, subj)["remedies"][name] = sel
    L.save(cid, dt)
    st.session_state[key], st.session_state[nkey] = sel, ""


def _reset_rem(name, key):
    dt = L.load(cid)
    L.subject(dt, subj)["remedies"].pop(name, None)
    L.save(cid, dt)
    st.session_state[key] = L.remedies(L.subject(dt, subj), subj, name)


with t3:
    if an is None:
        st.info("أضف تلاميذ لعرض التشخيص.")
    else:
        res, st_df = an
        plan = pd.DataFrame([{"المعيار": c["name"], "التملك %": st_df.loc["النسبة المئوية (%)", c["name"]],
                              "التلاميذ المعنيون بالخطة العلاجية": "، ".join(L.weak(res, c, sd)) or "—",
                              "الجهاز العلاجي": " | ".join(L.remedies(sd, subj, c["name"])) or "—"}
                             for c in crit])
        st.markdown("**الخطة العلاجية** — التلاميذ الذين نالوا أقل من نصف درجة المعيار يُدرجون تلقائياً")
        st.dataframe(plan, use_container_width=True, hide_index=True)
        for c in crit:
            nm = c["name"]
            p = st_df.loc["النسبة المئوية (%)", nm]
            ws = L.weak(res, c, sd)
            with st.expander(f"{'🔴' if p < sd['alert'] else '🟢'} {nm} — التملك {p}% — متعثرون: {len(ws)}",
                             expanded=p < sd["alert"]):
                st.markdown("**التلاميذ المعنيون بالمعالجة:** " + ("، ".join(ws) if ws else "لا أحد ✅"))
                ind = INDICATORS.get((subj, cls["degree"]), {}).get(nm)
                if ind:
                    st.markdown("**مؤشرات المعيار (" + cls["degree"] + "):** " + " · ".join(ind))
                dg = DIAGNOSTIC[subj].get(nm)
                if dg:
                    x, y = st.columns(2)
                    x.markdown("**الأخطاء المرصودة**\n\n" + "\n".join(f"- {e}" for e in dg["errors"]))
                    y.markdown("**تأويل الخطأ والأسباب**\n\n" + "\n".join(f"- {e}" for e in dg["causes"]))
                saved = L.remedies(sd, subj, nm)
                key, nkey = f"rm_{cid}_{subj}_{c['id']}", f"rmn_{cid}_{subj}_{c['id']}"
                if key not in st.session_state:
                    st.session_state[key] = saved
                opts = list(dict.fromkeys(L.remedy_presets(subj) + saved))
                st.multiselect("الجهاز العلاجي — اختر من الخيارات", opts, key=key)
                st.text_area("أو اكتب علاجاً مخصصاً", key=nkey, height=70)
                x, y, _ = st.columns([1, 1, 4])
                x.button("💾 حفظ", key=f"sv_{key}", on_click=_save_rem, args=(nm, key, nkey))
                y.button("↩️ الافتراضي", key=f"rs_{key}", on_click=_reset_rem, args=(nm, key))

    st.divider()
    st.markdown("### 📑 صفحة الكفايات والأداء المنتظر")
    pg, k = sd["page"], f"{cid}_{subj}"
    a, b = st.columns(2)
    dom = a.text_input("كفاية المجال", pg["domain"], key=f"pgd_{k}")
    sub_c = b.text_input("كفاية المادة", pg["subject"], key=f"pgs_{k}")
    opts = L.assess_options(subj)
    cur = pg["assessment"]
    ch = st.selectbox("نوع التقييم", opts, index=opts.index(cur) if cur in opts else len(opts) - 1,
                      key=f"pga_{k}")
    assess = st.text_input("نص نوع التقييم", cur if cur not in opts else "", key=f"pgc_{k}") \
        if ch == opts[-1] else ch
    perf = st.text_area("الأداء المنتظر (اتركه فارغاً لطباعة أسطر منقطة تُملأ يدوياً)", pg["performance"],
                        height=110, key=f"pgp_{k}")
    newpg = {"domain": dom, "subject": sub_c, "assessment": assess, "performance": perf}
    if newpg != pg:
        sd["page"] = newpg
        L.save(cid, data)

# ---------- 4) التصدير والنسخ ----------
with t4:
    items = []
    for s in CRITERIA:
        sx = L.subject(data, s)
        r = L.analyse(s, sx)
        if r is None:
            continue
        res_s, st_s = r
        diag = []
        for c in CRITERIA[s]:
            d = DIAGNOSTIC[s].get(c["name"], {"errors": [], "causes": []})
            diag.append({"name": c["name"], "pct": st_s.loc["النسبة المئوية (%)", c["name"]],
                         "weak": L.weak(res_s, c, sx), "errors": d["errors"], "causes": d["causes"],
                         "remedies": L.remedies(sx, s, c["name"])})
        items.append({"subject": s, "res": res_s, "st_df": st_s, "diag": diag, "page": sx["page"]})
    if items:
        meta = {**cfg, "class_name": cls["name"], "level": L.YEARS[cls["year"]], "degree": cls["degree"]}
        st.download_button("📄 تصدير تقرير القسم إلى Word (docx)", build_docx(meta, items),
                           f"taqyeem_{cls['name']}.docx",
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                           type="primary")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            for it in items:
                it["res"].to_excel(w, sheet_name=f"{it['subject']} - نتائج", index=False)
                it["st_df"].to_excel(w, sheet_name=f"{it['subject']} - إحصائيات")
            for ws in w.book.worksheets:
                ws.sheet_view.rightToLeft = True
        st.download_button("📊 تصدير إلى Excel", buf.getvalue(), f"taqyeem_{cls['name']}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.info("لا توجد نتائج لتصديرها في هذا القسم بعد.")
    st.divider()
    st.markdown("**نسخة احتياطية لكل الأقسام** — احتفظ بها دورياً: ملفات الخادم قد تُمسح عند إعادة تشغيل التطبيق.")
    st.download_button("💾 تنزيل النسخة الاحتياطية (zip)", L.backup_zip(), "taqyeem_backup.zip", "application/zip")
    bz = st.file_uploader("استرجاع نسخة احتياطية", type=["zip"], key="restore")
    if bz is not None and st.button("استرجاع"):
        try:
            n = L.restore_zip(bz.getvalue())
            for k in [k for k in st.session_state if k.startswith(("base_", "rm_"))]:
                del st.session_state[k]
            st.success(f"تم استرجاع {n} ملفات. أعد تحميل الصفحة.")
        except Exception as e:
            st.error(f"ملف غير صالح: {e}")
