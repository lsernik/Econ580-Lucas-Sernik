import requests
import csv
import os
import zipfile
import io
import pandas as pd
import unicodedata

MUNICIPALITY_ALIASES = {
    "sao luis do paraitinga": "sao luiz do paraitinga",
}

def get_municipalities(path):
    print("Getting municipalities")
    if os.path.exists(path + "/municipalities.csv"):
        return path + "/municipalities.csv"
    response = requests.get("https://transparencia.tce.sp.gov.br/api/json/municipios")
    d = response.json()
    with open(path + "/municipalities.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["municipio", "municipio_extenso"])
        writer.writeheader()
        writer.writerows(d)
    print("Saved municipalities at " + path + "/municipalities.csv")
    return path + "/municipalities.csv"

def create_municipality_folders(csv_path, base_dir):
    count = 0
    base_dir = base_dir + "/municipalities"
    if not os.path.exists(base_dir):
        os.mkdir(base_dir)
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder_path = os.path.join(base_dir, row["municipio"])
            os.makedirs(folder_path, exist_ok=True)
            count += 1
    print(f"Created folders for each municipality. Total municipalities is {count}")
    return count, base_dir

def download_expenses(base_dir, years, num):
    mun_count = 0
    count = 0
    for municipio in os.listdir(base_dir):
        mun_count += 1
        for year in years:
            count += 1
            if year == 2017:
                file_name = f"despesas-{municipio}-{year}.zip.csv"
            else:
                file_name = f"despesas-{municipio}-{year}.csv"
            path = os.path.join(base_dir, municipio, file_name)
            if os.path.exists(path):
                print(f"Already exists: {municipio} {year} — skipping")
                continue
            url = f"https://transparencia.tce.sp.gov.br/sites/default/files/csv/despesas-{municipio}-{year}.zip"
            for attempt in range(3):
                try:
                    response = requests.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                            for filename in z.namelist():
                                if filename.endswith(".csv"):
                                    csv_path = os.path.join(base_dir, municipio, filename)
                                    with open(csv_path, "w", encoding="utf-8") as out:
                                        out.write(z.read(filename).decode("latin-1"))
                                    print(f"({mun_count}) Extracted: {municipio} {year} -> {filename}")
                        break
                    else:
                        print(f"Not found: {municipio} {year} (status {response.status_code})")
                        break
                
                except requests.exceptions.Timeout:
                    print(f"Timeout: {municipio} {year} — requesting again")
                except Exception as e:
                    print(f"Error: {municipio} {year} — {e}")
    print(f"Total number of csvs is {count}, should be{num * 8}") # Counting for the state of sao paulo

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