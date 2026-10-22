import argparse
import os
import time
from copy import copy
from datetime import date as date_type
from datetime import datetime, time as datetime_time, timedelta

import pytz
import requests
from openpyxl import load_workbook


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

ARQUIVO_EXCEL = (
    r"C:\Users\catia.sepetauskas"
    r"\Documents\dadospluvio\chuvas.xlsx"
)


# ============================================================
# ESTAÇÕES
# ============================================================
#
# Cada estação possui:
#
# codigo: código da estação no DAEE
# nome: nome que será gravado no Excel
#
# Exemplo:
#
# ESTACOES = [
#     {"codigo": 1155, "nome": "Estação São José"},
#     {"codigo": 1156, "nome": "Estação Jacareí"},
# ]
#

ESTACOES = [
    {
        "codigo": 35572,
        "nome": "Barragem Jacareí"
    },
    {
        "codigo": 3,
        "nome": "Barragem Jaguari - Vargem"
    },
    {
        "codigo": 11,
        "nome": "Barragem Cachoeira"
    },
    {
        "codigo": 15,
        "nome": "Barragem Atibainha"
    },
    {
        "codigo": 458,
        "nome": "Desemboque do Tunel 5"
    },
    {
        "codigo": 31,
        "nome": "Barragem Paiva Castro"
    },
    {
        "codigo": 33,
        "nome": "Barragem Águas Claras"
    },
    {
        "codigo": 9,
        "nome": "F25b - Rio Jaguarí"
    },
    {
        "codigo": 28,
        "nome": "F-38 - Rio Juqueri"
    }
]


# ============================================================
# 1. CONSULTAR DADOS DO DAEE
# ============================================================

def get_precipitation(station, start_date, end_date):
    """
    Consulta o DAEE e retorna a precipitação acumulada
    para uma estação no intervalo informado.
    """

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
        f"Estação {station}: "
        f"{total} mm"
    )

    return total


# ============================================================
# 2. ENCONTRAR / CRIAR COLUNA DA DATA
# ============================================================

def get_or_create_date_column(
    worksheet,
    date_value
):
    """
    Procura a data na primeira linha.

    Estrutura:

        A = codigo
        B = nome_estacao
        C em diante = datas

    Se a data não existir, cria uma nova coluna.
    """

    target_date = (
        date_value.date()
        if isinstance(date_value, datetime)
        else date_value
    )

    def parse_header_date(value):
        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date_type):
            return value

        if isinstance(value, str):
            value = value.strip()
            for date_format in ("%d/%m/%Y", "%d/%m"):
                try:
                    parsed_date = datetime.strptime(
                        value,
                        date_format
                    ).date()
                    if date_format == "%d/%m":
                        parsed_date = parsed_date.replace(
                            year=target_date.year
                        )
                    return parsed_date
                except ValueError:
                    continue

        return None

    columns = []
    target_column = None

    for column in range(3, worksheet.max_column + 1):
        header_date = parse_header_date(
            worksheet.cell(row=1, column=column).value
        )
        cells = []
        for row in range(1, worksheet.max_row + 1):
            cell = worksheet.cell(row=row, column=column)
            cells.append(
                (
                    cell.value,
                    copy(cell._style),
                    copy(cell.comment),
                    copy(cell.hyperlink)
                )
            )
        columns.append((header_date, column, cells))

        if header_date == target_date:
            target_column = column

    if target_column is None:
        cells = [(target_date, None, None, None)]
        for row in range(2, worksheet.max_row + 1):
            cells.append((None, None, None, None))
        columns.append((target_date, worksheet.max_column + 1, cells))
        print(
            f"Nova coluna criada: "
            f"{target_date.strftime('%d/%m')}"
        )

    columns.sort(
        key=lambda item: (
            item[0] is None,
            item[0] or target_date,
            item[1]
        )
    )

    for new_column, (header_date, _, cells) in enumerate(
        columns,
        start=3
    ):
        for row, (value, style, comment, hyperlink) in enumerate(
            cells,
            start=1
        ):
            cell = worksheet.cell(row=row, column=new_column)
            cell.value = value
            cell._style = style
            cell.comment = comment
            cell._hyperlink = hyperlink

        if header_date is not None:
            header = worksheet.cell(row=1, column=new_column)
            header.value = header_date
            header.number_format = "dd/mm"

    for column in range(3, worksheet.max_column + 1):
        if parse_header_date(
            worksheet.cell(row=1, column=column).value
        ) == target_date:
            return column

    raise RuntimeError(
        f"Não foi possível encontrar a coluna de "
        f"{target_date.strftime('%d/%m/%Y')} após ordenar."
    )


# ============================================================
# 3. ENCONTRAR / CRIAR ESTAÇÃO
# ============================================================

def find_or_create_station_row(
    worksheet,
    station,
    station_name
):
    """
    Procura a estação na coluna A.

    Se encontrar:
        atualiza o nome na coluna B.

    Se não encontrar:
        cria uma nova linha.

    Estrutura:

        A = codigo
        B = nome_estacao
    """

    station = str(station).strip()

    station_name = str(
        station_name
    ).strip()

    # Procurar estação existente
    for row in range(
        2,
        worksheet.max_row + 1
    ):

        value = worksheet.cell(
            row=row,
            column=1
        ).value

        if value is not None:

            if (
                str(value).strip()
                == station
            ):

                # Atualizar nome
                worksheet.cell(
                    row=row,
                    column=2,
                    value=station_name
                )

                return row

    # --------------------------------------------------------
    # Estação não encontrada
    # --------------------------------------------------------

    new_row = worksheet.max_row + 1

    worksheet.cell(
        row=new_row,
        column=1,
        value=station
    )

    worksheet.cell(
        row=new_row,
        column=2,
        value=station_name
    )

    print(
        f"Estação {station} - "
        f"{station_name} não existia."
    )

    print(
        f"Nova linha criada: {new_row}"
    )

    return new_row


