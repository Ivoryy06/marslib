import json
import os
import time
from typing import Iterable

from app import app, db, Book
from gramedia_client import REQUEST_DELAY_SECONDS, RETRY_EVERY_BOOKS, build_session, search_gramedia_book


def sync_titles(titles: Iterable[str], max_per_query: int = 50):
    synced = []
    seen = set()
    session = build_session()

    with app.app_context():
        for index, raw_title in enumerate(titles, start=1):
            title = (raw_title or "").strip()
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
            if not book_title:
                continue

            if Book.query.filter_by(title=book_title).first():
                continue

            book = Book(
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
            db.session.add(book)
            synced.append({
                "title": book_title,
                "author": book.author,
                "publisher": book.publisher,
                "isbn": book.isbn,
                "cover_url": book.cover_url,
            })

            if len(synced) >= max_per_query:
                break

        db.session.commit()
        return synced


if __name__ == "__main__":
    default_titles = [
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
        "Design Patterns",
        "Cracking the Coding Interview",
        "Algorithms Unlocked",
        "The Lean Startup",
        "Zero to One",
        "Rich Dad Poor Dad",
        "Think and Grow Rich",
        "The Psychology of Money",
        "Ikigai",
        "The Power of Habit",
        "Digital Minimalism",
        "Essentialism",
        "Deep Work",
        "The 7 Habits of Highly Effective People",
        "How to Win Friends and Influence People",
        "Dilan 1990",
        "Sang Pemimpi",
        "Ayat Ayat Cinta",
        "Negeri 5 Menara",
        "Pulang",
        "Dunia Sophie",
        "The Little Prince",
        "Pride and Prejudice",
        "A Brief History of Time",
        "Cosmos",
        "Educated",
        "Born a Crime",
        "Harry Potter and the Sorcerer's Stone",
        "The Hunger Games",
        "The Maze Runner",
        "The Fault in Our Stars",
        "One Piece",
        "Attack on Titan",
        "Naruto",
        "Death Note",
        "Buku Matematika Kelas 10",
        "Buku Fisika Kelas 12",
        "Buku Biologi Kelas 11",
        "Buku Kimia Kelas 10",
        "Buku Bahasa Inggris Kelas 12",
        "Buku Sejarah Indonesia",
        "Buku Sosiologi Kelas 11",
        "Buku Ekonomi Kelas 12",
        "Ensiklopedia Sains",
        "Kisah Teladan Nabi",
        "Sejarah Nusantara",
        "Pendidikan Karakter",
        "Kumpulan Puisi Indonesia",
        "Kumpulan Cerpen Indonesia",
        "Biografi Presiden Republik Indonesia",
        "Komik Naruto",
        "Komik One Piece",
    ]

    titles = os.getenv("GRAMEDIA_TITLES")
    if titles:
        source = [part.strip() for part in titles.split("|") if part.strip()]
    else:
        source = default_titles

    imported = sync_titles(source)
    print(json.dumps({"ok": True, "count": len(imported), "books": imported}, ensure_ascii=False))
