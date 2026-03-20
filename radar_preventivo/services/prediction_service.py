from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from radar_preventivo.config import AppSettings
from radar_preventivo.repositories.dataset_repository import CsvDatasetRepository


logger = logging.getLogger(__name__)


TOP_DRIVER_LIMIT = 10
TOP_LOCATION_LIMIT = 3
TOP_EVENT_LIMIT = 4
TOP_DRIVERS_PER_EVENT_LIMIT = 3


@dataclass(slots=True)
class DatasetBundle:
    dados: pd.DataFrame
    dados_aggregated: pd.DataFrame
    dismissed_drivers: list[str]
    analytics_cache: dict[str, Any]


class MockPredictorBackend:
    backend_name = "mock-moving-average"

    def forecast(self, training_df: pd.DataFrame, periods: int) -> pd.DataFrame:
        recent_window = training_df["y"].tail(7)
        baseline = float(recent_window.mean()) if not recent_window.empty else 0.0
        recent_diff = training_df["y"].diff().tail(7)
        slope = float(recent_diff.mean()) if not recent_diff.dropna().empty else 0.0

        forecast_dates = pd.date_range(
            start=training_df["ds"].max() + pd.Timedelta(days=1),
            periods=periods,
            freq="D",
        )
        predictions = []
        for step, forecast_date in enumerate(forecast_dates, start=1):
            predictions.append(
                {
                    "ds": forecast_date,
                    "yhat1": max(round(baseline + (slope * 0.15 * step), 2), 0.0),
                }
            )

        return pd.DataFrame(predictions)


class NeuralProphetPredictorBackend:
    backend_name = "flask-neuralprophet"

    def __init__(self) -> None:
        self._model = None
        self._training_signature: tuple[pd.Timestamp, int] | None = None

    def forecast(self, training_df: pd.DataFrame, periods: int) -> pd.DataFrame:
        signature = (training_df["ds"].max(), len(training_df))
        if self._model is None or self._training_signature != signature:
            from neuralprophet import NeuralProphet

            self._model = NeuralProphet()
            self._model.fit(training_df, freq="D")
            self._training_signature = signature

        future_df = self._model.make_future_dataframe(df=training_df, periods=periods)
        predictions = self._model.predict(future_df)
        return predictions[predictions["ds"] > training_df["ds"].max()][["ds", "yhat1"]].copy()


