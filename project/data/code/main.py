import os
import replication_package_sernik_2026 as rp

election_years = [2016, 2020]
term_1 = list(range(2017, 2021))
term_2 = list(range(2021, 2025))
combined_terms = list(range(2017, 2025))

# Creates new folder in current directory where all data and
# models will be processed

dir_name = "./replication_results"
if not os.path.exists(dir_name):
    os.mkdir(dir_name)

# Download list with all municipalities in Sao Paulo via state
# API from Tribunal de Contas do Estado de São Paulo (TCESP)

municipalities_path = rp.get_municipalities(dir_name)

# The municipality of São Paulo has their own website for transparency. I will drop São Paulo from
# the analysis, since the data available is from 2021 to 2025. Adding it here just so we don't break
# the rest of the data pipeline

# rp.add_sao_paulo(municipalities_path)

# Create a new folder "municipalities" and new municipality folders and download data about the expenses of each municipality

response = rp.create_municipality_folders(municipalities_path, dir_name)

municipalities_num = response[0]
municipalities_dir = response[1]

# Collect expenses for each municipality for term 1 and term 2. This takes a while. If stuck,
# just run the file again

rp.download_expenses(municipalities_dir, combined_terms, municipalities_num)

# Collect election status for years 2016 and 2020. Did not use API to do it. Went to this website
#  https://sig.tse.jus.br/ords/dwapr/r/seai/sig-eleicao-arquivo/passo-1?p20_sq_conjunto_dados=4&cs=1o6XU8JlMV6jWQHCHAH7kY0Ho5EQRPwEQeBDSLcNSVSh7-rdngZmGXfE3QQwwunA-CQWrSMJFA0j8juiBaPBevg
# Made 2 requests. Selected years 2016 and 2020. Filtered for Position = Mayor and UF = SP.
# For dimensions, picked municipality, reelection status, situação de totalização 
# (elected or not), party symbol. On metrics, got quantity of candidates
# (just to generate the file). Type of file csv (en-US)

candidatos2016_path = "./replication_results/candidatos2016.csv/candidatos.csv"
candidatos2020_path = "./replication_results/candidatos2020.csv/candidatos.csv"

# Summarizes results on each election, important for the models

rp.generate_election_summaries(municipalities_dir, candidatos2016_path, candidatos2020_path)

# Creates a csv with all election results. All municipalities have corresponding election results.
# Might have problems with identifying some of them because of ' in the name and Luiz vs Luis

rp.generate_election_csv(municipalities_dir, candidatos2016_path, candidatos2020_path, dir_name + "/elections.csv")

# Saves a csv with the ids of each municipality, which will be used to make api calls to get data

rp.save_municipalities_ibge(dir_name + "/ibge_id.csv")

rp.fetch_indicators(dir_name + "/indicators.csv")

rp.fetch_age_distribution(dir_name + "/age.csv", dir_name + "/ibge_id.csv")

# For IDH and school quality and health quality, need to make manual donwloads form 
# http://www.atlasbrasil.org.br/ranking 
# (year 2010)

rp.merge_municipality_files(municipalities_path, dir_name + "/ibge_id.csv", dir_name + "/mun_ids_names.csv")

files = ["\indicators.csv", "/age.csv", "/idh.xlsx", "/mun_ids_names.csv", "/controls.csv"]

rp.build_regression_controls_dataset(dir_name + files[0], dir_name + files[1], dir_name + files[2], dir_name + files[3], dir_name + files[4])

# These guarantee consistency of city names across the files.

rp.fix_filenames(municipalities_path)
rp.fix_sao_luis(municipalities_path)

# This step takes some time

rp.compute_expenses(dir_name + "/municipalities", dir_name + "/expenses.csv")

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