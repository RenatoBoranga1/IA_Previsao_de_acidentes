import os
import pandas as pd
import numpy as np
# Importações não utilizadas no backend, mas mantidas se houver planos futuros:
# import matplotlib.pyplot as plt
# import seaborn as sns
# from termcolor import colored

import neuralprophet
from neuralprophet import NeuralProphet
import torch
import sys  # Para sys.exit() em caso de erros críticos

# Configurações de safe_globals do PyTorch
torch.serialization.add_safe_globals([
    neuralprophet.configure.ConfigSeasonality,
    neuralprophet.configure.Season,
    neuralprophet.configure.Train,
    torch.nn.modules.loss.SmoothL1Loss,
    torch.optim.AdamW,
    torch.optim.lr_scheduler.OneCycleLR,
    neuralprophet.configure.Trend,
    np.core.multiarray._reconstruct,
    np.ndarray,
    np.dtype,
    np.dtypes.Float64DType,
    neuralprophet.configure.AR,
    neuralprophet.configure.Normalization,
    neuralprophet.df_utils.ShiftScale,
    pd._libs.tslibs.timestamps._unpickle_timestamp,
    pd._libs.tslibs.timedeltas._timedelta_unpickle,
    np.core.multiarray.scalar,
    np.dtypes.Int64DType,
    neuralprophet.configure.ConfigFutureRegressors
])

# Importação do Flask
from flask import Flask, jsonify, request
from flask_cors import CORS  # Para permitir que o frontend acesse o backend

app = Flask(__name__)
CORS(app)  # Habilita CORS para todas as rotas

# --- INÍCIO DO CÓDIGO DE PREVISÃO ---
dados = None
modelo = None
df_aggregated = None
total_eventos = None
motoristas_desligados_list = []  # Variável global

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
        else:
            print("AVISO: Coluna 'Motorista' não encontrada em 'motoristas_desligados.csv'.")
            motoristas_desligados_list = []
    except FileNotFoundError:
        print("AVISO: 'motoristas_desligados.csv' não encontrado.")
        motoristas_desligados_list = []
    except Exception as e:
        print(f"ERRO ao carregar 'motoristas_desligados.csv': {e}")
        motoristas_desligados_list = []

    # Preencher valores ausentes
    if 'Motorista' in dados.columns:
        dados['Motorista'] = dados['Motorista'].fillna(dados['Motorista'].mode().iloc[0])
    else:
        print("AVISO: Coluna 'Motorista' não encontrada.")

    if 'Localidade' in dados.columns:
        dados['Localidade'] = dados['Localidade'].fillna('Desconhecida')
    else:
        print("AVISO: Coluna 'Localidade' não encontrada.")

    for column in dados.columns:
        if dados[column].dtype == 'object' and column not in ['Motorista', 'Localidade']:
            dados[column] = dados[column].fillna(dados[column].mode().iloc[0])
        elif dados[column].dtype in ['int64', 'float64']:
            dados[column] = dados[column].fillna(dados[column].mean())

    # Converter datas
    if 'Data' in dados.columns:
        dados['Data'] = pd.to_datetime(dados['Data'], format='mixed', dayfirst=True, errors='coerce')
        if dados['Data'].isnull().any():
            num_invalid_dates = dados['Data'].isnull().sum()
            print(f"AVISO: {num_invalid_dates} datas inválidas removidas.")
            dados.dropna(subset=['Data'], inplace=True)
        if dados.empty:
            print("ERRO CRÍTICO: DataFrame vazio após limpeza de datas.")
            sys.exit(1)
    else:
        print("ERRO CRÍTICO: Coluna 'Data' não encontrada.")
        sys.exit(1)

    # Agregar dados
    if 'QUANTIDADE' in dados.columns:
        df_aggregated = dados.groupby('Data', as_index=False)['QUANTIDADE'].sum()
    else:
        print("ERRO CRÍTICO: Coluna 'QUANTIDADE' não encontrada.")
        sys.exit(1)

    # Preparar dados para NeuralProphet
    df = df_aggregated.rename(columns={'Data': 'ds', 'QUANTIDADE': 'y'})
    modelo = NeuralProphet()

    print("Treinando o modelo NeuralProphet...")
    try:
        modelo.fit(df, freq='D')
        print("Modelo treinado.")
    except Exception as e:
        print(f"ERRO CRÍTICO ao treinar o modelo: {e}")
        sys.exit(1)

    total_eventos = dados['QUANTIDADE'].sum() if 'QUANTIDADE' in dados.columns else 0

# Carrega e treina o modelo na inicialização
print("Carregando e treinando o modelo. Isso pode levar alguns minutos...")
load_and_train_model()
print("Modelo carregado e treinado com sucesso!")
# --- FIM DO CÓDIGO DE PREVISÃO ---

