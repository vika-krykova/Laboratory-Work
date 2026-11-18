FROM apache/airflow:2.9.3-python3.11
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libatlas-base-dev \
    gfortran \
    cmake \
    && rm -rf /var/lib/apt/lists/*

USER airflow

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir --default-timeout=100 -r /requirements.txt