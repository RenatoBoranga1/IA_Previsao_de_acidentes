import pandas as pd
import numpy as np
# Importações não utilizadas no backend, mas mantidas se houver planos futuros:
# import matplotlib.pyplot as plt
# import seaborn as sns
# from termcolor import colored

import neuralprophet
from neuralprophet import NeuralProphet
import torch
import sys # Importado para sys.exit() em caso de erros críticos

# Suas configurações de safe_globals - CORRIGIDO: addsafeglobals -> add_safe_globals
# Mantidas as entradas específicas de numpy.dtypes conforme seu código original,
# pois o NeuralProphet pode ter requisitos específicos para isso.
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
    pd.libs.tslibs.timestamps.unpickle_timestamp,
    pd.libs.tslibs.timedeltas.timedelta_unpickle,
    np.core.multiarray.scalar,
    np.dtypes.Int64DType,
    neuralprophet.configure.ConfigFutureRegressors
])

# Importação do Flask
from flask import Flask, jsonify, request
from flask_cors import CORS # Para permitir que o frontend acesse o backend

app = Flask(__name__) # CORRIGIDO: name -> __name__
CORS(app) # Habilita CORS para todas as rotas

# --- INÍCIO DO SEU CÓDIGO DE PREVISÃO ADAPTADO PARA RODAR UMA VEZ ---
# Estas variáveis globais serão carregadas uma vez quando a aplicação iniciar
dados = None
modelo = None
df_aggregated = None # CORRIGIDO: dfaggregated -> df_aggregated
total_eventos = None

def load_and_train_model(): # CORRIGIDO: loadandtrain_model -> load_and_train_model
    global dados, modelo, df_aggregated, total_eventos # CORRIGIDO: dfaggregated -> df_aggregated, totaleventos -> total_eventos

    print("Iniciando carregamento e treinamento do modelo...")

    # 2. Carregar dados
    try:
        # Certifique-se de que 'basedadosseguranca.csv' está na mesma pasta ou forneça o caminho completo
        dados = pd.read_csv('basedadosseguranca.csv', delimiter=';')
    except FileNotFoundError:
        print("ERRO CRÍTICO: 'basedadosseguranca.csv' não encontrado. Certifique-se de que o arquivo está na pasta correta.")
        sys.exit(1) # Sai do programa se o arquivo de dados não for encontrado

    # 4. Verificar e preencher valores ausentes
    if 'Motorista' in dados.columns:
        dados['Motorista'] = dados['Motorista'].fillna(dados['Motorista'].mode()[0])
    else:
        print("AVISO: Coluna 'Motorista' não encontrada. Preenchimento de N/A para motoristas pode ser afetado.")

    for column in dados.columns:
        if dados[column].dtype == 'object' and column != 'Motorista': # Apenas colunas de objeto que não são 'Motorista'
            dados[column] = dados[column].fillna(dados[column].mode()[0])
        elif dados[column].dtype in ['int64', 'float64']:
            dados[column] = dados[column].fillna(dados[column].mean())

    # 6. Converter colunas de data para datetime
    if 'Data' in dados.columns:
        dados['Data'] = pd.to_datetime(dados['Data'], dayfirst=True)
    else:
        print("ERRO CRÍTICO: Coluna 'Data' não encontrada no arquivo CSV. Impossível prosseguir.")
        sys.exit(1)

    # 8. Remover duplicatas agregando a quantidade de eventos por data
    if 'QUANTIDADE' in dados.columns:
        df_aggregated = dados.groupby('Data', as_index=False)['QUANTIDADE'].sum() # CORRIGIDO: asindex -> as_index
    else:
        print("ERRO CRÍTICO: Coluna 'QUANTIDADE' não encontrada no arquivo CSV. Impossível prosseguir.")
        sys.exit(1)

    # 9. Preparar os dados para o NeuralProphet
    if df_aggregated is not None and not df_aggregated.empty:
        df = df_aggregated.rename(columns={'Data': 'ds', 'QUANTIDADE': 'y'})
    else:
        print("ERRO CRÍTICO: Dados agregados estão vazios ou não foram criados. Impossível treinar o modelo.")
        sys.exit(1)

    # 10. Criar o modelo NeuralProphet
    modelo = NeuralProphet()

    # 11. Ajustar o modelo aos dados
    print("Treinando o modelo NeuralProphet...")
    modelo.fit(df, freq='D')
    print("Modelo NeuralProphet treinado.")

    if 'QUANTIDADE' in dados.columns:
        total_eventos = dados['QUANTIDADE'].sum()
    else:
        total_eventos = 0
        print("AVISO: Coluna 'QUANTIDADE' não encontrada para calcular total_eventos.")

