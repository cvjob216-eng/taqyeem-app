# -*- coding: utf-8 -*-
"""توليد الخطة العلاجية بالذكاء الاصطناعي (Claude API).
لا تُرسل أي أسماء ولا نقاط فردية: فقط نسب تملك مجمّعة ونصوص الأداء المنتظر."""
import json
import os

MODEL_DEFAULT = "claude-sonnet-5-5"  # يمكن تغييره بإضافة ANTHROPIC_MODEL في Secrets
GEMINI_DEFAULT = "gemini-3.8-flash"  # يمكن تغييره بإضافة GEMINI_MODEL في Secrets
GEMINI_FALLBACKS = ("gemini-3.8-flash", "gemini-3.5-flash")  # تُجرَّب إن كان النموذج غير متاح (404)

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


def provider():
    """gemini (مجاني) إن وُجد مفتاحه، وإلا claude"""
    if _secret("GEMINI_API_KEY"):
        return "gemini"
    return "claude" if _secret("ANTHROPIC_API_KEY") else None


def available():
    return provider() is not None


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


def _call_claude(content):
    import anthropic
    client = anthropic.Anthropic(api_key=_secret("ANTHROPIC_API_KEY"))
    msg = client.messages.create(model=_secret("ANTHROPIC_MODEL") or MODEL_DEFAULT, max_tokens=4000,
                                 system=SYSTEM, messages=[{"role": "user", "content": content}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _call_gemini(content):
    """استدعاء REST مباشر (بلا مكتبة إضافية) — يعمل بالمفتاح المجاني من Google AI Studio"""
    import urllib.error
    import urllib.request
    body = json.dumps({"systemInstruction": {"parts": [{"text": SYSTEM}]},
                       "contents": [{"role": "user", "parts": [{"text": content}]}],
                       "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192,
                                            "responseMimeType": "application/json"}}).encode("utf-8")
    first = _secret("GEMINI_MODEL") or GEMINI_DEFAULT
    models = list(dict.fromkeys([first, *GEMINI_FALLBACKS]))
    data = None
    for k, model in enumerate(models):
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": _secret("GEMINI_API_KEY")})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "ignore")[:300]
            if e.code == 404 and k < len(models) - 1:  # نموذج غير متاح: جرّب التالي
                continue
            raise RuntimeError(f"Gemini ({e.code}، النموذج {model}): {msg}") from e
    cands = data.get("candidates") or []
    if not cands:
        raise RuntimeError(f"لم يُرجع Gemini أي رد: {str(data.get('promptFeedback', ''))[:200]}")
    return "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))


def generate_plan(payload):
    call = _call_gemini if provider() == "gemini" else _call_claude
    content = json.dumps(payload, ensure_ascii=False)
    err = None
    for attempt in range(2):
        text = call(content if attempt == 0 else content + "\n\nأعد الإجابة بـ JSON صالح فقط.")
        try:
            return parse(text)
        except Exception as e:  # noqa: BLE001
            err = e
    raise RuntimeError(f"رد غير مفهوم من النموذج: {err}")
