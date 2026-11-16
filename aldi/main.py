import os  # usado para verificar existência de ficheiros e caminhos
import sys  # usado para sair do programa
import time  # importado mas não está a ser usado diretamente neste ficheiro
import pandas as pd  # usado para ler e manipular o CSV final

# Componentes visuais da biblioteca Rich (UI no terminal)
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich import box
from rich.align import Align

# Importações internas do teu projeto (módulos teus)
from ui import console, AZUL_ALDI, LARANJA_ALDI  # consola custom + cores
from scrapper import download_pdf_aldi  # função que faz download do PDF do ALDI
from processor import extrair_dados_pdf, guardar_csv  # processamento do PDF e exportação

# URL do folheto semanal do ALDI
URL = "https://www.aldi.pt/folheto/esta-semana-n.html"

# Caminho onde o CSV final será guardado
CSV_PATH = "output/produtos_aldi_limpo.csv"


def mostrar_header():
    # Limpa o terminal antes de mostrar o header
    console.clear()

    # Cria um painel estilizado com Rich
    panel = Panel(
        Align.center(
            Text.assemble(
                ("     🛒 ALDI SCRAPER\n\n", "bold white"),  # título principal
                ("Extrator de Catálogo Semanal", f"{LARANJA_ALDI}")  # subtítulo
            )
        ),
        border_style=AZUL_ALDI,  # cor da borda
        padding=(1, 6),  # espaçamento interno
        title="[bold white]ALDI Portugal[/bold white]",  # título superior do painel
    )

    # Mostra o painel no terminal
    console.print(panel)
    console.print()


def mostrar_tabela(csv_path):
    # Verifica se o ficheiro CSV existe antes de tentar ler
    if not os.path.exists(csv_path):
        console.print("[red]Ficheiro CSV não encontrado para exibir a tabela.[/red]")
        return  # sai da função se não existir

    # Lê o CSV com pandas (separador ; e encoding típico PT)
    df = pd.read_csv(csv_path, sep=';', encoding='utf-8-sig')

    # Cria uma tabela formatada com Rich
    table = Table(
        title="🛒 Produtos ALDI — Catálogo desta semana",
        box=box.ROUNDED,  # estilo das bordas
        border_style=AZUL_ALDI,
        header_style=f"bold white on {AZUL_ALDI}",
        show_lines=True  # linhas separadoras entre rows
    )

    # Define colunas da tabela
    table.add_column("Página", style="dim", width=8, justify="center")
    table.add_column("Produto", style="bold white", min_width=40)
    table.add_column("Preço", style=f"bold {LARANJA_ALDI}", width=10, justify="right")

    # Itera por cada linha do CSV e adiciona à tabela
    for _, row in df.iterrows():
        table.add_row(str(row['Pagina']), str(row['Produto']), f"{row['Preco']} €")

    # Mostra tabela no terminal
    console.print(table)

    # Mostra total de produtos encontrados
    console.print(f"\n[dim]Total: {len(df)} produtos encontrados[/dim]\n")


