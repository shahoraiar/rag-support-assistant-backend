from rest_framework import serializers

from knowledgesu.choices import DocType
from knowledgesu.models import KnowledgeDocument


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.CharField(source="uploaded_by.get_full_name", read_only=True)
    chunk_count = serializers.IntegerField(read_only=True)
    page_count = serializers.IntegerField(read_only=True, allow_null=True)
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeDocument
        fields = (
            "id",
            "title",
            "doc_type",
            "status",
            "uploaded_by",
            "page_count",
            "chunk_count",
            "file_url",
            "error_message",
            "created_at",
        )
        read_only_fields = (
            "id",
            "status",
            "uploaded_by",
            "chunk_count",
            "page_count",
            "file_url",
            "error_message",
            "created_at",
        )

    def get_file_url(self, obj: KnowledgeDocument) -> str | None:
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class KnowledgeDocumentUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeDocument
        fields = ("title", "file", "doc_type")

    def validate(self, attrs):
        file = attrs.get("file")
        doc_type = attrs.get("doc_type")
        if file and not doc_type:
            ext = file.name.rsplit(".", 1)[-1].lower()
            ext_map = {"pdf": DocType.PDF, "docx": DocType.DOCX, "txt": DocType.TEXT, "md": DocType.TEXT}
            attrs["doc_type"] = ext_map.get(ext, DocType.TEXT)
        if not attrs.get("file"):
            raise serializers.ValidationError({"file": "A file is required."})
        return attrs

    def create(self, validated_data):
        validated_data["uploaded_by"] = self.context["request"].user
        return super().create(validated_data)
