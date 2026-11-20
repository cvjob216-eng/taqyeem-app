# -*- coding: utf-8 -*-
"""توليد الخطة العلاجية بالذكاء الاصطناعي (Claude API).
لا تُرسل أي أسماء ولا نقاط فردية: فقط نسب تملك مجمّعة ونصوص الأداء المنتظر."""
import json
import os

MODEL_DEFAULT = "claude-sonnet-5-5"  # يمكن تغييره بإضافة ANTHROPIC_MODEL في Secrets

SYSTEM = """أنت مستشار بيداغوجي خبير بالتعليم الابتدائي التونسي (الرياضيات والإيقاظ العلمي).
تصلك رسالة JSON فيها: مستوى القسم ودرجته ومادته، وإحصائيات مجمّعة لنسب تملك المعايير، والأداء المنتظر المستهدف في التقييم، وأخطاء وأسباب معروفة لكل معيار.
مهمتك بناء خطة علاجية. أعد JSON صالحاً فقط، بلا أي شرح ولا Markdown، بهذا الشكل:
{"parts":[{"id":"p1","diagnosis":"الصعوبة أو الخطأ الأرجح وسببه في جملة أو جملتين","remedies":["نشاط علاجي","..."]}],
 "criteria":[{"name":"اسم المعيار كما ورد بالضبط","remedies":["نشاط علاجي","..."]}]}
القواعد:
- لكل id في «الأداء المنتظر» عنصر واحد بالضبط في parts بنفس الـid.
- في criteria ضع كل معيار نسبة تملكه أقل من «عتبة التنبيه»؛ أما المعيار المتملَّك فاكتفِ له بنشاط تثبيت أو إثراء واحد أو لا تدرجه.
- من 2 إلى 4 حلول لكل عنصر، كل حل نشاط قابل للتنفيذ داخل القسم (وضعية، تمرين، وسيلة، لعبة) في جملة واحدة، متدرج من المحسوس إلى المجرد، ومناسب لمستوى السنة.
- كلما انخفضت نسبة التملك كان العلاج أكثف (جماعي ثم فردي)، واربط التشخيص بالأخطاء والأسباب المعروفة عند ملاءمتها.
- لا تخترع أسماء ولا معطيات غير مذكورة. العربية الفصحى المبسطة."""


def _secret(name):
    try:
        import streamlit as st
        v = st.secrets.get(name)
    except Exception:
        v = None
    return v or os.environ.get(name)


def available():
    return bool(_secret("ANTHROPIC_API_KEY"))


def _lines(v):
    return [x.strip() for x in v if isinstance(x, str) and x.strip()] if isinstance(v, list) else []


def parse(text):
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b < a:
        raise ValueError("لا يوجد JSON في رد النموذج")
    obj = json.loads(text[a:b + 1])
    if not isinstance(obj.get("parts"), list):
        raise ValueError("بنية الرد غير صحيحة (parts)")
    obj["parts"] = [{"id": p.get("id"), "diagnosis": str(p.get("diagnosis", "")).strip(),
                     "remedies": _lines(p.get("remedies"))} for p in obj["parts"] if isinstance(p, dict)]
    obj["criteria"] = [{"name": c.get("name"), "remedies": _lines(c.get("remedies"))}
                       for c in obj.get("criteria", []) if isinstance(c, dict)]
    return obj


def generate_plan(payload):
    import anthropic
    client = anthropic.Anthropic(api_key=_secret("ANTHROPIC_API_KEY"))
    model = _secret("ANTHROPIC_MODEL") or MODEL_DEFAULT
    content = json.dumps(payload, ensure_ascii=False)
    err = None
    for attempt in range(2):
        msg = client.messages.create(
            model=model, max_tokens=4000, system=SYSTEM,
            messages=[{"role": "user",
                       "content": content if attempt == 0 else content + "\n\nأعد الإجابة بـ JSON صالح فقط."}])
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        try:
            return parse(text)
        except Exception as e:  # noqa: BLE001
            err = e
    raise RuntimeError(f"رد غير مفهوم من النموذج: {err}")
