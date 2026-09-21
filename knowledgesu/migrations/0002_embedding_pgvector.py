import pgvector.django.indexes
import pgvector.django.vector
from django.db import migrations
from pgvector.django import VectorExtension


class Migration(migrations.Migration):

    dependencies = [
        ("knowledgesu", "0001_initial"),
    ]

    operations = [
        VectorExtension(),
        # Drop old JSON embeddings; reembed_knowledge fills the pgvector column
        migrations.RunSQL(
            sql="ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding;",
            reverse_sql="ALTER TABLE document_chunks ADD COLUMN embedding jsonb NULL;",
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="documentchunk",
                    name="embedding",
                    field=pgvector.django.vector.VectorField(
                        blank=True, dimensions=384, null=True
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE document_chunks ADD COLUMN embedding vector(384) NULL;",
                    reverse_sql="ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding;",
                ),
            ],
        ),
        migrations.AddIndex(
            model_name="documentchunk",
            index=pgvector.django.indexes.HnswIndex(
                ef_construction=64,
                fields=["embedding"],
                m=16,
                name="document_chunks_embedding_hnsw",
                opclasses=["vector_cosine_ops"],
            ),
        ),
    ]
