import os
import re
import time
from datetime import datetime, timedelta
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from gramedia_client import FALLBACK_BOOK_CATALOG, REQUEST_DELAY_SECONDS, RETRY_EVERY_BOOKS, build_session, search_gramedia_book

app = Flask(__name__)
FORCE_HTTPS = os.getenv("FORCE_HTTPS", "0").lower() in {"1", "true", "yes", "on"}
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY") or os.urandom(32).hex()
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///perpustakaan.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = FORCE_HTTPS
app.config["REMEMBER_COOKIE_SECURE"] = FORCE_HTTPS
app.config["PERMANENT_SESSION_LIFETIME"] = 1800
app.config["PREFERRED_URL_SCHEME"] = "https" if FORCE_HTTPS else "http"
app.config["JSON_SORT_KEYS"] = False
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)

ALLOWED_EMAIL_DOMAINS = ("@gmail.com", "@smamarsudirinibekasi.sch.id")
STAFF_EMAIL = "staff"
STAFF_PASSWORD = "admin123"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="student")
    status = db.Column(db.String(50), nullable=False, default="pendingApproval")
    approval_requested = db.Column(db.Boolean, default=False)
    id_proof_name = db.Column(db.String(200), default="")
    device_hash = db.Column(db.String(120), default="")
    setup_used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="pbkdf2:sha256:200000")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    event = db.Column(db.String(120), nullable=False)
    details = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='activity_logs')

class FinanceEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_type = db.Column(db.String(30), nullable=False, default="income")
    label = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, unique=True)
    author = db.Column(db.String(200), nullable=False, default="Gramedia")
    publisher = db.Column(db.String(200), nullable=False, default="Gramedia")
    isbn = db.Column(db.String(100), nullable=False, default="")
    cover_url = db.Column(db.String(500), nullable=False, default="")
    category = db.Column(db.String(100), nullable=False, default="Umum")
    call_number = db.Column(db.String(50), nullable=False, default="GRAMEDIA")
    available = db.Column(db.Boolean, default=True)
    source = db.Column(db.String(50), nullable=False, default="Gramedia")
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)


class BorrowRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrower_name = db.Column(db.String(150), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    absen = db.Column(db.String(20), nullable=False)
    loan_days = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default="pending")
    borrowed_at = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, default=None)
    returned_at = db.Column(db.DateTime, default=None)
    is_returned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='borrow_requests')
    book = db.relationship('Book', backref='borrow_requests')

class Karya(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200), nullable=False)
    teaser = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)

def _normalize_catalog_title(value):
    cleaned = (value or "").replace("_", " ")
    cleaned = re.sub(r"(?i)(^|[\s\-:;,_])file(?=$|[\s\-:;,_])", " ", cleaned)
    cleaned = re.sub(r"(?i)\bfile\b", " ", cleaned)
    cleaned = re.sub(r"[\-_:;,.]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_.,;:")
    return cleaned


def record_activity(user_id, event, details=""):
    log = ActivityLog(user_id=user_id, event=event, details=details)
    db.session.add(log)
    db.session.commit()


def is_book_available_for_borrow(book):
    if book is None:
        return False
    active_borrow = BorrowRequest.query.filter_by(book_id=book.id, is_returned=False).first()
    return active_borrow is None


def build_dashboard_summary():
    total_users = User.query.count()
    pending_users = User.query.filter(User.status == "pendingApproval").count()
    approved_users = User.query.filter(User.status == "approved").count()
    staff_count = User.query.filter_by(role="staff").count()
    borrow_total = BorrowRequest.query.count()
    income_total = FinanceEntry.query.filter_by(entry_type="income").with_entities(db.func.coalesce(db.func.sum(FinanceEntry.amount), 0)).scalar() or 0
    outcome_total = FinanceEntry.query.filter_by(entry_type="outcome").with_entities(db.func.coalesce(db.func.sum(FinanceEntry.amount), 0)).scalar() or 0
    current_balance = income_total - outcome_total
    recent_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(8).all()
    finance_rows = FinanceEntry.query.order_by(FinanceEntry.created_at.desc()).limit(8).all()
    borrow_logs = BorrowRequest.query.order_by(BorrowRequest.created_at.desc()).limit(8).all()
    full_activity_logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).all()
    full_finance_logs = FinanceEntry.query.order_by(FinanceEntry.created_at.desc()).all()
    full_borrow_logs = BorrowRequest.query.order_by(BorrowRequest.created_at.desc()).all()

    def fmt_dt(value):
        return value.strftime("%d %b %Y") if value else "-"

    return {
        "total_users": total_users,
        "pending_users": pending_users,
        "approved_users": approved_users,
        "staff_count": staff_count,
        "borrow_total": borrow_total,
        "income_total": float(income_total),
        "outcome_total": float(outcome_total),
        "current_balance": float(current_balance),
        "recent_logs": [{
            "event": item.event,
            "details": item.details,
            "created_at": item.created_at.strftime("%d %b %Y %H:%M")
        } for item in recent_logs],
        "finance_rows": [{
            "id": item.id,
            "entry_type": item.entry_type,
            "label": item.label,
            "amount": float(item.amount),
            "notes": item.notes,
            "created_at": item.created_at.strftime("%d %b %Y")
        } for item in finance_rows],
        "borrow_logs": [{
            "id": item.id,
            "borrower_name": item.borrower_name,
            "class_name": item.class_name,
            "absen": item.absen,
            "book_title": item.book.title if item.book else "-",
            "loan_days": item.loan_days,
            "borrowed_at": fmt_dt(item.borrowed_at or item.created_at),
            "due_date": fmt_dt(item.due_date or (item.borrowed_at or item.created_at) + timedelta(days=item.loan_days)),
            "returned_at": fmt_dt(item.returned_at),
            "status": item.status,
            "is_returned": bool(item.is_returned),
            "created_at": item.created_at.strftime("%d %b %Y %H:%M")
        } for item in borrow_logs],
        "activity_logs": [{
            "id": item.id,
            "event": item.event,
            "details": item.details,
            "created_at": item.created_at.strftime("%d %b %Y %H:%M")
        } for item in full_activity_logs],
        "all_finance_logs": [{
            "id": item.id,
            "entry_type": item.entry_type,
            "label": item.label,
            "amount": float(item.amount),
            "notes": item.notes,
            "created_at": item.created_at.strftime("%d %b %Y %H:%M")
        } for item in full_finance_logs],
        "all_borrow_logs": [{
            "id": item.id,
            "borrower_name": item.borrower_name,
            "class_name": item.class_name,
            "absen": item.absen,
            "book_title": item.book.title if item.book else "-",
            "loan_days": item.loan_days,
            "status": item.status,
            "borrowed_at": fmt_dt(item.borrowed_at or item.created_at),
            "due_date": fmt_dt(item.due_date or (item.borrowed_at or item.created_at) + timedelta(days=item.loan_days)),
            "returned_at": fmt_dt(item.returned_at),
            "created_at": item.created_at.strftime("%d %b %Y %H:%M")
        } for item in full_borrow_logs]
    }


