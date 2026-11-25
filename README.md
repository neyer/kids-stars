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

## Parents and kids

Any logged-in account that isn't linked to a kid is a **parent**: parents can
add and remove stars, use the Quick tap page, and approve requests.

To give a kid their own login:

```bash
python3 manage.py create_kid_login Allie allie   # prompts for a password
```

Run it again to reset the password. Kids land on their own page, where they can
ask for stars for a listed activity (any positive quick action) or a custom
one. Requests show up on the **Requests** page (with a count in the header) and
on the kid's page; stars are only added once a parent approves.

## REST API

Other apps can read balances and add or remove stars. Each app needs a token:

```bash
python3 manage.py create_api_token "Home Assistant"
```

The key is printed once and only a hash is stored. Tokens can also be created,
and revoked (untick "active"), in the admin under **Api tokens**.

Send the key on every request as `Authorization: Bearer <key>`. A kid can be
referred to by id or by name (case-insensitive).

| Method   | Path                          | What it does |
|----------|-------------------------------|--------------|
| `GET`    | `/api/kids/`                  | All kids with `balance` and `pending_stars` (requested, not yet approved) |
| `GET`    | `/api/kids/<kid>/`            | One kid, with recent transactions (`?limit=50`, max 500) |
| `POST`   | `/api/kids/<kid>/stars/`      | Add stars: `{"delta": 3, "reason": "Read a book"}`; a negative delta removes them |
| `DELETE` | `/api/transactions/<id>/`     | Undo a transaction |

```bash
curl -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
     -d '{"delta": 1, "reason": "Practiced piano"}' \
     http://127.0.0.1:8000/api/kids/allie/stars/
```

Errors come back as `{"error": "..."}` with status 400, 401, 404 or 405.
