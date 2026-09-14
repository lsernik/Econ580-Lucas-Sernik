import pandas as pd
import os
import shutil
import requests
import replication_package_sernik_2026 as rp

dir = "./replication_results"

df = pd.read_csv(dir + "/regression_dataset.csv")
missing = df[df["winner_2016_reelection"].isna()]["municipio"].unique()
print(f"{len(missing)} municipalities with no election data:")
for m in missing:
    print(f"  - {m}")