import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Criar tabela de estações
cursor.execute("""
    CREATE TABLE IF NOT EXISTS estacoes (
        id SERIAL PRIMARY KEY,
        codigo INTEGER NOT NULL UNIQUE,
        nome_estacao TEXT NOT NULL
    );
""")

# Criar tabela de precipitação
cursor.execute("""
    CREATE TABLE IF NOT EXISTS precipitacao (
        id SERIAL PRIMARY KEY,
        estacao_id INTEGER NOT NULL,
        data DATE NOT NULL,
        precipitacao_mm NUMERIC(10, 2),

        FOREIGN KEY (estacao_id)
            REFERENCES estacoes(id),

        UNIQUE (estacao_id, data)
    );
""")

# Inserir estação de teste
cursor.execute("""
    INSERT INTO estacoes (
        codigo,
        nome_estacao
    )
    VALUES (%s, %s)

    ON CONFLICT (codigo)
    DO UPDATE SET
        nome_estacao = EXCLUDED.nome_estacao

    RETURNING id;
""", (
    1155,
    "Estação de Teste"
))

estacao_id = cursor.fetchone()[0]

# Inserir precipitação de teste
cursor.execute("""
    INSERT INTO precipitacao (
        estacao_id,
        data,
        precipitacao_mm
    )
    VALUES (%s, %s, %s)

    ON CONFLICT (estacao_id, data)
    DO UPDATE SET
        precipitacao_mm = EXCLUDED.precipitacao_mm;
""", (
    estacao_id,
    "2026-09-29",
    12.50
))

conn.commit()

# Consultar
cursor.execute("""
    SELECT
        e.codigo,
        e.nome_estacao,
        p.data,
        p.precipitacao_mm
    FROM precipitacao p
    JOIN estacoes e
        ON e.id = p.estacao_id
    ORDER BY p.data;
""")

resultados = cursor.fetchall()

print("\nDados encontrados:\n")

for linha in resultados:
    print(linha)

cursor.close()
conn.close()

print("\nTeste concluído!")