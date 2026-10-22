import os
from datetime import datetime, time as datetime_time, timedelta

import psycopg2
import pytz
import requests
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


# ============================================================
# CONFIGURAÇÕES
# ============================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

ESTACOES = [
    (35572, "Barragem Jacareí / Joanópolis"),
    (3, "Barragem Jaguari - Vargem / Vargem"),
    (11, "Barragem Cachoeira / Piracaia"),
    (15, "Barragem Atibainha / Nazaré Paulista"),
    (458, "Desemboque do Tunel 5"),
    (31, "Barragem Paiva Castro / Franco da Rocha"),
    (33, "Barragem Águas Claras / Mariporã"),
    (9, "F25b - Rio Jaguarí / Extrema - MG"),
    (28, "F-38 - Rio Juqueri / Franco da Rocha")
]


# ============================================================
# CONSULTAR DAEE
# ============================================================

def get_measurements(station, start_date, end_date):

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

    return data.get("measurements", [])


# ============================================================
# CONVERTER DATA/HORA
# ============================================================

def convert_date(date_string):

    """
    O DAEE retorna a data aproximadamente 3 horas
    à frente do horário de Brasília.

    Exemplo:
        2026/10/01 10:50
    vira:
        2026-10-01 07:50
    """

    data = datetime.strptime(
        date_string,
        "%Y/%m/%d %H:%M"
    )
    data_utc = API_TZ.localize(data)

    return data_utc.astimezone(BRAZIL_TZ)


# ============================================================
# GARANTIR ESTAÇÃO NO BANCO
# ============================================================

def get_or_create_station(
    cursor,
    codigo,
    nome
):

    cursor.execute(
        """
        INSERT INTO estacoes (
            codigo,
            nome_estacao
        )
        VALUES (%s, %s)

        ON CONFLICT (codigo)
        DO UPDATE SET
            nome_estacao = EXCLUDED.nome_estacao

        RETURNING id
        """,
        (
            codigo,
            nome
        )
    )

    return cursor.fetchone()[0]


# ============================================================
# SALVAR MEDIÇÕES
# ============================================================

def save_measurements(
    cursor,
    station_id,
    measurements
):

    quantidade = 0

    for item in measurements:

        value = item.get("value")
        date_string = item.get("date")

        if value is None or float(value) == 0:
            continue

        if date_string is None:
            continue

        data_hora = convert_date(
            date_string
        )

        value = float(value)

        cursor.execute(
            """
            INSERT INTO precipitacao_10min (
                estacao_id,
                data_hora,
                precipitacao_mm
            )
            VALUES (%s, %s, %s)

            ON CONFLICT (
                estacao_id,
                data_hora
            )
            DO UPDATE SET
                precipitacao_mm =
                    EXCLUDED.precipitacao_mm
            """,
            (
                station_id,
                data_hora,
                value
            )
        )

        quantidade += 1

    return quantidade


# ============================================================
# PROCESSO PRINCIPAL
# ============================================================

def main():

    # --------------------------------------------------------
    # Dia anterior
    # --------------------------------------------------------

    hoje = datetime.now(BRAZIL_TZ)

    data_consulta = hoje - timedelta(days=1)

    # --------------------------------------------------------
    # Intervalo local do dia anterior, incluindo 00:00 e 23:59.
    # Os limites são convertidos para UTC antes da consulta.
    # --------------------------------------------------------

    start_date = format_api_boundary(
        data_consulta.date(),
        datetime_time(0, 0)
    )

    end_date = format_api_boundary(
        data_consulta.date(),
        datetime_time(23, 59)
    )

    print("=" * 60)
    print("COLETA DE PRECIPITAÇÃO - 10 MIN")
    print("=" * 60)

    print(
        f"Data local: "
        f"{data_consulta.strftime('%d/%m/%Y')}"
    )

    print(
        f"Consulta DAEE: "
        f"{start_date} até {end_date}"
    )

    # --------------------------------------------------------
    # Conectar banco
    # --------------------------------------------------------

    conn = psycopg2.connect(
        DATABASE_URL
    )

    cursor = conn.cursor()

    # --------------------------------------------------------
    # Estações
    # --------------------------------------------------------

    cursor.execute("SET TIME ZONE 'America/Sao_Paulo'")

    for station, station_name in ESTACOES:

        try:

            measurements = get_measurements(
                station,
                start_date,
                end_date
            )

            # Estação no banco
            station_id = get_or_create_station(
                cursor,
                station,
                station_name
            )

            quantidade = save_measurements(
                cursor,
                station_id,
                measurements
            )

            conn.commit()

            print(
                f"Estação {station} - "
                f"{station_name}: "
                f"{quantidade} registros salvos."
            )

        except Exception as e:

            conn.rollback()

            print(
                f"ERRO na estação "
                f"{station} - "
                f"{station_name}: {e}"
            )

    cursor.close()
    conn.close()

    print("=" * 60)
    print("PROCESSO FINALIZADO")
    print("=" * 60)


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":
    main()
