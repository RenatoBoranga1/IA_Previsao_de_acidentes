# Radar de Prevencao Operacional

Painel preditivo para prevencao de acidentes em operacoes logisticas, com API Flask modular, autenticacao por perfil, frontend executivo e esteira CI para lint, smoke test e deploy.

## Preview

### Dashboard desktop

![Dashboard desktop](docs/screenshots/dashboard-overview.png)

### Dashboard mobile

![Dashboard mobile](docs/screenshots/dashboard-mobile.png)

## O que mudou nesta evolucao

- separacao de camadas em modulos dedicados de configuracao, autenticacao, modelos, repositorios, servicos e rotas
- autenticacao por token com perfis `admin`, `gestor` e `analista`
- endpoint administrativo protegido para diretorio de usuarios
- frontend com login, sessao persistida, modo demo e painel administrativo por role
- screenshots reais do dashboard publicadas no repositorio
- pipeline GitHub Actions para lint, smoke test e deploy por hook

## Arquitetura

```text
.
|-- app_previsao.py
|-- radar_preventivo/
|   |-- config.py
|   |-- auth/
|   |-- models/
|   |-- repositories/
|   |-- routes/
|   `-- services/
|-- index.html
|-- style.css
|-- script.js
|-- auth_users.example.json
|-- requirements.txt
|-- requirements-dev.txt
|-- requirements-ci.txt
|-- docs/screenshots/
|-- scripts/capture_dashboard.ps1
|-- Dockerfile
|-- railway.json
|-- cloudbuild.yaml
`-- tests/
```

## Perfis de acesso

- `admin`: consulta o dashboard e acessa o diretorio de usuarios e permissoes
- `gestor`: acessa previsoes, hotspots e leitura executiva
- `analista`: acessa previsoes, rankings e detalhamento tecnico

Os endpoints protegidos exigem token Bearer:

- `GET /auth/me`
- `GET /auth/users` (`admin` apenas)
- `GET /predict?date=YYYY-MM-DD`

## Autenticacao

### Usuarios

O backend procura usuarios em `auth_users.json`. O arquivo de exemplo versionado e `auth_users.example.json`.

Fluxo recomendado:

1. copiar `auth_users.example.json` para `auth_users.json`
2. trocar os hashes e usuarios pelos dados reais do ambiente
3. manter `auth_users.json` fora do Git

### Login

`POST /auth/login`

Exemplo:

```json
{
  "email": "admin@radar.local",
  "password": "Admin123!"
}
```

Resposta:

```json
{
  "access_token": "token-assinado",
  "token_type": "Bearer",
  "expires_in": 28800,
  "user": {
    "name": "Admin Demo",
    "role": "admin",
    "role_title": "Administrador",
    "permissions": ["dashboard:view", "users:read", "auth:manage"]
  }
}
```

## Como rodar localmente

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python app_previsao.py
```

No PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python .\app_previsao.py
```

### Frontend

Abra `index.html` no navegador.

Com backend local:

- o frontend usa `http://127.0.0.1:5000` em `localhost`
- em `file://`, ele usa o fallback configurado em `FALLBACK_BACKEND_URL`
- voce pode sobrescrever a API com `?api=https://sua-api`

Modo demo para apresentacao e screenshots:

```text
index.html?demo=1
index.html?demo=1&demoRole=admin
```

## Deploy no Railway

O repositorio agora inclui:

- `Dockerfile`
- `.dockerignore`
- `railway.json`
- `render.yaml`
- `.python-version`

Isso faz o Railway usar build por Dockerfile em vez de depender da deteccao automatica do Railpack.

### Variaveis recomendadas no Railway

- `APP_SECRET_KEY`: chave de assinatura dos tokens
- `APP_ALLOW_DEMO_USERS=true`: util para validar a API rapidamente
- `APP_PREDICTOR_MODE=neuralprophet`: modo real

Se voce ainda nao tiver um `auth_users.json` real no deploy, use `APP_ALLOW_DEMO_USERS=true` temporariamente para testar login com:

- `admin@radar.local` / `Admin123!`
- `gestor@radar.local` / `Gestor123!`
- `analista@radar.local` / `Analista123!`

Depois, substitua por usuarios reais via `APP_AUTH_USERS_FILE` ou imagem customizada com o arquivo apropriado.

### Deploy no Render

Se voce for usar o Render, prefira apontar o servico para a branch mais recente do projeto ou fazer merge dela em `main`.

Arquivos incluidos para esse fluxo:

- `render.yaml`
- `.python-version`

Configuracao recomendada:

- `Build Command`: `pip install -r requirements.txt`
- `Start Command`: `gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 300 app_previsao:app`
- `Health Check Path`: `/health`

Primeiro deploy recomendado no Render:

- `APP_PREDICTOR_MODE=mock`
- `APP_ALLOW_DEMO_USERS=true`

Isso faz a API abrir a porta rapidamente e evita timeout de deploy por treinamento pesado do modelo. Depois que o servico estiver estavel, voce pode trocar `APP_PREDICTOR_MODE` para `neuralprophet`.

