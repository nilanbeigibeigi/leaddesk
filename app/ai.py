"""Follow-up email drafting. AI when available; a clear template when not. A person always sends it."""
import json
import os
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "qwen2.5:7b")

SYSTEM = """You write short, friendly follow-up emails for a freelance web, AI and finance-tools developer
in Vancouver. Write in {language}. {farsi_note}
Rules: 60-120 words. Refer to what was actually discussed (from the notes). One clear next step with a question.
No pressure, no made-up facts, prices or dates beyond what the notes say. Plain text.
Return ONLY JSON: {{"subject": "...", "body": "..."}}"""


def _chat(system, user):
    payload = {"model": CHAT_MODEL, "stream": False, "format": "json", "options": {"temperature": 0.3},
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())["message"]["content"]


def template(deal, language):
    first = deal["contact"].split()[0] if deal["contact"] else ""
    if language == "Farsi":
        return {"subject": f"پیگیری: {deal['title']}",
                "body": f"سلام {first} عزیز،\n\nخواستم درباره‌ی «{deal['title']}» حالتان را بپرسم و ببینم سؤالی دارید یا نه.\n"
                        f"اگر مایل باشید، یک تماس کوتاه ۱۵ دقیقه‌ای هماهنگ کنیم تا قدم بعدی را مشخص کنیم. چه زمانی برایتان مناسب است؟\n\nبا احترام،\nنیلان"}
    return {"subject": f"Following up: {deal['title']}",
            "body": f"Hi {first},\n\nI wanted to check in about {deal['title'].lower()} and see if you had any questions.\n"
                    f"If it helps, we could do a quick 15-minute call to agree on the next step. What time works for you this week?\n\nBest,\nNilan"}


def draft_followup(deal, activities, language="English", chat=None):
    chat = chat or _chat
    notes = "\n".join(f"- {a['on_date']} {a['kind']}: {a['note']}" for a in activities[-6:]) or "- (no notes yet)"
    user = (f"Contact: {deal['contact']} at {deal['company']}\nDeal: {deal['title']} ({deal['service']}, stage: {deal['stage']})\n"
            f"Next step planned: {deal.get('next_step') or 'none'}\nNotes:\n{notes}")
    system = SYSTEM.format(language=language,
                           farsi_note="Use natural, polite Persian (Farsi) as spoken by Iranians in Canada." if language == "Farsi" else "")
    try:
        out = json.loads(chat(system, user))
        if out.get("subject") and out.get("body"):
            return {**out, "source": "ai"}
        raise ValueError("empty draft")
    except Exception as e:
        return {**template(deal, language), "source": "template", "error": str(e)}
