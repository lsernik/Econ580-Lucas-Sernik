import requests, unicodedata, os, shutil
import pandas as pd
from linearmodels.panel import PanelOLS, RandomEffects
import statsmodels.api as sm
import numpy as np

MUNICIPALITY_ALIASES = {
    "sao luis do paraitinga": "sao luiz do paraitinga",
    "embu":                   "embu das artes",
    "florinia":               "florinea",
}

DROP_MUNICIPALITIES = ["florinea", "sao paulo"]

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

def merge_municipality_files(tce_csv, ibge_csv, output_path):
    df_tce  = pd.read_csv(tce_csv)   # municipio, municipio_extenso
    df_ibge = pd.read_csv(ibge_csv)  # id, nome

    df_tce["nome_norm"]  = df_tce["municipio_extenso"].apply(normalize_name)
    df_ibge["nome_norm"] = df_ibge["nome"].apply(normalize_name)

    df_merged = df_tce.merge(df_ibge[["id", "nome_norm"]], on="nome_norm", how="outer")

    # Check for TCE municipalities with no IBGE match
    unmatched_tce = df_merged[df_merged["id"].isna()]["municipio_extenso"].tolist()
    if unmatched_tce:
        print(f"TCE municipalities with no IBGE match ({len(unmatched_tce)}):")
        for m in unmatched_tce:
            print(f"  - {m}")

    # Check for IBGE municipalities with no TCE match
    unmatched_ibge = df_merged[df_merged["municipio"].isna()]["nome_norm"].tolist()
    if unmatched_ibge:
        print(f"IBGE municipalities with no TCE match ({len(unmatched_ibge)}):")
        for m in unmatched_ibge:
            print(f"  - {m}")

    # Keep only matched rows
    df_out = df_merged.dropna(subset=["id", "municipio"])[["municipio", "municipio_extenso", "id"]]
    df_out.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\nSaved: {len(df_out)} matched municipalities to {output_path}")
    return df_out

def build_regression_controls_dataset(indicators_csv, age_csv, idh_xlsx, municipalities_csv, output_path):
    df_ind  = pd.read_csv(indicators_csv, index_col="ibge_id")
    df_age  = pd.read_csv(age_csv, index_col="ibge_id")
    df_mun  = pd.read_csv(municipalities_csv)
    df_idh  = pd.read_excel(idh_xlsx)

    DROP_MUNICIPALITIES = ["florinea", "sao paulo"]

    MUNICIPALITY_ALIASES = {
        "sao luis do paraitinga": "sao luiz do paraitinga",
        "embu":                   "embu das artes",
    }

    def normalize_name(text):
        text = str(text)
        text = text.replace("(SP)", "").strip()
        text = unicodedata.normalize("NFD", text)
        text = "".join(c for c in text if unicodedata.category(c) != "Mn")
        text = text.lower().strip()
        text = text.replace("-", " ").replace("'", " ")
        text = " ".join(text.split())
        return MUNICIPALITY_ALIASES.get(text, text)

    # Normalize
    df_mun["nome_norm"] = df_mun["municipio_extenso"].apply(normalize_name)
    df_idh["nome_norm"] = df_idh["Territorialidade"].apply(normalize_name)

    # Drop excluded municipalities
    df_mun = df_mun[~df_mun["nome_norm"].isin(DROP_MUNICIPALITIES)]
    df_idh = df_idh[~df_idh["nome_norm"].isin(DROP_MUNICIPALITIES)]

    # Get IDs to keep and filter SIDRA datasets
    valid_ids = set(df_mun["id"].astype(int).tolist())
    df_ind = df_ind[df_ind.index.isin(valid_ids)]
    df_age = df_age[df_age.index.isin(valid_ids)]

    # Merge IDH with municipality IDs and municipio slug via normalized name
    df_idh = df_idh.merge(df_mun[["nome_norm", "id", "municipio"]], on="nome_norm", how="left")

    # Check for unmatched municipalities
    unmatched = df_idh[df_idh["id"].isna()]["Territorialidade"].tolist()
    if unmatched:
        print(f"Warning: {len(unmatched)} unmatched municipalities in IDH:")
        for m in unmatched:
            print(f"  - {m}")

    # Drop unmatched and set index
    df_idh = df_idh.dropna(subset=["id"])
    df_idh["id"] = df_idh["id"].astype(int)
    df_idh = df_idh[["id", "municipio", "IDHM", "IDHM Renda", "IDHM Educação", "IDHM Longevidade"]].set_index("id")

    # Merge all datasets
    df = df_ind.join(df_age, how="outer")
    df = df.join(df_idh, how="left")

    df.to_csv(output_path, encoding="utf-8")
    print(f"Saved: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")

