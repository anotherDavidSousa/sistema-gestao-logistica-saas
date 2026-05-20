"""
Dashboard, busca global e mapa interativo para o admin.
URLs registradas em filial16/urls.py (antes do path admin/).
"""
import logging
from datetime import date, timedelta, datetime

import json
import requests as http_requests
from .locais_fixos import LOCAIS_FIXOS

from django.conf import settings
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

log = logging.getLogger(__name__)


def _parse_date(s):
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            pass
    return None


@staff_member_required
def dashboard_api(request):
    """Retorna JSON com dados do dashboard para a data solicitada."""
    date_str = request.GET.get('date', '')
    selected = _parse_date(date_str) if date_str else date.today() - timedelta(days=1)

    from .models import Cavalo
    from fila.models import OST, CTe

    base_qs = Cavalo.objects.filter(criado_em__date__lte=selected)
    total      = base_qs.count()
    frotas     = base_qs.filter(classificacao='frota').count()
    agregados  = base_qs.filter(classificacao='agregado').count()
    terceiros  = base_qs.filter(classificacao='terceiro').count()

    def pct(n):
        return round(n / total * 100) if total else 0

    placas_ost = set(
        OST.objects.filter(data_manifesto=selected)
           .exclude(placa_cavalo='')
           .values_list('placa_cavalo', flat=True)
    )
    placas_cte = set(
        CTe.objects.filter(data_emissao=selected)
           .exclude(placa_cavalo='')
           .values_list('placa_cavalo', flat=True)
    )
    placas_trab = placas_ost | placas_cte

    if placas_trab:
        trab_qs        = base_qs.filter(placa__in=placas_trab)
        frotas_trab    = trab_qs.filter(classificacao='frota').count()
        agregados_trab = trab_qs.filter(classificacao='agregado').count()
        terceiros_trab = trab_qs.filter(classificacao='terceiro').count()
    else:
        frotas_trab = agregados_trab = terceiros_trab = 0

    _flag_label = {ADDITION: 'adicionado', CHANGE: 'alterado', DELETION: 'removido'}
    _flag_color = {ADDITION: '#16a34a',    CHANGE: '#d97706',  DELETION: '#dc2626'}
    _flag_bg    = {ADDITION: '#dcfce7',    CHANGE: '#fef9c3',  DELETION: '#fef2f2'}

    recent = []
    for e in (LogEntry.objects
              .select_related('user', 'content_type')
              .order_by('-action_time')[:20]):
        model_label = ''
        if e.content_type:
            model_label = (
                e.content_type.app_labeled_name
                if hasattr(e.content_type, 'app_labeled_name')
                else e.content_type.model
            )
        recent.append({
            'user':      e.user.get_full_name() or e.user.username,
            'user_init': (e.user.get_full_name() or e.user.username or '?')[0].upper(),
            'action':    _flag_label.get(e.action_flag, 'modificado'),
            'color':     _flag_color.get(e.action_flag, '#6b7280'),
            'bg':        _flag_bg.get(e.action_flag, '#f1f5f9'),
            'object':    str(e.object_repr),
            'model':     model_label,
            'time':      e.action_time.strftime('%d/%m %H:%M'),
            'change':    e.get_change_message() if e.action_flag == CHANGE else '',
        })

    return JsonResponse({
        'date': selected.strftime('%Y-%m-%d'),
        'cards': {
            'total':         total,
            'frotas':        frotas,      'frotas_pct':    pct(frotas),
            'agregados':     agregados,   'agregados_pct': pct(agregados),
            'terceiros':     terceiros,   'terceiros_pct': pct(terceiros),
        },
        'chart': {
            'frotas_meta':    frotas,       'frotas_real':    frotas_trab,
            'agregados_meta': agregados,    'agregados_real': agregados_trab,
            'terceiros_meta': terceiros,    'terceiros_real': terceiros_trab,
        },
        'recent': recent,
    })


@staff_member_required
def global_search_api(request):
    """Busca global rapida: placas, motoristas, proprietarios, OST, CTe."""
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'results': [], 'q': q})

    from django.urls import reverse
    from .models import Cavalo, Carreta, Motorista, Proprietario
    from fila.models import OST, CTe

    results = []

    def add(tipo, label, sub, url):
        results.append({'tipo': tipo, 'label': label, 'sub': sub, 'url': url})

    for obj in Cavalo.objects.filter(placa__icontains=q)[:4]:
        add('Cavalo', obj.placa,
            obj.motorista.nome if hasattr(obj, 'motorista') and obj.motorista else '',
            reverse('admin:core_cavalo_change', args=[obj.pk]))

    for obj in Carreta.objects.filter(placa__icontains=q)[:4]:
        add('Carreta', obj.placa, obj.marca or '',
            reverse('admin:core_carreta_change', args=[obj.pk]))

    for obj in Motorista.objects.filter(Q(nome__icontains=q) | Q(cpf__icontains=q))[:4]:
        add('Motorista', obj.nome or '', obj.cpf or '',
            reverse('admin:core_motorista_change', args=[obj.pk]))

    for obj in Proprietario.objects.filter(
            Q(nome_razao_social__icontains=q) | Q(codigo__icontains=q))[:3]:
        add('Proprietario', obj.nome_razao_social or obj.codigo or '', obj.tipo or '',
            reverse('admin:core_proprietario_change', args=[obj.pk]))

    for obj in OST.objects.filter(
            Q(documento__icontains=q) | Q(motorista__icontains=q) |
            Q(placa_cavalo__icontains=q))[:3]:
        doc = '.'.join(filter(None, [obj.filial, obj.serie, obj.documento]))
        label = doc if doc else 'OST #' + str(obj.pk)
        add('OST', label, obj.motorista or '',
            reverse('admin:fila_ost_change', args=[obj.pk]))

    for obj in CTe.objects.filter(
            Q(numero_cte__icontains=q) | Q(motorista__icontains=q) |
            Q(placa_cavalo__icontains=q))[:3]:
        doc = '/'.join(filter(None, [obj.filial, obj.serie, obj.numero_cte]))
        label = doc if doc else 'CT-e #' + str(obj.pk)
        add('CT-e', label, obj.motorista or '',
            reverse('admin:fila_cte_change', args=[obj.pk]))

    return JsonResponse({'results': results[:18], 'q': q})


