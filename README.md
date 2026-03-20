# Radar de Prevenção Operacional

Painel preditivo para prevenção de acidentes em operações logísticas, com API em Flask, modelo de séries temporais com NeuralProphet e frontend executivo em HTML/CSS/JavaScript puro.

## Visão geral

O projeto transforma o histórico de eventos de segurança em uma leitura prática para tomada de decisão:

- previsão consolidada de eventos para uma data futura
- ranking dos motoristas mais expostos
- hotspots de localidade
- recorte por tipo de evento
- insights prioritários para ação operacional
- série recente para leitura rápida de tendência

## Stack

- Backend: Python, Flask, Flask-CORS, NeuralProphet, pandas
- Frontend: HTML5, CSS3, JavaScript vanilla
- Dados: CSV operacional
- Deploy sugerido: Render para API e hospedagem estática para o frontend

## Destaques da versão atual

- dashboard redesenhado com identidade visual mais forte e responsiva
- API com payload mais rico para o frontend
- endpoint `/health` para monitoramento básico do backend
- resumo executivo com nível de risco, variação contra média histórica e foco prioritário
- detalhamento por motoristas, localidades e tipos de evento
- fallback inteligente de conexão entre frontend local e backend hospedado

## Estrutura

```text
.
|-- app_previsao.py
|-- index.html
|-- style.css
|-- script.js
|-- basedadosseguranca.csv
|-- motoristas_desligados.csv
|-- requirements.txt
```

## Como rodar localmente

### 1. Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app_previsao.py
```

No Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python .\app_previsao.py
```

A API sobe por padrão em `http://127.0.0.1:5000`.

### 2. Frontend

Você pode abrir [index.html](./index.html) diretamente no navegador para uma validação rápida.

Quando o frontend roda localmente:

- em `file://`, o script tenta usar o backend hospedado configurado em `FALLBACK_BACKEND_URL`
- em `localhost`, o script tenta usar `http://127.0.0.1:5000`
- opcionalmente, você pode sobrescrever a API com `?api=https://sua-api`

Exemplo:

```text
index.html?api=https://sua-api.onrender.com
```

## Endpoints

### `GET /health`

Retorna status do backend, quantidade de registros carregados e a janela histórica disponível.

### `GET /predict?date=YYYY-MM-DD`

Retorna a previsão para a data informada e os blocos analíticos usados pelo dashboard.

Exemplo resumido de resposta:

```json
{
  "data_previsao": "2025-10-12",
  "previsao_total_yhat1": 18.42,
  "forecast_period_start": "2025-10-12",
  "forecast_period_end": "2025-11-25",
  "top_10_motoristas_geral": [],
  "top_3_localidades": [],
  "top_tipos_evento": [],
  "probabilidade_eventos_especificos": {},
  "serie_historica_recente": [],
  "resumo_executivo": {},
  "dataset_contexto": {}
}
```

## Dados esperados

O CSV principal deve conter, no mínimo, estas colunas:

- `Data`
- `QUANTIDADE`
- `Motorista`
- `Localidade`
- `Tipo de Evento`

O arquivo `motoristas_desligados.csv` e opcional e serve para remover nomes que nao devem mais aparecer no ranking.

## Variáveis úteis

- `PORT`: porta da API
- `FORECAST_DAYS`: quantidade de dias futuros gerados pelo modelo
- `RECENT_HISTORY_DAYS`: quantidade de dias exibidos no histórico recente
- `LOG_LEVEL`: nível de log do backend

## Próximos passos recomendados

- adicionar testes automatizados para a API
- separar camadas de dados, modelo e rotas em módulos dedicados
- incluir autenticação e perfis de acesso
- publicar screenshots do dashboard no repositório
- adicionar pipeline CI para lint, smoke test e deploy

## Crédito

Projeto de Renato Boranga, evoluído para uma apresentação mais profissional com foco em prevenção operacional e experiência executiva no frontend.
