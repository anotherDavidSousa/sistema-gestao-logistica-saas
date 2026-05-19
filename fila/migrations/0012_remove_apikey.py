from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fila', '0011_remove_carregamento'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ApiKey',
        ),
    ]
