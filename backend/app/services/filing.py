"""Fetch, parse, and segment a 10-K primary document.

The valuation pipeline uses XBRL JSON only. This module is the opposite end: it
reads the human-readable filing, turns it into ordered text blocks, labels them
by Item, and can locate a verbatim quote inside them so the UI can highlight it.

Everything is cached under data/raw/filings/ so repeat views never re-download.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from app.config import settings
from app.services import edgar

MAX_BLOCKS = 6000
MAX_BLOCK_CHARS = 4000
MAX_HTML_BYTES = 40 * 1024 * 1024

HEADERS = {
    "User-Agent": settings.sec_user_agent,
    "Accept": "text/html,application/xhtml+xml",
}

ITEM_LABELS = {
    "1": "Business",
    "1A": "Risk Factors",
    "1B": "Unresolved Staff Comments",
    "1C": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Common Equity",
    "6": "Selected Financial Data",
    "7": "MD&A",
    "7A": "Quantitative and Qualitative Disclosures",
    "8": "Financial Statements",
    "9": "Accountant Changes and Disagreements",
    "9A": "Controls and Procedures",
    "9B": "Other Information",
    "9C": "Foreign Jurisdictions",
    "10": "Directors and Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership",
    "13": "Related Transactions",
    "14": "Principal Accountant Fees",
    "15": "Exhibits",
    "16": "Form 10-K Summary",
}

BLOCK_TAGS = ("p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr")
CONTAINER_TAGS = ("div", "table", "ul", "ol", "section", "article", "main", "td", "th")
SKIP_TAGS = ("script", "style", "noscript", "head")
ITEM_PATTERN = re.compile(r"^item\s+(\d{1,2}[a-c]?)\s*[.:]?\s*(.*)$", re.IGNORECASE)


@dataclass
class Block:
    index: int
    section: str
    text: str


@dataclass
class ParsedFiling:
    blocks: list[Block]
    sections: list[dict[str, Any]]


def _dir() -> Path:
    path = settings.data_dir / "raw" / "filings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalise(text: str) -> str:
    return " ".join(text.split())


def document_path(accession: str) -> Path:
    return _dir() / f"{accession}.html"


def fetch_document(cik: str, accession: str, document: str) -> str:
    """Return the primary 10-K document, downloading it at most once."""
    path = document_path(accession)
    if path.exists() and path.stat().st_size > 0:
        return path.read_text(errors="ignore")

    url = edgar.ARCHIVE_URL.format(
        cik=int(cik), accession=accession.replace("-", ""), document=document
    )
    response = httpx.get(url, headers=HEADERS, timeout=60.0, follow_redirects=True)
    response.raise_for_status()
    if len(response.content) > MAX_HTML_BYTES:
        raise ValueError(f"Filing is unexpectedly large ({len(response.content)} bytes)")
    path.write_text(response.text, errors="ignore")
    return response.text


def _is_junk(text: str) -> bool:
    if len(text) < 3 or not any(character.isalpha() for character in text):
        return True
    # Inline-XBRL namespace exports and bare URLs show up as text nodes.
    return text.startswith("http") and " " not in text[:80]


def _walk(node, out: list[str]) -> None:
    """Emit text for block-ish nodes, descending through containers.

    Filings commonly put headings in span-only <div>s, so selecting only
    p/li/h* loses them. A leaf <div> is a block; a <div> with block children is
    a container to walk through.
    """
    tag = (node.tag or "").lower()
    if tag in SKIP_TAGS:
        return

    children = [child for child in node.iter(include_text=False)]
    block_children = [
        child
        for child in children
        if (child.tag or "").lower() in BLOCK_TAGS + CONTAINER_TAGS
    ]

    if tag in BLOCK_TAGS or (tag in CONTAINER_TAGS and not block_children):
        text = _normalise(node.text(separator=" ", strip=True))
        if text and not _is_junk(text):
            out.append(text[:MAX_BLOCK_CHARS])
        return

    for child in children:
        _walk(child, out)


def _extract_blocks(html: str) -> list[str]:
    tree = HTMLParser(html)
    for node in tree.css("script, style, noscript"):
        node.decompose()

    body = tree.body or tree.root
    if body is None:
        return []

    texts: list[str] = []
    _walk(body, texts)

    # Drop consecutive duplicates produced by nested block tags.
    deduped: list[str] = []
    for text in texts:
        if deduped and deduped[-1] == text:
            continue
        deduped.append(text)
    return deduped[:MAX_BLOCKS]


def _section_for_heading(text: str) -> tuple[str, str] | None:
    """Return (item id, label) when the block looks like an Item heading."""
    if len(text) > 120:
        return None
    match = ITEM_PATTERN.match(text.strip())
    if not match:
        return None
    item = match.group(1).upper()
    suffix = match.group(2).strip()
    label = ITEM_LABELS.get(item)
    if label is None:
        return None
    if suffix and len(suffix) < 90:
        # "Item 1. Business" -> keep the standard label, ignore the tail.
        pass
    return item, f"Item {item} — {label}"


def parse(html: str) -> ParsedFiling:
    raw_blocks = _extract_blocks(html)
    blocks: list[Block] = []
    sections: list[dict[str, Any]] = [{"id": "Preamble", "label": "Preamble", "block": 0}]
    current = "Preamble"

    for index, text in enumerate(raw_blocks):
        heading = _section_for_heading(text)
        if heading is not None:
            item, label = heading
            # Only start a new section the first time an item appears.
            if not any(section["id"] == f"Item {item}" for section in sections):
                current = f"Item {item}"
                sections.append({"id": current, "label": label, "block": index})
        blocks.append(Block(index=index, section=current, text=text))

    return ParsedFiling(blocks=blocks, sections=sections)


def load(cik: str, accession: str, document: str) -> ParsedFiling:
    return parse(fetch_document(cik, accession, document))


def locate(quote: str, blocks: list[Block], *, section: str | None = None) -> dict[str, int] | None:
    """Find a verbatim quote in the parsed blocks.

    Returns {block, start, end} with offsets into the block's normalised text.
    """
    needle = _normalise(quote)
    if len(needle) < 12:
        return None

    ordered = blocks
    if section:
        scoped = [block for block in blocks if block.section == section]
        if scoped:
            ordered = scoped

    for block in ordered:
        position = block.text.find(needle)
        if position >= 0:
            return {"block": block.index, "start": position, "end": position + len(needle)}

    # Fall back to a shorter prefix: models occasionally trim mid-sentence.
    if len(needle) > 80:
        prefix = needle[:80]
        for block in ordered:
            position = block.text.find(prefix)
            if position >= 0:
                return {
                    "block": block.index,
                    "start": position,
                    "end": position + len(prefix),
                }
    return None


SCRIPT_PATTERN = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
EVENT_ATTRIBUTE = re.compile(
    r"""\s+on[a-z]+\s*=\s*("[^"]*"|'[^']*')""", re.IGNORECASE
)

