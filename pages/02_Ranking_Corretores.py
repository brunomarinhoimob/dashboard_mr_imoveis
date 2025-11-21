import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import date, datetime, timedelta

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

    # Padroniza nomes de colunas
    df.columns = [c.strip().upper() for c in df.columns]

    # Data
    if "DATA" in df.columns:
        df["DIA"] = limpar_para_data(df["DATA"])
    elif "DIA" in df.columns:
        df["DIA"] = limpar_para_data(df["DIA"])
    else:
        df["DIA"] = pd.NaT

    # Equipe / Corretor
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

    # Situação / Status
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

    # VGV
    if "OBSERVAÇÕES" in df.columns:
        df["VGV"] = pd.to_numeric(df["OBSERVAÇÕES"], errors="coerce").fillna(0.0)
    else:
        df["VGV"] = 0.0

    return df

df = carregar_dados()

if df.empty:
    st.error("Não foi possível carregar dados da planilha.")
    st.stop()

# ---------------------------------------------------------
# SIDEBAR – FILTROS
# ---------------------------------------------------------
st.sidebar.title("Filtros 🔎")

dias_validos = pd.Series(df["DIA"].dropna())

if not dias_validos.empty:
    data_max = dias_validos.max()
    data_min = dias_validos.min()
else:
    data_max = date.today()
    data_min = data_max - timedelta(days=365)

# Período padrão = últimos 30 dias com base na maior data da base
default_ini = data_max - timedelta(days=30)
if default_ini < data_min:
    default_ini = data_min

if "periodo_filtro" not in st.session_state:
    st.session_state["periodo_filtro"] = (default_ini, data_max)

periodo = st.sidebar.date_input(
    "Período (padrão = últimos 30 dias)",
    value=st.session_state["periodo_filtro"],
    min_value=data_min,
    max_value=data_max,
)

st.session_state["periodo_filtro"] = periodo

if isinstance(periodo, tuple) or isinstance(periodo, list):
    if len(periodo) == 2:
        data_ini, data_fim = periodo
    else:
        data_ini, data_fim = default_ini, data_max
else:
    data_ini, data_fim = default_ini, data_max

# Filtro de equipe
lista_equipes = sorted(df["EQUIPE"].dropna().unique())
equipe_sel = st.sidebar.selectbox("Equipe (opcional)", ["Todas"] + lista_equipes)

# ---------------------------------------------------------
# APLICA FILTROS
# ---------------------------------------------------------
df_periodo = df.copy()
dia_series_all = limpar_para_data(df_periodo["DIA"])
mask = (dia_series_all >= data_ini) & (dia_series_all <= data_fim)
df_periodo = df_periodo[mask]

if equipe_sel != "Todas":
    df_periodo = df_periodo[df_periodo["EQUIPE"] == equipe_sel]

registros_filtrados = len(df_periodo)

st.caption(
    f"Período filtrado: **{data_ini.strftime('%d/%m/%Y')}** até "
    f"**{data_fim.strftime('%d/%m/%Y')}** • Registros: **{registros_filtrados}**"
)
if equipe_sel != "Todas":
    st.caption(f"Equipe filtrada: **{equipe_sel}**")

if df_periodo.empty:
    st.warning("Nenhum registro no período selecionado.")
    st.stop()

# ---------------------------------------------------------
# RANKING POR CORRETOR
# ---------------------------------------------------------
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

# Remove corretores zerados
rank_cor = rank_cor[
    (rank_cor["ANALISES"] > 0)
    | (rank_cor["APROVACOES"] > 0)
    | (rank_cor["VENDAS"] > 0)
    | (rank_cor["VGV"] > 0)
]

# Taxas
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

# Ordena e gera POSIÇÃO
rank_cor = rank_cor.sort_values(["VENDAS", "VGV"], ascending=False).reset_index(drop=True)

# Coluna de posição numérica
rank_cor.insert(0, "POSIÇÃO_NUM", rank_cor.index + 1)

