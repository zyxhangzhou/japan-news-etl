from unittest.mock import MagicMock, patch
from etl.fetch import compute_url_hash
from etl.transform import classify_and_summarize, deduplicate
class _CursorContext:
    def __init__(self, rows):
        self._rows = rows
        self.executed = None
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def execute(self, query, params):
        self.executed = (query, params)
    def fetchall(self):
        return self._rows
class _ConnectionContext:
    def __init__(self, rows):
        self.cursor_obj = _CursorContext(rows)
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def cursor(self):
        return self.cursor_obj
def test_deduplicate_removes_existing():
    articles = [
        {"url": "https://example.com/existing", "url_hash": "existing-hash"},
        {"url": "https://example.com/new", "url_hash": "new-hash"},
    ]
    fake_connection = _ConnectionContext([("existing-hash",)])
    with patch("etl.transform._get_postgres_connection", return_value=fake_connection):
        result = deduplicate(articles)
    assert result == [{"url": "https://example.com/new", "url_hash": "new-hash"}]
def test_compute_url_hash_consistent():
    url = "https://example.com/same-url"
    first_hash = compute_url_hash(url)
    second_hash = compute_url_hash(url)
    assert first_hash == second_hash
def test_classify_returns_none_for_other():
    article = {
        "url": "https://example.com/other",
        "category": "immigration",
        "title": "Some unrelated article",
        "summary": "This should be filtered",
    }
    fake_response = MagicMock()
    fake_response.output_text = '{"category": "other", "summary_zh": "skip"}'
    fake_client = MagicMock()
    fake_client.responses.create.return_value = fake_response
    with patch("etl.transform._get_openai_client", return_value=fake_client):
        result = classify_and_summarize(article)
    assert result is None