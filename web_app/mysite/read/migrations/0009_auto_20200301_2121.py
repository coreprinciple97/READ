# Generated by Django 3.0.3 on 2020-03-01 15:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('read', '0008_classroom_pending_requests'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classroom',
            name='name',
            field=models.SlugField(max_length=100),
        ),
    ]
