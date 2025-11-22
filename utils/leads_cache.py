import os
import pickle
from datetime import datetime, timedelta

import pandas as pd
import requests

from utils.supremo_config import TOKEN_SUPREMO

# ---------------------------------------------------------
# CONFIGURAÇÃO DO CACHE
# ---------------------------------------------------------
BASE_URL_LEADS = "https://api.supremocrm.com.br/v1/leads"

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "leads_cache.pkl")
CACHE_TTL_MINUTES = 30  # tempo de vida do cache em minutos

os.makedirs(CACHE_DIR, exist_ok=True)


def _ler_cache():
    """Lê o cache do disco. Retorna (df, timestamp) ou (None, None)."""
    if not os.path.exists(CACHE_FILE):
        return None, None

    try:
        with open(CACHE_FILE, "rb") as f:
            data = pickle.load(f)
            return data.get("df"), data.get("timestamp")
    except:
        return None, None


def _salvar_cache(df):
    """Salva o cache SEM nunca quebrar o app."""
    try:
        payload = {"df": df, "timestamp": datetime.now()}
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(payload, f)
    except:
        pass


def _get_api_page(pagina):
    """Busca uma página da API. Se falhar, retorna DF vazio (sem mostrar erro na tela)."""
    headers = {"Authorization": f"Bearer {TOKEN_SUPREMO}"}
    params = {"pagina": pagina}

    try:
        r = requests.get(BASE_URL_LEADS, headers=headers, params=params, timeout=30)
        if r.status_code != 200:
            return pd.DataFrame()
        data = r.json()
    except:
        return pd.DataFrame()

    if isinstance(data, dict) and "data" in data:
        return pd.DataFrame(data["data"])

    if isinstance(data, list):
        return pd.DataFrame(data)

    return pd.DataFrame()


def carregar_leads(limit=1000, max_pages=100):
    """
    Lógica segura:
    1. Lê cache.
    2. Se tiver cache recente → usa.
    3. Se a API funcionar → atualiza cache.
    4. Se a API falhar → usa o cache antigo SEMPRE.
    """

    df_cache, ts_cache = _ler_cache()

    # 1 — se tem cache e está dentro do TTL → usa ele (NÃO chama API)
    if df_cache is not None and ts_cache is not None:
        if datetime.now() - ts_cache < timedelta(minutes=CACHE_TTL_MINUTES):
            return df_cache

    # 2 — tenta atualizar via API
    dfs = []
    total = 0
    pagina = 1

    while total < limit and pagina <= max_pages:
        df_page = _get_api_page(pagina)
        if df_page.empty:
            break
        dfs.append(df_page)
        total += len(df_page)
        pagina += 1

    # 3 — se API NÃO respondeu → usa cache antigo (mesmo expirado!)
    if not dfs:
        if df_cache is not None:
            return df_cache
        else:
            return pd.DataFrame()  # realmente não temos nada ainda

    # 4 — API respondeu, então atualiza o cache
    df_all = pd.concat(dfs, ignore_index=True)

    if "id" in df_all.columns:
        df_all = df_all.drop_duplicates(subset="id")

    if "data_captura" in df_all.columns:
        df_all["data_captura"] = pd.to_datetime(df_all["data_captura"], errors="coerce")

    df_all = df_all.head(limit)

    _salvar_cache(df_all)

    return df_all


def obter_timestamp_cache():
    """
    Retorna apenas o timestamp do cache (ou None).
    Serve para mostrar no dashboard quando os leads foram atualizados pela última vez.
    """
    _, ts_cache = _ler_cache()
    return ts_cache