# -- Mapa interativo -----------------------------------------------------------

def _inoprime_url(path):
    base = getattr(settings, 'INOPRIME_API_URL', 'http://localhost:8001').rstrip('/')
    return base + path


@staff_member_required
def mapa_view(request):
    """Renderiza a pagina do mapa interativo."""
    return render(request, 'admin/mapa.html', {
        'title': 'Mapa de Frota',
        'has_permission': True,
        'locais_fixos_json': json.dumps(LOCAIS_FIXOS, ensure_ascii=False),
    })


@staff_member_required
def mapa_veiculos_api(request):
    """Proxy para FastAPI Inoprime /veiculos."""
    url = _inoprime_url('/veiculos')
    try:
        resp = http_requests.get(
            url,
            params={k: v for k, v in request.GET.items()},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except http_requests.exceptions.ConnectionError:
        log.warning('Inoprime indisponivel em %s', url)
        return JsonResponse(
            {'erro': 'FastAPI Inoprime indisponivel. Verifique se o servico esta rodando.', 'veiculos': []},
            status=503,
        )
    except ValueError:
        # resp.json() falhou — a URL retornou HTML em vez de JSON
        preview = resp.text[:300] if 'resp' in dir() else '(sem resposta)'
        log.error('Inoprime retornou resposta nao-JSON em %s — preview: %s', url, preview)
        return JsonResponse(
            {'erro': 'URL da Inoprime retornou HTML (nao-JSON). Verifique INOPRIME_API_URL. URL chamada: ' + url,
             'veiculos': []},
            status=502,
        )
    except Exception as exc:
        log.error('Erro ao consultar Inoprime em %s: %s', url, exc)
        return JsonResponse({'erro': str(exc), 'veiculos': []}, status=502)

    veiculos = data.get('veiculos', data if isinstance(data, list) else [])

    # Normaliza lat/lng e placa (TrackerPrime repete a placa: "MSL2J23 MSL2J23MG" → "MSL2J23")
    for v in veiculos:
        if 'lat' not in v and 'latitude' in v:
            v['lat'] = v['latitude']
        if 'lng' not in v and 'longitude' in v:
            v['lng'] = v['longitude']
        raw = (v.get('placa') or '').strip()
        v['placa'] = raw.split()[0] if raw else ''

    # Filtra: apenas cavalos com classificação 'agregado' cadastrados no banco
    from .models import Cavalo
    placas_agregados = set(
        p.upper() for p in
        Cavalo.objects.filter(classificacao='agregado').values_list('placa', flat=True)
    )
    if placas_agregados:
        veiculos = [v for v in veiculos if (v.get('placa') or '').upper() in placas_agregados]

    return JsonResponse({
        'total': len(veiculos),
        'ultima_atualizacao': data.get('ultima_atualizacao'),
        'veiculos': veiculos,
    })


@staff_member_required
def mapa_cidades_api(request):
    """Lista as cidades de entrega com seus poligonos."""
    from .models import CidadeEntrega
    cidades = list(
        CidadeEntrega.objects.values('id', 'nome', 'poligono', 'cor', 'ativa_semana')
    )
    return JsonResponse({'cidades': cidades})


@staff_member_required
@require_POST
def mapa_cidade_toggle(request, pk):
    """Alterna ativa_semana de uma cidade (AJAX POST)."""
    from .models import CidadeEntrega
    try:
        cidade = CidadeEntrega.objects.get(pk=pk)
    except CidadeEntrega.DoesNotExist:
        return JsonResponse({'erro': 'Cidade nao encontrada.'}, status=404)
    cidade.ativa_semana = not cidade.ativa_semana
    cidade.save(update_fields=['ativa_semana', 'atualizado_em'])
    return JsonResponse({
        'id': cidade.pk,
        'nome': cidade.nome,
        'ativa_semana': cidade.ativa_semana,
    })


@staff_member_required
def frota_ultima_posicao(request, placa):
    """
    Retorna a última posição registrada de um veículo pelo cron.
    Usado pelo popup do mapa para mostrar 'Última posição registrada em ...'.
    """
    from .models import PosicaoVeiculo
    placa = placa.strip().upper()
    pos = (
        PosicaoVeiculo.objects
        .filter(placa=placa)
        .order_by('-capturado_em')
        .values('capturado_em', 'ignicao', 'lat', 'lng')
        .first()
    )
    if not pos:
        return JsonResponse({'erro': 'Sem histórico'}, status=404)

    # Formata data no fuso horário local (America/Sao_Paulo via USE_TZ + TIME_ZONE)
    from django.utils import timezone as dj_tz
    capturado = pos['capturado_em']
    capturado_local = dj_tz.localtime(capturado) if dj_tz.is_aware(capturado) else capturado
    return JsonResponse({
        'capturado_em': capturado_local.strftime('%d/%m/%Y %H:%M'),
        'ignicao': pos['ignicao'],
    })
