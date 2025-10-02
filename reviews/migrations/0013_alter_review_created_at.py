from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("reviews", "0012_remove_sentimentsnapshot"),
    ]

    operations = [
        migrations.AlterField(
            model_name="review",
            name="created_at",
            field=models.DateTimeField(default=django.utils.timezone.now, db_index=True),
        ),
    ]
