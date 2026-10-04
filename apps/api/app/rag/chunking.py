from __future__ import annotations

import re


HEADING = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.MULTILINE)


def _words(text: str) -> list[str]:
    return text.split()


def _window(words: list[str], target_words: int, overlap_words: int) -> list[str]:
    if len(words) <= target_words:
        return [" ".join(words)]
    chunks: list[str] = []
    step = max(target_words - overlap_words, 1)
    start = 0
    while start < len(words):
        piece = words[start : start + target_words]
        if not piece:
            break
        chunks.append(" ".join(piece))
        if start + target_words >= len(words):
            break
        start += step
    return chunks


def chunk_text(text: str, target_words: int = 450, overlap_words: int = 60, max_words: int = 620) -> list[dict]:
    """Split on markdown headings, then window only sections that exceed the token target."""
    cleaned = text.strip()
    if not cleaned:
        return []
    matches = list(HEADING.finditer(cleaned))
    sections: list[tuple[str | None, str]] = []
    if not matches:
        sections.append((None, cleaned))
    else:
        preface = cleaned[: matches[0].start()].strip()
        if preface:
            sections.append((None, preface))
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
            body = cleaned[match.end() : end].strip()
            sections.append((match.group(1).strip(), body))

    chunks: list[dict] = []
    for section, body in sections:
        if not body:
            continue
        words = _words(body)
        pieces = _window(words, target_words, overlap_words) if len(words) > max_words else [" ".join(words)]
        for piece in pieces:
            content = f"{section}\n{piece}" if section else piece
            chunks.append({"section": section, "content": content.strip()})
    return chunks
