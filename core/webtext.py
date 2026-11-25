"""Pull the readable paragraphs out of a web page. Standard library only."""

from __future__ import annotations

from html.parser import HTMLParser

BLOCKS = {"p", "li", "h1", "h2", "h3", "blockquote"}
SKIPPED = {"script", "style", "noscript", "nav", "header", "footer", "form"}
MIN_WORDS = 8  # shorter blocks are menus, captions and link lists, not prose


class _Paragraphs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.paragraphs: list[str] = []
        self._buffer: list[str] = []
        self._skip_depth = 0
        self._in_block = False
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in SKIPPED:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in BLOCKS:
            self._flush()
            self._in_block = True

    def handle_endtag(self, tag):
        if tag in SKIPPED:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in BLOCKS:
            self._flush()
            self._in_block = False

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
        elif self._in_block:
            self._buffer.append(data)

    def _flush(self):
        text = " ".join("".join(self._buffer).split())
        self._buffer = []
        if len(text.split()) >= MIN_WORDS:
            self.paragraphs.append(text)


def page_text(html: str) -> tuple[str, str]:
    """Return (title, text) for a page. The text is its prose paragraphs, one per line."""
    parser = _Paragraphs()
    parser.feed(html)
    parser.close()
    parser._flush()
    return " ".join(parser.title.split()), "\n".join(parser.paragraphs)
