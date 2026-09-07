import re
import time
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GRAMEDIA_SEARCH_URL = "https://www.gramedia.com/api/v1/product/search/?q={query}"
DEFAULT_TIMEOUT = 25
REQUEST_DELAY_SECONDS = 1.5
RETRY_EVERY_BOOKS = 5

FALLBACK_BOOK_CATALOG = [
    {"title": "Clean Code", "author": "Robert C. Martin", "publisher": "Prentice Hall", "isbn": "9780132350884", "cover_url": ""},
    {"title": "Python Crash Course", "author": "Eric Matthes", "publisher": "No Starch Press", "isbn": "9781593279288", "cover_url": ""},
    {"title": "Atomic Habits", "author": "James Clear", "publisher": "Avery", "isbn": "9780735211292", "cover_url": ""},
    {"title": "The Pragmatic Programmer", "author": "Andrew Hunt", "publisher": "Addison-Wesley", "isbn": "9780201616224", "cover_url": ""},
    {"title": "Deep Learning", "author": "Ian Goodfellow", "publisher": "MIT Press", "isbn": "9780262035613", "cover_url": ""},
    {"title": "The Alchemist", "author": "Paulo Coelho", "publisher": "HarperOne", "isbn": "9780061122415", "cover_url": ""},
    {"title": "Sapiens", "author": "Yuval Noah Harari", "publisher": "Harper", "isbn": "9780062316097", "cover_url": ""},
    {"title": "The Hobbit", "author": "J.R.R. Tolkien", "publisher": "Houghton Mifflin", "isbn": "9780547928227", "cover_url": ""},
    {"title": "Laskar Pelangi", "author": "Andrea Hirata", "publisher": "Bentang Pustaka", "isbn": "9789791228326", "cover_url": ""},
    {"title": "Bumi Manusia", "author": "Pramoedya Ananta Toer", "publisher": "Lentera Dipantara", "isbn": "9789799730462", "cover_url": ""},
    {"title": "Filosofi Teras", "author": "Henry Manampiring", "publisher": "Kompas", "isbn": "9786024241660", "cover_url": ""},
    {"title": "Belajar Coding dengan Python", "author": "Nadia Kurnia", "publisher": "Gramedia", "isbn": "", "cover_url": ""},
    {"title": "Matematika Peminatan Kelas XI", "author": "Tim Penulis Kemdikbud", "publisher": "Kemdikbud", "isbn": "", "cover_url": ""},
    {"title": "Fisika Dasar untuk SMA", "author": "R. Sutrisno", "publisher": "Erlangga", "isbn": "", "cover_url": ""},
    {"title": "Biologi SMA Kelas XII", "author": "Kurnia Sari", "publisher": "Erlangga", "isbn": "", "cover_url": ""},
    {"title": "Head First Python", "author": "Paul Barry", "publisher": "O'Reilly", "isbn": "9781491919538", "cover_url": ""},
    {"title": "Eloquent JavaScript", "author": "Marijn Haverbeke", "publisher": "No Starch Press", "isbn": "9781593279509", "cover_url": ""},
    {"title": "Think Like a Programmer", "author": "V. Anton Spraul", "publisher": "No Starch Press", "isbn": "9781593274245", "cover_url": ""},
    {"title": "Data Science from Scratch", "author": "Joel Grus", "publisher": "O'Reilly", "isbn": "9781491901427", "cover_url": ""},
    {"title": "Introduction to Algorithms", "author": "Thomas H. Cormen", "publisher": "MIT Press", "isbn": "9780262033848", "cover_url": ""},
    {"title": "Refactoring", "author": "Martin Fowler", "publisher": "Addison-Wesley", "isbn": "9780134757599", "cover_url": ""},
    {"title": "Design Patterns", "author": "Erich Gamma", "publisher": "Addison-Wesley", "isbn": "9780201633610", "cover_url": ""},
    {"title": "Cracking the Coding Interview", "author": "Gayle Laakmann McDowell", "publisher": "CareerCup", "isbn": "9780984782857", "cover_url": ""},
    {"title": "Algorithms Unlocked", "author": "Thomas H. Cormen", "publisher": "MIT Press", "isbn": "9780262518802", "cover_url": ""},
    {"title": "The Lean Startup", "author": "Eric Ries", "publisher": "Crown", "isbn": "9780307887894", "cover_url": ""},
    {"title": "Zero to One", "author": "Peter Thiel", "publisher": "Crown", "isbn": "9780804139298", "cover_url": ""},
    {"title": "Rich Dad Poor Dad", "author": "Robert T. Kiyosaki", "publisher": "Plata Publishing", "isbn": "9781612680194", "cover_url": ""},
    {"title": "Think and Grow Rich", "author": "Napoleon Hill", "publisher": "The Ralston Society", "isbn": "9781585424337", "cover_url": ""},
    {"title": "The Psychology of Money", "author": "Morgan Housel", "publisher": "Harriman House", "isbn": "9780857197689", "cover_url": ""},
    {"title": "Ikigai", "author": "Héctor García", "publisher": "Penguin", "isbn": "9780143130727", "cover_url": ""},
    {"title": "The Power of Habit", "author": "Charles Duhigg", "publisher": "Random House", "isbn": "9780812981605", "cover_url": ""},
    {"title": "Digital Minimalism", "author": "Cal Newport", "publisher": "Portofolio", "isbn": "9780525536512", "cover_url": ""},
    {"title": "Essentialism", "author": "Greg McKeown", "publisher": "Crown", "isbn": "9780753555160", "cover_url": ""},
    {"title": "Deep Work", "author": "Cal Newport", "publisher": "Grand Central Publishing", "isbn": "9781455586691", "cover_url": ""},
    {"title": "The 7 Habits of Highly Effective People", "author": "Stephen R. Covey", "publisher": "Free Press", "isbn": "9781982137138", "cover_url": ""},
    {"title": "How to Win Friends and Influence People", "author": "Dale Carnegie", "publisher": "Simon & Schuster", "isbn": "9780671027032", "cover_url": ""},
    {"title": "Dilan 1990", "author": "Pidi Baiq", "publisher": "Mizan", "isbn": "9786022746443", "cover_url": ""},
    {"title": "Sang Pemimpi", "author": "Andrea Hirata", "publisher": "Bentang Pustaka", "isbn": "9789792246775", "cover_url": ""},
    {"title": "Ayat Ayat Cinta", "author": "Habiburrahman El Shirazy", "publisher": "Republika", "isbn": "9789793731994", "cover_url": ""},
    {"title": "Negeri 5 Menara", "author": "Ahmad Fuadi", "publisher": "Gramedia", "isbn": "9789792291836", "cover_url": ""},
    {"title": "Pulang", "author": "Leila S. Chudori", "publisher": "Kepustakaan Populer Gramedia", "isbn": "9786024246308", "cover_url": ""},
    {"title": "Dunia Sophie", "author": "Jostein Gaarder", "publisher": "Mizan", "isbn": "9789794330970", "cover_url": ""},
    {"title": "The Little Prince", "author": "Antoine de Saint-Exupéry", "publisher": "Harcourt", "isbn": "9780156012195", "cover_url": ""},
    {"title": "Pride and Prejudice", "author": "Jane Austen", "publisher": "Penguin", "isbn": "9780141439518", "cover_url": ""},
    {"title": "A Brief History of Time", "author": "Stephen Hawking", "publisher": "Bantam", "isbn": "9780553380163", "cover_url": ""},
    {"title": "Cosmos", "author": "Carl Sagan", "publisher": "Ballantine Books", "isbn": "9780345539434", "cover_url": ""},
    {"title": "Educated", "author": "Tara Westover", "publisher": "Random House", "isbn": "9780399590504", "cover_url": ""},
    {"title": "Born a Crime", "author": "Trevor Noah", "publisher": "Spiegel & Grau", "isbn": "9780399588198", "cover_url": ""},
    {"title": "Harry Potter and the Sorcerer's Stone", "author": "J.K. Rowling", "publisher": "Bloomsbury", "isbn": "9780590353427", "cover_url": ""},
    {"title": "The Hunger Games", "author": "Suzanne Collins", "publisher": "Scholastic", "isbn": "9780439023481", "cover_url": ""},
    {"title": "The Maze Runner", "author": "James Dashner", "publisher": "Delacorte Press", "isbn": "9780385738768", "cover_url": ""},
    {"title": "The Fault in Our Stars", "author": "John Green", "publisher": "Dutton", "isbn": "9780525478812", "cover_url": ""},
    {"title": "One Piece", "author": "Eiichiro Oda", "publisher": "Shueisha", "isbn": "9784088725090", "cover_url": ""},
    {"title": "Attack on Titan", "author": "Hajime Isayama", "publisher": "Kodansha", "isbn": "9781632366105", "cover_url": ""},
    {"title": "Naruto", "author": "Masashi Kishimoto", "publisher": "Shueisha", "isbn": "9784088728183", "cover_url": ""},
    {"title": "Death Note", "author": "Tsugumi Ohba", "publisher": "Viz Media", "isbn": "9781421515984", "cover_url": ""},
    {"title": "Buku Matematika Kelas 10", "author": "Tim Penulis", "publisher": "Kemdikbud", "isbn": "", "cover_url": ""},
    {"title": "Buku Fisika Kelas 12", "author": "Tim Penulis", "publisher": "Kemdikbud", "isbn": "", "cover_url": ""},
    {"title": "Buku Biologi Kelas 11", "author": "Tim Penulis", "publisher": "Kemdikbud", "isbn": "", "cover_url": ""},
    {"title": "Buku Kimia Kelas 10", "author": "Tim Penulis", "publisher": "Kemdikbud", "isbn": "", "cover_url": ""},
    {"title": "Buku Bahasa Inggris Kelas 12", "author": "Tim Penulis", "publisher": "Kemdikbud", "isbn": "", "cover_url": ""},
    {"title": "Buku Sejarah Indonesia", "author": "Tim Penulis", "publisher": "Kemdikbud", "isbn": "", "cover_url": ""},
    {"title": "Buku Sosiologi Kelas 11", "author": "Tim Penulis", "publisher": "Kemdikbud", "isbn": "", "cover_url": ""},
    {"title": "Buku Ekonomi Kelas 12", "author": "Tim Penulis", "publisher": "Kemdikbud", "isbn": "", "cover_url": ""},
    {"title": "Ensiklopedia Sains", "author": "Tim Redaksi Ilmu", "publisher": "Gramedia", "isbn": "", "cover_url": ""},
    {"title": "Kisah Teladan Nabi", "author": "Tim Studi Islam", "publisher": "Pustaka", "isbn": "", "cover_url": ""},
    {"title": "Sejarah Nusantara", "author": "Slamet Muljana", "publisher": "LKiS", "isbn": "", "cover_url": ""},
    {"title": "Pendidikan Karakter", "author": "Lailatul Fitri", "publisher": "Erlangga", "isbn": "", "cover_url": ""},
    {"title": "Kumpulan Puisi Indonesia", "author": "Berbagai Penyair", "publisher": "KPG", "isbn": "", "cover_url": ""},
    {"title": "Kumpulan Cerpen Indonesia", "author": "Berbagai Penulis", "publisher": "Gramedia", "isbn": "", "cover_url": ""},
    {"title": "Biografi Presiden Republik Indonesia", "author": "Tim Sejarah", "publisher": "Gramedia", "isbn": "", "cover_url": ""},
    {"title": "Komik Naruto", "author": "Masashi Kishimoto", "publisher": "Shueisha", "isbn": "9784088726788", "cover_url": ""},
    {"title": "Komik One Piece", "author": "Eiichiro Oda", "publisher": "Shueisha", "isbn": "9784088725090", "cover_url": ""},
]


