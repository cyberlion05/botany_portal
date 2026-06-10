# 🌿 Department of Botany — Chandernagore College (Unofficial Portal)

A student-built, **unofficial** website for the Department of Botany with a full
**event-management portal** built in. Every page carries a disclaimer that the
College has no control over the site.

> This is **v1 for your review**. Run it, click around, and send feedback — some
> features are intentionally simple so you can tell me what to expand.

---

## What's inside

**Public website** (anyone can view)
- Home, About the Department, Faculty, Facilities, Excursion, Student & Wall Magazine,
  Departmental Events, Gallery, Announcements
- Digital **Invitation** page with **RSVP** (accept / decline — marked as required)
- Botanical "herbarium" theme: forest greens + parchment, falling-leaf animation,
  scroll reveals

**Event portal** (sign-in required)
- **Roles:** `admin` (you — one account, secured) · `coordinator` (event manager) · `student`
- **No public sign-up.** The admin creates every account; people only sign in.
- Program plan · Tiffin accept/decline + veg/non-veg · Feedback
- **Coordinators can:** suggest ideas to the team, mark attendance if the QR fails,
  run the tiffin desk, tick roster tasks
- **Attendance QR:** one event QR → student scans → enters roll number → name is
  verified → "take a seat" greeting + marked present
- **Tiffin rule enforced:** a student must be *present* to collect tiffin; an absent
  student can be marked present and given tiffin in one click (coordinator/admin)
- **Expenses:** everyone sees the total per item (flowers, gifts, tiffin…); **per-head
  contributions are visible to the admin only**; dashboard shows received vs spent vs balance
- **Roster:** task checklist with completed/not marking
- **Audit:** every marking records *who* did it — shown to the **admin only**
- **Maintenance mode:** one click in the dashboard; while on, only the admin can use the site

**Security**
- Passwords hashed (Werkzeug); session cookies HTTP-only + SameSite
- CSRF protection on every form (Flask-WTF)
- One-browser-one-login device lock for students/coordinators, with admin "reset device"
- Per-account toggle: password-protected **or** not (admin's choice). Admin is always protected.

---

## Tools you need

- **Python 3.12** and **pip** (this is the only must-have)
- Python packages (installed automatically from `requirements.txt`):
  Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, qrcode, Pillow, gunicorn
- **VS Code** + the **Claude Code** extension (you already have this) to run/extend it
- A free **GitHub** account + a free host account (see below) for going live
- No paid services, no API keys required.

---

## Run it locally (VS Code)

```bash
# 1. install dependencies
pip install -r requirements.txt

# 2. create the database + sample data (also prints the logins)
python seed.py

# 3. start the site
python app.py
```

Open **http://localhost:5000**.

**Sample logins** (from `seed.py`):
| Role | Username | Password |
|------|----------|----------|
| Admin | `botany_admin` | `ChangeMe@2026` |
| Coordinator | `riya` | `riya123` |
| Student | `arjun` | *(none — password-free account demo)* |

Sample roll numbers for the QR check-in: **BOT24-014**, **BOT24-COORD**.

> **Change the admin password before hosting.** Either edit `seed.py`, or set
> environment variables `ADMIN_USERNAME` and `ADMIN_PASSWORD` before running it.

---

## Host it for FREE

The app is a standard Flask app, so any free Python host works. Two good options:

### Option A — PythonAnywhere (recommended: free **and** your data persists)
1. Make a free account at pythonanywhere.com.
2. Upload the project (or pull from GitHub in a Bash console).
3. `pip install --user -r requirements.txt`, then `python seed.py` once.
4. Add a **Web app → Manual config (Flask)**, point the WSGI file to `wsgi.py`
   (`from app import app as application`).
5. Set the env var `SECRET_KEY` (any long random string) and `HTTPS_ONLY=1`.
6. Reload. You get `https://<you>.pythonanywhere.com` with working HTTPS (needed for
   QR scanning) and the SQLite file stays put.

### Option B — Render.com (easy deploys from GitHub)
- Push to GitHub → New **Web Service** → Build: `pip install -r requirements.txt`,
  Start: `gunicorn app:app`. Add env vars `SECRET_KEY` and `HTTPS_ONLY=1`.
- ⚠️ The free tier sleeps when idle and its disk is **ephemeral**, so the SQLite
  database can reset. Fine for a demo; for a real event, use PythonAnywhere, or I can
  switch the app to a free Postgres database (Neon/Supabase) so data is permanent.

Uploaded photos are saved to `static/uploads/` — on hosts with ephemeral disks those
reset too; tell me if you want uploads moved to free cloud storage.

---

## "Real-time" updates

Data is saved to the database and shows for everyone on their next page load/refresh.
True live-push (no refresh) needs WebSockets, which is heavier and not always free —
say the word if you want it for, e.g., the live attendance count.

---

## Notes / assumptions I made (tell me to change any)

1. **Faculty accounts:** faculty sign in with their **name only** (no roll number; no
   password unless you add one). Admin creates them on the Accounts page by typing the
   name and choosing the Faculty role. Faculty can accept the invitation (RSVP); see all
   responses under Admin → **RSVPs**.
2. **Password optional** is a per-account toggle the admin controls (admin is always protected).
3. **Attendance** uses a single event QR + roll-number entry (as you described), plus
   manual marking when the QR fails.
4. **Expenses** = item totals for everyone; **contributions** (per head) = admin-only.
5. I did **not** copy text/photos from the college website — sections use editable
   placeholders for you to fill from the admin panel.

## Project layout
```
botany_portal/
├── app.py            # routes + factory + maintenance gate
├── models.py         # database models
├── extensions.py     # db / login / csrf
├── seed.py           # creates admin + sample data
├── wsgi.py           # for PythonAnywhere / gunicorn
├── requirements.txt
├── templates/        # site/  portal/  admin/
└── static/           # css, js, uploads
```
