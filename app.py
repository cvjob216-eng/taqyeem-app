# -*- coding: utf-8 -*-
"""دفتر التقييم والمتابعة — الرياضيات والإيقاظ العلمي (الدرجة 2 و3)
تشغيل:  pip install -r requirements.txt  ثم  streamlit run app.py
"""
import io
import pandas as pd
import streamlit as st
from data import CRITERIA, DIAGNOSTIC, DEFAULT_MAX

st.set_page_config(page_title="دفتر التقييم والمتابعة", page_icon="📒", layout="wide")
st.markdown("<style>html,body,[class*='css']{direction:rtl;text-align:right}</style>",
            unsafe_allow_html=True)

# ---------------- الإعدادات ----------------
with st.sidebar:
    st.header("⚙️ الإعدادات")
    subject = st.radio("المادة", ["الرياضيات", "الإيقاظ العلمي"])
    degree = "الدرجة الثالثة (5 و6)"
    if subject == "الرياضيات":
        degree = st.radio("الدرجة", ["الدرجة الثانية (3 و4)", "الدرجة الثالثة (5 و6)"], index=1)
    school = st.text_input("المؤسسة", "المدرسة الابتدائية الخاصة \"ذو هايلو سكول\"")
    teacher = st.text_input("المربي", "شوقي سعداوي")
    year = st.text_input("السنة الدراسية", "2026-2027")
    threshold = st.slider("عتبة التملك (من أقصى درجة المعيار)", 0.3, 1.0, 0.5, 0.05,
                          help="في المصدر: النصف أو أكثر")
    alert_pct = st.slider("نسبة التملك الدنيا قبل التنبيه للمعالجة (%)", 10, 100, 50, 5)

crit = CRITERIA[subject]
minimal = [c for c in crit if not c["excellence"] and not c.get("mental")]
mental = [c for c in crit if c.get("mental")]
excellence = [c for c in crit if c["excellence"]]

st.title("📒 دفتر التقييم والمتابعة")
st.caption(f"{school} — المربي: {teacher} — السنة الدراسية {year} — {subject}"
           + (f" — {degree}" if subject == "الرياضيات" else ""))

# ---------------- سلّم الأعداد (قابل للتعديل) ----------------
st.subheader("1) سلّم التنقيط")
st.caption("التوزيع الافتراضي اقتراح (المصدر يحدد المجموع العام /20 فقط) — عدّله حسب سلّمك.")
key = subject
cols = st.columns(len(crit))
maxes = {}
for col, c in zip(cols, crit):
    maxes[c["id"]] = col.number_input(c["name"], 0.0, 20.0, float(DEFAULT_MAX[key][c["id"]]),
                                      0.5, key=f"max_{key}_{c['id']}")
total_max = sum(maxes.values())
if abs(total_max - 20) > 1e-9:
    st.warning(f"مجموع الدرجات القصوى = {total_max:g} (المطلوب 20).")

# ---------------- جدول الإدخال ----------------
st.subheader("2) إدخال نقاط التلاميذ")
names = [c["name"] for c in crit]
if "df" not in st.session_state or st.session_state.get("df_key") != key:
    st.session_state.df = pd.DataFrame({"الاسم واللقب": [""] * 5, **{n: [None] * 5 for n in names}})
    st.session_state.df_key = key

up = st.file_uploader("أو استورد قائمة من Excel/CSV (عمود «الاسم واللقب» + أعمدة المعايير)",
                      type=["xlsx", "csv"])
if up is not None and st.button("استيراد"):
    df_in = pd.read_csv(up) if up.name.endswith(".csv") else pd.read_excel(up)
    for n in names:
        if n not in df_in:
            df_in[n] = None
    st.session_state.df = df_in[["الاسم واللقب"] + names]

edited = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True,
                        key=f"ed_{key}")
df = edited.copy()
df = df[df["الاسم واللقب"].fillna("").astype(str).str.strip() != ""].reset_index(drop=True)
for n in names:
    df[n] = pd.to_numeric(df[n], errors="coerce")

# تحقق من تجاوز الحد الأقصى
bad = [(r["الاسم واللقب"], c["name"]) for _, r in df.iterrows() for c in crit
       if pd.notna(r[c["name"]]) and not (0 <= r[c["name"]] <= maxes[c["id"]])]
if bad:
    st.error("نقاط خارج المجال المسموح: " + "، ".join(f"{a} ({b})" for a, b in bad))

