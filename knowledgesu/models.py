from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField

from common.models import BaseModel
from knowledgesu.choices import DocStatus, DocType

EMBED_DIM = int(getattr(settings, "RAG_EMBED_DIM", 384))


class KnowledgeDocument(BaseModel):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="knowledge/", blank=True, null=True)
    doc_type = models.CharField(max_length=10, choices=DocType.choices)
    status = models.CharField(max_length=20, choices=DocStatus.choices, default=DocStatus.PENDING)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = "knowledge_documents"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def chunk_count(self):
        return self.chunks.count()

    @property
    def page_count(self):
        return self.metadata.get("page_count")


class DocumentChunk(BaseModel):
    document = models.ForeignKey(KnowledgeDocument, on_delete=models.CASCADE, related_name="chunks")
    content = models.TextField()
    chunk_index = models.PositiveIntegerField()
    embedding = VectorField(dimensions=EMBED_DIM, null=True, blank=True)
    token_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "document_chunks"
        ordering = ["chunk_index"]
        unique_together = ("document", "chunk_index")
        indexes = [
            HnswIndex(
                name="document_chunks_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"
