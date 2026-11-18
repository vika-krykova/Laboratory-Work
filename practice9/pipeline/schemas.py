import pandera as pa
from pandera import Column, Check
import pandas as pd
import logging
from pathlib import Path

log = logging.getLogger(__name__)

schema = pa.DataFrameSchema({
    "userId": Column(int, coerce=True),
    "movieId": Column(int, coerce=True),
    "rating": Column(float, Check.in_range(0.5, 5.0), coerce=True),
    "timestamp": Column(int, coerce=True)
})

def validate_data(df: pd.DataFrame, quarantine_dir: str = "data/quarantine"):
    try:
        schema.validate(df, lazy=True)
        log.info(f"Валидация пройдена! Все {len(df)} строк корректны.")
        return df
    except pa.errors.SchemaErrors as exc:
        log.warning(f"Найдены битые данные! Отправляем в карантин...")
        
        Path(quarantine_dir).mkdir(parents=True, exist_ok=True)
        bad_rows = exc.failure_cases
        bad_rows.to_csv(f"{quarantine_dir}/bad_rows.csv", index=False)
        
        invalid_indices = bad_rows["index"].dropna().unique()
        clean_df = df.drop(index=invalid_indices)
        
        log.info(f"Успешно очищено. Осталось {len(clean_df)} строк.")
        return clean_df