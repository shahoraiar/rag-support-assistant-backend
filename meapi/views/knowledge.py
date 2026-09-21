from rest_framework import generics, parsers, status
from rest_framework.response import Response

from common.permissions import IsAdminUser
from knowledgesu.models import KnowledgeDocument
from knowledgesu.services import process_knowledge_document
from meapi.serializers.knowledge import KnowledgeDocumentSerializer, KnowledgeDocumentUploadSerializer


class KnowledgeDocumentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminUser]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return KnowledgeDocumentUploadSerializer
        return KnowledgeDocumentSerializer

    def get_queryset(self):
        return KnowledgeDocument.objects.select_related("uploaded_by")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        process_knowledge_document(document)
        document.refresh_from_db()
        out = KnowledgeDocumentSerializer(document, context={"request": request})
        headers = self.get_success_headers(out.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)


class KnowledgeDocumentDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = KnowledgeDocumentSerializer
    permission_classes = [IsAdminUser]
    queryset = KnowledgeDocument.objects.all()

    def perform_destroy(self, instance):
        # Remove the physical file from MEDIA_ROOT as well as the DB row
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()
