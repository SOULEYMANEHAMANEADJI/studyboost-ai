"""Allow plain Markdown structure and safe links, never active HTML/resources."""
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlsplit

ALLOWED = {"p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "strong", "em", "b", "i", "ul", "ol", "li", "blockquote", "pre", "code", "table", "thead", "tbody", "tr", "th", "td", "a"}
VOID = {"br", "hr"}

class SafeMarkup(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.blocked = []

    def handle_starttag(self, tag, attrs):
        if self.blocked:
            if tag in ("script", "style", "iframe", "object", "svg", "math"):
                self.blocked.append(tag)
            return
        if tag in ("script", "style", "iframe", "object", "svg", "math"):
            self.blocked.append(tag)
            return
        if tag == "img":
            self.output.append(escape(dict(attrs).get("alt", "")))
        elif tag in ALLOWED:
            attributes = ""
            if tag == "a":
                href = dict(attrs).get("href", "") or ""
                try:
                    safe = urlsplit(href).scheme.lower() in ("http", "https", "mailto") or href.startswith("#")
                except ValueError:
                    safe = False
                if safe:
                    attributes = ' href="' + escape(href, quote=True) + '" rel="noopener noreferrer"'
            self.output.append("<" + tag + attributes + ">")

    def handle_endtag(self, tag):
        if self.blocked:
            if tag == self.blocked[-1]: self.blocked.pop()
            return
        if tag in ALLOWED and tag not in VOID:
            self.output.append("</" + tag + ">")

    def handle_data(self, data):
        if not self.blocked: self.output.append(escape(data))


def safe_markdown(text):
    import markdown
    parser = SafeMarkup()
    parser.feed(markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br"]))
    parser.close()
    return "".join(parser.output)
