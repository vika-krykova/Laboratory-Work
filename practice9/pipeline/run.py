import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import recsys

def run_pipeline(dataset: str, output_dir: str):
    logging.info(f"Запуск пайплайна для датасета: {dataset}")
    
    sys.argv = [
        "recsys.py",
        "--dataset", dataset,
        "--path", f"data/{dataset}",
        "--model", "all",
        "--evaluate",
        "--output", output_dir
    ]
    
    try:
        recsys.main()
        logging.info("Пайплайн успешно завершен!")
    except Exception as e:
        logging.error(f"Ошибка в пайплайне: {e}")
        raise