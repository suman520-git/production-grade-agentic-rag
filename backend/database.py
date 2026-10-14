import psycopg

from backend.config import settings


def get_connection():
    # Open a connection using the values from .env.
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        dbname=settings.postgres_db,
        connect_timeout=5
    )