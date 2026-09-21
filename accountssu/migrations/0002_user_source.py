from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accountssu", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="source",
            field=models.CharField(
                choices=[("email", "Email / password"), ("google", "Google")],
                default="email",
                help_text="How this account was created (email/password or Google).",
                max_length=20,
            ),
        ),
    ]
