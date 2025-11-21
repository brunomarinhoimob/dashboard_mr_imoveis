import streamlit as st
import pandas as pd
import numpy as np
import requests
import difflib
from datetime import date, timedelta  # <- acrescentei timedelta

from utils.supremo_config import TOKEN_SUPREMO  # <- precisa ter esse arquivo com TOKEN_SUPREMO

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
# LOGO MR IMÓVEIS (coloque logo_mr.png na mesma pasta)
# ---------------------------------------------------------
LOGO_PATH = "logo_mr.png"
try:
    st.sidebar.image(LOGO_PATH, use_container_width=True)
except Exception:
    st.sidebar.write("MR Imóveis")

# ---------------------------------------------------------
# CONFIG: LINK DA PLANILHA
# ---------------------------------------------------------
SHEET_ID = "1Ir_fPugLsfHNk6iH0XPCA6xM92bq8tTrn7UnunGRwCw"
GID_ANALISES = "1574157905"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID_ANALISES}"

# ---------------------------------------------------------
# CONFIG: API LEADS SUPREMO
# ---------------------------------------------------------
BASE_URL_LEADS = "https://api.supremocrm.com.br/v1/leads"


# ---------------------------------------------------------
# FUNÇÃO AUXILIAR PARA LIMPAR DATA
# ---------------------------------------------------------
def limpar_para_data(serie):
    dt = pd.to_datetime(serie, dayfirst=True, errors="coerce")
    return dt.dt.date


# ---------------------------------------------------------
# CARREGAR DADOS – PLANILHA
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
# CARREGAR LEADS DO SUPREMO (ÚLTIMOS ~1000)
# ---------------------------------------------------------
def get_leads_page(pagina: int = 1) -> pd.DataFrame:
    headers = {"Authorization": f"Bearer {TOKEN_SUPREMO}"}
    params = {"pagina": pagina}

    try:
        resp = requests.get(BASE_URL_LEADS, headers=headers, params=params, timeout=30)
    except Exception as e:
        st.error(f"Erro de conexão com a API de leads: {e}")
        return pd.DataFrame()

    if resp.status_code != 200:
        st.error(f"Erro {resp.status_code}: {resp.text}")
        return pd.DataFrame()

    try:
        data = resp.json()
    except Exception as e:
        st.error(f"Erro ao interpretar JSON de leads: {e}")
        return pd.DataFrame()

    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        return pd.DataFrame(data["data"])
    if isinstance(data, list):
        return pd.DataFrame(data)

    st.error("Formato inesperado do retorno da API de leads.")
    st.write(data)
    return pd.DataFrame()


@st.cache_data(ttl=60)
def carregar_leads(limit: int = 1000, max_pages: int = 20) -> pd.DataFrame:
    """
    Busca os últimos 'limit' leads no Supremo, varrendo páginas.
    """
    dfs = []
    total = 0
    pagina = 1

    while total < limit and pagina <= max_pages:
        df_page = get_leads_page(pagina=pagina)
        if df_page.empty:
            break
        dfs.append(df_page)
        total += len(df_page)
        pagina += 1

    if not dfs:
        return pd.DataFrame()

    df_all = pd.concat(dfs, ignore_index=True)

    if "id" in df_all.columns:
        df_all = df_all.drop_duplicates(subset="id", keep="first")

    if len(df_all) > limit:
        df_all = df_all.head(limit)

    # trata data de captura
    if "data_captura" in df_all.columns:
        df_all["data_captura"] = pd.to_datetime(df_all["data_captura"], errors="coerce")
    return df_all


df_leads = carregar_leads()

# 🔁 Guarda no session_state para outras páginas reaproveitarem sem chamar API de novo
if "df_leads" not in st.session_state:
    st.session_state["df_leads"] = df_leads

# ---------------------------------------------------------
# SIDEBAR - FILTROS
# ---------------------------------------------------------
st.sidebar.title("Filtros 🔎")

dias_validos = pd.Series(df["DIA"].dropna())

if not dias_validos.empty:
    data_min = dias_validos.min()
    data_max = dias_validos.max()
else:
    hoje = date.today()
    data_max = hoje
    data_min = hoje - timedelta(days=30)

# 🎯 janela padrão: últimos 30 dias até a última data da base
data_ini_default = max(data_min, data_max - timedelta(days=30))

