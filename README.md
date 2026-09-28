# 🤝 LeadDesk — a small CRM for a freelance service business

> **All data is synthetic.** Contacts and companies are fictional sample data; emails use the reserved `example.com` domain. Any resemblance to real businesses or people is coincidental.

A CRM (Customer Relationship Management system) keeps track of **who your customers are, which deals are in progress, and who to follow up with**. Big CRMs are built for sales teams. LeadDesk is built for one person running a small service business — and it's the CRM I use for my own freelance work.

| Page | What it does |
|---|---|
| ✅ **Follow-ups** | What's overdue, what's coming this week, deals that have **gone quiet for 14+ days**, and open deals with **no next step**. Plus pipeline value, expected value, won this month and win rate. |
| 📋 **Pipeline** | A board with every deal by stage (New lead → Contacted → Call booked → Quote sent → Won / Lost). Change a stage from the card; the move is logged. |
| 💼 **Deal page** | Next step + date, a full history of calls, emails and meetings, and an **AI follow-up email writer in English or Farsi**. |
| 👥 **Contacts** | Everyone you've talked to, where they came from, and what they're worth. |

## Design choices
- **Built around the follow-up.** Most small-business deals are lost to a forgotten follow-up, not to a competitor, so the home page is a to-do list, not a chart.
- **Expected value, not wishful value.** Open deals are weighted by stage (a quote sent is more likely than a new lead).
- **AI writes, you send.** The AI drafts from the deal's real history; you edit it and send it from your own email. It never sends anything itself.
- **Bilingual.** Drafts in natural Farsi for Persian-speaking clients, shown right-to-left.
- **Works without AI.** If Ollama isn't running, you get a clear template instead of an error.

## Tech
**FastAPI + HTMX** (server-rendered HTML, no JavaScript framework) · Jinja2 · SQLite · Ollama (Qwen 2.5, local) · pytest

## Run it
```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```
Open **http://127.0.0.1:8000**. The database and sample data are created on first run in `data/`.
**To use it for real (empty, no sample data):** delete the `data/` folder, then start it with sample data turned off:
```powershell
$env:LEADDESK_SEED="0"; python -m uvicorn app.main:app --reload
```
Your real data stays in `data/`, which is git-ignored, so it's never uploaded to GitHub.

For AI drafts, install [Ollama](https://ollama.com) and run `ollama pull qwen2.5:7b`.

## Tests
```bash
pytest -q
```
6 tests: pages load, follow-up detection (overdue and quiet deals), stage moves with history, adding a lead, adding an activity, and AI drafting with the template fallback.
