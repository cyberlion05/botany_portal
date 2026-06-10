"""
Seed the database with the single admin account + sample content.

Run once:   python seed.py
The admin username/password come from environment variables if set,
otherwise the safe defaults below (CHANGE THEM before going live).
"""
import os
import secrets
from app import app
from extensions import db
from models import (User, Setting, Faculty, Facility, Excursion, ProgramItem,
                    DeptEvent)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "botany_admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeMe@2026")


def s(key, value):
    row = db.session.get(Setting, key) or Setting(key=key)
    row.value = value
    db.session.add(row)


with app.app_context():
    db.drop_all()
    db.create_all()

    # ---- the one admin (you) ----
    admin = User(name="Department Admin", username=ADMIN_USERNAME, role="admin",
                 password_protected=True, qr_token=secrets.token_urlsafe(12))
    admin.set_password(ADMIN_PASSWORD)
    db.session.add(admin)

    # ---- a couple of sample accounts so you can try the portal ----
    coord = User(name="Riya Coordinator", roll_number="BOT24-COORD", batch="2024-2027",
                 username="riya", role="coordinator", password_protected=True,
                 permissions="attendance,tiffin,roster,finance,announce,student_chat",
                 qr_token=secrets.token_urlsafe(12))
    coord.set_password("riya123")
    stud = User(name="Arjun Das", roll_number="BOT24-014", batch="2024-2027",
                username="BOT24-014", role="student", mobile="9876543210",
                password_protected=True, qr_token=secrets.token_urlsafe(12))
    stud.set_password("543210")  # last 6 digits of the mobile number
    # Faculty sign in with their NAME ONLY (no roll number, no password by default)
    prof = User(name="Dr. Brij Kumar Tiwary", username="Dr. Brij Kumar Tiwary", role="faculty",
                password_protected=False, qr_token=secrets.token_urlsafe(12))
    db.session.add_all([coord, stud, prof])

    # ---- editable site text (real, verified facts; prose paraphrased) ----
    s("about_title", "About the Department")
    s("about_body",
      "The Department of Botany is one of the science departments of Chandernagore "
      "College, Chandannagar. The teaching of Biology at the college began in 1961 "
      "with the I.Sc. course; it was upgraded to the B.Sc. course in 1981, and the "
      "Honours course in Botany was introduced in 1994.\n\n"
      "Today the department brings together a mix of experienced and younger faculty "
      "working across different areas of plant science, supported by a sound "
      "infrastructure of laboratories and teaching resources.\n\n"
      "Chandernagore College itself was established in 1862 (re-established in 1931) "
      "and is a constituent college of the University of Burdwan, accredited A+ (3.46) "
      "in the 3rd cycle of NAAC. (Admin: edit any of this from Dashboard → Content.)")
    s("about_hod", "Head of the Department: Dr. Brij Kumar Tiwary (Assistant Professor).")
    s("facilities_intro",
      "The department is equipped for hands-on learning in plant science, with "
      "laboratory and teaching facilities supporting B.Sc. and Honours studies.")
    s("excursion_intro",
      "Field excursions are an important part of studying plants in their natural "
      "habitat, taking students beyond the classroom into the field.")
    s("invitation_title", "Annual Botany Fest 2026")
    s("invitation_body", "The Department of Botany cordially invites all faculty and students "
                         "to our annual celebration. Date, time and venue to be announced.")
    s("footer_note",
      "A student-run, unofficial portal for the Department of Botany, Chandernagore College. "
      "Campus: Strand Road, Bara Bazar, Chandannagar, Hooghly, West Bengal 712136.")
    s("maintenance", "0")

    # ---- faculty: verified HOD + clearly-marked slots for you to complete ----
    db.session.add(Faculty(name="Dr. Brij Kumar Tiwary", designation="Assistant Professor & Head of the Department",
                           specialization="", sort_order=0))
    for i, (n, d) in enumerate([
        ("[Add faculty name]", "Assistant Professor"),
        ("[Add faculty name]", "Assistant Professor / SACT"),
        ("[Add faculty name]", "Assistant Professor / SACT"),
    ], start=1):
        db.session.add(Faculty(name=n, designation=d, specialization="", sort_order=i))

    # ---- sample facilities ----
    for i, (ic, t, dsc) in enumerate([
        ("🔬", "Laboratories", "Well-equipped practical labs for microscopy and physiology."),
        ("🌿", "Herbarium", "A collection of preserved plant specimens for study."),
        ("🪴", "Departmental Garden", "Living plant collection used for teaching."),
        ("📚", "Seminar Library", "Reference books and journals for botany students."),
    ]):
        db.session.add(Facility(icon=ic, title=t, description=dsc, sort_order=i))

    # ---- sample program ----
    for i, (tm, t, pt, perf, pg, v) in enumerate([
        ("10:00 AM", "Inauguration & welcome", "Academic",        "HOD & Guests",          "",                  "Seminar Hall"),
        ("11:00 AM", "Guest lecture",          "Academic",        "Invited Speaker",        "",                  "Seminar Hall"),
        ("12:30 PM", "Prize distribution",     "Prize Distribution","Faculty Committee",    "HOD",               "Seminar Hall"),
        ("01:00 PM", "Lunch / tiffin",         "Break",           "",                       "",                  "Department Lawn"),
        ("02:30 PM", "Cultural programme",     "Cultural",        "Students of Dept. Botany","",                 "Auditorium"),
    ]):
        db.session.add(ProgramItem(start_time=tm, title=t, program_type=pt,
                                   performer=perf, prize_giver=pg, venue=v, sort_order=i))

    db.session.add(DeptEvent(title="Annual Botany Fest", date_text="2026",
                             description="The department's flagship annual event.", sort_order=0))
    db.session.add(Excursion(title="Botanical field excursion", place="To be added",
                             date_text="", description="Add your department's excursion details and photos here.",
                             sort_order=0))
    # Sample event (draft — admin publishes it when ready)
    from models import Event
    from datetime import date, time as dtime
    db.session.add(Event(
        name="Annual Botany Fest 2026",
        tagline="Roots & Shoots",
        date=date(2026, 8, 15),
        time=dtime(10, 0),
        venue="Seminar Hall, Chandernagore College",
        description="The annual celebration of the Department of Botany.",
        status="draft",
    ))

    db.session.commit()
    print("=" * 56)
    print(" Seeded the Botany portal.")
    print(f"  ADMIN  → username: {ADMIN_USERNAME}   password: {ADMIN_PASSWORD}")
    print("  COORD  → username: riya    password: riya123")
    print("  STUDENT→ roll: BOT24-014   password: 543210  (last 6 of mobile 9876543210)")
    print("  FACULTY→ sign in with name: Dr. Brij Kumar Tiwary  (no password)")
    print("  Sample roll numbers for QR check-in: BOT24-014, BOT24-COORD")
    print("  ** CHANGE THE ADMIN PASSWORD before hosting! **")
    print("=" * 56)
