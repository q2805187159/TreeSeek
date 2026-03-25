from treeseek.indexing.normalizer import extract_phrases, normalize_text, tokenize


def test_normalize_text_collapses_case_and_whitespace():
    assert normalize_text("  Direct-To-Consumer\nRevenue ") == "direct-to-consumer revenue"


def test_tokenize_preserves_hyphenated_token_and_parts():
    tokens = tokenize("Direct-to-consumer growth")
    assert "direct-to-consumer" in tokens
    assert "direct" in tokens
    assert "consumer" in tokens
    assert "growth" in tokens


def test_extract_phrases_prefers_quoted_phrase():
    assert extract_phrases('"Risk Factors" and liquidity') == ["risk factors"]


def test_extract_phrases_returns_empty_for_unquoted_multi_term_query():
    assert extract_phrases("financial stability") == []
