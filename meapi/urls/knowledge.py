from django.urls import path

from meapi.views.knowledge import KnowledgeDocumentDetailView, KnowledgeDocumentListCreateView

urlpatterns = [
    path("knowledge/documents/", KnowledgeDocumentListCreateView.as_view(), name="knowledge-documents"),
    path("knowledge/documents/<int:pk>/", KnowledgeDocumentDetailView.as_view(), name="knowledge-document-detail"),
]