# ---------------- الحساب ----------------
def compute(df):
    out = df.copy()
    mn = [c["name"] for c in minimal]
    out["مجموع المعايير الدنيا"] = out[mn].sum(axis=1, min_count=1)
    parts = [c["name"] for c in mental] + ["مجموع المعايير الدنيا"] + [c["name"] for c in excellence]
    out["المجموع العام /20"] = out[parts].sum(axis=1, min_count=1)
    return out

def stats(res):
    n = len(res)
    max_row, cnt, pct = {}, {}, {}
    for c in crit:
        nm = c["name"]
        max_row[nm] = maxes[c["id"]]
        ok = (res[nm] >= threshold * maxes[c["id"]]).sum() if maxes[c["id"]] else 0
        cnt[nm], pct[nm] = int(ok), round(100 * ok / n, 1) if n else 0.0
    min_max = sum(maxes[c["id"]] for c in minimal)
    ok = (res["مجموع المعايير الدنيا"] >= threshold * min_max).sum()
    max_row["مجموع المعايير الدنيا"] = min_max
    cnt["مجموع المعايير الدنيا"], pct["مجموع المعايير الدنيا"] = int(ok), round(100 * ok / n, 1) if n else 0.0
    ok = (res["المجموع العام /20"] >= 10).sum()
    max_row["المجموع العام /20"] = 20
    cnt["المجموع العام /20"], pct["المجموع العام /20"] = int(ok), round(100 * ok / n, 1) if n else 0.0
    return pd.DataFrame({"التملك الأقصى بالمعيار": max_row,
                         "عدد الذين حققوا التملك الأدنى": cnt,
                         "النسبة المئوية (%)": pct}).T

if df.empty:
    st.info("أضف تلميذاً واحداً على الأقل لعرض النتائج.")
    st.stop()

res = compute(df)
st_df = stats(res)

st.subheader("3) الجدول الإجمالي")
res_show = res.copy()
res_show.insert(0, "الرقم", range(1, len(res_show) + 1))
st.dataframe(res_show, use_container_width=True, hide_index=True)
st.markdown("**الصفوف الإحصائية**")
st.dataframe(st_df, use_container_width=True)
st.caption("عدد المتملكين = التلاميذ الذين تحصلوا على النصف أو أكثر (حسب العتبة) · "
           "النسبة = عدد المتملكين ÷ عدد التلاميذ × 100 · "
           "المجموع العام: معتبر متملكاً عند 10/20.")

# ---------------- التشخيص والمعالجة ----------------
st.subheader("4) التشخيص ومعالجة التعثرات")
for c in crit:
    if c.get("mental"):
        continue
    nm = c["name"]
    p = st_df.loc["النسبة المئوية (%)", nm]
    weak = res.loc[res[nm] < threshold * maxes[c["id"]], "الاسم واللقب"].tolist()
    flag = "🔴" if p < alert_pct else "🟢"
    with st.expander(f"{flag} {nm} — التملك {p}% — متعثرون: {len(weak)}", expanded=p < alert_pct):
        d = DIAGNOSTIC[subject].get(nm)
        if weak:
            st.markdown("**التلاميذ المعنيون بالمعالجة:** " + "، ".join(weak))
        else:
            st.success("لا يوجد متعثرون في هذا المعيار.")
        if d:
            a, b, r = st.columns(3)
            a.markdown("**الأخطاء المرصودة**\n\n" + "\n".join(f"- {x}" for x in d["errors"]))
            b.markdown("**تأويل الخطأ والأسباب**\n\n" + "\n".join(f"- {x}" for x in d["causes"]))
            r.markdown("**الجهاز العلاجي المقترح**\n\n" + "\n".join(f"- {x}" for x in d["remedy"]))

# ---------------- التصدير ----------------
def to_excel():
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        res_show.to_excel(w, sheet_name="الجدول الإجمالي", index=False)
        st_df.to_excel(w, sheet_name="الإحصائيات")
        rows = []
        for c in crit:
            nm = c["name"]
            d = DIAGNOSTIC[subject].get(nm)
            if not d:
                continue
            weak = res.loc[res[nm] < threshold * maxes[c["id"]], "الاسم واللقب"].tolist()
            rows.append({"المعيار": nm, "التملك %": st_df.loc["النسبة المئوية (%)", nm],
                         "المتعثرون": "، ".join(weak), "الأخطاء": " | ".join(d["errors"]),
                         "الأسباب": " | ".join(d["causes"]), "العلاج": " | ".join(d["remedy"])})
        pd.DataFrame(rows).to_excel(w, sheet_name="التشخيص والعلاج", index=False)
        for ws in w.book.worksheets:
            ws.sheet_view.rightToLeft = True
    return buf.getvalue()

st.download_button("📥 تصدير إلى Excel", to_excel(), f"taqyeem_{key}.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
