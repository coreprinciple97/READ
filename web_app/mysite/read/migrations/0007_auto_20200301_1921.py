# Generated by Django 3.0.3 on 2020-03-01 13:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('read', '0006_auto_20200301_1921'),
    ]

    operations = [
        migrations.AlterField(
            model_name='document',
            name='document_file',
            field=models.FileField(null=True, upload_to='read/documents/'),
        ),
    ]
