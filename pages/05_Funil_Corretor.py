import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import date

# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Funil por Corretor – MR Imóveis",
    page_icon="🧑‍💼",
    layout="wide",
)

st.title("🧑‍💼 Funil por Corretor – MR Imóveis")

st.caption(
    "Veja o funil individual de cada corretor (análises → aprovações → vendas) "
    "e planeje quantas análises/aprovações ele precisará para bater a meta de vendas."
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
# CARREGAR E PREPARAR DADOS
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
    "Período (para ver o funil do corretor)",
    value=(data_min, data_max),
    min_value=data_min,
    max_value=data_max,
)

if isinstance(periodo, tuple):
    data_ini, data_fim = periodo
else:
    data_ini, data_fim = data_min, data_max

# Filtro de corretor
lista_corretor = sorted(df["CORRETOR"].dropna().unique())
corretor_sel = st.sidebar.selectbox(
    "Corretor",
    ["Selecione um corretor"] + lista_corretor,
)

# ---------------------------------------------------------
# APLICA FILTRO DE PERÍODO
# ---------------------------------------------------------
df_periodo = df.copy()
dia_series_all = limpar_para_data(df_periodo["DIA"])
mask_data_all = (dia_series_all >= data_ini) & (dia_series_all <= data_fim)
df_periodo = df_periodo[mask_data_all]

registros_filtrados = len(df_periodo)

st.caption(
    f"Período filtrado: **{data_ini.strftime('%d/%m/%Y')}** até "
    f"**{data_fim.strftime('%d/%m/%Y')}** • "
    f"Registros considerados: **{registros_filtrados}** (todas as equipes)"
)

if corretor_sel == "Selecione um corretor":
    st.info("Selecione um corretor na barra lateral para ver o funil individual.")
    st.stop()

# ---------------------------------------------------------
# FUNIL DO CORRETOR NO PERÍODO SELECIONADO
# ---------------------------------------------------------
st.markdown(f"## 🧑‍💼 Funil do Corretor: **{corretor_sel}**")

df_cor_periodo = df_periodo[df_periodo["CORRETOR"] == corretor_sel].copy()

if df_cor_periodo.empty:
    st.warning(
        f"O corretor **{corretor_sel}** não possui registros no período selecionado."
    )
