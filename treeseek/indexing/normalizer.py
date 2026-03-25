from __future__ import annotations

import re
import unicodedata
from collections import Counter

WORD_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)*", re.UNICODE)
QUOTED_PHRASE_RE = re.compile(r'"([^"]+)"')


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", str(text)).lower()
    normalized = normalized.replace("—", "-").replace("–", "-").replace("−", "-")
    normalized = normalized.replace("’", "'").replace("‘", "'")
    normalized = re.sub(r"[\t\r\n]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_title_key(text: str | None) -> str:
    return normalize_text(text)


def tokenize(text: str | None) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    tokens: list[str] = []
    for token in WORD_RE.findall(normalized):
        tokens.append(token)
        if "-" in token:
            tokens.extend(part for part in token.split("-") if part)
    return tokens


def count_terms(text: str | None) -> Counter[str]:
    return Counter(tokenize(text))


def tokenize_with_positions(text: str | None) -> tuple[list[str], dict[str, list[int]]]:
    tokens = tokenize(text)
    positions: dict[str, list[int]] = {}
    for idx, token in enumerate(tokens):
        positions.setdefault(token, []).append(idx)
    return tokens, positions


def extract_phrases(query: str | None) -> list[str]:
    if not query:
        return []
    phrases = [normalize_text(match.group(1)) for match in QUOTED_PHRASE_RE.finditer(query)]
    phrases = [phrase for phrase in phrases if phrase]
    return phrases
