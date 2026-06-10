"""
Department of Botany, Chandernagore College — UNOFFICIAL site + Event Portal.
Roles: admin (one, you) · coordinator (event manager) · student.
Accounts are created by the admin only; everyone else just signs in.
"""
import io
import os
import re
import secrets
from datetime import datetime, date, time as dtime, timedelta

# India Standard Time offset (UTC +5:30)
# PythonAnywhere free servers run UTC; event times are entered in IST.
IST = timedelta(hours=5, minutes=30)


def _attendance_is_open(ev):
    """Return True if the attendance desk should be open right now.
    Admin toggle (ev.attendance_open) OR event datetime has arrived."""
    if not ev or ev.status != 'published':
        return False
    if ev.attendance_open:
        return True
    if ev.date and ev.time:
        event_dt = datetime.combine(ev.date, ev.time)
        return (datetime.utcnow() + IST) >= event_dt
    return False
from functools import wraps

import qrcode
from flask import (Flask, render_template, request, redirect, url_for, flash,
                   send_file, abort, session, jsonify)
from flask_login import (login_user, logout_user, login_required, current_user)
from werkzeug.utils import secure_filename

from extensions import db, login_manager, csrf
import models
from models import (User, Setting, Faculty, Facility, Excursion, MagazineEntry,
                    DeptEvent, ProgramItem, Tiffin, Attendance, Rsvp, ExpenseItem,
                    Contribution, RosterTask, Suggestion, Announcement, Photo, Feedback,
                    Message, Poll, PollOption, PollVote, Event, COORD_PERMS)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_IMG = {"png", "jpg", "jpeg", "gif", "webp"}


def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-key-change-me"),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(BASE_DIR, "instance", "botany.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # set to True automatically when served over HTTPS in production
        SESSION_COOKIE_SECURE=bool(os.environ.get("HTTPS_ONLY")),
    )
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth_login"
    csrf.init_app(app)
    register_routes(app)
    with app.app_context():
        db.create_all()
    return app


@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, int(uid))


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def setting(key, default=""):
    s = db.session.get(Setting, key)
    return s.value if s and s.value is not None else default


def set_setting(key, value):
    s = db.session.get(Setting, key) or Setting(key=key)
    s.value = value
    db.session.add(s)
    db.session.commit()


def admin_required(fn):
    @wraps(fn)
    @login_required
    def w(*a, **k):
        if not current_user.is_admin:
            abort(403)
        return fn(*a, **k)
    return w


def coordinator_required(fn):
    @wraps(fn)
    @login_required
    def w(*a, **k):
        if not current_user.is_coordinator:
            abort(403)
        return fn(*a, **k)
    return w


def perm_required(key):
    """Admin always passes; a coordinator passes only if granted this permission."""
    def deco(fn):
        @wraps(fn)
        @login_required
        def w(*a, **k):
            if current_user.is_admin or (current_user.role == "coordinator" and current_user.has_perm(key)):
                return fn(*a, **k)
            abort(403)
        return w
    return deco


def save_image(file_storage):
    if file_storage and "." in file_storage.filename:
        ext = file_storage.filename.rsplit(".", 1)[1].lower()
        if ext in ALLOWED_IMG:
            fname = f"{secrets.token_hex(8)}_{secure_filename(file_storage.filename)}"
            file_storage.save(os.path.join(UPLOAD_DIR, fname))
            return fname
    return None


