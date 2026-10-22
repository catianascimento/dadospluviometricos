import argparse
import os
from datetime import datetime, time as datetime_time, timedelta

import pytz
import requests
import psycopg2
from dotenv import load_dotenv


BRAZIL_TZ = pytz.timezone("America/Sao_Paulo")
API_TZ = pytz.UTC


def format_api_boundary(local_date, local_time):
    local_datetime = BRAZIL_TZ.localize(
        datetime.combine(
            local_date,
            local_time
        )
    )

    return local_datetime.astimezone(
        API_TZ
    ).strftime("%Y-%m-%d %H:%M")


def parse_command_date(value):
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Use o formato DD/MM/AAAA."
        ) from error


# ============================================================
# CONFIGURAÇÕES
# ============================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


# ============================================================
# ESTAÇÕES
# ============================================================

ESTACOES = [
    {
        "codigo": 35572,
        "nome": "Barragem Jacareí / Joanópolis"
    },
    {
        "codigo": 3,
        "nome": "Barragem Jaguari - Vargem / Vargem"
    },
    {
        "codigo": 11,
        "nome": "Barragem Cachoeira / Piracaia"
    },
    {
        "codigo": 15,
        "nome": "Barragem Atibainha / Nazaré Paulista"
    },
    {
        "codigo": 458,
        "nome": "Desemboque do Tunel 5"
    },
    {
        "codigo": 31,
        "nome": "Barragem Paiva Castro / Franco da Rocha"
    },
    {
        "codigo": 33,
        "nome": "Barragem Águas Claras / Mariporã"
    },
    {
        "codigo": 9,
        "nome": "F25b - Rio Jaguarí / Extrema - MG"
    },
    {
        "codigo": 28,
        "nome": "F-38 - Rio Juqueri / Franco da Rocha"
    }
]


# ============================================================
# CONEXÃO COM O POSTGRESQL
# ============================================================

def get_connection():

    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL não encontrada no arquivo .env"
        )

    return psycopg2.connect(
        DATABASE_URL
    )


# ============================================================
# CRIAR TABELAS
# ============================================================

def create_tables():

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # Tabela de estações
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estacoes (
            id SERIAL PRIMARY KEY,
            codigo INTEGER NOT NULL UNIQUE,
            nome_estacao TEXT NOT NULL
        );
    """)

    # --------------------------------------------------------
    # Tabela de precipitação
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS precipitacao (
            id SERIAL PRIMARY KEY,

            estacao_id INTEGER NOT NULL,

            data DATE NOT NULL,

            precipitacao_mm NUMERIC(10, 2),

            FOREIGN KEY (estacao_id)
                REFERENCES estacoes(id)
                ON DELETE CASCADE,

            UNIQUE (
                estacao_id,
                data
            )
        );
    """)

    conn.commit()

    cursor.close()
    conn.close()

    print("Tabelas verificadas com sucesso.")


# ============================================================
# CONSULTAR DAEE
# ============================================================

def get_precipitation(
    station,
    start_date,
    end_date
):

    url = (
        "https://cth.daee.sp.gov.br/"
        "sibh/api/v2/measurements"
    )

    params = {
        "format": "json",
        "start_date": start_date,
        "end_date": end_date,
        "group_type": "minute",
        "transmission_type_ids[]": 6,
        "station_prefix_ids[]": station,
    }

    print(
        f"Consultando DAEE - estação {station}..."
    )

    response = requests.get(
        url,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    measurements = data.get(
        "measurements",
        []
    )

    total = 0

    for item in measurements:

        value = item.get("value")

        if value is not None:
            total += float(value)

    total = round(total, 2)

    print(
        f"Precipitação encontrada: "
        f"{total} mm"
    )

    return total


# ============================================================
# CRIAR / ATUALIZAR ESTAÇÃO
# ============================================================

def get_or_create_station(
    station,
    station_name
):

    conn = get_connection()
    cursor = conn.cursor()

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
        station,
        station_name
    ))

    station_id = cursor.fetchone()[0]

    conn.commit()

    cursor.close()
    conn.close()

    return station_id


