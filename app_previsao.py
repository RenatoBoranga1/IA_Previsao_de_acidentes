import os
import pandas as pd
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
from neuralprophet import NeuralProphet

app = Flask(__name__)
CORS(app)

dados = None
modelo = None
df_aggregated = None
total_eventos = None

def load_and_train_model():
    global dados, modelo, df_aggregated, total_eventos

    print("Iniciando carregamento e treinamento do modelo...")

    try:
        dados = pd.read_csv('basedadosseguranca.csv', delimiter=';')
    except FileNotFoundError:
        print("ERRO CRÍTICO: 'basedadosseguranca.csv' não encontrado.")
        sys.exit(1)

    if 'Motorista' in dados.columns:
        dados['Motorista'] = dados['Motorista'].fillna(dados['Motorista'].mode()[0])

    for column in dados.columns:
        if dados[column].dtype == 'object' and column != 'Motorista':
            dados[column] = dados[column].fillna(dados[column].mode()[0])
        elif dados[column].dtype in ['int64', 'float64']:
            dados[column] = dados[column].fillna(dados[column].mean())

    if 'Data' in dados.columns:
        dados['Data'] = pd.to_datetime(dados['Data'], dayfirst=True)
    else:
        print("ERRO CRÍTICO: Coluna 'Data' não encontrada no arquivo CSV.")
        sys.exit(1)

    if 'QUANTIDADE' in dados.columns:
        df_aggregated = dados.groupby('Data', as_index=False)['QUANTIDADE'].sum()
    else:
        print("ERRO CRÍTICO: Coluna 'QUANTIDADE' não encontrada.")
        sys.exit(1)

    if df_aggregated is not None and not df_aggregated.empty:
        df = df_aggregated.rename(columns={'Data': 'ds', 'QUANTIDADE': 'y'})
    else:
        print("ERRO CRÍTICO: Dados agregados estão vazios.")
        sys.exit(1)

    modelo = NeuralProphet()
    print("Treinando o modelo NeuralProphet...")
    modelo.fit(df, freq='D')
    print("Modelo NeuralProphet treinado.")

    total_eventos = dados['QUANTIDADE'].sum() if 'QUANTIDADE' in dados.columns else 0

# Carrega ao iniciar
print("Carregando e treinando o modelo...")
load_and_train_model()
print("Modelo carregado e treinado com sucesso!")