def ensure_db_schema():
    inspector = db.inspect(db.engine)
    if not inspector.has_table("user"):
        return

    user_columns = {column["name"] for column in inspector.get_columns("user")}
    column_additions = {
        "role": "ALTER TABLE \"user\" ADD COLUMN role VARCHAR(30) NOT NULL DEFAULT 'student'",
        "last_login_at": "ALTER TABLE \"user\" ADD COLUMN last_login_at DATETIME",
        "status": "ALTER TABLE \"user\" ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'pendingApproval'",
        "approval_requested": "ALTER TABLE \"user\" ADD COLUMN approval_requested BOOLEAN DEFAULT 0",
        "id_proof_name": "ALTER TABLE \"user\" ADD COLUMN id_proof_name VARCHAR(200) DEFAULT ''",
        "device_hash": "ALTER TABLE \"user\" ADD COLUMN device_hash VARCHAR(120) DEFAULT ''",
        "setup_used": "ALTER TABLE \"user\" ADD COLUMN setup_used BOOLEAN DEFAULT 0",
    }

    for column_name, ddl in column_additions.items():
        if column_name not in user_columns:
            with db.engine.begin() as conn:
                conn.execute(text(ddl))

    with db.session.begin():
        db.session.execute(text("UPDATE \"user\" SET role = 'student' WHERE role IS NULL OR role = ''"))
        db.session.execute(text("UPDATE \"user\" SET status = 'pendingApproval' WHERE status IS NULL OR status = ''"))
        db.session.execute(text("UPDATE \"user\" SET approval_requested = 0 WHERE approval_requested IS NULL"))
        db.session.execute(text("UPDATE \"user\" SET setup_used = 0 WHERE setup_used IS NULL"))
        db.session.execute(text("UPDATE \"user\" SET device_hash = '' WHERE device_hash IS NULL"))
        db.session.execute(text("UPDATE \"user\" SET id_proof_name = '' WHERE id_proof_name IS NULL"))

    if inspector.has_table("book"):
        book_columns = {column["name"] for column in inspector.get_columns("book")}
        book_additions = {
            "author": "ALTER TABLE book ADD COLUMN author VARCHAR(200) NOT NULL DEFAULT 'Gramedia'",
            "publisher": "ALTER TABLE book ADD COLUMN publisher VARCHAR(200) NOT NULL DEFAULT 'Gramedia'",
            "isbn": "ALTER TABLE book ADD COLUMN isbn VARCHAR(100) NOT NULL DEFAULT ''",
            "cover_url": "ALTER TABLE book ADD COLUMN cover_url VARCHAR(500) NOT NULL DEFAULT ''",
            "category": "ALTER TABLE book ADD COLUMN category VARCHAR(100) NOT NULL DEFAULT 'Umum'",
            "call_number": "ALTER TABLE book ADD COLUMN call_number VARCHAR(50) NOT NULL DEFAULT 'GRAMEDIA'",
            "available": "ALTER TABLE book ADD COLUMN available BOOLEAN DEFAULT 1",
            "source": "ALTER TABLE book ADD COLUMN source VARCHAR(50) NOT NULL DEFAULT 'Gramedia'",
            "last_synced": "ALTER TABLE book ADD COLUMN last_synced DATETIME",
        }
        for column_name, ddl in book_additions.items():
            if column_name not in book_columns:
                with db.engine.begin() as conn:
                    conn.execute(text(ddl))

        with db.session.begin():
            db.session.execute(text("UPDATE book SET author = 'Gramedia' WHERE author IS NULL OR author = ''"))
            db.session.execute(text("UPDATE book SET publisher = 'Gramedia' WHERE publisher IS NULL OR publisher = ''"))
            db.session.execute(text("UPDATE book SET isbn = '' WHERE isbn IS NULL"))
            db.session.execute(text("UPDATE book SET cover_url = '' WHERE cover_url IS NULL"))
            db.session.execute(text("UPDATE book SET category = 'Umum' WHERE category IS NULL OR category = ''"))
            db.session.execute(text("UPDATE book SET call_number = 'GRAMEDIA' WHERE call_number IS NULL OR call_number = ''"))
            db.session.execute(text("UPDATE book SET available = 1 WHERE available IS NULL"))
            db.session.execute(text("UPDATE book SET source = 'Gramedia' WHERE source IS NULL OR source = ''"))

    borrow_columns = {column["name"] for column in inspector.get_columns("borrow_request")}
    borrow_additions = {
        "borrowed_at": "ALTER TABLE borrow_request ADD COLUMN borrowed_at DATETIME",
        "due_date": "ALTER TABLE borrow_request ADD COLUMN due_date DATETIME",
        "returned_at": "ALTER TABLE borrow_request ADD COLUMN returned_at DATETIME",
        "is_returned": "ALTER TABLE borrow_request ADD COLUMN is_returned BOOLEAN DEFAULT 0",
    }
    for column_name, ddl in borrow_additions.items():
        if column_name not in borrow_columns:
            with db.engine.begin() as conn:
                conn.execute(text(ddl))

    with db.session.begin():
        db.session.execute(text("UPDATE borrow_request SET borrowed_at = created_at WHERE borrowed_at IS NULL"))
        db.session.execute(text("UPDATE borrow_request SET due_date = datetime(created_at, '+' || loan_days || ' day') WHERE due_date IS NULL"))
        db.session.execute(text("UPDATE borrow_request SET is_returned = 0 WHERE is_returned IS NULL"))