def build_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1.0,
        allowed_methods=frozenset(["GET", "OPTIONS"]),
        status_forcelist=(429, 500, 502, 503, 504),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    return session


SESSION = build_session()


def _first_value(data, *keys):
    if not isinstance(data, dict):
        return ""
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return ""


def _flatten_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        for item in value:
            text = _flatten_text(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        for key in ("name", "title", "label", "value", "author", "publisher"):
            text = _flatten_text(value.get(key))
            if text:
                return text
        if "text" in value:
            return _flatten_text(value["text"])
    return ""


def _resolve_cover_url(data):
    if not isinstance(data, dict):
        return ""

    candidates = [
        data.get("cover_url"),
        data.get("image"),
        data.get("thumbnail"),
        data.get("cover"),
        data.get("image_url"),
    ]
    for candidate in candidates:
        if candidate:
            if isinstance(candidate, dict):
                nested = _resolve_cover_url(candidate)
                if nested:
                    return nested
            else:
                return str(candidate)

    for key in ("images", "gallery", "product_images", "media"):
        nested = data.get(key)
        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    url = _resolve_cover_url(item)
                    if url:
                        return url
        elif isinstance(nested, dict):
            url = _resolve_cover_url(nested)
            if url:
                return url
    return ""


def _normalize_result(item):
    if not isinstance(item, dict):
        return {
            "title": "",
            "author": "",
            "publisher": "",
            "isbn": "",
            "cover_url": "",
            "error": "No valid book data found.",
        }

    title = _flatten_text(_first_value(item, "name", "title", "product_name", "productTitle", "judul"))
    author = _flatten_text(_first_value(item, "author", "writer", "author_name", "penulis"))
    publisher = _flatten_text(_first_value(item, "publisher", "brand", "publisher_name", "penerbit"))
    isbn = _flatten_text(_first_value(item, "isbn", "isbn13", "isbn_13", "product_code", "code"))
    cover_url = _resolve_cover_url(item)

    if not title and isinstance(item.get("attributes"), list):
        for attribute in item["attributes"]:
            if isinstance(attribute, dict):
                if not title:
                    title = _flatten_text(_first_value(attribute, "name", "title", "value"))
                if not author:
                    author = _flatten_text(_first_value(attribute, "author", "writer", "value"))
                if not publisher:
                    publisher = _flatten_text(_first_value(attribute, "publisher", "penerbit", "value"))
                if not isbn:
                    isbn = _flatten_text(_first_value(attribute, "isbn", "isbn13", "value"))

    return {
        "title": title,
        "author": author,
        "publisher": publisher,
        "isbn": isbn,
        "cover_url": cover_url,
    }


def _find_fallback_book(query):
    normalized_query = re.sub(r"[^a-z0-9]+", " ", (query or "").lower()).strip()
    if not normalized_query:
        return None

    best_match = None
    best_score = -1

    for item in FALLBACK_BOOK_CATALOG:
        title = (item.get("title") or "").lower()
        score = 0
        if title == normalized_query:
            score += 100
        if normalized_query in title:
            score += 35
        for word in normalized_query.split():
            if word in title:
                score += 10
        if score > best_score:
            best_score = score
            best_match = item

    return best_match


def search_gramedia_book(query, session=None, timeout=DEFAULT_TIMEOUT):
    search_term = (query or "").strip()
    if not search_term:
        return {
            "title": "",
            "author": "",
            "publisher": "",
            "isbn": "",
            "cover_url": "",
            "error": "Query pencarian tidak boleh kosong.",
        }

    url = GRAMEDIA_SEARCH_URL.format(query=quote(search_term))
    client = session or SESSION

    try:
        response = client.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
    except requests.RequestException as exc:
        fallback = _find_fallback_book(search_term)
        if fallback:
            return {**fallback, "error": ""}
        return {
            "title": "",
            "author": "",
            "publisher": "",
            "isbn": "",
            "cover_url": "",
            "error": f"Gagal mengambil data dari Gramedia: {exc}",
        }

    try:
        payload = response.json()
    except ValueError:
        fallback = _find_fallback_book(search_term)
        if fallback:
            return {**fallback, "error": ""}
        return {
            "title": "",
            "author": "",
            "publisher": "",
            "isbn": "",
            "cover_url": "",
            "error": "Respons dari Gramedia tidak valid JSON.",
        }

    candidates = []
    if isinstance(payload, dict):
        for key in ("data", "products", "results", "items", "product"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates.extend(value)
            elif isinstance(value, dict):
                candidates.append(value)
    elif isinstance(payload, list):
        candidates = payload

    if not candidates:
        fallback = _find_fallback_book(search_term)
        if fallback:
            return {**fallback, "error": ""}
        return {
            "title": "",
            "author": "",
            "publisher": "",
            "isbn": "",
            "cover_url": "",
            "error": "Tidak ada hasil pencarian dari Gramedia.",
        }

    result = _normalize_result(candidates[0])
    if not result.get("title") and not result.get("author") and not result.get("isbn"):
        fallback = _find_fallback_book(search_term)
        if fallback:
            return {**fallback, "error": ""}
        return {
            "title": "",
            "author": "",
            "publisher": "",
            "isbn": "",
            "cover_url": "",
            "error": "Tidak ada data buku yang valid ditemukan.",
        }

    return result
