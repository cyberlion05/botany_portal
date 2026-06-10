"""Database models for the Botany Department site + event portal."""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

# Configurable coordinator abilities (key, human label)
COORD_PERMS = [
    ("attendance",   "Attendance desk"),
    ("tiffin",       "Tiffin desk"),
    ("roster",       "Roster"),
    ("finance",      "View finance"),
    ("announce",     "Post announcements"),
    ("student_chat", "Student chat inbox"),
]


class User(UserMixin, db.Model):
    """Admins, coordinators (event managers) and students.
    Accounts are created ONLY by the admin. No public sign-up."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    roll_number = db.Column(db.String(40))            # students / coordinators
    batch = db.Column(db.String(40))                  # e.g. "2024-2027"
    mobile = db.Column(db.String(20))                 # students: last 6 digits = password
    username = db.Column(db.String(60), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")  # admin/coordinator/student
    password_hash = db.Column(db.String(255))
    password_protected = db.Column(db.Boolean, default=True)  # admin can toggle per account
    device_token = db.Column(db.String(64))           # one-browser-one-login (non-admins)
    qr_token = db.Column(db.String(64), unique=True)
    permissions = db.Column(db.String(200))           # coordinators: comma-separated perm keys; None = all (legacy)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tiffin = db.relationship("Tiffin", backref="user", uselist=False, cascade="all, delete-orphan")
    attendance = db.relationship("Attendance", backref="user", uselist=False, cascade="all, delete-orphan")
    rsvp = db.relationship("Rsvp", backref="user", uselist=False, cascade="all, delete-orphan")

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw) if raw else None

    def check_password(self, raw):
        if not self.password_protected:
            return True
        return bool(self.password_hash) and check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_coordinator(self):
        return self.role in ("admin", "coordinator")

    @property
    def is_faculty(self):
        return self.role == "faculty"

    def has_perm(self, key):
        """Admin always allowed. Coordinators are gated by their permission list.
        permissions=None means full access (legacy / not yet configured)."""
        if self.is_admin:
            return True
        if self.role != "coordinator":
            return False
        if self.permissions is None:
            return True
        return key in self.permissions.split(",")


# ----- Site content (all admin-editable) ----------------------------------- #
class Setting(db.Model):
    """Simple key/value store: site text blocks, maintenance flag, invitation, etc."""
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text)


class Faculty(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    designation = db.Column(db.String(120))
    qualification = db.Column(db.String(200))
    specialization = db.Column(db.String(200))
    email = db.Column(db.String(120))
    photo = db.Column(db.String(200))
    sort_order = db.Column(db.Integer, default=0)


class Facility(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(10), default="\U0001F33F")
    sort_order = db.Column(db.Integer, default=0)


class Excursion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    place = db.Column(db.String(160))
    date_text = db.Column(db.String(80))
    description = db.Column(db.Text)
    photo = db.Column(db.String(200))
    sort_order = db.Column(db.Integer, default=0)


class MagazineEntry(db.Model):
    """Student magazine + wall magazine items (kind distinguishes them)."""
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), default="student")   # student / wall
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(120))
    body = db.Column(db.Text)
    image = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DeptEvent(db.Model):
    """Departmental events listed on the public site (separate from the live portal event)."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date_text = db.Column(db.String(80))
    description = db.Column(db.Text)
    photo = db.Column(db.String(200))
    sort_order = db.Column(db.Integer, default=0)


