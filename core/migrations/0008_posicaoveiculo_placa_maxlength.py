from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_posicaoveiculo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='posicaoveiculo',
            name='placa',
            field=models.CharField(
                db_index=True,
                max_length=30,
                verbose_name='Placa',
            ),
        ),
    ]
