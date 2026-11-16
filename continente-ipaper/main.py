"""
main.py — Interface principal do Scraper Continente (iPaper Enrichments API).

Utilização:
  python main.py                         (descobre automaticamente o folheto atual)
  python main.py --url <url_folheto>    (folheto específico)
  python main.py --debug                (diagnóstico detalhado)
  python main.py --pagina 4             (só a página indicada)
  python main.py --filtro frango        (filtrar produtos por nome)
  python main.py --min-preco 1.00       (só preços >= valor)
  python main.py --max-preco 5.00       (só preços <= valor)
  python main.py --tier large           (large / giant)
  python main.py --sem-csv              (não guardar ficheiro CSV)
"""

import argparse  # permite criar comandos de terminal (--url, --debug, etc.)
import os        # operações com ficheiros e caminhos
import sys       # controlo do programa (exit, erros)

import pandas as pd  # leitura e manipulação de dados em CSV/tabelas
from rich.align import Align  # alinhamento de texto na interface terminal
from rich.panel import Panel  # criação de caixas visuais no terminal
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn  # barras de progresso
from rich.table import Table  # tabelas formatadas no terminal
from rich.text import Text  # texto formatado Rich
from rich import box  # estilos de bordas para tabelas
from rich.console import Console  # consola Rich principal

from scraper import (
    descobrir_url_folheto,  # função que encontra automaticamente o folheto atual
    extrair_catalogo,       # função principal de scraping do Continente
    guardar_csv,            # exporta resultados para CSV
    mostrar_tabela,         # imprime tabela no terminal
    OUTPUT_DIR,             # diretório de saída (definido no scraper)
)

VERMELHO = "red"  # cor padrão da interface
console  = Console()  # instância da consola Rich


# ===========================================================================
# HEADER
# ===========================================================================

def mostrar_header():
    # limpa o terminal antes de mostrar interface
    console.clear()

    # cria painel visual de título
    painel = Panel(
        Align.center(
            Text.assemble(
                ("CONTINENTE SCRAPER\n\n", "bold white"),  # título principal
                ("Extrator de Catálogo via iPaper API", "white"),  # subtítulo
            )
        ),
        border_style=VERMELHO,
        padding=(1, 6),
        title="[bold white]Continente Portugal[/bold white]",
    )

    console.print(painel)
    console.print()


# ===========================================================================
# FILTROS
# ===========================================================================

def aplicar_filtros(dados: list, args) -> list:
    # recebe lista de produtos e aplica filtros do CLI

    resultado = dados  # começa sem alterações

    # filtro por página
    if args.pagina is not None:
        resultado = [r for r in resultado if r["Pagina"] == args.pagina]
        console.print(f"  [dim]Filtro página {args.pagina}: {len(resultado)} produtos[/]")

    # filtro por texto
    if args.filtro:
        termo = args.filtro.lower()
        resultado = [
            r for r in resultado
            if termo in r["Produto"].lower() or termo in r.get("Desc", "").lower()
        ]
        console.print(f"  [dim]Filtro '{args.filtro}': {len(resultado)} produtos[/]")

    # filtro por tipo/tier de produto (large/giant)
    if args.tier:
        resultado = [r for r in resultado if r["Tier"] == args.tier]
        console.print(f"  [dim]Filtro tier '{args.tier}': {len(resultado)} produtos[/]")

    # filtro de preço mínimo
    if args.min_preco is not None:
        def _v(r):
            try:
                return float(r["Preco"].replace(",", "."))
            except Exception:
                return 0.0  # fallback se preço inválido

        resultado = [r for r in resultado if _v(r) >= args.min_preco]
        console.print(f"  [dim]Filtro preço >= {args.min_preco:.2f}€: {len(resultado)} produtos[/]")

    # filtro de preço máximo
    if args.max_preco is not None:
        def _v2(r):
            try:
                return float(r["Preco"].replace(",", "."))
            except Exception:
                return 999.0  # fallback para não excluir indevidamente

        resultado = [r for r in resultado if _v2(r) <= args.max_preco]
        console.print(f"  [dim]Filtro preço <= {args.max_preco:.2f}€: {len(resultado)} produtos[/]")

    return resultado


# ===========================================================================
# MOSTRAR CSV GUARDADO
# ===========================================================================

