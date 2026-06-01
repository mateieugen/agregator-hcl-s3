import sys
import time
import sqlite3
from db import init_db, upsert_doc, load_topics, extract_obiect, classify_doc
from fetcher import get_doc_list, get_doc_text

ENTITY      = "4420465"
YEARS       = [2024, 2025, 2026]
DB_PATH     = "hcl.db"
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
                    "document_id":  str(doc_id),
                    "an":           year,
                    "numar_hcl":    str(dec["Number"]),
                    "data_adoptare": dec["DecisionDate"],
                    "titlu":        dec["Title"],
                    "obiect":       extract_obiect(text, fallback=dec["Title"]),
                    "tip_doc":      classify_doc(text, dec["Title"]),
                    "text_complet": text,
                    "url_original": dec.get("LinkExternal") or "",
                })
                conn.commit()
                total_new += 1
                _safe_print(f"  [OK] {doc_id}: {dec['Title'][:60]}")
                time.sleep(RATE_LIMIT_S)
            except Exception as e:
                total_err += 1
                _safe_print(f"  [ERR] {doc_id}: {e}", err=True)

    print(f"\nDone. new={total_new}  skipped={total_skip}  errors={total_err}")
    _write_gz()
    conn.close()


def _safe_print(msg: str, err: bool = False) -> None:
    """Evită UnicodeEncodeError în consola Windows (cp1252)."""
    stream = sys.stderr if err else sys.stdout
    enc = getattr(stream, "encoding", None) or "utf-8"
    stream.write(msg.encode(enc, errors="replace").decode(enc) + "\n")


def _write_gz() -> None:
    """Regenerează hcl.db.gz pentru deploy (Streamlit Cloud / GitHub)."""
    import gzip, shutil
    with open(DB_PATH, "rb") as fin, gzip.open(DB_PATH + ".gz", "wb") as fout:
        shutil.copyfileobj(fin, fout)
    print(f"[gz] {DB_PATH}.gz regenerat")


if __name__ == "__main__":
    main()
