import json
import re
import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Obiectul real al hotărârii apare în text ca „HOTĂRÂRE privind ...", urmat de
# preambul („Consiliul Local...", „Având în vedere...", etc.). Pentru ședințe
# extragem antetul procesului-verbal.
_OBIECT_RE = re.compile(r"HOT[ĂA]R[ÂA]RE\s+(privind\b.+)", re.IGNORECASE | re.DOTALL)
_PREAMBUL_RE = re.compile(
    r"\s+(?:Consiliul Local|În temeiul|Având în vedere|Analizând|Luând în)",
    re.IGNORECASE,
)
# Un proces-verbal real ÎNCEPE cu „PROCESUL VERBAL al ședinței ..." (în antet).
_PV_DETECT_RE = re.compile(r"PROCESUL VERBAL\s+al [sș]edin", re.IGNORECASE)
_PV_RE = re.compile(
    r"PROCESUL VERBAL\s+al ședinței\s+(\w+).{0,90}?din data de\s+([0-9]{1,2}\s+\w+\s+[0-9]{4})",
    re.IGNORECASE,
)


def classify_doc(text: str, titlu: str = "") -> str:
    """Returnează tipul documentului: 'PV' (proces-verbal) sau 'HCL' (hotărâre)."""
    if _PV_DETECT_RE.search((text or "")[:200]):
        return "PV"
    return "HCL"


def extract_obiect(text: str, fallback: str = "") -> str:
    """Extrage titlul descriptiv (obiectul) al documentului din textul complet."""
    if not text:
        return fallback
    # Proces-verbal: titlul e antetul ședinței, NU prima hotărâre din corp.
    if _PV_DETECT_RE.search(text[:200]):
        m = _PV_RE.search(text)
        if m:
            return f"Proces-verbal ședință {m.group(1).lower()} — {m.group(2)}"
        return fallback or "Proces-verbal ședință"
    m = _OBIECT_RE.search(text)
    if m:
        chunk = _PREAMBUL_RE.split(m.group(1), maxsplit=1)[0]
        chunk = re.sub(r"\s+", " ", chunk).strip()
        if len(chunk) > 350:
            chunk = chunk[:350].rsplit(" ", 1)[0] + "…"
        if chunk:
            return chunk
    return fallback


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    _ensure_columns(conn)
    conn.commit()
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    """Migrare idempotentă: adaugă coloane noi pe baze de date existente."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(hcl_documente)")]
    if "obiect" not in cols:
        conn.execute("ALTER TABLE hcl_documente ADD COLUMN obiect TEXT")
    if "tip_doc" not in cols:
        conn.execute("ALTER TABLE hcl_documente ADD COLUMN tip_doc TEXT")


def backfill_obiect(conn: sqlite3.Connection) -> int:
    """Populează `obiect` și `tip_doc` din `text_complet` pentru rândurile incomplete."""
    rows = conn.execute(
        "SELECT id, titlu, text_complet FROM hcl_documente "
        "WHERE obiect IS NULL OR obiect = '' OR tip_doc IS NULL OR tip_doc = ''"
    ).fetchall()
    for doc_id, titlu, text in rows:
        obiect = extract_obiect(text or "", fallback=titlu or "")
        tip = classify_doc(text or "", titlu or "")
        conn.execute(
            "UPDATE hcl_documente SET obiect = ?, tip_doc = ? WHERE id = ?",
            (obiect, tip, doc_id),
        )
    conn.commit()
    return len(rows)


def upsert_doc(conn: sqlite3.Connection, doc: dict) -> None:
    """Insert or update one HCL document. FTS sync is handled by DB triggers."""
    conn.execute(
        """
        INSERT INTO hcl_documente
            (document_id, an, numar_hcl, data_adoptare, titlu, obiect, tip_doc, text_complet, url_original)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(document_id) DO UPDATE SET
            an            = excluded.an,
            numar_hcl     = excluded.numar_hcl,
            data_adoptare = excluded.data_adoptare,
            titlu         = excluded.titlu,
            obiect        = excluded.obiect,
            tip_doc       = excluded.tip_doc,
            text_complet  = excluded.text_complet,
            url_original  = excluded.url_original
        """,
        (
            doc["document_id"], doc["an"], doc["numar_hcl"],
            doc["data_adoptare"], doc["titlu"], doc.get("obiect", ""),
            doc.get("tip_doc", "HCL"),
            doc["text_complet"], doc["url_original"],
        ),
    )


def search_fts(
    conn: sqlite3.Connection, query: str, limit: int = 50, tip: str = "HCL",
    ani: list = None
) -> list:
    where = "hcl_fts MATCH ?"
    params = [query]
    if tip:
        where += " AND d.tip_doc = ?"
        params.append(tip)
    if ani:  # listă de ani selectați; gol/None = toți anii
        placeholders = ",".join("?" * len(ani))
        where += f" AND d.an IN ({placeholders})"
        params.extend(ani)
    params.append(limit)
    try:
        cur = conn.execute(
            f"""
            SELECT d.document_id, d.numar_hcl, d.data_adoptare,
                   d.titlu, d.obiect, d.tip_doc, d.url_original, d.an
            FROM hcl_fts
            JOIN hcl_documente d ON hcl_fts.rowid = d.id
            WHERE {where}
            ORDER BY d.data_adoptare DESC, bm25(hcl_fts, 10.0, 1.0)
            LIMIT ?
            """,
            params,
        )
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except sqlite3.OperationalError:
        return []


def search_phrase(
    conn: sqlite3.Connection, text: str, limit: int = 50, tip: str = "HCL",
    ani: list = None
) -> list:
    """Caută textul ca frază exactă (cuvintele lipite, în ordine).

    Ex.: „eugen matei" găsește doar documentele unde apare chiar numele, nu cele
    care conțin „eugen" și „matei" separat, referitor la alte persoane.
    """
    cleaned = text.strip().strip('"“”„').strip()
    if not cleaned:
        return []
    phrase = '"' + cleaned.replace('"', '""') + '"'
    return search_fts(conn, phrase, limit, tip=tip, ani=ani)


def get_text(conn: sqlite3.Connection, document_id: str) -> str:
    """Aduce textul integral al unui singur document (pentru previzualizare la cerere)."""
    cur = conn.execute(
        "SELECT text_complet FROM hcl_documente WHERE document_id = ?", (document_id,)
    )
    row = cur.fetchone()
    return (row[0] if row else "") or ""


def search_topic(
    conn: sqlite3.Connection, topic_name: str, limit: int = 50, tip: str = "HCL",
    ani: list = None
) -> list:
    cur = conn.execute(
        "SELECT aliasuri FROM topicuri WHERE lower(nume) = lower(?)",
        (topic_name,),
    )
    row = cur.fetchone()
    terms = [topic_name]
    if row and row[0]:
        terms.extend(json.loads(row[0]))

    fts_query = " OR ".join('"' + t.replace('"', '""') + '"' for t in terms)
    return search_fts(conn, fts_query, limit, tip=tip, ani=ani)


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
