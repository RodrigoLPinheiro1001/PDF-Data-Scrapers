"""
scraper.py — Extração do catálogo Continente via iPaper Enrichments API.

Estratégia:
  1. Descoberta automática do URL do folheto em continente.pt/folhetos/
  2. Aceder à página do folheto (folhetos.continente.pt/...)
  3. Extrair window.staticSettings embebido no HTML
  4. Ler staticSettings.enrichments.chunkUrls → ficheiros JSON estruturados
  5. Cada chunk contém enrichments com name, price, pageIndex, productId
  6. Desduplicar, validar e exportar CSV

Sem download de PDF. Sem parsing de texto. Dados estruturados direto do iPaper.
"""

import json  # parsing de JSON vindo da API
import os  # manipulação de ficheiros e diretórios
import re  # regex para validação e extração de padrões
from datetime import datetime  # timestamps para nomes de ficheiros
from urllib.parse import urlparse  # análise de URLs

import pandas as pd  # estruturação e exportação de dados em CSV
import requests  # requisições HTTP para scraping
from bs4 import BeautifulSoup  # parsing do HTML da página de folhetos
from rich.console import Console  # logging bonito no terminal
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn  # progresso de downloads
from rich.table import Table  # tabelas no terminal
from rich import box  # estilos de tabelas

console = Console()

# diretório onde os CSVs são guardados
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# headers para simular browser real e evitar bloqueios básicos
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://www.continente.pt/",
}

# URL base onde os folhetos são listados
FOLHETOS_INDEX = "https://www.continente.pt/folhetos/"
FOLHETOS_HOST  = "folhetos.continente.pt"

# palavras-chave usadas para priorizar o folheto correto
_PRIORIDADE_SLUG = [
    "semanal",
    "semana",
    "verao",
    "ferias",
    "continente",
]


# ===========================================================================
# DESCOBERTA AUTOMÁTICA DO FOLHETO
# ===========================================================================

def _pontuar_url(url: str) -> int:
    # atribui score ao URL para escolher o folheto mais relevante
    url_lower = url.lower()
    score = 0

    # aumenta score se contiver palavras-chave relevantes
    for i, kw in enumerate(_PRIORIDADE_SLUG):
        if kw in url_lower:
            score += len(_PRIORIDADE_SLUG) - i
            break

    # penaliza folhetos não relevantes (regionais ou temáticos)
    for kw in ["acores", "açores", "madeira", "cbd", "bebe", "bebé",
               "magazine", "livro", "feira", "mk", "fm", "am", "er", "cd"]:
        if kw in url_lower:
            score -= 5

    return score


