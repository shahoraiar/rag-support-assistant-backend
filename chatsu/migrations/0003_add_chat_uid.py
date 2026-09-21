from django.db import migrations, models


def backfill_chat_uids(apps, schema_editor):
    ChatSession = apps.get_model("chatsu", "ChatSession")
    next_num = 1001
    for session in ChatSession.objects.order_by("id"):
        session.chat_uid = f"C-{next_num}"
        session.save(update_fields=["chat_uid"])
        next_num += 1


class Migration(migrations.Migration):

    dependencies = [
        ("chatsu", "0002_chatmessage_seen_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsession",
            name="chat_uid",
            field=models.CharField(blank=True, default="", editable=False, max_length=20),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_chat_uids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="chatsession",
            name="chat_uid",
            field=models.CharField(blank=True, editable=False, max_length=20, unique=True),
        ),
    ]
