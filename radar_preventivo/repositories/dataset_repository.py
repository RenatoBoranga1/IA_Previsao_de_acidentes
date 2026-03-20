from __future__ import annotations

from pathlib import Path

import pandas as pd

from radar_preventivo.config import AppSettings


class CsvDatasetRepository:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def load_events(self) -> pd.DataFrame:
        if not self.settings.data_file.exists():
            raise FileNotFoundError(f"Arquivo de dados nao encontrado: {self.settings.data_file}")
        return pd.read_csv(self.settings.data_file, delimiter=";")

    def load_dismissed_drivers(self) -> list[str]:
        file_path: Path = self.settings.dismissed_drivers_file
        if not file_path.exists():
            return []

        dismissed_df = pd.read_csv(file_path, delimiter=";")
        first_column = dismissed_df.columns[0]
        return (
            dismissed_df[first_column]
            .dropna()
            .astype(str)
            .str.strip()
            .loc[lambda values: values.ne("")]
            .tolist()
        )

    def prepare_events(self, raw_df: pd.DataFrame) -> pd.DataFrame:
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
                cleaned[column] = self._fill_text_column(cleaned[column], fallback)

        cleaned["QUANTIDADE"] = pd.to_numeric(cleaned["QUANTIDADE"], errors="coerce").fillna(0)
        cleaned["Data"] = pd.to_datetime(cleaned["Data"], format="mixed", dayfirst=True, errors="coerce")
        cleaned = cleaned.dropna(subset=["Data"]).copy()

        if cleaned.empty:
            raise ValueError("Nenhum dado valido restou apos a limpeza da coluna 'Data'.")

        return cleaned

    @staticmethod
    def _fill_text_column(series: pd.Series, fallback: str) -> pd.Series:
        mode = series.mode(dropna=True)
        replacement = mode.iloc[0] if not mode.empty else fallback
        return series.fillna(replacement)
