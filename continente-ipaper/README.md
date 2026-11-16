# Continente Scraper — iPaper Enrichments API

Este projeto é um extrator automatizado de catálogos e folhetos promocionais do **Continente Portugal**. Em vez de utilizar métodos pesados ou imprecisos como download de PDFs grandes ou OCR de imagens, este scraper extrai dados altamente estruturados diretamente da API interna do **iPaper** (plataforma que renderiza os folhetos interativos no site do Continente).

A aplicação possui uma interface de linha de comandos (CLI) moderna e interativa desenvolvida com a biblioteca `rich`, que exibe os dados organizados em tabelas e barras de progresso diretamente no terminal.

---

## 🚀 Funcionalidades

- **Descoberta Automática:** Localiza automaticamente o URL do folheto semanal mais recente e relevante no índice do Continente.
- **Extração Eficiente:** Faz o parsing inteligente do objeto `window.staticSettings` embebido no HTML para descarregar os blocos JSON (*chunks*) de enriquecimento.
- **Normalização de Dados:** Extrai automaticamente o formato/unidade do produto (ex: `kg`, `g`, `ml`, `pack`) a partir do nome usando expressões regulares.
- **Filtros Avançados via CLI:** Permite filtrar os resultados por página, nome, intervalo de preços e tier do produto antes de exibir ou guardar.
- **Exportação Limpa:** Guarda os resultados consolidados num ficheiro CSV formatado com tabulações (`\t`) e codificação `utf-8-sig` para compatibilidade total com o Excel.

---

## 📁 Estrutura do Projeto

```text
CONTINENTE-IPAPER/
├── output/              # Diretório gerado automaticamente para guardar os ficheiros CSV
├── main.py              # Interface de utilizador, CLI e aplicação de filtros
├── scraper.py           # Core do scraper (descoberta, requisições, parsing e exportação)
├── requirements.txt     # Dependências de bibliotecas de terceiros
└── teste_json.py        # Scripts/testes auxiliares para analisar a estrutura JSON