class PredictionService:
    def __init__(self, settings: AppSettings, dataset_repository: CsvDatasetRepository) -> None:
        self.settings = settings
        self.dataset_repository = dataset_repository
        self.dataset_bundle: DatasetBundle | None = None
        self.predictor_backend = self._build_predictor_backend()

    def initialize(self) -> None:
        raw_df = self.dataset_repository.load_events()
        dismissed_drivers = self.dataset_repository.load_dismissed_drivers()
        dados = self.dataset_repository.prepare_events(raw_df)
        analytics_cache = self._build_analytics(dados, dismissed_drivers)
        dados_aggregated = analytics_cache["aggregated"].copy()

        self.dataset_bundle = DatasetBundle(
            dados=dados,
            dados_aggregated=dados_aggregated,
            dismissed_drivers=dismissed_drivers,
            analytics_cache=analytics_cache,
        )
        logger.info(
            "Base carregada com sucesso. %s registros entre %s e %s.",
            analytics_cache["total_registros"],
            analytics_cache["data_inicio"],
            analytics_cache["data_fim"],
        )

    def health_payload(self) -> dict[str, Any]:
        bundle = self._require_dataset_bundle()
        historical_end = bundle.analytics_cache["data_fim"]
        suggested_prediction_date = (
            pd.to_datetime(historical_end) + pd.Timedelta(days=1)
        ).strftime("%Y-%m-%d")

        return {
            "status": "ok",
            "model_ready": True,
            "records_loaded": bundle.analytics_cache["total_registros"],
            "historical_window": {
                "start": bundle.analytics_cache["data_inicio"],
                "end": bundle.analytics_cache["data_fim"],
            },
            "suggested_prediction_date": self.settings.bootstrap_prediction_date
            or suggested_prediction_date,
            "forecast_days": self.settings.forecast_days,
            "predictor_mode": self.settings.predictor_mode,
            "backend_name": self.predictor_backend.backend_name,
        }

    def predict_for_date(self, requested_date_raw: str | None) -> dict[str, Any]:
        bundle = self._require_dataset_bundle()
        requested_date, parse_error = self._parse_requested_date(requested_date_raw)

        if parse_error:
            raise ValueError(parse_error)

        training_df = bundle.dados_aggregated.rename(columns={"Data": "ds", "QUANTIDADE": "y"})
        future_predictions = self.predictor_backend.forecast(
            training_df=training_df,
            periods=self.settings.forecast_days,
        )

        forecast_start_ts = future_predictions["ds"].min()
        forecast_end_ts = future_predictions["ds"].max()
        forecast_start = forecast_start_ts.strftime("%Y-%m-%d")
        forecast_end = forecast_end_ts.strftime("%Y-%m-%d")

        prediction_row = future_predictions[future_predictions["ds"].dt.date == requested_date.date()]
        if prediction_row.empty:
            raise LookupError(
                {
                    "error": "Data fora do intervalo de previsao.",
                    "requested_date": requested_date.strftime("%Y-%m-%d"),
                    "forecast_period_start": forecast_start,
                    "forecast_period_end": forecast_end,
                }
            )

        previsao_total = max(float(prediction_row["yhat1"].iloc[0]), 0.0)
        total_eventos_historicos = bundle.analytics_cache["total_eventos_historicos"]

        top_drivers_df = bundle.analytics_cache["driver_totals"].head(TOP_DRIVER_LIMIT)
        top_locations_df = bundle.analytics_cache["location_totals"].head(TOP_LOCATION_LIMIT)
        top_events_df = bundle.analytics_cache["event_totals"].head(TOP_EVENT_LIMIT)

        top_drivers = self._build_ranked_items(
            grouped_df=top_drivers_df,
            label_column="Motorista",
            total_eventos_historicos=total_eventos_historicos,
            previsao_total=previsao_total,
        )
        top_locations = self._build_ranked_items(
            grouped_df=top_locations_df,
            label_column="Localidade",
            total_eventos_historicos=total_eventos_historicos,
            previsao_total=previsao_total,
        )
        top_events = self._build_ranked_items(
            grouped_df=top_events_df,
            label_column="Tipo de Evento",
            total_eventos_historicos=total_eventos_historicos,
            previsao_total=previsao_total,
            output_label="TipoEvento",
        )
        event_breakdown = self._build_event_specific_probabilities(
            source_df=bundle.dados,
            event_totals=top_events_df,
            previsao_total=previsao_total,
            total_eventos_historicos=total_eventos_historicos,
            dismissed_drivers=bundle.dismissed_drivers,
        )
        resumo_executivo, insights_prioritarios = self._build_risk_summary(
            previsao_total=previsao_total,
            top_drivers=top_drivers,
            top_locations=top_locations,
            top_events=top_events,
            analytics_cache=bundle.analytics_cache,
        )

        return {
            "data_previsao": requested_date.strftime("%Y-%m-%d"),
            "previsao_total_yhat1": self._round_float(previsao_total),
            "forecast_period_start": forecast_start,
            "forecast_period_end": forecast_end,
            "top_10_motoristas_geral": top_drivers,
            "top_3_localidades": top_locations,
            "top_tipos_evento": top_events,
            "probabilidade_eventos_especificos": event_breakdown,
            "serie_historica_recente": bundle.analytics_cache["serie_historica_recente"],
            "resumo_executivo": resumo_executivo,
            "insights_prioritarios": insights_prioritarios,
            "dataset_contexto": {
                "total_registros": bundle.analytics_cache["total_registros"],
                "total_eventos_historicos": int(total_eventos_historicos),
                "motoristas_monitorados": bundle.analytics_cache["motoristas_monitorados"],
                "localidades_monitoradas": bundle.analytics_cache["localidades_monitoradas"],
                "tipos_evento_monitorados": bundle.analytics_cache["tipos_evento_monitorados"],
                "janela_historica_inicio": bundle.analytics_cache["data_inicio"],
                "janela_historica_fim": bundle.analytics_cache["data_fim"],
                "ultima_atualizacao_arquivo": bundle.analytics_cache["ultima_atualizacao_arquivo"],
                "motoristas_desligados_filtrados": len(bundle.dismissed_drivers),
            },
            "meta": {
                "backend": self.predictor_backend.backend_name,
                "forecast_days": self.settings.forecast_days,
                "recent_history_days": self.settings.recent_history_days,
                "predictor_mode": self.settings.predictor_mode,
            },
        }

    def _build_predictor_backend(self):
        if self.settings.predictor_mode == "mock":
            return MockPredictorBackend()
        return NeuralProphetPredictorBackend()

    def _require_dataset_bundle(self) -> DatasetBundle:
        if self.dataset_bundle is None:
            raise RuntimeError("A base ainda nao foi carregada.")
        return self.dataset_bundle

    def _parse_requested_date(self, raw_date: str | None) -> tuple[pd.Timestamp | None, str | None]:
        if raw_date:
            try:
                return pd.to_datetime(raw_date, format="%Y-%m-%d", errors="raise").normalize(), None
            except (TypeError, ValueError):
                return None, "Parametro 'date' invalido. Use o formato YYYY-MM-DD."

        bootstrap_date = self.settings.bootstrap_prediction_date
        if bootstrap_date:
            return pd.to_datetime(bootstrap_date, format="%Y-%m-%d", errors="raise").normalize(), None

        bundle = self._require_dataset_bundle()
        next_date = pd.to_datetime(bundle.analytics_cache["data_fim"]).normalize() + pd.Timedelta(days=1)
        return next_date, None

    def _build_analytics(self, source_df: pd.DataFrame, dismissed_drivers: list[str]) -> dict[str, Any]:
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
        if dismissed_drivers:
            driver_totals = driver_totals[
                ~driver_totals["Motorista"].isin(dismissed_drivers)
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
        recent_history = aggregated.tail(self.settings.recent_history_days).copy()

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
            "ultima_atualizacao_arquivo": pd.Timestamp(
                self.settings.data_file.stat().st_mtime, unit="s"
            )
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

    def _build_ranked_items(
        self,
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
                    "Probabilidade": self._round_float(participacao),
                    "ParticipacaoPercentual": self._round_float(participacao),
                    "EventosEsperados": self._round_float(eventos_esperados),
                }
            )

        return ranked_items

    def _build_event_specific_probabilities(
        self,
        source_df: pd.DataFrame,
        event_totals: pd.DataFrame,
        previsao_total: float,
        total_eventos_historicos: float,
        dismissed_drivers: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        if source_df.empty or event_totals.empty or total_eventos_historicos <= 0:
            return {}

        filtered_source = source_df.copy()
        if dismissed_drivers:
            filtered_source = filtered_source[
                ~filtered_source["Motorista"].isin(dismissed_drivers)
            ].copy()

        event_driver_totals = (
            filtered_source.groupby(["Tipo de Evento", "Motorista"], as_index=False)["QUANTIDADE"]
            .sum()
            .sort_values(["Tipo de Evento", "QUANTIDADE"], ascending=[True, False])
        )

        event_volume_lookup = {
            row["Tipo de Evento"]: row["QUANTIDADE"] for _, row in event_totals.iterrows()
        }
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
                    "Probabilidade": self._round_float((row["QUANTIDADE"] / event_volume) * 100),
                    "ParticipacaoNoEventoPercentual": self._round_float(
                        (row["QUANTIDADE"] / event_volume) * 100
                    ),
                    "EventosEsperados": self._round_float(
                        (row["QUANTIDADE"] / event_volume) * event_expected_total
                    ),
                }
                for _, row in top_event_drivers.iterrows()
            ]

        return response

    def _build_risk_summary(
        self,
        previsao_total: float,
        top_drivers: list[dict[str, Any]],
        top_locations: list[dict[str, Any]],
        top_events: list[dict[str, Any]],
        analytics_cache: dict[str, Any],
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
                f"Cenario {nivel_risco}: a previsao indica {self._round_float(previsao_total)} eventos "
                f"para a data selecionada, com variacao de {self._round_float(variacao_media)}% versus a media diaria."
            )
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
                "indice_risco_relativo": self._round_float(indice_risco, 3),
                "variacao_media_percentual": self._round_float(variacao_media),
                "media_diaria_historica": self._round_float(media_diaria),
                "pico_diario_historico": self._round_float(pico_historico),
                "motorista_prioritario": principal_motorista["Motorista"] if principal_motorista else None,
                "localidade_critica": principal_localidade["Localidade"] if principal_localidade else None,
                "tipo_evento_lider": principal_evento["TipoEvento"] if principal_evento else None,
            },
            insights,
        )

    @staticmethod
    def _round_float(value: float | int | None, digits: int = 2) -> float | None:
        if value is None:
            return None
        return round(float(value), digits)