# ----- Event portal --------------------------------------------------------- #
class ProgramItem(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    start_time   = db.Column(db.String(40))          # admin-only; hidden from coordinators
    title        = db.Column(db.String(160), nullable=False)
    program_type = db.Column(db.String(120))          # Cultural / Academic / Prize Distribution…
    performer    = db.Column(db.String(200))          # who performs or presents
    prize_giver  = db.Column(db.String(200))          # who distributes prize/gift (if applicable)
    venue        = db.Column(db.String(120))
    description  = db.Column(db.Text)
    sort_order   = db.Column(db.Integer, default=0)  # doubles as serial number


class Tiffin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    choice = db.Column(db.String(10))          # accept / decline
    meal_type = db.Column(db.String(10))       # veg / nonveg
    responded_at = db.Column(db.DateTime, default=datetime.utcnow)
    collected = db.Column(db.Boolean, default=False)
    collected_at = db.Column(db.DateTime)
    collected_by = db.Column(db.String(80))    # marker name (admin-visible)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    status = db.Column(db.String(10), default="present")
    method = db.Column(db.String(10))          # qr / manual
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
    marked_by = db.Column(db.String(80))       # marker name (admin-visible)


class Rsvp(db.Model):
    """Digital invitation acceptance (required for arrangements)."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    accepted = db.Column(db.Boolean, default=False)
    responded_at = db.Column(db.DateTime, default=datetime.utcnow)


class ExpenseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)   # flowers, gifts, tiffin...
    amount = db.Column(db.Float, default=0)            # total spent on this item
    note = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Contribution(db.Model):
    """Per-head money received — visible to ADMIN ONLY."""
    id = db.Column(db.Integer, primary_key=True)
    contributor = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, default=0)
    note = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RosterTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    assignee = db.Column(db.String(120))
    completed = db.Column(db.Boolean, default=False)
    completed_by = db.Column(db.String(80))    # marker name (admin-visible)
    completed_at = db.Column(db.DateTime)
    sort_order = db.Column(db.Integer, default=0)


class Suggestion(db.Model):
    """Coordinators suggest things to the team + admin."""
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(120))
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(80))
    status = db.Column(db.String(20), default='approved')  # approved | pending | rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    name = db.Column(db.String(120))
    rating = db.Column(db.Integer)
    comments = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)


class Message(db.Model):
    """Chat messages. room='team' for team chat; 's_<uid>' for student ↔ staff."""
    id          = db.Column(db.Integer, primary_key=True)
    room        = db.Column(db.String(60), nullable=False, index=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey("user.id"))
    sender_name = db.Column(db.String(120))   # denormalized for fast display
    body        = db.Column(db.Text, nullable=False)
    sent_at     = db.Column(db.DateTime, default=datetime.utcnow, index=True)


# ── Polls ──────────────────────────────────────────────────────────────────
class Poll(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    room         = db.Column(db.String(60), nullable=False, index=True)
    question     = db.Column(db.Text, nullable=False)
    created_by   = db.Column(db.Integer, db.ForeignKey("user.id"))
    creator_name = db.Column(db.String(120))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    closed       = db.Column(db.Boolean, default=False)
    options      = db.relationship("PollOption", backref="poll",
                                   cascade="all,delete-orphan",
                                   order_by="PollOption.sort_order")
    votes        = db.relationship("PollVote", backref="poll",
                                   cascade="all,delete-orphan")


class PollOption(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    poll_id   = db.Column(db.Integer, db.ForeignKey("poll.id"), nullable=False)
    text      = db.Column(db.String(200), nullable=False)
    sort_order= db.Column(db.Integer, default=0)


class PollVote(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    poll_id   = db.Column(db.Integer, db.ForeignKey("poll.id"), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey("poll_option.id"), nullable=False)
    voter_id  = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    voted_at  = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("poll_id", "voter_id"),)


# ── Event ──────────────────────────────────────────────────────────────────
class Event(db.Model):
    """The departmental event. Only one is 'published' at a time.
    status: draft → published → completed"""
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    tagline     = db.Column(db.String(300))          # short sub-title / theme
    date        = db.Column(db.Date)
    time        = db.Column(db.Time)
    venue       = db.Column(db.String(200))
    description = db.Column(db.Text)
    status      = db.Column(db.String(20), default='draft')  # draft | published | completed
    invitation_sent  = db.Column(db.Boolean, default=False)   # admin explicitly "sends" the invite
    attendance_open  = db.Column(db.Boolean, default=False)   # admin opens/closes the check-in desk
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
