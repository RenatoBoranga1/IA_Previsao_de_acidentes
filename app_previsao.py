import os
import logging
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify
from neuralprophet import NeuralProphet

# Configuração de logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Inicializar o Flask
app = Flask(__name__)

# Variáveis globais
dados = None
modelo = None
df_aggregated = None
periodo_treinamento = None

def carregar_dados():
    global dados, modelo, df_aggregated, periodo_treinamento
    try:
        # Carregar dados
        dados = pd.read_csv('basedadosseguranca.csv', delimiter=';', encoding='utf-8')

        if dados.empty:
            logging.error("O arquivo CSV está vazio.")
            return

        # Padronizar colunas
        dados.columns = [col.strip().upper() for col in dados.columns]
        logging.info(f"Colunas disponíveis: {dados.columns}")

        # Validar colunas necessárias
        colunas_necessarias = ['DATA', 'MOTORISTA', 'QUANTIDADE']
        for col in colunas_necessarias:
            if col not in dados.columns:
                logging.error(f"Coluna necessária ausente no CSV: {col}")
                return

        # Converter datas
        dados['Data'] = pd.to_datetime(dados['DATA'], dayfirst=True, errors='coerce')
        if dados['Data'].isnull().any():
            logging.warning("Existem datas inválidas no CSV. Linhas serão descartadas.")
            dados = dados.dropna(subset=['Data'])

        # Converter quantidade
        dados['QUANTIDADE'] = pd.to_numeric(dados['QUANTIDADE'], errors='coerce').fillna(0)

        # Agregar dados
        df_aggregated = dados.groupby('Data').agg({'QUANTIDADE': 'sum'}).reset_index()
        df_aggregated = df_aggregated.rename(columns={'Data': 'ds', 'QUANTIDADE': 'y'})

        # Definir período de treinamento
        periodo_treinamento = len(df_aggregated)

        # Treinar modelo
        modelo = NeuralProphet(yearly_seasonality=True, weekly_seasonality=True, daily_seasonality=False)
        modelo.fit(df_aggregated, freq='D')

        logging.info("Modelo treinado com sucesso.")

    except FileNotFoundError:
        logging.error("O arquivo basedadosseguranca.csv não foi encontrado.")
    except Exception as e:
        logging.exception(f"Erro ao carregar dados: {e}")


@app.route('/predict', methods=['GET'])
def predict():
    global dados, modelo, df_aggregated, periodo_treinamento
    try:
        if modelo is None or df_aggregated is None:
            return jsonify({"erro": "Modelo não está carregado. Tente novamente mais tarde."}), 500

        # Receber data da requisição
        data_referencia = request.args.get('data')
        if not data_referencia:
            return jsonify({"erro": "Por favor, forneça a data no formato YYYY-MM-DD."}), 400

        # Previsão
        futuro = modelo.make_future_dataframe(df_aggregated, periods=7, n_historic_predictions=True)
        forecast = modelo.predict(futuro)

        forecast['yhat1'] = forecast['yhat1'].clip(lower=0)

        previsao_data = forecast.loc[forecast['ds'] == data_referencia, 'yhat1']
        if previsao_data.empty:
            return jsonify({"erro": f"Não há previsão para a data {data_referencia}."}), 404

        total_previsto_hoje = float(previsao_data.values[0])

        # Distribuir por motoristas (histórico proporcional)
        df_motoristas = dados.groupby('MOTORISTA').agg({'QUANTIDADE': 'sum'}).reset_index()
        total_eventos = df_motoristas['QUANTIDADE'].sum()

        if total_eventos == 0:
            return jsonify({"erro": "Não há dados suficientes para calcular probabilidades."}), 500

        df_motoristas['Probabilidade'] = (df_motoristas['QUANTIDADE'] / total_eventos) * total_previsto_hoje
        df_motoristas['Probabilidade'] = np.maximum(0, df_motoristas['Probabilidade'])

        top_10_motoristas = df_motoristas.sort_values(by='Probabilidade', ascending=False).head(10)

        return jsonify({
            "data_referencia": data_referencia,
            "total_previsto": total_previsto_hoje,
            "top_10_motoristas": top_10_motoristas.to_dict(orient='records')
        })

    except Exception as e:
        logging.exception(f"Erro na previsão: {e}")
        return jsonify({"erro": str(e)}), 500


if __name__ == '__main__':
    carregar_dados()
    # Nunca usar debug=True em produção
    app.run(host="0.0.0.0", port=5000)
