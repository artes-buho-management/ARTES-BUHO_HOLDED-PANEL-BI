from __future__ import annotations

import pandas as pd

from data_processing import clean_and_prepare


def test_clean_and_prepare_normalizes_accented_columns():
    df = pd.DataFrame(
        {
            "Fecha Emisión": ["2026-01-01"],
            "Cliente Ñ": ["Empresa A"],
            "Importe €": ["1.234,56"],
        }
    )
    processed = clean_and_prepare(df)
    cols = set(processed.dataframe.columns)

    assert "fecha_emision" in cols
    assert "cliente_n" in cols
    assert "importe" in cols