@app.route('/predict', methods=['GET'])
def get_prediction():
    date_str = request.args.get('date', pd.to_datetime('today').normalize() + pd.Timedelta(days=1))
    if isinstance(date_str, str):
        data_especifica = pd.to_datetime(date_str)
    else:
        data_especifica = date_str

    if modelo is None or df_aggregated is None:
        return jsonify({
            "error": "O modelo ou os dados não foram carregados corretamente.",
            "requested_date": data_especifica.strftime('%Y-%m-%d')
        }), 500

    futuro = modelo.make_future_dataframe(df_aggregated.rename(columns={'Data': 'ds', 'QUANTIDADE': 'y'}), periods=30)
    previsao = modelo.predict(futuro)
    previsao_hoje = previsao[previsao['ds'].dt.date == data_especifica.date()]

    if previsao_hoje.empty:
        return jsonify({
            "error": "Data fora do intervalo de previsão.",
            "requested_date": data_especifica.strftime('%Y-%m-%d'),
            "forecast_period_start": previsao['ds'].min().strftime('%Y-%m-%d'),
            "forecast_period_end": previsao['ds'].max().strftime('%Y-%m-%d')
        }), 404

    total_previsto_hoje = previsao_hoje['yhat1'].values[0]
    top10list = []
    if dados is not None and 'Motorista' in dados.columns and 'QUANTIDADE' in dados.columns and total_eventos > 0:
        eventos_por_motorista = dados.groupby('Motorista')['QUANTIDADE'].sum().reset_index()
        top10motoristas = eventos_por_motorista.sort_values(by='QUANTIDADE', ascending=False).head(10)
        top10motoristas['Probabilidade'] = (top10motoristas['QUANTIDADE'] / total_eventos) * total_previsto_hoje
        top10list = top10motoristas[['Motorista', 'Probabilidade']].to_dict('records')

    probabilidade_eventos_especificos = {}
    eventos_especificos = ['Excesso de Velocidade', 'Fadiga', 'Curva Brusca']

    for evento_nome in eventos_especificos:
        if dados is None or 'Nome' not in dados.columns:
            probabilidade_eventos_especificos[evento_nome] = {"error": "Coluna 'Nome' não encontrada nos dados para eventos específicos."}
            continue
        dados_evento = dados[dados['Nome'] == evento_nome]
        if dados_evento.empty:
            probabilidade_eventos_especificos[evento_nome] = {"message": f"Nenhum dado para o evento: {evento_nome}."}
            continue

        total_eventos_tipo = dados_evento['QUANTIDADE'].sum()
        eventos_motorista_evento = dados_evento.groupby('Motorista')['QUANTIDADE'].sum().reset_index()
        top5motoristas_evento = eventos_motorista_evento.sort_values(by='QUANTIDADE', ascending=False).head(5)
        if not top5motoristas_evento.empty and total_eventos_tipo > 0:
            top5motoristas_evento['Probabilidade'] = (top5motoristas_evento['QUANTIDADE'] / total_eventos_tipo) * total_previsto_hoje
        else:
            top5motoristas_evento['Probabilidade'] = 0.0
        probabilidade_eventos_especificos[evento_nome] = top5motoristas_evento[['Motorista', 'Probabilidade']].to_dict('records')

    # NEW: Top 5 Locais de Maior Probabilidade
    top5_localidades_list = []
    # Verifica se a coluna 'Z' existe e se há dados para calcular
    if dados is not None and 'Z' in dados.columns and 'QUANTIDADE' in dados.columns and total_eventos > 0:
        # Agrupa eventos por localidade (coluna 'Z') e soma a quantidade
        eventos_por_localidade = dados.groupby('Z')['QUANTIDADE'].sum().reset_index()
        # Ordena e pega as top 5 localidades
        top5_localidades = eventos_por_localidade.sort_values(by='QUANTIDADE', ascending=False).head(5)
        # Calcula a probabilidade de cada localidade com base no total previsto
        top5_localidades['Probabilidade'] = (top5_localidades['QUANTIDADE'] / total_eventos) * total_previsto_hoje
        # Formata para a lista de dicionários esperada pelo frontend
        top5_localidades_list = top5_localidades[['Z', 'Probabilidade']].rename(columns={'Z': 'Localidade'}).to_dict('records')
    elif dados is None or 'Z' not in dados.columns:
        # Mensagem de erro se a coluna 'Z' não for encontrada
        top5_localidades_list = [{'message': 'Coluna "Z" (Localidades) não encontrada nos dados para calcular o top 5.'}]
    else:
        # Mensagem caso não haja dados ou total_eventos seja zero
        top5_localidades_list = [{'message': 'Nenhum dado disponível para calcular o top 5 de localidades.'}]


    return jsonify({
        "data_previsao": data_especifica.strftime('%Y-%m-%d'),
        "previsaototalyhat1": float(total_previsto_hoje),
        "top10motoristasgeral": top10list,
        "probabilidadeeventosespecificos": probabilidade_eventos_especificos,
        "top5localidades": top5_localidades_list # <-- Novo campo na resposta JSON
    })

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nome de arquivo vazio'}), 400
    if not file.filename.lower().endswith('.csv'):
        return jsonify({'error': 'Arquivo não permitido. Envie um arquivo .csv'}), 400

    try:
        file.save(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'basedadosseguranca.csv'))
        load_and_train_model()
        return jsonify({'success': True, 'message': 'Arquivo CSV atualizado e modelo recarregado com sucesso.'})
    except Exception as err:
        return jsonify({'error': f'Erro ao processar o arquivo: {str(err)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
