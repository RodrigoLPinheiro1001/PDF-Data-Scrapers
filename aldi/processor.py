import pdfplumber  # biblioteca para leitura de PDFs com extração de texto e informação posicional
import pandas as pd  # utilizada para estruturar dados e exportar para CSV
import re  # expressões regulares para limpeza e deteção de padrões
import os  # operações com sistema de ficheiros
from ui import console  # consola personalizada para output formatado

# =========================
# CONFIGURAÇÃO DE FONTES
# =========================

# tamanho de fonte típico associado a nomes de produtos
FONTE_NOME = 15.0

# tamanho de fonte típico associado a marcas
FONTE_MARCA = 10.0

# limite inferior de tamanho de fonte considerado relevante
FONTE_LIXO_MAX = 8.5

# intervalos de tamanhos de fonte associados à parte inteira do preço (euros)
FONTE_PRECO_EUROS = [(29.0, 31.5), (32.5, 33.5), (43.0, 45.0), (51.0, 56.5)]

# intervalos de tamanhos de fonte associados aos cêntimos
FONTE_PRECO_CENTS = [(21.5, 25.0), (31.8, 32.2), (34.0, 36.0), (37.0, 41.5)]

# conjunto de palavras consideradas ruído em folhetos promocionais
LIXO_TEXTO = {
    'CUSTA', 'POUCO', 'COMPRAR', 'BEM', 'SUPER', 'PREÇO', 'ESTA', 'PÁSCOA',
    'POUPA', 'ATÉ', 'APROVEITA', 'NOVO', 'PVPR', 'POR', 'CADA', 'GARRAFA',
    'DIAS', 'TODOS', 'OS', 'FRESCOS', 'HOME', 'CREATION', 'OSTER', 'PHANTASIE',
    'PLENO', 'SABOR', 'TRADER', 'ALMA', 'FRESCA', 'MILKA', 'AO', 'MELHOR',
    'DESCONTO', 'PEIXE', 'PASTELARIA', 'IMBATÍVEIS', 'DESCONTOS', 'XXL',
    'AINDA', 'MAIS', 'BAIXOS', 'PREÇOS', 'PARA', 'SEMPRE', 'A', 'PARTIR', 'DE',
    'UNID./CONJ', 'UNID/CONJ', 'UNID', 'CONJ'
}

# =========================
# UTILITÁRIOS DE PREÇO
# =========================

def reconstruir_preco(euros_text, cents_text):
    # combina a parte dos euros com os cêntimos para formar um valor monetário completo
    euros = euros_text.rstrip('.')  # remove possíveis pontos finais residuais
    cents = cents_text.strip()  # remove espaços desnecessários

    try:
        # tenta construir valor numérico e formatar com duas casas decimais
        valor = float(f"{euros}.{cents}")
        return f"{valor:.2f}".replace('.', ',')  # formatação portuguesa
    except:
        # fallback caso a estrutura do PDF esteja inconsistente
        return f"{euros},{cents}"


def _size_in_ranges(size, ranges):
    # verifica se um valor de tamanho de fonte pertence a algum intervalo definido
    return any(low <= size <= high for low, high in ranges)


def _is_fragmento_suspeito(nome):
    # valida se o nome extraído é demasiado curto ou inválido
    if not nome:
        return True
    if len(nome) < 3:
        return True
    return False


# =========================
# LIMPEZA DE NOMES
# =========================

