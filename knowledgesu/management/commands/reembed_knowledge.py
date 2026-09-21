from django.core.management.base import BaseCommand

from common.embeddings import embed_text
from knowledgesu.choices import DocStatus
from knowledgesu.models import DocumentChunk, KnowledgeDocument
from knowledgesu.services import process_knowledge_document


class Command(BaseCommand):
    help = "Embed (or re-process) READY knowledge PDF chunks into the vector store"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reprocess",
            action="store_true",
            help="Re-extract text from files and rebuild chunks+embeddings",
        )

    def handle(self, *args, **options):
        if options["reprocess"]:
            docs = KnowledgeDocument.objects.exclude(status=DocStatus.PROCESSING)
            self.stdout.write(f"Re-processing {docs.count()} documents…")
            for doc in docs:
                process_knowledge_document(doc)
                self.stdout.write(f"  ✓ {doc.title} ({doc.status})")
            return

        chunks = DocumentChunk.objects.filter(document__status=DocStatus.READY)
        updated = 0
        for chunk in chunks.iterator(chunk_size=100):
            chunk.embedding = embed_text(chunk.content or "")
            chunk.save(update_fields=["embedding", "updated_at"])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Embedded {updated} chunks"))
