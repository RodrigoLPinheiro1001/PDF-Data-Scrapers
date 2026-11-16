"""
teste_json.py — Vai ao site do Continente, descobre o folheto atual
e guarda o JSON completo (staticSettings + todos os chunks de enrichments)
em ficheiros separados na pasta output/json/.

Utilização:
  python teste_json.py
  python teste_json.py --url https://folhetos.continente.pt/2026/07/semanal-27-8i11/
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

OUTPUT_JSON_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "output", "json"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.continente.pt/",
}

FOLHETOS_INDEX = "https://www.continente.pt/folhetos/"
FOLHETOS_HOST  = "folhetos.continente.pt"


# ===========================================================================
# DESCOBERTA DO FOLHETO
# ===========================================================================

def descobrir_url_folheto() -> str:
    print(f"[1/4] A ligar a {FOLHETOS_INDEX} ...")
    r = requests.get(FOLHETOS_INDEX, headers=HEADERS, timeout=20, allow_redirects=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    candidatos = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        parsed = urlparse(href)
        if FOLHETOS_HOST in (parsed.netloc or ""):
            url = href if href.startswith("http") else f"https://{FOLHETOS_HOST}{href}"
            if url not in candidatos:
                candidatos.append(url)

    if not candidatos:
        raise ValueError("Nenhum folheto encontrado. Use --url manualmente.")

    def pontuar(url):
        u = url.lower()
        score = 0
        for i, kw in enumerate(["semanal", "semana", "verao", "continente"]):
            if kw in u:
                score += 10 - i
                break
        for kw in ["acores", "açores", "madeira", "bebe", "bebé", "magazine"]:
            if kw in u:
                score -= 5
        return score

    candidatos.sort(key=pontuar, reverse=True)
    print(f"       Encontrados {len(candidatos)} folhetos. Escolhido:")
    print(f"       {candidatos[0]}")
    return candidatos[0]


# ===========================================================================
# EXTRAÇÃO DO staticSettings
# ===========================================================================

def extrair_static_settings(html: str) -> dict:
    idx = html.find("window.staticSettings")
    if idx == -1:
        raise ValueError("window.staticSettings não encontrado no HTML.")
    start = html.find("{", idx)
    depth, in_str, esc, end = 0, False, False, start
    for i, ch in enumerate(html[start:], start=start):
        if esc:
            esc = False; continue
        if ch == "\\" and in_str:
            esc = True; continue
        if ch == '"' and not esc:
            in_str = not in_str; continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i; break
    return json.loads(html[start:end + 1])


# ===========================================================================
# GUARDAR JSON
# ===========================================================================

def guardar_json(dados: dict | list, nome: str) -> str:
    os.makedirs(OUTPUT_JSON_DIR, exist_ok=True)
    caminho = os.path.join(OUTPUT_JSON_DIR, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    tamanho = os.path.getsize(caminho)
    print(f"       Guardado: {caminho}  ({tamanho / 1024:.1f} KB)")
    return caminho


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Guarda o JSON do folheto Continente para inspeção"
    )
    parser.add_argument(
        "--url", default=None,
        help="URL do folheto (ex: https://folhetos.continente.pt/2026/07/semanal-27-8i11/)"
    )
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ficheiros_gerados = []

    # ── 1. Descobrir URL ────────────────────────────────────────────────────
    url_folheto = args.url
    if not url_folheto:
        url_folheto = descobrir_url_folheto()
    else:
        print(f"[1/4] URL fornecido: {url_folheto}")

    # ── 2. Descarregar HTML e extrair staticSettings ────────────────────────
    print(f"\n[2/4] A descarregar página do folheto ...")
    r = requests.get(url_folheto, headers=HEADERS, timeout=30)
    r.raise_for_status()

    settings = extrair_static_settings(r.text)
    paper_id = settings.get("paperId", "unknown")
    nome_folheto = settings.get("name", "folheto")
    slug = re.sub(r"[^\w]+", "_", nome_folheto.lower()).strip("_")
    print(f"       paperId: {paper_id} | nome: {nome_folheto}")

    # Guardar staticSettings completo
    print(f"\n[3/4] A guardar staticSettings.json ...")
    f1 = guardar_json(settings, f"static_settings_{slug}_{ts}.json")
    ficheiros_gerados.append(f1)

    # ── 3. Descarregar todos os chunks de enrichments ───────────────────────
    enrichments_meta = settings.get("enrichments", {})
    chunk_urls: dict = enrichments_meta.get("chunkUrls", {})

    if not chunk_urls:
        print("\n[AVISO] Nenhum chunkUrl encontrado no staticSettings.")
        print("        O folheto pode não ter enrichments disponíveis.")
    else:
        print(f"\n[4/4] A descarregar {len(chunk_urls)} chunks de enrichments ...")
        todos_enrichments = {}

        for i, (chave, url_chunk) in enumerate(chunk_urls.items(), start=1):
            print(f"       Chunk {i}/{len(chunk_urls)}: páginas {chave} ...")
            try:
                rc = requests.get(url_chunk, headers=HEADERS, timeout=20)
                rc.raise_for_status()
                dados_chunk = rc.json()
                todos_enrichments[chave] = dados_chunk

                # Guardar cada chunk individualmente
                nome_chunk = f"enrichments_chunk_{chave.replace('-','a')}_{ts}.json"
                f_chunk = guardar_json(dados_chunk, nome_chunk)
                ficheiros_gerados.append(f_chunk)

            except Exception as e:
                print(f"       [ERRO] Chunk {chave}: {e}")

        # Guardar todos os chunks num único ficheiro consolidado
        print(f"\n       A consolidar todos os chunks num único ficheiro ...")
        consolidado = {
            "folheto_url": url_folheto,
            "paperId": paper_id,
            "nome": nome_folheto,
            "extraido_em": ts,
            "chunks": todos_enrichments,
        }
        f2 = guardar_json(consolidado, f"enrichments_completo_{slug}_{ts}.json")
        ficheiros_gerados.append(f2)

    # ── Resumo ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("CONCLUÍDO — Ficheiros JSON gerados:")
    for f in ficheiros_gerados:
        size_kb = os.path.getsize(f) / 1024
        print(f"  {os.path.basename(f)}  ({size_kb:.1f} KB)")
    print(f"\nPasta: {OUTPUT_JSON_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
