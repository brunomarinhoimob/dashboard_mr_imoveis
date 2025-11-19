import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------
st.set_page_config(
    page_title="Clientes MR – Consultas",
    page_icon="🧍‍♂️",
    layout="wide",
)

st.title("🧍‍♂️ Consulta de Clientes – MR Imóveis")

# ---------------------------------------------------------
# PLANILHA
# ---------------------------------------------------------
SHEET_ID = "1Ir_fPugLsfHNk6iH0XPCA6xM92bq8tTrn7UnunGRwCw"
GID_ANALISES = "1574157905"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID_ANALISES}"


# ---------------------------------------------------------
# FUNÇÃO PADRÃO DE DATA
# ---------------------------------------------------------
def limpar_para_data(serie):
    dt = pd.to_datetime(serie, dayfirst=True, errors="coerce")
    return dt.dt.date


# ---------------------------------------------------------
# CARREGAR DADOS
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def carregar_dados():
    df = pd.read_csv(CSV_URL)

    df.columns = [c.strip().upper() for c in df.columns]

    # DIA
    if "DATA" in df.columns:
        df["DIA"] = limpar_para_data(df["DATA"])
    elif "DIA" in df.columns:
        df["DIA"] = limpar_para_data(df["DIA"])
    else:
        df["DIA"] = pd.NaT

    # PADRONIZA textos
    for col in ["CLIENTE", "CPF", "STATUS", "SITUAÇÃO ATUAL", "OBSERVAÇÕES"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip().str.upper()

    return df


df = carregar_dados()

if df.empty:
    st.error("Erro ao carregar dados.")
    st.stop()


# ---------------------------------------------------------
# BARRA DE CONSULTA
# ---------------------------------------------------------
st.markdown("### 🔎 Buscar cliente")

busca = st.text_input(
    "Digite nome completo, parte do nome ou CPF",
    placeholder="Exemplo: MARIA | 123.456 | 6789"
).strip().upper()


if busca == "":
    st.info("Digite algo para iniciar a busca.")
    st.stop()

# ---------------------------------------------------------
# FILTRO DE CLIENTES
# ---------------------------------------------------------
df_result = df[
    df["CLIENTE"].str.contains(busca, na=False)
    | df["CPF"].str.contains(busca, na=False)
]

qtd = len(df_result)

st.markdown(f"### Resultado: **{qtd} cliente(s) encontrado(s)**")

if qtd == 0:
    st.warning("Nenhum cliente encontrado para essa consulta.")
    st.stop()

# ---------------------------------------------------------
# MOSTRAR RESULTADOS
# ---------------------------------------------------------
for cliente in df_result["CLIENTE"].unique():

    bloco = df_result[df_result["CLIENTE"] == cliente].copy()

    # pega a última ocorrência pela data ↓↓↓
    bloco = bloco.sort_values("DIA", ascending=False)
    ultimo = bloco.iloc[0]

    # SITUAÇÃO ORIGINAL → AGORA 100% correta
    # Pega exatamente a célula que está na planilha (sem resumo)
    if "SITUAÇÃO ATUAL" in bloco.columns:
        situacao = ultimo["SITUAÇÃO ATUAL"]
    elif "STATUS" in bloco.columns:
        situacao = ultimo["STATUS"]
    else:
        situacao = "NÃO INFORMADO"

    # OBSERVAÇÃO — IGNORA números e pega só a última textual
    observacao_bruta = ultimo.get("OBSERVAÇÕES", "")
    try:
        float(observacao_bruta.replace(",", "").replace(".", ""))
        observacao = ""  # era número → ignora
    except:
        observacao = observacao_bruta

    # CPF
    cpf = ultimo.get("CPF", "NÃO INFORMADO")

    # Data da última atualização
    data_atual = ultimo.get("DIA", "—")

    # -----------------------------------------------------
    # EXIBIÇÃO
    # -----------------------------------------------------
    st.markdown("---")
    st.markdown(f"## 👤 **{cliente}**")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("CPF", cpf)

    with c2:
        st.metric("Situação atual", situacao)

    with c3:
        st.metric("Última atualização", data_atual)

    st.markdown("### 📄 Observação mais recente")
    if observacao.strip() == "":
        st.info("Nenhuma observação textual disponível.")
    else:
        st.success(observacao)

