import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import date, timedelta  # <-- acrescentei timedelta

# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Funil de Vendas – MR Imóveis",
    page_icon="🔻",
    layout="wide",
)

st.title("🔻 Funil de Vendas – MR Imóveis")

st.caption(
    "Veja o funil completo da imobiliária (análises → aprovações → vendas), "
    "planeje metas com base no histórico e compare o funil por equipe."
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
# CARREGAR E PREPARAR DADOS (PLANILHA)
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
# LEADS DO SUPREMO VINDOS DO app_dashboard (session_state)
# ---------------------------------------------------------
df_leads = st.session_state.get("df_leads", pd.DataFrame())

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
    data_min = hoje - timedelta(days=30)
    data_max = hoje

# 🔹 Janela padrão: últimos 30 dias até a última data da base
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

# Filtro opcional por equipe (para funil detalhado)
lista_equipes = sorted(df["EQUIPE"].dropna().unique())
equipe_sel = st.sidebar.selectbox(
    "Equipe (para funil detalhado)",
    ["Todas"] + lista_equipes,
)

# ---------------------------------------------------------
# APLICA FILTROS (FUNIL GERAL)
# ---------------------------------------------------------
df_periodo = df.copy()
dia_series_all = limpar_para_data(df_periodo["DIA"])
mask_data_all = (dia_series_all >= data_ini) & (dia_series_all <= data_fim)
df_periodo = df_periodo[mask_data_all]

registros_filtrados = len(df_periodo)

st.caption(
    f"Período filtrado: **{data_ini.strftime('%d/%m/%Y')}** até "
    f"**{data_fim.strftime('%d/%m/%Y')}** • "
    f"Registros considerados: **{registros_filtrados}**"
)

if df_periodo.empty:
    st.warning("Não há registros para o período selecionado.")
    st.stop()

# ---------------------------------------------------------
# LEADS NO PERÍODO (IMOBILIÁRIA INTEIRA)
# ---------------------------------------------------------
total_leads_periodo = None
if not df_leads.empty and "data_captura" in df_leads.columns:
    df_leads_use = df_leads.dropna(subset=["data_captura"]).copy()
    # garante tipo datetime
    df_leads_use["data_captura"] = pd.to_datetime(
        df_leads_use["data_captura"], errors="coerce"
    )
    df_leads_use["data_captura_date"] = df_leads_use["data_captura"].dt.date

    mask_leads = (
        (df_leads_use["data_captura_date"] >= data_ini)
        & (df_leads_use["data_captura_date"] <= data_fim)
    )
    total_leads_periodo = int(mask_leads.sum())

# ---------------------------------------------------------
# FUNÇÕES AUXILIARES DO FUNIL
# ---------------------------------------------------------
def conta_analises(s):
    """Análises totais (EM + RE) – volume."""
    return s.isin(["EM ANÁLISE", "REANÁLISE"]).sum()

def conta_analises_base(s):
    """Análises para base de conversão – SOMENTE EM ANÁLISE."""
    return (s == "EM ANÁLISE").sum()

def conta_reanalises(s):
    """Quantidade de REANÁLISE."""
    return (s == "REANÁLISE").sum()

def conta_aprovacoes(s):
    return (s == "APROVADO").sum()

def conta_vendas(s):
    return s.isin(["VENDA GERADA", "VENDA INFORMADA"]).sum()

# ---------------------------------------------------------
# FUNIL GERAL DA IMOBILIÁRIA
# ---------------------------------------------------------
st.markdown("## 🏢 Funil Geral da Imobiliária")

# Contagens gerais (respeitando o filtro de data)
analises_em = conta_analises_base(df_periodo["STATUS_BASE"])    # só EM ANÁLISE
reanalises_total = conta_reanalises(df_periodo["STATUS_BASE"])  # só REANÁLISE
analises_total = conta_analises(df_periodo["STATUS_BASE"])      # EM + RE (volume)
aprov_total = conta_aprovacoes(df_periodo["STATUS_BASE"])
vendas_total = conta_vendas(df_periodo["STATUS_BASE"])
vgv_total = df_periodo["VGV"].sum()

taxa_aprov_analise = (
    aprov_total / analises_em * 100 if analises_em > 0 else 0
)
taxa_venda_analise = (
    vendas_total / analises_em * 100 if analises_em > 0 else 0
)
taxa_venda_aprov = (
    vendas_total / aprov_total * 100 if aprov_total > 0 else 0
)

# Cards principais – agora com LEADS (CRM)
col_leads_card, col1, col2, col3, col4, col5 = st.columns(6)

with col_leads_card:
    if total_leads_periodo is None:
        st.metric("Leads (CRM)", "-")
    else:
        st.metric("Leads (CRM)", total_leads_periodo)

with col1:
    st.metric("Análises (só EM)", analises_em)
with col2:
    st.metric("Reanálises", reanalises_total)
with col3:
    st.metric("Análises (EM + RE)", analises_total)
with col4:
    st.metric("Aprovações", aprov_total)
with col5:
    st.metric("Vendas (Total)", vendas_total)

col_vgv, col_t1, col_t2, col_t3 = st.columns(4)
with col_vgv:
    st.metric(
        "VGV Total",
        f"R$ {vgv_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
    )
with col_t1:
    st.metric("Taxa Aprov./Análises (só EM)", f"{taxa_aprov_analise:.1f}%")
with col_t2:
    st.metric("Taxa Vendas/Análises (só EM)", f"{taxa_venda_analise:.1f}%")
with col_t3:
    st.metric("Taxa Vendas/Aprovações", f"{taxa_venda_aprov:.1f}%")

# Tabela resumindo o funil geral (base de conversão só EM)
df_funil_geral = pd.DataFrame(
    {
        "Etapa": ["Análises (só EM)", "Aprovações", "Vendas"],
        "Quantidade": [analises_em, aprov_total, vendas_total],
        "Conversão da etapa anterior (%)": [
            100.0 if analises_em > 0 else 0.0,
            taxa_aprov_analise if analises_em > 0 else 0.0,
            taxa_venda_aprov if aprov_total > 0 else 0.0,
        ],
    }
)

# 🔽 TABELA EM CIMA, GRÁFICO EMBAIXO
st.markdown("### 📋 Tabela do Funil Geral")
st.dataframe(
    df_funil_geral.style.format(
        {"Conversão da etapa anterior (%)": "{:.1f}%".format}
    ),
    use_container_width=True,
    hide_index=True,
)

st.markdown("### 📊 Gráfico do Funil Geral (Análises → Aprovações → Vendas)")
chart_funil = (
    alt.Chart(df_funil_geral)
    .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
    .encode(
        x=alt.X("Quantidade:Q", title="Quantidade"),
        y=alt.Y(
            "Etapa:N",
            sort=["Análises (só EM)", "Aprovações", "Vendas"],
            title="Etapa",
        ),
        tooltip=[
            "Etapa",
            "Quantidade",
            alt.Tooltip(
                "Conversão da etapa anterior (%)",
                title="Conversão",
                format=".1f",
            ),
        ],
    )
    .properties(height=300)
)
st.altair_chart(chart_funil, use_container_width=True)

# ---------------------------------------------------------
# PLANEJAMENTO DA IMOBILIÁRIA (ÚLTIMOS 3 MESES)
# + SITUAÇÃO ATUAL DO PERÍODO FILTRADO
# ---------------------------------------------------------
st.markdown("---")
st.markdown("## 📈 Planejamento de Vendas da Imobiliária (base últimos 3 meses)")

if df["DIA"].isna().all():
    st.info("Não há datas válidas na base para calcular os últimos 3 meses.")
else:
    dt_all = pd.to_datetime(df["DIA"], errors="coerce")
    ref_date = dt_all.max()

    if pd.isna(ref_date):
        st.info("Não foi possível identificar a data de referência na base.")
    else:
        limite_3m = ref_date - pd.DateOffset(months=3)
        mask_3m = (dt_all >= limite_3m) & (dt_all <= ref_date)
        df_3m = df[mask_3m].copy()

        if df_3m.empty:
            st.info(
                f"A base não possui registros nos últimos 3 meses "
                f"(janela usada: {limite_3m.date().strftime('%d/%m/%Y')} "
                f"até {ref_date.date().strftime('%d/%m/%Y')})."
            )
        else:
            analises_3m_base = conta_analises_base(df_3m["STATUS_BASE"])  # só EM ANÁLISE
            aprov_3m = conta_aprovacoes(df_3m["STATUS_BASE"])
            vendas_3m = conta_vendas(df_3m["STATUS_BASE"])

            if vendas_3m > 0:
                media_analise_por_venda_3m = (
                    analises_3m_base / vendas_3m if analises_3m_base > 0 else 0
                )
                media_aprov_por_venda_3m = (
                    aprov_3m / vendas_3m if aprov_3m > 0 else 0
                )
            else:
                media_analise_por_venda_3m = 0
                media_aprov_por_venda_3m = 0

            # Métricas históricas (3 meses)
            c_hist1, c_hist2, c_hist3 = st.columns(3)
            with c_hist1:
                st.metric("Análises (3m – só EM)", analises_3m_base)
            with c_hist2:
                st.metric("Aprovações (últimos 3 meses)", aprov_3m)
            with c_hist3:
                st.metric("Vendas (últimos 3 meses)", vendas_3m)

            c_hist4, c_hist5 = st.columns(2)
            with c_hist4:
                st.metric(
                    "Média de ANÁLISES por venda (3m, só EM)",
                    f"{media_analise_por_venda_3m:.1f}" if vendas_3m > 0 else "—",
                )
            with c_hist5:
                st.metric(
                    "Média de APROVAÇÕES por venda (3m)",
                    f"{media_aprov_por_venda_3m:.1f}" if vendas_3m > 0 else "—",
                )

            st.caption(
                f"Janela histórica usada: de {limite_3m.date().strftime('%d/%m/%Y')} "
                f"até {ref_date.date().strftime('%d/%m/%Y')}."
            )

            # Situação atual no período selecionado
            st.markdown("### 📌 Situação atual no período filtrado")
            c_at1, c_at2 = st.columns(2)
            with c_at1:
                st.metric(
                    "Análises já feitas no período (só EM)",
                    analises_em
                )
            with c_at2:
                st.metric(
                    "Vendas já realizadas no período",
                    vendas_total
                )

            # Planejamento de metas
            st.markdown("### 🎯 Quantas análises/aprovações preciso para bater a meta de vendas da imobiliária?")

            vendas_planejadas = st.number_input(
                "Vendas desejadas no mês (imobiliária inteira)",
                min_value=0,
                value=10,
                step=1,
                key="vendas_planejadas_imob",
            )

            if vendas_planejadas > 0 and vendas_3m > 0:
                analises_necessarias = media_analise_por_venda_3m * vendas_planejadas
                aprovacoes_necessarias = media_aprov_por_venda_3m * vendas_planejadas

                analises_necessarias_int = int(np.ceil(analises_necessarias))
                aprovacoes_necessarias_int = int(np.ceil(aprovacoes_necessarias))

                c_calc1, c_calc2, c_calc3 = st.columns(3)
                with c_calc1:
                    st.metric("Meta de vendas (mês)", vendas_planejadas)
                with c_calc2:
                    st.metric(
                        "Análises necessárias (aprox.)",
                        f"{analises_necessarias_int} análises",
                        help=f"Cálculo: {media_analise_por_venda_3m:.2f} análises/venda × {vendas_planejadas}",
                    )
                with c_calc3:
                    st.metric(
                        "Aprovações necessárias (aprox.)",
                        f"{aprovacoes_necessarias_int} aprovações",
                        help=f"Cálculo: {media_aprov_por_venda_3m:.2f} aprovações/venda × {vendas_planejadas}",
                    )

                st.caption(
                    "Os números são aproximados e arredondados para cima, "
                    "baseados no comportamento real da imobiliária nos últimos 3 meses."
                )
            elif vendas_planejadas > 0 and vendas_3m == 0:
                st.info(
                    "Ainda não há vendas registradas nos últimos 3 meses para calcular as médias por venda."
                )

# ---------------------------------------------------------
# FUNIL POR EQUIPE (VISÃO COMPARATIVA)
# ---------------------------------------------------------
st.markdown("---")
st.markdown("## 👥 Funil por Equipe (comparativo)")

rank_eq_funil = (
    df_periodo.groupby("EQUIPE")
    .agg(
        ANALISES=("STATUS_BASE", conta_analises),           # EM + RE (volume)
        ANALISES_BASE=("STATUS_BASE", conta_analises_base), # só EM ANÁLISE (conversão)
        REANALISES=("STATUS_BASE", conta_reanalises),       # só REANÁLISE
        APROVACOES=("STATUS_BASE", conta_aprovacoes),
        VENDAS=("STATUS_BASE", conta_vendas),
        VGV=("VGV", "sum"),
    )
    .reset_index()
)

rank_eq_funil = rank_eq_funil[
    (rank_eq_funil["ANALISES"] > 0)
    | (rank_eq_funil["APROVACOES"] > 0)
    | (rank_eq_funil["VENDAS"] > 0)
    | (rank_eq_funil["VGV"] > 0)
]

if rank_eq_funil.empty:
    st.info("Nenhuma equipe com movimentação no período selecionado.")
else:
    rank_eq_funil["TAXA_APROV_ANALISES"] = np.where(
        rank_eq_funil["ANALISES_BASE"] > 0,
        rank_eq_funil["APROVACOES"] / rank_eq_funil["ANALISES_BASE"] * 100,
        0,
    )
    rank_eq_funil["TAXA_VENDAS_ANALISES"] = np.where(
        rank_eq_funil["ANALISES_BASE"] > 0,
        rank_eq_funil["VENDAS"] / rank_eq_funil["ANALISES_BASE"] * 100,
        0,
    )
    rank_eq_funil["TAXA_VENDAS_APROV"] = np.where(
        rank_eq_funil["APROVACOES"] > 0,
        rank_eq_funil["VENDAS"] / rank_eq_funil["APROVACOES"] * 100,
        0,
    )

    rank_eq_funil = rank_eq_funil.sort_values(["VENDAS", "VGV"], ascending=False)

    # 🔽 TABELA EM CIMA, GRÁFICO EMBAIXO
    st.markdown("### 📋 Tabela do Funil por Equipe")
    st.dataframe(
        rank_eq_funil.style.format(
            {
                "VGV": "R$ {:,.2f}".format,
                "TAXA_APROV_ANALISES": "{:.1f}%".format,
                "TAXA_VENDAS_ANALISES": "{:.1f}%".format,
                "TAXA_VENDAS_APROV": "{:.1f}%".format,
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 💰 VGV por Equipe")
    chart_eq_vgv = (
        alt.Chart(rank_eq_funil)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("VGV:Q", title="VGV (R$)"),
            y=alt.Y("EQUIPE:N", sort="-x", title="Equipe"),
            tooltip=[
                "EQUIPE",
                alt.Tooltip("ANALISES_BASE:Q", title="Análises (só EM)"),
                alt.Tooltip("REANALISES:Q", title="Reanálises"),
                alt.Tooltip("ANALISES:Q", title="Análises (EM + RE)"),
                "APROVACOES",
                "VENDAS",
                alt.Tooltip("VGV:Q", title="VGV"),
                alt.Tooltip(
                    "TAXA_APROV_ANALISES:Q",
                    title="% Aprov./Análises (só EM)",
                    format=".1f",
                ),
                alt.Tooltip(
                    "TAXA_VENDAS_ANALISES:Q",
                    title="% Vendas/Análises (só EM)",
                    format=".1f",
                ),
                alt.Tooltip(
                    "TAXA_VENDAS_APROV:Q",
                    title="% Vendas/Aprovações",
                    format=".1f",
                ),
            ],
        )
        .properties(height=400)
    )
    st.altair_chart(chart_eq_vgv, use_container_width=True)

# ---------------------------------------------------------
# FUNIL DETALHADO + PLANEJAMENTO POR EQUIPE
# ---------------------------------------------------------
st.markdown("---")
st.markdown("## 🔍 Funil detalhado e planejamento por equipe")

if equipe_sel == "Todas":
    st.info("Selecione uma equipe específica na barra lateral para ver o funil e o planejamento dessa equipe.")
else:
    df_eq = df_periodo[df_periodo["EQUIPE"] == equipe_sel]

    if df_eq.empty:
        st.warning(f"A equipe **{equipe_sel}** não possui registros no período selecionado.")
    else:
        analises_eq_em = conta_analises_base(df_eq["STATUS_BASE"])   # só EM
        reanalises_eq = conta_reanalises(df_eq["STATUS_BASE"])       # só RE
        analises_eq_total = conta_analises(df_eq["STATUS_BASE"])     # EM + RE
        aprov_eq = conta_aprovacoes(df_eq["STATUS_BASE"])
        vendas_eq = conta_vendas(df_eq["STATUS_BASE"])
        vgv_eq = df_eq["VGV"].sum()

        taxa_aprov_eq = (
            aprov_eq / analises_eq_em * 100 if analises_eq_em > 0 else 0
        )
        taxa_venda_analises_eq = (
            vendas_eq / analises_eq_em * 100 if analises_eq_em > 0 else 0
        )
        taxa_venda_aprov_eq = (
            vendas_eq / aprov_eq * 100 if aprov_eq > 0 else 0
        )

        st.markdown(f"### Equipe: **{equipe_sel}**")

        # Cards separando análise x reanálise na equipe
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("Análises (só EM)", analises_eq_em)
        with c2:
            st.metric("Reanálises", reanalises_eq)
        with c3:
            st.metric("Análises (EM + RE)", analises_eq_total)
        with c4:
            st.metric("Aprovações", aprov_eq)
        with c5:
            st.metric("Vendas (Total)", vendas_eq)

        c6, c7, c8 = st.columns(3)
        with c6:
            st.metric(
                "VGV da equipe",
                f"R$ {vgv_eq:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            )
        with c7:
            st.metric("Taxa Aprov./Análises (só EM)", f"{taxa_aprov_eq:.1f}%")
        with c8:
            st.metric("Taxa Vendas/Análises (só EM)", f"{taxa_venda_analises_eq:.1f}%")

        c9, = st.columns(1)
        with c9:
            st.metric("Taxa Vendas/Aprovações", f"{taxa_venda_aprov_eq:.1f}%")

        # ---------------------------------------------
        # PLANEJAMENTO POR EQUIPE – ÚLTIMOS 3 MESES
        # ---------------------------------------------
        st.markdown("### 📊 Planejamento de vendas dessa equipe (base últimos 3 meses)")

        # Usa a base TOTAL mas filtrando pela equipe
        df_eq_full = df[df["EQUIPE"] == equipe_sel].copy()

        if df_eq_full["DIA"].isna().all():
            st.info("Não há datas válidas na base para calcular os últimos 3 meses dessa equipe.")
        else:
            dt_eq_all = pd.to_datetime(df_eq_full["DIA"], errors="coerce")
            ref_date_eq = dt_eq_all.max()

            if pd.isna(ref_date_eq):
                st.info("Não foi possível identificar a data de referência da equipe na base.")
            else:
                limite_3m_eq = ref_date_eq - pd.DateOffset(months=3)
                mask_3m_eq = (dt_eq_all >= limite_3m_eq) & (dt_eq_all <= ref_date_eq)
                df_eq_3m = df_eq_full[mask_3m_eq].copy()

                if df_eq_3m.empty:
                    st.info(
                        f"A equipe **{equipe_sel}** não possui registros nos últimos 3 meses "
                        f"(janela usada: {limite_3m_eq.date().strftime('%d/%m/%Y')} "
                        f"até {ref_date_eq.date().strftime('%d/%m/%Y')})."
                    )
                else:
                    analises_eq_3m_base = conta_analises_base(df_eq_3m["STATUS_BASE"])  # só EM ANÁLISE
                    aprov_eq_3m = conta_aprovacoes(df_eq_3m["STATUS_BASE"])
                    vendas_eq_3m = conta_vendas(df_eq_3m["STATUS_BASE"])

                    if vendas_eq_3m > 0:
                        media_analise_por_venda_eq = (
                            analises_eq_3m_base / vendas_eq_3m
                            if analises_eq_3m_base > 0 else 0
                        )
                        media_aprov_por_venda_eq = (
                            aprov_eq_3m / vendas_eq_3m if aprov_eq_3m > 0 else 0
                        )
                    else:
                        media_analise_por_venda_eq = 0
                        media_aprov_por_venda_eq = 0

                    h1, h2, h3 = st.columns(3)
                    with h1:
                        st.metric("Análises (3m – só EM)", analises_eq_3m_base)
                    with h2:
                        st.metric("Aprovações (3m – equipe)", aprov_eq_3m)
                    with h3:
                        st.metric("Vendas (3m – equipe)", vendas_eq_3m)

                    h4, h5 = st.columns(2)
                    with h4:
                        st.metric(
                            "Média de ANÁLISES por venda (equipe, 3m, só EM)",
                            f"{media_analise_por_venda_eq:.1f}" if vendas_eq_3m > 0 else "—",
                        )
                    with h5:
                        st.metric(
                            "Média de APROVAÇÕES por venda (equipe, 3m)",
                            f"{media_aprov_por_venda_eq:.1f}" if vendas_eq_3m > 0 else "—",
                        )

                    st.caption(
                        f"Janela histórica usada para a equipe **{equipe_sel}**: "
                        f"de {limite_3m_eq.date().strftime('%d/%m/%Y')} "
                        f"até {ref_date_eq.date().strftime('%d/%m/%Y')}."
                    )

                    st.markdown("#### 🎯 Quantas análises/aprovações essa equipe precisa para bater a meta de vendas?")

                    vendas_planejadas_eq = st.number_input(
                        f"Vendas desejadas no mês para a equipe {equipe_sel}",
                        min_value=0,
                        value=5,
                        step=1,
                        key="vendas_planejadas_equipe",
                    )

                    if vendas_planejadas_eq > 0 and vendas_eq_3m > 0:
                        analises_eq_necessarias = media_analise_por_venda_eq * vendas_planejadas_eq
                        aprovacoes_eq_necessarias = media_aprov_por_venda_eq * vendas_planejadas_eq

                        analises_eq_necessarias_int = int(np.ceil(analises_eq_necessarias))
                        aprovacoes_eq_necessarias_int = int(np.ceil(aprovacoes_eq_necessarias))

                        c_eq1, c_eq2, c_eq3 = st.columns(3)
                        with c_eq1:
                            st.metric("Meta de vendas (equipe)", vendas_planejadas_eq)
                        with c_eq2:
                            st.metric(
                                "Análises necessárias (aprox.)",
                                f"{analises_eq_necessarias_int} análises",
                                help=(
                                    f"Cálculo: {media_analise_por_venda_eq:.2f} análises/venda "
                                    f"× {vendas_planejadas_eq}"
                                ),
                            )
                        with c_eq3:
                            st.metric(
                                "Aprovações necessárias (aprox.)",
                                f"{aprovacoes_eq_necessarias_int} aprovações",
                                help=(
                                    f"Cálculo: {media_aprov_por_venda_eq:.2f} aprovações/venda "
                                    f"× {vendas_planejadas_eq}"
                                ),
                            )

                        st.caption(
                            "Os números são aproximados e arredondados para cima, "
                            "baseados no histórico real dessa equipe nos últimos 3 meses."
                        )
                    elif vendas_planejadas_eq > 0 and vendas_eq_3m == 0:
                        st.info(
                            f"A equipe **{equipe_sel}** ainda não possui vendas registradas nos últimos 3 meses "
                            "para calcular as médias por venda."
                        )
