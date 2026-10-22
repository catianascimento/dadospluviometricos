import os

import psycopg2
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


print("Tentando conectar ao PostgreSQL...")

try:

    conn = psycopg2.connect(
        DATABASE_URL
    )

    cursor = conn.cursor()

    cursor.execute(
        "SELECT version();"
    )

    version = cursor.fetchone()[0]

    print("Conexão realizada com sucesso!")
    print()
    print("PostgreSQL:")
    print(version)

    cursor.close()
    conn.close()

except Exception as e:

    print("Erro ao conectar:")
    print(e)