import pandas as pd

path = "c:\\Users\\lucas\\Documents\\current\\spring_2026\\econ_580\\project\\data\\ppa(2024-2027)\\CAD_PRODUTO_txt\\"

df = pd.read_csv("c:\\Users\\lucas\\Documents\\current\\spring_2026\\econ_580\\project\\data\\ppa(2024-2027)\\CAD_PRODUTO.csv",
                encoding='latin-1',
                sep=';'
)

df = df.apply(lambda x: x.str.strip(',') if x.dtype == 'object' else x)
df.columns = df.columns.str.strip(',')
print(df.shape)

for col in df.columns:
    with open(f"{path}{col}.txt", 'w', encoding='utf-8') as f:
        f.write(f"\n--- {col} ---")
        f.write(df[col].value_counts().to_string())
