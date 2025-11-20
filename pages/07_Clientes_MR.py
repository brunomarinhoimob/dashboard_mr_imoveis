import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

# ---------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Clientes MR – MR Imóveis",
    page_icon="🧑‍💼",
    layout="wide",
)

# ---------------------------------------------------------
# LOGO MR IMÓVEIS
# ---------------------------------------------------------
LOGO_PATH = "logo_mr.png"

col_tit, col_logo = st.columns([3, 1])
with col_tit:
    st.title("🧑‍💼 Página de Clientes – MR Imóveis")
    st.caption(
        "Busque clientes pelo nome (parcial) ou CPF e veja o histórico de análises, "
        "aprovações, vendas, situação atual, corretor responsável e a última observação registrada."
    )
with col_logo:
    try:
        st.image(LOGO_PATH, use_container_width=True)
    except Exception:
        st.write("MR Imóveis")

# ---------------------------------------------------------
# FUNÇÃO AUXILIAR PARA LIMPAR DATA
# ---------------------------------------------------------
def limpar_para_data(serie):
    dt = pd.to_datetime(serie, dayfirst=True, errors="coerce")
    return dt.dt.date

# ---------------------------------------------------------
# CONFIG: LINK DA PLANILHA
# ---------------------------------------------------------
SHEET_ID = "1Ir_fPugLsfHNk6iH0XPCA6xM92bq8tTrn7UnunGRwCw"
GID_ANALISES = "1574157905"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID_ANALISES}"

# ---------------------------------------------------------
# CARREGAR E PREPARAR DADOS
# ---------------------------------------------------------
@st.cache_data(ttl=60)
def carregar_dados():
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

    # -------------------------------------------------
    # CONSTRUTORA / EMPREENDIMENTO (para última mov.)
    # -------------------------------------------------
    possiveis_construtora = ["CONSTRUTORA", "INCORPORADORA"]
    possiveis_empreend = ["EMPREENDIMENTO", "PRODUTO", "IMÓVEL", "IMOVEL"]

    col_construtora = None
    for c in possiveis_construtora:
        if c in df.columns:
            col_construtora = c
            break

    col_empreend = None
    for c in possiveis_empreend:
        if c in df.columns:
            col_empreend = c
            break

    if col_construtora is None:
        df["CONSTRUTORA_BASE"] = "NÃO INFORMADO"
    else:
        df["CONSTRUTORA_BASE"] = (
            df[col_construtora].fillna("NÃO INFORMADO").astype(str).str.upper().str.strip()
        )

    if col_empreend is None:
        df["EMPREENDIMENTO_BASE"] = "NÃO INFORMADO"
    else:
        df["EMPREENDIMENTO_BASE"] = (
            df[col_empreend].fillna("NÃO INFORMADO").astype(str).str.upper().str.strip()
        )

    # STATUS BASE + COLUNA ORIGINAL DE SITUAÇÃO
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

        # Situação ORIGINAL – exatamente como na célula (só em maiúsculo e sem espaços extras)
        df["SITUACAO_ORIGINAL"] = (
            df[col_situacao].fillna("").astype(str).str.upper().str.strip()
        )
    else:
        df["SITUACAO_ORIGINAL"] = "NÃO INFORMADO"

    # OBSERVAÇÕES – guarda texto original e extrai VGV numérico
    if "OBSERVAÇÕES" in df.columns:
        df["OBSERVACOES_RAW"] = (
            df["OBSERVAÇÕES"]
            .fillna("")
            .astype(str)
            .str.strip()
        )
        df["VGV"] = pd.to_numeric(df["OBSERVAÇÕES"], errors="coerce").fillna(0.0)
    else:
        df["OBSERVACOES_RAW"] = ""
        df["VGV"] = 0.0

    # TENTA IDENTIFICAR COLUNA DE NOME E CPF DO CLIENTE
    possiveis_nome = ["NOME", "CLIENTE", "NOME CLIENTE", "NOME DO CLIENTE"]
    possiveis_cpf = ["CPF", "CPF CLIENTE", "CPF DO CLIENTE"]

    col_nome = None
    for c in possiveis_nome:
        if c in df.columns:
            col_nome = c
            break

    col_cpf = None
    for c in possiveis_cpf:
        if c in df.columns:
            col_cpf = c
            break

    # Nome base
    if col_nome is None:
        df["NOME_CLIENTE_BASE"] = "NÃO INFORMADO"
    else:
        df["NOME_CLIENTE_BASE"] = (
            df[col_nome].fillna("NÃO INFORMADO").astype(str).str.upper().str.strip()
        )

    # CPF base (apenas dígitos)
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


df = carregar_dados()

if df.empty:
    st.error("Não foi possível carregar dados da planilha. Verifique o link.")
    st.stop()

# ---------------------------------------------------------
# BARRA LATERAL – BUSCA
# ---------------------------------------------------------
st.sidebar.title("Busca de clientes 🔎")

tipo_busca = st.sidebar.radio(
    "Buscar por:",
    ("Nome (parcial)", "CPF"),
)

termo = st.sidebar.text_input(
    "Digite o nome ou CPF do cliente",
    placeholder="Ex: MARIA / 12345678901",
)

st.sidebar.caption(
    "• Nome: pode digitar só uma parte (ex: 'SILVA')\n"
    "• CPF: digite só números (não precisa de ponto ou traço)"
)

# ---------------------------------------------------------
# FILTRO POR BUSCA
# ---------------------------------------------------------
df_resultado = pd.DataFrame()

