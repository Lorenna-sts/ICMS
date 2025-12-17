import pandas as pd
import unicodedata
import warnings
import os

# Desativar avisos
warnings.simplefilter(action='ignore', category=FutureWarning)

def normalizar(txt):
    if pd.isna(txt): return ""
    return "".join(c for c in unicodedata.normalize('NFD', str(txt).upper().strip()) 
                   if unicodedata.category(c) != 'Mn')

def limpar_valor_numerico(valor):
    if pd.isna(valor): return 0.0
    if isinstance(valor, (int, float)): return float(valor)
    s = str(valor).strip()
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return 0.0

# Função para aplicar formato brasileiro: 1234.56 -> 1.234,56
def formatar_br(valor):
    return "{:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")

# 1. Configurações
mapeamento_categorias = {
    'INDÚSTRIA': 449,
    'COMÉRCIO ATACADISTA E DISTRIBUIDOR': 446,
    'COMÉRCIO VAREJISTA': 447,
    'PRESTAÇÃO DE SERVIÇO': 450,
    'PRODUÇÃO AGROPECUÁRIA': 451,
    'EXTRATOR MINERAL OU FÓSSIL': 448,
    'COMBUSTÍVEL': 452,
    'COMUNICAÇÃO': 453,
    'ENERGIA ELÉTRICA': 454,
    'OUTROS': 455
}

# 2. Carregar arquivos
df_icms = pd.read_csv(r'C:\Users\lorenna.santos\OneDrive - Subsecretaria de Tecnologia da Informação\Documentos\ICMS 2024.csv', 
                      sep=None, engine='python', encoding='latin1')
df_icms.columns = [c.strip() for c in df_icms.columns]

df_arrec = pd.read_csv(r'\\arquivosimb01\imb-geoprocessamento$\GEDE\BDE - Banco de Dados\2025\ipva_itcd_icms\Arrecadacao ICMS 2024_.csv', 
                       sep=';', encoding='latin1')
df_arrec.columns = [c.strip() for c in df_arrec.columns]

# 3. Processar ICMS 2024
df_icms['Valor Total'] = df_icms['Valor Total'].apply(limpar_valor_numerico)
df_icms['mun_norm'] = df_icms['Município Contribuinte'].apply(normalizar)

# A. Categorias
df_icms['GM_ALT_UPPER'] = df_icms['GM_ALT'].str.upper().str.strip()
cat_values = df_icms.groupby(['mun_norm', 'GM_ALT_UPPER'])['Valor Total'].sum().reset_index()
cat_values['var_cod'] = cat_values['GM_ALT_UPPER'].map(mapeamento_categorias)

# B. TOTAL (330)
total_values = df_icms.groupby('mun_norm')['Valor Total'].sum().reset_index()
total_values['var_cod'] = 330

novos_dados = pd.concat([
    cat_values.dropna(subset=['var_cod'])[['mun_norm', 'var_cod', 'Valor Total']],
    total_values[['mun_norm', 'var_cod', 'Valor Total']]
])

# Cálculo em Milhares (ainda como número para somas)
novos_dados['d_2024_num'] = (novos_dados['Valor Total'] / 1000)

# 4. Estruturar
df_arrec['mun_norm'] = df_arrec['LOC_NOME'].apply(normalizar)
municipios = df_arrec[['mun_norm', 'LOC_NOME', 'loc_cod']].drop_duplicates('mun_norm')

codigos_alvo = list(mapeamento_categorias.values()) + [330]
template = []
for _, mun in municipios.iterrows():
    for cod in codigos_alvo:
        template.append({'mun_norm': mun['mun_norm'], 'LOC_NOME': mun['LOC_NOME'], 'loc_cod': mun['loc_cod'], 'var_cod': cod})

df_template = pd.DataFrame(template)
df_final = pd.merge(df_template, novos_dados[['mun_norm', 'var_cod', 'd_2024_num']], on=['mun_norm', 'var_cod'], how='left')
df_final['d_2024_num'] = df_final['d_2024_num'].fillna(0)

# 5. Unir com o restante do arquivo
df_arrec_outros = df_arrec[~df_arrec['var_cod'].isin(codigos_alvo)].copy()
df_arrec_outros['d_2024_num'] = df_arrec_outros['d_2024'].apply(limpar_valor_numerico)

resultado = pd.concat([df_arrec_outros, df_final], ignore_index=True)

# --- PASSO DA SEGUNDA IMAGEM (FORMATAÇÃO) ---
# Aqui transformamos o número no formato "1.234,56"
resultado['d_2024'] = resultado['d_2024_num'].apply(formatar_br)

# 6. Salvar no diretório Z:
diretorio_saida = r'Z:\GEDE\BDE - Banco de Dados\2025\ipva_itcd_icms'
caminho_final = os.path.join(diretorio_saida, 'Arrecadacao_ICMS_2024_Formatado.csv')

# Selecionar apenas as colunas necessárias para o formato final
colunas_finais = ['LOC_NOME', 'loc_cod', 'var_cod', 'd_2024']

resultado[colunas_finais].sort_values(['LOC_NOME', 'var_cod']).to_csv(
    caminho_final, 
    sep=';', 
    index=False, 
    encoding='latin1'
)

print(f"Sucesso! Valores formatados conforme a imagem em: {caminho_final}")