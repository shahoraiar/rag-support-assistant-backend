from django.db import models


class DocType(models.TextChoices):
    PDF = "pdf", "PDF"
    FAQ = "faq", "FAQ"
    DOCX = "docx", "DOCX"
    TEXT = "text", "Text"


class DocStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"
