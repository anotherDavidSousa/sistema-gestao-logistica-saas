# Generated manually — 2026-05-20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_cidadeentrega'),
    ]

    operations = [
        migrations.CreateModel(
            name='PosicaoVeiculo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('placa', models.CharField(db_index=True, max_length=10, verbose_name='Placa')),
                ('lat', models.FloatField(verbose_name='Latitude')),
                ('lng', models.FloatField(verbose_name='Longitude')),
                ('ignicao', models.BooleanField(verbose_name='Ignição')),
                ('capturado_em', models.DateTimeField(auto_now_add=True, verbose_name='Capturado em')),
                ('ultima_atualizacao_rastreador', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='Últ. atualização rastreador',
                )),
            ],
            options={
                'verbose_name': 'Posição de Veículo',
                'verbose_name_plural': 'Posições de Veículos',
                'ordering': ['-capturado_em'],
                'indexes': [
                    models.Index(fields=['placa', 'capturado_em'], name='core_posica_placa_4e7a3f_idx'),
                ],
            },
        ),
    ]
