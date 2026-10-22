# Dados Pluviometricos

## Preparacao

Abra o PowerShell na pasta do projeto. Os comandos abaixo usam o ambiente
virtual `venv` existente:

```powershell
.\venv\Scripts\Activate.ps1
```

Para gravar os dados no PostgreSQL, configure `DATABASE_URL` no arquivo
`.env` antes de executar `app_banco.py`.

## Coleta diaria

Sem informar datas, cada script consulta somente ontem, das 00:00 as 23:59
no horario de Brasilia:

```powershell
.\venv\Scripts\python.exe app.py
.\venv\Scripts\python.exe app_banco.py
```

`app.py` atualiza `chuvas.xlsx`; `app_banco.py` grava no PostgreSQL.
O arquivo `executar_chuvas.bat` executa os dois scripts nessa modalidade
diaria.

## Reprocessar um periodo

Informe a data inicial e final no formato `DD/MM/AAAA`. As datas inicial e
final sao inclusivas e a data final deve ser, no maximo, ontem:

```powershell
.\venv\Scripts\python.exe app.py 01/10/2026 20/10/2026
.\venv\Scripts\python.exe app_banco.py 01/10/2026 20/10/2026
```

O script consulta cada dia separadamente, das 00:00 as 23:59 de Brasilia,
e associa o total a data correspondente. Valores existentes nas datas
selecionadas sao atualizados. Para preencher outro periodo, substitua as
duas datas nos comandos.

Se `chuvas.xlsx` estiver aberto e nao puder ser salvo, `app.py` grava uma
copia com o sufixo `_atualizado` na mesma pasta.

## Dashboard

Para abrir o painel de consulta:

```powershell
.\venv\Scripts\streamlit.exe run dashboard.py
```
