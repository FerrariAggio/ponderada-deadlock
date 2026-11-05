"""Gera diagramas analíticos e páginas de evidências a partir das saídas preservadas.

Requer Pillow somente para as imagens; os experimentos não dependem deste arquivo.
Não executa novamente as medições nem altera os resultados brutos.
"""

from html import escape
import json
import math
from pathlib import Path
import textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "ponderada/img"
RESULTADOS = ROOT / "ponderada/resultados"
FONTES = Path("/usr/share/fonts/truetype/dejavu")
INSTRUCOES = {
    1: ("lw x5, 0(x10)", "x5", ("x10",), True),
    2: ("add x6, x6, x5", "x6", ("x6", "x5"), False),
    3: ("lw x7, 0(x11)", "x7", ("x11",), True),
    4: ("sub x6, x6, x7", "x6", ("x6", "x7"), False),
    5: ("sw x6, 0(x12)", None, ("x6", "x12"), False),
    6: ("addi x10, x10, 4", "x10", ("x10",), False),
    7: ("addi x11, x11, 4", "x11", ("x11",), False),
}


def fonte(tamanho=22, mono=False, bold=False):
    """Recebe tamanho/estilo; retorna fonte DejaVu do sistema para imagens legíveis."""
    nome = "DejaVuSansMono" if mono else "DejaVuSans"
    return ImageFont.truetype(str(FONTES / (nome + ("-Bold" if bold else "") + ".ttf")), tamanho)


def planejar(ordem, forwarding):
    """Recebe ordem dos IDs e forwarding completo; retorna cronograma de 5 estágios.

    ID fica retido até poder ler WB (sem forwarding) ou consumir o resultado em EX.
    IF é retido pelo backpressure de ID. Loads disponibilizam dados após MEM.
    O forwarding considerado inclui o valor que sw leva para a memória.
    """
    linhas = []
    produtores = {}
    for ident in ordem:
        texto, destino, fontes, load = INSTRUCOES[ident]
        inicio_id = linhas[-1]["ID_fim"] + 1 if linhas else 2
        fim_id = inicio_id
        for reg in fontes:
            if reg in produtores:
                anterior = produtores[reg]
                necessario = anterior["MEM"] if anterior["load"] else anterior["EX"]
                fim_id = max(fim_id, necessario if forwarding else anterior["WB"])
        busca = linhas[-1]["ID_inicio"] if linhas else 1
        linha = {"id": ident, "texto": texto, "IF": busca, "ID_inicio": inicio_id,
                 "ID_fim": fim_id, "EX": fim_id + 1, "MEM": fim_id + 2,
                 "WB": fim_id + 3, "load": load, "store": ident == 5}
        linhas.append(linha)
        if destino:
            produtores[destino] = linha
    return {"ciclos": max(l["WB"] for l in linhas),
            "stalls": sum(l["ID_fim"] - l["ID_inicio"] for l in linhas), "linhas": linhas}


def desenhar_pipeline(dado, titulo, arquivo):
    """Recebe cronograma/título/nome; grava PNG com todos os ciclos e retenções."""
    ciclos = dado["ciclos"]
    esquerda, largura, altura = 450, 70, 64
    im = Image.new("RGB", (esquerda + ciclos * largura + 40, 710), "white")
    d = ImageDraw.Draw(im)
    d.text((28, 22), titulo, font=fonte(28, bold=True), fill="#152b44")
    d.text((28, 68), f"{ciclos} ciclos | {dado['stalls']} bolhas | WB escreve antes da leitura de ID",
           font=fonte(21), fill="#30445a")
    cores = {"IF": "#ddebf7", "ID": "#d9ead3", "EX": "#fff2cc", "MEM": "#eadcf4", "WB": "#d7e9e8", "—": "#f0f0f0"}
    for c in range(1, ciclos + 1):
        d.text((esquerda + (c - 1) * largura + 23, 122), str(c), font=fonte(20, mono=True), fill="black")
    for index, row in enumerate(dado["linhas"]):
        y = 165 + index * altura
        d.text((28, y + 17), f"I{row['id']}: {row['texto']}", font=fonte(20, mono=True), fill="black")
        eventos = {}
        for c in range(row["IF"], row["ID_inicio"]): eventos[c] = "IF" if c == row["IF"] else "IF*"
        for c in range(row["ID_inicio"], row["ID_fim"] + 1): eventos[c] = "ID" if c == row["ID_inicio"] else "ID*"
        eventos.update({row["EX"]: "EX", row["MEM"]: "MEM", row["WB"]: "—" if row["store"] else "WB"})
        for c in range(1, ciclos + 1):
            x = esquerda + (c - 1) * largura
            etapa = eventos.get(c, "")
            cor = "#f8d7da" if "*" in etapa else cores.get(etapa, "white")
            d.rectangle((x, y, x + largura - 3, y + altura - 5), fill=cor, outline="#d0d6db")
            if etapa: d.text((x + 11, y + 17), etapa, font=fonte(19, mono=True), fill="black")
    d.text((28, 635), "* = estágio retido por stall; IF* é efeito da mesma bolha, não uma bolha adicional.", font=fonte(19), fill="#30445a")
    d.text((28, 668), "— = sw percorre a posição final sem escrever registrador; instruções finais são addi.", font=fonte(19), fill="#30445a")
    im.save(IMG / arquivo)