BRIDGE = r"""
<style>
  mark.filing-hit {
    background: #fcd34d;
    color: inherit;
    padding: 0;
    border-radius: 2px;
  }

  /* Filings hardcode black-on-white inline styles, so no variable-based theme
     will reach them. Inverting the page and re-inverting media keeps contrast,
     table shading and emphasis intact. */
  html.filing-dark {
    filter: invert(1) hue-rotate(180deg);
    background: #f4f4f5;
    color-scheme: dark;
  }

  html.filing-dark img,
  html.filing-dark svg,
  html.filing-dark video,
  html.filing-dark canvas {
    filter: invert(1) hue-rotate(180deg);
  }

  html.filing-dark mark.filing-hit {
    background: #f59e0b;
  }
</style>
<script>
(function () {
  var HIT = "filing-hit";
  var TOC_SKIP_CHARS = 8000;

  function norm(value) {
    return String(value || "").replace(/\u00a0/g, " ").replace(/\s+/g, " ");
  }

  function textNodes() {
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        var element = node.parentElement;
        if (!element) return NodeFilter.FILTER_REJECT;
        var tag = element.tagName;
        if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT") return NodeFilter.FILTER_REJECT;
        if (element.checkVisibility && !element.checkVisibility({ checkOpacity: false, checkVisibilityCSS: true })) {
          return NodeFilter.FILTER_REJECT;
        }
        var style = getComputedStyle(element);
        if (style.display === "none" || style.visibility === "hidden") return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var nodes = [];
    var node;
    while ((node = walker.nextNode())) nodes.push(node);
    return nodes;
  }

  // Flatten visible text into a whitespace-normalised string plus a map back to
  // raw offsets, so a quote can be found regardless of markup boundaries.
  function flatten() {
    var nodes = textNodes();
    var raw = "";
    var spans = [];
    for (var i = 0; i < nodes.length; i += 1) {
      var value = nodes[i].nodeValue;
      spans.push({ node: nodes[i], start: raw.length, end: raw.length + value.length });
      // A separator mirrors how block text is extracted server-side; without it,
      // words either side of inline markup get glued together.
      raw += value + " ";
    }

    var chars = [];
    var map = [];
    var lastSpace = true;
    for (var j = 0; j < raw.length; j += 1) {
      var ch = raw[j] === "\u00a0" ? " " : raw[j];
      if (/\s/.test(ch)) {
        if (lastSpace) continue;
        lastSpace = true;
        chars.push(" ");
        map.push(j);
      } else {
        lastSpace = false;
        chars.push(ch);
        map.push(j);
      }
    }
    return { text: chars.join(""), map: map, spans: spans };
  }

  function clear() {
    var marks = document.querySelectorAll("mark." + HIT);
    for (var i = 0; i < marks.length; i += 1) {
      var mark = marks[i];
      var parent = mark.parentNode;
      if (!parent) continue;
      parent.replaceChild(document.createTextNode(mark.textContent || ""), mark);
      parent.normalize();
    }
  }

  function wrapRange(spans, rawStart, rawEnd) {
    for (var k = 0; k < spans.length; k += 1) {
      var span = spans[k];
      if (span.end <= rawStart || span.start >= rawEnd) continue;
      var localStart = Math.max(0, rawStart - span.start);
      var localEnd = Math.min(span.node.nodeValue.length, rawEnd - span.start);
      if (localEnd <= localStart) continue;
      var target = span.node.splitText(localStart);
      target.splitText(localEnd - localStart);
      var mark = document.createElement("mark");
      mark.className = HIT;
      target.parentNode.replaceChild(mark, target);
      mark.appendChild(target);
    }
  }

  function highlight(rawQuote, sectionLabel) {
    clear();
    var needle = norm(rawQuote).trim();
    if (needle.length < 8) return false;

    var flat = flatten();
    var from = 0;
    if (sectionLabel) {
      var haystack = flat.text.toUpperCase();
      var heading = "ITEM " + String(sectionLabel).replace(/^item\s*/i, "").toUpperCase();
      var headingAt = haystack.indexOf(heading);
      while (headingAt >= 0 && flat.map[headingAt] <= TOC_SKIP_CHARS) {
        headingAt = haystack.indexOf(heading, headingAt + 1);
      }
      if (headingAt < 0) headingAt = haystack.indexOf(heading);
      if (headingAt >= 0) from = headingAt;
    }

    var found = flat.text.indexOf(needle, from);
    if (found < 0) found = flat.text.indexOf(needle);
    if (found < 0) return false;

    var rawStart = flat.map[found];
    var rawEnd = flat.map[found + needle.length - 1] + 1;
    wrapRange(flat.spans, rawStart, rawEnd);

    var first = document.querySelector("mark." + HIT);
    if (first) first.scrollIntoView({ block: "center" });
    return true;
  }

  function scrollToSection(label) {
    var wanted = norm(label).trim().toUpperCase();
    if (!wanted) return false;

    var flat = flatten();
    var haystack = flat.text.toUpperCase();
    var index = haystack.indexOf(wanted);
    var chosen = -1;
    while (index >= 0) {
      // Skip the table of contents near the top of the document.
      if (flat.map[index] > TOC_SKIP_CHARS) {
        chosen = index;
        break;
      }
      index = haystack.indexOf(wanted, index + 1);
    }
    if (chosen < 0) {
      chosen = haystack.indexOf(wanted);
      if (chosen < 0) return false;
    }

    var raw = flat.map[chosen];
    var spans = flat.spans;
    for (var k = 0; k < spans.length; k += 1) {
      if (spans[k].end > raw) {
        var element = spans[k].node.parentElement || spans[k].node;
        element.scrollIntoView({ block: "start" });
        return true;
      }
    }
    return false;
  }

  function applyTheme(mode) {
    var dark = String(mode || "").toLowerCase() === "dark";
    document.documentElement.classList.toggle("filing-dark", dark);
  }

  function announce() {
    if (window.parent) window.parent.postMessage({ type: "ready" }, "*");
  }

  window.addEventListener("message", function (event) {
    var data = event.data || {};
    if (data.type === "highlight") {
      var found = highlight(String(data.quote || ""), String(data.section || ""));
      if (event.source) event.source.postMessage({ type: "highlighted", found: found }, "*");
    } else if (data.type === "clear") {
      clear();
    } else if (data.type === "section") {
      clear();
      scrollToSection(String(data.label || ""));
    } else if (data.type === "theme") {
      applyTheme(data.mode);
    } else if (data.type === "ping") {
      announce();
    }
  });

  if (document.readyState === "complete") announce();
  else window.addEventListener("load", announce);
  announce();
})();
</script>
"""


