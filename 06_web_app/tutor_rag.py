"""Persistent vector index for shared teaching material (UTF-8 text and Markdown)."""

import argparse
import hashlib
import json
import math
import os
from contextlib import closing
from pathlib import Path
import sqlite3
import urllib.request

EMBEDDING_MODEL = "gemini-embedding-001"
DIMENSIONS = 768


def index_path():
    default = Path(__file__).resolve().parent / "tutor_index.sqlite3"
    return Path(os.getenv("TUTOR_INDEX_PATH") or default).resolve()


def gemini_request(key, model, action, payload):
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{action}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read())


def embed(key, text, task):
    result = gemini_request(key, EMBEDDING_MODEL, "embedContent", {
        "content": {"parts": [{"text": text}]},
        "taskType": task,
        "outputDimensionality": DIMENSIONS,
    })
    values = result["embedding"]["values"]
    if len(values) != DIMENSIONS or not all(math.isfinite(value) for value in values) or not any(values):
        raise ValueError("Invalid embedding")
    return values


def connect(path, *, create=False):
    import sqlite_vec

    connection = sqlite3.connect(path.as_uri() + ("?mode=rwc" if create else "?mode=ro"), uri=True)
    try:
        connection.enable_load_extension(True)
        try:
            sqlite_vec.load(connection)
        finally:
            connection.enable_load_extension(False)
        connection.row_factory = sqlite3.Row
        return connection
    except Exception:
        connection.close()
        raise


def chunks(text):
    text = " ".join(text.split())
    while len(text) > 1100:
        end = text.rfind(" ", 800, 1101)
        end = end if end >= 0 else 1100
        yield text[:end]
        start = text.find(" ", end - 140, end)
        text = text[start + 1 if start >= 0 else end:].lstrip()
    if text:
        yield text


def ingest(path, key, source, title, text):
    parts = list(chunks(text))
    if not parts:
        raise ValueError("Empty document")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    from sqlite_vec import serialize_float32

    with closing(connect(path, create=True)) as db:
        db.executescript(f"""
            CREATE TABLE IF NOT EXISTS documents (
                source TEXT PRIMARY KEY, title TEXT NOT NULL, digest TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY, source TEXT NOT NULL, ordinal INTEGER NOT NULL, text TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS chunks_source ON chunks(source);
            CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING vec0(embedding float[{DIMENSIONS}] distance_metric=cosine);
        """)
        existing = db.execute("SELECT digest, title FROM documents WHERE source = ?", (source,)).fetchone()
        if existing and tuple(existing) == (digest, title):
            return len(parts)
        vectors = [serialize_float32(embed(key, f"{title}\n{part}", "RETRIEVAL_DOCUMENT")) for part in parts]
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM vectors WHERE rowid IN (SELECT id FROM chunks WHERE source = ?)", (source,))
            db.execute("DELETE FROM chunks WHERE source = ?", (source,))
            db.execute("INSERT OR REPLACE INTO documents VALUES (?, ?, ?)", (source, title, digest))
            for ordinal, (part, vector) in enumerate(zip(parts, vectors), 1):
                row = db.execute("INSERT INTO chunks(source, ordinal, text) VALUES (?, ?, ?)", (source, ordinal, part))
                db.execute("INSERT INTO vectors(rowid, embedding) VALUES (?, ?)", (row.lastrowid, vector))
    return len(parts)


def search(key, query):
    path = index_path()
    if not path.is_file():
        return []
    from sqlite_vec import serialize_float32

    with closing(connect(path)) as db:
        if not db.execute("SELECT 1 FROM chunks LIMIT 1").fetchone():
            return []
        vector = serialize_float32(embed(key, query, "RETRIEVAL_QUERY"))
        rows = db.execute("""
            WITH nearest AS (
                SELECT rowid, distance FROM vectors WHERE embedding MATCH ? AND k = 4
            )
            SELECT d.title, c.source, c.ordinal, c.text, n.distance
            FROM nearest n JOIN chunks c ON c.id = n.rowid
            JOIN documents d ON d.source = c.source
            WHERE n.distance <= ?
            ORDER BY n.distance, c.id
        """, (vector, float(os.getenv("TUTOR_MAX_COSINE_DISTANCE", "0.40"))))
        return [dict(row) for row in rows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--source", required=True, help="Stable public ID for replacing a document")
    parser.add_argument("--title", help="Title shown in citations")
    args = parser.parse_args()
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        parser.error("Set GEMINI_API_KEY before ingesting documents")
    if args.file.suffix.lower() not in {".txt", ".md"}:
        parser.error("Supported formats: .txt and .md")
    title = " ".join((args.title or args.file.stem).split())
    source = " ".join(args.source.split())
    if not title or not source:
        parser.error("Title and source must be non-empty")
    count = ingest(index_path(), key, source, title, args.file.read_text(encoding="utf-8-sig"))
    print(f"{source}: {count} chunks in {index_path()}")


if __name__ == "__main__":
    main()
