# InFlow

> *Map your thinking. Draw it once.*

A small Django CRUD app for making flowcharts as a family tree. Type a node, give it a shape, and the layout sorts itself.

## What it does

InFlow is a flowchart maker built around one idea: most flows have a shape — top to bottom, parent to child, branching when there's a decision. That shape is a tree, and a tree doesn't need to be hand-positioned.

- **Flowcharts** — a container for one diagram (you can have many)
- **Nodes** — a single shape in the flow, with a parent and any number of children
- **Shapes** — Process (rounded rect), Decision (diamond), Start / End (pill), Input / Output (parallelogram), Data (skewed corners), Note (dashed)
- **Branch labels** — short text on the connector from a parent to a child ("Yes" / "No" out of a decision, for example)
- **Drag to reparent** — drop any node onto another to make it a child; drop on the canvas top to make it a root
- **Tags** — a shared catalog for cross-cutting labels (Approval, Manual step, Risk, …)
- **Soft archive** — set a flowchart aside without deleting it

## What's notable

- **Family-tree layout** — branches stay readable as the flow grows; no canvas wrangling.
- **Inline "+ Add child"** — click the little chip under any node, type a label, pick a shape, done.
- **Edit-trail per node** — every change is logged so you can see when something moved.
- **Starter flow on signup** — new accounts get a tiny example flowchart so the editor isn't empty on first login.

## Built with

- **Python 3.12** + **Django**
- **PostgreSQL** (SQLite fallback for first-run dev)
- **django-environ** + **python-dotenv** for env vars
- **WhiteNoise** for static file serving in production
- **gunicorn** as the production WSGI server
- **dj-database-url** for Heroku Postgres connection parsing
- Plain Django templates, vanilla CSS (Grid + Flexbox), Inter + Fraunces from Google Fonts
- Hand-rolled SVG illustrations
- Tiny vanilla-JS drag-and-drop on the flowchart canvas (no front-end framework)

## Project layout

```
InFlow/
├── manage.py
├── Pipfile
├── Procfile
├── inflow/                 # project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── main_app/               # the actual app
    ├── models.py           # Flowchart, Node, NodeLog, Tag
    ├── views.py
    ├── forms.py
    ├── urls.py
    ├── admin.py
    ├── static/
    │   ├── css/base.css
    │   └── images/         # SVG illustrations
    └── templates/
        ├── base.html
        ├── home.html
        ├── about.html
        ├── flowcharts/     # index, detail, _node partial
        ├── main_app/       # form & confirm_delete templates (CBV convention)
        └── registration/   # login, signup
```

## Data model

```
User ─┬── Flowchart ── Node ──┬── Node (parent self-ref)
      │                       ├── NodeLog (history)
      │                       └── Tag (M2M, shared catalog)
      └── ...
```

- One `User` owns many `Flowchart`s.
- Each `Flowchart` contains many `Node`s.
- `Node.parent` points to another `Node` in the same flowchart (so a tree grows).
- `NodeLog` records each rename / reparent / shape change.
- `Tag` is a flat, shared catalog across all users.

## Authorization model

- All flowchart, node, and tag CRUD requires login.
- Flowcharts and nodes are scoped per-user: you can only see, edit, or delete your own.
- Tags are a shared catalog (any logged-in user can read all tags and add new ones).
- Guests can see the marketing home page, the About page, and the auth screens.

## Running locally

```bash
pipenv install
pipenv shell
python manage.py migrate
python manage.py runserver
```

The dev server runs at http://127.0.0.1:8000/. With no DB env vars set, SQLite is used and a `db.sqlite3` file is created in the project root.

## Attributions

- **Inter** typeface by Rasmus Andersson — [Google Fonts](https://fonts.google.com/specimen/Inter)
- **Fraunces** typeface by Phaedra Charles, Lasse Fister & Travis Kochel — [Google Fonts](https://fonts.google.com/specimen/Fraunces)
- All illustrations are hand-authored SVG (no third-party clip art).
