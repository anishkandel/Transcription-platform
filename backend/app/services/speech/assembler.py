from __future__ import annotations


def assemble_transcript_parts(parts: list[str]) -> str:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return ""
    # Keep a readable join for bilingual meeting text.
    return "\n".join(cleaned)
