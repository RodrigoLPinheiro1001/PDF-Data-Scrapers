import os  # operações com sistema de ficheiros (criar pastas, verificar caminhos, etc.)
import time  # usado para delays no fluxo de execução e espera por elementos
import re  # utilizado para expressões regulares na extração de URLs
import requests  # usado para download direto do ficheiro PDF via HTTP

# Selenium é utilizado para automação de browser (simula interação humana no site)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service  # gestão do serviço do ChromeDriver
from selenium.webdriver.chrome.options import Options  # configuração de opções do browser
from selenium.webdriver.common.by import By  # definição de métodos de localização de elementos
from selenium.webdriver.support.ui import WebDriverWait  # espera explícita por elementos
from selenium.webdriver.support import expected_conditions as EC  # condições de espera
from webdriver_manager.chrome import ChromeDriverManager  # instalação automática do ChromeDriver

from ui import console  # consola personalizada para output formatado


def _build_driver():
    options = Options()

    # executa o Chrome em modo headless (sem interface gráfica)
    options.add_argument("--headless=new")

    # define o tamanho da janela do browser para consistência no layout
    options.add_argument("--window-size=1920,1080")

    # opções para compatibilidade em ambientes Linux/containers
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # desativa aceleração GPU 
    options.add_argument("--disable-gpu")

    # user-agent para simular um navegador real e evitar bloqueios simples
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    # instalação e configuração automática do ChromeDriver compatível
    service = Service(ChromeDriverManager().install())

    # criação e retorno do driver Selenium configurado
    return webdriver.Chrome(service=service, options=options)


def _aceitar_cookies(driver):
    console.print("[info]🍪 A aguardar banner de cookies...[/info]")

    # tentativa repetida de detetar e aceitar cookies dinâmicos
    for _ in range(30):
        try:
            resultado = driver.execute_script("""
                const host = document.querySelector('#usercentrics-root');

                // verifica existência de shadow DOM onde o banner pode estar encapsulado
                if (!host || !host.shadowRoot) return 'sem-host';
                const shadow = host.shadowRoot;

                // tenta localizar botão de aceitação direto por atributo específico
                let btn = shadow.querySelector('button[data-testid="uc-accept-all-button"]');

                // fallback: procura botão por texto visível
                if (!btn) {
                    const todos = Array.from(shadow.querySelectorAll('button'));
                    btn = todos.find(b =>
                        b.textContent.toLowerCase().includes('aceitar tudo') ||
                        b.textContent.toLowerCase().includes('aceitar') ||
                        b.textContent.toLowerCase().includes('accept all')
                    );
                }

                // se botão for encontrado, executa clique
                if (btn) {
                    btn.click();
                    return 'clicado';
                }

                return 'sem-botao';
            """)

            # se cookies foram aceites, aguarda estabilização da página
            if resultado == 'clicado':
                console.print("[success]Cookies aceites com sucesso.[/success]")
                time.sleep(2)
                return

        except Exception:
            # ignora erros durante tentativa de acesso ao DOM
            pass

        # pequena pausa entre tentativas para evitar loop agressivo
        time.sleep(0.5)

    # fallback para sistema OneTrust caso o primeiro método falhe
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        driver.execute_script("arguments[0].click();", btn)

        console.print("[success]Cookies aceites via OneTrust.[/success]")
        time.sleep(2)
        return

    except Exception:
        pass

    # caso nenhum banner seja encontrado, continua execução
    console.print("[dim]Banner de cookies não detetado.[/dim]")


def _obter_url_pdf(driver):
    # lista de possíveis seletores para encontrar link de download do PDF
    seletores = [
        (By.CSS_SELECTOR, "[data-testid='leaflet-download-button']"),
        (By.XPATH, "//a[contains(@href,'GetPDF.ashx')]"),
        (By.XPATH, "//a[contains(@href,'.pdf')]"),
        (By.XPATH, "//a[contains(translate(normalize-space(.),'DESCARRGAR','descarrgar'),'descarregar')]"),
        (By.XPATH, "//a[contains(translate(normalize-space(.),'DOWNLOAD','download'),'download')]"),
        (By.XPATH, "//a[@data-attr-2='Download Leaflet']"),
    ]

    # tentativa sequencial de localizar elemento com link do PDF
    for by, seletor in seletores:
        try:
            elem = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((by, seletor))
            )

            href = elem.get_attribute("href") or ""

            # validação de URL encontrada
            if href:
                console.print(f"[success]URL do PDF encontrada.[/success]")
                return href

        except Exception:
            continue

    # fallback: procura URL diretamente no HTML da página
    match = re.search(r'https?://[^\s"\'<>]+GetPDF\.ashx[^\s"\'<>]*', driver.page_source)
    if match:
        return match.group(0)

    match = re.search(r'https?://[^\s"\'<>]+\.pdf[^\s"\'<>]*', driver.page_source, re.IGNORECASE)
    if match:
        return match.group(0)

    return None


def _guardar_pdf(pdf_url):
    # criação da pasta de destino caso não exista
    os.makedirs("downloads", exist_ok=True)

    caminho = "downloads/catalogo_aldi.pdf"

    console.print("[info]Download do PDF iniciado.[/info]")

    # headers para simular pedido legítimo de browser
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.aldi.pt/",
    }

    # pedido HTTP com stream para ficheiros grandes
    r = requests.get(pdf_url, headers=headers, stream=True, timeout=60)
    r.raise_for_status()

    # escrita do ficheiro em chunks para eficiência de memória
    with open(caminho, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

    # cálculo do tamanho final do ficheiro
    tamanho_kb = os.path.getsize(caminho) // 1024

    console.print(f"[success]PDF guardado com sucesso ({tamanho_kb} KB).[/success]")

    return caminho


def download_pdf_aldi(url):
    console.print(f"[info]A abrir URL: {url}[/info]")

    driver = _build_driver()

    try:
        # abre a página principal do ALDI
        driver.get(url)

        # tentativa de aceitar cookies antes de interagir com a página
        _aceitar_cookies(driver)

        # espera para garantir carregamento completo do conteúdo dinâmico
        time.sleep(3)

        console.print("[info]Procura do botão de download do PDF iniciada.[/info]")

        # tentativa de extração do link do PDF
        pdf_url = _obter_url_pdf(driver)

        # se link encontrado, procede ao download direto
        if pdf_url:
            return _guardar_pdf(pdf_url)

        # caso falhe, guarda screenshot para debugging
        driver.save_screenshot("downloads/debug_screenshot.png")

        console.print("[error]Não foi possível encontrar o botão de download.[/error]")
        return None

    except Exception as e:
        # tratamento de erro geral do processo
        console.print(f"[error]Erro durante execução: {e}[/error]")

        try:
            # tentativa de capturar estado da página em caso de erro
            driver.save_screenshot("downloads/debug_screenshot.png")
        except Exception:
            pass

        return None

    finally:
        # garante encerramento do browser para libertar recursos
        driver.quit()