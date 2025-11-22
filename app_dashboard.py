import streamlit as st
import pandas as pd
from datetime import timedelta

from utils.leads_cache import carregar_leads, obter_timestamp_cache

# (se você usar TOKEN_SUPREMO em outro lugar, mantém aqui)
# from utils.supremo_config import TOKEN_SUPREMO

# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Dashboard Imobiliária – MR Imóveis",
    page_icon="🏠",
    layout="wide",
)

# ---------------------------------------------------------
# ESTILO (CSS)
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background-color: #050814;
        color: #f5f5f5;
    }
    section[data-testid="stSidebar"] {
        background: #111827;
        border-right: 1px solid #1f2937;
    }
    div[data-testid="stMetric"] {
        background: #111827;
        padding: 16px;
        border-radius: 16px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.45);
        border: 1px solid #1f2937;
    }
    .dataframe tbody tr:hover {
        background: #111827 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# LOGO
# ---------------------------------------------------------
LOGO_PATH = "logo_mr.png"
try:
    st.sidebar.image(LOGO_PATH, use_container_width=True)
except Exception:
    pass

# ---------------------------------------------------------
# PLANILHA – GOOGLE SHEETS
# ---------------------------------------------------------
SHEET_ID = "1Ir_fPugLsfHNk6iH0XPCA6xM92bq8tTrn7UnunGRwCw"
GID_ANALISES = "1574157905"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID_ANALISES}"


def limpar_para_data(serie: pd.Series) -> pd.Series:
    dt = pd.to_datetime(serie, dayfirst=True, errors="coerce")
    return dt.dt.date


@st.cache_data(ttl=60)
def carregar_dados_planilha() -> pd.DataFrame:
    df = pd.read_csv(CSV_URL)
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

    # STATUS BASE
    possiveis_cols_situacao = [
        "SITUAÇÃO", "SITUAÇÃO ATUAL", "STATUS",
        "SITUACAO", "SITUACAO ATUAL"
    ]
    col_situacao = next((c for c in possiveis_cols_situacao if c in df.columns), None)

    df["STATUS_BASE"] = ""
    if col_situacao:
        s = df[col_situacao].fillna("").astype(str).str.upper()
        df.loc[s.str.contains("EM ANÁLISE"), "STATUS_BASE"] = "EM ANÁLISE"
        df.loc[s.str.contains("REANÁLISE"), "STATUS_BASE"] = "REANÁLISE"
        df.loc[s.str.contains("APROV"), "STATUS_BASE"] = "APROVADO"
        df.loc[s.str.contains("REPROV"), "STATUS_BASE"] = "REPROVADO"
        df.loc[s.str.contains("VENDA GERADA"), "STATUS_BASE"] = "VENDA GERADA"
        df.loc[s.str.contains("VENDA INFORMADA"), "STATUS_BASE"] = "VENDA INFORMADA"

    # VGV
    if "OBSERVAÇÕES" in df.columns:
        df["VGV"] = pd.to_numeric(df["OBSERVAÇÕES"], errors="coerce").fillna(0)
    else:
        df["VGV"] = 0

    # NOME / CPF BASE
    possiveis_nome = ["NOME", "CLIENTE", "NOME CLIENTE", "NOME DO CLIENTE"]
    possiveis_cpf = ["CPF", "CPF CLIENTE", "CPF DO CLIENTE"]

    col_nome = next((c for c in possiveis_nome if c in df.columns), None)
    col_cpf = next((c for c in possiveis_cpf if c in df.columns), None)

    if col_nome is None:
        df["NOME_CLIENTE_BASE"] = "NÃO INFORMADO"
    else:
        df["NOME_CLIENTE_BASE"] = (
            df[col_nome]
            .fillna("NÃO INFORMADO")
            .astype(str)
            .str.upper()
            .str.strip()
        )

    if col_cpf is None:
        df["CPF_CLIENTE_BASE"] = ""
    else:
        df["CPF_CLIENTE_BASE"] = (
            df[col_cpf]
            .fillna("")
            .astype(str)
            .str.replace(r"\D", "", regex=True)
        )

    return df


