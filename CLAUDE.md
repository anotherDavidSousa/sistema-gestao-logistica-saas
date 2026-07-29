# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é

Sistema de gestão de frota da **Fertran — Filial 16** (agregamentoipatinga.com). Projeto Django cuja UI é o **admin Jazzmin** (não há front-end separado): o cadastro de frota, o dashboard, o mapa e o histórico de posições são todos telas do `/admin/`. A raiz `/` redireciona para `/admin/`.

Todo o código, comentários, verbose_names e mensagens estão em **português**. Mantenha esse padrão ao editar.

**Stack:** Django + PostgreSQL + admin Jazzmin; microserviço FastAPI (`inoprime_api`, porta 8001) para GPS; n8n para ingestão de documentos; MinIO (S3) para arquivos. Deploy via Docker Compose (Proxmox) atrás de Nginx + Cloudflare. **Não há Selenium, pdftk nem Ghostscript neste repositório** — a coleta de GPS é scraping HTTP puro e o split/compressão de PDF é feito no n8n (ver Fluxos de integração).

## Comandos

Rodar sempre dentro do container `web` (as credenciais de Postgres/MinIO vêm do `.env` via ambiente do Compose):

```bash
docker compose up -d                                     # sobe web + nginx + cron + minio
docker compose exec web python manage.py migrate
docker compose exec web python manage.py test            # suite de testes
docker compose exec web python manage.py test fila       # testes de um app
docker compose exec web python manage.py test core.tests.NomeTest.test_metodo   # teste único
docker compose exec web python manage.py createsuperuser
docker compose logs -f web                               # tracebacks 500 (LOGGING → console)
```

Comandos de gestão próprios:

```bash
docker compose exec web python manage.py salvar_posicoes [--dry-run] [--url ...]   # snapshot de posições (roda pelo cron a cada 5 min)
docker compose exec web python manage.py sync_googlesheets                          # sincroniza cavalos → Google Sheets
docker compose exec web python manage.py remover_pdfs_antigos_minio                 # limpeza de PDFs no MinIO
```

O serviço `docker compose exec web ...` assume o container de pé. Localmente sem Docker: `python manage.py ...` funciona desde que exista um `.env` na raiz com as variáveis de Postgres/MinIO (carregado em `filial16/settings.py`).

## Arquitetura

Dois apps Django + um microserviço FastAPI separado.

**Regra prática:** a lógica de negócio de frota vive em `core/signals.py` (`pre_save`/`post_save` de Cavalo e Motorista), **não nas views nem no admin**. Antes de alterar Cavalo/Motorista/Carreta, leia os signals.

### `core` — frota (domínio principal)
Modelos em `core/models.py`. Grafo de relacionamentos:

- **Proprietario** ─(1:N)→ **Cavalo** ─(1:1)→ **Carreta** (`Cavalo.carreta`, OneToOne). Um cavalo tem no máximo uma carreta acoplada.
- **Cavalo** ─(1:1)← **Motorista** (`Motorista.cavalo`, OneToOne) e ─(N:1)→ **Gestor**.
- **CidadeEntrega** — zona de entrega como polígono `[[lat,lng],...]` em JSONField, usada pelo mapa e pelo cálculo de visitas.
- **PosicaoVeiculo** — snapshot de GPS (placa, lat, lng, ignição). Gravado a cada 5 min pelo cron; base do histórico de frota.
- **LogCarreta** e **HistoricoGestor** — trilha de auditoria escrita **automaticamente por signals**, não manualmente.

**Regra de negócio central — `core/signals.py`:** toda troca de acoplamento (cavalo↔carreta), motorista, gestor ou proprietário é detectada em `pre_save`/`post_save` do Cavalo e do Motorista comparando o estado antigo (`.get(pk=...)`) com o novo, e materializada em `LogCarreta`/`HistoricoGestor`. Ao mexer nesses modelos, **entenda os signals antes** — muita lógica de estado (fechar histórico de gestor, `atualizar_status_automatico` do proprietário, sync com Google Sheets) vive lá, não nas views. `classificacao` ('agregado'/'frota'/'terceiro') é um discriminador usado em quase todos os filtros e relatórios.

### `fila` — documentos de transporte (OST e CT-e)
Modelos em `fila/models.py`: **OST** (Ordem de Serviço de Transporte) e **CTe** (Conhecimento de Transporte Eletrônico). São registros achatados (quase tudo `CharField`) representando **uma página** de um PDF grande. Cada um guarda `pdf_storage_key` — a chave do PDF daquela página no MinIO. **Estes modelos são preenchidos externamente pelo n8n**, não pela UI (ver Integrações).

