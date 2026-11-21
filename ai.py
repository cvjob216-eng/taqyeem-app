# -*- coding: utf-8 -*-
"""توليد الخطة العلاجية بالذكاء الاصطناعي (Claude API).
لا تُرسل أي أسماء ولا نقاط فردية: فقط نسب تملك مجمّعة ونصوص الأداء المنتظر."""
import json
import os

MODEL_DEFAULT = "claude-sonnet-5-5"  # يمكن تغييره بإضافة ANTHROPIC_MODEL في Secrets
GEMINI_DEFAULT = "gemini-3.8-flash"  # يمكن تغييره بإضافة GEMINI_MODEL في Secrets
GEMINI_FALLBACKS = ("gemini-3.8-flash", "gemini-3.5-flash")  # تُجرَّب إن كان النموذج غير متاح (404)

SYSTEM = """أنت معلم ومفتّش خبير بمنهج التعليم الابتدائي التونسي (الرياضيات والإيقاظ العلمي)، وتعمل كمعلم حقيقي يشخّص ويعالج.
تصلك رسالة JSON فيها: مستوى القسم ودرجته ومادته، ونص «الأداء المنتظر» لهذا التقييم مفكَّكاً إلى مكوّنات (لكل منها id)، ونسب التملك الفعلية للقسم في كل معيار مع مؤشراته.
لا تتوفر أوراق التلاميذ، فاستنتج بخبرة المعلم الأخطاء الأكثر ترجيحاً عند تلاميذ هذا المستوى بالذات في كل مكوّن.
أعد JSON صالحاً فقط (بلا شرح ولا Markdown) بهذا الشكل:
{"parts":[{"id":"p1","criteria":["اسم معيار"],"errors":["..."],"causes":["..."],"remedies":["..."]}]}
القواعد الصارمة:
- عنصر واحد لكل id وبنفس الـid.
- criteria: من 1 إلى 2 من أسماء المعايير الواردة في الرسالة، منقولة حرفياً، وهي الأقرب لمضمون المكوّن.
- errors: من 3 إلى 5 أخطاء محددة ودقيقة ترتبط مباشرة بنص المكوّن وبمستوى السنة المذكورة (مثل: «يضع الفاصل قبل منزلة الآحاد»). يُمنع التعميم، ويُمنع ذكر أي مفهوم أو عملية أو عدد أو كلمة لا تدخل في نص المكوّن ولا في منهج هذه السنة.
- causes: من 2 إلى 3 أسباب تفسّر تلك الأخطاء تفسيراً بيداغوجياً.
- remedies: من 2 إلى 4 أنشطة علاجية قابلة للتنفيذ في القسم، كل نشاط في جملة واحدة، متدرجة من المحسوس إلى المجرد، ومناسبة لهذا المستوى؛ وكلما انخفضت نسبة تملك المعيار المرتبط كان العلاج أكثف.
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
    obj["parts"] = [{"id": p.get("id"), "criteria": _lines(p.get("criteria")), "errors": _lines(p.get("errors")),
                     "causes": _lines(p.get("causes")), "remedies": _lines(p.get("remedies"))}
                    for p in obj["parts"] if isinstance(p, dict)]
    return obj


def _call_claude(content):
    import anthropic
    client = anthropic.Anthropic(api_key=_secret("ANTHROPIC_API_KEY"))
    msg = client.messages.create(model=_secret("ANTHROPIC_MODEL") or MODEL_DEFAULT, max_tokens=4000,
                                 system=SYSTEM, messages=[{"role": "user", "content": content}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _gemini_once(model, body, timeout):
    import urllib.request
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": _secret("GEMINI_API_KEY")})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _call_gemini(content):
    """REST مباشر (بلا مكتبة إضافية) بالمفتاح المجاني من Google AI Studio.
    عند الازدحام (503) يعيد المحاولة بتمهّل ثم ينتقل إلى النموذج التالي؛ ويُنتقل أيضاً عند 404 أو انتهاء المهلة.
    GEMINI_MODEL في Secrets يقبل عدة نماذج مفصولة بفاصلة (بترتيب الأفضلية)."""
    import time
    import urllib.error
    body = json.dumps({"systemInstruction": {"parts": [{"text": SYSTEM}]},
                       "contents": [{"role": "user", "parts": [{"text": content}]}],
                       "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192,
                                            "responseMimeType": "application/json"}}).encode("utf-8")
    wanted = [m.strip() for m in (_secret("GEMINI_MODEL") or GEMINI_DEFAULT).split(",") if m.strip()]
    models = list(dict.fromkeys(wanted + list(GEMINI_FALLBACKS)))
    data, last = None, "لا يوجد نموذج متاح"
    for k, model in enumerate(models):
        for attempt in range(3):
            try:
                data = _gemini_once(model, body, 150 if k == 0 else 90)
                break
            except urllib.error.HTTPError as e:
                last = f"Gemini ({e.code}، النموذج {model}): {e.read().decode('utf-8', 'ignore')[:300]}"
                if e.code == 503 and attempt < 2:  # ازدحام مؤقت: انتظر ثم أعد المحاولة
                    time.sleep(5 * (attempt + 1))
                    continue
                if e.code in (404, 503):
                    break  # النموذج التالي
                raise RuntimeError(last) from e
            except (TimeoutError, urllib.error.URLError) as e:
                last = f"انتهت مهلة الانتظار أو تعذّر الاتصال بـ Gemini (النموذج {model}): {e}"
                break
        if data is not None:
            break
    if data is None:
        raise RuntimeError(last + " — النماذج كلها مزدحمة حالياً؛ أعد المحاولة بعد دقائق.")
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