RESET_DATABASE_ON_BOOT = os.getenv("RESET_DATABASE_ON_BOOT", "0").lower() in {"1", "true", "yes", "on"}

POPULAR_BOOK_SEEDS = [
    {"title": "Clean Code", "author": "Robert C. Martin", "category": "Teknologi", "call_number": "005.1/MAR", "publisher": "Prentice Hall"},
    {"title": "The Pragmatic Programmer", "author": "Andrew Hunt", "category": "Teknologi", "call_number": "005.1/HUN", "publisher": "Addison-Wesley"},
    {"title": "Python Crash Course", "author": "Eric Matthes", "category": "Teknologi", "call_number": "005.133/MAT", "publisher": "No Starch Press"},
    {"title": "Deep Learning", "author": "Ian Goodfellow", "category": "Teknologi", "call_number": "006.31/GOO", "publisher": "MIT Press"},
    {"title": "Atomic Habits", "author": "James Clear", "category": "Pengembangan Diri", "call_number": "158.1/CLE", "publisher": "Avery"},
    {"title": "The Alchemist", "author": "Paulo Coelho", "category": "Novel", "call_number": "813.6/COE", "publisher": "HarperOne"},
    {"title": "Laskar Pelangi", "author": "Andrea Hirata", "category": "Novel", "call_number": "813.6/HIR", "publisher": "Bentang Pustaka"},
    {"title": "Bumi Manusia", "author": "Pramoedya Ananta Toer", "category": "Novel", "call_number": "813.6/PRA", "publisher": "Hasta Mitra"},
    {"title": "Sapiens", "author": "Yuval Noah Harari", "category": "Sejarah", "call_number": "909.8/HAR", "publisher": "Harper"},
    {"title": "Filosofi Teras", "author": "Henry Manampiring", "category": "Pelajaran", "call_number": "190.1/MAN", "publisher": "Kompas"},
    {"title": "Belajar Coding dengan Python", "author": "Nadia Kurnia", "category": "Teknologi", "call_number": "005.1/KUR", "publisher": "Gramedia"},
    {"title": "Matematika Peminatan Kelas XI", "author": "Tim Penulis Kemdikbud", "category": "Pelajaran", "call_number": "510.2/MAT", "publisher": "Kemdikbud"},
    {"title": "Fisika Dasar untuk SMA", "author": "R. Sutrisno", "category": "Pelajaran", "call_number": "530.1/SUT", "publisher": "Erlangga"},
    {"title": "Biologi SMA Kelas XII", "author": "Kurnia Sari", "category": "Pelajaran", "call_number": "570.2/SAR", "publisher": "Erlangga"},
    {"title": "The Hobbit", "author": "J.R.R. Tolkien", "category": "Fantasi", "call_number": "823.9/TOL", "publisher": "Houghton Mifflin"},
    {"title": "A Brief History of Time", "author": "Stephen Hawking", "category": "Sains", "call_number": "523.1/HAW", "publisher": "Bantam"},
    {"title": "Pride and Prejudice", "author": "Jane Austen", "category": "Novel", "call_number": "823.7/AUS", "publisher": "Penguin"},
    {"title": "The Little Prince", "author": "Antoine de Saint-Exupéry", "category": "Novel", "call_number": "843.9/SAI", "publisher": "Harcourt"},
    {"title": "One Piece Vol. 1", "author": "Eiichiro Oda", "category": "Komik", "call_number": "741.5/ODA", "publisher": "Shueisha"},
    {"title": "Dilan 1990", "author": "Pidi Baiq", "category": "Novel", "call_number": "813.6/BAI", "publisher": "Mizan"},
    {"title": "Mereka Bilang, Saya Monyet", "author": "Raditya Dika", "category": "Novel", "call_number": "818.6/DIK", "publisher": "KPG"},
    {"title": "B.J. Habibie: Bapak Teknologi Indonesia", "author": "M. Ridwan", "category": "Biografi", "call_number": "920/HAB", "publisher": "Gramedia"},
    {"title": "Sang Pemimpi", "author": "Andrea Hirata", "category": "Biografi", "call_number": "920/HIR", "publisher": "Bentang Pustaka"},
    {"title": "Sejarah Nusantara Ringkas", "author": "Slamet Muljana", "category": "Sejarah & Budaya", "call_number": "959.8/MUL", "publisher": "LKiS"},
    {"title": "Jejak Budaya Nusantara", "author": "Koentjaraningrat", "category": "Sejarah & Budaya", "call_number": "306.09/KOE", "publisher": "Gramedia"},
    {"title": "Kumpulan Puisi Chairil Anwar", "author": "Chairil Anwar", "category": "Sastra & Puisi", "call_number": "899.21/ANW", "publisher": "KPG"},
    {"title": "Hujan Bulan Juni", "author": "Sapardi Djoko Damono", "category": "Sastra & Puisi", "call_number": "899.21/DAM", "publisher": "Gramedia"},
    {"title": "Bumi (Trilogi Bumi #1)", "author": "Tere Liye", "category": "Fantasi", "call_number": "813.7/LIY", "publisher": "Gramedia"},
    {"title": "Dunia Anna", "author": "Jostein Gaarder", "category": "Fantasi", "call_number": "839.8/GAA", "publisher": "Mizan"},
    {"title": "Kisah Teladan Para Nabi", "author": "Tim Studi Islam", "category": "Agama", "call_number": "297.6/TSI", "publisher": "Pustaka"},
    {"title": "Renungan Harian Remaja", "author": "Yohanes Prasetyo", "category": "Agama", "call_number": "242/PRA", "publisher": "Gramedia"},
    {"title": "Panduan Fotografi untuk Pemula", "author": "Budi Santoso", "category": "Hobi & Keterampilan", "call_number": "770.2/SAN", "publisher": "Gramedia"},
    {"title": "Creativepreneur: Menjadi Pebisnis Kreatif", "author": "Rizal Aditya", "category": "Hobi & Keterampilan", "call_number": "658.4/ADI", "publisher": "Gramedia"},
    {"title": "Membaca Cepat dan Efektif", "author": "Nina Rahma", "category": "Hobi & Keterampilan", "call_number": "371.3/RAH", "publisher": "Gramedia"},
    {"title": "Seni Lukis untuk Pemula", "author": "Rina Fadilah", "category": "Hobi & Keterampilan", "call_number": "751.1/FAD", "publisher": "Gramedia"},
    {"title": "Buku Manajemen Waktu", "author": "Ayu Lestari", "category": "Hobi & Keterampilan", "call_number": "650.1/LES", "publisher": "Gramedia"},
    {"title": "Ensiklopedia Sains Populer", "author": "Tim Redaksi Ilmu", "category": "Sains & Ensiklopedia", "call_number": "503/ENS", "publisher": "Gramedia"},
    {"title": "Alam Semesta dalam Angka", "author": "Yuval N. Hartawan", "category": "Sains & Ensiklopedia", "call_number": "520.1/HAR", "publisher": "Gramedia"},
    {"title": "The Power of Habit", "author": "Charles Duhigg", "category": "Sains & Ensiklopedia", "call_number": "153.8/DUH", "publisher": "Random House"},
    {"title": "English Grammar in Use", "author": "Raymond Murphy", "category": "Pelajaran", "call_number": "425/MUR", "publisher": "Cambridge"},
    {"title": "Filosofi Teras", "author": "Henry Manampiring", "category": "Pelajaran", "call_number": "190.1/MAN", "publisher": "Kompas"},
    {"title": "Pendidikan Karakter untuk SMA", "author": "Lailatul Fitri", "category": "Pelajaran", "call_number": "370.1/FIT", "publisher": "Erlangga"},
    {"title": "Ekonomi untuk SMA", "author": "Rina Widyastuti", "category": "Pelajaran", "call_number": "330.9/WID", "publisher": "Erlangga"},
    {"title": "Sosiologi Kelas XII", "author": "Teguh Prasetyo", "category": "Pelajaran", "call_number": "301.5/PRA", "publisher": "Erlangga"},
    {"title": "Matahari", "author": "Tere Liye", "category": "Fantasi", "call_number": "813.7/LIY2", "publisher": "Gramedia"},
    {"title": "Rindu", "author": "Tere Liye", "category": "Fantasi", "call_number": "813.7/LIY3", "publisher": "Gramedia"},
    {"title": "Bocah Tengger", "author": "Tere Liye", "category": "Novel", "call_number": "813.7/LIY4", "publisher": "Gramedia"},
    {"title": "Harry Potter and the Philosopher's Stone", "author": "J.K. Rowling", "category": "Fantasi", "call_number": "823.9/ROW", "publisher": "Bloomsbury"}
]