`fila/menu_perms.py` implementa autorização por grupo (`require_menu_perm` decorator): staff/superuser veem tudo; grupo **Operadores** vê só Fila e Cavalos.

### `filial16` — projeto/config
`filial16/settings.py` concentra tudo: apps, MinIO (django-storages/S3), JWT, Jazzmin e endurecimento de segurança sob `if not DEBUG`. `filial16/urls.py` monta as rotas de dashboard/mapa/n8n **antes** de `admin/` (a ordem importa — elas interceptam sub-paths de `/admin/`).

## Fluxos de integração (onde entram os serviços externos)

**Nenhum destes está no request/response do Django — todos são assíncronos/externos.**

1. **Rastreamento GPS — microserviço `inoprime_api/` (FastAPI, container separado, porta 8001).**
   `inoprime_api/main.py` é um **wrapper com cache** sobre o site TrackerPrime (`trackerprime.inoprime.com.br`). A coleta é **scraping HTTP puro**: login via sessão `requests` + token CSRF, **sem navegador headless / sem Selenium**. Mantém em memória as posições da frota, atualizadas a cada 5 min por um APScheduler. Expõe `/veiculos`, `/rota/{id}`, etc.
   - Django consome via `INOPRIME_API_URL` de dois jeitos: o management command `salvar_posicoes` (cron, grava `PosicaoVeiculo` só dos cavalos `classificacao='agregado'`) e a view-proxy `core/views_dashboard.py::mapa_veiculos_api` (mapa ao vivo).

2. **n8n → OST/CT-e.** O **split, a extração e a compressão** dos PDFs de 1400+ páginas, e o upload ao MinIO, acontecem **inteiramente no n8n — fora deste repositório**. O Django só recebe o resultado: `POST /api/n8n/ost/` e `/api/n8n/cte/` (`fila/n8n_api.py`) com o JSON já extraído + `pdf_storage_key`. Esses endpoints fazem upsert idempotente (chave: filial+série+documento[+NF]; opção `apenas_criar`). Autenticação: JWT ou sessão (ver `REST_FRAMEWORK` no settings).
   - **Código legado já removido:** os extratores pdfplumber (`fila/ost_extractor.py`, `fila/processador_cte.py`) e o `fila/signals.py` inerte foram apagados — a extração real acontece no n8n. Resta `fila/api_key_auth.py`, que referencia um modelo `ApiKey` já removido (migration `0012`); confirme antes de reutilizar.

3. **Google Sheets.** `core/google_sheets.py` espelha os Cavalos numa planilha. Disparado pelos signals de forma "async" (best-effort, dentro de `try/except` que só loga). Controlado por `GOOGLE_SHEETS_ENABLED`.

4. **Armazenamento — MinIO (S3).** `STORAGES['default']` é S3Boto3 → **todo `FileField`/`ImageField` (fotos, documentos, PDFs) vai para o bucket MinIO**, nunca para o disco local. URLs são assinadas e expiram em 1h (`AWS_QUERYSTRING_EXPIRE`). Downloads de PDF passam por `default_storage.open(...)` nas views `ost_download_pdf`/`cte_download_pdf`.

## Convenções e cuidados

- **Migrations:** revisar sempre antes de aplicar. Migrations de dados/correção existem no histórico (ex.: `core/0005_fix_motorista_id_sequence`) — não é um app "só schema".
- **Nunca commitar** `.env` nem credenciais de MinIO/Postgres (já no `.gitignore`, junto com `nginx/ssl/`, `minio/` e vários scripts locais).
- Ao filtrar/relatar frota, quase sempre o recorte é `Cavalo.objects.filter(classificacao='agregado')` — confira se a nova query respeita esse discriminador.
- Placas do TrackerPrime vêm como `"PLACA DESCRIÇÃO"` ou repetidas (`"MSL2J23 MSL2J23MG"`); normalize com `.split()[0]` como já é feito em `salvar_posicoes` e `mapa_veiculos_api`.
- Deploy: Docker Compose em Proxmox, atrás de Nginx + Cloudflare (que termina o TLS — daí `SECURE_PROXY_SSL_HEADER`). Gunicorn com `--preload` e timeout de 300s por causa dos uploads grandes.
