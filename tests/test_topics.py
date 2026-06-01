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


def test_search_topic_ranks_by_relevance_then_recent(tmp_path):
    # Relevanță egală pe ambele → cel mai recent primul (departajare după dată).
    conn = init_db(str(tmp_path / "test.db"))
    upsert_doc(conn, _doc(10, "Laminor martie", "laminor", "2026-03-01"))
    upsert_doc(conn, _doc(5,  "Laminor ianuarie", "laminor", "2026-01-01"))
    conn.commit()
    results = search_topic(conn, "laminor")
    assert results[0]["document_id"] == "10"
    assert results[1]["document_id"] == "5"


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
