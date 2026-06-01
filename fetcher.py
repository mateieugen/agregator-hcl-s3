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