def seed_library_books():
    existing_titles = {book.title for book in Book.query.all()}

    catalog_items = []
    for item in FALLBACK_BOOK_CATALOG:
        title = (item.get("title") or "").strip()
        if title and title not in existing_titles:
            catalog_items.append({
                **item,
                "category": "Umum",
                "call_number": "GRAMEDIA",
                "available": True,
                "source": "Gramedia",
            })
            existing_titles.add(title)

    for item in POPULAR_BOOK_SEEDS:
        title = (item.get("title") or "").strip()
        if title and title not in existing_titles:
            catalog_items.append({
                "title": title,
                "author": (item.get("author") or "Gramedia").strip(),
                "publisher": (item.get("publisher") or "Gramedia").strip(),
                "isbn": (item.get("isbn") or "").strip(),
                "cover_url": (item.get("cover_url") or "").strip(),
                "category": item.get("category") or "Umum",
                "call_number": item.get("call_number") or "GRAMEDIA",
                "available": True,
                "source": "Gramedia",
            })
            existing_titles.add(title)

    for item in catalog_items:
        book = Book(
            title=(item.get("title") or "").strip(),
            author=(item.get("author") or "Gramedia").strip(),
            publisher=(item.get("publisher") or "Gramedia").strip(),
            isbn=(item.get("isbn") or "").strip(),
            cover_url=(item.get("cover_url") or "").strip(),
            category=item.get("category") or "Umum",
            call_number=item.get("call_number") or "GRAMEDIA",
            available=True,
            source="Gramedia",
        )
        db.session.add(book)

    db.session.commit()


