from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from neuralprophet import NeuralProphet


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "basedadosseguranca.csv"
DISMISSED_DRIVERS_FILE = BASE_DIR / "motoristas_desligados.csv"
FORECAST_DAYS = int(os.getenv("FORECAST_DAYS", "45"))
RECENT_HISTORY_DAYS = int(os.getenv("RECENT_HISTORY_DAYS", "14"))
TOP_DRIVER_LIMIT = 10
TOP_LOCATION_LIMIT = 3
TOP_EVENT_LIMIT = 4
TOP_DRIVERS_PER_EVENT_LIMIT = 3


app = Flask(__name__)
CORS(app)


dados: pd.DataFrame | None = None
modelo: NeuralProphet | None = None
df_aggregated: pd.DataFrame | None = None
analytics_cache: dict[str, Any] = {}
motoristas_desligados_list: list[str] = []


def round_float(value: float | int | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def fill_text_column(series: pd.Series, fallback: str) -> pd.Series:
    mode = series.mode(dropna=True)
    replacement = mode.iloc[0] if not mode.empty else fallback
    return series.fillna(replacement)


def load_dismissed_drivers() -> list[str]:
    if not DISMISSED_DRIVERS_FILE.exists():
        logger.warning("Arquivo de motoristas desligados nao encontrado.")
        return []

    desligados_df = pd.read_csv(DISMISSED_DRIVERS_FILE, delimiter=";")
    first_column = desligados_df.columns[0]
    drivers = (
        desligados_df[first_column]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda values: values.ne("")]
        .tolist()
    )
    logger.info("%s motoristas desligados carregados para filtro.", len(drivers))
    return drivers


def prepare_dataset(raw_df: pd.DataFrame) -> pd.DataFrame:
    if "QUANTIDADE" not in raw_df.columns:
        raise ValueError("Coluna 'QUANTIDADE' nao encontrada no CSV.")
    if "Data" not in raw_df.columns:
        raise ValueError("Coluna 'Data' nao encontrada no CSV.")

    cleaned = raw_df.copy()

    for column, fallback in {
        "Motorista": "Nao informado",
        "Localidade": "Nao informada",
        "Tipo de Evento": "Nao informado",
        "Criticidade": "Nao informada",
    }.items():
        if column in cleaned.columns:
            cleaned[column] = fill_text_column(cleaned[column], fallback)

    cleaned["QUANTIDADE"] = pd.to_numeric(cleaned["QUANTIDADE"], errors="coerce").fillna(0)
    cleaned["Data"] = pd.to_datetime(cleaned["Data"], format="mixed", dayfirst=True, errors="coerce")
    cleaned = cleaned.dropna(subset=["Data"]).copy()

    if cleaned.empty:
        raise ValueError("Nenhum dado valido restou apos a limpeza da coluna 'Data'.")

    return cleaned


def build_ranked_items(
    grouped_df: pd.DataFrame,
    label_column: str,
    total_eventos_historicos: float,
    previsao_total: float,
    output_label: str | None = None,
) -> list[dict[str, Any]]:
    if grouped_df.empty or total_eventos_historicos <= 0:
        return []

    label_key = output_label or label_column
    ranked_items: list[dict[str, Any]] = []

    for _, row in grouped_df.iterrows():
        volume_historico = float(row["QUANTIDADE"])
        participacao = (volume_historico / total_eventos_historicos) * 100
        eventos_esperados = (volume_historico / total_eventos_historicos) * previsao_total

        ranked_items.append(
            {
                label_key: row[label_column],
                "VolumeHistorico": int(volume_historico),
                "Probabilidade": round_float(participacao),
                "ParticipacaoPercentual": round_float(participacao),
                "EventosEsperados": round_float(eventos_esperados),
            }
        )

    return ranked_items


