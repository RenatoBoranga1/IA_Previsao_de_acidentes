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

# Suas configurações de safe_globals
# Adicionando os globais do pandas._libs que o PyTorch explicitamente pede para permitir,
# para desserialização segura.
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
    # Adicionado conforme a mensagem de erro do PyTorch
    pd._libs.tslibs.timestamps._unpickle_timestamp,
    pd._libs.tslibs.timedeltas._timedelta_unpickle, # Adicionado preventivamente, caso ocorra erro similar com Timedelta
    np.core.multiarray.scalar,
    np.dtypes.Int64DType,
    neuralprophet.configure.ConfigFutureRegressors
])

# Importação do Flask
from flask import Flask, jsonify, request
from flask_cors import CORS # Para permitir que o frontend acesse o backend

app = Flask(__name__)
CORS(app) # Habilita CORS para todas as rotas

# --- INÍCIO DO SEU CÓDIGO DE PREVISÃO ADAPTADO PARA RODAR UMA VEZ ---
# Estas variáveis globais serão carregadas uma vez quando a aplicação iniciar
dados = None
modelo = None
df_aggregated = None
total_eventos = None
motoristas_desligados_list = [] # NOVA VARIÁVEL GLOBAL

def load_and_train_model():
    global dados, modelo, df_aggregated, total_eventos, motoristas_desligados_list

    print("Iniciando carregamento e treinamento do modelo...")

    # 2. Carregar dados principais
    try:
        dados = pd.read_csv('basedadosseguranca.csv', delimiter=';')
    except FileNotFoundError:
        print("ERRO CRÍTICO: 'basedadosseguranca.csv' não encontrado. Certifique-se de que o arquivo está na pasta correta.")
        sys.exit(1) # Sai do programa se o arquivo de dados não for encontrado

    # NOVO: Carregar motoristas desligados
    try:
        desligados_df = pd.read_csv('motoristas_desligados.csv', delimiter=';')
        if 'Motorista' in desligados_df.columns:
            motoristas_desligados_list = desligados_df['Motorista'].tolist()
            print(f"INFO: {len(motoristas_desligados_list)} motoristas desligados carregados.")
        else:
            print("AVISO: 'motoristas_desligados.csv' encontrado, mas não contém a coluna 'Motorista'. Nenhum motorista será filtrado.")
            motoristas_desligados_list = []
    except FileNotFoundError:
        print("AVISO: 'motoristas_desligados.csv' não encontrado. Nenhum motorista será filtrado como desligado.")
        motoristas_desligados_list = []
    except Exception as e:
        print(f"ERRO ao carregar 'motoristas_desligados.csv': {e}. Nenhum motorista será filtrado.")
        motoristas_desligados_list = []


    # 4. Verificar e preencher valores ausentes
    if 'Motorista' in dados.columns:
        dados['Motorista'] = dados['Motorista'].fillna(dados['Motorista'].mode().iloc[0])
    else:
        print("AVISO: Coluna 'Motorista' não encontrada. Preenchimento de N/A para motoristas pode ser afetado.")

    # Verificar e preencher valores ausentes na coluna 'Localidade'
    if 'Localidade' in dados.columns:
        dados['Localidade'] = dados['Localidade'].fillna('Desconhecida') # Preenche com um valor padrão
    else:
        print("AVISO: Coluna 'Localidade' não encontrada. Preenchimento de N/A para localidades pode ser afetado.")


    # Lidar com outras colunas de objeto e numéricas
    for column in dados.columns:
        # Exclui 'Motorista' e 'Localidade' do preenchimento genérico, pois já foram tratados
        if dados[column].dtype == 'object' and column not in ['Motorista', 'Localidade']:
            dados[column] = dados[column].fillna(dados[column].mode().iloc[0])
        elif dados[column].dtype in ['int64', 'float64']:
            dados[column] = dados[column].fillna(dados[column].mean())

    # 6. Converter colunas de data para datetime
    if 'Data' in dados.columns:
        # === ALTERAÇÃO AQUI: Usar format='mixed' e errors='coerce' ===
        dados['Data'] = pd.to_datetime(dados['Data'], format='mixed', dayfirst=True, errors='coerce')

        # Verificar se há valores NaT após a conversão, indicando falhas na conversão
        if dados['Data'].isnull().any():
            num_invalid_dates = dados['Data'].isnull().sum()
            print(f"AVISO: {num_invalid_dates} valores na coluna 'Data' não puderam ser convertidos para datetime e foram definidos como NaT.")
            print("Por favor, verifique a consistência do formato das datas no seu 'basedadosseguranca.csv'.")
            
            # Remover as linhas com datas inválidas para evitar problemas no treinamento do modelo
            dados.dropna(subset=['Data'], inplace=True)
            print("INFO: Linhas com datas inválidas foram removidas para prosseguir com o treinamento do modelo.")
        
        # Verificar se o DataFrame não ficou vazio após a remoção de linhas com datas inválidas
        if dados.empty:
            print("ERRO CRÍTICO: Após a limpeza de datas inválidas, o DataFrame ficou vazio. Impossível prosseguir.")
            sys.exit(1)

    else:
        print("ERRO CRÍTICO: Coluna 'Data' não encontrada no arquivo CSV. Impossível prosseguir.")
        sys.exit(1)

    # 8. Remover duplicatas agregando a quantidade de eventos por data
    if 'QUANTIDADE' in dados.columns:
        df_aggregated = dados.groupby('Data', as_index=False)['QUANTIDADE'].sum()
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
    try:
        modelo.fit(df, freq='D')
        print("Modelo NeuralProphet treinado.")
    except Exception as e:
        print(f"ERRO CRÍTICO ao treinar o modelo NeuralProphet: {e}")
        print("Certifique-se de que todas as dependências estão corretas e que o Pandas e o PyTorch estão compatíveis.")
        sys.exit(1)


    if 'QUANTIDADE' in dados.columns:
        total_eventos = dados['QUANTIDADE'].sum()
    else:
        total_eventos = 0
        print("AVISO: Coluna 'QUANTIDADE' não encontrada para calcular total_eventos.")