periodo = st.sidebar.date_input(
    "Período",
    value=(data_ini_default, data_max),
    min_value=data_min,
    max_value=data_max,
)

if isinstance(periodo, tuple):
    data_ini, data_fim = periodo
else:
    data_ini, data_fim = data_ini_default, data_max

# Filtro de equipe
lista_equipes = sorted(df["EQUIPE"].dropna().unique())
equipe_sel = st.sidebar.selectbox("Equipe", ["Todas"] + lista_equipes)

# Base para montar lista de corretores (dependente da equipe)
if equipe_sel == "Todas":
    base_cor = df
else:
    base_cor = df[df["EQUIPE"] == equipe_sel]

lista_corretor = sorted(base_cor["CORRETOR"].dropna().unique())
corretor_sel = st.sidebar.selectbox("Corretor", ["Todos"] + lista_corretor)

# ---------------------------------------------------------
# APLICA OS FILTROS NA BASE GOOGLE SHEETS
# ---------------------------------------------------------
df_filtrado = df.copy()

# Período
dia_series_all = limpar_para_data(df_filtrado["DIA"])
mask_data_all = (dia_series_all >= data_ini) & (dia_series_all <= data_fim)
df_filtrado = df_filtrado[mask_data_all]

# Equipe
if equipe_sel != "Todas":
    df_filtrado = df_filtrado[df_filtrado["EQUIPE"] == equipe_sel]

# Corretor
if corretor_sel != "Todos":
    df_filtrado = df_filtrado[df_filtrado["CORRETOR"] == corretor_sel]

registros_filtrados = len(df_filtrado)

# ---------------------------------------------------------
# TÍTULO / CABEÇALHO
# ---------------------------------------------------------
st.title("📊 Dashboard Imobiliária – MR Imóveis")
caption_text = (
    f"Período: **{data_ini.strftime('%d/%m/%Y')}** até **{data_fim.strftime('%d/%m/%Y')}** • "
    f"Registros filtrados: **{registros_filtrados}**"
)

if equipe_sel != "Todas":
    caption_text += f" • Equipe: **{equipe_sel}**"
if corretor_sel != "Todos":
    caption_text += f" • Corretor: **{corretor_sel}**"

st.caption(caption_text)

if df_filtrado.empty:
    st.warning("Não há registros para os filtros selecionados.")
    st.stop()

# ---------------------------------------------------------
# CÁLCULOS PRINCIPAIS (PLANILHA)
# ---------------------------------------------------------
em_analise = (df_filtrado["STATUS_BASE"] == "EM ANÁLISE").sum()
reanalise = (df_filtrado["STATUS_BASE"] == "REANÁLISE").sum()
aprovacoes = (df_filtrado["STATUS_BASE"] == "APROVADO").sum()
reprovacoes = (df_filtrado["STATUS_BASE"] == "REPROVADO").sum()
venda_gerada = (df_filtrado["STATUS_BASE"] == "VENDA GERADA").sum()
venda_informada = (df_filtrado["STATUS_BASE"] == "VENDA INFORMADA").sum()

analises_total = em_analise + reanalise
vendas_total = venda_gerada + venda_informada

taxa_aprov_analise = (aprovacoes / analises_total * 100) if analises_total > 0 else 0
taxa_venda_analise = (vendas_total / analises_total * 100) if analises_total > 0 else 0
taxa_venda_aprov = (vendas_total / aprovacoes * 100) if aprovacoes > 0 else 0

vgv_total = df_filtrado["VGV"].sum()
maior_vgv = df_filtrado["VGV"].max() if registros_filtrados > 0 else 0
ticket_medio = (vgv_total / vendas_total) if vendas_total > 0 else 0

# ---------------------------------------------------------
# VISÃO GERAL – MÉTRICAS (PLANILHA)
# ---------------------------------------------------------
st.subheader("Resumo de Análises, Aprovações e Vendas")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Em análise", em_analise)
with c2:
    st.metric("Reanálise", reanalise)
with c3:
    st.metric("Aprovações (Total)", aprovacoes)
with c4:
    st.metric("Reprovações", reprovacoes)

c5, c6, c7 = st.columns(3)
with c5:
    st.metric("Vendas GERADAS", venda_gerada)