# ============================================================
# 4. ENCONTRAR / CRIAR ABA DO MÊS
# ============================================================

def get_or_create_month_sheet(
    workbook,
    date
):
    """
    O nome da aba será:

        MM-AAAA

    Exemplos:

        30/09/2026 -> 09-2026
        01/10/2026 -> 10-2026
        01/01/2027 -> 01-2027

    Se a aba não existir, ela será criada.
    """

    nome_aba = date.strftime(
        "%m-%Y"
    )

    # --------------------------------------------------------
    # Aba já existe
    # --------------------------------------------------------

    if nome_aba in workbook.sheetnames:

        worksheet = workbook[nome_aba]

        print(
            f"Aba encontrada: {nome_aba}"
        )

        return worksheet

    # --------------------------------------------------------
    # Criar nova aba
    # --------------------------------------------------------

    worksheet = workbook.create_sheet(
        nome_aba
    )

    # Criar cabeçalhos
    worksheet.cell(
        row=1,
        column=1,
        value="codigo"
    )

    worksheet.cell(
        row=1,
        column=2,
        value="Sistema Cantareira"
    )

    print(
        f"Nova aba criada: {nome_aba}"
    )

    return worksheet


# ============================================================
# 5. ATUALIZAR EXCEL
# ============================================================

def update_excel(
    worksheet,
    station,
    station_name,
    coluna_data,
    total
):
    linha_estacao = find_or_create_station_row(
        worksheet,
        station,
        station_name
    )

    # --------------------------------------------------------
    # Gravar acumulado
    # --------------------------------------------------------

    cell = worksheet.cell(
        row=linha_estacao,
        column=coluna_data
    )

    cell.value = total
    cell.number_format = "0.00"

    print(
        f"Atualizando estação "
        f"{station} - {station_name}"
    )

    print(
        f"Precipitação: {total} mm"
    )


def save_workbook(workbook, arquivo):
    try:
        workbook.save(arquivo)
        print(
            "Excel atualizado com sucesso!"
        )
    except PermissionError:
        print()
        print("=" * 60)
        print(
            "O arquivo Excel original está aberto "
            "ou sem permissão para gravação."
        )
        print(
            "Salvando os dados em um novo arquivo."
        )

        nome_base, extensao = os.path.splitext(arquivo)
        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )
        novo_arquivo = (
            f"{nome_base}_atualizado_{timestamp}{extensao}"
        )
        numero = 1

        while os.path.exists(novo_arquivo):
            novo_arquivo = (
                f"{nome_base}_atualizado_{timestamp}_{numero}"
                f"{extensao}"
            )
            numero += 1

        workbook.save(novo_arquivo)

        print(
            f"Novo arquivo salvo: {novo_arquivo}"
        )
        print("=" * 60)


# ============================================================
# 6. PROCESSO PRINCIPAL
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Atualiza os acumulados diários de precipitação "
            "na planilha Excel."
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

    print(
        "ATUALIZAÇÃO DIÁRIA DE "
        "PRECIPITAÇÃO"
    )

    print("=" * 60)

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

    # --------------------------------------------------------
    # Informações da execução
    # --------------------------------------------------------

    print(
        f"Hoje: "
        f"{hoje.strftime('%d/%m/%Y %H:%M:%S')}"
    )

    print(f"Período buscado: {data_inicial:%d/%m/%Y} até {data_final:%d/%m/%Y}")

    print("=" * 60)

    if not os.path.exists(ARQUIVO_EXCEL):
        raise FileNotFoundError(
            f"Arquivo não encontrado: {ARQUIVO_EXCEL}"
        )

    print(
        f"\nAbrindo Excel: {ARQUIVO_EXCEL}"
    )
    workbook = load_workbook(ARQUIVO_EXCEL)
    planilha_alterada = False

    # --------------------------------------------------------
    # Atualizar cada data e estação
    # --------------------------------------------------------

    quantidade_dias = (data_final - data_inicial).days + 1

    for deslocamento in range(quantidade_dias):
        data_busca = data_inicial + timedelta(days=deslocamento)
        start_date = format_api_boundary(
            data_busca,
            datetime_time(0, 0)
        )
        end_date = format_api_boundary(
            data_busca,
            datetime_time(23, 59)
        )
        worksheet = None
        coluna_data = None

        print(
            f"\nData: {data_busca:%d/%m/%Y} "
            f"(consulta DAEE: {start_date} até {end_date})"
        )

        for estacao in ESTACOES:

            station = estacao["codigo"]
            station_name = estacao["nome"]

            try:
                total = get_precipitation(
                    station,
                    start_date,
                    end_date
                )

                if worksheet is None:
                    worksheet = get_or_create_month_sheet(
                        workbook,
                        data_busca
                    )
                    worksheet.column_dimensions["A"].hidden = True
                    worksheet.cell(row=1, column=1, value="codigo")
                    worksheet.cell(
                        row=1,
                        column=2,
                        value="Sistema Cantareira"
                    )
                    coluna_data = get_or_create_date_column(
                        worksheet,
                        data_busca
                    )

                update_excel(
                    worksheet=worksheet,
                    station=station,
                    station_name=station_name,
                    coluna_data=coluna_data,
                    total=total
                )
                planilha_alterada = True

            except Exception as e:
                print()
                print(
                    f"ERRO na estação "
                    f"{station} - "
                    f"{station_name}: {e}"
                )

    if planilha_alterada:
        save_workbook(workbook, ARQUIVO_EXCEL)

    print("=" * 60)

    print(
        "PROCESSO FINALIZADO"
    )

    print("=" * 60)


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":

    main()