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


# ── Histórico de frota ────────────────────────────────────────────────────────

@staff_member_required
def frota_historico_view(request):
    """Renderiza a página de histórico de posições de um veículo."""
    from .models import PosicaoVeiculo, Cavalo
    from django.utils import timezone as dj_tz

    cutoff = dj_tz.now() - timedelta(days=90)
    placas_com_dados = list(
        PosicaoVeiculo.objects
        .filter(capturado_em__gte=cutoff)
        .values_list('placa', flat=True)
        .distinct()
        .order_by('placa')
    )
    cavalos = {c.placa.upper(): c for c in Cavalo.objects.all()}
    opcoes = []
    for placa in placas_com_dados:
        c = cavalos.get(placa.upper())
        motorista = ''
        if c and hasattr(c, 'motorista') and c.motorista:
            motorista = c.motorista.nome
        opcoes.append({
            'placa': placa,
            'label': f'{placa}' + (f' — {motorista}' if motorista else ''),
        })
    return render(request, 'admin/historico_frota.html', {
        'title': 'Historico de Frota',
        'has_permission': True,
        'opcoes_veiculos': json.dumps(opcoes, ensure_ascii=False),
    })


def _haversine(lat1, lng1, lat2, lng2):
    import math
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _point_in_polygon(lat, lng, polygon):
    """Ray-casting point-in-polygon. polygon = [[lat, lng], ...]"""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / (yj - yi + 1e-10) + xi
        ):
            inside = not inside
        j = i
    return inside


@staff_member_required
def frota_historico_api(request):
    """
    API JSON para o historico de posicoes de um veiculo.
    Params: placa, data_inicio (YYYY-MM-DD), data_fim (YYYY-MM-DD)
    """
    import math
    from .models import PosicaoVeiculo, CidadeEntrega
    from django.utils import timezone as dj_tz

    placa = (request.GET.get('placa') or '').strip().upper()
    if not placa:
        return JsonResponse({'erro': 'Parametro placa obrigatorio.'}, status=400)

    data_inicio = _parse_date(request.GET.get('data_inicio', '')) or date.today()
    data_fim = _parse_date(request.GET.get('data_fim', '')) or data_inicio

    try:
        import pytz
        tz = pytz.timezone('America/Sao_Paulo')
    except Exception:
        tz = None

    def make_aware_local(d, t_min=True):
        from datetime import time as dtime
        t = dtime.min if t_min else dtime(23, 59, 59)
        dt = datetime.combine(d, t)
        if tz:
            return dj_tz.make_aware(dt, tz)
        return dj_tz.make_aware(dt)

    dt_inicio = make_aware_local(data_inicio, t_min=True)
    dt_fim = make_aware_local(data_fim, t_min=False)

    posicoes_qs = list(
        PosicaoVeiculo.objects
        .filter(placa=placa, capturado_em__range=(dt_inicio, dt_fim))
        .order_by('capturado_em')
        .values('lat', 'lng', 'ignicao', 'capturado_em')
    )

    if not posicoes_qs:
        return JsonResponse({'posicoes': [], 'stats': None, 'aviso': 'Sem dados para este periodo.'})

    def fmt_ts(ts):
        local = dj_tz.localtime(ts, tz) if (tz and dj_tz.is_aware(ts)) else ts
        return local.strftime('%d/%m/%Y %H:%M')

    # Serializa posicoes
    posicoes_out = [
        {'lat': p['lat'], 'lng': p['lng'], 'ignicao': p['ignicao'], 'ts': fmt_ts(p['capturado_em'])}
        for p in posicoes_qs
    ]

    # KM total
    km_total = 0.0
    for i in range(1, len(posicoes_qs)):
        km_total += _haversine(
            posicoes_qs[i - 1]['lat'], posicoes_qs[i - 1]['lng'],
            posicoes_qs[i]['lat'], posicoes_qs[i]['lng'],
        )

    # Paradas longas (ignicao off >= 15 min consecutivos)
    PARADA_MIN = 15
    paradas = []
    i = 0
    while i < len(posicoes_qs):
        if not posicoes_qs[i]['ignicao']:
            j = i
            while j < len(posicoes_qs) and not posicoes_qs[j]['ignicao']:
                j += 1
            dur = (posicoes_qs[j - 1]['capturado_em'] - posicoes_qs[i]['capturado_em']).total_seconds() / 60
            if dur >= PARADA_MIN:
                mid = (i + j - 1) // 2
                paradas.append({
                    'lat': posicoes_qs[mid]['lat'],
                    'lng': posicoes_qs[mid]['lng'],
                    'inicio': fmt_ts(posicoes_qs[i]['capturado_em']),
                    'fim': fmt_ts(posicoes_qs[j - 1]['capturado_em']),
                    'duracao_min': round(dur),
                })
            i = j
        else:
            i += 1

    # Cidades ativas visitadas
    cidades_visitadas = []
    for c in CidadeEntrega.objects.filter(ativa_semana=True).values('nome', 'poligono'):
        poly = c.get('poligono')
        if not poly:
            continue
        if isinstance(poly, str):
            import json as _j
            try:
                poly = _j.loads(poly)
            except Exception:
                continue
        for p in posicoes_qs:
            if _point_in_polygon(p['lat'], p['lng'], poly):
                cidades_visitadas.append(c['nome'])
                break

    # Locais fixos visitados
    locais_visitados = []
    for loc in LOCAIS_FIXOS:
        poly = loc.get('poligono')
        if not poly:
            continue
        for p in posicoes_qs:
            if _point_in_polygon(p['lat'], p['lng'], poly):
                locais_visitados.append({'id': loc['id'], 'nome': loc['nome']})
                break

    return JsonResponse({
        'posicoes': posicoes_out,
        'stats': {
            'km_total': round(km_total, 1),
            'total_pontos': len(posicoes_qs),
            'paradas_longas': paradas,
            'cidades_visitadas': sorted(cidades_visitadas),
            'locais_visitados': locais_visitados,
            'periodo_inicio': fmt_ts(posicoes_qs[0]['capturado_em']),
            'periodo_fim': fmt_ts(posicoes_qs[-1]['capturado_em']),
        },
    })
