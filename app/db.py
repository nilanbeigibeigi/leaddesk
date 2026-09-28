"""SQLite storage for LeadDesk. All seed data is fictional (emails use the reserved example.com domain)."""
import datetime as dt
import os
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("LEADDESK_DB", os.path.join(os.path.dirname(HERE), "data", "leaddesk.db"))

STAGES = ["New lead", "Contacted", "Call booked", "Quote sent", "Won", "Lost"]
OPEN_STAGES = STAGES[:4]
PROBABILITY = {"New lead": .1, "Contacted": .2, "Call booked": .4, "Quote sent": .6, "Won": 1, "Lost": 0}
SERVICES = ["Website", "AI tool", "Finance & data", "Care plan"]
SOURCES = ["Referral", "Instagram", "Google", "Walk-in", "Website form", "Community event"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, company TEXT NOT NULL, email TEXT, source TEXT,
  language TEXT NOT NULL DEFAULT 'English', created_on TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS deals (
  id INTEGER PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES contacts(id), title TEXT NOT NULL,
  service TEXT NOT NULL, value REAL NOT NULL DEFAULT 0, stage TEXT NOT NULL DEFAULT 'New lead',
  next_step TEXT, next_step_on TEXT, created_on TEXT NOT NULL, closed_on TEXT);
CREATE TABLE IF NOT EXISTS activities (
  id INTEGER PRIMARY KEY, deal_id INTEGER NOT NULL REFERENCES deals(id), kind TEXT NOT NULL,
  note TEXT NOT NULL, on_date TEXT NOT NULL);
"""


def conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def rows(sql, params=()):
    with conn() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def one(sql, params=()):
    r = rows(sql, params)
    return r[0] if r else None


def execute(sql, params=()):
    with conn() as c:
        return c.execute(sql, params).lastrowid


def init(seed=None):
    if seed is None:
        seed = os.environ.get("LEADDESK_SEED", "1") != "0"
    with conn() as c:
        c.executescript(SCHEMA)
        empty = c.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 0
    if seed and empty:
        _seed()


def _seed():
    t = dt.date.today()
    d = lambda n: (t + dt.timedelta(days=n)).isoformat()
    contacts = [
        ("Leila Karimi", "Golestan Café (sample)", "leila@example.com", "Community event", "Farsi", d(-40)),
        ("Mark Chen", "Northside Auto Repair (sample)", "mark@example.com", "Google", "English", d(-30)),
        ("Shirin Ahmadi", "Rose Hair Studio (sample)", "shirin@example.com", "Instagram", "Farsi", d(-21)),
        ("Dr. Hana Park", "Bright Smile Dental (sample)", "office@example.com", "Referral", "English", d(-18)),
        ("Reza Mohammadi", "Tehran Bakery (sample)", "reza@example.com", "Walk-in", "Farsi", d(-12)),
        ("Olivia Grant", "Grant Renovations (sample)", "olivia@example.com", "Website form", "English", d(-6)),
        ("Kian Farahani", "Kian Imports (sample)", "kian@example.com", "Referral", "Farsi", d(-50)),
        ("Sam Patel", "Patel Accounting (sample)", "sam@example.com", "Google", "English", d(-60)),
    ]
    deals = [  # contact_id, title, service, value, stage, next_step, next_step_on, created, closed
        (1, "Bilingual café website + online menu", "Website", 1400, "Quote sent", "Follow up on quote", d(-3), d(-35), None),
        (2, "Booking page for service appointments", "Website", 1200, "Call booked", "Discovery call", d(1), d(-28), None),
        (3, "Instagram booking + AI chatbot", "AI tool", 800, "Contacted", "Send examples of chatbots", d(-6), d(-20), None),
        (4, "Monthly patient-volume dashboard", "Finance & data", 900, "New lead", "First call", d(0), d(-17), None),
        (5, "Sales & waste dashboard", "Finance & data", 600, "Quote sent", "Answer question about Excel", d(2), d(-11), None),
        (6, "Daily site report system", "AI tool", 2500, "New lead", "Reply to website form", d(-1), d(-6), None),
        (7, "Import invoice checking", "Finance & data", 900, "Won", None, None, d(-48), d(-20)),
        (7, "Website care plan", "Care plan", 588, "Won", None, None, d(-20), d(-19)),
        (8, "Client portal website", "Website", 2000, "Lost", None, None, d(-58), d(-30)),
    ]
    acts = [
        (1, "Meeting", "Met Leila at a community event. Wants a Farsi/English menu site; unhappy with current PDF menu.", d(-35)),
        (1, "Email", "Sent quote: $1,400 for 5-page bilingual site with menu. She'll discuss with her partner.", d(-10)),
        (2, "Call", "Mark gets 20+ calls a day just to book oil changes. Wants online booking.", d(-25)),
        (3, "Instagram", "Shirin asked if a chatbot can answer price questions in DMs and on the website.", d(-19)),
        (5, "Visit", "Reza tracks sales in a notebook; throws away bread daily. Wants to see what sells.", d(-11)),
        (5, "Email", "Sent quote for $600 dashboard. He asked if he must use Excel.", d(-4)),
        (7, "Note", "Invoice checker delivered. Kian very happy; referred Sam Patel.", d(-20)),
        (9, "Note", "Went with a bigger agency; budget was fine but wanted a team.", d(-30)),
    ]
    with conn() as c:
        c.executemany("INSERT INTO contacts (name, company, email, source, language, created_on) VALUES (?,?,?,?,?,?)", contacts)
        c.executemany("""INSERT INTO deals (contact_id, title, service, value, stage, next_step, next_step_on, created_on, closed_on)
                         VALUES (?,?,?,?,?,?,?,?,?)""", deals)
        c.executemany("INSERT INTO activities (deal_id, kind, note, on_date) VALUES (?,?,?,?)", acts)
