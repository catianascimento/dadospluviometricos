import os
from datetime import datetime, time as datetime_time, timedelta

import pandas as pd
import pytz
import requests


BRAZIL_TZ = pytz.timezone("America/Sao_Paulo")
API_TZ = pytz.UTC


def format_api_boundary(local_date):
    local_datetime = BRAZIL_TZ.localize(
        datetime.combine(
            local_date,
            datetime_time(7)
        )
    )

    return local_datetime.astimezone(
        API_TZ
    ).strftime("%Y-%m-%d %H:%M")


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ARQUIVO_EXCEL = (
    r"C:\Users\catia.sepetauskas"
    r"\Documents\dadospluvio"
    r"\chuvas_10min.xlsx"
)

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

def get_measurements(
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

    return data.get("measurements", [])


# ============================================================
# CONVERTER DATA/HORA
# ============================================================

def convert_date(date_string):

    data = datetime.strptime(
        date_string,
        "%Y/%m/%d %H:%M"
    )
    data_utc = API_TZ.localize(data)

    return data_utc.astimezone(
        BRAZIL_TZ
    ).replace(tzinfo=None)


# ============================================================
# LER EXCEL EXISTENTE
# ============================================================

def load_existing_data():

    if not os.path.exists(
        ARQUIVO_EXCEL
    ):

        return pd.DataFrame(
            columns=[
                "codigo",
                "nome_estacao",
                "data_hora",
                "precipitacao_mm"
            ]
        )

    df = pd.read_excel(
        ARQUIVO_EXCEL
    )

    # Garantir que as colunas existam
    colunas = [
        "codigo",
        "nome_estacao",
        "data_hora",
        "precipitacao_mm"
    ]

    for coluna in colunas:

        if coluna not in df.columns:

            df[coluna] = None

    return df[colunas]


# ============================================================
# PROCESSO PRINCIPAL
# ============================================================

def main():

    # --------------------------------------------------------
    # Dia anterior
    # --------------------------------------------------------

    hoje = datetime.now(BRAZIL_TZ)

    data_consulta = (
        hoje - timedelta(days=1)
    )

    start_date = format_api_boundary(
        data_consulta.date()
    )

    data_seguinte = (
        data_consulta + timedelta(days=1)
    )

    end_date = format_api_boundary(
        data_seguinte.date()
    )

    print("=" * 60)
    print("COLETA DE PRECIPITAÇÃO - 10 MIN")
    print("=" * 60)

    print(
        f"Data: "
        f"{data_consulta.strftime('%d/%m/%Y')}"
    )

    print(
        f"Consulta DAEE: "
        f"{start_date} até {end_date}"
    )

    # --------------------------------------------------------
    # Carregar Excel
    # --------------------------------------------------------

    df_existente = load_existing_data()

    novos_registros = []

    # --------------------------------------------------------
    # Consultar estações
    # --------------------------------------------------------

    for station, station_name in ESTACOES:

        try:

            measurements = get_measurements(
                station,
                start_date,
                end_date
            )

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

                novos_registros.append(
                    {
                        "codigo": station,
                        "nome_estacao": station_name,
                        "data_hora": data_hora,
                        "precipitacao_mm": float(value)
                    }
                )

                quantidade += 1

            print(
                f"Estação {station} - "
                f"{station_name}: "
                f"{quantidade} registros encontrados."
            )

        except Exception as e:

            print(
                f"ERRO na estação "
                f"{station} - "
                f"{station_name}: {e}"
            )

    # --------------------------------------------------------
    # Nenhum dado
    # --------------------------------------------------------

    if not novos_registros:

        print(
            "Nenhum novo registro encontrado."
        )

        return

    # --------------------------------------------------------
    # Criar DataFrame dos novos dados
    # --------------------------------------------------------

    df_novos = pd.DataFrame(
        novos_registros
    )

    # --------------------------------------------------------
    # Juntar com dados existentes
    # --------------------------------------------------------

    df_final = pd.concat(
        [
            df_existente,
            df_novos
        ],
        ignore_index=True
    )

    # --------------------------------------------------------
    # Remover duplicidades
    #
    # Uma estação + data/hora = um registro
    # --------------------------------------------------------

    df_final = df_final.drop_duplicates(
        subset=[
            "codigo",
            "data_hora"
        ],
        keep="last"
    )

    # --------------------------------------------------------
    # Ordenar
    # --------------------------------------------------------

    df_final = df_final.sort_values(
        [
            "codigo",
            "data_hora"
        ]
    )

    # --------------------------------------------------------
    # Salvar Excel
    # --------------------------------------------------------

    df_final.to_excel(
        ARQUIVO_EXCEL,
        index=False
    )

    print()
    print(
        f"Excel atualizado: "
        f"{ARQUIVO_EXCEL}"
    )

    print(
        f"Total de registros: "
        f"{len(df_final)}"
    )

    print("=" * 60)
    print("PROCESSO FINALIZADO")
    print("=" * 60)


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":
    main()
