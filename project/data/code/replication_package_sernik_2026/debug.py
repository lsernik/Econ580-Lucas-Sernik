import requests, unicodedata, os
import pandas as pd

# For TSE_api

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

def find_missing_election_results(election_csv_path, municipalities_csv_path):
    df_election = pd.read_csv(election_csv_path)
    df_municipalities = pd.read_csv(municipalities_csv_path)

    # Normalize both for comparison
    df_election['municipio_norm'] = df_election['municipio'].apply(
        normalize_name
    )
    df_municipalities['nome_norm'] = df_municipalities['nome'].apply(
        normalize_name
    )

    election_names = set(df_election['municipio_norm'])
    missing = df_municipalities[~df_municipalities['nome_norm'].isin(election_names)]

    print(f"Found {len(missing)} municipalities with no election results:")
    for _, row in missing.iterrows():
        print(f"  - {row['nome']}")

    return missing[['id', 'nome']]

# For IBGE_api

def debug_age(municipalities_csv):
    df_mun = pd.read_csv(municipalities_csv)
    ibge_ids = df_mun["id"].astype(str).tolist()[:5]  # just 5 municipalities
    ids_str = ",".join(ibge_ids)

    # try requesting just one age group explicitly
    url = (
        "https://apisidra.ibge.gov.br/values"
        f"/t/1378/n6/{ids_str}"
        "/v/93/p/2010"
        "/c287/93070"   # just "0 a 4 anos"
        "/c1/0/c2/0/c455/0"
    )
    print(f"URL: {url}")
    response = requests.get(url, timeout=120)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:500]}")

def get_age_categories():
    meta_url = "https://servicodados.ibge.gov.br/api/v3/agregados/1378/metadados"
    meta = requests.get(meta_url).json()
    for c in meta.get("classificacoes", []):
        if c["id"] == 287:
            print("All age categories:")
            for cat in c.get("categorias", []):
                print(f"  id={cat['id']}, nome={cat['nome']}, nivel={cat['nivel']}")

def debug_expenses(mun_dir):
    print(f"Directories in mun_dir: {os.listdir(mun_dir)[:5]}")
    
    first_mun = os.listdir(mun_dir)[0]
    mun_path = os.path.join(mun_dir, first_mun)
    print(f"\nFirst municipality: {first_mun}")
    print(f"Is directory: {os.path.isdir(mun_path)}")
    print(f"Files inside: {os.listdir(mun_path)[:5]}")
    
    # Try reading the first csv
    for f in os.listdir(mun_path):
        print(f"\nFile: {f}")
        print(f"Ends with .csv: {f.endswith('.csv')}")
        filepath = os.path.join(mun_path, f)
        try:
            df = pd.read_csv(filepath, sep=None, engine="python", nrows=3)
            print(f"tp_despesa values: {df['tp_despesa'].unique().tolist()}")
        except Exception as e:
            print(f"Error: {e}")
        break

def debug_tp_despesa(mun_dir):
    first_mun = os.listdir(mun_dir)[0]
    mun_path = os.path.join(mun_dir, first_mun)
    
    for f in sorted(os.listdir(mun_path)):
        if not f.endswith(".csv"):
            continue
        filepath = os.path.join(mun_path, f)
        df = pd.read_csv(filepath, sep=None, engine="python", usecols=["tp_despesa"])
        print(f"{f}: {df['tp_despesa'].unique().tolist()}")

def debug_datasets(controls_csv, elections_csv, expenses_csv):
    df_controls  = pd.read_csv(controls_csv, nrows=3)
    df_elections = pd.read_csv(elections_csv, nrows=3)
    df_expenses  = pd.read_csv(expenses_csv, nrows=3)

    print("=== CONTROLS ===")
    print(df_controls.columns.tolist())
    print(df_controls.head(2))

    print("\n=== ELECTIONS ===")
    print(df_elections.columns.tolist())
    print(df_elections.head(2))

    print("\n=== EXPENSES ===")
    print(df_expenses.columns.tolist())
    print(df_expenses.head(2))

