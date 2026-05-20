"""
Management command: salvar_posicoes
====================================
Consulta a inoprime-api (/veiculos) e grava um snapshot de posicao
para cada Cavalo com classificacao=agregado no banco de dados.

Uso:
    python manage.py salvar_posicoes
    python manage.py salvar_posicoes --dry-run
    python manage.py salvar_posicoes --url http://localhost:8001

Chamado automaticamente a cada 5 minutos pelo servico cron no Docker Compose.
"""

import logging

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import PosicaoVeiculo, Cavalo

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Salva snapshot de posicao dos Cavalos agregados no banco de dados."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            default=None,
            help="URL base da inoprime-api (padrao: INOPRIME_API_URL do settings)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas imprime os dados, nao salva no banco.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=30,
            help="Timeout da requisicao HTTP em segundos (padrao: 30)",
        )

    def handle(self, *args, **options):
        base_url = options["url"] or getattr(settings, "INOPRIME_API_URL", "http://localhost:8001")
        endpoint = base_url.rstrip("/") + "/veiculos"
        dry_run = options["dry_run"]
        timeout = options["timeout"]

        # Carrega apenas placas de Cavalos agregados cadastrados no sistema
        placas_agregados = set(
            p.upper() for p in
            Cavalo.objects.filter(classificacao="agregado")
            .exclude(placa__isnull=True)
            .exclude(placa="")
            .values_list("placa", flat=True)
        )

        if not placas_agregados:
            self.stdout.write(self.style.WARNING(
                "Nenhum Cavalo com classificacao=agregado encontrado no banco. Nada a salvar."
            ))
            return

        self.stdout.write("Consultando " + endpoint + " ...")
        self.stdout.write("Placas de agregados no sistema: " + str(len(placas_agregados)))

        try:
            resp = requests.get(endpoint, timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise CommandError("Erro ao consultar inoprime-api: " + str(exc)) from exc

        dados = resp.json()
        veiculos = dados.get("veiculos", [])

        if not veiculos:
            self.stdout.write(self.style.WARNING("Nenhum veiculo retornado pela API."))
            return

        registros = []
        ignorados = 0
        nao_agregado = 0

        for v in veiculos:
            placa_raw = (v.get("placa") or "").strip()
            # TrackerPrime retorna "PLACA DESCRICAO" — pega so o primeiro token
            placa = placa_raw.split()[0].upper() if placa_raw else ""
            if not placa:
                ignorados += 1
                continue

            # Salva apenas Cavalos agregados cadastrados no sistema
            if placa not in placas_agregados:
                nao_agregado += 1
                continue

            try:
                lat = float(v.get("lat") or v.get("latitude") or 0)
                lng = float(v.get("lng") or v.get("longitude") or 0)
            except (TypeError, ValueError):
                log.debug("Veiculo %s com coordenadas invalidas — ignorado.", placa)
                ignorados += 1
                continue

            if lat == 0 and lng == 0:
                log.debug("Veiculo %s sem coordenadas — ignorado.", placa)
                ignorados += 1
                continue

            ignicao_raw = v.get("ignicao", 0)
            ignicao = bool(ignicao_raw) if ignicao_raw is not None else False

            if dry_run:
                self.stdout.write(
                    "  " + placa.ljust(10) + "  lat=" + str(round(lat, 5))
                    + "  lng=" + str(round(lng, 5))
                    + "  ign=" + ("ON " if ignicao else "off")
                )

            registros.append(PosicaoVeiculo(
                placa=placa,
                lat=lat,
                lng=lng,
                ignicao=ignicao,
                ultima_atualizacao_rastreador=None,
            ))

        extra_parts = []
        if ignorados:
            extra_parts.append(str(ignorados) + " sem coordenadas ignorados")
        if nao_agregado:
            extra_parts.append(str(nao_agregado) + " nao agregados ignorados")
        extra = " (" + ", ".join(extra_parts) + ")" if extra_parts else ""

        if not dry_run:
            PosicaoVeiculo.objects.bulk_create(registros)
            self.stdout.write(self.style.SUCCESS(
                "Salvas " + str(len(registros)) + " posicoes de agregados." + extra
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "Dry-run: " + str(len(registros)) + " registros seriam salvos." + extra
            ))
