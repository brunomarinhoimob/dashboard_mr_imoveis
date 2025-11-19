import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import date

# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Ranking por Corretor – MR Imóveis",
    page_icon="🏆",
    layout="wide",
)

st.title("🏆 Ranking por Corretor – MR Imóveis")

st.caption(
    "Filtre o período e (opcionalmente) uma equipe para ver o ranking de corretores "
    "em análises, aprovações, vendas e VGV."
)

# ---------------------------------------------------------
# CONFIG: LINK DA PLANILHA  (MESMO DO APP PRINCIPAL)
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
# CARREGAR E PREPARAR DADOS (IGUAL AO APP PRINCIPAL)
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def carregar_dados():
    df = pd.read_csv(CSV_URL)

    # Padroniza colunas
    df.columns = [c.strip().upper() for c in df.columns]

    # DATA / DIA
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

    # SITUAÇÃO BASE
    possiveis_cols_situacao = [
        "SITUAÇÃO",
        "SITUAÇÃO ATUAL",
        "STATUS",
        "SITUACAO",
        "SITUACAO ATUAL",
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

    # VGV (via coluna OBSERVAÇÕES) – sempre em REAL
    if "OBSERVAÇÕES" in df.columns:
        df["VGV"] = pd.to_numeric(df["OBSERVAÇÕES"], errors="coerce").fillna(0.0)
    else:
        df["VGV"] = 0.0

    return df


df = carregar_dados()

if df.empty:
    st.error("Não foi possível carregar dados da planilha. Verifique o link/gid.")
    st.stop()

# ---------------------------------------------------------
# SIDEBAR – FILTROS
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

periodo = st.sidebar.date_input(
    "Período",
    value=(data_min, data_max),
    min_value=data_min,
    max_value=data_max,
)

if isinstance(periodo, tuple):
    data_ini, data_fim = periodo
else:
    data_ini, data_fim = data_min, data_max

# Filtro opcional por equipe
lista_equipes = sorted(df["EQUIPE"].dropna().unique())
equipe_sel = st.sidebar.selectbox("Equipe (opcional)", ["Todas"] + lista_equipes)

# ---------------------------------------------------------
# APLICA FILTROS
# ---------------------------------------------------------
df_periodo = df.copy()
dia_series_all = limpar_para_data(df_periodo["DIA"])
mask_data_all = (dia_series_all >= data_ini) & (dia_series_all <= data_fim)
df_periodo = df_periodo[mask_data_all]

if equipe_sel != "Todas":
    df_periodo = df_periodo[df_periodo["EQUIPE"] == equipe_sel]

registros_filtrados = len(df_periodo)

st.caption(
    f"Período filtrado: **{data_ini.strftime('%d/%m/%Y')}** até "
    f"**{data_fim.strftime('%d/%m/%Y')}** • "
    f"Registros considerados: **{registros_filtrados}**"
)
if equipe_sel != "Todas":
    st.caption(f"Equipe filtrada: **{equipe_sel}**")

if df_periodo.empty:
    st.warning("Não há registros para o período / filtros selecionados.")
    st.stop()

# ---------------------------------------------------------
# RANKING POR CORRETOR
# ---------------------------------------------------------
st.markdown("### 📊 Resumo geral por corretor")

def conta_analises(s):
    return s.isin(["EM ANÁLISE", "REANÁLISE"]).sum()

def conta_vendas(s):
    return s.isin(["VENDA GERADA", "VENDA INFORMADA"]).sum()

def conta_aprovacoes(s):
    return (s == "APROVADO").sum()

rank_cor = (
    df_periodo.groupby("CORRETOR")
    .agg(
        ANALISES=("STATUS_BASE", conta_analises),
        APROVACOES=("STATUS_BASE", conta_aprovacoes),
        VENDAS=("STATUS_BASE", conta_vendas),
        VGV=("VGV", "sum"),
    )
    .reset_index()
)

# remove corretores totalmente zerados (sem análise, sem venda, sem VGV)
rank_cor = rank_cor[
    (rank_cor["ANALISES"] > 0)
    | (rank_cor["APROVACOES"] > 0)
    | (rank_cor["VENDAS"] > 0)
    | (rank_cor["VGV"] > 0)
]

if rank_cor.empty:
    st.info("Nenhum corretor com movimentação no período selecionado.")
    st.stop()

# Taxas de conversão
rank_cor["TAXA_APROV_ANALISES"] = np.where(
    rank_cor["ANALISES"] > 0,
    rank_cor["APROVACOES"] / rank_cor["ANALISES"] * 100,
    0,
)
rank_cor["TAXA_VENDAS_ANALISES"] = np.where(
    rank_cor["ANALISES"] > 0,
    rank_cor["VENDAS"] / rank_cor["ANALISES"] * 100,
    0,
)

# Ordenação padrão: VENDAS, depois VGV
rank_cor = rank_cor.sort_values(["VENDAS", "VGV"], ascending=False)

# ---------------------------------------------------------
# EXIBIÇÃO – TABELA EM CIMA, GRÁFICO EMBAIXO
# ---------------------------------------------------------

st.markdown("#### 📋 Tabela detalhada do ranking por corretor")
st.dataframe(
    rank_cor.style.format(
        {
            "VGV": "R$ {:,.2f}".format,
            "TAXA_APROV_ANALISES": "{:.1f}%".format,
            "TAXA_VENDAS_ANALISES": "{:.1f}%".format,
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown("#### 💰 VGV por corretor (período filtrado)")
chart_vgv = (
    alt.Chart(rank_cor)
    .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
    .encode(
        x=alt.X("VGV:Q", title="VGV (R$)"),
        y=alt.Y("CORRETOR:N", sort="-x", title="Corretor"),
        tooltip=[
            "CORRETOR",
            "ANALISES",
            "APROVACOES",
            "VENDAS",
            alt.Tooltip("VGV:Q", title="VGV"),
            alt.Tooltip(
                "TAXA_APROV_ANALISES:Q",
                title="% Aprov./Análises",
                format=".1f"
            ),
            alt.Tooltip(
                "TAXA_VENDAS_ANALISES:Q",
                title="% Vendas/Análises",
                format=".1f"
            ),
        ],
    )
    .properties(height=500)
)
st.altair_chart(chart_vgv, use_container_width=True)

st.markdown(
    "<hr style='border-color:#1f2937'>"
    "<p style='text-align:center; color:#6b7280;'>"
    "Ranking por corretor baseado em análises, aprovações, vendas e VGV do período filtrado."
    "</p>",
    unsafe_allow_html=True,
)