# --------------------------------------------------------------------------- #
#  Routes
# --------------------------------------------------------------------------- #
def register_routes(app):

    @app.context_processor
    def inject():
        ua = request.headers.get("User-Agent", "").lower()
        mobile = bool(re.search(r"mobile|android|iphone|ipad|ipod|opera mini|iemobile|blackberry", ua))
        active_event = Event.query.filter_by(status='published').order_by(Event.date).first()
        return dict(
            DEPT="Department of Botany",
            COLLEGE="Chandernagore College",
            setting=setting,
            maintenance_on=(setting("maintenance") == "1"),
            is_mobile=mobile,
            device_type=("mobile" if mobile else "desktop"),
            active_event=active_event,
            invitation_live=(active_event is not None and active_event.invitation_sent),
            attendance_is_open=_attendance_is_open(active_event),
            now=datetime.utcnow(),
        )

    @app.before_request
    def maintenance_gate():
        if setting("maintenance") == "1":
            allowed = {"auth_login", "do_logout", "static", "event_qr_png"}
            if request.endpoint in allowed:
                return
            if current_user.is_authenticated and current_user.is_admin:
                return
            return render_template("maintenance.html"), 503

    # ---------------- Public site ---------------- #
    @app.route("/")
    def home():
        return render_template("site/home.html",
                               faculty=Faculty.query.order_by(Faculty.sort_order).limit(4).all(),
                               events=DeptEvent.query.order_by(DeptEvent.sort_order).limit(3).all())

    @app.route("/about")
    def about():
        return render_template("site/about.html")

    @app.route("/faculty")
    def faculty():
        return render_template("site/faculty.html",
                               faculty=Faculty.query.order_by(Faculty.sort_order, Faculty.id).all())

    @app.route("/facilities")
    def facilities():
        return render_template("site/facilities.html",
                               facilities=Facility.query.order_by(Facility.sort_order, Facility.id).all())

    @app.route("/excursion")
    def excursion():
        return render_template("site/excursion.html",
                               items=Excursion.query.order_by(Excursion.sort_order, Excursion.id).all())

    @app.route("/magazine")
    def magazine():
        return render_template("site/magazine.html",
                               student=MagazineEntry.query.filter_by(kind="student").order_by(MagazineEntry.created_at.desc()).all(),
                               wall=MagazineEntry.query.filter_by(kind="wall").order_by(MagazineEntry.created_at.desc()).all())

    @app.route("/events")
    def dept_events():
        return render_template("site/events.html",
                               items=DeptEvent.query.order_by(DeptEvent.sort_order, DeptEvent.id).all())

    @app.route("/invitation")
    def invitation():
        rsvp = current_user.rsvp if current_user.is_authenticated and not current_user.is_admin else None
        return render_template("site/invitation.html", rsvp=rsvp)

    @app.route("/invitation/accept", methods=["POST"])
    @login_required
    def invitation_accept():
        if current_user.is_admin:
            return redirect(url_for("invitation"))
        answer = request.form.get("answer")
        r = current_user.rsvp or Rsvp(user_id=current_user.id)
        r.accepted = (answer == "yes")
        r.responded_at = datetime.utcnow()
        db.session.add(r); db.session.commit()
        if answer == "yes":
            flash("Invitation accepted! Please choose your tiffin preference below.", "ok")
            return redirect(url_for("portal_tiffin"))
        flash("Response recorded. We hope to see you next time!", "ok")
        return redirect(url_for("invitation"))

    # ---------------- Auth ---------------- #
    @app.route("/login", methods=["GET", "POST"])
    def auth_login():
        if current_user.is_authenticated:
            return redirect(url_for("admin_dashboard") if current_user.is_admin else url_for("portal_home"))
        if request.method == "POST":
            role = request.form.get("role", "student")
            u = None
            if role == "student":
                roll = request.form.get("roll_number", "").strip()
                pw = request.form.get("password", "").strip()
                u = User.query.filter_by(roll_number=roll, role="student").first()
                if not u or not u.check_password(pw):
                    flash("Invalid roll number or password. (Password = last 6 digits of your mobile.)", "error")
                    return redirect(url_for("auth_login", role="student"))
            elif role == "faculty":
                uname = request.form.get("faculty", "").strip()
                u = User.query.filter_by(username=uname, role="faculty").first()
                if not u:
                    flash("Please select your name from the list.", "error")
                    return redirect(url_for("auth_login", role="faculty"))
            else:  # coordinator path (also used by admin, kept discreet)
                uname = request.form.get("username", "").strip()
                pw = request.form.get("password", "")
                u = User.query.filter(User.username == uname,
                                      User.role.in_(["coordinator", "admin"])).first()
                if not u or not u.check_password(pw):
                    flash("Invalid credentials.", "error")
                    return redirect(url_for("auth_login", role="coordinator"))
            # one browser, one login (non-admins)
            device_id = request.cookies.get("device_id") or secrets.token_urlsafe(16)
            if not u.is_admin:
                if not u.device_token:
                    u.device_token = device_id
                    db.session.commit()
                elif u.device_token != device_id:
                    flash("This account is already signed in on another device. Ask the admin to reset it.", "error")
                    return redirect(url_for("auth_login", role=role))
            login_user(u)
            dest = url_for("admin_dashboard") if u.is_admin else url_for("portal_home")
            resp = redirect(dest)
            resp.set_cookie("device_id", device_id, max_age=60*60*24*30, httponly=True, samesite="Lax")
            return resp
        faculty_accounts = User.query.filter_by(role="faculty").order_by(User.name).all()
        return render_template("login.html", faculty_accounts=faculty_accounts,
                               active_role=request.args.get("role", "student"))

    @app.route("/logout")
    def do_logout():
        logout_user()
        return redirect(url_for("home"))

    # ---------------- Event check-in (scan event QR -> enter roll) ---------------- #
    @app.route("/checkin", methods=["GET", "POST"])
    def checkin():
        ev = Event.query.filter_by(status='published').first()
        is_open = _attendance_is_open(ev)

        if not is_open:
            return render_template("portal/checkin.html", locked=True, event=ev)

        if request.method == "POST":
            roll = request.form.get("roll_number", "").strip()
            u = User.query.filter_by(roll_number=roll).first()
            if not u or u.role not in ("student", "coordinator"):
                flash("Roll number not recognised. Please see a coordinator.", "error")
                return redirect(url_for("checkin"))
            if not u.attendance:
                db.session.add(Attendance(user_id=u.id, status="present",
                                          method="qr", marked_by="self (QR)"))
                db.session.commit()
            return render_template("portal/greeting.html", person=u)
        return render_template("portal/checkin.html", locked=False, event=ev)

    @app.route("/event-qr.png")
    def event_qr_png():
        url = request.url_root.rstrip("/") + url_for("checkin")
        img = qrcode.make(url)
        buf = io.BytesIO(); img.save(buf, "PNG"); buf.seek(0)
        return send_file(buf, mimetype="image/png")

    # ---------------- Portal (logged-in) ---------------- #
    @app.route("/portal")
    @login_required
    def portal_home():
        if current_user.is_admin:
            return redirect(url_for("admin_dashboard"))
        if current_user.role == "coordinator":
            return redirect(url_for("coordinator_home"))
        if current_user.role == "faculty":
            return redirect(url_for("faculty_home"))
        # Student home
        announcements = (Announcement.query.filter_by(status="approved")
                         .order_by(Announcement.created_at.desc()).limit(5).all())
        unread = Message.query.filter_by(room=f"s_{current_user.id}").count()
        return render_template("portal/home.html", announcements=announcements, unread=unread)

    @app.route("/portal/coordinator")
    @coordinator_required
    def coordinator_home():
        if current_user.is_admin:
            return redirect(url_for("admin_dashboard"))
        stats = dict(
            present=Attendance.query.count(),
            tiffin_yes=Tiffin.query.filter_by(choice="accept").count(),
            roster_done=RosterTask.query.filter_by(completed=True).count(),
            roster_total=RosterTask.query.count(),
            pending=Announcement.query.filter_by(status="pending", author=current_user.name).count(),
        )
        announcements = (Announcement.query.filter_by(status="approved")
                         .order_by(Announcement.created_at.desc()).limit(3).all())
        return render_template("portal/coordinator_home.html", stats=stats,
                               announcements=announcements,
                               my_tiffin=current_user.tiffin,
                               my_attendance=current_user.attendance)

    @app.route("/portal/faculty")
    @login_required
    def faculty_home():
        if current_user.role != "faculty":
            abort(403)
        announcements = (Announcement.query.filter_by(status="approved")
                         .order_by(Announcement.created_at.desc()).limit(6).all())
        return render_template("portal/faculty_home.html",
                               rsvp=current_user.rsvp, announcements=announcements)

    @app.route("/portal/program")
    @login_required
    def portal_program():
        if current_user.role in ("student", "faculty"):
            abort(403)
        items = ProgramItem.query.order_by(ProgramItem.sort_order, ProgramItem.id).all()
        return render_template("portal/program.html", items=items,
                               show_time=current_user.is_admin,
                               enumerate=enumerate)

    @app.route("/portal/tiffin", methods=["GET", "POST"])
    @login_required
    def portal_tiffin():
        u = current_user
        if request.method == "POST":
            choice = request.form.get("choice")
            meal = request.form.get("meal_type") if choice == "accept" else None
            if choice not in ("accept", "decline") or (choice == "accept" and meal not in ("veg", "nonveg")):
                flash("Please complete your tiffin choice.", "error")
                return redirect(url_for("portal_tiffin"))
            t = u.tiffin or Tiffin(user_id=u.id)
            t.choice, t.meal_type, t.responded_at = choice, meal, datetime.utcnow()
            db.session.add(t); db.session.commit()
            flash("Your tiffin preference is saved.", "ok")
            return redirect(url_for("portal_home"))
        return render_template("portal/tiffin.html", tiffin=u.tiffin)

    @app.route("/portal/suggestions", methods=["GET", "POST"])
    @coordinator_required
    def portal_suggestions():
        if request.method == "POST":
            body = request.form.get("body", "").strip()
            if body:
                db.session.add(Suggestion(author=current_user.name, body=body))
                db.session.commit()
                flash("Suggestion shared with the team.", "ok")
            return redirect(url_for("portal_suggestions"))
        items = Suggestion.query.order_by(Suggestion.created_at.desc()).all()
        return render_template("portal/suggestions.html", items=items)

    @app.route("/portal/expenses")
    @perm_required('finance')
    def portal_expenses():
        items = ExpenseItem.query.order_by(ExpenseItem.created_at).all()
        total_spent = sum(i.amount for i in items)
        all_contributions = Contribution.query.order_by(Contribution.created_at).all()
        total_received = sum(c.amount for c in all_contributions)
        contrib_public = setting("contributions_public") == "1"
        # Show individual contributions to admin always; to coordinator only when toggle is on
        contributions = all_contributions if (current_user.is_admin or contrib_public) else []
        return render_template("portal/expenses.html", items=items, total_spent=total_spent,
                               total_received=total_received, balance=total_received - total_spent,
                               contributions=contributions, contrib_public=contrib_public,
                               heads=len(all_contributions))

    @app.route("/portal/feedback", methods=["GET", "POST"])
    @login_required
    def portal_feedback():
        if request.method == "POST":
            try:
                rating = int(request.form.get("rating", 0))
            except ValueError:
                rating = 0
            db.session.add(Feedback(user_id=current_user.id, name=current_user.name,
                                    rating=rating, comments=request.form.get("comments", "").strip()))
            db.session.commit()
            flash("Thanks for your feedback!", "ok")
            return redirect(url_for("portal_home"))
        return render_template("portal/feedback.html")

    @app.route("/my-account", methods=["GET", "POST"])
    @login_required
    def my_account():
        u = current_user
        if request.method == "POST":
            action = request.form.get("action")
            if action == "username":
                new_username = request.form.get("new_username", "").strip()
                if not new_username:
                    flash("Username cannot be empty.", "error")
                elif new_username != u.username and User.query.filter_by(username=new_username).first():
                    flash("That username is already taken.", "error")
                else:
                    old = u.username
                    u.username = new_username
                    db.session.commit()
                    flash(f"Username changed from '{old}' to '{new_username}'.", "ok")
            elif action == "password":
                current_pw = request.form.get("current_password", "")
                new_pw = request.form.get("new_password", "").strip()
                confirm_pw = request.form.get("confirm_password", "").strip()
                if u.password_protected and not u.check_password(current_pw):
                    flash("Current password is incorrect.", "error")
                elif len(new_pw) < 6:
                    flash("New password must be at least 6 characters.", "error")
                elif new_pw != confirm_pw:
                    flash("Passwords don't match.", "error")
                else:
                    u.set_password(new_pw)
                    u.password_protected = True
                    db.session.commit()
                    flash("Password updated successfully.", "ok")
            return redirect(url_for("my_account"))
        return render_template("my_account.html")

    @app.route("/gallery")
    def gallery():
        return render_template("site/gallery.html",
                               photos=Photo.query.order_by(Photo.uploaded_at.desc()).all())

    @app.route("/announcements")
    def announcements():
        return render_template("site/announcements.html",
                               items=Announcement.query.filter_by(status='approved')
                                     .order_by(Announcement.created_at.desc()).all())

    @app.route("/portal/post-announcement", methods=["GET", "POST"])
    @login_required
    def portal_post_announcement():
        # Students blocked; coordinators need announce perm; faculty + admin always allowed
        if current_user.role == "student":
            abort(403)
        if current_user.role == "coordinator" and not current_user.has_perm("announce"):
            abort(403)
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            body  = request.form.get("body",  "").strip()
            if not title or not body:
                flash("Title and body are required.", "error")
            else:
                # Admin + faculty → live immediately; coordinator → pending approval
                status = "approved" if (current_user.is_admin or current_user.role == "faculty") else "pending"
                db.session.add(Announcement(title=title, body=body,
                                            author=current_user.name, status=status))
                db.session.commit()
                flash("Announcement published." if status == "approved"
                      else "Submitted — goes live once admin approves it.", "ok")
            return redirect(url_for("portal_post_announcement"))
        my_posts = (Announcement.query.filter_by(author=current_user.name)
                    .order_by(Announcement.created_at.desc()).all())
        return render_template("portal/post_announcement.html", my_posts=my_posts)

    # ── Chat: shared send + poll endpoints ────────────────────────────── #
    def _check_room_access(room):
        """Validate that current_user may access this chat room. Returns True or aborts."""
        if room == "team":
            if not current_user.is_coordinator:
                abort(403)
        elif room.startswith("s_"):
            try:
                uid = int(room[2:])
            except ValueError:
                abort(400)
            if current_user.role == "student" and current_user.id != uid:
                abort(403)
            if current_user.role == "faculty":
                abort(403)
            if current_user.role == "coordinator" and not current_user.has_perm("student_chat"):
                abort(403)
        else:
            abort(400)
        return True

    def _build_timeline(msgs, polls):
        """Merge messages and polls sorted by creation time."""
        items = [("msg",  m, m.sent_at)    for m in msgs]  + \
                [("poll", p, p.created_at) for p in polls]
        items.sort(key=lambda x: x[2])
        return [(kind, obj) for kind, obj, _ in items]

    def _poll_data(polls, user_id, is_admin):
        """Return {poll_id: dict} with precomputed vote counts for templates."""
        data = {}
        for p in polls:
            all_votes = p.votes
            total = len(all_votes)
            my_vote_opt = next((v.option_id for v in all_votes if v.voter_id == user_id), None)
            counts = {}
            for v in all_votes:
                counts[v.option_id] = counts.get(v.option_id, 0) + 1
            data[p.id] = {
                "total":    total,
                "my_vote":  my_vote_opt,
                "counts":   counts,
                "can_close": (p.created_by == user_id or is_admin) and not p.closed,
            }
        return data

    def _poll_to_json(p, user_id, is_admin):
        all_votes = p.votes
        total = len(all_votes)
        my_vote_opt = next((v.option_id for v in all_votes if v.voter_id == user_id), None)
        counts = {}
        for v in all_votes:
            counts[v.option_id] = counts.get(v.option_id, 0) + 1
        return {
            "id":           p.id,
            "question":     p.question,
            "creator":      p.creator_name,
            "closed":       p.closed,
            "total":        total,
            "my_vote":      my_vote_opt,
            "can_close":    (p.created_by == user_id or is_admin) and not p.closed,
            "options": [{
                "id":    o.id,
                "text":  o.text,
                "votes": counts.get(o.id, 0),
            } for o in p.options],
        }

    @app.route("/chat/send", methods=["POST"])
    @login_required
    def chat_send():
        room = request.form.get("room", "").strip()
        body = request.form.get("body", "").strip()
        _check_room_access(room)
        if body:
            db.session.add(Message(room=room, sender_id=current_user.id,
                                   sender_name=current_user.name, body=body))
            db.session.commit()
        return jsonify(ok=True)

    @app.route("/chat/poll")
    @login_required
    def chat_poll():
        room         = request.args.get("room", "")
        since_id     = request.args.get("since",      0, type=int)
        since_poll   = request.args.get("since_poll", 0, type=int)
        _check_room_access(room)
        new_msgs = (Message.query.filter_by(room=room)
                    .filter(Message.id > since_id)
                    .order_by(Message.sent_at).all())
        new_polls = (Poll.query.filter_by(room=room)
                     .filter(Poll.id > since_poll)
                     .order_by(Poll.created_at).all())
        active_polls = Poll.query.filter_by(room=room, closed=False).all()
        uid  = current_user.id
        adm  = current_user.is_admin
        return jsonify(
            messages=[{
                "id": m.id, "name": m.sender_name, "body": m.body,
                "time": m.sent_at.strftime("%H:%M"), "mine": m.sender_id == uid,
            } for m in new_msgs],
            new_polls  =[_poll_to_json(p, uid, adm) for p in new_polls],
            active_polls=[_poll_to_json(p, uid, adm) for p in active_polls],
        )

    # ── Poll CRUD ──────────────────────────────────────────────────── #
    @app.route("/chat/poll/create", methods=["POST"])
    @login_required
    def chat_create_poll():
        room = request.form.get("room", "").strip()
        _check_room_access(room)
        if current_user.role == "student":
            abort(403)   # students can vote but not create
        question = request.form.get("question", "").strip()
        options  = [v.strip() for v in request.form.getlist("options[]") if v.strip()]
        if not question or len(options) < 2:
            return jsonify(error="Need a question and at least 2 options"), 400
        poll = Poll(room=room, question=question,
                    created_by=current_user.id, creator_name=current_user.name)
        db.session.add(poll)
        db.session.flush()
        for i, opt_text in enumerate(options[:6]):
            db.session.add(PollOption(poll_id=poll.id, text=opt_text, sort_order=i))
        db.session.commit()
        return jsonify(ok=True, poll_id=poll.id)

    @app.route("/chat/poll/<int:pid>/vote", methods=["POST"])
    @login_required
    def chat_vote_poll(pid):
        poll = db.session.get(Poll, pid)
        if not poll or poll.closed:
            return jsonify(error="This poll is closed."), 400
        _check_room_access(poll.room)
        if PollVote.query.filter_by(poll_id=pid, voter_id=current_user.id).first():
            return jsonify(error="You have already voted."), 400
        option_id = request.form.get("option_id", type=int)
        opt = db.session.get(PollOption, option_id)
        if not opt or opt.poll_id != pid:
            return jsonify(error="Invalid option."), 400
        db.session.add(PollVote(poll_id=pid, option_id=option_id,
                                voter_id=current_user.id))
        db.session.commit()
        return jsonify(ok=True, poll=_poll_to_json(poll, current_user.id, current_user.is_admin))

    @app.route("/chat/poll/<int:pid>/close", methods=["POST"])
    @login_required
    def chat_close_poll(pid):
        poll = db.session.get(Poll, pid)
        if not poll:
            abort(404)
        if poll.created_by != current_user.id and not current_user.is_admin:
            abort(403)
        poll.closed = True
        db.session.commit()
        return jsonify(ok=True)

    # ── Phase 6: Team chat ─────────────────────────────────────────── #
    @app.route("/chat/team")
    @coordinator_required
    def chat_team():
        msgs  = Message.query.filter_by(room="team").order_by(Message.sent_at).all()
        polls = Poll.query.filter_by(room="team").order_by(Poll.created_at).all()
        timeline = _build_timeline(msgs, polls)
        pd   = _poll_data(polls, current_user.id, current_user.is_admin)
        last_msg_id  = msgs[-1].id  if msgs  else 0
        last_poll_id = polls[-1].id if polls else 0
        return render_template("chat/team.html", timeline=timeline, poll_data=pd,
                               room="team", last_msg_id=last_msg_id,
                               last_poll_id=last_poll_id)

    # ── Phase 7: Student ↔ staff chat ─────────────────────────────── #
    @app.route("/chat/student")
    @login_required
    def chat_student():
        if current_user.role not in ("student",):
            abort(403)
        room  = f"s_{current_user.id}"
        msgs  = Message.query.filter_by(room=room).order_by(Message.sent_at).all()
        polls = Poll.query.filter_by(room=room).order_by(Poll.created_at).all()
        timeline = _build_timeline(msgs, polls)
        pd   = _poll_data(polls, current_user.id, current_user.is_admin)
        return render_template("chat/student.html", timeline=timeline, poll_data=pd,
                               room=room,
                               last_msg_id=msgs[-1].id   if msgs  else 0,
                               last_poll_id=polls[-1].id if polls else 0)

    @app.route("/admin/chats")
    @perm_required("student_chat")
    def admin_chats():
        students = User.query.filter_by(role="student").order_by(User.name).all()
        last_msgs = {}
        for s in students:
            last_msgs[s.id] = (Message.query.filter_by(room=f"s_{s.id}")
                               .order_by(Message.sent_at.desc()).first())
        return render_template("admin/chats.html", students=students, last_msgs=last_msgs)

    @app.route("/admin/chats/<int:uid>")
    @perm_required("student_chat")
    def admin_chat_student(uid):
        student = db.session.get(User, uid)
        if not student or student.role != "student":
            abort(404)
        room  = f"s_{uid}"
        msgs  = Message.query.filter_by(room=room).order_by(Message.sent_at).all()
        polls = Poll.query.filter_by(room=room).order_by(Poll.created_at).all()
        timeline = _build_timeline(msgs, polls)
        pd   = _poll_data(polls, current_user.id, current_user.is_admin)
        return render_template("admin/chat_student.html", student=student,
                               timeline=timeline, poll_data=pd, room=room,
                               last_msg_id=msgs[-1].id   if msgs  else 0,
                               last_poll_id=polls[-1].id if polls else 0)

    register_admin_routes(app)


