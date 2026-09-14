import unicodedata, os
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

def generate_election_summaries(base_dir, csv_2016_path, csv_2020_path):
    df_2016 = pd.read_csv(csv_2016_path, sep=None, engine='python')
    df_2020 = pd.read_csv(csv_2020_path, sep=None, engine='python')

    # Normalize municipality names in both dataframes once
    df_2016['municipio_norm'] = df_2016['Município'].apply(normalize_name)
    df_2020['municipio_norm'] = df_2020['Município'].apply(normalize_name)

    for municipio in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, municipio)
        if not os.path.isdir(folder_path):
            continue

        # Normalize folder name the same way
        municipio_norm = remove_accents(municipio.upper().replace("-", " "))

        mun_2016 = df_2016[df_2016['municipio_norm'] == municipio_norm]
        mun_2020 = df_2020[df_2020['municipio_norm'] == municipio_norm]

        if mun_2016.empty and mun_2020.empty:
            continue

        # 2016 winner
        winner_2016 = mun_2016[mun_2016['Situação de totalização'] == 'Eleito']
        winner_2016_reelection = winner_2016['Reeleição'].values[0] == 'S' if not winner_2016.empty else None

        # Did the 2016 incumbent run in 2020?
        incumbent_ran_2020 = mun_2020['Reeleição'].str.upper().eq('S').any()

        # 2020 winner
        winner_2020 = mun_2020[mun_2020['Situação de totalização'] == 'Eleito']
        winner_2020_reelection = winner_2020['Reeleição'].values[0] == 'S' if not winner_2020.empty else None

        # Number of candidates
        n_candidates_2016 = len(mun_2016)
        n_candidates_2020 = len(mun_2020)

        # Write TXT
        txt_path = os.path.join(folder_path, "election_summary.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"Election Summary: {municipio.upper()}\n")
            f.write(f"{'='*40}\n")
            f.write(f"2016 winner was in reelection campaign:\t{'Yes' if winner_2016_reelection else 'No' if winner_2016_reelection is not None else 'N/A'}\n")
            f.write(f"2016 incumbent ran in 2020:\t{'Yes' if incumbent_ran_2020 else 'No'}\n")
            f.write(f"2020 winner was in reelection campaign:\t{'Yes' if winner_2020_reelection else 'No' if winner_2020_reelection is not None else 'N/A'}\n")
            f.write(f"Number of candidates in 2016:\t{n_candidates_2016}\n")
            f.write(f"Number of candidates in 2020:\t{n_candidates_2020}\n")

        print(f"Written: {municipio}")

def generate_election_csv(base_dir, csv_2016_path, csv_2020_path, output_path):
    df_2016 = pd.read_csv(csv_2016_path, sep=None, engine='python')
    df_2020 = pd.read_csv(csv_2020_path, sep=None, engine='python')

    df_2016['municipio_norm'] = df_2016['Município'].apply(normalize_name)
    df_2020['municipio_norm'] = df_2020['Município'].apply(normalize_name)

    rows = []

    for municipio in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, municipio)
        if not os.path.isdir(folder_path):
            continue

        municipio_norm = normalize_name(municipio)

        mun_2016 = df_2016[df_2016['municipio_norm'] == municipio_norm]
        mun_2020 = df_2020[df_2020['municipio_norm'] == municipio_norm]

        if mun_2016.empty and mun_2020.empty:
            continue

        winner_2016 = mun_2016[mun_2016['Situação de totalização'] == 'Eleito']
        winner_2016_reelection = winner_2016['Reeleição'].values[0] == 'S' if not winner_2016.empty else None

        incumbent_ran_2020 = mun_2020['Reeleição'].str.upper().eq('S').any()

        winner_2020 = mun_2020[mun_2020['Situação de totalização'] == 'Eleito']
        winner_2020_reelection = winner_2020['Reeleição'].values[0] == 'S' if not winner_2020.empty else None

        rows.append({
            "municipio": municipio,
            "winner_2016_reelection": int(winner_2016_reelection) if winner_2016_reelection is not None else None,
            "incumbent_ran_2020": int(incumbent_ran_2020),
            "winner_2020_reelection": int(winner_2020_reelection) if winner_2020_reelection is not None else None,
            "n_candidates_2016": len(mun_2016),
            "n_candidates_2020": len(mun_2020),
        })

    df_out = pd.DataFrame(rows)
    df_out.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Saved: {output_path} ({len(df_out)} rows)")