import streamlit as st
import pandas as pd
from datetime import date
from streamlit_autorefresh import st_autorefresh

# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Análises Diárias – MR Imóveis",
    page_icon="📅",
    layout="wide",
)

# ---------------------------------------------------------
# CABEÇALHO COM TÍTULO + LOGO MR (DENTRO DA PÁGINA)
# ---------------------------------------------------------
LOGO_PATH = "logo_mr.png"  # precisa estar na mesma pasta deste arquivo

col_titulo, col_logo = st.columns([3, 1])
with col_titulo:
    st.title("📅 Análises Diárias – Gestão à Vista")
with col_logo:
    try:
        st.image(LOGO_PATH, use_container_width=True)
    except Exception:
        st.write("")

# Auto-refresh a cada 60 segundos (60000 ms)
st_autorefresh(interval=60000, key="analises_diarias_refresh")

# ---------------------------------------------------------
# CONFIG: LINK DA PLANILHA
# (mesmos dados do app_dashboard.py)
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
# CARREGAR DADOS
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

    return df

df = carregar_dados()

if df.empty:
    st.error("Não foi possível carregar dados da planilha. Verifique o link/gid.")
    st.stop()

# ---------------------------------------------------------
# SIDEBAR - FILTROS BÁSICOS
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

dia_padrao = data_max

dia_escolhido = st.sidebar.date_input(
    "Dia das análises",
    value=dia_padrao,
    min_value=data_min,
    max_value=data_max,
)

# Filtro Equipe
lista_equipes = sorted(df["EQUIPE"].dropna().unique())
equipe_sel = st.sidebar.selectbox("Equipe", ["Todas"] + lista_equipes)

# Filtro Corretor
lista_corretor = sorted(df["CORRETOR"].dropna().unique())
corretor_sel = st.sidebar.selectbox("Corretor", ["Todos"] + lista_corretor)

# ---------------------------------------------------------
# BASE DE ANÁLISES DO DIA
# ---------------------------------------------------------
st.caption(
    f"Dia selecionado: **{dia_escolhido.strftime('%d/%m/%Y')}** "
    f"• Atualiza automaticamente a cada 1 minuto."
)

# Base SOMENTE com análises (EM ANÁLISE / REANÁLISE)
df_analise_base = df[df["STATUS_BASE"].isin(["EM ANÁLISE", "REANÁLISE"])].copy()

if df_analise_base.empty:
    st.info("Não há análises registradas na base.")
    st.stop()

# Filtra SOMENTE análises do dia escolhido
df_dia = df_analise_base[limpar_para_data(df_analise_base["DIA"]) == dia_escolhido]

# Aplica filtros de equipe/corretor
if equipe_sel != "Todas":
    df_dia = df_dia[df_dia["EQUIPE"] == equipe_sel]
if corretor_sel != "Todos":
    df_dia = df_dia[df_dia["CORRETOR"] == corretor_sel]

qtde_total_dia = len(df_dia)

if qtde_total_dia == 0:
    st.warning(
        f"Não foram encontradas ANÁLISES para o dia "
        f"**{dia_escolhido.strftime('%d/%m/%Y')}** com os filtros atuais."
    )
    st.stop()

# ---------------------------------------------------------
# VISÃO GERAL DO DIA
# ---------------------------------------------------------
c1, c2 = st.columns([1, 3])
with c1:
    st.metric("Total de análises no dia", qtde_total_dia)
with c2:
    st.markdown(
        f"### Hoje já foram registradas **{qtde_total_dia} análises** "
        f"no dia **{dia_escolhido.strftime('%d/%m/%Y')}**."
    )

st.markdown("---")

col_eq, col_corr = st.columns(2)

# --------- QUADRO POR EQUIPE + TOTAL IMOB ---------
with col_eq:
    st.markdown("### 📌 Análises por Equipe (no dia)")
    analises_equipe = (
        df_dia.groupby("EQUIPE", as_index=False)
        .size()
        .rename(columns={"size": "ANÁLISES"})
        .sort_values("ANÁLISES", ascending=False)
    )
    total_row = pd.DataFrame(
        {"EQUIPE": ["TOTAL IMOBILIÁRIA"], "ANÁLISES": [qtde_total_dia]}
    )
    tabela_equipe = pd.concat([analises_equipe, total_row], ignore_index=True)
    st.dataframe(tabela_equipe, use_container_width=True, hide_index=True)

# --------- QUADRO POR CORRETOR ---------
with col_corr:
    st.markdown("### 👥 Corretores que Subiram Análises (no dia)")
    analises_corretor = (
        df_dia.groupby("CORRETOR", as_index=False)
        .size()
        .rename(columns={"size": "ANÁLISES"})
        .sort_values("ANÁLISES", ascending=False)
    )
    st.dataframe(analises_corretor, use_container_width=True, hide_index=True)

st.markdown(
    "<hr style='border-color:#1f2937'>"
    "<p style='text-align:center; color:#6b7280;'>"
    "Painel de Análises Diárias – ideal para TV no salão da imobiliária. "
    "Atualizado automaticamente a cada 60 segundos."
    "</p>",
    unsafe_allow_html=True,
)
