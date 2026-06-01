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
