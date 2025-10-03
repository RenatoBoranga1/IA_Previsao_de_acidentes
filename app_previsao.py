import pandas as pd
import numpy as np
import neuralprophet
from neuralprophet import NeuralProphet
import torch
import sys  # Para sys.exit() em caso de erros críticos

# Importação do Flask
from flask import Flask, jsonify, request
from flask_cors import CORS  # Para permitir que o frontend acesse o backend

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas

# --- INÍCIO DO SEU CÓDIGO DE PREVISÃO ADAPTADO PARA RODAR UMA VEZ ---
# Variáveis globais carregadas na inicialização
dados = None
modelo = None
df_aggregated = None
total_eventos = None
motoristas_desligados_list = []  # NOVA VARIÁVEL GLOBAL

def load_and_train_model():
    global dados, modelo, df_aggregated, total_eventos, motoristas_desligados_list

    print("Iniciando carregamento e treinamento do modelo...")

    # Carregar dados principais
    try:
        dados = pd.read_csv('basedadosseguranca.csv', delimiter=';')
    except FileNotFoundError:
        print("ERRO CRÍTICO: 'basedadosseguranca.csv' não encontrado.")
        sys.exit(1)

    # Carregar motoristas desligados
    try:
        desligados_df = pd.read_csv('motoristas_desligados.csv', delimiter=';')
        if 'Motorista' in desligados_df.columns:
            motoristas_desligados_list = desligados_df['Motorista'].tolist()
            print(f"INFO: {len(motoristas_desligados_list)} motoristas desligados carregados.")
    except FileNotFoundError:
        print("AVISO: 'motoristas_desligados.csv' não encontrado. Nenhum motorista será filtrado.")
    except Exception as e:
        print(f"ERRO ao carregar 'motoristas_desligados.csv': {e}")

    # Preencher valores ausentes
    if 'Motorista' in dados.columns:
        dados['Motorista'] = dados['Motorista'].fillna(dados['Motorista'].mode().iloc[0])
    if 'Localidade' in dados.columns:
        dados['Localidade'] = dados['Localidade'].fillna('Desconhecida')

    for column in dados.columns:
        if dados[column].dtype == 'object' and column not in ['Motorista', 'Localidade']:
            dados[column] = dados[column].fillna(dados[column].mode().iloc[0])
        elif dados[column].dtype in ['int64', 'float64']:
            dados[column] = dados[column].fillna(dados[column].mean())

    # Converter colunas de data
    if 'Data' in dados.columns:
        dados['Data'] = pd.to_datetime(dados['Data'], format='mixed', dayfirst=True, errors='coerce')
        dados.dropna(subset=['Data'], inplace=True)
        if dados.empty:
            print("ERRO CRÍTICO: DataFrame vazio após limpeza de datas inválidas.")
            sys.exit(1)
    else:
        print("ERRO CRÍTICO: Coluna 'Data' não encontrada no CSV.")
        sys.exit(1)

    # Agregar quantidade de eventos por data
    if 'QUANTIDADE' in dados.columns:
        df_aggregated = dados.groupby('Data', as_index=False)['QUANTIDADE'].sum()
    else:
        print("ERRO CRÍTICO: Coluna 'QUANTIDADE' não encontrada no CSV.")
        sys.exit(1)

    # Preparar dados para o NeuralProphet
    df = df_aggregated.rename(columns={'Data': 'ds', 'QUANTIDADE': 'y'})

    # Criar e treinar o modelo
    modelo = NeuralProphet()
    try:
        modelo.fit(df, freq='D')
        print("Modelo NeuralProphet treinado.")
    except Exception as e:
        print(f"ERRO ao treinar o modelo: {e}")
        sys.exit(1)

    total_eventos = dados['QUANTIDADE'].sum() if 'QUANTIDADE' in dados.columns else 0

# Carrega e treina o modelo ao iniciar a aplicação
print("Carregando e treinando o modelo...")
load_and_train_model()
print("Modelo carregado e treinado com sucesso!")
# --- FIM DO CÓDIGO DE PREVISÃO ---

@app.route('/predict', methods=['GET'])
def get_prediction():
    date_str = request.args.get('date', pd.to_datetime('today').normalize() + pd.Timedelta(days=1))
    if isinstance(date_str, str):
        data_especifica = pd.to_datetime(date_str)
    else:
        data_especifica = date_str

    if modelo is None or df_aggregated is None:
        return jsonify({
            "error": "O modelo ou os dados agregados não foram carregados corretamente.",
            "requested_date": data_especifica.strftime('%Y-%m-%d')
        }), 500

    if df_aggregated.empty:
        return jsonify({
            "error": "Não há dados históricos para gerar previsões.",
            "requested_date": data_especifica.strftime('%Y-%m-%d')
        }), 500

    try:
        futuro = modelo.make_future_dataframe(df=df_aggregated.rename(columns={'Data': 'ds', 'QUANTIDADE': 'y'}), periods=30)
        previsao = modelo.predict(futuro)
    except Exception as e:
        return jsonify({"error": f"Erro ao gerar previsão: {e}"}), 500

    previsao_hoje = previsao[previsao['ds'].dt.date == data_especifica.date()]
    if previsao_hoje.empty:
        return jsonify({"error": "Data fora do intervalo de previsão."}), 404

    total_previsto_hoje = previsao_hoje['yhat1'].values[0]

    # Top 10 motoristas
    top_10_list = []
    if dados is not None and 'Motorista' in dados.columns and total_eventos > 0:
        eventos_por_motorista = dados.groupby('Motorista')['QUANTIDADE'].sum().reset_index()
        top_10_motoristas = eventos_por_motorista.sort_values(by='QUANTIDADE', ascending=False)
        if motoristas_desligados_list:
            top_10_motoristas = top_10_motoristas[~top_10_motoristas['Motorista'].isin(motoristas_desligados_list)]
        top_10_motoristas = top_10_motoristas.head(10)
        top_10_motoristas['Probabilidade'] = (top_10_motoristas['QUANTIDADE'] / total_eventos) * total_previsto_hoje
        top_10_list = top_10_motoristas[['Motorista', 'Probabilidade']].to_dict('records')

    # Top 3 localidades
    top_3_localidades_list = []
    if dados is not None and 'Localidade' in dados.columns and total_eventos > 0:
        eventos_por_localidade = dados.groupby('Localidade')['QUANTIDADE'].sum().reset_index()
        top_3_localidades = eventos_por_localidade.sort_values(by='QUANTIDADE', ascending=False).head(3)
        top_3_localidades['Probabilidade'] = (top_3_localidades['QUANTIDADE'] / total_eventos) * total_previsto_hoje
        top_3_localidades_list = top_3_localidades[['Localidade', 'Probabilidade']].to_dict('records')

    return jsonify({
        "data_previsao": data_especifica.strftime('%Y-%m-%d'),
        "previsao_total_yhat1": float(total_previsto_hoje),
        "top_10_motoristas_geral": top_10_list,
        "top_3_localidades": top_3_localidades_list
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