def descobrir_url_folheto(verbose: bool = True) -> str:
    """
    Obtém automaticamente o folheto atual do Continente.
    Faz scraping da página principal de folhetos e escolhe o mais relevante.
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    if verbose:
        console.print(f"  [dim]A ligar a {FOLHETOS_INDEX}[/dim]")

    # pedido à página de folhetos
    r = session.get(FOLHETOS_INDEX, timeout=20, allow_redirects=True)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    candidatos = []

    # recolhe links de folhetos
    for a in soup.find_all("a", href=True):
        href = a["href"]
        parsed = urlparse(href)

        if FOLHETOS_HOST in (parsed.netloc or ""):
            url_completo = href if href.startswith("http") else f"https://{FOLHETOS_HOST}{href}"

            if url_completo not in candidatos:
                candidatos.append(url_completo)

    if not candidatos:
        raise ValueError("Nenhum folheto encontrado. Fornecer URL manualmente.")

    if verbose:
        console.print(f"  [dim]Encontrados {len(candidatos)} folhetos disponíveis[/dim]")

    # ordena por relevância
    candidatos_ord = sorted(candidatos, key=_pontuar_url, reverse=True)

    url_escolhido = candidatos_ord[0]

    if verbose:
        console.print(f"  [dim]✓ Escolhido: {url_escolhido}[/dim]")

    return url_escolhido


# ===========================================================================
# EXTRAÇÃO DO staticSettings
# ===========================================================================

def _extrair_static_settings(html: str) -> dict:
    # localiza bloco JS window.staticSettings dentro do HTML
    idx = html.find("window.staticSettings")

    if idx == -1:
        raise ValueError("window.staticSettings não encontrado")

    start = html.find("{", idx)
    if start == -1:
        raise ValueError("JSON não encontrado após staticSettings")

    # parsing manual de JSON (porque está embebido em JS, não é JSON puro)
    depth, in_str, esc, end = 0, False, False, start

    for i, ch in enumerate(html[start:], start=start):
        if esc:
            esc = False
            continue

        if ch == "\\" and in_str:
            esc = True
            continue

        if ch == '"' and not esc:
            in_str = not in_str
            continue

        if in_str:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break

    return json.loads(html[start:end + 1])


def obter_settings(url_folheto: str) -> dict:
    # obtém HTML do folheto e extrai configurações estruturadas
    r = requests.get(url_folheto, headers=HEADERS, timeout=30)
    r.raise_for_status()

    settings = _extrair_static_settings(r.text)

    pages = settings.get("pages", [])
    enrichments_meta = settings.get("enrichments", {})

    return {
        "paperId": settings.get("paperId"),
        "nome": settings.get("name", "Continente — Folheto"),
        "num_paginas": len(pages),
        "chunkUrls": enrichments_meta.get("chunkUrls", {}),
        "pageChunksIndexes": enrichments_meta.get("pageChunksIndexes", {}),
    }


# ===========================================================================
# EXTRAÇÃO DE PRODUTOS (ENRICHMENTS API)
# ===========================================================================

_TIPO_PRODUTO = {13}  # tipo de enrichment que representa produto

_LIXO_NOME = [
    re.compile(r"^\s*$"),
    re.compile(r"^\d+$"),
    re.compile(r"^[^\w]+$"),
]

def _nome_valido(nome: str) -> bool:
    # valida nome mínimo de produto
    if not nome or len(nome.strip()) < 3:
        return False
    for p in _LIXO_NOME:
        if p.match(nome.strip()):
            return False
    letras = [c for c in nome if c.isalpha()]
    return len(letras) >= 2


def _preco_valido(preco) -> bool:
    # valida intervalo plausível de preço
    try:
        v = float(preco)
        return 0.01 <= v <= 500.0
    except (TypeError, ValueError):
        return False


def _classificar_tier(preco: float) -> str:
    # classificação simples de produto por preço
    return "giant" if preco >= 15.0 else "large"


def _formatar_preco(preco: float) -> str:
    # formatação PT-PT com vírgula decimal
    return f"{preco:.2f}".replace(".", ",")


def extrair_produtos_de_chunk(chunk_url: str) -> list:
    """
    Extrai produtos de um chunk JSON do iPaper.
    Cada chunk contém lista de enrichments estruturados.
    """

    r = requests.get(chunk_url, headers=HEADERS, timeout=20)
    r.raise_for_status()

    data = r.json()
    enrichments = data.get("enrichments", [])

    produtos = []

    for item in enrichments:
        tipo = item.get("type")
        if tipo not in _TIPO_PRODUTO:
            continue

        nome = (item.get("name") or "").strip()
        preco_raw = item.get("price")
        page_index = item.get("pageIndex", 0)
        desc = (item.get("desc") or "").strip()
        prod_id = str(item.get("productId") or "")

        if not _nome_valido(nome):
            continue
        if not _preco_valido(preco_raw):
            continue

        preco_float = float(preco_raw)

        produtos.append({
            "Pagina": page_index + 1,
            "Produto": nome,
            "Desc": desc[:80] if desc else "",
            "Formato": _extrair_formato_do_nome(nome),
            "Preco": _formatar_preco(preco_float),
            "PrecoNum": preco_float,
            "Tier": _classificar_tier(preco_float),
            "ProductId": prod_id,
        })

    return produtos


_FORMATO_RE = re.compile(
    r"\b(\d+\s*(?:x\s*)?\d*\s*(?:g|kg|ml|cl|l|un\.?|unid\.?|pack|emb\.?))\b",
    re.IGNORECASE,
)


def _extrair_formato_do_nome(nome: str) -> str:
    # tenta extrair unidades/embalagem do nome do produto
    matches = _FORMATO_RE.findall(nome)
    return " ".join(m.strip() for m in matches[:2]).strip() if matches else ""


# ===========================================================================
# DEDUPLICAÇÃO
# ===========================================================================

def deduplicar(resultados: list) -> list:
    # remove duplicados por (nome + preço)
    vistos, unicos = set(), []

    for r in resultados:
        k = (r["Produto"].upper(), r["Preco"])
        if k not in vistos:
            vistos.add(k)
            unicos.append(r)

    return unicos


# ===========================================================================
# EXTRAÇÃO COMPLETA DO CATÁLOGO
# ===========================================================================

def extrair_catalogo(url_folheto: str, debug: bool = False) -> tuple[list, dict]:
    """
    Fluxo completo:
    1. Obter settings do folheto
    2. Ler chunk URLs
    3. Extrair todos os produtos
    4. Deduplicar e ordenar
    """

    meta = obter_settings(url_folheto)

    chunk_urls = meta.pop("chunkUrls")
    meta.pop("pageChunksIndexes", None)

    if not chunk_urls:
        raise ValueError("Sem enrichments disponíveis neste folheto")

    todos = []
    chunk_list = list(chunk_urls.items())

    # progress bar de execução
    with Progress(
        SpinnerColumn(style="bold red"),
        TextColumn("{task.description}"),
        BarColumn(bar_width=30, style="red", complete_style="bright_red"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
        transient=True,
    ) as progress:

        task = progress.add_task(
            f"A descarregar {len(chunk_list)} chunks...",
            total=len(chunk_list),
        )

        for chunk_key, chunk_url in chunk_list:
            try:
                produtos = extrair_produtos_de_chunk(chunk_url)

                if debug:
                    console.print(f"Chunk {chunk_key}: {len(produtos)} produtos")

                todos.extend(produtos)

            except Exception as e:
                console.print(f"[yellow]Erro chunk {chunk_key}: {e}[/yellow]")

            progress.advance(task)

    todos = deduplicar(todos)
    todos.sort(key=lambda r: (r["Pagina"], r["PrecoNum"]))

    return todos, meta


# ===========================================================================
# EXPORTAÇÃO CSV
# ===========================================================================

def guardar_csv(dados: list, nome_ficheiro: str | None = None) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if nome_ficheiro is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_ficheiro = f"continente_{ts}.csv"

    caminho = os.path.join(OUTPUT_DIR, nome_ficheiro)

    colunas = ["Pagina", "Produto", "Desc", "Formato", "Preco", "Tier", "ProductId"]

    df = pd.DataFrame(dados, columns=colunas)

    df.to_csv(caminho, sep="\t", index=False, encoding="utf-8-sig")

    return caminho


# ===========================================================================
# MOSTRAR TABELA
# ===========================================================================

def mostrar_tabela(dados: list):
    tabela = Table(
        title=f"🛒 Produtos Continente — {len(dados)} registos",
        box=box.ROUNDED,
        border_style="red",
        header_style="bold white on red",
        show_lines=False,
    )

    tabela.add_column("Pág", justify="center", width=5)
    tabela.add_column("Produto", style="bold white", min_width=40)
    tabela.add_column("Desc", style="dim white", max_width=30)
    tabela.add_column("Formato", style="dim white", max_width=14)
    tabela.add_column("Preço", justify="right", width=9)
    tabela.add_column("Tier", justify="center", width=8)

    for r in dados:
        tabela.add_row(
            str(r.get("Pagina", "—")),
            str(r.get("Produto", "—")),
            str(r.get("Desc", "")),
            str(r.get("Formato", "")),
            str(r.get("Preco", "—")) + " €",
            str(r.get("Tier", "")),
        )

    console.print(tabela)
    console.print(f"\n[dim]Total: {len(dados)} produtos[/dim]\n")