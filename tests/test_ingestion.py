"""Tests for Ingestion Pipeline — chunking, extraction, enrichment, gateway."""

import pytest


class TestSemanticChunker:
    def test_short_text_single_chunk(self):
        from ingestion.chunker import SemanticChunker
        chunker = SemanticChunker()
        text = "This is a short text that fits in one chunk."
        chunks = chunker.chunk(text)
        assert len(chunks) == 1
        assert chunks[0]["index"] == 0
        assert chunks[0]["content"] == text

    def test_long_text_multiple_chunks(self):
        from ingestion.chunker import SemanticChunker
        chunker = SemanticChunker()
        # Generate text > 500 tokens (~2000+ chars)
        paragraphs = [f"Paragraph {i}. " + "Word " * 100 for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = chunker.chunk(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk["token_estimate"] > 0
            assert chunk["content"].strip() != ""

    def test_empty_text(self):
        from ingestion.chunker import SemanticChunker
        chunker = SemanticChunker()
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []

    def test_chunk_code(self):
        from ingestion.chunker import SemanticChunker
        chunker = SemanticChunker()
        code = """
def function_a():
    pass

def function_b():
    return 42

class MyClass:
    def method(self):
        pass
"""
        # Code is short, so it might be a single chunk
        chunks = chunker.chunk_code(code)
        assert len(chunks) >= 1
        assert any("function" in c["content"] for c in chunks)

    def test_estimate_tokens(self):
        from ingestion.chunker import SemanticChunker
        assert SemanticChunker.estimate_tokens("abcd") == 1
        assert SemanticChunker.estimate_tokens("a" * 100) == 25
        assert SemanticChunker.estimate_tokens("") == 0


class TestMetadataEnricher:
    def test_detect_language_russian(self, db):
        from ingestion.enricher import MetadataEnricher
        enricher = MetadataEnricher(db)
        assert enricher.detect_language("Привет мир, как дела у вас?") == "ru"

    def test_detect_language_english(self, db):
        from ingestion.enricher import MetadataEnricher
        enricher = MetadataEnricher(db)
        assert enricher.detect_language("Hello world, how are you?") == "en"

    def test_detect_content_type_code(self, db):
        from ingestion.enricher import MetadataEnricher
        enricher = MetadataEnricher(db)
        code = "def main():\n    if True:\n        for i in range(10):\n            print(i)"
        assert enricher.detect_content_type(code) == "code"

    def test_detect_content_type_docs(self, db):
        from ingestion.enricher import MetadataEnricher
        enricher = MetadataEnricher(db)
        docs = "# Overview\n\n**Important:** This is documentation.\n\n> Note: read carefully.\n\n1. First step"
        assert enricher.detect_content_type(docs) == "documentation"

    def test_enricher_metadata(self, db):
        from ingestion.enricher import MetadataEnricher
        enricher = MetadataEnricher(db)
        result = enricher.enrich("Hello world, this is a test message")
        assert "language" in result
        assert result["language"] == "en"
        assert "estimated_tokens" in result
        assert result["estimated_tokens"] > 0
        assert "word_count" in result
        assert result["has_code"] is False

    def test_enricher_preserves_existing(self, db):
        from ingestion.enricher import MetadataEnricher
        enricher = MetadataEnricher(db)
        result = enricher.enrich("Some text", metadata={"project": "myproject"})
        assert result["project"] == "myproject"


class TestConceptExtractor:
    def test_concept_extractor_fast(self, db, graph_store):
        from ingestion.extractor import ConceptExtractor
        # Add known nodes to graph
        graph_store.add_node("concept", "authentication")
        graph_store.add_node("technology", "golang")

        extractor = ConceptExtractor(db)
        result = extractor.extract_fast("Implement authentication in golang")
        assert len(result["concepts"]) + len(result["entities"]) >= 1

    def test_concept_extractor_empty(self, db):
        from ingestion.extractor import ConceptExtractor
        extractor = ConceptExtractor(db)
        result = extractor.extract_fast("")
        assert result["concepts"] == []
        assert result["entities"] == []


class TestIngestGateway:
    def test_ingest_gateway_queue(self, db):
        from ingestion.gateway import IngestGateway
        gateway = IngestGateway(db)

        ingest_id = gateway.ingest(
            content="Test content for ingestion pipeline",
            source="test",
            content_type="text",
        )
        assert ingest_id is not None

        status = gateway.get_queue_status()
        assert status["total"] >= 1

    def test_ingest_gateway_empty_content(self, db):
        from ingestion.gateway import IngestGateway
        gateway = IngestGateway(db)

        ingest_id = gateway.ingest(content="   ", source="test", content_type="text")
        # Empty content should be marked as error
        row = db.execute(
            "SELECT status FROM ingest_queue WHERE id = ?", (ingest_id,)
        ).fetchone()
        assert row[0] == "error"