def render_for_web(html: str, document_url: str) -> str:
    """Return a same-origin, script-stripped copy of the filing with a bridge.

    The original document is XHTML with inline styles and a hidden inline-XBRL
    header. Serving it as-is would expose us to whatever script it contains, so
    scripts and event handlers are stripped and a single highlighter is injected.
    """
    cleaned = SCRIPT_PATTERN.sub("", html)
    cleaned = EVENT_ATTRIBUTE.sub("", cleaned)

    directory = document_url.rsplit("/", 1)[0] + "/"
    if "<base " not in cleaned.lower():
        base = f'<base href="{directory}">'
        if re.search(r"<head[^>]*>", cleaned, re.IGNORECASE):
            cleaned = re.sub(
                r"(<head[^>]*>)", lambda match: match.group(1) + base, cleaned,
                count=1, flags=re.IGNORECASE,
            )
        else:
            cleaned = base + cleaned

    if re.search(r"</body>", cleaned, re.IGNORECASE):
        cleaned = re.sub(
            r"</body>", lambda match: BRIDGE + "</body>", cleaned,
            count=1, flags=re.IGNORECASE,
        )
    else:
        cleaned = cleaned + BRIDGE
    return cleaned


def section_text(blocks: list[Block], section: str) -> str:
    return "\n".join(block.text for block in blocks if block.section == section)


def chunks_for_section(
    blocks: list[Block], section: str, *, chunk_chars: int = 6000
) -> list[list[Block]]:
    """Group a section's blocks into roughly equal windows."""
    scoped = [block for block in blocks if block.section == section]
    chunks: list[list[Block]] = []
    current: list[Block] = []
    size = 0

    for block in scoped:
        if current and size + len(block.text) > chunk_chars:
            chunks.append(current)
            current = []
            size = 0
        current.append(block)
        size += len(block.text)

    if current:
        chunks.append(current)
    return chunks


def cache_path(accession: str) -> Path:
    return _dir() / f"{accession}.claims.json"


def load_cached_claims(accession: str) -> dict[str, Any] | None:
    path = cache_path(accession)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def save_cached_claims(accession: str, payload: dict[str, Any]) -> None:
    cache_path(accession).write_text(json.dumps(payload))