df = carregar_dados_planilha()

if df.empty:
    st.error("Erro ao carregar planilha.")
    st.stop()

# ---------------------------------------------------------
# LEADS – USANDO CACHE CENTRAL
# ---------------------------------------------------------
df_leads = carregar_leads()
ts_cache = obter_timestamp_cache()

if "df_leads" not in st.session_state:
    st.session_state["df_leads"] = df_leads

# ---------------------------------------------------------
# SIDEBAR – FILTROS
# ---------------------------------------------------------
st.sidebar.title("Filtros 🔎")

dias_validos = df["DIA"].dropna()
data_min = dias_validos.min()
data_max = dias_validos.max()

data_ini_default = max(data_min, data_max - timedelta(days=30))

periodo = st.sidebar.date_input(
    "Período",
    value=(data_ini_default, data_max),
    min_value=data_min,
    max_value=data_max,
)

data_ini, data_fim = periodo

lista_equipes = sorted(df["EQUIPE"].unique())
equipe_sel = st.sidebar.selectbox("Equipe", ["Todas"] + lista_equipes)

if equipe_sel == "Todas":
    base_cor = df
else:
    base_cor = df[df["EQUIPE"] == equipe_sel]

lista_corretor = sorted(base_cor["CORRETOR"].unique())
corretor_sel = st.sidebar.selectbox("Corretor", ["Todos"] + lista_corretor)

# ---------------------------------------------------------
# FILTRO PRINCIPAL
# ---------------------------------------------------------
df_filtrado = df[
    (df["DIA"] >= data_ini) &
    (df["DIA"] <= data_fim)
].copy()

if equipe_sel != "Todas":
    df_filtrado = df_filtrado[df_filtrado["EQUIPE"] == equipe_sel]

if corretor_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["CORRETOR"] == corretor_sel]

registros_filtrados = len(df_filtrado)

# ---------------------------------------------------------
# TÍTULO
# ---------------------------------------------------------
st.title("📊 Dashboard Imobiliária – MR Imóveis")
st.caption(
    f"Período: {data_ini.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')} • "
    f"Registros filtrados: {registros_filtrados}"
)

# Mostra hora da última atualização dos leads (pra você ver que não é 1 em 1 min)
if ts_cache is not None:
    st.caption(f"🕒 Última atualização dos leads (Supremo): {ts_cache.strftime('%d/%m/%Y %H:%M:%S')}")
else:
    st.caption("🕒 Leads ainda não carregados do cache.")

# ---------------------------------------------------------
# CÁLCULOS PRINCIPAIS
# ---------------------------------------------------------
em_analise = (df_filtrado["STATUS_BASE"] == "EM ANÁLISE").sum()
reanalise = (df_filtrado["STATUS_BASE"] == "REANÁLISE").sum()
aprovacoes = (df_filtrado["STATUS_BASE"] == "APROVADO").sum()
reprovacoes = (df_filtrado["STATUS_BASE"] == "REPROVADO").sum()

analises_total = em_analise + reanalise

# VENDAS – status final por cliente
df_vendas_ref = df_filtrado[
    df_filtrado["STATUS_BASE"].isin(["VENDA GERADA", "VENDA INFORMADA"])
].copy()

if not df_vendas_ref.empty:
    df_vendas_ref["CHAVE_CLIENTE"] = (
        df_vendas_ref["NOME_CLIENTE_BASE"].fillna("NÃO INFORMADO")
        + " | "
        + df_vendas_ref["CPF_CLIENTE_BASE"].fillna("")
    )

    df_vendas_ref = df_vendas_ref.sort_values("DIA")
    df_vendas_ult = df_vendas_ref.groupby("CHAVE_CLIENTE").tail(1)

    venda_gerada = (df_vendas_ult["STATUS_BASE"] == "VENDA GERADA").sum()
    venda_informada = (df_vendas_ult["STATUS_BASE"] == "VENDA INFORMADA").sum()
    vendas_total = int(venda_gerada + venda_informada)

    vgv_total = df_vendas_ult["VGV"].sum()
    maior_vgv = df_vendas_ult["VGV"].max() if vendas_total > 0 else 0
