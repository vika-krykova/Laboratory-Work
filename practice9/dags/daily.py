from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import sys
import os
import pandas as pd
import numpy as np

# Добавляем пути, чтобы Airflow видел наши модули
sys.path.append('/opt/airflow/pipeline')
sys.path.append('/opt/airflow')

from pipeline.schemas import validate_data
from pipeline.load import load_metrics_to_db

default_args = {
    'owner': 'vika',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=1),
}

def collect_task():
    print("Шаг 1: Сбор данных...")
    print("Данные успешно собраны.")

def validate_task():
    print("Шаг 2: Валидация данных и карантин...")
    
    os.makedirs('/tmp/ml-data', exist_ok=True)
    np.random.seed(42)
    
    df_ratings = pd.DataFrame({
        "userId": np.random.randint(1, 11, 150),
        "movieId": np.random.randint(1, 21, 150),
        
        # =================================================================
        # 🔴 ДЛЯ ТЕСТА 1 (ОШИБКА ВАЛИДАЦИИ): 
        # Раскомментируй строку ниже (с плохими данными) 
        # и закомментируй строку с нормальными данными.
        # =================================================================
        #"rating": ["плохая_оценка"] * 150,  # <--- ПЛОХИЕ ДАННЫЕ
        "rating": np.random.uniform(1.0, 5.0, 150),  # <--- ХОРОШИЕ ДАННЫЕ
        # =================================================================
        
        "timestamp": np.arange(150)
    })
    df_ratings = df_ratings.drop_duplicates(subset=['userId', 'movieId'])
    
    df_movies = pd.DataFrame({
        "movieId": range(1, 21),
        "title": [f"Movie {i}" for i in range(1, 21)],
        "genres": ["Action|Sci-Fi"] * 10 + ["Comedy|Romance"] * 10
    })
    
    clean_df = validate_data(df_ratings)
    
    # =================================================================
    # 🔴 ДЛЯ ТЕСТА 1: Эта проверка заставит задачу покраснеть, 
    # если все данные оказались плохими и ушли в карантин.
    # =================================================================
    if len(clean_df) == 0:
        raise ValueError("Критическая ошибка: 100% данных ушли в карантин! Пайплайн остановлен.")
    # =================================================================
    
    clean_df.to_csv('/tmp/ml-data/ratings.csv', index=False)
    df_movies.to_csv('/tmp/ml-data/movies.csv', index=False)
    print(f"Валидация пройдена. Сохранено {len(clean_df)} строк.")

with DAG(
    'recsys_daily_pipeline',
    default_args=default_args,
    description='Пайплайн рекомендательной системы',
    schedule_interval='0 3 * * *',
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=['recsys'],
) as dag:

    t1_collect = PythonOperator(
        task_id='collect_data',
        python_callable=collect_task,
    )

    t2_validate = PythonOperator(
        task_id='validate_and_quarantine',
        python_callable=validate_task,
    )

    # Если будешь делать ТЕСТ 3 (Ретраи), раскомментируй execution_timeout ниже
    t3_train = BashOperator(
        task_id='train_models',
        bash_command='cd /opt/airflow && python recsys.py --dataset movielens --path /tmp/ml-data --model all --k 5 --evaluate --output /tmp/results --min-interactions 1 --min-history 1 --n-test 1',
     #   execution_timeout=timedelta(seconds=1)
    )

    t4_load = PythonOperator(
        task_id='load_to_db',
        python_callable=load_metrics_to_db,
        op_kwargs={'metrics_csv_path': '/tmp/results/metrics.csv'}
    )

    t1_collect >> t2_validate >> t3_train >> t4_load