# Carrega e treina o modelo quando a aplicação Flask é iniciada
print("Carregando e treinando o modelo. Isso pode levar alguns minutos...")
load_and_train_model()
print("Modelo carregado e treinado com sucesso!")
# --- FIM DO SEU CÓDIGO DE PREVISÃO ADAPTADO ---


@app.route('/predict', methods=['GET'])
def get_prediction():
    # Pega a data da requisição GET, se não for fornecida, usa a data do dia seguinte
    date_str = request.args.get('date', pd.to_datetime('today').normalize() + pd.Timedelta(days=1))

    # Se for uma string, converte para datetime
    if isinstance(date_str, str):
        data_especifica = pd.to_datetime(date_str)
    else:
        data_especifica = date_str

    # Validação inicial do modelo e dados
    if modelo is None or df_aggregated is None:
        return jsonify({
            "error": "O modelo ou os dados agregados não foram carregados corretamente na inicialização. Por favor, verifique os logs do servidor.",
            "requested_date": data_especifica.strftime('%Y-%m-%d')
        }), 500

    # 12. Criar um DataFrame para as futuras previsões (ajuste periods conforme necessário)
    # A renomeação é feita aqui para o método make_future_dataframe que espera 'ds' e 'y'
    # Certifique-se que df_aggregated é um DataFrame e tem as colunas esperadas
    if df_aggregated.empty:
        return jsonify({
            "error": "Não há dados históricos para gerar previsões futuras.",
            "requested_date": data_especifica.strftime('%Y-%m-%d')
        }), 500

    try:
        futuro = modelo.make_future_dataframe(df=df_aggregated.rename(columns={'Data': 'ds', 'QUANTIDADE': 'y'}), periods=30)
    except Exception as e:
        return jsonify({
            "error": f"Erro ao criar o dataframe futuro para previsão: {e}",
            "requested_date": data_especifica.strftime('%Y-%m-%d')
        }), 500

    # 13. Fazer a previsão
    try:
        previsao = modelo.predict(futuro)
    except Exception as e:
        return jsonify({
            "error": f"Erro ao fazer a previsão com o modelo: {e}",
            "requested_date": data_especifica.strftime('%Y-%m-%d')
        }), 500

    # 14. Filtrar a previsão para a data específica, comparando apenas a parte da data
    previsao_hoje = previsao[previsao['ds'].dt.date == data_especifica.date()]

    if previsao_hoje.empty:
        # Se a data não for encontrada, retorna um erro ou uma mensagem para o frontend
        return jsonify({
            "error": "Data fora do intervalo de previsão ou não encontrada. Verifique se a data solicitada está dentro do período de previsão gerado.",
            "requested_date": data_especifica.strftime('%Y-%m-%d'),
            "forecast_period_start": previsao['ds'].min().strftime('%Y-%m-%d') if not previsao.empty else "N/A",
            "forecast_period_end": previsao['ds'].max().strftime('%Y-%m-%d') if not previsao.empty else "N/A"
        }), 404 # Código de status HTTP 404 Not Found

    total_previsto_hoje = previsao_hoje['yhat1'].values[0]

    # 15. Analisando os 10 motoristas mais propensos a eventos
    top_10_list = []
    # Verifica se os dados necessários estão presentes e não vazios
    if dados is not None and not dados.empty and 'Motorista' in dados.columns and 'QUANTIDADE' in dados.columns and total_eventos is not None and total_eventos > 0 and not pd.isna(total_previsto_hoje):
        eventos_por_motorista = dados.groupby('Motorista')['QUANTIDADE'].sum().reset_index()
        top_10_motoristas = eventos_por_motorista.sort_values(by='QUANTIDADE', ascending=False) # Não filtra com head(10) ainda

        # NOVO: FILTRAR MOTORISTAS DESLIGADOS
        if motoristas_desligados_list: # Verifica se a lista de desligados não está vazia
            top_10_motoristas = top_10_motoristas[~top_10_motoristas['Motorista'].isin(motoristas_desligados_list)]
            print(f"INFO: Motoristas desligados filtrados do top motoristas geral.")
        else:
            print("INFO: Nenhum motorista desligado para filtrar do top motoristas geral.")

        # Agora aplica o head(10) após o filtro
        top_10_motoristas = top_10_motoristas.head(10)

        # Evita divisão por zero ou cálculo com NaN
        if total_eventos > 0 and not pd.isna(total_previsto_hoje):
            top_10_motoristas['Probabilidade'] = (top_10_motoristas['QUANTIDADE'] / total_eventos) * total_previsto_hoje
        else:
            top_10_motoristas['Probabilidade'] = 0.0

        top_10_list = top_10_motoristas[['Motorista', 'Probabilidade']].to_dict('records')
    else:
        print("AVISO: Não foi possível calcular o Top 10 Motoristas (dados ausentes, total de eventos zero, ou total previsto inválido).")


    # 17. Analisando os 5 motoristas mais propensos a um tipo específico de evento
    eventos_especificos = ['Excesso de Velocidade', 'Fadiga', 'Curva Brusca']
    eventos_probabilidades = {}

    for evento_nome in eventos_especificos:
        # Adiciona verificação para as colunas essenciais
        if dados is None or dados.empty or 'Nome' not in dados.columns or 'Motorista' not in dados.columns or 'QUANTIDADE' not in dados.columns:
            eventos_probabilidades[evento_nome] = {"error": "Dados necessários (colunas 'Nome', 'Motorista', 'QUANTIDADE') não encontrados ou dados vazios para eventos específicos. Verifique seu CSV."}
            continue

        dados_evento = dados[dados['Nome'] == evento_nome]

        if dados_evento.empty:
            eventos_probabilidades[evento_nome] = {"message": f"Nenhum dado histórico encontrado para o evento: {evento_nome}."}
            continue

        total_eventos_tipo = dados_evento['QUANTIDADE'].sum()
        eventos_por_motorista_evento = dados_evento.groupby('Motorista')['QUANTIDADE'].sum().reset_index()
        top_5_motoristas_evento = eventos_por_motorista_evento.sort_values(by='QUANTIDADE', ascending=False) # Não filtra com head(5) ainda

        # NOVO: FILTRAR MOTORISTAS DESLIGADOS PARA EVENTOS ESPECÍFICOS
        if motoristas_desligados_list:
            top_5_motoristas_evento = top_5_motoristas_evento[~top_5_motoristas_evento['Motorista'].isin(motoristas_desligados_list)]
            print(f"INFO: Motoristas desligados filtrados do top 5 de '{evento_nome}'.")
        else:
            print(f"INFO: Nenhum motorista desligado para filtrar do top 5 de '{evento_nome}'.")

        # Agora aplica o head(5) após o filtro
        top_5_motoristas_evento = top_5_motoristas_evento.head(5)


        if top_5_motoristas_evento.empty:
            eventos_probabilidades[evento_nome] = {"message": f"Nenhum motorista encontrado para o evento: {evento_nome} após filtro de desligados."}
            continue

        # Evita divisão por zero ou cálculo com NaN
        if total_eventos_tipo > 0 and not pd.isna(total_previsto_hoje):
            top_5_motoristas_evento['Probabilidade'] = (top_5_motoristas_evento['QUANTIDADE'] / total_eventos_tipo) * total_previsto_hoje
        else:
            top_5_motoristas_evento['Probabilidade'] = 0.0

        eventos_probabilidades[evento_nome] = top_5_motoristas_evento[['Motorista', 'Probabilidade']].to_dict('records')

    # NOVO: Analisando os 3 locais mais propensos a eventos
    top_3_localidades_list = []
    if dados is not None and not dados.empty and 'Localidade' in dados.columns and 'QUANTIDADE' in dados.columns and total_eventos is not None and total_eventos > 0 and not pd.isna(total_previsto_hoje):
        eventos_por_localidade = dados.groupby('Localidade')['QUANTIDADE'].sum().reset_index()
        top_3_localidades = eventos_por_localidade.sort_values(by='QUANTIDADE', ascending=False).head(3)

        if not top_3_localidades.empty:
            # Evita divisão por zero ou cálculo com NaN
            if total_eventos > 0 and not pd.isna(total_previsto_hoje):
                top_3_localidades['Probabilidade'] = (top_3_localidades['QUANTIDADE'] / total_eventos) * total_previsto_hoje
            else:
                top_3_localidades['Probabilidade'] = 0.0
            top_3_localidades_list = top_3_localidades[['Localidade', 'Probabilidade']].to_dict('records')
        else:
            print("AVISO: Nenhuma localidade encontrada para calcular o Top 3 Locais.")
    else:
        print("AVISO: Não foi possível calcular o Top 3 Locais (dados ausentes, coluna 'Localidade' inexistente, total de eventos zero, ou total previsto inválido).")


    # Retorna todos os dados como JSON
    return jsonify({
        "data_previsao": data_especifica.strftime('%Y-%m-%d'),
        "previsao_total_yhat1": float(total_previsto_hoje),
        "top_10_motoristas_geral": top_10_list,
        "probabilidade_eventos_especificos": eventos_probabilidades,
        "top_3_localidades": top_3_localidades_list
    })

if __name__ == '__main__':
    # Para rodar em ambiente de desenvolvimento
    app.run(debug=True, port=5000)