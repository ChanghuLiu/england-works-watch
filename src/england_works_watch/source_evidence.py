from __future__ import annotations

from html.parser import HTMLParser
import hashlib
import re
from typing import Iterable


class _MainTextParser(HTMLParser):
    """Extract stable visible text from the document's <main> element.

    GOV.UK page chrome, analytics attributes, script payloads and markup can change
    without changing sponsor guidance. Fingerprinting visible <main> text gives the
    runtime change detector a substantially lower-noise signal while still failing
    closed on substantive guidance changes.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.main_depth = 0
        self.skip_depth = 0
        self.parts: list[str] = []
        self.saw_main = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "main":
            self.main_depth += 1
            self.saw_main = True
            return
        if self.main_depth and tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "main" and self.main_depth:
            self.main_depth -= 1
            return
        if self.main_depth and tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.main_depth and not self.skip_depth:
            text = data.strip()
            if text:
                self.parts.append(text)


def normalized_guidance_text(html: str) -> str:
    parser = _MainTextParser()
    parser.feed(html)
    if not parser.saw_main:
        # Fail safely to all visible-ish text rather than returning an empty hash.
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
    else:
        text = " ".join(parser.parts)
    return re.sub(r"\s+", " ", text).strip()


def semantic_sha256(html: str) -> str:
    return hashlib.sha256(normalized_guidance_text(html).encode("utf-8")).hexdigest()


def missing_expected_markers(html: str, markers: Iterable[str]) -> list[str]:
    visible = normalized_guidance_text(html).lower()
    current_version = re.search(r"\bversion\s+(\d{2}/\d{2})\b", visible)
    missing = []
    for marker in markers:
        version = re.fullmatch(r"version\s+(\d{2}/\d{2})", marker.lower())
        if version:
            if not current_version or version[1] != current_version[1]:
                missing.append(marker)
        elif marker.lower() not in visible:
            missing.append(marker)
    return missing

