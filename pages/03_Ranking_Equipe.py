import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import date

# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Ranking por Equipe – MR Imóveis",
    page_icon="👥",
    layout="wide",
)

st.title("👥 Ranking por Equipe – MR Imóveis")

st.caption(
    "Filtre o período para ver o ranking das equipes "
    "em análises, aprovações, vendas e VGV."
)

# ---------------------------------------------------------
# CONFIG: LINK DA PLANILHA
# ---------------------------------------------------------
SHEET_ID = "1Ir_fPugLsfHNk6iH0XPCA6xM92bq8tTrn7UnunGRwCw"
GID_ANALISES = "1574157905"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID_ANALISES}"

# ---------------------------------------------------------
# FUNÇÃO AUXILIAR PARA LIMPAR DATA
# ---------------------------------------------------------
def limpar_para_data(serie):
    dt = pd.to_datetime(serie, dayfirst=True, errors="coerce")
    return dt.dt.date

# ---------------------------------------------------------
# CARREGAR E PREPARAR DADOS
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def carregar_dados():
    df = pd.read_csv(CSV_URL)

    df.columns = [c.strip().upper() for c in df.columns]

    if "DATA" in df.columns:
        df["DIA"] = limpar_para_data(df["DATA"])
    elif "DIA" in df.columns:
        df["DIA"] = limpar_para_data(df["DIA"])
    else:
        df["DIA"] = pd.NaT

    for col in ["EQUIPE", "CORRETOR"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .fillna("NÃO INFORMADO")
                .astype(str)
                .str.upper()
                .str.strip()
            )
        else:
            df[col] = "NÃO INFORMADO"

    possiveis_cols_situacao = [
        "SITUAÇÃO", "SITUAÇÃO ATUAL", "STATUS",
        "SITUACAO", "SITUACAO ATUAL"
    ]
    col_situacao = None
    for c in possiveis_cols_situacao:
        if c in df.columns:
            col_situacao = c
            break

    df["STATUS_BASE"] = ""
    if col_situacao:
        status = df[col_situacao].fillna("").astype(str).str.upper()
        df.loc[status.str.contains("EM ANÁLISE"), "STATUS_BASE"] = "EM ANÁLISE"
        df.loc[status.str.contains("REANÁLISE"), "STATUS_BASE"] = "REANÁLISE"
        df.loc[status.str.contains("APROV"), "STATUS_BASE"] = "APROVADO"
        df.loc[status.str.contains("REPROV"), "STATUS_BASE"] = "REPROVADO"
        df.loc[status.str.contains("VENDA GERADA"), "STATUS_BASE"] = "VENDA GERADA"
        df.loc[status.str.contains("VENDA INFORMADA"), "STATUS_BASE"] = "VENDA INFORMADA"

    if "OBSERVAÇÕES" in df.columns:
        df["VGV"] = pd.to_numeric(df["OBSERVAÇÕES"], errors="coerce").fillna(0.0)
    else:
        df["VGV"] = 0.0

    return df


df = carregar_dados()

if df.empty:
    st.error("Não foi possível carregar dados da planilha. Verifique o link.")
    st.stop()

# ---------------------------------------------------------
# FILTRO DE PERÍODO — COM SESSION_STATE
# ---------------------------------------------------------
st.sidebar.title("Filtros 🔎")

dias_validos = pd.Series(df["DIA"].dropna())

if not dias_validos.empty:
    data_min = dias_validos.min()
    data_max = dias_validos.max()
else:
    hoje = date.today()
    data_min = hoje
    data_max = hoje

# 👇 Mantém a data fixa entre páginas
if "periodo_filtro" not in st.session_state:
    st.session_state["periodo_filtro"] = (data_min, data_max)

periodo = st.sidebar.date_input(
    "Período",
    value=st.session_state["periodo_filtro"],
    min_value=data_min,
    max_value=data_max,
)

st.session_state["periodo_filtro"] = periodo

if isinstance(periodo, tuple):
    data_ini, data_fim = periodo
else:
    data_ini, data_fim = data_min, data_max