def fix_filenames(mun_dir):
    for municipio in os.listdir(mun_dir):
        mun_path = os.path.join(mun_dir, municipio)
        if not os.path.isdir(mun_path):
            continue
        for f in os.listdir(mun_path):
            if not f.endswith(".csv"):
                continue
            if ".zip.csv" in f:
                old = os.path.join(mun_path, f)
                new = os.path.join(mun_path, f.replace(".zip.csv", ".csv"))
                os.rename(old, new)
                print(f"Renamed: {f} -> {os.path.basename(new)}")
            elif ".zip" in f and f.endswith(".csv"):
                old = os.path.join(mun_path, f)
                new = os.path.join(mun_path, f.replace(".zip", ""))
                os.rename(old, new)
                print(f"Renamed: {f} -> {os.path.basename(new)}")

def fix_sao_luis(mun_dir):
    old_path = os.path.join(mun_dir, "sao-luis-do-paraitinga")
    new_path = os.path.join(mun_dir, "sao-luiz-do-paraitinga")
    
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        print("Renamed: sao-luis-do-paraitinga -> sao-luiz-do-paraitinga")
        
        # Also rename the files inside
        for f in os.listdir(new_path):
            if "sao-luis" in f:
                old_file = os.path.join(new_path, f)
                new_file = os.path.join(new_path, f.replace("sao-luis", "sao-luiz"))
                os.rename(old_file, new_file)
                print(f"  Renamed file: {f} -> {f.replace('sao-luis', 'sao-luiz')}")
    else:
        print("sao-luis-do-paraitinga not found — already correct or doesn't exist")

def describe_dataset_latex(csv_path):
    df = pd.read_csv(csv_path)

    print(f"% Dataset: {csv_path}")
    print(f"% Shape: {df.shape[0]} rows x {df.shape[1]} columns\n")

    # Descriptive statistics
    desc = df.describe().T
    desc = desc[["count", "mean", "std", "min", "max"]]
    desc.columns = ["N", "Mean", "Std. Dev.", "Min", "Max"]

    print("\\begin{table}[htbp]")
    print("\\centering")
    print("\\caption{Descriptive Statistics}")
    print("\\label{tab:descriptive_stats}")
    print("\\begin{tabular}{lrrrrr}")
    print("\\hline\\hline")
    print("Variable & N & Mean & Std. Dev. & Min & Max \\\\")
    print("\\hline")

    for col, row in desc.iterrows():
        n    = int(row["N"])
        mean = f"{row['Mean']:.4f}"
        std  = f"{row['Std. Dev.']:.4f}"
        mn   = f"{row['Min']:.4f}"
        mx   = f"{row['Max']:.4f}"
        # Escape underscores for LaTeX
        col_latex = col.replace("_", "\\_")
        print(f"{col_latex} & {n} & {mean} & {std} & {mn} & {mx} \\\\")

    print("\\hline\\hline")
    print("\\end{tabular}")
    print("\\end{table}")

    # Missing values
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    if not missing.empty:
        print("\n% Missing Values:")
        for col, count in missing.items():
            print(f"% - {col}: {count} ({round(count / len(df) * 100, 2)}%)")

def check_disc_share_variance(dataset_csv):
    df = pd.read_csv(dataset_csv)
    
    print("=== disc_share_total ===")
    print(f"Mean:    {df['disc_share_total'].mean():.4f}")
    print(f"Std:     {df['disc_share_total'].std():.4f}")
    print(f"Min:     {df['disc_share_total'].min():.4f}")
    print(f"Max:     {df['disc_share_total'].max():.4f}")
    print(f"CV:      {df['disc_share_total'].std() / df['disc_share_total'].mean():.4f}")
    
    # Check correlation between R and R_x_D with and without demeaning
    df["R"]       = df["winner_2016_reelection"].fillna(0).astype(int)
    df["D"]       = df["disc_share_total"]
    df["D_dem"]   = df["D"] - df["D"].mean()
    df["R_x_D"]   = df["R"] * df["D"]
    df["R_x_D_dem"] = df["R"] * df["D_dem"]
    
    print(f"\nCorr(R, R_x_D) without demeaning: {df['R'].corr(df['R_x_D']):.4f}")
    print(f"Corr(R, R_x_D) with demeaning:    {df['R'].corr(df['R_x_D_dem']):.4f}")

def check_disc_wealth_correlation(dataset_csv):
    df = pd.read_csv(dataset_csv)
    
    print("Corr(disc_share_total, pib_per_capita):", 
          df["disc_share_total"].corr(df["pib_per_capita"]))
    print("Corr(disc_share_total, IDHM):", 
          df["disc_share_total"].corr(df["IDHM"]))
    print("Corr(disc_share_total, populacao):", 
          df["disc_share_total"].corr(df["populacao"]))