if termo.strip():
    termo_limpo = termo.strip().upper()

    if tipo_busca.startswith("Nome"):
        df_resultado = df[
            df["NOME_CLIENTE_BASE"].str.contains(termo_limpo, na=False)
        ].copy()
    else:
        termo_cpf = "".join(ch for ch in termo if ch.isdigit())
        df_resultado = df[
            df["CPF_CLIENTE_BASE"].str.contains(termo_cpf, na=False)
        ].copy()

# ---------------------------------------------------------
# EXIBIÇÃO DOS RESULTADOS
# ---------------------------------------------------------
if not termo.strip():
    st.info("Digite um nome ou CPF na lateral para iniciar a busca.")
elif df_resultado.empty:
    st.warning("Nenhum cliente encontrado com esse critério de busca.")
else:
    # Chave única por cliente
    df_resultado["CHAVE_CLIENTE"] = (
        df_resultado["NOME_CLIENTE_BASE"].fillna("NÃO INFORMADO")
        + " | "
        + df_resultado["CPF_CLIENTE_BASE"].fillna("")
    )

    # Funções auxiliares
    def conta_analises(s):
        return s.isin(["EM ANÁLISE", "REANÁLISE"]).sum()

    def conta_aprovacoes(s):
        return (s == "APROVADO").sum()

    def conta_vendas(s):
        return s.isin(["VENDA GERADA", "VENDA INFORMADA"]).sum()

    # Resumo por cliente
    resumo = (
        df_resultado.groupby("CHAVE_CLIENTE")
        .agg(
            NOME=("NOME_CLIENTE_BASE", "first"),
            CPF=("CPF_CLIENTE_BASE", "first"),
            ANALISES=("STATUS_BASE", conta_analises),
            APROVACOES=("STATUS_BASE", conta_aprovacoes),
            VENDAS=("STATUS_BASE", conta_vendas),
            VGV=("VGV", "sum"),
            ULT_STATUS=("SITUACAO_ORIGINAL", lambda x: x.iloc[-1] if len(x) > 0 else ""),
            ULT_DATA=("DIA", lambda x: x.max()),
        )
        .reset_index()
    )

    st.markdown(
        f"### 🔎 Resultado da busca – {len(resumo)} cliente(s) encontrado(s)"
    )

    # Tabela geral
    st.markdown("#### 📋 Visão geral")
    st.dataframe(
        resumo[
            ["NOME", "CPF", "ULT_STATUS", "ULT_DATA", "ANALISES", "APROVACOES", "VENDAS", "VGV"]
        ]
        .sort_values(["VENDAS", "VGV"], ascending=False)
        .style.format({"VGV": "R$ {:,.2f}".format}),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### 💳 Detalhes por cliente (cards)")

    # Função para checar se uma observação é numérica
    def observacao_e_numero(txt: str) -> bool:
        if not txt:
            return False
        t = (
            txt.upper()
            .replace("R$", "")
            .replace(".", "")
            .replace(",", "")
            .replace(" ", "")
        )
        return t.isdigit()

    # Cards para cada cliente
    for _, row in resumo.sort_values(["VENDAS", "VGV"], ascending=False).iterrows():
        chave = row["CHAVE_CLIENTE"]
        df_cli = df_resultado[df_resultado["CHAVE_CLIENTE"] == chave].copy()

        # Ordena por data para pegar a última linha (última movimentação)
        df_cli = df_cli.sort_values("DIA")
        ultima_linha = df_cli.iloc[-1]

        # Construtora / Empreendimento / Corretor da última movimentação
        ult_constr = ultima_linha.get("CONSTRUTORA_BASE", "NÃO INFORMADO")
        ult_empr = ultima_linha.get("EMPREENDIMENTO_BASE", "NÃO INFORMADO")
        ult_corretor = ultima_linha.get("CORRETOR", "NÃO INFORMADO")

        # Pega somente observações não numéricas
        obs_validas = [
            obs for obs in df_cli["OBSERVACOES_RAW"].fillna("")
            if obs and not observacao_e_numero(obs)
        ]
        ultima_obs = obs_validas[-1] if obs_validas else ""

        # Separa análise x reanálise
        analises_em = (df_cli["STATUS_BASE"] == "EM ANÁLISE").sum()
        reanalises = (df_cli["STATUS_BASE"] == "REANÁLISE").sum()
        analises_total = analises_em + reanalises

        with st.container():
            st.markdown("---")
            st.markdown(f"##### 👤 {row['NOME']}")

            col_top1, col_top2 = st.columns(2)
            with col_top1:
                cpf_fmt = row["CPF"]
                if cpf_fmt:
                    st.write(f"**CPF:** {cpf_fmt}")
                else:
                    st.write("**CPF:** não informado")
                st.write(f"**Situação atual:** {row['ULT_STATUS'] or 'NÃO INFORMADO'}")
                st.write(f"**Corretor responsável (última movimentação):** {ult_corretor}")
                st.write(f"**Construtora (última movimentação):** {ult_constr}")
                st.write(f"**Empreendimento (última movimentação):** {ult_empr}")
                if ultima_obs:
                    st.write(f"**Última observação:** {ultima_obs}")
            with col_top2:
                if pd.notna(row["ULT_DATA"]):
                    st.write(f"**Última movimentação:** {row['ULT_DATA'].strftime('%d/%m/%Y')}")
                else:
                    st.write("**Última movimentação:** não informada")

            # Métricas separando análise / reanálise
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Análises (só EM)", int(analises_em))
            with m2:
                st.metric("Reanálises", int(reanalises))
            with m3:
                st.metric("Análises (EM + RE)", int(analises_total))

            m4, m5, m6 = st.columns(3)
            with m4:
                st.metric("Aprovações", int(row["APROVACOES"]))
            with m5:
                st.metric("Vendas", int(row["VENDAS"]))
            with m6:
                st.metric(
                    "VGV total",
                    f"R$ {row['VGV']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