# --------------------------------------------------------------------------- #
#  Admin routes (split out for readability)
# --------------------------------------------------------------------------- #
def register_admin_routes(app):

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        people = User.query.filter(User.role.in_(["student", "coordinator"])).all()
        total = len(people)
        stats = dict(
            total=total,
            faculty=User.query.filter_by(role="faculty").count(),
            present=Attendance.query.count(),
            accepted=Tiffin.query.filter_by(choice="accept").count(),
            collected=Tiffin.query.filter_by(collected=True).count(),
            veg=Tiffin.query.filter_by(choice="accept", meal_type="veg").count(),
            nonveg=Tiffin.query.filter_by(choice="accept", meal_type="nonveg").count(),
            rsvp_yes=Rsvp.query.filter_by(accepted=True).count(),
            received=sum(c.amount for c in Contribution.query.all()),
            spent=sum(e.amount for e in ExpenseItem.query.all()),
            heads=Contribution.query.count(),
        )
        stats["balance"] = stats["received"] - stats["spent"]
        stats["per_head"] = round(stats["received"] / stats["heads"], 2) if stats["heads"] else 0
        return render_template("admin/dashboard.html", stats=stats)

    @app.route("/admin/event", methods=["GET", "POST"])
    @admin_required
    def admin_event():
        if request.method == "POST":
            f = request.form
            try:
                evt_date = date.fromisoformat(f.get("date")) if f.get("date") else None
                evt_time = dtime.fromisoformat(f.get("time")) if f.get("time") else None
            except ValueError:
                flash("Invalid date or time format.", "error")
                return redirect(url_for("admin_event"))
            ev = Event(
                name=f.get("name", "").strip(),
                tagline=f.get("tagline", "").strip(),
                date=evt_date, time=evt_time,
                venue=f.get("venue", "").strip(),
                description=f.get("description", "").strip(),
                status="draft",
            )
            db.session.add(ev); db.session.commit()
            flash(f"Event '{ev.name}' created as draft.", "ok")
            return redirect(url_for("admin_event"))
        events = Event.query.order_by(Event.created_at.desc()).all()
        return render_template("admin/event.html", events=events)

    @app.route("/admin/event/<int:eid>/edit", methods=["GET", "POST"])
    @admin_required
    def admin_edit_event(eid):
        ev = db.session.get(Event, eid)
        if not ev: abort(404)
        if request.method == "POST":
            f = request.form
            try:
                ev.date = date.fromisoformat(f.get("date")) if f.get("date") else None
                ev.time = dtime.fromisoformat(f.get("time")) if f.get("time") else None
            except ValueError:
                flash("Invalid date or time.", "error")
                return redirect(url_for("admin_edit_event", eid=eid))
            ev.name        = f.get("name", "").strip()
            ev.tagline     = f.get("tagline", "").strip()
            ev.venue       = f.get("venue", "").strip()
            ev.description = f.get("description", "").strip()
            db.session.commit()
            flash("Event updated.", "ok")
            return redirect(url_for("admin_event"))
        return render_template("admin/event_edit.html", ev=ev)

    @app.route("/admin/event/<int:eid>/publish", methods=["POST"])
    @admin_required
    def admin_publish_event(eid):
        ev = db.session.get(Event, eid)
        if not ev: abort(404)
        # Archive any currently published event
        Event.query.filter_by(status='published').update({"status": "completed"})
        ev.status = "published"
        db.session.commit()
        flash(f"'{ev.name}' is now published — event details are visible to all.", "ok")
        return redirect(url_for("admin_event"))

    @app.route("/admin/event/<int:eid>/send-invitation", methods=["POST"])
    @admin_required
    def admin_send_invitation(eid):
        ev = db.session.get(Event, eid)
        if not ev: abort(404)
        if ev.status != "published":
            flash("Publish the event first before sending the invitation.", "error")
            return redirect(url_for("admin_event"))
        ev.invitation_sent = True
        db.session.commit()
        flash("Invitation sent — it's now prominently visible on everyone's dashboard.", "ok")
        return redirect(url_for("admin_event"))

    @app.route("/admin/event/<int:eid>/recall-invitation", methods=["POST"])
    @admin_required
    def admin_recall_invitation(eid):
        ev = db.session.get(Event, eid)
        if ev:
            ev.invitation_sent = False; db.session.commit()
            flash("Invitation recalled.", "ok")
        return redirect(url_for("admin_event"))

    @app.route("/admin/event/<int:eid>/complete", methods=["POST"])
    @admin_required
    def admin_complete_event(eid):
        ev = db.session.get(Event, eid)
        if ev:
            ev.status = "completed"; db.session.commit()
            flash(f"'{ev.name}' marked as completed.", "ok")
        return redirect(url_for("admin_event"))

    @app.route("/admin/event/<int:eid>/draft", methods=["POST"])
    @admin_required
    def admin_draft_event(eid):
        ev = db.session.get(Event, eid)
        if ev:
            ev.status = "draft"; ev.invitation_sent = False
            db.session.commit()
            flash("Event moved back to draft.", "ok")
        return redirect(url_for("admin_event"))

    @app.route("/admin/event/<int:eid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_event(eid):
        ev = db.session.get(Event, eid)
        if ev and ev.status == "draft":
            db.session.delete(ev); db.session.commit()
            flash("Draft event deleted.", "ok")
        else:
            flash("Only draft events can be deleted.", "error")
        return redirect(url_for("admin_event"))

    @app.route("/admin/rsvp")
    @admin_required
    def admin_rsvp():
        people = (User.query.filter(User.role.in_(["faculty", "coordinator", "student"]))
                  .order_by(User.role, User.name).all())
        accepted = sum(1 for p in people if p.rsvp and p.rsvp.accepted)
        declined = sum(1 for p in people if p.rsvp and p.rsvp.responded_at and not p.rsvp.accepted)
        return render_template("admin/rsvp.html", people=people,
                               accepted=accepted, declined=declined,
                               pending=len(people) - accepted - declined)

    @app.route("/admin/permissions", methods=["GET", "POST"])
    @admin_required
    def admin_permissions():
        if request.method == "POST":
            cid = request.form.get("coordinator_id")
            c = db.session.get(User, int(cid)) if cid and cid.isdigit() else None
            if c and c.role == "coordinator":
                granted = [k for k, _ in COORD_PERMS if request.form.get("perm_" + k) == "on"]
                c.permissions = ",".join(granted)
                db.session.commit()
                flash(f"Permissions updated for {c.name}.", "ok")
            return redirect(url_for("admin_permissions"))
        coordinators = User.query.filter_by(role="coordinator").order_by(User.name).all()
        return render_template("admin/permissions.html", coordinators=coordinators, perms=COORD_PERMS)

    @app.route("/admin/event/toggle-attendance", methods=["POST"])
    @admin_required
    def admin_toggle_attendance():
        ev = Event.query.filter_by(status='published').first()
        if ev:
            ev.attendance_open = not ev.attendance_open
            db.session.commit()
            state = "OPEN — students can now check in via QR." if ev.attendance_open \
                    else "closed — students will see a countdown."
            flash(f"Attendance desk {state}", "ok")
        else:
            flash("No published event found.", "error")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/maintenance", methods=["POST"])
    @admin_required
    def admin_maintenance():
        new = "0" if setting("maintenance") == "1" else "1"
        set_setting("maintenance", new)
        flash("Maintenance mode " + ("ENABLED — only you can use the site now." if new == "1"
                                      else "disabled — site is live again."), "ok")
        return redirect(url_for("admin_dashboard"))

    # ----- Users ----- #
    @app.route("/admin/users")
    @admin_required
    def admin_users():
        users = User.query.order_by(User.role, User.name).all()
        return render_template("admin/users.html", users=users)

    @app.route("/admin/users/add", methods=["POST"])
    @admin_required
    def admin_add_user():
        f = request.form
        name = f.get("name", "").strip()
        role = f.get("role") if f.get("role") in ("student", "coordinator", "faculty") else "student"

        if role == "student":
            roll = f.get("roll_number", "").strip()
            mobile = "".join(ch for ch in f.get("mobile", "") if ch.isdigit())
            if not name or not roll or len(mobile) < 6:
                flash("A student needs a name, roll number and a valid mobile number (at least 6 digits).", "error")
            elif User.query.filter_by(username=roll).first() or User.query.filter_by(roll_number=roll, role="student").first():
                flash("A student with that roll number already exists.", "error")
            else:
                u = User(name=name, roll_number=roll, batch=f.get("batch", "").strip(),
                         username=roll, role="student", mobile=mobile,
                         password_protected=True, qr_token=secrets.token_urlsafe(12))
                u.set_password(mobile[-6:])
                db.session.add(u); db.session.commit()
                flash(f"Student {name} created. They sign in with roll '{roll}' and the last 6 digits of their mobile.", "ok")

        elif role == "faculty":
            username = name  # faculty sign in by selecting their name
            if not name:
                flash("Faculty name is required.", "error")
            elif User.query.filter_by(username=username).first():
                flash("A faculty member with that name already exists.", "error")
            else:
                u = User(name=name, username=username, role="faculty",
                         password_protected=False, qr_token=secrets.token_urlsafe(12))
                db.session.add(u); db.session.commit()
                flash(f"Faculty {name} created — they sign in by selecting their name (no password).", "ok")

        else:  # coordinator
            username = f.get("username", "").strip()
            if not name or not username:
                flash("A coordinator needs a name and a username.", "error")
            elif User.query.filter_by(username=username).first():
                flash("That username is already taken.", "error")
            else:
                protected = f.get("password_protected") == "on"
                u = User(name=name, roll_number=f.get("roll_number", "").strip(),
                         batch=f.get("batch", "").strip(), username=username, role="coordinator",
                         password_protected=protected, qr_token=secrets.token_urlsafe(12),
                         permissions=",".join(k for k, _ in COORD_PERMS))
                if protected:
                    u.set_password(f.get("password", "") or secrets.token_urlsafe(6))
                db.session.add(u); db.session.commit()
                flash(f"Coordinator {name} created (username: {username}).", "ok")
        return redirect(url_for("admin_users"))

    @app.route("/admin/faculty/<int:fid>/edit", methods=["GET", "POST"])
    @admin_required
    def admin_edit_faculty(fid):
        f = db.session.get(Faculty, fid)
        if not f:
            abort(404)
        if request.method == "POST":
            f.name          = request.form.get("name", "").strip()
            f.designation   = request.form.get("designation", "").strip()
            f.qualification = request.form.get("qualification", "").strip()
            f.specialization= request.form.get("specialization", "").strip()  # Area of Interest
            f.email         = request.form.get("email", "").strip()
            f.sort_order    = int(request.form.get("sort_order") or 0)
            new_photo = save_image(request.files.get("photo"))
            if new_photo:
                f.photo = new_photo
            db.session.commit()
            flash(f"{f.name} updated.", "ok")
            return redirect(url_for("admin_faculty"))
        return render_template("admin/faculty_edit.html", faculty=f)

    @app.route("/admin/users/<int:uid>/update", methods=["POST"])
    @admin_required
    def admin_update_user(uid):
        u = db.session.get(User, uid)
        if not u or u.is_admin:
            return redirect(url_for("admin_users"))
        name = request.form.get("name", "").strip()
        if name:
            u.name = name
        if u.role == "student":
            roll = request.form.get("roll_number", "").strip()
            if roll and roll != u.roll_number:
                if User.query.filter(User.roll_number == roll, User.id != uid).first():
                    flash("That roll number is already used.", "error")
                    return redirect(url_for("admin_users"))
                u.roll_number = roll
                u.username    = roll          # username = roll for students
            u.batch = request.form.get("batch", "").strip() or u.batch
            mobile = "".join(ch for ch in request.form.get("mobile", "") if ch.isdigit())
            if len(mobile) >= 6:
                u.mobile = mobile
                u.set_password(mobile[-6:])
                u.password_protected = True
        elif u.role == "coordinator":
            roll = request.form.get("roll_number", "").strip()
            new_username = request.form.get("username", "").strip()
            if new_username and new_username != u.username:
                if User.query.filter(User.username == new_username, User.id != uid).first():
                    flash("That username is already taken.", "error")
                    return redirect(url_for("admin_users"))
                u.username = new_username
            if roll:
                u.roll_number = roll
            u.batch = request.form.get("batch", "").strip() or u.batch
            u.password_protected = request.form.get("password_protected") == "on"
            pw = request.form.get("password", "")
            if pw:
                u.set_password(pw)
            if not u.password_protected:
                u.password_hash = None
        elif u.role == "faculty":
            if name and name != u.username:
                if User.query.filter(User.username == name, User.id != uid).first():
                    flash("A faculty with that name already exists.", "error")
                    return redirect(url_for("admin_users"))
                u.username = name          # faculty login = their name
        db.session.commit()
        flash(f"Updated {u.name}.", "ok")
        return redirect(url_for("admin_users"))

    @app.route("/admin/users/<int:uid>/reset_device", methods=["POST"])
    @admin_required
    def admin_reset_device(uid):
        u = db.session.get(User, uid)
        if u:
            u.device_token = None; db.session.commit()
            flash(f"{u.name} can sign in on a new device now.", "ok")
        return redirect(url_for("admin_users"))

    @app.route("/admin/users/<int:uid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_user(uid):
        u = db.session.get(User, uid)
        if u and not u.is_admin:
            db.session.delete(u); db.session.commit()
            flash("Account removed.", "ok")
        return redirect(url_for("admin_users"))

    # ----- Site content editor ----- #
    @app.route("/admin/content", methods=["GET", "POST"])
    @admin_required
    def admin_content():
        keys = ["about_title", "about_body", "about_hod", "facilities_intro",
                "excursion_intro", "invitation_title", "invitation_body", "footer_note"]
        if request.method == "POST":
            for k in keys:
                set_setting(k, request.form.get(k, ""))
            flash("Content updated. Changes are live.", "ok")
            return redirect(url_for("admin_content"))
        return render_template("admin/content.html", keys=keys)

    # ----- Faculty ----- #
    @app.route("/admin/faculty", methods=["GET", "POST"])
    @admin_required
    def admin_faculty():
        if request.method == "POST":
            db.session.add(Faculty(
                name=request.form.get("name", "").strip(),
                designation=request.form.get("designation", "").strip(),
                qualification=request.form.get("qualification", "").strip(),
                specialization=request.form.get("specialization", "").strip(),
                email=request.form.get("email", "").strip(),
                photo=save_image(request.files.get("photo")),
                sort_order=int(request.form.get("sort_order") or 0)))
            db.session.commit(); flash("Faculty added.", "ok")
            return redirect(url_for("admin_faculty"))
        return render_template("admin/faculty.html",
                               faculty=Faculty.query.order_by(Faculty.sort_order, Faculty.id).all())

    @app.route("/admin/faculty/<int:fid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_faculty(fid):
        f = db.session.get(Faculty, fid)
        if f:
            db.session.delete(f); db.session.commit()
        return redirect(url_for("admin_faculty"))

    # ----- Facilities ----- #
    @app.route("/admin/facilities", methods=["GET", "POST"])
    @admin_required
    def admin_facilities():
        if request.method == "POST":
            db.session.add(Facility(title=request.form.get("title", "").strip(),
                                    description=request.form.get("description", "").strip(),
                                    icon=request.form.get("icon", "").strip() or "\U0001F33F",
                                    sort_order=int(request.form.get("sort_order") or 0)))
            db.session.commit(); flash("Facility added.", "ok")
            return redirect(url_for("admin_facilities"))
        return render_template("admin/facilities.html",
                               facilities=Facility.query.order_by(Facility.sort_order, Facility.id).all())

    @app.route("/admin/facilities/<int:fid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_facility(fid):
        x = db.session.get(Facility, fid)
        if x:
            db.session.delete(x); db.session.commit()
        return redirect(url_for("admin_facilities"))

    # ----- Excursion ----- #
    @app.route("/admin/excursion", methods=["GET", "POST"])
    @admin_required
    def admin_excursion():
        if request.method == "POST":
            db.session.add(Excursion(title=request.form.get("title", "").strip(),
                                     place=request.form.get("place", "").strip(),
                                     date_text=request.form.get("date_text", "").strip(),
                                     description=request.form.get("description", "").strip(),
                                     photo=save_image(request.files.get("photo")),
                                     sort_order=int(request.form.get("sort_order") or 0)))
            db.session.commit(); flash("Excursion added.", "ok")
            return redirect(url_for("admin_excursion"))
        return render_template("admin/excursion.html",
                               items=Excursion.query.order_by(Excursion.sort_order, Excursion.id).all())

    @app.route("/admin/excursion/<int:xid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_excursion(xid):
        x = db.session.get(Excursion, xid)
        if x:
            db.session.delete(x); db.session.commit()
        return redirect(url_for("admin_excursion"))

    # ----- Magazine ----- #
    @app.route("/admin/magazine", methods=["GET", "POST"])
    @admin_required
    def admin_magazine():
        if request.method == "POST":
            db.session.add(MagazineEntry(kind=request.form.get("kind", "student"),
                                         title=request.form.get("title", "").strip(),
                                         author=request.form.get("author", "").strip(),
                                         body=request.form.get("body", "").strip(),
                                         image=save_image(request.files.get("image"))))
            db.session.commit(); flash("Magazine entry added.", "ok")
            return redirect(url_for("admin_magazine"))
        return render_template("admin/magazine.html",
                               items=MagazineEntry.query.order_by(MagazineEntry.created_at.desc()).all())

    @app.route("/admin/magazine/<int:mid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_magazine(mid):
        m = db.session.get(MagazineEntry, mid)
        if m:
            db.session.delete(m); db.session.commit()
        return redirect(url_for("admin_magazine"))

    # ----- Dept events ----- #
    @app.route("/admin/dept-events", methods=["GET", "POST"])
    @admin_required
    def admin_dept_events():
        if request.method == "POST":
            db.session.add(DeptEvent(title=request.form.get("title", "").strip(),
                                     date_text=request.form.get("date_text", "").strip(),
                                     description=request.form.get("description", "").strip(),
                                     photo=save_image(request.files.get("photo")),
                                     sort_order=int(request.form.get("sort_order") or 0)))
            db.session.commit(); flash("Event added.", "ok")
            return redirect(url_for("admin_dept_events"))
        return render_template("admin/dept_events.html",
                               items=DeptEvent.query.order_by(DeptEvent.sort_order, DeptEvent.id).all())

    @app.route("/admin/dept-events/<int:eid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_dept_event(eid):
        e = db.session.get(DeptEvent, eid)
        if e:
            db.session.delete(e); db.session.commit()
        return redirect(url_for("admin_dept_events"))

    # ----- Program ----- #
    @app.route("/admin/program", methods=["GET", "POST"])
    @admin_required
    def admin_program():
        if request.method == "POST":
            db.session.add(ProgramItem(
                start_time=request.form.get("start_time", "").strip(),
                title=request.form.get("title", "").strip(),
                program_type=request.form.get("program_type", "").strip(),
                performer=request.form.get("performer", "").strip(),
                prize_giver=request.form.get("prize_giver", "").strip(),
                venue=request.form.get("venue", "").strip(),
                description=request.form.get("description", "").strip(),
                sort_order=int(request.form.get("sort_order") or 0)))
            db.session.commit(); flash("Program item added.", "ok")
            return redirect(url_for("admin_program"))
        return render_template("admin/program.html",
                               items=ProgramItem.query.order_by(ProgramItem.sort_order, ProgramItem.id).all())

    @app.route("/admin/program/<int:pid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_program(pid):
        it = db.session.get(ProgramItem, pid)
        if it:
            db.session.delete(it); db.session.commit()
        return redirect(url_for("admin_program"))

    # ----- Attendance (admin + coordinator) ----- #
    @app.route("/portal/attendance")
    @perm_required('attendance')
    def manage_attendance():
        people = User.query.filter(User.role.in_(["student", "coordinator"])).order_by(User.name).all()
        return render_template("admin/attendance.html", people=people,
                               qr_url=url_for("checkin", _external=True))

    @app.route("/portal/attendance/<int:uid>/toggle", methods=["POST"])
    @perm_required('attendance')
    def toggle_attendance(uid):
        u = db.session.get(User, uid)
        if u:
            if u.attendance:
                db.session.delete(u.attendance)
            else:
                db.session.add(Attendance(user_id=u.id, status="present",
                                          method="manual", marked_by=current_user.name))
            db.session.commit()
        return redirect(url_for("manage_attendance"))

    # ----- Tiffin collection (present-before-tiffin rule) ----- #
    @app.route("/portal/tiffin-desk")
    @perm_required('tiffin')
    def tiffin_desk():
        rows = (db.session.query(User, Tiffin).join(Tiffin, Tiffin.user_id == User.id)
                .filter(Tiffin.choice == "accept").order_by(User.name).all())
        return render_template("admin/tiffin_desk.html", rows=rows)

    @app.route("/portal/tiffin-desk/<int:uid>/collect", methods=["POST"])
    @perm_required('tiffin')
    def collect_tiffin(uid):
        u = db.session.get(User, uid)
        also_present = request.form.get("also_present") == "1"
        if u and u.tiffin:
            present = Attendance.query.filter_by(user_id=u.id).first()
            if not present and also_present:
                present = Attendance(user_id=u.id, status="present",
                                     method="manual", marked_by=current_user.name)
                db.session.add(present)
            if not present:
                flash(f"{u.name} is not marked present yet — an absent student can't collect tiffin. "
                      "Mark them present first.", "error")
                return redirect(url_for("tiffin_desk"))
            t = u.tiffin
            t.collected = not t.collected
            t.collected_at = datetime.utcnow() if t.collected else None
            t.collected_by = current_user.name if t.collected else None
            db.session.commit()
        return redirect(url_for("tiffin_desk"))

    # ----- Roster ----- #
    @app.route("/portal/roster", methods=["GET", "POST"])
    @perm_required('roster')
    def roster():
        if request.method == "POST" and current_user.is_admin:
            db.session.add(RosterTask(title=request.form.get("title", "").strip(),
                                      assignee=request.form.get("assignee", "").strip(),
                                      sort_order=int(request.form.get("sort_order") or 0)))
            db.session.commit(); flash("Task added.", "ok")
            return redirect(url_for("roster"))
        return render_template("admin/roster.html",
                               tasks=RosterTask.query.order_by(RosterTask.sort_order, RosterTask.id).all())

    @app.route("/portal/roster/<int:tid>/toggle", methods=["POST"])
    @perm_required('roster')
    def toggle_roster(tid):
        t = db.session.get(RosterTask, tid)
        if t:
            t.completed = not t.completed
            t.completed_by = current_user.name if t.completed else None
            t.completed_at = datetime.utcnow() if t.completed else None
            db.session.commit()
        return redirect(url_for("roster"))

    @app.route("/portal/roster/<int:tid>/delete", methods=["POST"])
    @admin_required
    def delete_roster(tid):
        t = db.session.get(RosterTask, tid)
        if t:
            db.session.delete(t); db.session.commit()
        return redirect(url_for("roster"))

    # ----- Expenses & contributions (admin) ----- #
    @app.route("/admin/finance", methods=["GET", "POST"])
    @admin_required
    def admin_finance():
        if request.method == "POST":
            kind = request.form.get("kind")
            if kind == "expense":
                db.session.add(ExpenseItem(name=request.form.get("name", "").strip(),
                                           amount=float(request.form.get("amount") or 0),
                                           note=request.form.get("note", "").strip()))
            elif kind == "contribution":
                db.session.add(Contribution(contributor=request.form.get("contributor", "").strip(),
                                            amount=float(request.form.get("amount") or 0),
                                            note=request.form.get("note", "").strip()))
            db.session.commit(); flash("Saved.", "ok")
            return redirect(url_for("admin_finance"))
        expenses = ExpenseItem.query.order_by(ExpenseItem.created_at).all()
        contributions = Contribution.query.order_by(Contribution.created_at).all()
        spent = sum(e.amount for e in expenses)
        received = sum(c.amount for c in contributions)
        return render_template("admin/finance.html", expenses=expenses, contributions=contributions,
                               spent=spent, received=received, balance=received - spent,
                               per_head=round(received / len(contributions), 2) if contributions else 0)

    @app.route("/admin/finance/expense/<int:eid>/delete", methods=["POST"])
    @admin_required
    def delete_expense(eid):
        e = db.session.get(ExpenseItem, eid)
        if e:
            db.session.delete(e); db.session.commit()
        return redirect(url_for("admin_finance"))

    @app.route("/admin/finance/contribution/<int:cid>/delete", methods=["POST"])
    @admin_required
    def delete_contribution(cid):
        c = db.session.get(Contribution, cid)
        if c:
            db.session.delete(c); db.session.commit()
        return redirect(url_for("admin_finance"))

    # ----- Announcements ----- #
    @app.route("/admin/announcements", methods=["GET", "POST"])
    @admin_required
    def admin_announcements():
        if request.method == "POST":
            db.session.add(Announcement(title=request.form.get("title", "").strip(),
                                        body=request.form.get("body", "").strip(),
                                        author=current_user.name, status='approved'))
            db.session.commit(); flash("Announcement published.", "ok")
            return redirect(url_for("admin_announcements"))
        approved = Announcement.query.filter_by(status='approved').order_by(Announcement.created_at.desc()).all()
        pending  = Announcement.query.filter_by(status='pending').order_by(Announcement.created_at.asc()).all()
        rejected = Announcement.query.filter_by(status='rejected').order_by(Announcement.created_at.desc()).all()
        return render_template("admin/announcements.html",
                               approved=approved, pending=pending, rejected=rejected)

    @app.route("/admin/announcements/<int:aid>/approve", methods=["POST"])
    @admin_required
    def admin_approve_announcement(aid):
        a = db.session.get(Announcement, aid)
        if a:
            a.status = 'approved'; db.session.commit()
            flash(f"'{a.title}' approved and published.", "ok")
        return redirect(url_for("admin_announcements"))

    @app.route("/admin/announcements/<int:aid>/reject", methods=["POST"])
    @admin_required
    def admin_reject_announcement(aid):
        a = db.session.get(Announcement, aid)
        if a:
            a.status = 'rejected'; db.session.commit()
            flash(f"'{a.title}' rejected.", "ok")
        return redirect(url_for("admin_announcements"))

    @app.route("/admin/finance/toggle-contributions", methods=["POST"])
    @admin_required
    def toggle_contributions_public():
        new = "0" if setting("contributions_public") == "1" else "1"
        set_setting("contributions_public", new)
        flash("Contributor visibility " + (
            "set to PUBLIC — coordinators can now see individual amounts." if new == "1"
            else "back to ADMIN ONLY."), "ok")
        return redirect(url_for("admin_finance"))

    @app.route("/admin/announcements/<int:aid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_announcement(aid):
        a = db.session.get(Announcement, aid)
        if a:
            db.session.delete(a); db.session.commit()
        return redirect(url_for("admin_announcements"))

    # ----- Gallery ----- #
    @app.route("/admin/gallery", methods=["GET", "POST"])
    @admin_required
    def admin_gallery():
        if request.method == "POST":
            fname = save_image(request.files.get("photo"))
            if fname:
                db.session.add(Photo(filename=fname, caption=request.form.get("caption", "").strip()))
                db.session.commit(); flash("Photo uploaded.", "ok")
            else:
                flash("Please choose a valid image.", "error")
            return redirect(url_for("admin_gallery"))
        return render_template("admin/gallery.html",
                               photos=Photo.query.order_by(Photo.uploaded_at.desc()).all())

    @app.route("/admin/gallery/<int:pid>/delete", methods=["POST"])
    @admin_required
    def admin_delete_photo(pid):
        p = db.session.get(Photo, pid)
        if p:
            try:
                os.remove(os.path.join(UPLOAD_DIR, p.filename))
            except OSError:
                pass
            db.session.delete(p); db.session.commit()
        return redirect(url_for("admin_gallery"))

    # ----- Feedback + suggestions view ----- #
    @app.route("/admin/feedback")
    @admin_required
    def admin_feedback():
        return render_template("admin/feedback.html",
                               items=Feedback.query.order_by(Feedback.submitted_at.desc()).all(),
                               suggestions=Suggestion.query.order_by(Suggestion.created_at.desc()).all())


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
