from django.contrib import admin

from knowledgesu.models import DocumentChunk, KnowledgeDocument


class DocumentChunkInline(admin.TabularInline):
    model = DocumentChunk
    extra = 0


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "doc_type", "status", "uploaded_by", "created_at")
    list_filter = ("status", "doc_type")
    inlines = [DocumentChunkInline]