# ============================================================
# SALVAR PRECIPITAÇÃO
# ============================================================

def save_precipitation(
    station_id,
    date,
    total
):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO precipitacao (
            estacao_id,
            data,
            precipitacao_mm
        )
        VALUES (%s, %s, %s)

        ON CONFLICT (
            estacao_id,
            data
        )
        DO UPDATE SET
            precipitacao_mm =
                EXCLUDED.precipitacao_mm;
    """, (
        station_id,
        date,
        total
    ))

    conn.commit()

    cursor.close()
    conn.close()

    print(
        f"Dados salvos no PostgreSQL: "
        f"{date} = {total} mm"
    )


# ============================================================
# PROCESSAR UMA ESTAÇÃO
# ============================================================

def process_station(
    station,
    station_name,
    data_consulta
):
    # Intervalo consultado no DAEE
    start_date = format_api_boundary(
        data_consulta,
        datetime_time(0, 0)
    )
    end_date = format_api_boundary(
        data_consulta,
        datetime_time(23, 59)
    )

    # Consultar DAEE
    total = get_precipitation(
        station,
        start_date,
        end_date
    )

    # Garantir que a estação existe
    station_id = get_or_create_station(
        station,
        station_name
    )

    # Salvar o acumulado na data consultada
    save_precipitation(
        station_id,
        data_consulta,
        total
    )


# ============================================================
# PROCESSO PRINCIPAL
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Atualiza os acumulados diários de precipitação "
            "no PostgreSQL."
        )
    )
    parser.add_argument(
        "data_inicial",
        nargs="?",
        type=parse_command_date,
        help="Primeiro dia do período, no formato DD/MM/AAAA."
    )
    parser.add_argument(
        "data_final",
        nargs="?",
        type=parse_command_date,
        help="Último dia do período, no formato DD/MM/AAAA."
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ATUALIZAÇÃO DE PRECIPITAÇÃO")
    print("=" * 60)

    # --------------------------------------------------------
    # Data atual
    # --------------------------------------------------------

    hoje = datetime.now(BRAZIL_TZ)

    ontem = hoje.date() - timedelta(days=1)

    if (args.data_inicial is None) != (args.data_final is None):
        parser.error(
            "Informe as duas datas: inicial e final."
        )

    if args.data_inicial is None:
        data_inicial = ontem
        data_final = ontem
    else:
        data_inicial = args.data_inicial
        data_final = args.data_final

        if data_inicial > data_final:
            parser.error(
                "A data inicial deve ser anterior ou igual à data final."
            )

        if data_final > ontem:
            parser.error(
                "A data final deve ser até ontem, pois o acumulado do "
                "dia atual ainda não cobre 00:00 a 23:59."
            )

    print(
        f"Hoje: "
        f"{hoje.strftime('%d/%m/%Y %H:%M:%S')}"
    )

    print(
        f"Período buscado: "
        f"{data_inicial:%d/%m/%Y} até {data_final:%d/%m/%Y}"
    )

    print("=" * 60)

    # --------------------------------------------------------
    # Garantir que as tabelas existem
    # --------------------------------------------------------

    create_tables()

    # --------------------------------------------------------
    # Processar cada data e estação
    # --------------------------------------------------------

    quantidade_dias = (data_final - data_inicial).days + 1

    for deslocamento in range(quantidade_dias):
        data_busca = data_inicial + timedelta(days=deslocamento)

        print(
            f"\nProcessando {data_busca:%d/%m/%Y}"
        )

        for estacao in ESTACOES:

            station = estacao["codigo"]
            station_name = estacao["nome"]

            try:
                process_station(
                    station,
                    station_name,
                    data_busca
                )

            except Exception as e:
                print(
                    f"ERRO na estação "
                    f"{station} - "
                    f"{station_name}: {e}"
                )

    print("=" * 60)
    print("PROCESSO FINALIZADO")
    print("=" * 60)


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":
    main()