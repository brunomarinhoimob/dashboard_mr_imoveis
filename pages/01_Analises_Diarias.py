import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta

# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Análises Diárias – MR Imóveis",
    page_icon="📅",
    layout="wide",
)

# ---------------------------------------------------------
# ESTILO
# ---------------------------------------------------------
st.markdown(
    """
    <style>
        .stApp {
            background-color: #050814 !important;
        }
        .metric-container {
            background-color: #111827;
            padding: 18px;
            border-radius: 16px;
            border: 1px solid #1f2937;
            box-shadow: 0 10px 25px rgba(0,0,0,0.45);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# LEITURA DA PLANILHA
# ---------------------------------------------------------
SHEET_ID = "1Ir_fPugLsfHNk6iH0XPCA6xM92bq8tTrn7UnunGRwCw"
GID_ANALISES = "1574157905"
URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID_ANALISES}"

@st.cache_data(ttl=60)
def carregar_planilha():
    df = pd.read_csv(URL)
    df.columns = [c.strip().upper() for c in df.columns]

    # Tratamento da coluna de data
    possiveis_datas = ["DATA", "DIA", "DATA DA ANÁLISE"]
    col_data = next((c for c in possiveis_datas if c in df.columns), None)

    if col_data:
        df["DIA"] = pd.to_datetime(df[col_data], errors="coerce", dayfirst=True).dt.date
    else:
        df["DIA"] = pd.NaT

    # Normalização STATUS
    df["STATUS_BASE"] = df["SITUAÇÃO"].astype(str).str.upper()

    df.loc[df["STATUS_BASE"].str.contains("EM ANÁLISE"), "STATUS_BASE"] = "EM ANÁLISE"
    df.loc[df["STATUS_BASE"].str.contains("REANÁLISE"), "STATUS_BASE"] = "REANÁLISE"

    # Normalização corretor & equipe
    for col in ["CORRETOR", "EQUIPE"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.upper().str.strip()
        else:
            df[col] = "NÃO INFORMADO"

    return df

df = carregar_planilha()

# ---------------------------------------------------------
# FILTRO DE DIA
# ---------------------------------------------------------
st.title("📅 Análises Diárias – Gestão à Vista")

lista_dias = sorted(df["DIA"].dropna().unique(), reverse=True)
dia_selecionado = st.sidebar.date_input(
    "Dia das análises",
    value=lista_dias[0] if lista_dias else date.today(),
)

df_dia = df[df["DIA"] == dia_selecionado]

# ---------------------------------------------------------
# CONTAGEM — SOMENTE “EM ANÁLISE”
# ---------------------------------------------------------
df_em_analise = df_dia[df_dia["STATUS_BASE"] == "EM ANÁLISE"]
qtde_total_dia = len(df_em_analise)

# ---------------------------------------------------------
# FRASE ESPECIAL VERSÃO 1
# ---------------------------------------------------------
st.markdown(
    f"""
    ### 🚀 **VERSÃO 1 — No dia {dia_selecionado.strftime('%d/%m/%Y')}, nossa equipe já registrou {qtde_total_dia} análises EM ANÁLISE!**
    Acelerando rumo às metas! 🔥
    """
)

# ---------------------------------------------------------
# CARD TOTAL
# ---------------------------------------------------------
st.subheader("Total de análises no dia")
st.metric(label="", value=qtde_total_dia)

# ---------------------------------------------------------
# ANALISES POR EQUIPE
# ---------------------------------------------------------
st.subheader("📌 Análises por Equipe (no dia)")

df_equipes = df_em_analise.groupby("EQUIPE").size().reset_index(name="ANÁLISES")
df_equipes = df_equipes.sort_values("ANÁLISES", ascending=False)

st.dataframe(df_equipes, use_container_width=True)

# ---------------------------------------------------------
# ANALISES POR CORRETOR
# ---------------------------------------------------------
st.subheader("👥 Corretores que Subiram Análises (no dia)")

df_corretor = df_em_analise.groupby("CORRETOR").size().reset_index(name="ANÁLISES")
df_corretor = df_corretor.sort_values("ANÁLISES", ascending=False)

st.dataframe(df_corretor, use_container_width=True)

st.markdown("---")
st.caption("Dashboard MR Imóveis • Atualizado automaticamente • VERSÃO 1")
