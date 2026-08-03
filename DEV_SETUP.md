# Desenvolvimento local (SQLite, sem Postgres/Docker)

Para rodar o projeto numa máquina de desenvolvimento **sem instalar PostgreSQL e
sem Docker**, use SQLite (já embutido no Python). O banco fica num arquivo local
`db.sqlite3` (ignorado pelo git) e não tem nenhuma relação com o banco de produção.

O modo SQLite é **opt-in**: só é ativado quando a variável de ambiente
`USE_SQLITE=1` está definida. Sem ela, o projeto usa PostgreSQL normalmente
(comportamento de produção).

## Passos

1. Criar e ativar um ambiente virtual:

   ```bash
   python -m venv .venv
   # Windows (PowerShell):
   .venv\Scripts\Activate.ps1
   # Windows (cmd):
   .venv\Scripts\activate.bat
   # Linux/macOS:
   source .venv/bin/activate
   ```

2. Instalar as dependências:

   ```bash
   pip install -r requirements.txt
   ```

3. Definir a variável de ambiente `USE_SQLITE=1`:

   - Windows (PowerShell): `$env:USE_SQLITE="1"`
   - Windows (cmd): `set USE_SQLITE=1`
   - Linux/macOS: `export USE_SQLITE=1`

   Alternativamente, coloque `USE_SQLITE=1` no `.env` local (que **não** deve ir
   para produção).

4. Criar as tabelas:

   ```bash
   python manage.py migrate
   ```

5. Criar um superusuário:

   ```bash
   python manage.py createsuperuser
   ```

6. Subir o servidor de desenvolvimento:

   ```bash
   python manage.py runserver
   ```

   A UI é o admin Jazzmin em `http://127.0.0.1:8000/admin/` (a raiz `/` redireciona
   para lá).

## Observações

- **Produção não define `USE_SQLITE`**, então continua usando PostgreSQL
  (`POSTGRES_*`) exatamente como antes. Nada muda no comportamento de produção.
- O SQLite cobre o cadastro de frota, dashboard e telas do admin. Serviços
  externos (GPS `inoprime_api`, MinIO/S3, n8n, Google Sheets) continuam
  dependendo das respectivas variáveis de ambiente / containers — o SQLite só
  substitui o banco relacional.
- O arquivo `db.sqlite3` (e variações como `db.sqlite3-journal`) está no
  `.gitignore`; nunca o comite.
