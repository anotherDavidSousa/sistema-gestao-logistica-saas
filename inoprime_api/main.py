"""
TrackerPrime API — Wrapper local com cache inteligente
======================================================
Busca os veículos do site trackerprime.inoprime.com.br e os serve
via REST, sem sobrecarregar o servidor original.

Estratégia anti-sobrecarga:
  - Apenas UMA sessão autenticada é mantida.
  - Posições do mapa: buscadas uma vez a cada REFRESH_INTERVAL_MINUTES (cache global).
  - Rotas/posições históricas: cache por (veiculo_id + data), TTL de 2 min para
    o dia atual e 30 min para dias passados (dados imutáveis).
  - Relogin automático caso a sessão expire.

Endpoints:
  GET /                                   → status da API e do cache
  GET /veiculos                           → todos os veículos (cache 5 min)
  GET /veiculos/{id}                      → veículo por ID interno
  GET /buscar?placa=                      → busca por placa (parcial)
  GET /stats                              → resumo estatístico da frota
  GET /rota/{id}?inicio=&fim=             → histórico de posições de um veículo
  GET /rota/{id}/hoje                     → posições de hoje do veículo
  POST /buscar-placas                     → busca rápida de lista de placas no cache (mapa)
  POST /posicoes-lista                    → posições por período para lista de placas
  POST /atualizar                         → força atualização imediata do cache

Notas:
  - Placas com sufixo de UF (ex: "QWW1G07MG") são normalizadas automaticamente.
  - /buscar-placas usa o cache local — resposta em milissegundos, zero impacto no site.
  - /posicoes-lista faz uma requisição por veículo encontrado — use períodos curtos.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List

import os

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─── Configuração ──────────────────────────────────────────────────────────────
BASE_URL        = "https://trackerprime.inoprime.com.br"
LOGIN_URL       = f"{BASE_URL}/login"
VEICULOS_URL    = f"{BASE_URL}/home-v2?veiculos=true"
POSICOES_URL    = f"{BASE_URL}/posicoes/simplificado"
EMAIL           = os.environ.get("INOPRIME_EMAIL", "")
PASSWORD        = os.environ.get("INOPRIME_PASSWORD", "")

REFRESH_INTERVAL_MINUTES = 5   # intervalo do cache de veículos (posição atual)
REQUEST_TIMEOUT          = 45  # segundos para timeout (rotas podem ser grandes)

# TTL do cache de rotas históricas
ROTA_TTL_HOJE_SEG    = 120   # 2 min para o dia atual (dados mudam)
ROTA_TTL_PASSADO_SEG = 1800  # 30 min para dias passados (dados imutáveis)

# ─── Estado global ─────────────────────────────────────────────────────────────
cache: dict = {
    "veiculos":         [],
    "ultima_atualizacao": None,
    "status":           "aguardando primeira carga",
    "total_atualizacoes": 0,
    "erros":            0,
}

# Cache de rotas: chave = "veiculo_id|YYYY-MM-DD|YYYY-MM-DD"
# valor = {"data": [...], "ts": timestamp_unix, "total": int}
rota_cache: dict = {}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
})

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("trackerapi")

# ─── Autenticação ──────────────────────────────────────────────────────────────

def _obter_csrf() -> str:
    """Carrega a página de login e extrai o token CSRF."""
    resp = session.get(LOGIN_URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    from html.parser import HTMLParser

    class CsrfParser(HTMLParser):
        token = None
        def handle_starttag(self, tag, attrs):
            if tag == "input":
                attrs_dict = dict(attrs)
                if attrs_dict.get("name") == "_token":
                    self.token = attrs_dict.get("value")

    parser = CsrfParser()
    parser.feed(resp.text)
    if not parser.token:
        raise RuntimeError("Token CSRF não encontrado na página de login.")
    return parser.token


def fazer_login() -> bool:
    """Faz login no site e mantém a sessão autenticada."""
    try:
        log.info("Realizando login no TrackerPrime...")
        csrf = _obter_csrf()
        resp = session.post(
            LOGIN_URL,
            data={"_token": csrf, "email": EMAIL, "password": PASSWORD},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        # Login bem-sucedido redireciona para /home
        if "login" in resp.url:
            log.error("Login falhou — credenciais inválidas ou bloqueio.")
            return False
        log.info("Login realizado com sucesso.")
        return True
    except Exception as e:
        log.error(f"Erro no login: {e}")
        return False


# ─── Busca de dados ────────────────────────────────────────────────────────────

def _checar_sessao(resp: requests.Response) -> bool:
    """Retorna True se a sessão expirou e precisou de relogin."""
    if resp.status_code in (401, 403) or "login" in resp.url:
        log.warning("Sessão expirada, refazendo login...")
        return not fazer_login()
    return False


def buscar_veiculos() -> list[dict]:
    """Faz a requisição ao endpoint de veículos e retorna a lista JSON."""
    resp = session.get(
        VEICULOS_URL,
        timeout=REQUEST_TIMEOUT,
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    if _checar_sessao(resp):
        raise RuntimeError("Não foi possível renovar a sessão.")
    if "login" in resp.url:
        resp = session.get(VEICULOS_URL, timeout=REQUEST_TIMEOUT,
                           headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"})

    resp.raise_for_status()
    dados = resp.json()
    if not isinstance(dados, list):
        raise ValueError(f"Resposta inesperada: {str(dados)[:200]}")
    return dados


def _get_csrf_da_sessao() -> str:
    """Obtém o CSRF token da página de posições (sessão já autenticada)."""
    resp = session.get(POSICOES_URL, timeout=REQUEST_TIMEOUT)
    from html.parser import HTMLParser
    class P(HTMLParser):
        token = None
        def handle_starttag(self, tag, attrs):
            if tag == "meta":
                d = dict(attrs)
                if d.get("name") == "csrf-token":
                    self.token = d.get("content")
    p = P(); p.feed(resp.text)
    return p.token or ""


def buscar_rota(veiculo_id: int, data_ini: str, data_fim: str) -> dict:
    """
    Consulta o histórico de posições de um veículo no TrackerPrime.
    data_ini / data_fim: formato 'YYYY-MM-DD HH:MM:SS'
    Retorna o JSON completo (recordsTotal, data[]).
    """
    csrf = _get_csrf_da_sessao()
    payload = {
        "_token":  csrf,
        "veiculo": str(veiculo_id),
        "dataIni": f"{data_ini} - {data_fim}",
        "length":  "9999",          # pegar todos os registros do período
        "start":   "0",
        "draw":    "1",
    }
    resp = session.post(
        POSICOES_URL,
        data=payload,
        timeout=REQUEST_TIMEOUT,
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    if _checar_sessao(resp):
        raise RuntimeError("Não foi possível renovar a sessão para buscar rota.")

    resp.raise_for_status()
    return resp.json()


def atualizar_cache():
    """Busca os veículos e atualiza o cache em memória."""
    global cache
    try:
        log.info("Atualizando cache de veículos...")
        inicio = time.time()
        veiculos = buscar_veiculos()
        duracao = round(time.time() - inicio, 2)

        cache["veiculos"]            = veiculos
        cache["ultima_atualizacao"]  = datetime.now(timezone.utc).isoformat()
        cache["status"]              = "ok"
        cache["total_atualizacoes"] += 1
        cache["duracao_ultima_req"]  = f"{duracao}s"
        cache["erros"]               = 0

        log.info(f"Cache atualizado: {len(veiculos)} veículos em {duracao}s.")
    except Exception as e:
        cache["status"] = f"erro: {e}"
        cache["erros"]  = cache.get("erros", 0) + 1
        log.error(f"Falha ao atualizar cache: {e}")


# ─── Lifespan (startup + shutdown) ────────────────────────────────────────────

scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──
    if not fazer_login():
        log.warning("Login inicial falhou — tentará novamente no próximo ciclo.")
    else:
        atualizar_cache()

    scheduler.add_job(
        atualizar_cache,
        "interval",
        minutes=REFRESH_INTERVAL_MINUTES,
        id="refresh_veiculos",
    )
    scheduler.start()
    log.info(f"Scheduler iniciado: refresh a cada {REFRESH_INTERVAL_MINUTES} min.")

    yield  # ← aplicação rodando

    # ── SHUTDOWN ──
    log.info("Encerrando scheduler...")
    scheduler.shutdown(wait=False)
    log.info("Scheduler encerrado.")


# ─── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="TrackerPrime API",
    description="Wrapper local com cache — dados de veículos Fertran",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", summary="Status da API")
def status():
    return {
        "api":               "TrackerPrime API",
        "status":            cache["status"],
        "ultima_atualizacao": cache["ultima_atualizacao"],
        "total_veiculos":    len(cache["veiculos"]),
        "total_atualizacoes": cache["total_atualizacoes"],
        "duracao_ultima_req": cache.get("duracao_ultima_req"),
        "erros_consecutivos": cache["erros"],
        "refresh_automatico": f"a cada {REFRESH_INTERVAL_MINUTES} minutos",
    }


@app.get("/veiculos", summary="Lista todos os veículos")
def listar_veiculos(
    ignicao: Optional[int] = Query(None, description="Filtrar por ignição: 1=ligado, 0=desligado"),
    tipo_id: Optional[int] = Query(None, description="Filtrar por tipo de veículo"),
):
    veiculos = cache["veiculos"]
    if not veiculos:
        raise HTTPException(503, "Cache ainda não carregado. Tente em instantes.")
    if ignicao is not None:
        veiculos = [v for v in veiculos if v.get("ignicao") == ignicao]
    if tipo_id is not None:
        veiculos = [v for v in veiculos if v.get("tipo_id") == tipo_id]
    return {
        "total": len(veiculos),
        "ultima_atualizacao": cache["ultima_atualizacao"],
        "veiculos": veiculos,
    }


@app.get("/veiculos/{veiculo_id}", summary="Busca veículo por ID")
def get_veiculo(veiculo_id: int):
    encontrado = next((v for v in cache["veiculos"] if v.get("id") == veiculo_id), None)
    if not encontrado:
        raise HTTPException(404, f"Veículo com id={veiculo_id} não encontrado.")
    return encontrado


@app.get("/buscar", summary="Busca veículos por placa (parcial)")
def buscar_por_placa(placa: str = Query(..., description="Texto a buscar na placa")):
    termo = placa.upper().strip()
    resultado = [
        v for v in cache["veiculos"]
        if termo in (v.get("placa") or "").upper()
    ]
    return {
        "total": len(resultado),
        "ultima_atualizacao": cache["ultima_atualizacao"],
        "veiculos": resultado,
    }


@app.get("/stats", summary="Estatísticas gerais da frota")
def stats():
    veiculos = cache["veiculos"]
    if not veiculos:
        raise HTTPException(503, "Cache ainda não carregado.")

    ligados   = sum(1 for v in veiculos if v.get("ignicao") == 1)
    desligados = len(veiculos) - ligados

    tipos: dict[int, int] = {}
    icones: dict[str, int] = {}
    for v in veiculos:
        t = v.get("tipo_id")
        if t:
            tipos[t] = tipos.get(t, 0) + 1
        ic = v.get("icone", "")
        icones[ic] = icones.get(ic, 0) + 1

    return {
        "ultima_atualizacao": cache["ultima_atualizacao"],
        "total_veiculos":     len(veiculos),
        "ignicao_ligada":     ligados,
        "ignicao_desligada":  desligados,
        "por_tipo_id":        dict(sorted(tipos.items())),
        "por_icone":          dict(sorted(icones.items(), key=lambda x: -x[1])),
    }


@app.get("/rota/{veiculo_id}", summary="Histórico de posições de um veículo")
def get_rota(
    veiculo_id: int,
    inicio: str = Query(..., description="Data/hora inicial: YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS"),
    fim:    str = Query(..., description="Data/hora final:   YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS"),
    sem_cache: bool = Query(False, description="Ignorar cache e forçar nova busca"),
):
    """
    Retorna o histórico de posições GPS de um veículo em um período.

    **Anti-sobrecarga:**
    - Dias passados: cache de 30 minutos (dados não mudam).
    - Dia atual: cache de 2 minutos (dados mudam com frequência).
    - Mesma consulta feita várias vezes não reacessa o TrackerPrime.
    """
    # Normalizar datas
    if len(inicio) == 10:
        inicio = f"{inicio} 00:00:00"
    if len(fim) == 10:
        fim = f"{fim} 23:59:59"

    hoje = date.today().isoformat()
    eh_hoje = fim[:10] >= hoje

    chave = f"{veiculo_id}|{inicio}|{fim}"
    ttl   = ROTA_TTL_HOJE_SEG if eh_hoje else ROTA_TTL_PASSADO_SEG
    agora = time.time()

    # Verificar cache
    if not sem_cache and chave in rota_cache:
        entrada = rota_cache[chave]
        idade   = agora - entrada["ts"]
        if idade < ttl:
            log.info(f"Rota {veiculo_id} servida do cache (idade {idade:.0f}s / TTL {ttl}s).")
            return {
                **entrada,
                "cache": True,
                "cache_idade_seg": round(idade),
                "cache_ttl_seg":   ttl,
            }

    # Buscar no TrackerPrime
    log.info(f"Buscando rota do veículo {veiculo_id} de {inicio} a {fim}...")
    t0 = time.time()
    try:
        resultado = buscar_rota(veiculo_id, inicio, fim)
    except Exception as e:
        raise HTTPException(502, f"Erro ao buscar rota no TrackerPrime: {e}")

    duracao = round(time.time() - t0, 2)
    posicoes = resultado.get("data", [])

    entrada = {
        "veiculo_id":    veiculo_id,
        "periodo_inicio": inicio,
        "periodo_fim":    fim,
        "total":          resultado.get("recordsTotal", len(posicoes)),
        "posicoes":       posicoes,
        "duracao_req":    f"{duracao}s",
        "ts":             agora,
        "cache":          False,
    }
    rota_cache[chave] = entrada
    log.info(f"Rota {veiculo_id}: {len(posicoes)} posições em {duracao}s.")

    return {k: v for k, v in entrada.items() if k != "ts"}


@app.get("/rota/{veiculo_id}/hoje", summary="Posições de hoje do veículo")
def get_rota_hoje(veiculo_id: int):
    """Atalho que busca as posições do veículo entre 00:00 e agora (hoje)."""
    hoje = date.today().isoformat()
    agora_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return get_rota(veiculo_id, inicio=hoje + " 00:00:00", fim=agora_str)