def main():
    # Mostra o header inicial da aplicação
    mostrar_header()

    # Variáveis de controlo do estado do programa
    sucesso = False  # indica se o processo terminou com sucesso
    lista_dados = []  # vai guardar os dados extraídos do PDF
    erro_msg = ""  # guarda mensagem de erro caso aconteça

    # Barra de progresso visual (Rich Progress)
    with Progress(
        SpinnerColumn(style=f"bold {AZUL_ALDI}"),  # spinner animado
        TextColumn("[bold white]{task.description}"),  # descrição da tarefa
        BarColumn(bar_width=40, style=AZUL_ALDI, complete_style=LARANJA_ALDI, finished_style=f"bold {LARANJA_ALDI}"),
        TextColumn("[bold white]{task.percentage:>3.0f}%"),  # percentagem
        TimeElapsedColumn(),  # tempo decorrido
        console=console,
        transient=False  # mantém progresso visível no final
    ) as progress:

        # Cria tarefa com 100% total
        tarefa = progress.add_task("A iniciar...", total=100)

        # Atualiza estado inicial
        progress.update(tarefa, description="🌐 A aceder ao site do ALDI...", completed=5)

        try:
            # Faz download do PDF do ALDI
            caminho_pdf = download_pdf_aldi(URL)

            # Verifica se o PDF foi realmente criado
            if caminho_pdf and os.path.exists(caminho_pdf):
                progress.update(tarefa, description="✅ PDF descarregado!", completed=40)
            else:
                # Se falhar, levanta erro para cair no except
                raise Exception("Ficheiro PDF não foi gerado. Verifica o screenshot em downloads/debug_screenshot.png")

        except Exception as e:
            # Captura erro do download
            erro_msg = str(e)
            progress.update(tarefa, description="❌ Erro no download!", completed=100)
            caminho_pdf = None  # garante que não avança processamento

        # Só continua se houver PDF válido
        if caminho_pdf:
            progress.update(tarefa, description="🔍 A analisar o PDF...", completed=50)

            try:
                # Extrai dados do PDF para uma lista estruturada
                lista_dados = extrair_dados_pdf(caminho_pdf)

                if lista_dados:
                    # Se houver dados, guarda em CSV
                    progress.update(tarefa, description="💾 A guardar CSV...", completed=85)

                    guardar_csv(lista_dados, "produtos_aldi_limpo.csv")

                    progress.update(tarefa, description="✅ Concluído!", completed=100)
                    sucesso = True
                else:
                    # Caso o PDF não tenha produtos reconhecidos
                    erro_msg = "Nenhum produto detetado no PDF."
                    progress.update(tarefa, description="❌ Extração vazia!", completed=100)

            except Exception as e:
                # Erro durante processamento do PDF
                erro_msg = str(e)
                progress.update(tarefa, description="❌ Erro no processamento!", completed=100)

    # Linha em branco após progresso
    console.print()

    # Se tudo correu bem, mostra painel de sucesso
    if sucesso:
        console.print(Panel(
            f"[bold white]✅ Pesquisa concluída!\n\n"
            f"[{LARANJA_ALDI}]{len(lista_dados)} produtos[/{LARANJA_ALDI}] extraídos.\n\n"
            f"[dim]Pressiona [bold white]V[/bold white] para ver tabela ou [bold white]E[/bold white] para sair[/dim]",
            border_style="green",
            title="[bold green]SUCESSO[/bold green]",
            padding=(1, 4)
        ))
    else:
        # Caso tenha falhado, mostra erro
        console.print(Panel(
            f"[bold white]❌ Erro na pesquisa!\n\n"
            f"[red]{erro_msg}[/red]\n\n"
            f"[dim]Pressiona [bold white]E[/bold white] para sair[/dim]",
            border_style="red",
            title="[bold red]ERRO[/bold red]",
            padding=(1, 4)
        ))

    # Loop de interação com o utilizador no terminal
    while True:
        tecla = console.input("\n [bold white]> [/]").strip().lower()

        if tecla == 'e':
            # Sai do programa
            console.print(f"\n[{AZUL_ALDI}]Até à próxima! 👋[/{AZUL_ALDI}]\n")
            sys.exit(0)

        elif tecla == 'v' and sucesso:
            # Mostra tabela se houver dados
            mostrar_tabela(CSV_PATH)
            console.print(f"[dim]Pressiona [bold white]E[/bold white] para sair[/dim]")

        elif tecla == 'v' and not sucesso:
            # Tentativa de ver tabela sem sucesso anterior
            console.print("[red]Não há resultados para mostrar.[/red]")

        else:
            # Qualquer outro input inválido
            console.print("[dim]Comando inválido. Usa V ou E.[/dim]")


# Ponto de entrada do programa (executa apenas se correr este ficheiro diretamente)
if __name__ == "__main__":
    main()