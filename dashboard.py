import os

import pandas as pd
import psycopg2
import streamlit as st
from dotenv import load_dotenv


# ============================================================
# CONFIGURAÇÃO
# ============================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


# ============================================================
# CONEXÃO
# ============================================================

def get_connection():

    return psycopg2.connect(
        DATABASE_URL
    )


def load_page(
    count_query,
    data_query,
    query_params,
    widget_key
):

    conn = get_connection()

    try:

        with conn.cursor() as cursor:
            cursor.execute(
                count_query,
                query_params
            )
            total_rows = cursor.fetchone()[0]

        columns = st.columns([1, 1, 3])

        with columns[0]:
            page_size = st.selectbox(
                "Linhas por página",
                [9, 25, 50, 100, 250],
                key=f"{widget_key}_page_size"
            )

        total_pages = max(
            1,
            (total_rows + page_size - 1) // page_size
        )
        page_key = f"{widget_key}_page"
        st.session_state[page_key] = min(
            max(1, st.session_state.get(page_key, 1)),
            total_pages
        )

        with columns[1]:
            page_number = st.number_input(
                "Página",
                min_value=1,
                max_value=total_pages,
                step=1,
                key=page_key
            )

        with columns[2]:
            st.caption(
                f"{total_rows:,} registros | "
                f"página {page_number} de {total_pages}"
            )

        offset = (page_number - 1) * page_size
        df = pd.read_sql_query(
            data_query,
            conn,
            params=(
                *query_params,
                page_size,
                offset
            )
        )

        return df, total_rows, page_number

    finally:
        conn.close()


def render_csv_download(df, filename, key):

    st.download_button(
        "Baixar CSV desta página",
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        key=key
    )


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Precipitação",
    page_icon="🌧️",
    layout="wide"
)

st.title("🌧️ Dados de Precipitação")

st.write(
    "Consulte os dados de precipitação armazenados no PostgreSQL."
)


# ============================================================
# MENU
# ============================================================

opcao = st.radio(
    "Escolha uma consulta:",
    [
        "Todas as estações por data",
        "Histórico de uma estação"
    ],
    horizontal=True
)


# ============================================================
# OPÇÃO 1
# TODAS AS ESTAÇÕES POR DATA
# ============================================================

if opcao == "Todas as estações por data":

    st.subheader(
        "Precipitação por data"
    )

    # --------------------------------------------------------
    # Buscar datas disponíveis
    # --------------------------------------------------------

    conn = get_connection()

    datas = pd.read_sql_query(
        """
        SELECT DISTINCT data
        FROM precipitacao
        ORDER BY data DESC
        """,
        conn
    )

    conn.close()

    # --------------------------------------------------------
    # Verificar se existem dados
    # --------------------------------------------------------

    if datas.empty:

        st.warning(
            "Ainda não existem dados de precipitação."
        )

    else:

        data_selecionada = st.date_input(
            "Escolha a data:",
            value=datas.iloc[0]["data"]
        )

        # ----------------------------------------------------
        # Consultar todas as estações
        # ----------------------------------------------------

        df, total_rows, page_number = load_page(
            """
            SELECT COUNT(*)
            FROM precipitacao
            WHERE data = %s
            """,
            """
            SELECT
                e.codigo,
                e.nome_estacao,
                p.data,
                p.precipitacao_mm
            FROM precipitacao p

            INNER JOIN estacoes e
                ON e.id = p.estacao_id

            WHERE p.data = %s

            ORDER BY e.codigo
            LIMIT %s OFFSET %s
            """,
            (data_selecionada,),
            "daily"
        )

        # ----------------------------------------------------
        # Mostrar tabela
        # ----------------------------------------------------

        st.write(
            f"Dados de {data_selecionada.strftime('%d/%m/%Y')}"
        )

        if df.empty:

            st.warning(
                "Não existem dados para esta data."
            )

        else:

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )

            render_csv_download(
                df,
                f"precipitacao_{data_selecionada:%Y-%m-%d}_pagina_{page_number}.csv",
                f"daily_csv_{data_selecionada}"
            )


# ============================================================
# OPÇÃO 2
# HISTÓRICO DE UMA ESTAÇÃO
# ============================================================

else:

    st.subheader(
        "Histórico de uma estação"
    )

    # --------------------------------------------------------
    # Buscar estações
    # --------------------------------------------------------

    conn = get_connection()

    estacoes = pd.read_sql_query(
        """
        SELECT
            id,
            codigo,
            nome_estacao
        FROM estacoes
        ORDER BY codigo
        """,
        conn
    )

    conn.close()

    # --------------------------------------------------------
    # Verificar se existem estações
    # --------------------------------------------------------

    if estacoes.empty:

        st.warning(
            "Nenhuma estação cadastrada."
        )

    else:

        # ----------------------------------------------------
        # Criar opções para o selectbox
        # ----------------------------------------------------

        opcoes = {
            f"{row.codigo} - {row.nome_estacao}":
            row.id

            for row in estacoes.itertuples()
        }

        estacao_selecionada = st.selectbox(
            "Escolha a estação:",
            list(opcoes.keys())
        )

        estacao_id = opcoes[
            estacao_selecionada
        ]
        
        # ----------------------------------------------------
        # Buscar histórico
        # ----------------------------------------------------

        df, total_rows, page_number = load_page(
            """
            SELECT COUNT(*)
            FROM precipitacao
            WHERE estacao_id = %s
            """,
            """
            SELECT
                e.codigo,
                e.nome_estacao,
                p.data,
                p.precipitacao_mm
            FROM precipitacao p

            INNER JOIN estacoes e
                ON e.id = p.estacao_id

            WHERE e.id = %s

            ORDER BY p.data DESC
            LIMIT %s OFFSET %s
            """,
            (estacao_id,),
            f"station_{estacao_id}"
        )

        # ----------------------------------------------------
        # Mostrar histórico
        # ----------------------------------------------------

        st.write(
            f"Histórico: {estacao_selecionada}"
        )

        if df.empty:

            st.warning(
                "Não existem dados para esta estação."
            )

        else:

            st.dataframe(
                df,
                width="stretch",
                hide_index=True
            )

            render_csv_download(
                df,
                f"historico_estacao_{estacao_id}_pagina_{page_number}.csv",
                f"station_csv_{estacao_id}"
            )
