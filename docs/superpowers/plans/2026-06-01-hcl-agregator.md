# HCL Agregator — Căutare Tematică — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI ingest tool + Streamlit search UI that indexes hotărârile Consiliului Local Sector 3 (2024–2026) from hcl.usr.ro into an SQLite FTS5 database and lets users find all HCL-uri relevante la un topic (cu alias-uri).

**Architecture:** `fetcher.py` wraps the two hcl.usr.ro API endpoints; `db.py` owns the SQLite schema (hcl_documente + FTS5 virtual table cu triggere + topicuri) and all queries; `ingest.py` is a thin orchestration script; `app.py` is the Streamlit UI. Topics and aliases live in `topics.yaml`. FTS5 sync is handled entirely by DB triggers — no manual index management in Python.

**Tech Stack:** Python 3.10+, SQLite3 (built-in) with FTS5, `requests`, `beautifulsoup4`, `pyyaml`, `streamlit`, `pytest`

---

## File Map

| File | Responsibility |
|------|---------------|
| `requirements.txt` | Python dependencies |
| `schema.sql` | Canonical schema SQL (single source of truth) |
| `db.py` | init_db, upsert_doc, search_fts, search_topic, load_topics |
| `fetcher.py` | get_doc_list, get_doc_text, strip_html |
| `ingest.py` | Orchestrates download + DB insert for years 2024–2026 |
| `topics.yaml` | Topic definitions with Romanian aliases |
| `app.py` | Streamlit UI with free-text and topic-based search tabs |
| `tests/test_db.py` | DB schema, upsert, FTS search, trigger tests |
| `tests/test_fetcher.py` | Fetcher tests (mocked HTTP) |
| `tests/test_topics.py` | Topic alias expansion tests |

---

## Schema (referință pentru toate task-urile)

```sql
-- hcl_documente: un rând per hotărâre
CREATE TABLE IF NOT EXISTS hcl_documente (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id   TEXT UNIQUE,      -- id de la api_getdocument
    an            INTEGER,
    numar_hcl     TEXT,
    data_adoptare TEXT,
    titlu         TEXT,
    text_complet  TEXT,
    url_original  TEXT
);

CREATE TABLE IF NOT EXISTS topicuri (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nume     TEXT UNIQUE,
    aliasuri TEXT                   -- JSON: ["alias1","alias2",...]
);

-- FTS5 cu content table; rowid = hcl_documente.id
CREATE VIRTUAL TABLE IF NOT EXISTS hcl_fts USING fts5(
    titlu, text_complet,
    content='hcl_documente', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

-- Triggere de sincronizare FTS <-> tabel principal
CREATE TRIGGER IF NOT EXISTS hcl_ai AFTER INSERT ON hcl_documente BEGIN
    INSERT INTO hcl_fts(rowid, titlu, text_complet)
    VALUES (new.id, new.titlu, new.text_complet);
END;
CREATE TRIGGER IF NOT EXISTS hcl_ad AFTER DELETE ON hcl_documente BEGIN
    INSERT INTO hcl_fts(hcl_fts, rowid, titlu, text_complet)
    VALUES ('delete', old.id, old.titlu, old.text_complet);
END;
CREATE TRIGGER IF NOT EXISTS hcl_au AFTER UPDATE ON hcl_documente BEGIN
    INSERT INTO hcl_fts(hcl_fts, rowid, titlu, text_complet)
    VALUES ('delete', old.id, old.titlu, old.text_complet);
    INSERT INTO hcl_fts(rowid, titlu, text_complet)
    VALUES (new.id, new.titlu, new.text_complet);
END;
```

---

## Task 1: Project Bootstrap

**Files:**
- Create: `requirements.txt`
- Create: `schema.sql`
- Create: `tests/__init__.py`
- Create: `topics.yaml`

- [ ] **Step 1.1: Create requirements.txt**

```
requests>=2.31.0
beautifulsoup4>=4.12.0
pyyaml>=6.0
streamlit>=1.32.0
pytest>=8.0.0
```

- [ ] **Step 1.2: Install dependencies**

```
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 1.3: Create schema.sql**

```sql
CREATE TABLE IF NOT EXISTS hcl_documente (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id   TEXT UNIQUE,
    an            INTEGER,
    numar_hcl     TEXT,
    data_adoptare TEXT,
    titlu         TEXT,
    text_complet  TEXT,
    url_original  TEXT
);