with app.app_context():
    if RESET_DATABASE_ON_BOOT:
        db.drop_all()
    db.create_all()
    ensure_db_schema()
    seed_library_books()
    db.session.commit()


def allowed_email(email):
    value = (email or "").strip().lower()
    if value == STAFF_EMAIL:
        return True
    return any(value.endswith(domain) for domain in ALLOWED_EMAIL_DOMAINS)


def is_school_email(email):
    value = (email or "").strip().lower()
    return value.endswith("@smamarsudirinibekasi.sch.id")


@app.before_request
def enforce_https_redirect():
    if not FORCE_HTTPS:
        return None
    if request.endpoint in {"static", None}:
        return None
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        return None
    url = request.url.replace("http://", "https://", 1)
    return redirect(url, code=301)


def generate_device_hash():
    user_agent = request.user_agent.string if request.user_agent else "unknown-agent"
    remote_addr = request.remote_addr or "unknown-ip"
    raw = f"{user_agent}|{remote_addr}"
    return generate_password_hash(raw, method="pbkdf2:sha256:200000")[:64]


def user_from_session():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


@app.route("/")
def home():
    user = user_from_session()
    if not user:
        return redirect(url_for("auth_page"))
    return redirect(url_for("library_page"))


@app.route("/auth")
def auth_page():
    return render_template("auth.html")


@app.route("/library")
def library_page():
    user = user_from_session()
    if not user:
        return redirect(url_for("auth_page"))
    if user.email.endswith("@gmail.com") and user.status != "approved":
        return redirect(url_for("auth_page"))
    return render_template("perpustakaan-sekolah.html", user=user, dashboard=build_dashboard_summary())


@app.route("/staff/setup")
def staff_setup_page():
    user = user_from_session()
    if not user or user.role != "staff_setup":
        return redirect(url_for("auth_page"))
    if user.setup_used and not session.get("staff_setup_active"):
        return redirect(url_for("auth_page"))
    current_device = generate_device_hash()
    if user.device_hash and user.device_hash != current_device:
        user.device_hash = current_device
        db.session.commit()
    return render_template("staff_setup.html", user=user)


@app.route("/admin")
def admin_page():
    user = user_from_session()
    if not user or user.role != "staff":
        return redirect(url_for("auth_page"))
    return render_template("admin.html", user=user, dashboard=build_dashboard_summary())


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.form
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    approval_requested = data.get("approval_requested") == "true"

    if not name:
        return jsonify({"ok": False, "message": "Nama lengkap harus diisi."}), 400
    if not allowed_email(email):
        return jsonify({"ok": False, "message": "Email harus menggunakan @gmail.com atau @smamarsudirinibekasi.sch.id."}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "message": "Password minimal 6 karakter."}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"ok": False, "message": "Email sudah terdaftar."}), 400

    stored_proof_name = ""
    if email.endswith("@gmail.com"):
        uploaded = request.files.get("id_proof")
        if uploaded and uploaded.filename:
            original_name = secure_filename(uploaded.filename)
            ext = os.path.splitext(original_name)[1].lower()
            stored_proof_name = f"{uuid4().hex}{ext}"
            uploaded.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_proof_name))
        elif not approval_requested:
            return jsonify({"ok": False, "message": "Akun Gmail harus menyertakan identitas atau meminta persetujuan staf perpustakaan."}), 400

    user = User(
        name=name,
        email=email,
        status="approved" if is_school_email(email) else "pendingApproval",
        approval_requested=approval_requested,
        id_proof_name=stored_proof_name
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    return jsonify({"ok": True, "message": "Pendaftaran berhasil."})


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.form
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "student").strip().lower()

    if email == STAFF_EMAIL:
        user = User.query.filter_by(email=STAFF_EMAIL).first()
    else:
        user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        if email == STAFF_EMAIL:
            return jsonify({"ok": False, "message": "Login disposable staff gagal. Cek email dan password staff."}), 401
        return jsonify({"ok": False, "message": "Email atau password salah."}), 401

    if user.email == STAFF_EMAIL:
        if user.role != "staff_setup":
            user.role = "staff_setup"
            user.status = "approved"
            user.approval_requested = False
            user.setup_used = False
            user.device_hash = ""
        if user.setup_used:
            return jsonify({"ok": False, "message": "Akun staff disposable sudah dipakai dan tidak bisa digunakan lagi di perangkat mana pun."}), 403
        current_device = generate_device_hash()
        if user.device_hash and user.device_hash != current_device:
            return jsonify({"ok": False, "message": "Akun staff disposable sudah digunakan di perangkat lain dan tidak bisa dipakai lagi."}), 403
        user.device_hash = current_device
        user.setup_used = True
        user.last_login_at = datetime.utcnow()
        session["user_id"] = user.id
        session["staff_setup_active"] = True
        db.session.commit()
        return jsonify({"ok": True, "message": "Login setup staff berhasil.", "redirect": url_for("staff_setup_page")})

    if role and user.role != role:
        return jsonify({"ok": False, "message": "Login gagal. Peran akunnya tidak sesuai dengan pilihan masuk."}), 401

    if user.email.endswith("@gmail.com") and user.status != "approved":
        return jsonify({"ok": False, "message": "Akun Gmail Anda belum disetujui oleh staf perpustakaan."}), 403

    user.last_login_at = datetime.utcnow()
    session["user_id"] = user.id
    record_activity(user.id, "Login", f"{user.name} masuk ke sistem.")
    db.session.commit()

    redirect_target = url_for("admin_page") if user.role == "staff" else url_for("library_page")
    return jsonify({"ok": True, "message": "Login berhasil.", "redirect": redirect_target})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True, "redirect": url_for("auth_page")})


