"""
Management command: salvar_posicoes
====================================
Consulta a inoprime-api (/veiculos) e grava um snapshot de posição
para cada veículo ativo no banco de dados (model PosicaoVeiculo).

Uso:
    python manage.py salvar_posicoes
    python manage.py salvar_posicoes --dry-run   # apenas imprime, não salva
    python manage.py salvar_posicoes --url http://localhost:8001

Chamado automaticamente a cada 5 minutos pelo serviço 'cron' no Docker Compose.

Nota sobre ultima_atualizacao_rastreador:
    O endpoint /veiculos do TrackerPrime não retorna o timestamp do último sinal
    do rastreador (campo "Data" visível no card do mapa). Esse dado só está
    disponível na tela de detalhe por veículo. Por ora o campo é salvo como None.
    Quando a página de histórico for implementada, poderemos buscar esse dado
    separadamente via /rota/{id}/hoje e pegar o timestamp da última posição.
"""

import logging

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import PosicaoVeiculo

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Salva snapshot de posição de todos os veículos rastreados no banco de dados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            default=None,
            help='URL base da inoprime-api (padrão: INOPRIME_API_URL do settings)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas imprime os dados, não salva no banco.',
        )
        parser.add_argument(
            '--timeout',
            type=int,
            default=30,
            help='Timeout da requisição HTTP em segundos (padrão: 30)',
        )

    def handle(self, *args, **options):
        base_url = options['url'] or getattr(settings, 'INOPRIME_API_URL', 'http://localhost:8001')
        endpoint = f'{base_url.rstrip("/")}/veiculos'
        dry_run  = options['dry_run']
        timeout  = options['timeout']

        self.stdout.write(f'Consultando {endpoint} ...')

        try:
            resp = requests.get(endpoint, timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError(f'Erro ao consultar inoprime-api: {exc}') from exc

        dados = resp.json()
        veiculos = dados.get('veiculos', [])

        if not veiculos:
            self.stdout.write(self.style.WARNING('Nenhum veículo retornado pela API.'))
            return

        registros: list[PosicaoVeiculo] = []
        ignorados = 0

        for v in veiculos:
            placa = (v.get('placa') or '').strip().upper()
            if not placa:
                ignorados += 1
                continue

            # Coordenadas — chegam como string ou float dependendo da versão da API
            try:
                lat = float(v.get('lat') or v.get('latitude') or 0)
                lng = float(v.get('lng') or v.get('longitude') or 0)
            except (TypeError, ValueError):
                log.debug('Veículo %s com coordenadas inválidas — ignorado.', placa)
                ignorados += 1
                continue

            if lat == 0 and lng == 0:
                log.debug('Veículo %s sem coordenadas — ignorado.', placa)
                ignorados += 1
                continue

            ignicao_raw = v.get('ignicao', 0)
            ignicao = bool(ignicao_raw) if ignicao_raw is not None else False

            if dry_run:
                self.stdout.write(
                    f'  {placa:10s}  lat={lat:.5f}  lng={lng:.5f}  '
                    f'ign={"ON " if ignicao else "off"}'
                )

            # Acumula para bulk_create (e conta no dry-run também)
            registros.append(PosicaoVeiculo(
                placa=placa,
                lat=lat,
                lng=lng,
                ignicao=ignicao,
                ultima_atualizacao_rastreador=None,  # não disponível no endpoint /veiculos
            ))

        extra = f' ({ignorados} sem coordenadas ignorados)' if ignorados else ''
        if not dry_run:
            PosicaoVeiculo.objects.bulk_create(registros)
            self.stdout.write(self.style.SUCCESS('Salvas ' + str(len(registros)) + ' posicoes.' + extra))
        else:
            self.stdout.write(self.style.SUCCESS('Dry-run: ' + str(len(registros)) + ' registros seriam salvos.' + extra))
