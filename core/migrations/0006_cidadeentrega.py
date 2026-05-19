from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_fix_motorista_id_sequence'),
    ]

    operations = [
        migrations.CreateModel(
            name='CidadeEntrega',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=100, unique=True, verbose_name='Cidade')),
                ('poligono', models.JSONField(
                    blank=True,
                    default=list,
                    help_text='Lista de pares [[lat, lng], ...] definindo os vértices da zona.',
                    verbose_name='Polígono',
                )),
                ('cor', models.CharField(
                    default='#3b82f6',
                    help_text='Cor hexadecimal da zona no mapa (ex.: #3b82f6).',
                    max_length=7,
                    verbose_name='Cor',
                )),
                ('ativa_semana', models.BooleanField(
                    default=False,
                    help_text='Indica se a cidade está sendo atendida na semana atual.',
                    verbose_name='Ativa nesta semana',
                )),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Cidade de Entrega',
                'verbose_name_plural': 'Cidades de Entrega',
                'ordering': ['nome'],
            },
        ),
    ]
