#IA Previsão de Eventos 

Este sistema realiza previsão de eventos (operações/logística) utilizando um modelo de séries temporais com NeuralProphet. Ele conta com uma API RESTful (Flask), frontend web responsivo e deploy em nuvem via Render.
________________________________________
🎯 ##Objetivo
Antecipar o número de eventos em cada dia futuro e apresentar rankings dos motoristas mais propensos a aparecerem em incidentes, além de análises específicas por tipo de evento, tornando a gestão logística mais eficiente e preventiva.
________________________________________
🚀 ##Arquitetura
•	Backend: Python (Flask, NeuralProphet, pandas, torch)
•	Frontend: HTML5, CSS3, JavaScript
•	Hospedagem: Render (Backend e Site Estático)
•	Banco de dados: Arquivo CSV de histórico (basedadosseguranca.csv)
________________________________________
🗂️ ##Funcionalidades
•	Previsão diária de eventos operacionais
•	Top 10 motoristas mais propensos a eventos
•	Ranking dos cinco motoristas mais envolvidos por tipo de evento
•	Respostas em tempo real via API RESTful
•	Interface web dinâmica e amigável
•	Mensagens de erro detalhadas e consistentes
•	Deploy automático e separado para frontend/backend
________________________________________
⚙️ ##Como Usar
1. Backend
Requisitos:
•	Python 3.11+
•	Virtualenv recomendado
Instalação:
bashCopiar
git clone https://github.com/seu-usuario/seu-repo.git
cd seu-repo
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
Copie seu arquivo basedadosseguranca.csv para a pasta do projeto.
Rodando localmente:
bashCopiar
python app_previsao.py
# ou para produção
gunicorn app_previsao:app
2. Frontend
•	Edite o arquivo script.js se necessário para apontar para a URL correta do backend (exemplo: https://ia-previsao-ritmo-backend.onrender.com/predict).
•	Hospede arquivos do frontend como site estático no Render, Netlify, Vercel ou GitHub Pages.
•	Ou simplesmente abra index.html no navegador para testes locais.
3. Testando
1.	Acesse o frontend pela URL ou arquivo local.
2.	Escolha uma data e clique em "Buscar Previsão".
3.	Resultados e rankings serão exibidos na tela.
________________________________________
🔗 ##Endpoints e API
GET /predict?date=YYYY-MM-DD
Parâmetro:
•	date: data para previsão (YYYY-MM-DD, opcional. Default = amanhã)
Resposta:
jsonCopiar
{
  "data_previsao": "2025-06-15",
  "previsao_total_yhat1": 19.12,
  "top10_motoristas_geral": [
    {"Motorista": "João", "Probabilidade": 3.02},
    ...
  ],
  "probabilidade_eventos_especificos": {
    "Excesso de Velocidade": [
      {"Motorista": "Carlos", "Probabilidade": 0.25},
      ...
    ],
    ...
  }
}
•	404: Data fora do intervalo previsto
•	500: Erro interno ao preparar/prever
________________________________________
✨ ##Personalização
•	Mude estilos no style.css conforme a paleta institucional.
•	Edite textos/front em index.html e script.js.
•	Atualize o arquivo CSV para novos dados.
•	Para deploy contínuo, faça push para a branch configurada no Render/Netlify.
________________________________________
✅ ##Melhores Práticas
•	Padronização em snake_case para nomes de variáveis e chaves JSON.
•	CORS habilitado no backend.
•	Tratamento robusto de exceções e mensagens ao usuário final.
________________________________________
📚 ##Roadmap (Sugestões Futuras)
•	Adicionar autenticação (JWT ou OAuth2)
•	Dashboard visual com gráficos interativos (Plotly, Chart.js)
•	Cadastro e upload de novos arquivos CSV via web
•	Notificações por e-mail ou WhatsApp quando previsões forem críticas
________________________________________
🙋 ##FAQ
Preciso reiniciar o backend ao trocar o CSV?
Sim. O modelo é treinado ao inicializar a aplicação.
Posso publicar/modificar para outro contexto?
Sim! Basta adaptar a estrutura dos dados e reconfigurar ingestão/modelo.
O frontend funciona em qualquer hosting estático?
Sim! Basta apontar a URL da API no script.js corretamente.
________________________________________
👨‍💻 ##Créditos
Desenvolvido por Renato Boranga
IA de Previsão de Acidentes para Ritmo Logística