def _limpar_nome(nome):
    # normalização de caracteres especiais provenientes do PDF
    nome = nome.replace('\xad', '-').replace('\u2011', '-')

    # padrões de marketing e ruído textual a remover
    sufixos_lixo = [
        r'\s+PREÇOS PARA SEMPRE$',
        r'\s+A partir de(?:\s+Sáb)?$',
        r'\s+UNID\./CONJ\.?$',
        r'\s+un\.\s*=\s*$',
        r'\b(?:PVP|un\.?|=)\b'
    ]

    # aplicação dos padrões de remoção
    for pattern in sufixos_lixo:
        nome = re.sub(pattern, '', nome, flags=re.IGNORECASE).strip()

    # remoção de unidades de medida e quantidades
    nome = re.sub(r'\b\d+(?:[.,]\d+)?\s*(?:kg|g|ml|l|un\.?|dose|pack)\b', '', nome, flags=re.IGNORECASE).strip()

    # remoção de prefixos inválidos ou artefactos de parsing
    nome = re.sub(r'^(=|[-+])\s*', '', nome)
    nome = re.sub(r'^(?:\d+(?:[.,]\d+)?\.?\s*){1,3}', '', nome).strip()
    nome = re.sub(r'^(?:\d+\.ª\s*UN\.?\s*)+', '', nome, flags=re.IGNORECASE).strip()

    # remoção de palavras funcionais iniciais (stopwords)
    nome = re.sub(r'^(?:e|ou|com|de|do|da|dos|das|para|em|a|o)\s+', '', nome, flags=re.IGNORECASE)

    # normalização de hífenes
    nome = re.sub(r'\s*-\s*', '-', nome)
    nome = re.sub(r'-+', '-', nome)
    nome = re.sub(r'\b(Grão|Meio|Pós|Recém|Pré|Anti|Extra|Pára)-', r'\1-', nome, flags=re.IGNORECASE)

    # limpeza geral de espaços e pontuação
    nome = re.sub(r'\s+', ' ', nome).strip(' ;,.-=')

    # remoção de letras isoladas (ruído visual em alguns PDFs)
    if len(re.findall(r'\b[A-Z]\b', nome)) >= 3:
        nome = re.sub(r'\b[A-Z]\b', '', nome)

    # filtragem baseada em lista de palavras irrelevantes
    palavras = nome.split()
    palavras_limpas = []

    for p in palavras:
        if p.upper() not in LIXO_TEXTO:
            palavras_limpas.append(p)
        elif p.lower() in {'de', 'do', 'da', 'dos', 'das', 'com', 'e', 'ou'}:
            palavras_limpas.append(p)

    if not palavras_limpas:
        return ""

    nome = " ".join(palavras_limpas).strip(' ;,.-=')

    # remoção de números residuais no final do texto
    nome = re.sub(r'\b\d+\s+\d+\b$', '', nome).strip()
    nome = re.sub(r'\s+\d+$', '', nome).strip()

    return nome if len(nome) >= 3 else ""


def _nome_ruidoso(nome):
    # deteção de nomes com baixa qualidade estrutural
    if not nome:
        return True

    letras = len(re.findall(r'[A-Za-zÀ-ÿ]', nome))
    digitos = len(re.findall(r'\d', nome))

    # validação mínima de conteúdo textual
    if letras < 2:
        return True

    # deteção de excesso de números face a letras
    if digitos > letras + 3:
        return True

    return False


def _dist_voronoi(palavra, preco):
    # métrica heurística de distância espacial entre elementos no PDF
    diff_y = abs(float(palavra['top']) - preco['top'])
    diff_x = float(palavra['x0']) - preco['x0']

    if diff_x > 0:
        return diff_y + diff_x * 0.8

    return diff_y + abs(diff_x) * 0.4


# =========================
# EXTRAÇÃO PRINCIPAL
# =========================

