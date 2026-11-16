from rich.console import Console
from rich.theme import Theme

# --- DEFINIÇÕES DE IDENTIDADE VISUAL ALDI ---
# Guardamos as cores oficiais em constantes para serem reutilizadas em todo o projeto.
# O prefixo # indica que estamos a usar códigos HEX (padrão web).
AZUL_ALDI = "#0050AA"
LARANJA_ALDI = "#FF6600"

# --- CRIAÇÃO DO TEMA PERSONALIZADO ---
# A classe Theme do Rich permite criar "apelidos" (aliases) para estilos.
# Em vez de escreveres f"bold {#0050AA}", escreves apenas "info".
theme = Theme({
    "info": f"bold {AZUL_ALDI}",      # Usado para mensagens de estado e navegação
    "accent": f"bold {LARANJA_ALDI}", # Usado para destaques, como preços ou títulos
    "success": "bold green",          # Usado para confirmar operações concluídas
    "error": "bold red",              # Usado para falhas críticas
    "debug": "dim white"              # Usado para logs secundários (cinzento suave)
})

# --- INSTÂNCIA GLOBAL DO CONSOLE ---
# Criamos um único objeto 'console' que já carrega o nosso tema.
# Todos os outros ficheiros (main.py, scrapper.py, etc.) importam este objeto.
console = Console(theme=theme)