# Coluna de posição formatada com medalhas
def format_posicao(pos):
    if pos == 1:
        return "🥇 1º"
    elif pos == 2:
        return "🥈 2º"
    elif pos == 3:
        return "🥉 3º"
    else:
        return f"{pos}º"

rank_cor["POSIÇÃO"] = rank_cor["POSIÇÃO_NUM"].apply(format_posicao)

# Reorganiza colunas (POSIÇÃO visível, POSIÇÃO_NUM só para lógica se quiser)
colunas_ordem = [
    "POSIÇÃO",
    "CORRETOR",
    "ANALISES",
    "APROVACOES",
    "VENDAS",
    "VGV",
    "TAXA_APROV_ANALISES",
    "TAXA_VENDAS_ANALISES",
]
rank_cor = rank_cor[colunas_ordem + ["POSIÇÃO_NUM"]]

# ---------------------------------------------------------
# ESTILO DA TABELA (1, 2 e 3 que você pediu)
# ---------------------------------------------------------
st.markdown("#### 📋 Tabela detalhada do ranking por corretor")

def zebra_rows(row):
    """Zebra nas linhas."""
    base_color_even = "#020617"  # bem escuro
    base_color_odd = "#0b1120"   # um pouco mais claro
    color = base_color_even if row.name % 2 == 0 else base_color_odd
    return [f"background-color: {color}"] * len(row)

def highlight_top3(row):
    """Destaque para os TOP 3."""
    if row.name == 0:  # 1º lugar
        return ["background-color: rgba(250, 204, 21, 0.18); font-weight: bold;"] * len(row)
    elif row.name == 1:  # 2º lugar
        return ["background-color: rgba(148, 163, 184, 0.25); font-weight: bold;"] * len(row)
    elif row.name == 2:  # 3º lugar
        return ["background-color: rgba(248, 250, 252, 0.06); font-weight: bold;"] * len(row)
    else:
        return [""] * len(row)

# Estilos de header e células
table_styles = [
    {
        "selector": "th",
        "props": [
            ("background-color", "#0f172a"),  # azul bem escuro
            ("color", "#e5e7eb"),             # cinza claro
            ("font-weight", "bold"),
            ("text-align", "center"),
            ("padding", "6px 8px"),
        ],
    },
    {
        "selector": "tbody td",
        "props": [
            ("border", "0px solid transparent"),
            ("padding", "4px 8px"),
            ("font-size", "0.9rem"),
        ],
    },
]

# Cria Styler
styled_rank = (
    rank_cor.drop(columns=["POSIÇÃO_NUM"])  # não mostra POSIÇÃO_NUM
    .style
    .format(
        {
            "VGV": "R$ {:,.2f}".format,
            "TAXA_APROV_ANALISES": "{:.1f}%".format,
            "TAXA_VENDAS_ANALISES": "{:.1f}%".format,
        }
    )
    .set_table_styles(table_styles)
    .apply(zebra_rows, axis=1)
    .apply(highlight_top3, axis=1)
    .set_properties(
        subset=["POSIÇÃO", "ANALISES", "APROVACOES", "VENDAS"],
        **{"text-align": "center"}
    )
    .set_properties(
        subset=["VGV", "TAXA_APROV_ANALISES", "TAXA_VENDAS_ANALISES"],
        **{"text-align": "right"}
    )
)

st.dataframe(
    styled_rank,
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------------
# GRÁFICO – VGV POR CORRETOR
# ---------------------------------------------------------
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
            alt.Tooltip("TAXA_APROV_ANALISES:Q", title="% Aprov./Análises", format=".1f"),
            alt.Tooltip("TAXA_VENDAS_ANALISES:Q", title="% Vendas/Análises", format=".1f"),
        ],
    )
    .properties(height=500)
)

st.altair_chart(chart_vgv, use_container_width=True)

st.markdown(
    "<hr><p style='text-align:center;color:#666;'>"
    "Ranking por corretor baseado em análises, aprovações, vendas e VGV."
    "</p>",
    unsafe_allow_html=True,
)