CREATE TABLE IF NOT EXISTS topicuri (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    nume     TEXT UNIQUE,
    aliasuri TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS hcl_fts USING fts5(
    titlu, text_complet,
    content='hcl_documente', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS hcl_ai AFTER INSERT ON hcl_documente BEGIN
    INSERT INTO hcl_fts(rowid, titlu, text_complet)
    VALUES (new.id, new.titlu, new.text_complet);
END;
CREATE TRIGGER IF NOT EXISTS hcl_ad AFTER DELETE ON hcl_documente BEGIN
    INSERT INTO hcl_fts(hcl_fts, rowid, titlu, text_complet)
    VALUES ('delete', old.id, old.titlu, old.text_complet);
END;
CREATE TRIGGER IF NOT EXISTS hcl_au AFTER UPDATE ON hcl_documente BEGIN
    INSERT INTO hcl_fts(hcl_fts, rowid, titlu, text_complet)
    VALUES ('delete', old.id, old.titlu, old.text_complet);
    INSERT INTO hcl_fts(rowid, titlu, text_complet)
    VALUES (new.id, new.titlu, new.text_complet);
END;
```

- [ ] **Step 1.4: Create tests/__init__.py (empty file)**

- [ ] **Step 1.5: Create topics.yaml with initial Sector 3 topics**

```yaml
- nume: Hala Laminor
  aliasuri:
    - laminor
    - parc industrial
    - Dudesti-Pantelimon
    - Sos. Dudesti

- nume: RADET
  aliasuri:
    - termoficare
    - agent termic
    - centrala termica
    - energie termica

- nume: Parcul IOR
  aliasuri:
    - IOR
    - parc IOR
    - Titan

- nume: Pasajul Mihai Bravu
  aliasuri:
    - pasaj
    - Mihai Bravu

- nume: Buget local
  aliasuri:
    - rectificare bugetara
    - bugetul local
    - credite bugetare
```

- [ ] **Step 1.6: Commit**

```bash
git add requirements.txt schema.sql tests/__init__.py topics.yaml
git commit -m "chore: project bootstrap — deps, schema, initial topics"
```

---

## Task 2: Database Module

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

- [ ] **Step 2.1: Write failing tests**

Create `tests/test_db.py`:

```python
import json
import pytest
from db import init_db, upsert_doc, search_fts


def _doc(document_id, titlu, text_complet, data_adoptare="2026-01-05", an=2026):
    return {
        "document_id": str(document_id),
        "an": an,
        "numar_hcl": str(document_id),
        "data_adoptare": data_adoptare,
        "titlu": titlu,
        "text_complet": text_complet,
        "url_original": f"https://example.com/{document_id}",
    }


def test_init_db_creates_tables(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = {row[0] for row in cur.fetchall()}
    assert "hcl_documente" in names
    assert "topicuri" in names


def test_init_db_creates_fts(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE name='hcl_fts'"
    )
    assert cur.fetchone() is not None


def test_init_db_creates_triggers(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
    names = {row[0] for row in cur.fetchall()}
    assert {"hcl_ai", "hcl_ad", "hcl_au"}.issubset(names)


def test_upsert_doc_inserts_row(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(1, "Hotarare privind Hala Laminor",
                          "Se aproba proiectul Hala Laminor din Sectorul 3"))
    conn.commit()
    cur = conn.execute(
        "SELECT document_id, titlu FROM hcl_documente WHERE document_id = '1'"
    )
    row = cur.fetchone()
    assert row is not None
    assert row[1] == "Hotarare privind Hala Laminor"


def test_upsert_doc_is_idempotent(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(1, "Titlu initial", "Text initial"))
    conn.commit()
    upsert_doc(conn, _doc(1, "Titlu actualizat", "Text actualizat"))
    conn.commit()
    cur = conn.execute("SELECT COUNT(*) FROM hcl_documente")
    assert cur.fetchone()[0] == 1


def test_trigger_indexes_on_insert(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(1, "Hotarare Laminor", "Parc industrial Dudesti"))
    conn.commit()
    # FTS entry must exist (trigger hcl_ai fired)
    cur = conn.execute(
        "SELECT COUNT(*) FROM hcl_fts WHERE hcl_fts MATCH 'Laminor'"
    )
    assert cur.fetchone()[0] == 1


def test_search_fts_finds_document(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(1, "Hotarare privind Hala Laminor",
                          "Se aproba proiectul Hala Laminor din Sectorul 3"))
    conn.commit()
    results = search_fts(conn, "Laminor")
    assert len(results) == 1
    assert results[0]["document_id"] == "1"
    assert results[0]["titlu"] == "Hotarare privind Hala Laminor"
    assert "url_original" in results[0]
    assert "data_adoptare" in results[0]


def test_search_fts_diacritics_insensitive(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(1, "Hotărâre privind bugetul",
                          "Consiliul local aprobă bugetul local"))
    conn.commit()
    # Search without diacritics should find doc with diacritics
    results = search_fts(conn, "hotarare")
    assert len(results) == 1
    results2 = search_fts(conn, "aproba")
    assert len(results2) == 1


def test_search_fts_no_results(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    results = search_fts(conn, "inexistentxyz")
    assert results == []


def test_search_fts_bad_query_returns_empty(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    results = search_fts(conn, "OR AND")
    assert results == []


def test_search_fts_ordered_chronologically(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(2, "Hotarare laminor martie", "laminor",
                          data_adoptare="2026-03-01"))
    upsert_doc(conn, _doc(1, "Hotarare laminor ianuarie", "laminor",
                          data_adoptare="2026-01-01"))
    conn.commit()
    results = search_fts(conn, "laminor")
    assert results[0]["document_id"] == "1"
    assert results[1]["document_id"] == "2"
```

- [ ] **Step 2.2: Run tests to verify they fail**

```
pytest tests/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'db'`

- [ ] **Step 2.3: Create db.py**

```python
import json
import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    return conn


def upsert_doc(conn: sqlite3.Connection, doc: dict) -> None:
    """Insert or update one HCL document. FTS sync is handled by DB triggers."""
    conn.execute(
        """
        INSERT INTO hcl_documente
            (document_id, an, numar_hcl, data_adoptare, titlu, text_complet, url_original)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(document_id) DO UPDATE SET
            an            = excluded.an,
            numar_hcl     = excluded.numar_hcl,
            data_adoptare = excluded.data_adoptare,
            titlu         = excluded.titlu,
            text_complet  = excluded.text_complet,
            url_original  = excluded.url_original
        """,
        (
            doc["document_id"], doc["an"], doc["numar_hcl"],
            doc["data_adoptare"], doc["titlu"],
            doc["text_complet"], doc["url_original"],
        ),
    )


def search_fts(conn: sqlite3.Connection, query: str, limit: int = 50) -> list:
    try:
        cur = conn.execute(
            """
            SELECT d.document_id, d.numar_hcl, d.data_adoptare,
                   d.titlu, d.url_original, d.an
            FROM hcl_fts
            JOIN hcl_documente d ON hcl_fts.rowid = d.id
            WHERE hcl_fts MATCH ?
            ORDER BY d.data_adoptare ASC
            LIMIT ?
            """,
            (query, limit),
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except sqlite3.OperationalError:
        return []


def search_topic(conn: sqlite3.Connection, topic_name: str, limit: int = 50) -> list:
    cur = conn.execute(
        "SELECT aliasuri FROM topicuri WHERE lower(nume) = lower(?)",
        (topic_name,),
    )
    row = cur.fetchone()
    terms = [topic_name]
    if row and row[0]:
        terms.extend(json.loads(row[0]))

    fts_query = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)
    return search_fts(conn, fts_query, limit)


def load_topics(conn: sqlite3.Connection, yaml_path: str) -> int:
    import yaml
    with open(yaml_path, encoding="utf-8") as f:
        topics = yaml.safe_load(f)
    conn.execute("DELETE FROM topicuri")
    for t in topics:
        conn.execute(
            "INSERT INTO topicuri (nume, aliasuri) VALUES (?, ?)",
            (t["nume"], json.dumps(t.get("aliasuri", []))),
        )
    conn.commit()
    return len(topics)
```

- [ ] **Step 2.4: Run tests to verify they all pass**

```
pytest tests/test_db.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 2.5: Commit**

```bash
git add schema.sql db.py tests/test_db.py
git commit -m "feat: SQLite schema with FTS5 triggers and db module"
```

---

## Task 3: Fetcher Module

**Files:**
- Create: `fetcher.py`
- Create: `tests/test_fetcher.py`

- [ ] **Step 3.1: Write failing tests**

Create `tests/test_fetcher.py`:

```python
from unittest.mock import patch, Mock
from fetcher import get_doc_list, get_doc_text, strip_html


def test_strip_html_removes_tags():
    html = "<h3>MUNICIPIUL BUCUREȘTI</h3><p>Text continut hotarare</p>"
    result = strip_html(html)
    assert "MUNICIPIUL BUCUREȘTI" in result
    assert "Text continut hotarare" in result
    assert "<h3>" not in result
    assert "<p>" not in result


def test_strip_html_handles_empty():
    assert strip_html("") == ""


def test_strip_html_handles_plain_text():
    assert strip_html("plain text") == "plain text"


def test_get_doc_list_parses_response():
    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {
        "success": True, "entity": "4420465", "year": 2026, "count": 2,
        "decisions": [
            {
                "DecisionID": 385553, "Number": 1, "DecisionType": "HOTA",
                "DecisionDate": "2026-01-05", "Title": "HCLS3 nr.1 din 05.01.2026",
                "DocumentID": 504282, "DocumentTYpe": "MAIN",
                "AnnexNumber": 0, "LinkExternal": "https://example.com/1.pdf"
            },
            {
                "DecisionID": 387015, "Number": 5, "DecisionType": "PRVB",
                "DecisionDate": "2026-01-05", "Title": "Proces-verbal nr.5",
                "DocumentID": 504290, "DocumentTYpe": "MAIN",
                "AnnexNumber": 0, "LinkExternal": "https://example.com/5.pdf"
            }
        ]
    }
    with patch("fetcher.requests.get", return_value=mock_resp):
        decisions = get_doc_list("4420465", 2026)
    assert len(decisions) == 2
    assert decisions[0]["DocumentID"] == 504282
    assert decisions[0]["DecisionDate"] == "2026-01-05"


def test_get_doc_list_calls_correct_url():
    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.json.return_value = {"success": True, "decisions": []}
    with patch("fetcher.requests.get", return_value=mock_resp) as mock_get:
        get_doc_list("4420465", 2024)
    mock_get.assert_called_once_with(
        "https://hcl.usr.ro/api_getdoclist.php?entity=4420465&year=2024",
        timeout=30,
    )


def test_get_doc_text_strips_html():
    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.text = "<h1>Hotarare</h1><p>Continut hotarare Sector 3</p>"
    with patch("fetcher.requests.get", return_value=mock_resp):
        text = get_doc_text(12345)
    assert "Hotarare" in text
    assert "Continut hotarare Sector 3" in text
    assert "<h1>" not in text


def test_get_doc_text_calls_correct_url():
    mock_resp = Mock()
    mock_resp.raise_for_status = Mock()
    mock_resp.text = "<p>text</p>"
    with patch("fetcher.requests.get", return_value=mock_resp) as mock_get:
        get_doc_text(99999)
    mock_get.assert_called_once_with(
        "https://hcl.usr.ro/api_getdocument.php?documentid=99999",
        timeout=30,
    )
```

- [ ] **Step 3.2: Run tests to verify they fail**

```
pytest tests/test_fetcher.py -v
```

Expected: `ModuleNotFoundError: No module named 'fetcher'`

- [ ] **Step 3.3: Create fetcher.py**

```python
import requests
from bs4 import BeautifulSoup

BASE_LIST = "https://hcl.usr.ro/api_getdoclist.php"
BASE_DOC  = "https://hcl.usr.ro/api_getdocument.php"


def get_doc_list(entity: str, year: int) -> list:
    resp = requests.get(f"{BASE_LIST}?entity={entity}&year={year}", timeout=30)
    resp.raise_for_status()
    return resp.json()["decisions"]


def get_doc_text(document_id: int) -> str:
    resp = requests.get(f"{BASE_DOC}?documentid={document_id}", timeout=30)
    resp.raise_for_status()
    return strip_html(resp.text)


def strip_html(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)
```

- [ ] **Step 3.4: Run tests to verify they pass**

```
pytest tests/test_fetcher.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 3.5: Commit**

```bash
git add fetcher.py tests/test_fetcher.py
git commit -m "feat: fetcher module with HTML stripping"
```

---

## Task 4: Topics Support

**Files:**
- Create: `tests/test_topics.py`

- [ ] **Step 4.1: Write failing tests**

Create `tests/test_topics.py`:

```python
import json
import pytest
from db import init_db, upsert_doc, search_topic, load_topics


def _doc(document_id, titlu, text_complet, data_adoptare=None):
    return {
        "document_id": str(document_id),
        "an": 2026,
        "numar_hcl": str(document_id),
        "data_adoptare": data_adoptare or f"2026-0{document_id}-01",
        "titlu": titlu,
        "text_complet": text_complet,
        "url_original": f"https://example.com/{document_id}",
    }


def test_search_topic_finds_by_alias(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(1, "Hotarare privind parcul industrial",
                          "Se aproba proiectul parc industrial Dudesti-Pantelimon"))
    upsert_doc(conn, _doc(2, "Hotarare privind bugetul",
                          "Se aproba rectificarea bugetara pentru 2026"))
    conn.execute(
        "INSERT INTO topicuri (nume, aliasuri) VALUES (?, ?)",
        ("Hala Laminor", json.dumps(["parc industrial", "laminor"])),
    )
    conn.commit()
    results = search_topic(conn, "Hala Laminor")
    assert len(results) == 1
    assert results[0]["document_id"] == "1"


def test_search_topic_no_alias_match(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(1, "Alt subiect", "Nu contine termeni relevanti"))
    conn.execute(
        "INSERT INTO topicuri (nume, aliasuri) VALUES (?, ?)",
        ("Hala Laminor", json.dumps(["laminor"])),
    )
    conn.commit()
    assert search_topic(conn, "Hala Laminor") == []


def test_search_topic_unknown_topic_uses_name(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(1, "Hotarare laminor", "Text despre laminor"))
    conn.commit()
    results = search_topic(conn, "laminor")
    assert len(results) == 1


def test_search_topic_results_ordered_by_date(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(10, "Laminor martie", "laminor", "2026-03-01"))
    upsert_doc(conn, _doc(5,  "Laminor ianuarie", "laminor", "2026-01-01"))
    conn.commit()
    results = search_topic(conn, "laminor")
    assert results[0]["document_id"] == "5"
    assert results[1]["document_id"] == "10"


def test_load_topics_from_yaml(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    yaml_path = tmp_path / "topics.yaml"
    yaml_path.write_text(
        "- nume: Test Topic\n  aliasuri:\n    - alias1\n    - alias2\n",
        encoding="utf-8",
    )
    count = load_topics(conn, str(yaml_path))
    assert count == 1
    cur = conn.execute("SELECT aliasuri FROM topicuri WHERE nume = 'Test Topic'")
    row = cur.fetchone()
    assert row is not None
    assert json.loads(row[0]) == ["alias1", "alias2"]


def test_load_topics_replaces_existing(tmp_path):
    conn = init_db(str(tmp_path / "test.db"))
    conn.execute("INSERT INTO topicuri (nume, aliasuri) VALUES ('Old', '[]')")
    conn.commit()
    yaml_path = tmp_path / "topics.yaml"
    yaml_path.write_text("- nume: New Topic\n  aliasuri: []\n", encoding="utf-8")
    load_topics(conn, str(yaml_path))
    cur = conn.execute("SELECT COUNT(*) FROM topicuri")
    assert cur.fetchone()[0] == 1
    cur = conn.execute("SELECT nume FROM topicuri")
    assert cur.fetchone()[0] == "New Topic"
```

- [ ] **Step 4.2: Run ALL tests to confirm topics tests pass**

```
pytest tests/ -v
```

Expected: all tests PASS — test_topics uses functions already implemented in db.py (Task 2).

- [ ] **Step 4.3: Commit**

```bash
git add tests/test_topics.py
git commit -m "test: topic alias expansion and load_topics coverage"
```

---

## Task 5: Ingest Script

**Files:**
- Create: `ingest.py`

- [ ] **Step 5.1: Create ingest.py**

```python
import sys
import time
import sqlite3
from db import init_db, upsert_doc, load_topics
from fetcher import get_doc_list, get_doc_text

ENTITY     = "4420465"
YEARS      = [2024, 2025, 2026]
DB_PATH    = "hcl.db"
TOPICS_PATH = "topics.yaml"
RATE_LIMIT_S = 0.3


def already_fetched(conn: sqlite3.Connection, document_id: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM hcl_documente WHERE document_id = ?", (document_id,)
    )
    return cur.fetchone() is not None


def main() -> None:
    conn = init_db(DB_PATH)

    try:
        n = load_topics(conn, TOPICS_PATH)
        print(f"[topics] {n} topics loaded from {TOPICS_PATH}")
    except FileNotFoundError:
        print(f"[topics] {TOPICS_PATH} not found, skipping")

    total_new = total_skip = total_err = 0

    for year in YEARS:
        print(f"\n[{year}] fetching list...")
        try:
            decisions = get_doc_list(ENTITY, year)
        except Exception as e:
            print(f"[{year}] ERROR: {e}", file=sys.stderr)
            continue
        print(f"[{year}] {len(decisions)} decisions found")

        for dec in decisions:
            doc_id = dec.get("DocumentID")
            if not doc_id:
                continue

            if already_fetched(conn, str(doc_id)):
                total_skip += 1
                continue

            try:
                text = get_doc_text(doc_id)
                upsert_doc(conn, {
                    "document_id": str(doc_id),
                    "an":          year,
                    "numar_hcl":   str(dec["Number"]),
                    "data_adoptare": dec["DecisionDate"],
                    "titlu":       dec["Title"],
                    "text_complet": text,
                    "url_original": dec.get("LinkExternal") or "",
                })
                conn.commit()
                total_new += 1
                print(f"  [OK] {doc_id}: {dec['Title'][:60]}")
                time.sleep(RATE_LIMIT_S)
            except Exception as e:
                total_err += 1
                print(f"  [ERR] {doc_id}: {e}", file=sys.stderr)

    print(f"\nDone. new={total_new}  skipped={total_skip}  errors={total_err}")
    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5.2: Smoke-test — run ingest for one year only (editează temporar YEARS = [2026])**

```
python ingest.py
```

Expected output (prima rulare, ~155 docs pentru 2026):
```
[topics] 5 topics loaded from topics.yaml

[2026] fetching list...
[2026] 155 decisions found
  [OK] 504282: HCLS3 nr.1 din 05.01.2026
  ...
Done. new=155  skipped=0  errors=0
```

Rulând din nou: `skipped=155  new=0` (idempotent).

- [ ] **Step 5.3: Revine YEARS la [2024, 2025, 2026] și commit**

```bash
git add ingest.py
git commit -m "feat: ingest script — downloads and indexes HCL docs into SQLite FTS5"
```

---

## Task 6: Streamlit UI

**Files:**
- Create: `app.py`

- [ ] **Step 6.1: Create app.py**

```python
import streamlit as st
from db import init_db, search_fts, search_topic

DB_PATH = "hcl.db"

st.set_page_config(
    page_title="HCL Sector 3 — Căutare tematică",
    layout="wide",
)

st.title("Hotărâri Consiliu Local Sector 3")
st.caption("Sursă: hcl.usr.ro · Perioade indexate: 2024–2026")


@st.cache_resource
def get_conn():
    return init_db(DB_PATH)


conn = get_conn()


def render_results(results: list) -> None:
    if not results:
        st.info("Niciun rezultat.")
        return
    st.success(f"{len(results)} hotărâri găsite")
    for r in results:
        url   = r.get("url_original") or ""
        data  = r.get("data_adoptare", "")
        titlu = r.get("titlu") or "—"
        if url:
            st.markdown(f"**[{titlu}]({url})** &nbsp; `{data}`")
        else:
            st.markdown(f"**{titlu}** &nbsp; `{data}`")


tab_free, tab_topic = st.tabs(["Căutare liberă", "Căutare pe topic"])

with tab_free:
    st.markdown("Caută direct în textul hotărârilor. Funcționează cu sau fără diacritice.")
    query = st.text_input(
        "Termen de căutare:",
        placeholder='ex: "Hala Laminor" sau termoficare',
        key="free_query",
    )
    if query:
        render_results(search_fts(conn, query))

with tab_topic:
    st.markdown("Alege un topic predefinit — căutarea include automat toate alias-urile.")
    cur = conn.execute("SELECT nume FROM topicuri ORDER BY nume")
    topics = [row[0] for row in cur.fetchall()]
    if not topics:
        st.warning(
            "Niciun topic definit. Adaugă în `topics.yaml` și rulează `python ingest.py`."
        )
    else:
        topic = st.selectbox("Topic:", topics)
        if topic:
            render_results(search_topic(conn, topic))
```

- [ ] **Step 6.2: Pornește app-ul și verifică manual**

```
streamlit run app.py
```

Expected: browser la `http://localhost:8501`. Tab "Căutare liberă": tastează `laminor` → rezultate. Tab "Căutare pe topic": selectează "Hala Laminor" → rezultate cu alias-uri incluse. Verifică că link-urile duc la PDF-uri pe primarie3.ro.

- [ ] **Step 6.3: Commit**

```bash
git add app.py
git commit -m "feat: Streamlit UI with free-text and topic-based search tabs"
```

---

## Task 7: Deploy pe Streamlit Community Cloud

**Files:**
- Create: `.gitignore`
- Create: `README.md` (minimal, pentru Streamlit Cloud)

- [ ] **Step 7.1: Creează .gitignore**

```
__pycache__/
*.pyc
.env
*.db-journal
```

Notă: `hcl.db` **nu** este ignorat — îl commitem pentru deploy.

- [ ] **Step 7.2: Rulează ingest complet (2024–2026)**

```
python ingest.py
```

Expected final:
```
Done. new=~600  skipped=0  errors=0
```

Verifică mărimea bazei de date:
```
python -c "import os; print(f'{os.path.getsize(\"hcl.db\")/1e6:.1f} MB')"
```

Expected: sub 100 MB (limita GitHub per fișier). Dacă depășește, revino cu întrebare înainte de Step 7.3.

- [ ] **Step 7.3: Inițializează repo Git și push pe GitHub**

```bash
git init
git add .
git commit -m "feat: initial release — HCL aggregator Sector 3 2024-2026"
```

Creează un repo nou privat pe GitHub (fără README, fără .gitignore), apoi:
```bash
git remote add origin https://github.com/<username>/hcl-sector3.git
git branch -M main
git push -u origin main
```

- [ ] **Step 7.4: Deploy pe Streamlit Community Cloud**

1. Mergi la [share.streamlit.io](https://share.streamlit.io) și conectează-ți contul GitHub.
2. Click **"New app"** → selectează repo-ul `hcl-sector3` → branch `main` → Main file: `app.py`.
3. Click **"Deploy"** — primul deploy durează 2-3 minute.
4. URL-ul aplicației (ex: `https://hcl-sector3.streamlit.app`) → trimite colegilor.

- [ ] **Step 7.5: Verifică app-ul deployed**

Deschide URL-ul în browser. Verifică:
- Tab "Căutare liberă": tastează `termoficare` → rezultate cu linkuri.
- Tab "Căutare pe topic": selectează "RADET" → rezultate cu alias-uri.
- Click pe un link → se deschide PDF-ul de pe primarie3.ro.

- [ ] **Step 7.6: Commit final**

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
git push
```

### Update lunar (procedură pentru Eugen)

Când apar HCL-uri noi (ex. după ședința de consiliu):
```bash
python ingest.py          # adaugă docs noi, sare peste cele existente
git add hcl.db
git commit -m "data: update HCL $(date +%Y-%m)"
git push                  # Streamlit Cloud redeployează automat în ~2 minute
```

---

## Self-Review Against Spec

| Cerință spec | Task care o acoperă |
|-------------|---------------------|
| API lista: entity=4420465&year=YYYY | Task 3 — fetcher.get_doc_list |
| API document: documentid=ID | Task 3 — fetcher.get_doc_text |
| Text OCR de pe site (fără OCR local) | Task 3 — strip_html păstrează textul, elimină HTML |
| Ani 2024–2026 (extensibil la 2016) | Task 5 — YEARS = [2024, 2025, 2026], simplu de extins |
| Salvăm text brut + FTS5 | Task 1/2 — schema.sql + db.py cu triggere |
| Link la HCL original | schema `url_original`; Task 6 — render_results |
| Topicuri cu alias-uri | Task 2 — topicuri table + search_topic; Task 4 — YAML |
| `hcl_documente`, `topicuri`, FTS5 | Task 1/2 — schema exact ca spec + triggere |
| `python ingest.py` | Task 5 |
| `streamlit run app.py` | Task 6 |
| remove_diacritics (hotarare = hotărâre) | Task 1/2 — tokenize='unicode61 remove_diacritics 2' + test_search_fts_diacritics_insensitive |
| URL public accesibil colegilor | Task 7 — Streamlit Community Cloud deploy |
| Update ușor la date noi | Task 7 — procedură git push → redeploy automat |
