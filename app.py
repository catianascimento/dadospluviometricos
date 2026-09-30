import os
from datetime import datetime, timedelta

import requests
from openpyxl import load_workbook


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ARQUIVO_EXCEL = r"C:\Users\catia.sepetauskas\Documents\dadospluvio\chuvas.xlsx"

# Estações que serão atualizadas
ESTACOES = [
    1155,
    # 1156,
    # 1157,
]


# ============================================================
# 1. CONSULTAR DADOS DO DAEE
# ============================================================

def get_precipitation(station, start_date, end_date):
    """
    Consulta o DAEE e retorna a precipitação acumulada
    para uma estação no intervalo informado.
    """

    url = "https://cth.daee.sp.gov.br/sibh/api/v2/measurements"

    params = {
        "format": "json",
        "start_date": start_date,
        "end_date": end_date,
        "group_type": "minute",
        "transmission_type_ids[]": 6,
        "station_prefix_ids[]": station,
    }

    print(f"Consultando DAEE - estação {station}...")

    response = requests.get(
        url,
        params=params,
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    measurements = data.get("measurements", [])

    total = 0

    for item in measurements:

        value = item.get("value")

        if value is not None:
            total += float(value)

    total = round(total, 2)

    print(f"Estação {station}: {total} mm")

    return total


# ============================================================
# 2. ENCONTRAR / CRIAR COLUNA DA DATA
# ============================================================

def get_or_create_date_column(worksheet, date_label):
    """
    Procura a data na primeira linha.

    Se existir:
        retorna a coluna.

    Se não existir:
        cria uma nova coluna no final.
    """

    # Procurar a data existente
    for cell in worksheet[1]:

        if str(cell.value).strip() == date_label:
            return cell.column

    # Data não encontrada.
    # Criar nova coluna.
    new_column = worksheet.max_column + 1

    worksheet.cell(
        row=1,
        column=new_column,
        value=date_label
    )

    print(f"Nova coluna criada: {date_label}")

    return new_column


# ============================================================
# 3. ENCONTRAR / CRIAR ESTAÇÃO
# ============================================================

def find_or_create_station_row(worksheet, station):
    """
    Procura a estação na coluna A.

    Se não encontrar:
        cria uma nova linha.
    """

    station = str(station).strip()

    # Procurar estação existente
    for row in range(2, worksheet.max_row + 1):

        value = worksheet.cell(
            row=row,
            column=1
        ).value

        if value is not None:

            if str(value).strip() == station:
                return row

    # Estação não encontrada.
    # Criar nova linha.
    new_row = worksheet.max_row + 1

    worksheet.cell(
        row=new_row,
        column=1,
        value=station
    )

    print(
        f"Estação {station} não existia. "
        f"Nova linha criada: {new_row}"
    )

    return new_row


# ============================================================
# 4. ENCONTRAR / CRIAR ABA DO ANO
# ============================================================

def get_or_create_month_sheet(workbook, date):
    """
    O nome da aba será mês-ano.

    Exemplos:
        29/09/2026 -> 09-2026
        01/10/2026 -> 10-2026
        15/01/2027 -> 01-2027

    Se a aba não existir, ela será criada.
    """

    nome_aba = date.strftime("%m-%Y")

    # Aba já existe
    if nome_aba in workbook.sheetnames:

        worksheet = workbook[nome_aba]

        print(f"Aba encontrada: {nome_aba}")

        return worksheet

    # Criar nova aba
    worksheet = workbook.create_sheet(nome_aba)

    # Criar cabeçalho
    worksheet.cell(
        row=1,
        column=1,
        value="codigo"
    )

    print(f"Nova aba criada: {nome_aba}")

    return worksheet


# ============================================================
# 5. ATUALIZAR EXCEL
# ============================================================

def update_excel(
    arquivo,
    station,
    date,
    total
):
    """
    Atualiza o Excel.

    A aba é definida pelo ano da data.

    A coluna é definida pelo dia/mês.
    """

    if not os.path.exists(arquivo):

        raise FileNotFoundError(
            f"Arquivo não encontrado: {arquivo}"
        )

    print(f"\nAbrindo Excel: {arquivo}")

    workbook = load_workbook(arquivo)

    # --------------------------------------------------------
    # Encontrar ou criar aba do ano
    # --------------------------------------------------------

    worksheet = get_or_create_month_sheet(
        workbook,
        date
    )

    # --------------------------------------------------------
    # Nome da coluna da data
    # --------------------------------------------------------

    date_label = date.strftime("%d/%m")

    # --------------------------------------------------------
    # Encontrar ou criar coluna
    # --------------------------------------------------------

    coluna_data = get_or_create_date_column(
        worksheet,
        date_label
    )

    # --------------------------------------------------------
    # Encontrar ou criar estação
    # --------------------------------------------------------

    linha_estacao = find_or_create_station_row(
        worksheet,
        station
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
        f"Atualizando estação {station} "
        f"na data {date_label}: {total} mm"
    )

    # --------------------------------------------------------
    # Salvar
    # --------------------------------------------------------

    workbook.save(arquivo)

    print("Excel atualizado com sucesso!")


# ============================================================
# 6. PROCESSO PRINCIPAL
# ============================================================

def main():

    print("=" * 60)
    print("ATUALIZAÇÃO DIÁRIA DE PRECIPITAÇÃO")
    print("=" * 60)

    # --------------------------------------------------------
    # Data atual
    # --------------------------------------------------------

    hoje = datetime.now()

    # --------------------------------------------------------
    # Dia anterior
    # --------------------------------------------------------

    data_busca = hoje - timedelta(days=1)

    # --------------------------------------------------------
    # Formato da data que será exibida no Excel
    # --------------------------------------------------------

    date_label = data_busca.strftime("%d/%m")

    # --------------------------------------------------------
    # Intervalo consultado no DAEE
    #
    # Dia anterior:
    # 00:01 até 23:59
    # --------------------------------------------------------

    start_date = data_busca.strftime(
        "%Y-%m-%d 00:01"
    )

    # end_date = data_busca.strftime(
    #     "%Y-%m-%d 23:59"
    # )
    end_date = hoje.strftime(
            "%Y-%m-%d 02:20"
        )

    # --------------------------------------------------------
    # Informações da execução
    # --------------------------------------------------------

    print(f"Hoje: {hoje.strftime('%d/%m/%Y %H:%M:%S')}")

    print(
        f"Data buscada: "
        f"{data_busca.strftime('%d/%m/%Y')}"
    )

    print(f"Início: {start_date}")

    print(f"Fim: {end_date}")

    print("=" * 60)

    # --------------------------------------------------------
    # Atualizar cada estação
    # --------------------------------------------------------

    for station in ESTACOES:

        try:

            # ------------------------------------------------
            # Consultar DAEE
            # ------------------------------------------------

            total = get_precipitation(
                station,
                start_date,
                end_date
            )

            # ------------------------------------------------
            # Atualizar Excel
            # ------------------------------------------------

            update_excel(
                arquivo=ARQUIVO_EXCEL,
                station=station,
                date=data_busca,
                total=total
            )

        except Exception as e:

            print(
                f"ERRO na estação {station}: {e}"
            )

    print("=" * 60)
    print("PROCESSO FINALIZADO")
    print("=" * 60)


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":
    main()