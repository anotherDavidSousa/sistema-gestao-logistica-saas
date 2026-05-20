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

Sobre o campo ultima_atualizacao_rastreador:
    O campo tenta capturar o timestamp interno do rastreador GPS — indica
    quando o dispositivo enviou a última posição válida. Se este valor divergir
    muito de capturado_em, o rastreador pode estar com falha ou sem sinal.
    Candidatos testados (ordem de prioridade): ultima_atualizacao, data_posicao,
    posicao_data, dt_gps, gps_data, data_gps, posicao_em, updated_at.
    Se nenhum for encontrado, o campo fica None e um aviso é exibido na
    primeira execução.
"""

import logging
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.utils import timezone as dj_timezone

from core.models import PosicaoVeiculo

log = logging.getLogger(__name__)

# Candidatos para o timestamp do rastreador — testados na ordem
_TIMESTAMP_CANDIDATOS = [
    'ultima_atualizacao',
    'data_posicao',
    'posicao_data',
    'dt_gps',
    'gps_data',
    'data_gps',
    'posicao_em',
    'updated_at',
    'updatedAt',
    'last_update',
]


def _parse_ts(valor: str | None) -> datetime | None:
    """Tenta converter uma string de data/hora em datetime aware (UTC)."""
    if not valor:
        return None
    try:
        dt = parse_datetime(str(valor))
        if dt is None:
            # Tenta formato comum do TrackerPrime: 'DD/MM/YYYY HH:MM:SS'
            for fmt in ('%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
                try:
                    dt = datetime.strptime(str(valor), fmt)
                    break
                except ValueError:
                    continue
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _campo_ts_rastreador(veiculo: dict, aviso_dado: list) -> datetime | None:
    """Extrai o timestamp do rastreador testando os candidatos conhecidos."""
    for campo in _TIMESTAMP_CANDIDATOS:
        valor = veiculo.get(campo)
        if valor is not None:
            return _parse_ts(valor)
    # Nenhum candidato encontrado — emite aviso apenas uma vez por execução
    if not aviso_dado:
        campos_disponiveis = list(veiculo.keys())
        log.warning(
            'Não foi possível identificar o campo de timestamp do rastreador. '
            'Campos disponíveis no veículo: %s  '
            'Edite _TIMESTAMP_CANDIDATOS em salvar_posicoes.py para mapear o campo correto.',
            campos_disponiveis,
        )
        aviso_dado.append(True)
    return None


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

        aviso_dado: list = []
        registros: list[PosicaoVeiculo] = []

        for v in veiculos:
            placa = (v.get('placa') or '').strip().upper()
            if not placa:
                continue

            lat = v.get('lat') or v.get('latitude')
            lng = v.get('lng') or v.get('longitude')
            if lat is None or lng is None:
                log.debug('Veículo %s sem coordenadas — ignorado.', placa)
                continue

            ignicao_raw = v.get('ignicao', 0)
            ignicao = bool(ignicao_raw) if ignicao_raw is not None else False

            ts_rastreador = _campo_ts_rastreador(v, aviso_dado)

            if dry_run:
                self.stdout.write(
                    f'  {placa:10s}  lat={lat:.5f}  lng={lng:.5f}  '
                    f'ign={"ON" if ignicao else "off"}  '
                    f'ts_rastreador={ts_rastreador}'
                )
            else:
                registros.append(PosicaoVeiculo(
                    placa=placa,
                    lat=float(lat),
                    lng=float(lng),
                    ignicao=ignicao,
                    ultima_atualizacao_rastreador=ts_rastreador,
                ))

        if not dry_run:
            PosicaoVeiculo.objects.bulk_create(registros)
            self.stdout.write(
                self.style.SUCCESS(f'Salvas {len(registros)} posições.')
            )
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Dry-run: {len(registros)} registros seriam salvos.'
            ))
