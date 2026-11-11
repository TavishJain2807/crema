# Contributing to Crema

Thanks for taking a look. Crema is a small personal project, so the bar for changes is mostly: keep it small, keep it readable, and do not add a build step.

## Ground rules

- **No frameworks or bundlers.** The frontend is plain HTML, CSS, and vanilla JavaScript in `static/`. Keep it that way.
- **No new services.** The app must keep running with Flask, SQLite, and the filesystem. No Redis, no external database, no cloud APIs.
- **Preserve the look.** The design is deliberately quiet: warm paper tones, serif headings, restrained motion. Match the existing tokens in `static/styles.css` rather than introducing a new palette.
- **Mobile first.** Test at 390 × 844 as well as desktop widths.

## Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export COFFEE_DATA_DIR="$PWD/data"
python app.py
```

The app is at <http://127.0.0.1:8787>. `python app.py` uses Flask's development server; do not use it in production.

## Before opening a pull request

1. `python -m unittest discover -s tests -v`
2. `node --check static/app.js`
3. Click through the flow you changed at phone and desktop widths.
4. If you changed the database schema, add an idempotent migration in `ensure_db()` and confirm an existing database still opens.
5. If you changed the PDF, regenerate the sample and check that pages do not clip or strand a single shot.

## Reporting bugs

Include:

- what you expected and what happened;
- browser and OS (or that it was the API);
- whether the app was installed as a PWA;
- any console or server output.

Never paste your database, photos, session cookies, or real email addresses. Redact them.

## Security

Please do not open a public issue for a security problem. See [`SECURITY.md`](SECURITY.md).