# Carrega e treina o modelo quando a aplicação Flask é iniciada
print("Carregando e treinando o modelo. Isso pode levar alguns minutos...")
load_and_train_model() # CORRIGIDO: loadandtrain_model -> load_and_train_model
print("Modelo carregado e treinado com sucesso!")
# --- FIM DO SEU CÓDIGO DE PREVISÃO ADAPTADO ---


@app.route('/predict', methods=['GET'])
def get_prediction():
    # Pega a data da requisição GET, se não for fornecida, usa a data do dia seguinte
    date_str = request.args.get('date', pd.to_datetime('today').normalize() + pd.Timedelta(days=1)) # CORRIGIDO: pd.todatetime -> pd.to_datetime, datestr -> date_str

    # Se for uma string, converte para datetime
    if isinstance(date_str, str):
        data_especifica = pd.to_datetime(date_str) # CORRIGIDO: dataespecifica -> data_especifica, pd.todatetime -> pd.to_datetime
    else: # se já for um datetime object (do default)
        data_especifica = date_str # CORRIGIDO: dataespecifica -> data_especifica

    # Validação inicial do modelo e dados
    if modelo is None or df_aggregated is None:
        return jsonify({
            "error": "O modelo ou os dados agregados não foram carregados corretamente na inicialização. Por favor, verifique os logs do servidor.",
            "requested_date": data_especifica.strftime('%Y-%m-%d')
        }), 500

    # 12. Criar um DataFrame para as futuras previsões (ajuste periods conforme necessário)
    futuro = modelo.make_future_dataframe(df_aggregated.rename(columns={'Data': 'ds', 'QUANTIDADE': 'y'}), periods=30) # CORRIGIDO: makefuturedataframe -> make_future_dataframe

    # 13. Fazer a previsão
    previsao = modelo.predict(futuro)

    # 14. Filtrar a previsão para a data específica, comparando apenas a parte da data
    previsao_hoje = previsao[previsao['ds'].dt.date == data_especifica.date()] # CORRIGIDO: previsaohoje -> previsao_hoje, dataespecifica -> data_especifica

    if previsao_hoje.empty:
        # Se a data não for encontrada, retorna um erro ou uma mensagem para o frontend
        return jsonify({
            "error": "Data fora do intervalo de previsão ou não encontrada. Verifique se a data solicitada está dentro do período de previsão gerado.",
            "requested_date": data_especifica.strftime('%Y-%m-%d'), # CORRIGIDO: requesteddate -> requested_date
            "forecast_period_start": previsao['ds'].min().strftime('%Y-%m-%d'), # CORRIGIDO: forecastperiodstart -> forecast_period_start
            "forecast_period_end": previsao['ds'].max().strftime('%Y-%m-%d') # CORRIGIDO: forecastperiodend -> forecast_period_end
        }), 404 # Código de status HTTP 404 Not Found

    total_previsto_hoje = previsao_hoje['yhat1'].values[0] # CORRIGIDO: totalprevistohoje -> total_previsto_hoje

    # 15. Analisando os 10 motoristas mais propensos a eventos
    top_10_list = []
    if dados is not None and 'Motorista' in dados.columns and 'QUANTIDADE' in dados.columns and total_eventos is not None and total_eventos > 0 and not pd.isna(total_previsto_hoje):
        eventos_por_motorista = dados.groupby('Motorista')['QUANTIDADE'].sum().reset_index() # CORRIGIDO: eventospormotorista -> eventos_por_motorista
        top_10_motoristas = eventos_por_motorista.sort_values(by='QUANTIDADE', ascending=False).head(10) # CORRIGIDO: top10motoristas -> top_10_motoristas

        # Evita divisão por zero ou cálculo com NaN
        if total_eventos > 0 and not pd.isna(total_previsto_hoje):
            top_10_motoristas['Probabilidade'] = (top_10_motoristas['QUANTIDADE'] / total_eventos) * total_previsto_hoje
        else:
            top_10_motoristas['Probabilidade'] = 0.0

        top_10_list = top_10_motoristas[['Motorista', 'Probabilidade']].to_dict('records') # CORRIGIDO: top10list -> top_10_list
    else:
        print("AVISO: Não foi possível calcular o Top 10 Motoristas (dados ausentes ou total de eventos zero).")


    # 17. Analisando os 5 motoristas mais propensos a um tipo específico de evento
    eventos_especificos = ['Excesso de Velocidade', 'Fadiga', 'Curva Brusca']
    eventos_probabilidades = {} # CORRIGIDO: eventos_probabilidades

    for evento_nome in eventos_especificos: # CORRIGIDO: eventonome -> evento_nome
        # Verifique se a coluna 'Nome' existe nos dados de origem
        if dados is None or 'Nome' not in dados.columns:
            eventos_probabilidades[evento_nome] = {"error": "Coluna 'Nome' não encontrada nos dados de origem para eventos específicos. Verifique seu CSV."}
            continue

        dados_evento = dados[dados['Nome'] == evento_nome] # CORRIGIDO: dadosevento -> dados_evento

        if dados_evento.empty:
            eventos_probabilidades[evento_nome] = {"message": f"Nenhum dado histórico encontrado para o evento: {evento_nome}."}
            continue

        total_eventos_tipo = dados_evento['QUANTIDADE'].sum() # CORRIGIDO: totaleventostipo -> total_eventos_tipo
        eventos_por_motorista_evento = dados_evento.groupby('Motorista')['QUANTIDADE'].sum().reset_index() # CORRIGIDO: eventospormotoristaevento -> eventos_por_motorista_evento
        top_5_motoristas_evento = eventos_por_motorista_evento.sort_values(by='QUANTIDADE', ascending=False).head(5) # CORRIGIDO: top5motoristasevento -> top_5_motoristas_evento

        if top_5_motoristas_evento.empty:
            eventos_probabilidades[evento_nome] = {"message": f"Nenhum motorista encontrado para o evento: {evento_nome}."}
            continue

        # Evita divisão por zero ou cálculo com NaN
        if total_eventos_tipo > 0 and not pd.isna(total_previsto_hoje):
            top_5_motoristas_evento['Probabilidade'] = (top_5_motoristas_evento['QUANTIDADE'] / total_eventos_tipo) * total_previsto_hoje
        else:
            top_5_motoristas_evento['Probabilidade'] = 0.0

        eventos_probabilidades[evento_nome] = top_5_motoristas_evento[['Motorista', 'Probabilidade']].to_dict('records') # CORRIGIDO: todict -> to_dict


    # Retorna todos os dados como JSON
    return jsonify({
        "data_previsao": data_especifica.strftime('%Y-%m-%d'), # CORRIGIDO: dataprevisao -> data_previsao
        "previsao_total_yhat1": float(total_previsto_hoje), # CORRIGIDO: previsaototalyhat1 -> previsao_total_yhat1
        # "detalhes_previsao": previsao_hoje.iloc[0].drop('ds').to_dict(), # Removido conforme sua solicitação para o frontend
        "top_10_motoristas_geral": top_10_list, # CORRIGIDO: top10motoristasgeral -> top_10_motoristas_geral
        "probabilidade_eventos_especificos": eventos_probabilidades # CORRIGIDO: probabilidadeeventosespecificos -> probabilidade_eventos_especificos
    })

if __name__ == '__main__': # CORRIGIDO: name -> __name__
    # Para rodar em ambiente de desenvolvimento
    app.run(debug=True, port=5000)
