import gzip
import shutil
from pathlib import Path

import streamlit as st
from db import init_db, search_fts, search_topic


@st.cache_data(show_spinner=False, max_entries=64)
def load_readable(document_id: str) -> str:
    """Aduce documentul live de la hcl.usr.ro și-l formatează lizibil (cache pe sesiune)."""
    from fetcher import get_doc_html, html_to_readable
    try:
        return html_to_readable(get_doc_html(document_id))
    except Exception:
        return ""

DB_PATH = "hcl.db"
DB_GZ_PATH = "hcl.db.gz"


def ensure_db() -> None:
    """Pe Streamlit Cloud repo conține doar hcl.db.gz — decomprimăm la prima pornire."""
    if Path(DB_PATH).exists():
        return
    if Path(DB_GZ_PATH).exists():
        with gzip.open(DB_GZ_PATH, "rb") as fin, open(DB_PATH, "wb") as fout:
            shutil.copyfileobj(fin, fout)

st.set_page_config(
    page_title="HCL Sector 3 — Căutare tematică",
    layout="wide",
)

st.title("Hotărâri Consiliu Local Sector 3")
st.caption("Sursă: hcl.usr.ro · Perioade indexate: 2024–2026")


@st.cache_resource
def get_conn():
    ensure_db()
    from db import backfill_obiect
    conn = init_db(DB_PATH)
    backfill_obiect(conn)  # populează obiect/tip_doc dacă lipsesc (baze vechi)
    return conn


conn = get_conn()

TIP_LABELS = {"Hotărâri (HCL)": "HCL", "Procese-verbale": "PV"}


def render_results(results: list, prefix: str) -> None:
    if not results:
        st.info("Niciun rezultat.")
        return
    st.success(f"{len(results)} documente găsite")
    for r in results:
        doc_id = r.get("document_id", "")
        url    = r.get("url_original") or ""
        data   = r.get("data_adoptare", "")
        nr     = r.get("numar_hcl", "")
        an     = r.get("an", "")
        titlu  = r.get("obiect") or r.get("titlu") or "—"
        eticheta = f"HCL nr. {nr}/{an}" if r.get("tip_doc") == "HCL" else "Proces-verbal"
        st.markdown(f"**{titlu}**")
        st.caption(f"{eticheta} &nbsp;·&nbsp; `{data}`")

        # Previzualizare „lazy": textul integral se aduce doar la click, doar pentru
        # documentul ales — ca să nu încărcăm pagina cu textul tuturor rezultatelor.
        state_key = f"show_{prefix}_{doc_id}"
        if st.button("👁 Previzualizare text", key=f"btn_{prefix}_{doc_id}"):
            st.session_state[state_key] = not st.session_state.get(state_key, False)
        if st.session_state.get(state_key):
            with st.spinner("Se încarcă documentul…"):
                text = load_readable(doc_id)
            with st.container(border=True):
                st.markdown(text or "_(text indisponibil)_", unsafe_allow_html=True)
        if url:
            st.markdown(f"[📄 PDF oficial]({url})")
        st.divider()


def tip_selector(key: str) -> str:
    label = st.radio(
        "Tip document:",
        list(TIP_LABELS.keys()),
        horizontal=True,
        key=key,
    )
    return TIP_LABELS[label]


tab_free, tab_topic = st.tabs(["Căutare liberă", "Căutare pe topic"])

with tab_free:
    st.markdown("Caută direct în textul documentelor. Funcționează cu sau fără diacritice.")
    tip_free = tip_selector("tip_free")
    query = st.text_input(
        "Termen de căutare:",
        placeholder='ex: "Hala Laminor" sau termoficare',
        key="free_query",
    )
    if query:
        render_results(search_fts(conn, query, tip=tip_free), prefix="free")

with tab_topic:
    st.markdown("Alege un topic predefinit — căutarea include automat toate alias-urile.")
    tip_topic = tip_selector("tip_topic")
    cur = conn.execute("SELECT nume FROM topicuri ORDER BY nume")
    topics = [row[0] for row in cur.fetchall()]
    if not topics:
        st.warning(
            "Niciun topic definit. Adaugă în `topics.yaml` și rulează `python ingest.py`."
        )
    else:
        topic = st.selectbox("Topic:", topics)
        if topic:
            render_results(search_topic(conn, topic, tip=tip_topic), prefix="topic")