with c6:
    st.metric("Vendas INFORMADAS", venda_informada)
with c7:
    st.metric("Vendas (Total)", vendas_total)

c8, c9, c10 = st.columns(3)
with c8:
    st.metric("Taxa aprovações / análises", f"{taxa_aprov_analise:.1f}%")
with c9:
    st.metric("Taxa vendas / análises", f"{taxa_venda_analise:.1f}%")
with c10:
    st.metric("Taxa vendas / aprovações", f"{taxa_venda_aprov:.1f}%")


# ---------------------------------------------------------
# RESUMO DE LEADS – SUPREMO CRM
# ---------------------------------------------------------
st.markdown("---")
st.subheader("📈 Resumo de Leads (Supremo CRM)")

df_leads_use = pd.DataFrame()
total_leads_periodo = 0

if df_leads.empty or "data_captura" not in df_leads.columns:
    st.info("Não foi possível carregar leads do Supremo CRM ou a coluna `data_captura` não existe.")
else:
    df_leads_use = df_leads.copy()
    df_leads_use = df_leads_use.dropna(subset=["data_captura"])
    df_leads_use["data_captura_date"] = df_leads_use["data_captura"].dt.date

    # Filtro por período
    mask_lead_data = (
        (df_leads_use["data_captura_date"] >= data_ini)
        & (df_leads_use["data_captura_date"] <= data_fim)
    )
    df_leads_use = df_leads_use[mask_lead_data]

    # Normaliza nome do corretor
    if "nome_corretor" in df_leads_use.columns:
        df_leads_use["nome_corretor_norm"] = (
            df_leads_use["nome_corretor"].astype(str).str.upper().str.strip()
        )

        # Filtro por corretor / equipe com base na planilha
        if corretor_sel != "Todos":
            alvo = corretor_sel.upper().strip()
            # aqui ainda sem fuzzy, o fuzzy entra na parte da relação
            df_leads_use = df_leads_use[
                df_leads_use["nome_corretor_norm"].str.contains(alvo, na=False)
            ]
        elif equipe_sel != "Todas":
            corretores_equipe = (
                df[df["EQUIPE"] == equipe_sel]["CORRETOR"]
                .dropna()
                .astype(str)
                .str.upper()
                .str.strip()
                .unique()
            )
            df_leads_use = df_leads_use[
                df_leads_use["nome_corretor_norm"].isin(corretores_equipe)
            ]
        # senão: todos os corretores

        total_leads_periodo = len(df_leads_use)

        col_leads1, col_leads2, col_leads3 = st.columns(3)
        with col_leads1:
            st.metric("Leads recebidos no período", total_leads_periodo)
        with col_leads2:
            st.metric(
                "Corretores com pelo menos 1 lead",
                df_leads_use["nome_corretor_norm"].nunique(),
            )
        with col_leads3:
            if df_leads_use["nome_corretor_norm"].nunique() > 0:
                media_leads_cor = total_leads_periodo / df_leads_use[
                    "nome_corretor_norm"
                ].nunique()
                st.metric("Média de leads por corretor", f"{media_leads_cor:.1f}")
            else:
                st.metric("Média de leads por corretor", "-")
    else:
        st.info("A coluna `nome_corretor` não existe no retorno dos leads.")


# ---------------------------------------------------------
# RELAÇÃO LEADS x ANÁLISES (SÓ EM ANÁLISE) – COM FUZZY MATCH
# ---------------------------------------------------------
st.markdown("---")
st.subheader("🔍 Relação Leads x Análises (só EM ANÁLISE) por Corretor")

if df_leads_use.empty or "nome_corretor" not in df_leads_use.columns:
    st.info("Não há leads suficientes para montar a relação Leads x Análises nesse período/filtro.")
