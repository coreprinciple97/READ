# Generated by Django 3.0.3 on 2020-03-01 14:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('read', '0007_auto_20200301_1921'),
    ]

    operations = [
        migrations.AddField(
            model_name='classroom',
            name='pending_requests',
            field=models.IntegerField(default=0),
        ),
    ]