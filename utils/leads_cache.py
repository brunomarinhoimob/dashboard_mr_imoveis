import os
import pickle
from datetime import datetime, timedelta

import pandas as pd
import requests

from utils.supremo_config import TOKEN_SUPREMO

BASE_URL_LEADS = "https://api.supremocrm.com.br/v1/leads"

CACHE_DIR = "cache"
CACHE_FILE = os.path.join(CACHE_DIR, "leads_cache.pkl")
CACHE_TTL_MINUTES = 30

os.makedirs(CACHE_DIR, exist_ok=True)


def _ler_cache():
    if not os.path.exists(CACHE_FILE):
        return None, None

    try:
        with open(CACHE_FILE, "rb") as f:
            data = pickle.load(f)
            return data.get("df"), data.get("timestamp")
    except:
        return None, None


def _salvar_cache(df):
    try:
        payload = {"df": df, "timestamp": datetime.now()}
        with open(CACHE_FILE, "wb") as f:
            pickle.dump(payload, f)
    except:
        pass


def _get_api_page(pagina):
    headers = {"Authorization": f"Bearer {TOKEN_SUPREMO}"}
    params = {"pagina": pagina}

    try:
        r = requests.get(BASE_URL_LEADS, headers=headers, params=params, timeout=15)
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
    df_cache, ts_cache = _ler_cache()

    # 1. Se o cache existe e está DENTRO do TTL → usa imediatamente
    if df_cache is not None and ts_cache is not None:
        if datetime.now() - ts_cache < timedelta(minutes=CACHE_TTL_MINUTES):
            return df_cache

    # 2. Tenta atualizar da API
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

    # 3. SE A API FALHAR OU VIER VAZIA → USA O CACHE ANTIGO (mesmo expirado)
    if not dfs:
        if df_cache is not None:
            return df_cache  # <-- nunca mais os leads somem
        else:
            return pd.DataFrame()  # primeira execução sem cache

    # 4. API deu certo → constrói o DF novo
    df_all = pd.concat(dfs, ignore_index=True)

    if "id" in df_all.columns:
        df_all = df_all.drop_duplicates(subset="id")

    if "data_captura" in df_all.columns:
        df_all["data_captura"] = pd.to_datetime(df_all["data_captura"], errors="coerce")

    df_all = df_all.head(limit)

    # 5. SALVA no cache apenas se a API trouxe dados
    if not df_all.empty:
        _salvar_cache(df_all)

    return df_all