@app.route("/api/user")
def api_user():
    user = user_from_session()
    if not user:
        return jsonify({"ok": False}), 401
    return jsonify({
        "ok": True,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "status": user.status
        }
    })


@app.route("/api/books")
def api_books():
    category_order = {
        "Pelajaran": 0,
        "Novel": 1,
        "Komik": 2,
        "Biografi": 3,
        "Sains & Ensiklopedia": 4,
        "Sejarah & Budaya": 5,
        "Sastra & Puisi": 6,
        "Fantasi": 7,
        "Fantasi & Fiksi Ilmiah": 8,
        "Agama": 9,
        "Agama & Kerohanian": 10,
        "Hobi & Keterampilan": 11,
        "Teknologi": 12,
        "Pengembangan Diri": 13,
        "Sejarah": 14,
        "Umum": 99,
    }

    books = Book.query.all()
    books = sorted(books, key=lambda b: (category_order.get(b.category, 999), (b.title or "").lower()))

    book_payload = []
    for b in books:
        book_payload.append({
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "publisher": getattr(b, "publisher", "Gramedia"),
            "isbn": getattr(b, "isbn", ""),
            "cover_url": getattr(b, "cover_url", ""),
            "category": b.category,
            "call_number": b.call_number,
            "available": is_book_available_for_borrow(b),
        })
    return jsonify({"books": book_payload})


@app.route("/api/search-external")
def api_search_external():
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"ok": False, "message": "Parameter q harus diisi."}), 400

    result = search_gramedia_book(query)
    if result.get("error"):
        return jsonify({"ok": False, "message": result["error"]}), 404

    return jsonify({"ok": True, "result": result})


@app.route("/api/sync-gramedia")
def api_sync_gramedia():
    titles_param = (request.args.get("titles") or "").strip()
    titles = [part.strip() for part in titles_param.split("|") if part.strip()] if titles_param else [
        "Clean Code",
        "Python Crash Course",
        "Atomic Habits",
        "The Alchemist",
        "Laskar Pelangi",
        "Bumi Manusia",
        "Sapiens",
        "The Hobbit",
        "The Pragmatic Programmer",
        "Deep Learning",
        "Filosofi Teras",
        "Belajar Coding dengan Python",
        "Matematika Peminatan Kelas XI",
        "Fisika Dasar untuk SMA",
        "Biologi SMA Kelas XII",
        "Belajar Python untuk Pemula",
        "Head First Python",
        "JavaScript The Good Parts",
        "Eloquent JavaScript",
        "Think Like a Programmer",
        "Data Science from Scratch",
        "Artificial Intelligence A Modern Approach",
        "Introduction to Algorithms",
        "Refactoring",
        "The Pragmatic Programmer",
        "Design Patterns",
        "Cracking the Coding Interview",
        "Algorithms Unlocked",
        "The Lean Startup",
        "Zero to One",
        "Rich Dad Poor Dad",
        "Think and Grow Rich",
        "The Psychology of Money",
        "Ikigai",
        "Atomic Habits",
        "The Power of Habit",
        "Filosofi Teras",
        "Manajemen Waktu",
        "Digital Minimalism",
        "Essentialism",
        "Deep Work",
        "The 7 Habits of Highly Effective People",
        "How to Win Friends and Influence People",
        "The Subtle Art of Not Giving a F*ck",
        "Dilan 1990",
        "Laskar Pelangi",
        "Bumi Manusia",
        "Sang Pemimpi",
        "Ayat Ayat Cinta",
        "Negeri 5 Menara",
        "Pulang",
        "Dunia Sophie",
        "The Little Prince",
        "Pride and Prejudice",
        "A Brief History of Time",
        "Cosmos",
        "The Theory of Everything",
        "Educated",
        "Born a Crime",
        "The Diary of a Young Girl",
        "A Song of Ice and Fire",
        "Harry Potter and the Sorcerer's Stone",
        "Fantastic Beasts and Where to Find Them",
        "The Hobbit",
        "Animal Farm",
        "1984",
        "Foundation",
        "The Martian",
        "The Silent Patient",
        "The Book Thief",
        "To Kill a Mockingbird",
        "The Kite Runner",
        "Percy Jackson and the Lightning Thief",
        "The Hunger Games",
        "The Maze Runner",
        "The Fault in Our Stars",
        "One Piece",
        "Attack on Titan",
        "Naruto",
        "Death Note",
        "Spy x Family",
        "Buku Matematika Kelas 10",
        "Buku Fisika Kelas 12",
        "Buku Biologi Kelas 11",
        "Buku Kimia Kelas 10",
        "Buku Bahasa Inggris Kelas 12",
        "Buku Sejarah Indonesia",
        "Buku Sosiologi Kelas 11",
        "Buku Ekonomi Kelas 12",
        "Buku Geografi Kelas 10",
        "Ensiklopedia Sains",
        "Kisah Teladan Nabi",
        "Sejarah Nusantara",
        "Pendidikan Karakter",
        "Kumpulan Puisi Indonesia",
    ]

    imported = []
    seen = set()
    session = build_session()

    for index, title in enumerate(titles, start=1):
        if not title or title in seen:
            continue
        seen.add(title)

        if index > 1:
            if index % RETRY_EVERY_BOOKS == 0:
                time.sleep(2.5)
            else:
                time.sleep(REQUEST_DELAY_SECONDS)

        result = None
        for attempt in range(3):
            result = search_gramedia_book(title, session=session)
            if not result.get("error"):
                break
            if attempt < 2:
                time.sleep(2 ** attempt)

        if result.get("error"):
            continue

        book_title = (result.get("title") or title).strip()
        if not book_title or Book.query.filter_by(title=book_title).first():
            continue
        record = Book(
            title=book_title,
            author=(result.get("author") or "Gramedia").strip(),
            publisher=(result.get("publisher") or "Gramedia").strip(),
            isbn=(result.get("isbn") or "").strip(),
            cover_url=(result.get("cover_url") or "").strip(),
            category="Umum",
            call_number="GRAMEDIA",
            available=True,
            source="Gramedia",
        )
        db.session.add(record)
        imported.append({
            "title": book_title,
            "author": record.author,
            "publisher": record.publisher,
            "isbn": record.isbn,
            "cover_url": record.cover_url,
        })

    db.session.commit()
    return jsonify({"ok": True, "count": len(imported), "books": imported})


