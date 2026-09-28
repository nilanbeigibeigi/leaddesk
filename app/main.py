"""LeadDesk — a small CRM for a freelance service business.

Run:  python -m uvicorn app.main:app --reload     then open http://127.0.0.1:8000
"""
import datetime as dt
import os
from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import ai, db

HERE = os.path.dirname(os.path.abspath(__file__))


@asynccontextmanager
async def lifespan(app):
    db.init()
    yield


app = FastAPI(title="LeadDesk", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
today = dt.date.today


def days_from_today(s):
    return (dt.date.fromisoformat(s) - today()).days if s else None


def money(v):
    return f"${v:,.0f}"


templates.env.globals.update(days_from_today=days_from_today, stages=db.STAGES, prob=db.PROBABILITY)
templates.env.filters["money"] = money

DEAL_SQL = """SELECT d.*, c.name AS contact, c.company, c.email, c.language, c.source,
              (SELECT MAX(on_date) FROM activities a WHERE a.deal_id = d.id) AS last_touch
              FROM deals d JOIN contacts c ON c.id = d.contact_id"""


def deals(where="1=1", params=()):
    out = db.rows(f"{DEAL_SQL} WHERE {where} ORDER BY d.next_step_on IS NULL, d.next_step_on", params)
    for d in out:
        d["due_in"] = days_from_today(d["next_step_on"])
        last = d["last_touch"] or d["created_on"]
        d["quiet_days"] = -days_from_today(last)
    return out


def get_deal(did):
    d = deals("d.id = ?", (did,))
    if not d:
        raise HTTPException(404, "Deal not found")
    return d[0]


def board_ctx():
    all_deals = deals()
    columns = {s: [d for d in all_deals if d["stage"] == s] for s in db.STAGES}
    return {"columns": columns, "totals": {s: sum(d["value"] for d in ds) for s, ds in columns.items()}}


# ------------------------------------------------------------------ dashboard
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    open_deals = [d for d in deals() if d["stage"] in db.OPEN_STAGES]
    closed = db.rows("SELECT stage, value, closed_on FROM deals WHERE stage IN ('Won','Lost')")
    won = [c for c in closed if c["stage"] == "Won"]
    month = today().isoformat()[:7]
    return templates.TemplateResponse(request, "dashboard.html", {
        "page": "dash",
        "due": [d for d in open_deals if d["due_in"] is not None and d["due_in"] <= 0],
        "upcoming": [d for d in open_deals if d["due_in"] is not None and 0 < d["due_in"] <= 7],
        "no_step": [d for d in open_deals if not d["next_step_on"]],
        "quiet": [d for d in open_deals if d["quiet_days"] >= 14],
        "pipeline": sum(d["value"] for d in open_deals),
        "weighted": sum(d["value"] * db.PROBABILITY[d["stage"]] for d in open_deals),
        "won_month": sum(c["value"] for c in won if (c["closed_on"] or "")[:7] == month),
        "win_rate": round(100 * len(won) / len(closed)) if closed else None,
        "open_count": len(open_deals),
    })


# ------------------------------------------------------------------ pipeline board
@app.get("/pipeline", response_class=HTMLResponse)
def pipeline(request: Request):
    return templates.TemplateResponse(request, "pipeline.html", {"page": "pipeline", **board_ctx()})


@app.post("/deals/{did}/move", response_class=HTMLResponse)
def move(request: Request, did: int, stage: str = Form(...)):
    if stage not in db.STAGES:
        raise HTTPException(400, "Unknown stage")
    closed = today().isoformat() if stage in ("Won", "Lost") else None
    db.execute("UPDATE deals SET stage=?, closed_on=? WHERE id=?", (stage, closed, did))
    db.execute("INSERT INTO activities (deal_id, kind, note, on_date) VALUES (?,?,?,?)",
               (did, "Stage", f"Moved to {stage}", today().isoformat()))
    return templates.TemplateResponse(request, "partials/board.html", board_ctx())


# ------------------------------------------------------------------ deal detail
@app.get("/deals/{did}", response_class=HTMLResponse)
def deal_page(request: Request, did: int):
    return templates.TemplateResponse(request, "deal.html", {
        "page": "pipeline", "d": get_deal(did),
        "acts": db.rows("SELECT * FROM activities WHERE deal_id=? ORDER BY on_date DESC, id DESC", (did,))})


@app.post("/deals/{did}/activities", response_class=HTMLResponse)
def add_activity(request: Request, did: int, kind: str = Form(...), note: str = Form(...)):
    get_deal(did)
    if not note.strip():
        raise HTTPException(400, "Note is empty")
    aid = db.execute("INSERT INTO activities (deal_id, kind, note, on_date) VALUES (?,?,?,?)",
                     (did, kind, note.strip(), today().isoformat()))
    return templates.TemplateResponse(request, "partials/activity.html",
                                      {"a": db.one("SELECT * FROM activities WHERE id=?", (aid,))})


@app.post("/deals/{did}/next-step")
def set_next_step(did: int, next_step: str = Form(""), next_step_on: str = Form("")):
    get_deal(did)
    if next_step_on:
        dt.date.fromisoformat(next_step_on)
    db.execute("UPDATE deals SET next_step=?, next_step_on=? WHERE id=?", (next_step.strip() or None, next_step_on or None, did))
    return RedirectResponse(f"/deals/{did}", status_code=303)


@app.post("/deals/{did}/draft", response_class=HTMLResponse)
def draft(request: Request, did: int, language: str = Form("English")):
    d = get_deal(did)
    acts = db.rows("SELECT * FROM activities WHERE deal_id=? ORDER BY on_date, id", (did,))
    e = ai.draft_followup(d, acts, language)
    mailto = f"mailto:{d['email'] or ''}?subject={quote(e['subject'])}&body={quote(e['body'])}"
    return templates.TemplateResponse(request, "partials/draft.html", {"e": e, "d": d, "mailto": mailto, "language": language})


# ------------------------------------------------------------------ contacts
@app.get("/contacts", response_class=HTMLResponse)
def contacts(request: Request):
    cs = db.rows("""SELECT c.*, COUNT(d.id) AS deals, COALESCE(SUM(CASE WHEN d.stage='Won' THEN d.value END),0) AS won
                    FROM contacts c LEFT JOIN deals d ON d.contact_id=c.id GROUP BY c.id ORDER BY c.created_on DESC""")
    return templates.TemplateResponse(request, "contacts.html", {
        "page": "contacts", "contacts": cs, "services": db.SERVICES, "sources": db.SOURCES,
        "soon": (today() + dt.timedelta(days=2)).isoformat()})


@app.post("/contacts")
def add_contact(name: str = Form(...), company: str = Form(...), email: str = Form(""), source: str = Form(""),
                language: str = Form("English"), title: str = Form(...), service: str = Form(...),
                value: float = Form(0), next_step_on: str = Form("")):
    t = today().isoformat()
    cid = db.execute("INSERT INTO contacts (name, company, email, source, language, created_on) VALUES (?,?,?,?,?,?)",
                     (name.strip(), company.strip(), email.strip() or None, source, language, t))
    did = db.execute("""INSERT INTO deals (contact_id, title, service, value, next_step, next_step_on, created_on)
                        VALUES (?,?,?,?,?,?,?)""", (cid, title.strip(), service, value, "First contact", next_step_on or t, t))
    return RedirectResponse(f"/deals/{did}", status_code=303)