## Deploy no Google Cloud Run

O `Dockerfile` atual ja pode ser usado no Cloud Run. Para este projeto, esse fluxo tende a ser mais robusto do que o Railway quando a imagem cresce por causa das dependencias de ML.

Arquivos incluidos para esse fluxo:

- `Dockerfile`
- `.gcloudignore`
- `cloudbuild.yaml`

### Opcao 1: deploy direto com `gcloud`

1. Autentique e selecione o projeto:

```bash
gcloud auth login
gcloud config set project SEU_PROJECT_ID
```

2. Habilite as APIs necessarias:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

3. Crie um repositorio Docker no Artifact Registry:

```bash
gcloud artifacts repositories create ia-previsao-images \
  --repository-format=docker \
  --location=southamerica-east1 \
  --description="Imagens da API IA_Previsao_de_acidentes"
```

4. Construa a imagem com o `Dockerfile` da raiz:

```bash
gcloud builds submit \
  --tag southamerica-east1-docker.pkg.dev/SEU_PROJECT_ID/ia-previsao-images/ia-previsao-api
```

5. Publique no Cloud Run:

```bash
gcloud run deploy ia-previsao-api \
  --image southamerica-east1-docker.pkg.dev/SEU_PROJECT_ID/ia-previsao-images/ia-previsao-api \
  --region southamerica-east1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 4Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars APP_ALLOW_DEMO_USERS=true,APP_PREDICTOR_MODE=neuralprophet,APP_CORS_ORIGINS=*
```

6. Depois do deploy, defina uma chave fixa para os tokens:

```bash
gcloud run services update ia-previsao-api \
  --region southamerica-east1 \
  --update-env-vars APP_SECRET_KEY=SUA_CHAVE_FORTE
```

### Opcao 2: build e deploy automaticos com Cloud Build

O arquivo `cloudbuild.yaml` ja esta preparado para:

- construir a imagem com Docker
- enviar para o Artifact Registry
- implantar no Cloud Run

Execucao manual:

```bash
gcloud builds submit --config cloudbuild.yaml
```

Se quiser um primeiro deploy mais leve, voce pode sobrescrever o modo do preditor:

```bash
gcloud builds submit --config cloudbuild.yaml --substitutions=_PREDICTOR_MODE=mock
```

### Usuarios reais no Cloud Run

Para validar rapidamente, use `APP_ALLOW_DEMO_USERS=true`.

Para producao, o ideal e:

- guardar `APP_SECRET_KEY` em Secret Manager
- montar o arquivo de usuarios como secret ou ajustar a aplicacao para ler usuarios de variavel ou secret
- trocar `APP_ALLOW_DEMO_USERS` para `false`

### Observacoes praticas

- o CSV principal presente hoje no repositorio e pequeno, entao o peso da imagem tende a vir mais das dependencias de ML do que dos dados
- para reduzir cold start, vale considerar `min instances > 0` no Cloud Run
- se o primeiro objetivo for validar a infraestrutura, use `APP_PREDICTOR_MODE=mock` e depois volte para `neuralprophet`

## Geracao de screenshots

Script incluido:

```powershell
.\scripts\capture_dashboard.ps1
```

O script usa Chrome headless para gerar:

- `docs/screenshots/dashboard-overview.png`
- `docs/screenshots/dashboard-mobile.png`

## Testes e pipeline

### Lint local

```bash
ruff check .
```

### Smoke test local

```bash
pytest
```

Os testes usam `predictor_mode=mock`, evitando depender de treinamento real do NeuralProphet no CI.

### GitHub Actions

Workflow em `.github/workflows/ci.yml`:

- instala dependencias leves de CI
- roda `ruff check .`
- roda `pytest`
- dispara deploy via hooks do Render em `main`

Secrets esperados para deploy:

- `RENDER_BACKEND_DEPLOY_HOOK_URL`
- `RENDER_FRONTEND_DEPLOY_HOOK_URL`

## Configuracoes uteis

- `APP_DATA_FILE`: caminho do CSV principal
- `APP_DISMISSED_DRIVERS_FILE`: caminho do CSV de motoristas desligados
- `APP_AUTH_USERS_FILE`: caminho do arquivo real de usuarios
- `APP_ALLOW_DEMO_USERS`: habilita usuarios demo no backend
- `APP_PREDICTOR_MODE`: `neuralprophet` ou `mock`
- `APP_SECRET_KEY`: chave de assinatura dos tokens
- `APP_TOKEN_TTL_SECONDS`: validade do token
- `FORECAST_DAYS`: horizonte da previsao
- `RECENT_HISTORY_DAYS`: janela da serie recente

## Observacoes de deploy

- o fluxo de deploy do workflow usa hooks para desacoplar CI de provedor
- o frontend continua estatico e pode ser hospedado em Render, Netlify, Vercel ou GitHub Pages
- o backend suporta mock mode para smoke tests e NeuralProphet para ambiente real

## Credito

Projeto de Renato Boranga, evoluido para uma base mais profissional com foco em produto, governanca de acesso, apresentacao visual e operacao continua.