@app.route('/predict', methods=['GET'])
def get_prediction():
    date_str = request.args.get('date', pd.to_datetime('today').normalize() + pd.Timedelta(days=1))
    data_especifica = pd.to_datetime(date_str) if isinstance(date_str, str) else date_str

    if modelo is None or df_aggregated is None:
        return jsonify({
            "error": "O modelo ou dados não foram carregados corretamente.",
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
        return jsonify({
            "error": f"Erro ao gerar previsões: {e}",
            "requested_date": data_especifica.strftime('%Y-%m-%d')
        }), 500

    previsao_hoje = previsao[previsao['ds'].dt.date == data_especifica.date()]
    if previsao_hoje.empty:
        return jsonify({
            "error": "Data fora do intervalo de previsão.",
            "requested_date": data_especifica.strftime('%Y-%m-%d'),
            "forecast_period_start": previsao['ds'].min().strftime('%Y-%m-%d') if not previsao.empty else "N/A",
            "forecast_period_end": previsao['ds'].max().strftime('%Y-%m-%d') if not previsao.empty else "N/A"
        }), 404

    total_previsto_hoje = previsao_hoje['yhat1'].values[0]

    # Top 10 motoristas
    top_10_list = []
    if dados is not None and not dados.empty and 'Motorista' in dados.columns and 'QUANTIDADE' in dados.columns and total_eventos > 0:
        eventos_por_motorista = dados.groupby('Motorista')['QUANTIDADE'].sum().reset_index()
        top_10_motoristas = eventos_por_motorista.sort_values(by='QUANTIDADE', ascending=False)
        if motoristas_desligados_list:
            top_10_motoristas = top_10_motoristas[~top_10_motoristas['Motorista'].isin(motoristas_desligados_list)]
        top_10_motoristas = top_10_motoristas.head(10)
        top_10_motoristas['Probabilidade'] = (top_10_motoristas['QUANTIDADE'] / total_eventos) * total_previsto_hoje
        top_10_list = top_10_motoristas[['Motorista', 'Probabilidade']].to_dict('records')

    # Eventos específicos
    eventos_especificos = ['Excesso de Velocidade', 'Fadiga', 'Curva Brusca']
    eventos_probabilidades = {}
    for evento_nome in eventos_especificos:
        if dados is None or dados.empty or 'Nome' not in dados.columns:
            eventos_probabilidades[evento_nome] = {"error": "Dados insuficientes."}
            continue
        dados_evento = dados[dados['Nome'] == evento_nome]
        if dados_evento.empty:
            eventos_probabilidades[evento_nome] = {"message": f"Nenhum dado histórico para {evento_nome}."}
            continue
        total_eventos_tipo = dados_evento['QUANTIDADE'].sum()
        eventos_por_motorista_evento = dados_evento.groupby('Motorista')['QUANTIDADE'].sum().reset_index()
        top_5_motoristas_evento = eventos_por_motorista_evento.sort_values(by='QUANTIDADE', ascending=False)
        if motoristas_desligados_list:
            top_5_motoristas_evento = top_5_motoristas_evento[~top_5_motoristas_evento['Motorista'].isin(motoristas_desligados_list)]
        top_5_motoristas_evento = top_5_motoristas_evento.head(5)
        top_5_motoristas_evento['Probabilidade'] = (top_5_motoristas_evento['QUANTIDADE'] / total_eventos_tipo) * total_previsto_hoje if total_eventos_tipo > 0 else 0
        eventos_probabilidades[evento_nome] = top_5_motoristas_evento[['Motorista', 'Probabilidade']].to_dict('records')

    # Top 3 localidades
    top_3_localidades_list = []
    if dados is not None and not dados.empty and 'Localidade' in dados.columns and total_eventos > 0:
        eventos_por_localidade = dados.groupby('Localidade')['QUANTIDADE'].sum().reset_index()
        top_3_localidades = eventos_por_localidade.sort_values(by='QUANTIDADE', ascending=False).head(3)
        top_3_localidades['Probabilidade'] = (top_3_localidades['QUANTIDADE'] / total_eventos) * total_previsto_hoje
        top_3_localidades_list = top_3_localidades[['Localidade', 'Probabilidade']].to_dict('records')

    return jsonify({
        "data_previsao": data_especifica.strftime('%Y-%m-%d'),
        "previsao_total_yhat1": float(total_previsto_hoje),
        "top_10_motoristas_geral": top_10_list,
        "probabilidade_eventos_especificos": eventos_probabilidades,
        "top_3_localidades": top_3_localidades_list
    })

if __name__ == '__main__':
    # Render exige porta dinâmica
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
