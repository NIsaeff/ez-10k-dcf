"""Filing parsing, quote location, and claim validation. No network, no LLM."""

from app.services import claims, filing

HTML = """
<html><body>
<div><span style="font-weight:700">ITEM 1. BUSINESS</span></div>
<p>We make beverages. Revenue was $47.9 billion in 2025.</p>
<div><span>Our brands are sold in more than 200 countries.</span></div>
<div><span>ITEM 7. MANAGEMENT DISCUSSION AND ANALYSIS</span></div>
<p>Operating income increased 12% to $13.8 billion.</p>
<p>We expect capital expenditures of approximately $2.2 billion in 2026.</p>
<p>Net operating revenues grew 2% for the year, driven by price and mix, while concentrate
shipment volume was flat. Operating margin expanded on lower commodity costs and productivity
savings, partially offset by higher marketing investment. We continue to expect volatility in
foreign exchange rates, and we hedge a portion of our exposure. Our bottling partners invest in
cold-drink equipment and route-to-market capacity, which supports long-term volume growth in
emerging markets and protects our share in developed markets. The company also repurchased
shares during the year under its existing authorization.</p>
</body></html>
"""


def test_parse_finds_span_only_headings() -> None:
    parsed = filing.parse(HTML)
    ids = [section["id"] for section in parsed.sections]

    assert ids == ["Preamble", "Item 1", "Item 7"]
    assert parsed.blocks[1].section == "Item 1"
    assert parsed.blocks[-1].section == "Item 7"


def test_parse_skips_junk_blocks() -> None:
    parsed = filing.parse(
        "<html><body><div>http://fasb.org/us-gaap/2025#Assets</div>"
        "<p>Real text with letters.</p></body></html>"
    )
    assert [block.text for block in parsed.blocks] == ["Real text with letters."]


def test_locate_returns_offsets() -> None:
    parsed = filing.parse(HTML)
    located = filing.locate("Operating income increased 12% to $13.8 billion.", parsed.blocks)

    assert located is not None
    block = parsed.blocks[located["block"]]
    assert block.text[located["start"] : located["end"]] == (
        "Operating income increased 12% to $13.8 billion."
    )


def test_locate_normalises_whitespace() -> None:
    parsed = filing.parse(HTML)
    located = filing.locate("Operating   income increased 12%\n to $13.8 billion.", parsed.blocks)
    assert located is not None


def test_locate_rejects_missing_text() -> None:
    parsed = filing.parse(HTML)
    assert filing.locate("Revenue tripled overnight.", parsed.blocks) is None


def test_locate_scopes_to_section() -> None:
    parsed = filing.parse(HTML)
    located = filing.locate(
        "Revenue was $47.9 billion in 2025.", parsed.blocks, section="Item 7"
    )
    # Present only in Item 1, so section scoping correctly finds nothing.
    assert located is None


def test_strip_json_handles_code_fences() -> None:
    payload = claims._strip_json('```json\n{"parents": []}\n```')
    assert payload == {"parents": []}


def test_extract_marks_unverified_quotes(monkeypatch) -> None:
    parsed = filing.parse(HTML)
    payload = {
        "parents": [
            {
                "statement": "Revenue scale",
                "kind": "segment",
                "children": [
                    {
                        "statement": "Operating income rose 12%",
                        "quote": "Operating income increased 12% to $13.8 billion.",
                        "confidence": "high",
                    },
                    {
                        "statement": "Fabricated claim",
                        "quote": "Revenue tripled overnight.",
                        "confidence": "low",
                    },
                ],
            }
        ]
    }

    monkeypatch.setattr(claims, "_ask", lambda section, text: payload)
    nodes, flags = claims.extract(parsed)

    assert flags == []
    children = nodes[0]["children"]
    assert children[0]["verified"] is True
    assert children[0]["block"] is not None
    assert children[1]["verified"] is False
    assert children[1]["block"] is None


def test_extract_flags_when_model_fails(monkeypatch) -> None:
    parsed = filing.parse(HTML)
    monkeypatch.setattr(claims, "_ask", lambda section, text: None)

    nodes, flags = claims.extract(parsed)

    assert nodes == []
    assert any(flag.startswith("claims_failed") for flag in flags)
