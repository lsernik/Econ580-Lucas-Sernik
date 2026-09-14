import requests, csv, unicodedata
import pandas as pd

MUNICIPALITY_ALIASES = {
    "sao luis do paraitinga": "sao luiz do paraitinga",
}

def remove_accents(text):
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

def normalize_name(text):
    text = remove_accents(text)
    text = text.lower()
    text = text.replace("-", " ")
    text = text.replace("'", " ")
    text = " ".join(text.split())
    return MUNICIPALITY_ALIASES.get(text, text)

def save_municipalities_ibge(csv_path):
    url = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/SP/municipios"
    response = requests.get(url)
    municipalities = response.json()

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "nome"])
        writer.writeheader()
        for m in municipalities:
            writer.writerow({"id": m["id"], "nome": remove_accents(m["nome"])})

    print(f"Saved {len(municipalities)} municipalities to {csv_path}")

SIDRA_TABLES = {
    "populacao":            ("200",  "2010", "93"),
    "pib_per_capita":       ("5938", "2013", "37"),
    # "salario_medio":        ("3548", "2010", "140"),  
    # "mortalidade_inf":      ("2612", "2010", "218"),
    "saneamento":           ("3218", "2010", "96"),
}

def check_table_metadata(tabela):
    """Check what territorial levels and variables a table supports."""
    url = f"https://servicodados.ibge.gov.br/api/v3/agregados/{tabela}/metadados"
    response = requests.get(url)
    meta = response.json()
    print(f"\nTable {tabela}: {meta.get('nome')}")
    print(f"  Territorial levels: {meta.get('nivelTerritorial')}")
    print(f"  Periods: {meta.get('periodicidade')}")
    print(f"  Variables: {[v['id'] for v in meta.get('variaveis', [])]}")

def fetch_sidra(name, tabela, periodo, variavel, retries=3):
    url = (
        f"https://apisidra.ibge.gov.br/values"
        f"/t/{tabela}"
        f"/n6/all"
        f"/v/{variavel}"
        f"/p/{periodo}"
    )
    print(f"Fetching {name}: {url}")
    
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=120)
            if response.status_code != 200:
                print(f"  Error {response.status_code}: {response.text[:200]}")
                check_table_metadata(tabela)
                return None
            data = response.json()
            df = pd.DataFrame(data[1:])
            df.columns = data[0].values()
            return df
        except requests.exceptions.ReadTimeout:
            print(f"  Timeout on attempt {attempt + 1}/{retries} — retrying...")
    
    print(f"  Failed after {retries} attempts: {name}")
    return None

def fetch_indicators(output_path):
    dfs = []
    for name, (tabela, periodo, variavel) in SIDRA_TABLES.items():
        df = fetch_sidra(name, tabela, periodo, variavel)
        if df is None:
            print(f"  Skipping {name}")
            continue

        cod_col = "Município (Código)"
        
        # Convert to string and check a sample value
        df[cod_col] = df[cod_col].astype(str)
        print(f"  Sample code: {df[cod_col].iloc[0]}")  # check what codes look like

        df_sp = df[df[cod_col].str.startswith("35")]
        print(f"  SP rows: {len(df_sp)}")

        df_sp = df_sp[[cod_col, "Valor"]].rename(
            columns={cod_col: "ibge_id", "Valor": name}
        )
        dfs.append(df_sp.set_index("ibge_id"))

    if not dfs:
        print("No dataframes to concat!")
        return

    result = pd.concat(dfs, axis=1)
    result.to_csv(output_path, encoding="utf-8")
    print(f"\nSaved to {output_path} ({len(result)} rows)")

def fetch_age_distribution(output_path, municipalities_csv):
    df_mun = pd.read_csv(municipalities_csv)
    ibge_ids = df_mun["id"].astype(str).tolist()

    chunk_size = 100
    chunks = [ibge_ids[i:i+chunk_size] for i in range(0, len(ibge_ids), chunk_size)]

    age_groups = {
        "0 a 4 anos":      ("93070",  "children"),
        "5 a 9 anos":      ("93084",  "children"),
        "10 a 14 anos":    ("93085",  "children"),
        "15 a 17 anos":    ("107453", "children"),
        "18 ou 19 anos":   ("111286", "children"),
        "20 a 24 anos":    ("93087",  "working_age"),
        "25 a 29 anos":    ("93088",  "working_age"),
        "30 a 34 anos":    ("93089",  "working_age"),
        "35 a 39 anos":    ("93090",  "working_age"),
        "40 a 44 anos":    ("93091",  "working_age"),
        "45 a 49 anos":    ("93092",  "working_age"),
        "50 a 54 anos":    ("93093",  "working_age"),
        "55 a 59 anos":    ("93094",  "working_age"),
        "60 a 64 anos":    ("93095",  "working_age"),
        "65 a 69 anos":    ("93096",  "working_age"),
        "70 anos ou mais": ("496",    "elderly"),
        "Total":           ("0",      "total"),
    }

    totals = {}

    for age_name, (age_id, group) in age_groups.items():
        print(f"Fetching: {age_name}...")
        for i, chunk in enumerate(chunks):
            ids_str = ",".join(chunk)
            url = (
                "https://apisidra.ibge.gov.br/values"
                f"/t/1378/n6/{ids_str}"
                "/v/93/p/2010"
                f"/c287/{age_id}"
                "/c1/0/c2/0/c455/0"
            )

            try:
                response = requests.get(url, timeout=120)
            except requests.exceptions.ReadTimeout:
                print(f"  Timeout on {age_name} chunk {i+1} — skipping")
                continue

            if response.status_code != 200 or not response.text.strip():
                print(f"  Error on {age_name} chunk {i+1}: {response.text[:100]}")
                continue

            data = response.json()
            df = pd.DataFrame(data[1:])
            df.columns = data[0].values()

            cod_col = [c for c in df.columns if "Município (Código)" in c][0]
            val_col = [c for c in df.columns if c in ("V", "Valor")][0]
            df[val_col] = pd.to_numeric(df[val_col], errors="coerce")

            for _, row in df.iterrows():
                ibge_id = row[cod_col]
                val = row[val_col]
                if ibge_id not in totals:
                    totals[ibge_id] = {"total": 0, "children": 0, "working_age": 0, "elderly": 0}
                totals[ibge_id][group] += val if pd.notna(val) else 0

    results = []
    for ibge_id, vals in totals.items():
        total = vals["total"]
        results.append({
            "ibge_id":         ibge_id,
            "pct_children":    round(vals["children"]    / total * 100, 2) if total > 0 else None,
            "pct_working_age": round(vals["working_age"] / total * 100, 2) if total > 0 else None,
            "pct_elderly":     round(vals["elderly"]     / total * 100, 2) if total > 0 else None,
        })

    df_out = pd.DataFrame(results).set_index("ibge_id")
    df_out.to_csv(output_path, encoding="utf-8")
    print(f"Saved: {df_out.shape}")
