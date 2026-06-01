import re

import requests
from bs4 import BeautifulSoup

BASE_LIST = "https://hcl.usr.ro/api_getdoclist.php"
BASE_DOC  = "https://hcl.usr.ro/api_getdocument.php"


def get_doc_list(entity: str, year: int) -> list:
    resp = requests.get(f"{BASE_LIST}?entity={entity}&year={year}", timeout=30)
    resp.raise_for_status()
    return resp.json()["decisions"]


def get_doc_html(document_id) -> str:
    """Răspunsul HTML brut al documentului (păstrează structura: <p>, <h3>, <li>)."""
    resp = requests.get(f"{BASE_DOC}?documentid={document_id}", timeout=30)
    resp.raise_for_status()
    return resp.text


def get_doc_text(document_id) -> str:
    return strip_html(get_doc_html(document_id))


def strip_html(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


# Etichetă de vorbitor într-un proces-verbal: „Dl. Consilier X", „Dna. Savu Ileana",
# „Dl. Președinte de ședință …", „Domnul Viceprimar …" etc.
_SPEAKER_RE = re.compile(r"^(?:Dl|Dna|D-l|D-na|Dnul|Domnul|Doamna)\b\.?\s+\S")


def _is_speaker(txt: str) -> bool:
    if len(txt) > 90 or not _SPEAKER_RE.match(txt):
        return False
    # propozițiile (se termină cu punct și sunt lungi) nu sunt etichete de vorbitor
    if txt.endswith(".") and len(txt) > 45:
        return False
    return True


def html_to_readable(html: str, pv: bool = False) -> str:
    """Convertește HTML-ul documentului în HTML lizibil, cu rânduri strânse.

    Păstrează structura din hcl.usr.ro (titlu, paragraf, element de listă), fiecare
    pe rândul lui, cu spațiere verticală mică.

    La procese-verbale (`pv=True`), numele vorbitorului rămâne la margine (bold), iar
    intervenția lui e indentată — ca să se vadă ușor cine a luat cuvântul.
    """
    if not html:
        return ""
    from html import escape

    soup = BeautifulSoup(html, "html.parser")
    raw = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "li", "tr"]):
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        # liniile-zgomot (numere de pagină din OCR: „9", „J", etc.)
        if len(txt) <= 2 and not txt[0].isalpha():
            continue
        raw.append(txt)
    if not raw:
        raw = [l for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]

    rows = []
    for txt in raw:
        if pv and _is_speaker(txt):
            rows.append(
                f'<div style="font-weight:600;margin:12px 0 2px 0">{escape(txt)}</div>'
            )
            continue
        if txt.startswith("-"):
            txt = "– " + txt.lstrip("-").strip()
        indent = 24 if pv else 0
        rows.append(f'<div style="margin:0 0 4px {indent}px">{escape(txt)}</div>')
    return f'<div style="line-height:1.35">{"".join(rows)}</div>'
