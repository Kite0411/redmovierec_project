"""
Auto-generated migration to add created_at to Rating.

This migration was created to match the current `models.py` which
defines `created_at = models.DateTimeField(auto_now_add=True, null=True)`
for the Rating model. Existing rows are allowed to have NULL.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('moviehub', '0002_userprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='rating',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