def build_event_specific_probabilities(
    source_df: pd.DataFrame,
    event_totals: pd.DataFrame,
    previsao_total: float,
    total_eventos_historicos: float,
    dismissed_drivers: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if source_df.empty or event_totals.empty or total_eventos_historicos <= 0:
        return {}

    filtered_source = source_df.copy()
    if dismissed_drivers and "Motorista" in filtered_source.columns:
        filtered_source = filtered_source[
            ~filtered_source["Motorista"].isin(dismissed_drivers)
        ].copy()

    event_driver_totals = (
        filtered_source.groupby(["Tipo de Evento", "Motorista"], as_index=False)["QUANTIDADE"]
        .sum()
        .sort_values(["Tipo de Evento", "QUANTIDADE"], ascending=[True, False])
    )

    event_volume_lookup = dict(
        zip(event_totals["Tipo de Evento"], event_totals["QUANTIDADE"], strict=False)
    )

    response: dict[str, list[dict[str, Any]]] = {}

    for event_name in event_totals["Tipo de Evento"].tolist():
        event_volume = float(event_volume_lookup.get(event_name, 0))
        if event_volume <= 0:
            response[event_name] = []
            continue

        event_expected_total = (event_volume / total_eventos_historicos) * previsao_total
        top_event_drivers = event_driver_totals[
            event_driver_totals["Tipo de Evento"] == event_name
        ].head(TOP_DRIVERS_PER_EVENT_LIMIT)

        response[event_name] = [
            {
                "Motorista": row["Motorista"],
                "VolumeHistorico": int(row["QUANTIDADE"]),
                "Probabilidade": round_float((row["QUANTIDADE"] / event_volume) * 100),
                "ParticipacaoNoEventoPercentual": round_float(
                    (row["QUANTIDADE"] / event_volume) * 100
                ),
                "EventosEsperados": round_float(
                    (row["QUANTIDADE"] / event_volume) * event_expected_total
                ),
            }
            for _, row in top_event_drivers.iterrows()
        ]

    return response


def build_analytics(source_df: pd.DataFrame) -> dict[str, Any]:
    aggregated = (
        source_df.groupby("Data", as_index=False)["QUANTIDADE"]
        .sum()
        .sort_values("Data")
        .reset_index(drop=True)
    )

    driver_totals = (
        source_df.groupby("Motorista", as_index=False)["QUANTIDADE"]
        .sum()
        .sort_values("QUANTIDADE", ascending=False)
        .reset_index(drop=True)
    )
    if motoristas_desligados_list:
        driver_totals = driver_totals[
            ~driver_totals["Motorista"].isin(motoristas_desligados_list)
        ].reset_index(drop=True)

    location_totals = (
        source_df.groupby("Localidade", as_index=False)["QUANTIDADE"]
        .sum()
        .sort_values("QUANTIDADE", ascending=False)
        .reset_index(drop=True)
    )
    event_totals = (
        source_df.groupby("Tipo de Evento", as_index=False)["QUANTIDADE"]
        .sum()
        .sort_values("QUANTIDADE", ascending=False)
        .reset_index(drop=True)
    )

    total_eventos_historicos = float(source_df["QUANTIDADE"].sum())
    recent_history = aggregated.tail(RECENT_HISTORY_DAYS).copy()

    return {
        "aggregated": aggregated,
        "driver_totals": driver_totals,
        "location_totals": location_totals,
        "event_totals": event_totals,
        "total_eventos_historicos": total_eventos_historicos,
        "media_diaria_historica": float(aggregated["QUANTIDADE"].mean()),
        "pico_diario_historico": float(aggregated["QUANTIDADE"].max()),
        "data_inicio": aggregated["Data"].min().strftime("%Y-%m-%d"),
        "data_fim": aggregated["Data"].max().strftime("%Y-%m-%d"),
        "total_registros": int(len(source_df)),
        "motoristas_monitorados": int(source_df["Motorista"].nunique()),
        "localidades_monitoradas": int(source_df["Localidade"].nunique()),
        "tipos_evento_monitorados": int(source_df["Tipo de Evento"].nunique()),
        "ultima_atualizacao_arquivo": pd.Timestamp(DATA_FILE.stat().st_mtime, unit="s")
        .tz_localize("UTC")
        .tz_convert("America/Sao_Paulo")
        .strftime("%Y-%m-%d %H:%M"),
        "serie_historica_recente": [
            {
                "data": row.Data.strftime("%Y-%m-%d"),
                "total": int(row.QUANTIDADE),
            }
            for row in recent_history.itertuples(index=False)
        ],
    }


def build_risk_summary(
    previsao_total: float,
    top_drivers: list[dict[str, Any]],
    top_locations: list[dict[str, Any]],
    top_events: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    media_diaria = analytics_cache["media_diaria_historica"]
    pico_historico = analytics_cache["pico_diario_historico"]
    variacao_media = ((previsao_total - media_diaria) / media_diaria * 100) if media_diaria else 0
    indice_risco = (previsao_total / media_diaria) if media_diaria else 0

    if indice_risco >= 1.2:
        nivel_risco = "alto"
    elif indice_risco >= 0.9:
        nivel_risco = "moderado"
    else:
        nivel_risco = "controlado"

    principal_motorista = top_drivers[0] if top_drivers else None
    principal_localidade = top_locations[0] if top_locations else None
    principal_evento = top_events[0] if top_events else None

    insights = [
        (
            f"Cenario {nivel_risco}: a previsao indica {round_float(previsao_total)} eventos "
            f"para a data selecionada, com variacao de {round_float(variacao_media)}% versus a media diaria."
        ),
    ]

    if principal_motorista:
        insights.append(
            f"Motorista prioritario para acompanhamento: {principal_motorista['Motorista']} "
            f"({principal_motorista['ParticipacaoPercentual']}% do historico, "
            f"{principal_motorista['EventosEsperados']} eventos esperados)."
        )
    if principal_localidade:
        insights.append(
            f"Hotspot operacional: {principal_localidade['Localidade']} concentra "
            f"{principal_localidade['ParticipacaoPercentual']}% dos eventos historicos mapeados."
        )
    if principal_evento:
        insights.append(
            f"O tipo de evento com maior peso atual e {principal_evento['TipoEvento']}, "
            f"com {principal_evento['EventosEsperados']} ocorrencias esperadas."
        )

    return (
        {
            "nivel_risco": nivel_risco,
            "indice_risco_relativo": round_float(indice_risco, 3),
            "variacao_media_percentual": round_float(variacao_media),
            "media_diaria_historica": round_float(media_diaria),
            "pico_diario_historico": round_float(pico_historico),
            "motorista_prioritario": principal_motorista["Motorista"] if principal_motorista else None,
            "localidade_critica": principal_localidade["Localidade"] if principal_localidade else None,
            "tipo_evento_lider": principal_evento["TipoEvento"] if principal_evento else None,
        },
        insights,
    )


def load_and_train_model() -> None:
    global dados, modelo, df_aggregated, analytics_cache, motoristas_desligados_list

    logger.info("Iniciando carga de dados e treinamento do modelo.")

    if not DATA_FILE.exists():
        logger.error("Arquivo %s nao encontrado.", DATA_FILE.name)
        sys.exit(1)

    raw_df = pd.read_csv(DATA_FILE, delimiter=";")
    motoristas_desligados_list = load_dismissed_drivers()
    dados = prepare_dataset(raw_df)
    analytics_cache = build_analytics(dados)
    df_aggregated = analytics_cache["aggregated"].copy()

    treino_df = df_aggregated.rename(columns={"Data": "ds", "QUANTIDADE": "y"})
    modelo = NeuralProphet()
    modelo.fit(treino_df, freq="D")

    logger.info(
        "Modelo treinado com sucesso. %s registros carregados de %s ate %s.",
        analytics_cache["total_registros"],
        analytics_cache["data_inicio"],
        analytics_cache["data_fim"],
    )


def parse_requested_date(raw_date: str | None) -> tuple[pd.Timestamp | None, str | None]:
    if not raw_date:
        default_date = pd.Timestamp.now().normalize() + pd.Timedelta(days=1)
        return default_date, None

    try:
        parsed_date = pd.to_datetime(raw_date, format="%Y-%m-%d", errors="raise")
        return parsed_date.normalize(), None
    except (TypeError, ValueError):
        return None, "Parametro 'date' invalido. Use o formato YYYY-MM-DD."


@app.route("/health", methods=["GET"])
def healthcheck():
    historical_end = analytics_cache.get("data_fim")
    suggested_prediction_date = None
    if historical_end:
        suggested_prediction_date = (
            pd.to_datetime(historical_end) + pd.Timedelta(days=1)
        ).strftime("%Y-%m-%d")

    return jsonify(
        {
            "status": "ok" if modelo is not None and df_aggregated is not None else "degraded",
            "model_ready": modelo is not None,
            "records_loaded": analytics_cache.get("total_registros", 0),
            "historical_window": {
                "start": analytics_cache.get("data_inicio"),
                "end": analytics_cache.get("data_fim"),
            },
            "suggested_prediction_date": suggested_prediction_date,
            "forecast_days": FORECAST_DAYS,
        }
    )


@app.route("/predict", methods=["GET"])
def get_prediction():
    requested_date_raw = request.args.get("date")
    requested_date, parse_error = parse_requested_date(requested_date_raw)

    if parse_error:
        return jsonify({"error": parse_error, "requested_date": requested_date_raw}), 400

    if modelo is None or df_aggregated is None or dados is None:
        return (
            jsonify(
                {
                    "error": "O modelo ainda nao esta pronto para gerar previsoes.",
                    "requested_date": requested_date.strftime("%Y-%m-%d") if requested_date else None,
                }
            ),
            500,
        )

    treino_df = df_aggregated.rename(columns={"Data": "ds", "QUANTIDADE": "y"})

    try:
        futuro = modelo.make_future_dataframe(df=treino_df, periods=FORECAST_DAYS)
        previsao = modelo.predict(futuro)
    except Exception as exc:
        logger.exception("Erro ao gerar previsao.")
        return jsonify({"error": f"Erro ao gerar previsao: {exc}"}), 500

    forecast_start_ts = df_aggregated["Data"].max() + pd.Timedelta(days=1)
    forecast_end_ts = forecast_start_ts + pd.Timedelta(days=FORECAST_DAYS - 1)
    previsao_futura = previsao[
        (previsao["ds"] >= forecast_start_ts) & (previsao["ds"] <= forecast_end_ts)
    ].copy()

    forecast_start = forecast_start_ts.strftime("%Y-%m-%d")
    forecast_end = forecast_end_ts.strftime("%Y-%m-%d")

    previsao_selecionada = previsao_futura[
        previsao_futura["ds"].dt.date == requested_date.date()
    ]
    if previsao_selecionada.empty:
        return (
            jsonify(
                {
                    "error": "Data fora do intervalo de previsao.",
                    "requested_date": requested_date.strftime("%Y-%m-%d"),
                    "forecast_period_start": forecast_start,
                    "forecast_period_end": forecast_end,
                }
            ),
            404,
        )

    previsao_total = max(float(previsao_selecionada["yhat1"].iloc[0]), 0.0)
    total_eventos_historicos = analytics_cache["total_eventos_historicos"]

    top_drivers_df = analytics_cache["driver_totals"].head(TOP_DRIVER_LIMIT)
    top_locations_df = analytics_cache["location_totals"].head(TOP_LOCATION_LIMIT)
    top_events_df = analytics_cache["event_totals"].head(TOP_EVENT_LIMIT)

    top_drivers = build_ranked_items(
        grouped_df=top_drivers_df,
        label_column="Motorista",
        total_eventos_historicos=total_eventos_historicos,
        previsao_total=previsao_total,
    )
    top_locations = build_ranked_items(
        grouped_df=top_locations_df,
        label_column="Localidade",
        total_eventos_historicos=total_eventos_historicos,
        previsao_total=previsao_total,
    )
    top_events = build_ranked_items(
        grouped_df=top_events_df,
        label_column="Tipo de Evento",
        total_eventos_historicos=total_eventos_historicos,
        previsao_total=previsao_total,
        output_label="TipoEvento",
    )
    probabilidade_eventos_especificos = build_event_specific_probabilities(
        source_df=dados,
        event_totals=top_events_df,
        previsao_total=previsao_total,
        total_eventos_historicos=total_eventos_historicos,
        dismissed_drivers=motoristas_desligados_list,
    )

    resumo_executivo, insights_prioritarios = build_risk_summary(
        previsao_total=previsao_total,
        top_drivers=top_drivers,
        top_locations=top_locations,
        top_events=top_events,
    )

    return jsonify(
        {
            "data_previsao": requested_date.strftime("%Y-%m-%d"),
            "previsao_total_yhat1": round_float(previsao_total),
            "forecast_period_start": forecast_start,
            "forecast_period_end": forecast_end,
            "top_10_motoristas_geral": top_drivers,
            "top_3_localidades": top_locations,
            "top_tipos_evento": top_events,
            "probabilidade_eventos_especificos": probabilidade_eventos_especificos,
            "serie_historica_recente": analytics_cache["serie_historica_recente"],
            "resumo_executivo": resumo_executivo,
            "insights_prioritarios": insights_prioritarios,
            "dataset_contexto": {
                "total_registros": analytics_cache["total_registros"],
                "total_eventos_historicos": int(total_eventos_historicos),
                "motoristas_monitorados": analytics_cache["motoristas_monitorados"],
                "localidades_monitoradas": analytics_cache["localidades_monitoradas"],
                "tipos_evento_monitorados": analytics_cache["tipos_evento_monitorados"],
                "janela_historica_inicio": analytics_cache["data_inicio"],
                "janela_historica_fim": analytics_cache["data_fim"],
                "ultima_atualizacao_arquivo": analytics_cache["ultima_atualizacao_arquivo"],
                "motoristas_desligados_filtrados": len(motoristas_desligados_list),
            },
            "meta": {
                "backend": "flask-neuralprophet",
                "forecast_days": FORECAST_DAYS,
                "recent_history_days": RECENT_HISTORY_DAYS,
            },
        }
    )


if __name__ == "__main__":
    logger.info("Inicializando API de previsao.")
    load_and_train_model()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
else:
    load_and_train_model()
