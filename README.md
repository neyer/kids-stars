# Star Tracker

A small Django app for tracking kids' star balances. Pick a kid from the home
screen to see their ledger, then add or remove stars with a quick-action
button or the manual form.

## Setup (already done, for reference)

```bash
source /home/mark/venvs/personal/bin/activate
pip install django
python3 manage.py migrate
```

`migrate` also seeds three default kids (Allie, Paul, Charlotte) and a few
quick actions (dinner on time, bedtime routine, screen time violation, etc.)
via a data migration, so you shouldn't need to create them by hand.

## Running the app

```bash
cd /home/mark/src/kids-stars
source /home/mark/venvs/personal/bin/activate
python3 manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

## Admin site

To add/edit kids or quick actions directly, create a superuser once:

```bash
python3 manage.py createsuperuser
```

Then log in at http://127.0.0.1:8000/admin/.

## Data

Everything is stored in `db.sqlite3` in the project root (SQLite).
