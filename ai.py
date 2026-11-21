# -*- coding: utf-8 -*-
"""توليد الخطة العلاجية بالذكاء الاصطناعي: يجرّب المزوّدين المفعّلين بالتتابع (Groq ثم Gemini ثم Claude).
لا تُرسل أي أسماء ولا نقاط فردية: فقط نسب تملك مجمّعة ونصوص الأداء المنتظر."""
import json
import os

VERSION = 8  # يُقارَن بما يتوقعه app.py

MODEL_DEFAULT = "claude-sonnet-5-5"  # يمكن تغييره بإضافة ANTHROPIC_MODEL في Secrets
GEMINI_DEFAULT = "gemini-3.8-flash"  # يمكن تغييره بإضافة GEMINI_MODEL في Secrets
GEMINI_FALLBACKS = ("gemini-3.8-flash", "gemini-3.5-flash")  # تُجرَّب إن كان النموذج غير متاح أو مزدحماً
GROQ_DEFAULT = "openai/gpt-oss-120b"  # يمكن تغييره (أو إضافة قائمة مفصولة بفاصلة) بـ GROQ_MODEL في Secrets
GROQ_FALLBACKS = ("llama-3.3-70b-versatile",)

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


def providers():
    """المزوّدون المفعّلون بحسب المفاتيح الموجودة، بترتيب التجربة"""
    return [p for p, k in (("groq", "GROQ_API_KEY"), ("gemini", "GEMINI_API_KEY"),
                           ("claude", "ANTHROPIC_API_KEY")) if _secret(k)]


def available():
    return bool(providers())


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


def _post(url, headers, body, timeout):
    import urllib.request
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json",
                                                           "User-Agent": "taqyeem-app/1.0", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _try_models(label, models, call_once):
    """يجرّب النماذج بالترتيب. 5xx: إعادة محاولة بتمهّل ثم النموذج التالي؛ 404/429/انتهاء المهلة: النموذج التالي؛
    مفتاح غير صالح أو طلب خاطئ: يتوقف فوراً."""
    import time
    import urllib.error
    last = f"{label}: لا يوجد نموذج متاح"
    for k, model in enumerate(models):
        for attempt in range(3):
            try:
                return call_once(model, 120 if k == 0 else 75)
            except urllib.error.HTTPError as e:
                last = f"{label} ({e.code}، {model}): {e.read().decode('utf-8', 'ignore')[:200]}"
                if e.code in (500, 502, 503) and attempt < 2:
                    time.sleep(5 * (attempt + 1))
                    continue
                if e.code in (404, 429, 500, 502, 503):
                    break
                raise RuntimeError(last) from e
            except (TimeoutError, urllib.error.URLError) as e:
                last = f"{label} ({model}): انتهت المهلة أو تعذّر الاتصال ({e})"
                break
    raise RuntimeError(last)


def _models(secret, default, fallbacks):
    wanted = [m.strip() for m in (_secret(secret) or default).split(",") if m.strip()]
    return list(dict.fromkeys(wanted + list(fallbacks)))


def _call_groq(content):
    """Groq: واجهة متوافقة مع OpenAI، مستوى مجاني بلا بطاقة دفع"""
    def once(model, timeout):
        body = json.dumps({"model": model, "temperature": 0.4, "max_completion_tokens": 8000,
                           "messages": [{"role": "system", "content": SYSTEM},
                                        {"role": "user", "content": content}]}).encode("utf-8")
        data = _post("https://api.groq.com/openai/v1/chat/completions",
                     {"Authorization": f"Bearer {_secret('GROQ_API_KEY')}"}, body, timeout)
        return data["choices"][0]["message"]["content"] or ""
    return _try_models("Groq", _models("GROQ_MODEL", GROQ_DEFAULT, GROQ_FALLBACKS), once)


def _call_gemini(content):
    """Gemini (REST مباشر) بالمفتاح المجاني من Google AI Studio"""
    def once(model, timeout):
        body = json.dumps({"systemInstruction": {"parts": [{"text": SYSTEM}]},
                           "contents": [{"role": "user", "parts": [{"text": content}]}],
                           "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192,
                                                "responseMimeType": "application/json"}}).encode("utf-8")
        data = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                     {"x-goog-api-key": _secret("GEMINI_API_KEY")}, body, timeout)
        cands = data.get("candidates") or []
        if not cands:
            raise RuntimeError(f"Gemini: لا رد ({str(data.get('promptFeedback', ''))[:150]})")
        return "".join(p.get("text", "") for p in cands[0].get("content", {}).get("parts", []))
    return _try_models("Gemini", _models("GEMINI_MODEL", GEMINI_DEFAULT, GEMINI_FALLBACKS), once)


def generate_plan(payload):
    calls = {"groq": _call_groq, "gemini": _call_gemini, "claude": _call_claude}
    content = json.dumps(payload, ensure_ascii=False)
    errors = []
    for prov in providers():
        for attempt in range(2):
            try:
                text = calls[prov](content if attempt == 0 else content + "\n\nأعد الإجابة بـ JSON صالح فقط.")
            except Exception as e:  # noqa: BLE001
                errors.append(f"{prov}: {e}")
                break  # المزوّد نفسه فشل بعد محاولاته الداخلية: انتقل إلى التالي
            try:
                return parse(text)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{prov}: رد غير مفهوم ({e})")
    raise RuntimeError(" | ".join(errors) if errors else "لا يوجد مزوّد مفعّل")
