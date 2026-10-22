import sys
import streamlit.web.cli as stcli

# IMPORTS EXPLICITOS PARA O PYINSTALLER
import os
import pandas
import psycopg2
import dotenv
import streamlit
# Esta linha abaixo corrige exatamente o erro ModuleNotFoundError:
import streamlit.runtime.scriptrunner.magic_funcs 

if __name__ == "__main__":
    sys.argv = ["streamlit", "run", "dashboard.py", "--global.developmentMode=false"]
    sys.exit(stcli.main())
