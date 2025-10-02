from django.db import migrations


def noop(*args, **kwargs):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0011_fix_competitorapp'),
    ]

    operations = [
        migrations.DeleteModel(
            name='SentimentSnapshot',
        ),
    ]
