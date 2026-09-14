import os
import replication_package_sernik_2026 as rp
import requests
import pandas as pd

dir_name = "./replication_results"

# rp.fetch_indicators(dir_name + "/indicators.csv")

# rp.get_age_categories()

# rp.fetch_age_distribution(dir_name + "/age.csv", dir_name + "/ibge_id.csv")

files = ["/indicators.csv", "/age.csv", "/idh.xlsx", "/mun_ids_names.csv", "/controls.csv"]

# rp.build_regression_controls_dataset(dir_name + files[0], dir_name + files[1], dir_name + files[2], dir_name + files[3], dir_name + files[4])

mun = dir_name + "/municipalities"

# rp.debug_expenses(dir_name + "/municipalities")

# rp.debug_tp_despesa(mun)

files = [dir_name + "/controls.csv", dir_name + "/elections.csv", dir_name + "/expenses.csv"]

# rp.debug_datasets(files[0], files[1], files[2])

# rp.fix_filenames(mun)
# rp.fix_sao_luis(mun)

# rp.compute_expenses(dir_name + "/municipalities", dir_name + "/expenses.csv")

rp.build_regression_dataset(
    controls_csv  = dir_name + "/controls.csv",
    elections_csv = dir_name + "/elections.csv",
    expenses_csv  = dir_name + "/expenses.csv",
    output_path   = dir_name + "/regression_dataset.csv"
)

# Run regression for each spending category
for cat in [
    "disc_share_saude",
    "disc_share_educacao",
    "disc_share_urbanismo",
    "disc_share_assistencia_social",
    "disc_share_administracao",
    "disc_share_transporte"
]:
    rp.run_regression(dir_name + "/regression_dataset.csv", cat)

stats = rp.generate_descriptive_stats(
        dataset_csv  = "./replication_results/regression_dataset.csv",
        output_tex   = "./replication_results/descriptive_stats.tex"
    )