@app.route("/api/karya")
def api_karya():
    karya = Karya.query.order_by(Karya.id).all()
    return jsonify({
        "karya": [{
            "id": k.id,
            "type": k.type,
            "title": k.title,
            "author": k.author,
            "teaser": k.teaser,
            "body": k.body
        } for k in karya]
    })


@app.route("/api/borrow", methods=["POST"])
def api_borrow():
    user = user_from_session()
    if not user:
        return jsonify({"ok": False, "message": "Silakan masuk terlebih dahulu."}), 401

    data = request.get_json(silent=True) or {}
    book_id = data.get("book_id")
    borrower_name = (data.get("borrower_name") or "").strip()
    class_name = (data.get("class_name") or "").strip()
    absen = (data.get("absen") or "").strip()
    loan_days = int(data.get("loan_days") or 7)

    if not book_id or not borrower_name or not class_name or not absen:
        return jsonify({"ok": False, "message": "Lengkapi seluruh data peminjaman."}), 400

    book = Book.query.get(book_id)
    if not book:
        return jsonify({"ok": False, "message": "Buku tidak ditemukan."}), 404
    if not is_book_available_for_borrow(book):
        return jsonify({"ok": False, "message": "Buku sedang dipinjam."}), 400

    now = datetime.utcnow()
    book.available = False
    borrow_request = BorrowRequest(
        user_id=user.id,
        book_id=book.id,
        borrower_name=borrower_name,
        class_name=class_name,
        absen=absen,
        loan_days=loan_days,
        status="pending",
        borrowed_at=now,
        due_date=now + timedelta(days=loan_days),
        returned_at=None,
        is_returned=False,
    )
    db.session.add(borrow_request)
    db.session.commit()

    return jsonify({"ok": True, "message": f"Peminjaman buku '{book.title}' berhasil diajukan."})


@app.route("/api/staff/upgrade", methods=["POST"])
def api_staff_upgrade():
    user = user_from_session()
    if not user or user.role != "staff_setup":
        return jsonify({"ok": False, "message": "Akses staff setup ditolak."}), 403
    if not session.get("staff_setup_active"):
        return jsonify({"ok": False, "message": "Sesi setup staff sudah berakhir."}), 403

    data = request.form
    target_email = (data.get("target_email") or "").strip().lower()
    new_name = (data.get("staff_name") or "").strip()
    new_password = (data.get("password") or "").strip()

    if not target_email or not new_name or len(new_password) < 6:
        return jsonify({"ok": False, "message": "Isi email staff, nama staff, dan password minimal 6 karakter."}), 400
    if not allowed_email(target_email):
        return jsonify({"ok": False, "message": "Email staff harus memakai @gmail.com atau @smamarsudirinibekasi.sch.id."}), 400

    existing = User.query.filter_by(email=target_email).first()
    if existing and existing.email == STAFF_EMAIL:
        return jsonify({"ok": False, "message": "Akun staff disposable tidak bisa dipakai lagi."}), 403
    if existing and existing.role == "staff":
        return jsonify({"ok": False, "message": "Akun staff dengan email ini sudah ada."}), 400

    if existing and existing.role == "student":
        staff_account = existing
    else:
        staff_account = User(
            name=new_name,
            email=target_email,
            role="staff",
            status="approved",
            approval_requested=False,
            id_proof_name="",
        )
        db.session.add(staff_account)

    staff_account.name = new_name
    staff_account.role = "staff"
    staff_account.status = "approved"
    staff_account.approval_requested = False
    staff_account.id_proof_name = ""
    staff_account.set_password(new_password)
    staff_account.last_login_at = datetime.utcnow()

    user.setup_used = True
    user.status = "used"
    user.device_hash = generate_device_hash()
    db.session.commit()

    session.pop("staff_setup_active", None)
    session["user_id"] = staff_account.id
    return jsonify({"ok": True, "message": "Akun staff berhasil dibuat.", "redirect": url_for("admin_page")})


@app.route("/api/approval-queue")
def api_approval_queue():
    staff = user_from_session()
    if not staff or staff.role != "staff":
        return jsonify({"ok": False, "message": "Akses ditolak."}), 403

    users = User.query.filter(User.email.endswith("@gmail.com")).order_by(User.created_at.desc()).all()
    return jsonify({
        "users": [{
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "status": user.status,
            "approval_requested": user.approval_requested,
            "id_proof_name": user.id_proof_name
        } for user in users if user.status in ("pendingApproval", "rejected")]
    })


@app.route("/api/approval/<int:user_id>/<action>", methods=["POST"])
def api_approval_action(user_id, action):
    staff = user_from_session()
    if not staff or staff.role != "staff":
        return jsonify({"ok": False, "message": "Akses ditolak."}), 403

    user = User.query.get_or_404(user_id)
    if action == "approve":
        user.status = "approved"
        user.approval_requested = False
        record_activity(user.id, "Persetujuan akun", f"Akun {user.email} disetujui oleh staff.")
    elif action == "reject":
        user.status = "rejected"
        record_activity(user.id, "Penolakan akun", f"Akun {user.email} ditolak oleh staff.")
    else:
        return jsonify({"ok": False, "message": "Aksi tidak valid."}), 400
    db.session.commit()
    return jsonify({"ok": True, "message": "Status akun diperbarui."})


