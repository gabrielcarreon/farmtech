from app.rag.chunking import chunk_text
from app.rag.filters import build_metadata_filters, full_text_query, reciprocal_rank_fusion


def test_full_text_query_uses_or_between_content_words():
    assert full_text_query("Why is tomato suitable for this planting period?") == "tomato | suitable | planting | period"


def test_metadata_filters_drop_empty_values():
    assert build_metadata_filters(crop="Tomato", region="Central Luzon", province=None, year=None) == {
        "crop": "Tomato",
        "region": "Central Luzon",
    }


def test_reciprocal_rank_fusion_prefers_items_in_both_lists():
    fused = reciprocal_rank_fusion([[1, 2], [2, 3]], limit=3)
    assert fused[0] == 2
    assert fused == [2, 1, 3]


def test_chunks_follow_section_headings():
    text = "## Climate Requirements\nTomato needs a dry season.\n\n## Harvest\nPick when color breaks.\n"
    chunks = chunk_text(text)
    assert [chunk["section"] for chunk in chunks] == ["Climate Requirements", "Harvest"]
    assert "dry season" in chunks[0]["content"]