else:
    venda_gerada = 0
    venda_informada = 0
    vendas_total = 0
    vgv_total = 0
    maior_vgv = 0

ticket_medio = (vgv_total / vendas_total) if vendas_total > 0 else 0

taxa_aprov_analise = (aprovacoes / analises_total * 100) if analises_total else 0
taxa_venda_analise = (vendas_total / analises_total * 100) if analises_total else 0
taxa_venda_aprov = (vendas_total / aprovacoes * 100) if aprovacoes else 0

# ---------------------------------------------------------
# CARDS
# ---------------------------------------------------------
st.subheader("Resumo de Análises & Vendas")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Em análise", em_analise)
c2.metric("Reanálise", reanalise)
c3.metric("Aprovações", aprovacoes)
c4.metric("Reprovações", reprovacoes)

c5, c6, c7 = st.columns(3)
c5.metric("Vendas GERADAS (clientes)", int(venda_gerada))
c6.metric("Vendas INFORMADAS (clientes)", int(venda_informada))
c7.metric("Total Vendas (clientes)", int(vendas_total))

c8, c9, c10 = st.columns(3)
c8.metric("Aprov./Análises", f"{taxa_aprov_analise:.1f}%")
c9.metric("Vendas/Análises", f"{taxa_venda_analise:.1f}%")
c10.metric("Vendas/Aprovações", f"{taxa_venda_aprov:.1f}%")

# ---------------------------------------------------------
# LEADS – RESUMO
# ---------------------------------------------------------
st.markdown("---")
st.subheader("📈 Resumo de Leads (Supremo CRM)")

df_leads_use = df_leads.copy()

if not df_leads_use.empty and "data_captura" in df_leads_use.columns:
    df_leads_use = df_leads_use.dropna(subset=["data_captura"])
    df_leads_use["data_captura_date"] = df_leads_use["data_captura"].dt.date

    df_leads_use = df_leads_use[
        (df_leads_use["data_captura_date"] >= data_ini) &
        (df_leads_use["data_captura_date"] <= data_fim)
    ]

    total_leads_periodo = len(df_leads_use)

    cL1, cL2, cL3 = st.columns(3)
    cL1.metric("Leads recebidos", total_leads_periodo)

    if "nome_corretor" in df_leads_use.columns:
        df_leads_use["nome_corretor_norm"] = (
            df_leads_use["nome_corretor"].astype(str).str.upper().str.strip()
        )

        qtd_corretor = df_leads_use["nome_corretor_norm"].nunique()
        cL2.metric("Corretores ativos", qtd_corretor)

        if qtd_corretor > 0:
            media_leads = total_leads_periodo / qtd_corretor
            cL3.metric("Média por corretor", f"{media_leads:.1f}")
        else:
            cL3.metric("Média por corretor", "-")
else:
    st.info("Nenhum lead carregado ou campo 'data_captura' ausente na base.")

# ---------------------------------------------------------
# INDICADORES DE VGV
# ---------------------------------------------------------
st.markdown("---")
st.subheader("💰 Indicadores de VGV (apenas clientes com venda)")


def format_currency(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


c11, c12, c13 = st.columns(3)
c11.metric("VGV Total", format_currency(vgv_total))
c12.metric("Ticket Médio", format_currency(ticket_medio))
c13.metric("Maior VGV", format_currency(maior_vgv))

st.markdown(
    "<hr><p style='text-align:center; color:#6b7280;'>"
    "Dashboard MR Imóveis integrado ao Google Sheets + Supremo CRM"
    "</p>",
    unsafe_allow_html=True,
)
