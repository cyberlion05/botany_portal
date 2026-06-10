# Deploy the Botany Portal on PythonAnywhere (free, exact steps)

You do NOT need Python on your own computer for this. Everything runs in the cloud.
Replace **YOURUSERNAME** everywhere with your PythonAnywhere username.

---

## 1. Make an account
Sign up for a free **"Beginner"** account at https://www.pythonanywhere.com

## 2. Upload the code
- Top right → **Files**.
- Under "Files" in your home directory, click **Upload a file** and upload `botany_portal.zip`.

## 3. Unzip + install (Bash console)
- Top menu → **Consoles** → **Bash**. Run these one at a time:

```bash
unzip botany_portal.zip
ls /usr/bin/python3.*          # see which Python versions exist (pick 3.11 if listed)
mkvirtualenv --python=/usr/bin/python3.11 botenv
cd botany_portal
pip install -r requirements.txt
```

(The virtualenv `botenv` activates automatically — your prompt shows `(botenv)`.)

## 4. Create the database + your secret admin login
Choose a private username and a strong password, then seed ONCE:

```bash
export ADMIN_USERNAME='your_private_admin_name'
export ADMIN_PASSWORD='YourStrong!Password123'
python seed.py
```

It prints the sample logins. Your admin login is what you typed above — keep it confidential.
⚠️ Run `seed.py` only this once. Re-running it ERASES all data. (Future updates won't need it.)

## 5. Create the web app
- Top menu → **Web** → **Add a new web app** → **Next**.
- Choose **Manual configuration** (NOT "Flask"). → choose **Python 3.11** (match step 3) → **Next**.

Now on the web app's configuration page, set:

- **Source code:** `/home/YOURUSERNAME/botany_portal`
- **Working directory:** `/home/YOURUSERNAME/botany_portal`
- **Virtualenv:** type `botenv` (it expands to `/home/YOURUSERNAME/.virtualenvs/botenv`)

### WSGI file
Click the **WSGI configuration file** link (looks like `/var/www/YOURUSERNAME_pythonanywhere_com_wsgi.py`).
Delete everything in it and paste exactly this (edit the username + secret string):

```python
import os, sys

project_home = '/home/YOURUSERNAME/botany_portal'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# A long random string — keeps logins valid across reloads. Change it once, then leave it.
os.environ['SECRET_KEY'] = 'paste-a-long-random-string-here-aaaa1111bbbb2222'
os.environ['HTTPS_ONLY'] = '1'

from app import app as application
```

Save it.

### Static files (recommended, faster)
On the web app page, under **Static files**, add:
- URL: `/static/`
- Directory: `/home/YOURUSERNAME/botany_portal/static`

### Force HTTPS
Under **Security**, turn **Force HTTPS** = ON (needed for the attendance QR and secure cookies).

## 6. Go live
- Click the big green **Reload** button.
- Visit **https://YOURUSERNAME.pythonanywhere.com**
- Sign in with the admin username/password from step 4.

Done — your site is on the free internet. 🎉

---

## Keeping it running
Free web apps ask you to click **"Run until 3 months from today"** on the Web tab every ~3 months. One click keeps it alive.

## Redeploying after each feature phase
1. Upload the changed files (overwrite) in the **Files** tab, OR use git if you set it up.
2. If a phase changes the database structure, I'll give you a tiny one-time **migration** command to run in the Bash console (it adds the new fields WITHOUT erasing your data).
3. Click **Reload** on the Web tab.

Never re-run `seed.py` on the live site after step 4 — it wipes everything.

## If something breaks
- Web tab → **Error log** / **Server log** links show what went wrong.
- Most common: a typo in the WSGI file path, or the virtualenv name not matching.
