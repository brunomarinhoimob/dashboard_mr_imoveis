import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import date, timedelta

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

    # DATA
    if "DATA" in df.columns:
        df["DIA"] = limpar_para_data(df["DATA"])
    elif "DIA" in df.columns:
        df["DIA"] = limpar_para_data(df["DIA"])
    else:
        df["DIA"] = pd.NaT

    # EQUIPE / CORRETOR
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

    # STATUS
    possiveis_cols_situacao = ["SITUAÇÃO", "SITUAÇÃO ATUAL", "STATUS", "SITUACAO", "SITUACAO ATUAL"]
    col_situacao = next((c for c in possiveis_cols_situacao if c in df.columns), None)

    df["STATUS_BASE"] = ""
    if col_situacao:
        status = df[col_situacao].fillna("").str.upper()
        df.loc[status.str.contains("EM ANÁLISE"), "STATUS_BASE"] = "EM ANÁLISE"
        df.loc[status.str.contains("REANÁLISE"), "STATUS_BASE"] = "REANÁLISE"
        df.loc[status.str.contains("APROV"), "STATUS_BASE"] = "APROVADO"
        df.loc[status.str.contains("REPROV"), "STATUS_BASE"] = "REPROVADO"
        df.loc[status.str.contains("VENDA GERADA"), "STATUS_BASE"] = "VENDA GERADA"
        df.loc[status.str.contains("VENDA INFORMADA"), "STATUS_BASE"] = "VENDA INFORMADA"

    # VGV
    if "OBSERVAÇÕES" in df.columns:
        df["VGV"] = pd.to_numeric(df["OBSERVAÇÕES"], errors="coerce").fillna(0.0)
    else:
        df["VGV"] = 0.0

    return df


df = carregar_dados()

if df.empty:
    st.error("Não foi possível carregar dados.")
    st.stop()

# ---------------------------------------------------------
# FILTRO DE PERÍODO (ULTIMOS 30 DIAS EDITÁVEIS)
# ---------------------------------------------------------

st.sidebar.title("Filtros 🔎")

dias_validos = pd.Series(df["DIA"].dropna())

if dias_validos.empty:
    data_min = data_max = date.today()
else:
    data_min = dias_validos.min()
    data_max = dias_validos.max()

# Padrão = últimos 30 dias
default_ini = data_max - timedelta(days=30)
if default_ini < data_min:
    default_ini = data_min

if "rank_eq_periodo" not in st.session_state:
    st.session_state["rank_eq_periodo"] = (default_ini, data_max)

periodo = st.sidebar.date_input(
    "Período (padrão: últimos 30 dias)",
    value=st.session_state["rank_eq_periodo"],
    min_value=data_min,
    max_value=data_max,
)

# Validação
if isinstance(periodo, (tuple, list)) and len(periodo) == 2:
    data_ini, data_fim = periodo
else:
    data_ini, data_fim = default_ini, data_max

st.session_state["rank_eq_periodo"] = (data_ini, data_fim)

# ---------------------------------------------------------
# APLICA FILTRO DE DATA
# ---------------------------------------------------------
df_periodo = df[
    (df["DIA"] >= data_ini) & (df["DIA"] <= data_fim)
]

registros_filtrados = len(df_periodo)

st.caption(
    f"Período filtrado: **{data_ini.strftime('%d/%m/%Y')}** → "
    f"**{data_fim.strftime('%d/%m/%Y')}** • Registros: **{registros_filtrados}**"
)

if df_periodo.empty:
    st.warning("Nenhum registro neste período.")
    st.stop()

# ---------------------------------------------------------
# AGRUPAMENTO POR EQUIPE
# ---------------------------------------------------------
def conta_analises(s): return s.isin(["EM ANÁLISE", "REANÁLISE"]).sum()
def conta_vendas(s): return s.isin(["VENDA GERADA", "VENDA INFORMADA"]).sum()
def conta_aprovacoes(s): return (s == "APROVADO").sum()

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

# Remove equipes zeradas
rank_eq = rank_eq[
    (rank_eq["ANALISES"] > 0)
    | (rank_eq["APROVACOES"] > 0)
    | (rank_eq["VENDAS"] > 0)
    | (rank_eq["VGV"] > 0)
]

if rank_eq.empty:
    st.info("Nenhuma equipe teve movimentação neste período.")
    st.stop()

# Taxas
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

# Ordenação
rank_eq = rank_eq.sort_values(["VENDAS", "VGV"], ascending=False).reset_index(drop=True)

# ---------------------------------------------------------
# ESTILO VISUAL DA TABELA
# ---------------------------------------------------------

st.markdown("### 📋 Tabela de Ranking das Equipes")

def zebra(row):
    cor = "#0b1120" if row.name % 2 else "#020617"
    return [f"background-color: {cor}"] * len(row)

def highlight_top3(row):
    if row.name == 0:
        return ["background-color: rgba(250, 204, 21, .25); font-weight:bold;"] * len(row)
    if row.name == 1:
        return ["background-color: rgba(148, 163, 184, .15); font-weight:bold;"] * len(row)
    if row.name == 2:
        return ["background-color: rgba(248, 250, 252, .08); font-weight:bold;"] * len(row)
    return [""] * len(row)

# Linha TOTAL imobiliária
total_row = pd.DataFrame({
    "EQUIPE": ["TOTAL IMOBILIÁRIA"],
    "ANALISES": [rank_eq["ANALISES"].sum()],
    "APROVACOES": [rank_eq["APROVACOES"].sum()],
    "VENDAS": [rank_eq["VENDAS"].sum()],
    "VGV": [rank_eq["VGV"].sum()],
    "TAXA_APROV_ANALISES": [
        (rank_eq["APROVACOES"].sum() / rank_eq["ANALISES"].sum() * 100)
        if rank_eq["ANALISES"].sum() > 0 else 0
    ],
    "TAXA_VENDAS_ANALISES": [
        (rank_eq["VENDAS"].sum() / rank_eq["ANALISES"].sum() * 100)
        if rank_eq["ANALISES"].sum() > 0 else 0
    ],
})

rank_eq_table = pd.concat([rank_eq, total_row], ignore_index=True)

styles = [
    {"selector": "th", "props": [
        ("background-color", "#0f172a"),
        ("color", "#e5e7eb"),
        ("padding", "6px"),
        ("text-align", "center"),
        ("font-weight", "bold")
    ]},
    {"selector": "tbody td", "props": [
        ("padding", "6px"),
        ("border", "0px"),
        ("font-size", "0.9rem")
    ]},
]

styled = (
    rank_eq_table
    .style
    .format({
        "VGV": "R$ {:,.2f}".format,
        "TAXA_APROV_ANALISES": "{:.1f}%".format,
        "TAXA_VENDAS_ANALISES": "{:.1f}%".format,
    })
    .set_table_styles(styles)
    .apply(zebra, axis=1)
    .apply(highlight_top3, axis=1)
)

st.dataframe(styled, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# GRÁFICO
# ---------------------------------------------------------

st.markdown("### 💰 VGV por equipe")

chart = (
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
            alt.Tooltip("TAXA_APROV_ANALISES:Q", title="% Aprov.", format=".1f"),
            alt.Tooltip("TAXA_VENDAS_ANALISES:Q", title="% Vendas", format=".1f"),
        ]
    )
    .properties(height=450)
)

st.altair_chart(chart, use_container_width=True)

st.markdown(
    "<hr><p style='text-align:center;color:#6b7280;'>Ranking por equipe baseado em análises, aprovações, vendas e VGV.</p>",
    unsafe_allow_html=True
)