def mostrar_tabela_csv(caminho_csv: str):
    # mostra CSV previamente guardado no terminal

    if not os.path.exists(caminho_csv):
        console.print("[red]CSV não encontrado.[/red]")
        return

    # lê CSV (tab-separated)
    df = pd.read_csv(caminho_csv, sep="\t", encoding="utf-8-sig")

    # cria tabela visual
    tabela = Table(
        title=f"🛒 Produtos Continente — {len(df)} registos",
        box=box.ROUNDED,
        border_style=VERMELHO,
        header_style=f"bold white on {VERMELHO}",
        show_lines=False,
    )

    # colunas da tabela
    tabela.add_column("Pág",     justify="center", width=5)
    tabela.add_column("Produto", style="bold white", min_width=40)
    tabela.add_column("Desc",    style="dim white", max_width=30)
    tabela.add_column("Formato", style="dim white", max_width=14)
    tabela.add_column("Preço",   justify="right", width=9)
    tabela.add_column("Tier",    justify="center", width=8)

    # preenchimento da tabela linha a linha
    for _, linha in df.iterrows():
        tabela.add_row(
            str(linha.get("Pagina",  "—")),
            str(linha.get("Produto", "—")),
            str(linha.get("Desc",    "")),
            str(linha.get("Formato", "")),
            str(linha.get("Preco",   "—")) + " €",
            str(linha.get("Tier",    "")),
        )

    console.print(tabela)
    console.print(f"\n[dim]Total: {len(df)} produtos[/dim]\n")


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    # parser de argumentos do terminal
    parser = argparse.ArgumentParser(
        description="Scraper do catálogo Continente via iPaper Enrichments API"
    )

    # opções disponíveis no CLI
    parser.add_argument("--url", default=None, help="URL do folheto (descoberta automática se omitido)")
    parser.add_argument("--debug", action="store_true", help="Diagnóstico detalhado")
    parser.add_argument("--pagina", type=int, default=None, metavar="N", help="Filtrar só a página N")
    parser.add_argument("--filtro", type=str, default=None, metavar="TEXTO", help="Filtrar por nome/descrição")
    parser.add_argument("--tier", type=str, default=None, choices=["large", "giant"], help="Filtrar por tier")
    parser.add_argument("--min-preco", type=float, default=None, dest="min_preco", metavar="VALOR")
    parser.add_argument("--max-preco", type=float, default=None, dest="max_preco", metavar="VALOR")
    parser.add_argument("--sem-csv", action="store_true", dest="sem_csv", help="Não guardar CSV")

    args = parser.parse_args()

    # mostra interface inicial
    mostrar_header()

    url_folheto = args.url

    # ── 0. Descoberta automática do folheto ────────────────────────────────
    if url_folheto is None:
        console.print("[bold]A descobrir o folheto atual do Continente...[/bold]\n")

        try:
            url_folheto = descobrir_url_folheto(verbose=True)
        except Exception as e:
            # erro crítico na descoberta automática
            console.print(
                Panel(
                    f"[yellow]Não foi possível descobrir o folheto automaticamente.[/yellow]\n\n"
                    f"[dim]{e}[/dim]\n\n"
                    f"[bold]Solução:[/bold] fornecer URL manualmente:\n"
                    f"[cyan]  python main.py --url <URL_DO_FOLHETO>[/cyan]",
                    title="[bold red]Descoberta falhada[/bold red]",
                    border_style="red",
                )
            )
            sys.exit(1)

    console.print(f"[bold]URL do folheto:[/] [cyan]{url_folheto}[/]\n")

    # ── 1. Extração de dados ───────────────────────────────────────────────
    try:
        dados, meta = extrair_catalogo(url_folheto, debug=args.debug)
    except Exception as e:
        console.print(f"\n[red]Erro na extração: {e}[/]")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    # ── 2. Aplicação de filtros ────────────────────────────────────────────
    tem_filtro = any([
        args.pagina is not None,
        args.filtro is not None,
        args.tier is not None,
        args.min_preco is not None,
        args.max_preco is not None,
    ])

    if tem_filtro:
        console.print("\n[bold]A aplicar filtros...[/]")
        dados_filtrados = aplicar_filtros(dados, args)
    else:
        dados_filtrados = dados

    # ── 3. Caso não existam resultados ─────────────────────────────────────
    if not dados_filtrados:
        console.print(
            Panel(
                "[yellow]Nenhum produto encontrado com os filtros indicados.[/yellow]",
                border_style="yellow",
            )
        )
        sys.exit(0)

    # ── 4. Apresentação dos dados ───────────────────────────────────────────
    mostrar_tabela(dados_filtrados)

    # ── 5. Exportação CSV ───────────────────────────────────────────────────
    caminho_csv = None

    if not args.sem_csv:
        try:
            caminho_csv = guardar_csv(dados_filtrados)
        except Exception as e:
            console.print(f"[yellow]Aviso: não foi possível guardar CSV: {e}[/]")

    # ── 6. Resumo final ─────────────────────────────────────────────────────
    linhas = [
        "[bold green]✓ Extração concluída via iPaper Enrichments API[/bold green]\n",
        f"Folheto:  [bold]{meta.get('nome', '—')}[/bold]",
        f"Páginas:  {meta.get('num_paginas', '—')}",
        f"Produtos: [bold]{len(dados)}[/bold] extraídos",
    ]

    if tem_filtro:
        linhas.append(f"Filtrados: [bold]{len(dados_filtrados)}[/bold]")

    if caminho_csv:
        linhas.append(f"CSV:      [cyan]{caminho_csv}[/cyan]")

    console.print(
        Panel(
            "\n".join(linhas),
            title="RESULTADO",
            border_style="green",
            padding=(1, 2),
        )
    )


if __name__ == "__main__":
    main()