# ---------------------------------------------------------
# APLICA FILTRO DE DATA
# ---------------------------------------------------------
df_periodo = df.copy()
dia_series_all = limpar_para_data(df_periodo["DIA"])
mask_data_all = (dia_series_all >= data_ini) & (dia_series_all <= data_fim)
df_periodo = df_periodo[mask_data_all]

registros_filtrados = len(df_periodo)

st.caption(
    f"Período filtrado: **{data_ini.strftime('%d/%m/%Y')}** até "
    f"**{data_fim.strftime('%d/%m/%Y')}** • Registros: **{registros_filtrados}**"
)

if df_periodo.empty:
    st.warning("Nenhum registro encontrado para o período filtrado.")
    st.stop()

# ---------------------------------------------------------
# AGRUPAMENTO POR EQUIPE
# ---------------------------------------------------------
st.markdown("### 📊 Resumo geral por equipe")

def conta_analises(s):
    return s.isin(["EM ANÁLISE", "REANÁLISE"]).sum()

def conta_vendas(s):
    return s.isin(["VENDA GERADA", "VENDA INFORMADA"]).sum()

def conta_aprovacoes(s):
    return (s == "APROVADO").sum()

rank_eq = (
    df_periodo.groupby("EQUIPE")
    .agg(
        ANALISES=("STATUS_BASE", conta_analises),
        APROVACOES=("STATUS_BASE", conta_aprovacoes),
        VENDAS=("STATUS_BASE", conta_vendas),
        VGV=("VGV", "sum"),
    )
    .reset_index()
)

rank_eq = rank_eq[
    (rank_eq["ANALISES"] > 0)
    | (rank_eq["APROVACOES"] > 0)
    | (rank_eq["VENDAS"] > 0)
    | (rank_eq["VGV"] > 0)
]

if rank_eq.empty:
    st.info("Nenhuma equipe com movimentação nesse período.")
    st.stop()

rank_eq["TAXA_APROV_ANALISES"] = np.where(
    rank_eq["ANALISES"] > 0,
    rank_eq["APROVACOES"] / rank_eq["ANALISES"] * 100,
    0
)

rank_eq["TAXA_VENDAS_ANALISES"] = np.where(
    rank_eq["ANALISES"] > 0,
    rank_eq["VENDAS"] / rank_eq["ANALISES"] * 100,
    0
)

rank_eq = rank_eq.sort_values(["VENDAS", "VGV"], ascending=False)

# ---------------------------------------------------------
# EXIBIÇÃO — TABELA EM CIMA, GRÁFICO EMBAIXO
# ---------------------------------------------------------

st.markdown("#### 📋 Tabela detalhada do ranking por equipe")
st.dataframe(
    rank_eq.style.format(
        {
            "VGV": "R$ {:,.2f}".format,
            "TAXA_APROV_ANALISES": "{:.1f}%".format,
            "TAXA_VENDAS_ANALISES": "{:.1f}%".format,
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown("#### 💰 VGV por equipe (período filtrado)")
chart_vgv_eq = (
    alt.Chart(rank_eq)
    .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    .encode(
        x=alt.X("VGV:Q", title="VGV (R$)"),
        y=alt.Y("EQUIPE:N", sort="-x", title="Equipe"),
        tooltip=[
            "EQUIPE",
            "ANALISES",
            "APROVACOES",
            "VENDAS",
            alt.Tooltip("VGV:Q", title="VGV"),
            alt.Tooltip("TAXA_APROV_ANALISES:Q", title="% Aprov./Análises", format=".1f"),
            alt.Tooltip("TAXA_VENDAS_ANALISES:Q", title="% Vendas/Análises", format=".1f"),
        ],
    )
    .properties(height=500)
)
st.altair_chart(chart_vgv_eq, use_container_width=True)

st.markdown(
    "<hr style='border-color:#1f2937'>"
    "<p style='text-align:center; color:#6b7280;'>"
    "Ranking por equipe baseado em análises, aprovações, vendas e VGV."
    "</p>",
    unsafe_allow_html=True,
)
