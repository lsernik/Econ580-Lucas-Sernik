import pandas as pd

skip = ['id_despesa_detalhe', 'ano_exercicio', 'ds_municipio', 'mes_ref_extenso', 'dt_emissao_despesa']

df = pd.read_csv("c:\\Users\\lucas\\Documents\\current\\spring_2026\\econ_580\\project\\data\\adamantina\\despesas-adamantina-2025.csv",
                 sep=';',
                 encoding='latin-1'
)

df = df.apply(lambda x: x.str.strip(',') if x.dtype == 'object' else x)
df.columns = df.columns.str.strip(',')
print(df.shape)
print(df.columns.tolist())

count = 0

for col in df.columns:
    with open(f"{col}.txt", 'w') as f:
        f.write(f"\n--- {col} ---")
        f.write(df[col].value_counts().to_string())