else:
    # Corretores da planilha (base para referência)
    corretores_sheet_norm = (
        df["CORRETOR"]
        .dropna()
        .astype(str)
        .str.upper()
        .str.strip()
        .unique()
    )

    def map_corretor_fuzzy(nome_crm: str) -> str:
        if not isinstance(nome_crm, str):
            return "SEM NOME"
        nome_norm = nome_crm.upper().strip()
        if len(corretores_sheet_norm) == 0:
            return nome_norm
        # pega melhor similaridade
        match = difflib.get_close_matches(nome_norm, corretores_sheet_norm, n=1, cutoff=0.6)
        return match[0] if match else nome_norm

    # aplica mapeamento fuzzy
    df_leads_use["corretor_mapeado"] = df_leads_use["nome_corretor_norm"].apply(map_corretor_fuzzy)

    # Agrupa LEADS por corretor mapeado
    grp_leads_cor = (
        df_leads_use.groupby("corretor_mapeado")
        .size()
        .reset_index(name="qtd_leads")
    )

    # Agrupa ANÁLISES (só EM ANÁLISE) por corretor, usando df_filtrado já nos filtros
    df_analises_base = df_filtrado[df_filtrado["STATUS_BASE"] == "EM ANÁLISE"].copy()
    if df_analises_base.empty:
        grp_analises_cor = pd.DataFrame(columns=["corretor_norm", "qtd_analises"])
    else:
        df_analises_base["corretor_norm"] = (
            df_analises_base["CORRETOR"].astype(str).str.upper().str.strip()
        )
        grp_analises_cor = (
            df_analises_base.groupby("corretor_norm")
            .size()
            .reset_index(name="qtd_analises")
        )

    # Junta LEADS x ANÁLISES
    comp = pd.merge(
        grp_leads_cor,
        grp_analises_cor,
        left_on="corretor_mapeado",
        right_on="corretor_norm",
        how="left",
    )

    comp["qtd_analises"] = comp["qtd_analises"].fillna(0).astype(int)

    # Métricas
    comp["%_leads_viram_analise"] = (
        comp["qtd_analises"] / comp["qtd_leads"] * 100
    ).round(1)

    def calc_leads_por_analise(row):
        if row["qtd_analises"] > 0:
            return round(row["qtd_leads"] / row["qtd_analises"], 1)
        return None

    comp["leads_por_analise"] = comp.apply(calc_leads_por_analise, axis=1)

    comp = comp.sort_values("qtd_leads", ascending=False)

    # Mostra tabela resumida
    st.dataframe(
        comp[["corretor_mapeado", "qtd_leads", "qtd_analises", "%_leads_viram_analise", "leads_por_analise"]],
        use_container_width=True,
    )

    # Resumo geral da relação
    c_rel1, c_rel2, c_rel3 = st.columns(3)
    with c_rel1:
        st.metric("Corretores na relação", comp["corretor_mapeado"].nunique())
    with c_rel2:
        media_perc = comp["%_leads_viram_analise"].replace([np.inf, -np.inf], np.nan).dropna().mean()
        if pd.isna(media_perc):
            st.metric("Média % leads → análise", "—")
        else:
            st.metric("Média % leads → análise", f"{media_perc:.1f}%")
    with c_rel3:
        media_lpa = comp["leads_por_analise"].dropna().mean()
        if pd.isna(media_lpa):
            st.metric("Média leads por análise", "—")
        else:
            st.metric("Média leads por análise", f"{media_lpa:.1f}")

    st.caption(
        "• **qtd_leads** = leads recebidos no período (Supremo CRM, mapeados por similaridade para o nome do corretor da planilha)\n"
        "• **qtd_analises** = quantidade de registros **EM ANÁLISE** (sem REANÁLISE) no período, pela planilha\n"
        "• **%_leads_viram_analise** = percentual dos leads que viram análise\n"
        "• **leads_por_analise** = em média, quantos leads são necessários para gerar 1 análise"
    )

# ---------------------------------------------------------
# INDICADORES DE VGV
# ---------------------------------------------------------
st.markdown("---")
st.subheader("💰 Indicadores de VGV")

c11, c12, c13 = st.columns(3)
with c11:
    st.metric(
        "VGV Total (filtrado)",
        f"R$ {vgv_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    )
with c12:
    st.metric(
        "Ticket Médio por venda",
        f"R$ {ticket_medio:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    )
with c13:
    st.metric(
        "Maior VGV em uma venda",
        f"R$ {maior_vgv:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    )

st.markdown(
    "<hr style='border-color:#1f2937'>"
    "<p style='text-align:center; color:#6b7280;'>"
    "Dashboard MR Imóveis conectado ao Google Sheets e Supremo CRM. "
    "Atualize as fontes e, em até 1 minuto, o painel é recarregado automaticamente."
    "</p>",
    unsafe_allow_html=True,
)
