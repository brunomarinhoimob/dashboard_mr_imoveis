import streamlit as st
import pandas as pd
from datetime import date
from streamlit_autorefresh import st_autorefresh
import unicodedata

# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Análises Diárias – MR Imóveis",
    page_icon="📅",
    layout="wide",
)

# ---------------------------------------------------------
# CABEÇALHO COM TÍTULO + LOGO MR
# ---------------------------------------------------------
LOGO_PATH = "logo_mr.png"

col_titulo, col_logo = st.columns([3, 1])
with col_titulo:
    st.title("📅 Análises Diárias – Gestão à Vista")
with col_logo:
    try:
        st.image(LOGO_PATH, use_column_width=True)
    except Exception:
        pass

# Auto-refresh a cada 60 segundos
st_autorefresh(interval=60000, key="analises_diarias_refresh")

# ---------------------------------------------------------
# PLANILHA
# ---------------------------------------------------------
SHEET_ID = "1Ir_fPugLsfHNk6iH0XPCA6xM92bq8tTrn7UnunGRwCw"
GID_ANALISES = "1574157905"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID_ANALISES}"

# ---------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------
def limpar_para_data(serie):
    dt = pd.to_datetime(serie, dayfirst=True, errors="coerce")
    return dt.dt.date


def remover_acentos(texto: str) -> str:
    """
    Remove acentos para facilitar comparação de textos.
    """
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def carregar_dados():
    """
    Carrega dados da planilha SEM cache do Streamlit.
    """
    df = pd.read_csv(CSV_URL)

    # Padroniza nomes de colunas
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

    return df


# ---------------------------------------------------------
# CARREGA BASE
# ---------------------------------------------------------
df = carregar_dados()

if df.empty:
    st.error("Erro ao carregar planilha.")
    st.stop()

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------
st.sidebar.title("Filtros 🔎")

dias_validos = df["DIA"].dropna()
data_min = dias_validos.min()
data_max = dias_validos.max()

dia_escolhido = st.sidebar.date_input(
    "Dia das análises",
    value=data_max,
    min_value=data_min,
    max_value=data_max,
)

lista_equipes = sorted(df["EQUIPE"].unique())
equipe_sel = st.sidebar.selectbox("Equipe", ["Todas"] + lista_equipes)

lista_corretor = sorted(df["CORRETOR"].unique())
corretor_sel = st.sidebar.selectbox("Corretor", ["Todos"] + lista_corretor)

# ---------------------------------------------------------
# BASE DE ANÁLISES DO DIA  — APENAS "EM ANÁLISE" (SEM REANÁLISE)
# ---------------------------------------------------------
st.caption(
    f"Dia selecionado: **{dia_escolhido.strftime('%d/%m/%Y')}** "
    "• Atualiza automaticamente a cada 1 minuto."
)

# Descobre a coluna de situação original
possiveis_cols_situacao = [
    "SITUAÇÃO",
    "SITUAÇÃO ATUAL",
    "STATUS",
    "SITUACAO",
    "SITUACAO ATUAL",
]
col_situacao = next((c for c in possiveis_cols_situacao if c in df.columns), None)

if col_situacao:
    # Normaliza texto: maiúsculo, sem espaços extras, sem acentos
    status_raw = df[col_situacao].fillna("").astype(str)
    status_upper = status_raw.str.upper().str.strip()
    status_norm = status_upper.apply(remover_acentos)

    # 🔥 FILTRO DEFINITIVO:
    # 1) Começa com "EM ANALISE"
    # 2) NÃO contém "REANALISE" em nenhuma parte do texto
    mask_analise = status_norm.str.startswith("EM ANALISE") & ~status_norm.str.contains(
        "REANALISE"
    )

    df_analise_base = df[mask_analise].copy()
else:
    df_analise_base = pd.DataFrame()

if df_analise_base.empty:
    st.info("Não há lançamentos com situação começando por 'EM ANÁLISE' (sem REANÁLISE).")
    st.stop()

# Apenas o dia escolhido
df_dia = df_analise_base[df_analise_base["DIA"] == dia_escolhido]

# Filtros adicionais
if equipe_sel != "Todas":
    df_dia = df_dia[df_dia["EQUIPE"] == equipe_sel]

if corretor_sel != "Todos":
    df_dia = df_dia[df_dia["CORRETOR"] == corretor_sel]

qtde_total_dia = len(df_dia)

if qtde_total_dia == 0:
    st.warning(
        f"Nenhuma ANÁLISE (situação iniciando por 'EM ANÁLISE' e sem 'REANÁLISE') no dia "
        f"{dia_escolhido.strftime('%d/%m/%Y')} com esses filtros."
    )
    st.stop()

# ---------------------------------------------------------
# VISÃO GERAL
# ---------------------------------------------------------
c1, c2 = st.columns([1, 3])
with c1:
    st.metric("Total de análises no dia", qtde_total_dia)
with c2:
    st.markdown(
        f"### Hoje já foram registradas **{qtde_total_dia} análises** "
        f"no dia **{dia_escolhido.strftime('%d/%m/%Y')}**, "
        "considerando apenas situações que começam com **EM ANÁLISE** "
        "e **não** contêm **REANÁLISE** (sem APROVAÇÃO, VENDA, etc.)."
    )

st.markdown("---")

col_eq, col_corr = st.columns(2)

# ---------------------------------------------------------
# POR EQUIPE
# ---------------------------------------------------------
with col_eq:
    st.markdown("### 📌 Análises por Equipe (no dia)")
    analises_equipe = (
        df_dia.groupby("EQUIPE")
        .size()
        .reset_index(name="ANÁLISES")
        .sort_values("ANÁLISES", ascending=False)
    )
    total_row = pd.DataFrame(
        {"EQUIPE": ["TOTAL IMOBILIÁRIA"], "ANÁLISES": [qtde_total_dia]}
    )
    tabela_equipe = pd.concat([analises_equipe, total_row], ignore_index=True)
    st.dataframe(tabela_equipe, use_container_width=True, hide_index=True)

# ---------------------------------------------------------
# POR CORRETOR
# ---------------------------------------------------------
with col_corr:
    st.markdown("### 👥 Corretores que Subiram Análises (no dia)")
    analises_corretor = (
        df_dia.groupby("CORRETOR")
        .size()
        .reset_index(name="ANÁLISES")
        .sort_values("ANÁLISES", ascending=False)
    )
    st.dataframe(analises_corretor, use_container_width=True, hide_index=True)

st.markdown(
    "<hr style='border-color:#1f2937'>"
    "<p style='text-align:center; color:#6b7280;'>"
    "Painel de Análises Diárias — conta apenas situação iniciando por "
    "'EM ANÁLISE' e exclui qualquer linha com 'REANÁLISE'. "
    "Atualiza a cada 60 segundos."
    "</p>",
    unsafe_allow_html=True,
)
