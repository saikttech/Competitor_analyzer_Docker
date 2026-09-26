import os
import boto3
from pathlib import Path
from dotenv import load_dotenv
from botocore.client import Config

load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")

# PostgreSQL (ВАЖНО: 'db' - это имя сервиса в docker-compose.yml)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/competitors_db")

# Redis (ВАЖНО: 'redis' - это имя сервиса в docker-compose.yml)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Локальная папка для отчетов
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "./reports"))
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# S3 / MinIO (опционально)
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "reports")
S3_REGION = os.getenv("S3_REGION", "us-east-1")

s3_client = None
if S3_ENDPOINT_URL and S3_ACCESS_KEY:
    s3_client = boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name=S3_REGION,
        config=Config(signature_version='s3v4')
    )
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET_NAME)
    except Exception:
        try:
            s3_client.create_bucket(Bucket=S3_BUCKET_NAME)
        except Exception:
            pass