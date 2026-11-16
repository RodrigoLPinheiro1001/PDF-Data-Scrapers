# 🛒 Aldi Scrapper

Um scraper desenvolvido em Python que descarrega automaticamente o folheto semanal do **ALDI Portugal**, extrai os produtos e respetivos preços diretamente do PDF e exporta os resultados para um ficheiro CSV.

O projeto utiliza automação web com Selenium para obter o folheto mais recente e técnicas de processamento de PDFs para reconstruir a informação dos produtos.

---

## Funcionalidades

- Download automático do folheto semanal do ALDI
- Aceitação automática do banner de cookies
- Extração automática do PDF do catálogo
- Processamento inteligente do conteúdo do PDF
- Associação entre produtos e preços através da posição dos elementos
- Limpeza e normalização dos nomes dos produtos
- Remoção de duplicados
- Exportação dos resultados para CSV
- Interface de terminal moderna utilizando Rich

---

## Tecnologias Utilizadas

- Python 3
- Selenium
- WebDriver Manager
- Requests
- pdfplumber
- Pandas
- Rich

---

## Estrutura do Projeto

```
Aldi Scrapper
│
├── downloads/
│   └── catalogo_aldi.pdf
│   
│
├── output/
│   └── produtos_aldi_limpo.csv
│   
│
├── main.py
├── processor.py
├── scrapper.py
├── ui.py
├── requirements.txt
└── README.md
```

---

## Funcionamento

O programa executa automaticamente as seguintes etapas:

1. Abre o site oficial do ALDI Portugal.
2. Aceita o banner de cookies.
3. Procura o botão de download do catálogo.
4. Obtém o link direto para o PDF.
5. Descarrega o catálogo semanal.
6. Analisa todas as páginas do PDF.
7. Identifica:
   - Nome do produto
   - Marca
   - Preço
8. Remove informação irrelevante.
9. Elimina duplicados.
10. Exporta os resultados para um ficheiro CSV.

---

## Algoritmo de Extração

Ao contrário de muitos PDFs, os folhetos promocionais não possuem uma estrutura organizada em tabelas.

Por esse motivo, foi desenvolvido um algoritmo baseado em heurísticas que utiliza:

- posição X/Y das palavras;
- tamanho da fonte;
- proximidade entre elementos;
- reconstrução dos preços (euros + cêntimos);
- associação espacial entre produtos e preços;
- limpeza automática de texto promocional.

Estas heurísticas permitem obter uma elevada taxa de sucesso na identificação dos produtos.

---

## Instalação


Entre na pasta:

```bash
cd "Aldi"
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

---

## Como executar

Execute:

```bash
python main.py
```

O programa irá:

- descarregar o folheto;
- processar o PDF;
- gerar o CSV;
- permitir visualizar os produtos diretamente no terminal.

---

## Output

O ficheiro final é guardado em:

```
output/produtos_aldi_limpo.csv
```

Exemplo:

| Página  |        Produto      |Preço |
|---------|---------------------|------|
| 3       | Café Torrado Delta  | 4,99 |
| 5       | Iogurte Grego       | 2,49 |
| 8       | Queijo Flamengo     | 5,99 |

---

## Interface

A aplicação utiliza a biblioteca **Rich**, proporcionando:

- barras de progresso
- tabelas formatadas
- mensagens coloridas
- painéis informativos
- feedback visual durante todo o processo

---

## Dependências

- pandas
- pdfplumber
- selenium
- webdriver-manager
- requests
- rich

---

## Possíveis Melhorias

- Exportação para Excel
- Exportação para JSON
- Histórico de folhetos
- Comparação entre semanas
- Pesquisa por produto
- Filtros por categoria
- Interface gráfica (Tkinter ou PyQt)
- API REST
- Base de dados SQLite

---

## Autor

Desenvolvido por **Rodrigo L. Pinheiro**

---

## Licença

Este projeto foi desenvolvido para fins académicos e educativos.

Não possui qualquer afiliação com o ALDI Portugal.