def compute_expenses(mun_dir, output_path):
    EARMARKED = [
        "TRANSFERÊNCIAS E CONVÊNIOS FEDERAIS-VINCULADOS",
        "TRANSFERÊNCIAS E CONVÊNIOS ESTADUAIS-VINCULADOS",
        "RECURSOS PRÓPRIOS DE FUNDOS ESPECIAIS DE DESPESA-VINCULADOS"
    ]
    DISCRETIONARY = [
        "TESOURO",
        "RECURSOS PRÓPRIOS DA ADMINISTRAÇÃO INDIRETA"
    ]

    results = []

    for municipio in os.listdir(mun_dir):
        mun_path = os.path.join(mun_dir, municipio)
        if not os.path.isdir(mun_path):
            continue

        for f in os.listdir(mun_path):
            if not f.endswith(".csv"):
                continue

            year = f.replace(f"despesas-{municipio}-", "").replace(".csv", "")
            try:
                year = int(year)
            except ValueError:
                print(f"Skipping unrecognized file: {f}")
                continue

            filepath = os.path.join(mun_path, f)
            try:
                df = pd.read_csv(filepath, sep=None, engine="python")
            except Exception as e:
                print(f"Error reading {filepath}: {e}")
                continue

            df = df[df["tp_despesa"] == "Valor Liquidado"].copy()

            df["vl_despesa"] = (
                df["vl_despesa"]
                .str.replace(".", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df["vl_despesa"] = pd.to_numeric(df["vl_despesa"], errors="coerce")
            df = df.dropna(subset=["vl_despesa"])

            total      = df["vl_despesa"].sum()
            total_disc = df[df["ds_fonte_recurso"].isin(DISCRETIONARY)]["vl_despesa"].sum()

            if total == 0:
                continue

            row = {
                "municipio":         municipio,
                "ano":               year,
                "total_expenditure": total,
                "total_discretionary": total_disc,
                "disc_share_total":  round(total_disc / total * 100, 4),
            }

            for func, func_df in df.groupby("ds_funcao_governo"):
                func_key  = normalize_name(func).replace(" ", "_")
                func_total = func_df["vl_despesa"].sum()
                func_disc  = func_df[func_df["ds_fonte_recurso"].isin(DISCRETIONARY)]["vl_despesa"].sum()

                # Total spending share
                row[f"share_{func_key}"]      = round(func_total / total * 100, 4) if total > 0 else 0
                # Discretionary spending share — mayoral choice variable
                row[f"disc_share_{func_key}"] = round(func_disc / total_disc * 100, 4) if total_disc > 0 else 0

            results.append(row)
            print(f"Processed: {municipio} {year}")

    df_out = pd.DataFrame(results)
    df_out.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\nSaved: {df_out.shape}")


def build_regression_dataset(controls_csv, elections_csv, expenses_csv, output_path):
    df_controls  = pd.read_csv(controls_csv)
    df_elections = pd.read_csv(elections_csv)
    df_expenses  = pd.read_csv(expenses_csv)

    df_elections["winner_2016_reelection"] = df_elections["winner_2016_reelection"].fillna(0)
    df_elections["incumbent_ran_2020"]     = df_elections["incumbent_ran_2020"].fillna(0)
    df_elections["winner_2020_reelection"] = df_elections["winner_2020_reelection"].fillna(0)

    df = df_elections.merge(df_controls, on="municipio", how="inner")
    df = df.merge(df_expenses, on="municipio", how="inner")
    df = df.loc[:, ~df.columns.duplicated()]

    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Saved: {df.shape}")
    print(f"Years: {sorted(df['ano'].unique().tolist())}")
    print(f"Municipalities: {df['municipio'].nunique()}")
    return df


def run_regression(dataset_csv, dependent_var):
    """
    dependent_var: e.g. 'disc_share_saude'
    D_it: disc_share_total --- discretionary share of total expenditure (mayoral fiscal power)
    """
    df = pd.read_csv(dataset_csv)

    if dependent_var not in df.columns:
        raise ValueError(f"Column '{dependent_var}' not found.")

    df["winner_2016_reelection"] = df["winner_2016_reelection"].fillna(0)
    df["winner_2020_reelection"] = df["winner_2020_reelection"].fillna(0)

    controls = [
        "pib_per_capita", "IDHM",
        "pct_children",
    ]

    cols_needed = [
        "municipio", "ano", dependent_var,
        "winner_2016_reelection", "winner_2020_reelection",
        "disc_share_total", "populacao",
        "n_candidates_2016", "n_candidates_2020"
    ] + controls

    df = df[cols_needed].dropna()
    df["ano"] = df["ano"].astype(int)

    # R_i varies by municipality-term
    df["R"] = np.where(
        df["ano"] <= 2020,
        1 - df["winner_2016_reelection"],
        1 - df["winner_2020_reelection"]
    )

    # N_candidates varies by municipality-term
    df["N_candidates"] = np.where(
        df["ano"] <= 2020,
        df["n_candidates_2016"],
        df["n_candidates_2020"]
    )

    # Log population
    df["log_populacao"] = np.log(df["populacao"])

    df["D_demeaned"] = df["disc_share_total"] - df["disc_share_total"].mean()
    df["R_x_D"]      = df["R"] * df["D_demeaned"]

    df = df.set_index(["municipio", "ano"])

    X_cols = [
        "R", "D_demeaned", "R_x_D",
        "log_populacao",
        "N_candidates"
    ] + controls

    X = sm.add_constant(df[X_cols])
    y = df[dependent_var]

    print(f"\n{'='*60}")
    print(f"Regression: {dependent_var}")
    print(f"{'='*60}")

    model = PanelOLS(y, X, time_effects=True, drop_absorbed=True)
    result = model.fit(cov_type="clustered", cluster_entity=True)
    print(result.summary)
    return result

import pandas as pd
import numpy as np

def generate_descriptive_stats(dataset_csv, output_tex):
    """
    Generates a LaTeX table of descriptive statistics for the regression variables.
    """
    df = pd.read_csv(dataset_csv)
    df["ano"] = df["ano"].astype(int)

    # Construct regression variables
    df["winner_2016_reelection"] = df["winner_2016_reelection"].fillna(0)
    df["winner_2020_reelection"] = df["winner_2020_reelection"].fillna(0)

    df["R"] = np.where(
        df["ano"] <= 2020,
        1 - df["winner_2016_reelection"],
        1 - df["winner_2020_reelection"]
    )

    df["N_candidates"] = np.where(
        df["ano"] <= 2020,
        df["n_candidates_2016"],
        df["n_candidates_2020"]
    )

    df["log_populacao"]  = np.log(df["populacao"])
    df["D"]              = df["disc_share_total"]
    df["D_demeaned"]     = df["disc_share_total"] - df["disc_share_total"].mean()
    df["R_x_D"]          = df["R"] * df["D_demeaned"]

    # Define variables and their display names
    variables = {
        # Dependent variables
        "disc_share_saude":              "Health (\\textit{Saúde})",
        "disc_share_educacao":           "Education (\\textit{Educação})",
        "disc_share_urbanismo":          "Urbanismo",
        "disc_share_assistencia_social": "Social Assistance",
        "disc_share_administracao":      "Administration",
        "disc_share_transporte":         "Transport",
        # Key regressors
        "R":                             "Reelection eligibility ($R_{it}$)",
        "D":                             "Discretionary share ($D_{it}$, \\%)",
        "D_demeaned":                    "Demeaned discretionary share ($\\tilde{D}_{it}$)",
        "R_x_D":                         "Interaction ($R_{it} \\times \\tilde{D}_{it}$)",
        # Controls
        "log_populacao":                 "Log population ($\\ln P_i$)",
        "N_candidates":                  "Number of candidates ($N_{it}$)",
        "pib_per_capita":                "PIB per capita (R\\$)",
        "IDHM":                          "IDHM",
        "pct_children":                  "Share of children (\\%)",
    }

    # Compute statistics
    rows = []
    for var, label in variables.items():
        if var not in df.columns:
            print(f"Warning: {var} not found in dataset, skipping.")
            continue
        col = df[var].dropna()
        rows.append({
            "Variable": label,
            "N":    int(col.count()),
            "Mean": col.mean(),
            "SD":   col.std(),
            "Min":  col.min(),
            "P25":  col.quantile(0.25),
            "P50":  col.median(),
            "P75":  col.quantile(0.75),
            "Max":  col.max(),
        })

    stats = pd.DataFrame(rows)

    # Format numbers
    def fmt(x):
        if abs(x) >= 1000:
            return f"{x:,.0f}"
        elif abs(x) >= 1:
            return f"{x:.3f}"
        elif abs(x) >= 0.001:
            return f"{x:.4f}"
        else:
            return f"{x:.2e}"

    # Write LaTeX table
    with open(output_tex, "w", encoding="utf-8") as f:
        f.write("\\begin{table}[htbp]\n")
        f.write("\\centering\n")
        f.write("\\caption{Descriptive Statistics}\n")
        f.write("\\label{tab:descriptive}\n")
        f.write("\\resizebox{\\textwidth}{!}{%\n")
        f.write("\\begin{tabular}{lrrrrrrrr}\n")
        f.write("\\hline\\hline\n")
        f.write("Variable & $N$ & Mean & SD & Min & P25 & Median & P75 & Max \\\\\n")
        f.write("\\hline\n")

        # Panel A: Dependent variables
        f.write("\\multicolumn{9}{l}{\\textit{Panel A: Dependent variables"
                " (discretionary spending share, \\%)}} \\\\\n")
        dep_vars = [
            "disc_share_saude", "disc_share_educacao", "disc_share_urbanismo",
            "disc_share_assistencia_social", "disc_share_administracao",
            "disc_share_transporte"
        ]
        for var in dep_vars:
            label = variables[var]
            row = stats[stats["Variable"] == label].iloc[0]
            f.write(f"\\quad {label} & {row['N']:,} & {fmt(row['Mean'])} & "
                    f"{fmt(row['SD'])} & {fmt(row['Min'])} & {fmt(row['P25'])} & "
                    f"{fmt(row['P50'])} & {fmt(row['P75'])} & {fmt(row['Max'])} \\\\\n")

        # Panel B: Key regressors
        f.write("\\hline\n")
        f.write("\\multicolumn{9}{l}{\\textit{Panel B: Key regressors}} \\\\\n")
        key_vars = ["R", "D", "D_demeaned", "R_x_D"]
        for var in key_vars:
            label = variables[var]
            row = stats[stats["Variable"] == label].iloc[0]
            f.write(f"\\quad {label} & {row['N']:,} & {fmt(row['Mean'])} & "
                    f"{fmt(row['SD'])} & {fmt(row['Min'])} & {fmt(row['P25'])} & "
                    f"{fmt(row['P50'])} & {fmt(row['P75'])} & {fmt(row['Max'])} \\\\\n")

        # Panel C: Controls
        f.write("\\hline\n")
        f.write("\\multicolumn{9}{l}{\\textit{Panel C: Controls}} \\\\\n")
        control_vars = ["log_populacao", "N_candidates", "pib_per_capita",
                        "IDHM", "pct_children"]
        for var in control_vars:
            label = variables[var]
            row = stats[stats["Variable"] == label].iloc[0]
            f.write(f"\\quad {label} & {row['N']:,} & {fmt(row['Mean'])} & "
                    f"{fmt(row['SD'])} & {fmt(row['Min'])} & {fmt(row['P25'])} & "
                    f"{fmt(row['P50'])} & {fmt(row['P75'])} & {fmt(row['Max'])} \\\\\n")

        f.write("\\hline\\hline\n")
        f.write("\\multicolumn{9}{l}{\\footnotesize Panel A variables are measured "
                "as percentage shares of total discretionary spending.} \\\\\n")
        f.write("\\multicolumn{9}{l}{\\footnotesize $D_{it}$ is the share of total "
                "expenditure funded by discretionary treasury resources (\\%).} \\\\\n")
        f.write("\\multicolumn{9}{l}{\\footnotesize $\\tilde{D}_{it} = D_{it} - "
                "\\bar{D}$ where $\\bar{D} = 71.4\\%$ is the sample mean.} \\\\\n")
        f.write("\\multicolumn{9}{l}{\\footnotesize PIB per capita in 2010 BRL. "
                "Population from 2010 IBGE Census.} \\\\\n")
        f.write("\\end{tabular}%\n")
        f.write("}\n")
        f.write("\\end{table}\n")

    print(f"Table saved to {output_tex}")
    return stats