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
    cur = conn.execute("SELECT name FROM sqlite_master WHERE name='hcl_fts'")
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