def seta(draw, pontos, cor="#26384a", largura=4):
    """Recebe pontos e estilo; desenha linha orientada com ponta no último ponto."""
    draw.line(pontos, fill=cor, width=largura)
    x, y = pontos[-1]
    ax, ay = pontos[-2]
    angulo = math.atan2(y - ay, x - ax)
    draw.polygon([(x, y), (x - 16 * math.cos(angulo - .4), y - 16 * math.sin(angulo - .4)),
                  (x - 16 * math.cos(angulo + .4), y - 16 * math.sin(angulo + .4))], fill=cor)


def estados():
    """Sem parâmetros/retorno; grava o diagrama dos cinco estados e transições."""
    im = Image.new("RGB", (1490, 610), "white")
    d = ImageDraw.Draw(im)
    d.text((30, 22), "A3 — Estados de um processo / thread escalonável", font=fonte(28, bold=True), fill="#152b44")
    caixas = {"Criação": (40, 180, 270, 270), "Pronto": (390, 180, 620, 270),
              "Execução": (820, 180, 1050, 270), "Término": (1220, 180, 1450, 270),
              "Espera": (820, 420, 1050, 510)}
    for nome, box in caixas.items():
        d.rounded_rectangle(box, radius=14, fill="#e9f0f6", outline="#38556b", width=2)
        d.text((box[0] + 47, box[1] + 29), nome, font=fonte(25), fill="black")
    seta(d, [(270, 225), (390, 225)]); d.text((281, 192), "admissão", font=fonte(17), fill="black")
    seta(d, [(620, 225), (820, 225)]); d.text((648, 192), "escalonamento", font=fonte(17), fill="black")
    seta(d, [(1050, 225), (1220, 225)]); d.text((1083, 192), "finalização", font=fonte(17), fill="black")
    seta(d, [(935, 180), (935, 112), (505, 112), (505, 180)])
    d.text((590, 78), "preempção / fim do quantum", font=fonte(19), fill="black")
    seta(d, [(935, 270), (935, 420)])
    d.text((953, 330), "E/S, timer ou recurso", font=fonte(19), fill="black")
    seta(d, [(820, 465), (505, 465), (505, 270)])
    d.text((535, 427), "evento concluído", font=fonte(19), fill="black")
    d.text((35, 557), "Sensor periódico: espera pelo timer/E/S → pronto → execução; não precisa fazer polling contínuo.", font=fonte(21), fill="#30445a")
    im.save(IMG / "a3-estados.png")


