import os
import pandas as pd
from sqlalchemy import create_engine, text
import logging

log = logging.getLogger(__name__)

def load_metrics_to_db(metrics_csv_path: str):
    db_url = os.getenv("DATABASE_URL", "postgresql://airflow:airflow@postgres/airflow")
    engine = create_engine(db_url)
    
    df = pd.read_csv(metrics_csv_path)
    
    df = df.rename(columns={'K': 'k'})
    df['k'] = df['k'].astype(int)
    df['value'] = df['value'].fillna(0.0).astype(float)
    df['ci95'] = df['ci95'].fillna(0.0).astype(float)
    df['n_users'] = df['n_users'].fillna(0).astype(int)
    
    log.info(f"Загружаем {len(df)} строк метрик в базу...")
    
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS model_metrics (
                dataset VARCHAR, model VARCHAR, segment VARCHAR, 
                metric VARCHAR, k INTEGER, value FLOAT, 
                ci95 FLOAT, n_users INTEGER,
                PRIMARY KEY (dataset, model, segment, metric, k)
            )
        """))
        
    records = df[['dataset', 'model', 'segment', 'metric', 'k', 'value', 'ci95', 'n_users']].to_dict(orient='records')
    
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO model_metrics (dataset, model, segment, metric, k, value, ci95, n_users)
            VALUES (:dataset, :model, :segment, :metric, :k, :value, :ci95, :n_users)
            ON CONFLICT (dataset, model, segment, metric, k) 
            DO UPDATE SET 
                value = EXCLUDED.value,
                ci95 = EXCLUDED.ci95,
                n_users = EXCLUDED.n_users;
        """), records)
    
    log.info("Данные успешно сохранены в БД (UPSERT выполнен).")