else:
    # Separando análises
    analises_em_cor = conta_analises_base(df_cor_periodo["STATUS_BASE"])   # só EM
    reanalises_cor = conta_reanalises(df_cor_periodo["STATUS_BASE"])       # só RE
    analises_total_cor = conta_analises(df_cor_periodo["STATUS_BASE"])     # EM + RE

    aprov_cor = conta_aprovacoes(df_cor_periodo["STATUS_BASE"])
    vendas_cor = conta_vendas(df_cor_periodo["STATUS_BASE"])
    vgv_cor = df_cor_periodo["VGV"].sum()

    taxa_aprov_cor = (aprov_cor / analises_em_cor * 100) if analises_em_cor > 0 else 0
    taxa_venda_analises_cor = (
        vendas_cor / analises_em_cor * 100
    ) if analises_em_cor > 0 else 0
    taxa_venda_aprov_cor = (
        vendas_cor / aprov_cor * 100
    ) if aprov_cor > 0 else 0

    # Cards principais – separando análise x reanálise
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Análises (só EM)", analises_em_cor)
    with c2:
        st.metric("Reanálises", reanalises_cor)
    with c3:
        st.metric("Análises (EM + RE)", analises_total_cor)
    with c4:
        st.metric("Aprovações", aprov_cor)
    with c5:
        st.metric("Vendas (Total)", vendas_cor)

    c6, c7, c8 = st.columns(3)
    with c6:
        st.metric(
            "VGV do corretor (período)",
            f"R$ {vgv_cor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        )
    with c7:
        st.metric("Taxa Aprov./Análises (só EM)", f"{taxa_aprov_cor:.1f}%")
    with c8:
        st.metric("Taxa Vendas/Análises (só EM)", f"{taxa_venda_analises_cor:.1f}%")

    c9, = st.columns(1)
    with c9:
        st.metric("Taxa Vendas/Aprovações", f"{taxa_venda_aprov_cor:.1f}%")

    # Tabela do funil do corretor (usando só EM como base)
    df_funil_cor = pd.DataFrame(
        {
            "Etapa": ["Análises (só EM)", "Aprovações", "Vendas"],
            "Quantidade": [analises_em_cor, aprov_cor, vendas_cor],
            "Conversão da etapa anterior (%)": [
                100.0 if analises_em_cor > 0 else 0.0,
                taxa_aprov_cor if analises_em_cor > 0 else 0.0,
                taxa_venda_aprov_cor if aprov_cor > 0 else 0.0,
            ],
        }
    )

    # 🔽 TABELA EM CIMA, GRÁFICO EMBAIXO
    st.markdown("### 📋 Tabela do Funil do Corretor (período)")
    st.dataframe(
        df_funil_cor.style.format(
            {"Conversão da etapa anterior (%)": "{:.1f}%".format}
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 📊 Gráfico do Funil do Corretor (período)")
    chart_funil_cor = (
        alt.Chart(df_funil_cor)
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
    st.altair_chart(chart_funil_cor, use_container_width=True)

# ---------------------------------------------------------
# PLANEJAMENTO INDIVIDUAL – BASEADO NOS ÚLTIMOS 3 MESES DO CORRETOR
# ---------------------------------------------------------
st.markdown("---")
st.markdown("## 📈 Planejamento de Vendas do Corretor (base últimos 3 meses)")

# Usa a base TOTAL filtrada pelo corretor
df_cor_full = df[df["CORRETOR"] == corretor_sel].copy()

if df_cor_full.empty or df_cor_full["DIA"].isna().all():
    st.info(
        f"O corretor **{corretor_sel}** ainda não possui histórico suficiente "
        "para cálculo dos últimos 3 meses."
    )
else:
    dt_cor_all = pd.to_datetime(df_cor_full["DIA"], errors="coerce")
    ref_date_cor = dt_cor_all.max()

    if pd.isna(ref_date_cor):
        st.info("Não foi possível identificar a data de referência do corretor na base.")
    else:
        limite_3m_cor = ref_date_cor - pd.DateOffset(months=3)
        mask_3m_cor = (dt_cor_all >= limite_3m_cor) & (dt_cor_all <= ref_date_cor)
        df_cor_3m = df_cor_full[mask_3m_cor].copy()

        if df_cor_3m.empty:
            st.info(
                f"O corretor **{corretor_sel}** não possui registros nos últimos 3 meses "
                f"(janela usada: {limite_3m_cor.date().strftime('%d/%m/%Y')} "
                f"até {ref_date_cor.date().strftime('%d/%m/%Y')})."
            )
        else:
            analises_cor_3m_base = conta_analises_base(df_cor_3m["STATUS_BASE"])  # só EM
            aprov_cor_3m = conta_aprovacoes(df_cor_3m["STATUS_BASE"])
            vendas_cor_3m = conta_vendas(df_cor_3m["STATUS_BASE"])

            if vendas_cor_3m > 0:
                media_analise_por_venda_cor = (
                    analises_cor_3m_base / vendas_cor_3m
                    if analises_cor_3m_base > 0 else 0
                )
                media_aprov_por_venda_cor = (
                    aprov_cor_3m / vendas_cor_3m if aprov_cor_3m > 0 else 0
                )
            else:
                media_analise_por_venda_cor = 0
                media_aprov_por_venda_cor = 0

            h1, h2, h3 = st.columns(3)
            with h1:
                st.metric("Análises (3m – só EM)", analises_cor_3m_base)
            with h2:
                st.metric("Aprovações (3m – corretor)", aprov_cor_3m)
            with h3:
                st.metric("Vendas (3m – corretor)", vendas_cor_3m)

            h4, h5 = st.columns(2)
            with h4:
                st.metric(
                    "Média de ANÁLISES por venda (3m, só EM)",
                    f"{media_analise_por_venda_cor:.1f}" if vendas_cor_3m > 0 else "—",
                )
            with h5:
                st.metric(
                    "Média de APROVAÇÕES por venda (3m)",
                    f"{media_aprov_por_venda_cor:.1f}" if vendas_cor_3m > 0 else "—",
                )

            st.caption(
                f"Janela histórica usada para o corretor **{corretor_sel}**: "
                f"de {limite_3m_cor.date().strftime('%d/%m/%Y')} "
                f"até {ref_date_cor.date().strftime('%d/%m/%Y')}."
            )

            st.markdown("### 🎯 Quantas análises/aprovações esse corretor precisa para bater a meta de vendas?")

            vendas_planejadas_cor = st.number_input(
                f"Meta de vendas no mês para {corretor_sel}",
                min_value=0,
                value=3,
                step=1,
                key="vendas_planejadas_corretor",
            )

            if vendas_planejadas_cor > 0 and vendas_cor_3m > 0:
                analises_cor_necessarias = media_analise_por_venda_cor * vendas_planejadas_cor
                aprovacoes_cor_necessarias = media_aprov_por_venda_cor * vendas_planejadas_cor

                analises_cor_necessarias_int = int(np.ceil(analises_cor_necessarias))
                aprovacoes_cor_necessarias_int = int(np.ceil(aprovacoes_cor_necessarias))

                c_cor1, c_cor2, c_cor3 = st.columns(3)
                with c_cor1:
                    st.metric("Meta de vendas (corretor)", vendas_planejadas_cor)
                with c_cor2:
                    st.metric(
                        "Análises necessárias (aprox.)",
                        f"{analises_cor_necessarias_int} análises",
                        help=(
                            f"Cálculo: {media_analise_por_venda_cor:.2f} análises/venda "
                            f"× {vendas_planejadas_cor}"
                        ),
                    )
                with c_cor3:
                    st.metric(
                        "Aprovações necessárias (aprox.)",
                        f"{aprovacoes_cor_necessarias_int} aprovações",
                        help=(
                            f"Cálculo: {media_aprov_por_venda_cor:.2f} aprovações/venda "
                            f"× {vendas_planejadas_cor}"
                        ),
                    )

                st.caption(
                    "Os números são aproximados e arredondados para cima, "
                    "baseados no histórico real desse corretor nos últimos 3 meses."
                )
            elif vendas_planejadas_cor > 0 and vendas_cor_3m == 0:
                st.info(
                    f"O corretor **{corretor_sel}** ainda não possui vendas registradas "
                    "nos últimos 3 meses para calcular as médias por venda."
                )