def deadlock():
    """Sem parâmetros/retorno; grava grafo com recursos de uma instância e ciclo A5."""
    im = Image.new("RGB", (1440, 850), "white")
    d = ImageDraw.Draw(im)
    d.text((30, 20), "A5 — Grafo de alocação no instante do deadlock", font=fonte(28, bold=True), fill="#152b44")
    pontos = [(720, 145), (1120, 290), (1120, 550), (720, 700), (320, 550), (320, 290)]
    nomes = ["I2C", "thread_sensor", "LOG", "thread_log", "BLE", "thread_config"]
    for i, (x, y) in enumerate(pontos):
        nx, ny = pontos[(i + 1) % 6]
        tamanho = math.hypot(nx - x, ny - y)
        margem_a = 85 if i % 2 == 0 else 100
        margem_b = 100 if (i + 1) % 2 else 85
        a = (x + (nx - x) / tamanho * margem_a, y + (ny - y) / tamanho * margem_a)
        b = (nx - (nx - x) / tamanho * margem_b, ny - (ny - y) / tamanho * margem_b)
        seta(d, [a, b], "#1e6091" if i % 2 == 0 else "#b45309", 5)
    for i, ((x, y), nome) in enumerate(zip(pontos, nomes)):
        if i % 2 == 0:
            d.rectangle((x - 80, y - 48, x + 80, y + 48), fill="#e9f0f6", outline="#38556b", width=2)
            d.text((x - 31, y - 20), nome, font=fonte(24, bold=True), fill="black")
            d.ellipse((x - 4, y + 20, x + 4, y + 28), fill="black")
        else:
            d.ellipse((x - 99, y - 78, x + 99, y + 78), fill="#fff2cc", outline="#8b6826", width=2)
            parte = nome.replace("_", "\n")
            d.multiline_text((x - 60, y - 30), parte, font=fonte(22), fill="black", align="center")
    d.text((470, 350), "I2C → sensor → LOG", font=fonte(24, bold=True), fill="#152b44")
    d.text((470, 390), "→ log → BLE → config → I2C", font=fonte(24, bold=True), fill="#152b44")
    d.text((35, 790), "Azul: recurso → detentor. Laranja: thread → recurso solicitado. Cada recurso tem uma instância.", font=fonte(20), fill="#30445a")
    im.save(IMG / "a5-deadlock.png")


def pagina_captura(titulo, texto, destino):
    """Recebe título/saída preservada/destino; salva HTML escapado para captura real."""
    manifesto = json.loads((RESULTADOS / "manifesto.json").read_text())
    html = ("<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>" + escape(titulo)
            + "</title><style>body{margin:36px;background:#fff;color:#10283e;font:17px sans-serif}"
            + "h1{font-size:25px}pre{padding:24px;background:#f1f4f7;color:#101820;"
            + "font:16px/1.55 monospace;white-space:pre-wrap;overflow-wrap:anywhere}"
            + "p{max-width:1000px}</style><h1>" + escape(titulo) + "</h1><p>"
            + escape("Lorenzo Ferrari Aggio · D1=7 · D2=9 · N=7 · Evidência coletada em " + manifesto["data"])
            + "</p><p>Visualização da saída real preservada em resultados/. Sem valores simulados.</p><pre>"
            + escape(texto) + "</pre></html>")
    destino.write_text(html, encoding="utf-8")


def main():
    """Sem parâmetros; gera três pipelines, dois grafos e quatro páginas de captura."""
    IMG.mkdir(exist_ok=True)
    todos = {}
    for chave, ordem, fwd, titulo in (
        ("sem-forwarding", [1, 2, 3, 4, 5, 6, 7], False, "A2 — Ordem original, sem forwarding"),
        ("com-forwarding", [1, 2, 3, 4, 5, 6, 7], True, "A2 — Ordem original, com forwarding"),
        ("reordenado", [1, 3, 2, 4, 5, 6, 7], True, "A2 — Reordenado: I1, I3, I2, I4, I5, I6, I7"),
    ):
        dado = planejar(ordem, fwd)
        todos[chave] = dado
        desenhar_pipeline(dado, titulo, "a2-" + chave + ".png")
    (RESULTADOS / "pipeline.json").write_text(json.dumps(todos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    estados()
    deadlock()
    for v in (1, 2, 3):
        texto = (RESULTADOS / f"v{v}_exec1.txt").read_text()
        pagina_captura(f"A4 — Versão {v}, execução 1", texto, RESULTADOS / f"captura-v{v}.html")
    texto = (RESULTADOS / "lscpu-caches.txt").read_text()
    texto += "\n\nTrechos da saída completa de lscpu:\n"
    for linha in (RESULTADOS / "lscpu.txt").read_text().splitlines():
        if any(chave in linha for chave in ("Model name:", "Architecture:", "CPU(s):", "L1d cache:", "L1i cache:", "L2 cache:", "L3 cache:")):
            texto += linha + "\n"
    pagina_captura("A1 — Caches da máquina: saída real de lscpu", texto, RESULTADOS / "captura-caches.html")
    print({chave: (valor["ciclos"], valor["stalls"]) for chave, valor in todos.items()})


if __name__ == "__main__":
    main()
