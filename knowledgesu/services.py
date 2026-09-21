from __future__ import annotations

import re
from pathlib import Path

from knowledgesu.choices import DocStatus, DocType
from knowledgesu.models import DocumentChunk, KnowledgeDocument


CHUNK_SIZE = 900
CHUNK_OVERLAP = 120


def _chunk_text(text: str) -> list[str]:
    cleaned = re.sub(r"\r\n?", "\n", text).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + CHUNK_SIZE, length)
        if end < length:
            # Prefer breaking on paragraph/sentence boundaries
            window = cleaned[start:end]
            break_at = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if break_at > CHUNK_SIZE // 3:
                end = start + break_at + 1
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= length:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def _extract_text(document: KnowledgeDocument) -> tuple[str, int | None]:
    if not document.file:
        raise ValueError("No file attached")

    path = Path(document.file.path)
    if not path.exists():
        raise ValueError("Uploaded file is missing on disk")

    suffix = path.suffix.lower()
    if document.doc_type == DocType.PDF or suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n\n".join(pages).strip(), len(reader.pages)

    if suffix in {".txt", ".md"} or document.doc_type in {DocType.TEXT, DocType.FAQ}:
        return path.read_text(encoding="utf-8", errors="ignore").strip(), None

    if suffix == ".docx" or document.doc_type == DocType.DOCX:
        try:
            from docx import Document as DocxDocument
        except ImportError as exc:
            raise ValueError("DOCX support requires python-docx") from exc
        doc = DocxDocument(str(path))
        return "\n".join(p.text for p in doc.paragraphs).strip(), None

    raise ValueError(f"Unsupported file type: {suffix or document.doc_type}")


def process_knowledge_document(document: KnowledgeDocument) -> KnowledgeDocument:
    """Extract text, create chunks, mark document ready (or failed)."""
    document.status = DocStatus.PROCESSING
    document.error_message = ""
    document.save(update_fields=["status", "error_message", "updated_at"])

    try:
        text, page_count = _extract_text(document)
        if not text:
            raise ValueError("No extractable text found in file")

        chunks = _chunk_text(text)
        if not chunks:
            raise ValueError("Could not split document into chunks")

        DocumentChunk.objects.filter(document=document).delete()
        from common.embeddings import embed_text

        DocumentChunk.objects.bulk_create(
            [
                DocumentChunk(
                    document=document,
                    content=chunk,
                    chunk_index=index,
                    token_count=len(chunk.split()),
                    embedding=embed_text(chunk),
                )
                for index, chunk in enumerate(chunks)
            ]
        )

        metadata = dict(document.metadata or {})
        if page_count is not None:
            metadata["page_count"] = page_count
        metadata["char_count"] = len(text)
        metadata["embedded"] = True
        metadata["chunk_count"] = len(chunks)
        document.metadata = metadata
        document.status = DocStatus.READY
        document.error_message = ""
        document.save(update_fields=["metadata", "status", "error_message", "updated_at"])
    except Exception as exc:  # noqa: BLE001 — surface any parse failure to admins
        document.status = DocStatus.FAILED
        document.error_message = str(exc)[:500]
        document.save(update_fields=["status", "error_message", "updated_at"])

    return document