def extrair_dados_pdf(pdf_path):
    # início do processo de extração
    console.print("[info]📄 A extrair dados do PDF...[/info]")

    dados = []  # estrutura final de armazenamento

    with pdfplumber.open(pdf_path) as pdf:
        console.print(f"[info]Total de páginas: {len(pdf.pages)}[/info]")

        for i, pagina in enumerate(pdf.pages):

            # extração de palavras com metadados posicionais
            palavras = pagina.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                extra_attrs=["size", "fontname"]
            )

            # estruturas intermédias de classificação
            nomes, marcas, euros, cents = [], [], [], []
            precos_diretos = []

            # classificação inicial dos tokens extraídos
            for p in palavras:
                size = round(float(p['size']), 1)
                txt = p['text'].strip()

                # remoção de ruído básico
                if not txt or len(txt) < 1 or size <= FONTE_LIXO_MAX or txt.upper() in LIXO_TEXTO:
                    continue

                if re.match(r'^-\d+', txt):
                    continue

                if txt.endswith('€'):
                    continue

                # deteção de preços completos em formato único
                m_preco_direto = re.match(r'^(\d{1,3})[.,](\d{2})$', txt)
                if m_preco_direto and 14.1 <= size <= 20.0:
                    precos_diretos.append({
                        'x0': float(p['x0']),
                        'x1': float(p['x1']),
                        'top': float(p['top']),
                        'bottom': float(p['bottom']),
                        'preco': f"{m_preco_direto.group(1)},{m_preco_direto.group(2)}",
                        'size': size
                    })
                    continue

                # filtros adicionais de exclusão
                if re.match(r'^-?\d+%$', txt):
                    continue
                if re.match(r'^\d{1,2}\.\d{1,2}\.?(\d{2,4})?$', txt):
                    continue
                if txt in {'Seg.', 'Dom.', 'Qua.', '-', '®', '*'}:
                    continue

                # classificação por tamanho de fonte
                if size == FONTE_NOME or 10.5 <= size <= 17.5:
                    nomes.append(p)
                elif size == FONTE_MARCA or 9.5 <= size <= 11.2:
                    if re.match(r'^\d+[.,]\d+$', txt):
                        continue
                    if len(txt) <= 1:
                        continue
                    marcas.append(p)
                elif _size_in_ranges(size, FONTE_PRECO_EUROS):
                    if re.match(r'^\d+\.?$', txt):
                        euros.append(p)
                elif _size_in_ranges(size, FONTE_PRECO_CENTS):
                    if re.match(r'^\d{2}$', txt):
                        cents.append(p)

            # =========================
            # COMBINAÇÃO DE PREÇOS
            # =========================

            precos = []
            usados_cents = set()

            # associação entre euros e cêntimos com base em proximidade espacial
            for e in euros:
                melhor_cent, melhor_dist = None, float('inf')

                for j, c in enumerate(cents):
                    if j in usados_cents:
                        continue

                    dist_x = float(c['x0']) - float(e['x1'])
                    dist_y = abs(float(c['top']) - float(e['top']))

                    if -15 <= dist_x <= 45 and dist_y <= 35:
                        score = dist_y + abs(dist_x)

                        if score < melhor_dist:
                            melhor_dist = score
                            melhor_cent = (j, c)

                if melhor_cent:
                    j, c = melhor_cent
                    usados_cents.add(j)

                    precos.append({
                        'x0': float(e['x0']),
                        'x1': float(c['x1']),
                        'top': float(e['top']),
                        'bottom': float(e['bottom']),
                        'preco': reconstruir_preco(e['text'], c['text']),
                        'tipo': 'grande'
                    })

            # inclusão de preços diretos já detetados
            for p in precos_diretos:
                p['tipo'] = 'direto'

            precos.extend(precos_diretos)

            # remoção de duplicados com base em proximidade espacial e valor
            precos_dedup = []

            for pr in sorted(precos, key=lambda x: (x['top'], x['x0'])):
                repetido = False

                for ex in precos_dedup:
                    if abs(pr['x0'] - ex['x0']) < 10 and abs(pr['top'] - ex['top']) < 10 and pr['preco'] == ex['preco']:
                        repetido = True
                        break

                if not repetido:
                    precos_dedup.append(pr)

            precos = precos_dedup

            # =========================
            # ASSOCIAÇÃO PRODUTO ↔ PREÇO
            # =========================

            usados_nomes = set()

            for preco in precos:
                candidatos_nome = []

                for j, n in enumerate(nomes):
                    if j in usados_nomes:
                        continue

                    diff_y = preco['top'] - float(n['top'])
                    raw_dx = float(n['x0']) - preco['x0']
                    diff_x = abs(raw_dx)

                    # filtro espacial básico de associação
                    if -120 < diff_y < 160 and diff_x < 300:
                        if raw_dx > 60:
                            continue

                        penalizacao_direita = 150 if raw_dx > 0 else 0
                        mesma_coluna = 0 if (diff_x < 160 or abs(diff_y) < 25) else 200

                        score = penalizacao_direita + mesma_coluna + abs(diff_y) + diff_x * 0.4

                        candidatos_nome.append((score, j, n))

                if not candidatos_nome:
                    continue

                candidatos_nome.sort()
                _, _, nome_ancora = candidatos_nome[0]

                x_ref, top_ref = float(nome_ancora['x0']), float(nome_ancora['top'])

                fragmentos = []
                idx_fragmentos = []

                for _, j, n in candidatos_nome:
                    if abs(float(n['x0']) - x_ref) < 120 and abs(float(n['top']) - top_ref) < 80:

                        dist_aqui = _dist_voronoi(n, preco)

                        dist_ancora_x = abs(float(n['x0']) - x_ref)
                        dist_ancora_y = abs(float(n['top']) - top_ref)

                        is_mesma_bloco = dist_ancora_y < 25 and dist_ancora_x < 100

                        roubado = False

                        # verificação de conflitos com outros preços
                        for outro in precos:
                            if outro is preco:
                                continue

                            if outro.get('tipo') == 'direto' and preco.get('tipo') == 'grande':
                                continue

                            margem = 60 if is_mesma_bloco else 15

                            if _dist_voronoi(n, outro) < dist_aqui - margem:
                                roubado = True
                                break

                        if roubado:
                            continue

                        fragmentos.append((float(n['top']), float(n['x0']), n['text']))
                        idx_fragmentos.append(j)

                if not fragmentos:
                    continue

                # deteção de marca associada ao produto
                marca_texto = ""
                melhor_marca = float('inf')

                for m in marcas:
                    diff_y_marca = abs(top_ref - float(m['top']))
                    diff_x_marca = abs(float(m['x0']) - x_ref)

                    if diff_y_marca < 40 and diff_x_marca < 110:
                        score_marca = diff_y_marca + diff_x_marca

                        if score_marca < melhor_marca:
                            melhor_marca = score_marca
                            marca_texto = m['text']

                # construção final do nome do produto
                fragmentos.sort()
                nome_final = " ".join(f[2] for f in fragmentos).strip()

                if marca_texto and not nome_final.startswith(marca_texto):
                    nome_final = f"{marca_texto} {nome_final}".strip()

                nome_final = _limpar_nome(nome_final)

                if _is_fragmento_suspeito(nome_final) or _nome_ruidoso(nome_final):
                    continue

                for j in idx_fragmentos:
                    usados_nomes.add(j)

                dados.append({
                    'Pagina': i + 1,
                    'Produto': nome_final,
                    'Preco': preco['preco']
                })

    console.print(f"[success]Processamento concluído com sucesso.[/success]")
    return dados


# =========================
# EXPORTAÇÃO CSV
# =========================

def guardar_csv(lista_produtos, nome_ficheiro):
    if not lista_produtos:
        return

    df = pd.DataFrame(lista_produtos)

    # validação mínima de qualidade dos dados
    df = df[df['Produto'].str.len() > 3]
    df = df[~df['Preco'].isin(['0,00'])]

    # remoção de palavras repetidas dentro do nome
    def limpar_repeticoes(nome):
        palavras = nome.split()
        vistas = []

        for p in palavras:
            if p not in vistas:
                vistas.append(p)

        return ' '.join(vistas)

    df['Produto'] = df['Produto'].apply(limpar_repeticoes)

    # remoção de duplicados
    df = df.drop_duplicates(subset=['Pagina', 'Produto', 'Preco'])

    # ordenação final dos resultados
    df = df.sort_values(['Pagina', 'Produto'])

    # criação da pasta de output se necessário
    os.makedirs('output', exist_ok=True)

    caminho_final = os.path.join('output', nome_ficheiro)

    # exportação para CSV com encoding compatível com PT
    df.to_csv(caminho_final, index=False, sep=';', encoding='utf-8-sig')

    console.print(f"[success]Ficheiro guardado em: {caminho_final}[/success]")