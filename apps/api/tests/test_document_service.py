from app.services.document_service import embedding_status_for_counts


def test_embedding_status_bands():
    assert embedding_status_for_counts(0, 0) == "pending"
    assert embedding_status_for_counts(4, 0) == "pending"
    assert embedding_status_for_counts(4, 2) == "partial"
    assert embedding_status_for_counts(4, 4) == "ready"