@app.route("/api/admin/summary")
def api_admin_summary():
    user = user_from_session()
    if not user or user.role != "staff":
        return jsonify({"ok": False, "message": "Akses ditolak."}), 403
    return jsonify({"ok": True, "dashboard": build_dashboard_summary()})


@app.route("/api/borrow/return/<int:borrow_id>", methods=["POST"])
def api_mark_borrow_returned(borrow_id):
    staff = user_from_session()
    if not staff or staff.role != "staff":
        return jsonify({"ok": False, "message": "Akses ditolak."}), 403

    borrow = BorrowRequest.query.get_or_404(borrow_id)
    if not borrow.is_returned:
        borrow.is_returned = True
        borrow.returned_at = datetime.utcnow()
        borrow.status = "returned"
        book = Book.query.get(borrow.book_id)
        if book:
            book.available = True
        record_activity(staff.id, "Pengembalian buku", f"{borrow.borrower_name} mengembalikan {borrow.book.title if borrow.book else 'buku'}.")
    db.session.commit()
    return jsonify({"ok": True, "message": "Status pengembalian buku diperbarui."})


def validate_finance_payload(form_data):
    entry_type = (form_data.get("entry_type") or "").strip().lower()
    label = (form_data.get("label") or "").strip()
    amount_value = (form_data.get("amount") or "0").strip()
    notes = (form_data.get("notes") or "").strip()

    if entry_type not in {"income", "outcome"}:
        return None, {"ok": False, "message": "Tipe data keuangan harus income atau outcome."}, 400
    if not label:
        return None, {"ok": False, "message": "Judul pemasukan/pengeluaran harus diisi."}, 400
    try:
        amount = float(amount_value)
    except ValueError:
        return None, {"ok": False, "message": "Nominal harus berupa angka."}, 400
    if amount <= 0:
        return None, {"ok": False, "message": "Nominal harus lebih dari 0."}, 400

    return {"entry_type": entry_type, "label": label, "amount": amount, "notes": notes or "Catatan staf perpustakaan"}, None, None


@app.route("/api/admin/finance", methods=["POST"])
def api_admin_finance():
    staff = user_from_session()
    if not staff or staff.role != "staff":
        return jsonify({"ok": False, "message": "Akses ditolak."}), 403

    payload, error, status = validate_finance_payload(request.form)
    if error:
        return jsonify(error), status

    entry = FinanceEntry(**payload)
    db.session.add(entry)
    db.session.commit()
    record_activity(staff.id, "Keuangan", f"{payload['entry_type'].upper()} ditambahkan: {payload['label']} (Rp {payload['amount']:,.0f})")

    return jsonify({"ok": True, "message": "Data keuangan berhasil ditambahkan.", "redirect": url_for("admin_page")})


@app.route("/api/admin/finance/<int:entry_id>", methods=["PUT"])
def api_admin_finance_update(entry_id):
    staff = user_from_session()
    if not staff or staff.role != "staff":
        return jsonify({"ok": False, "message": "Akses ditolak."}), 403

    entry = FinanceEntry.query.get_or_404(entry_id)
    payload, error, status = validate_finance_payload(request.form)
    if error:
        return jsonify(error), status

    old_label = entry.label
    old_amount = entry.amount
    old_type = entry.entry_type
    entry.entry_type = payload["entry_type"]
    entry.label = payload["label"]
    entry.amount = payload["amount"]
    entry.notes = payload["notes"]
    db.session.commit()
    record_activity(
        staff.id,
        "Keuangan diedit",
        f"{old_type.upper()} diubah: '{old_label}' (Rp {old_amount:,.0f}) -> '{payload['label']}' (Rp {payload['amount']:,.0f})"
    )

    return jsonify({"ok": True, "message": "Data keuangan berhasil diubah."})


@app.route("/api/admin/finance/<int:entry_id>", methods=["DELETE"])
def api_admin_finance_delete(entry_id):
    staff = user_from_session()
    if not staff or staff.role != "staff":
        return jsonify({"ok": False, "message": "Akses ditolak."}), 403

    entry = FinanceEntry.query.get_or_404(entry_id)
    label = entry.label
    entry_type = entry.entry_type
    db.session.delete(entry)
    db.session.commit()
    record_activity(staff.id, "Keuangan dihapus", f"{entry_type.upper()} dihapus: '{label}'")

    return jsonify({"ok": True, "message": "Data keuangan berhasil dihapus."})


@app.route("/api/admin/finance/bulk-delete", methods=["POST"])
def api_admin_finance_bulk_delete():
    staff = user_from_session()
    if not staff or staff.role != "staff":
        return jsonify({"ok": False, "message": "Akses ditolak."}), 403

    data = request.get_json(silent=True) or {}
    entry_ids = data.get("ids") or []
    if not isinstance(entry_ids, list) or not entry_ids:
        return jsonify({"ok": False, "message": "Pilih minimal satu data keuangan."}), 400

    entries = FinanceEntry.query.filter(FinanceEntry.id.in_(entry_ids)).all()
    if not entries:
        return jsonify({"ok": False, "message": "Data yang dipilih tidak ditemukan."}), 404

    for entry in entries:
        record_activity(staff.id, "Keuangan bulk dihapus", f"{entry.entry_type.upper()} dihapus: '{entry.label}'")
        db.session.delete(entry)
    db.session.commit()

    return jsonify({"ok": True, "message": f"{len(entries)} data keuangan berhasil dihapus."})




if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
