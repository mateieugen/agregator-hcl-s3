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


def html_to_readable(html: str) -> str:
    """Convertește HTML-ul documentului în HTML lizibil, cu rânduri strânse.

    Păstrează structura din hcl.usr.ro (titlu, paragraf, element de listă), fiecare
    pe rândul lui, dar cu spațiere verticală mică între rânduri.
    """
    if not html:
        return ""
    from html import escape

    soup = BeautifulSoup(html, "html.parser")
    blocks = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "li", "tr"]):
        txt = el.get_text(" ", strip=True)
        if not txt:
            continue
        # liniile-zgomot (numere de pagină din OCR: „9", „J", etc.)
        if len(txt) <= 2 and not txt[0].isalpha():
            continue
        if txt.startswith("-"):
            txt = "– " + txt.lstrip("-").strip()
        blocks.append(escape(txt))
    if not blocks:
        blocks = [escape(l) for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]
    rows = "".join(f'<div style="margin:0 0 4px 0">{b}</div>' for b in blocks)
    return f'<div style="line-height:1.35">{rows}</div>'
