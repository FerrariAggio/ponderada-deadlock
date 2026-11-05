"""Executa três rodadas de cada versão em processos isolados e preserva evidências."""

import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import shlex
import subprocess
import sys
from zoneinfo import ZoneInfo


def main():
    """Sem parâmetros; grava nove JSONs, logs, CSV, manifesto e saída real de lscpu."""
    root = Path(__file__).resolve().parents[2]
    resultados = root / "ponderada/resultados"
    resultados.mkdir(exist_ok=True)
    registros = []
    for versao in (1, 2, 3):
        for rodada in (1, 2, 3):
            arquivo = f"ponderada/resultados/v{versao}_exec{rodada}.json"
            comando = [sys.executable, f"ponderada/codigo/versao{versao}.py", "--json", arquivo]
            processo = subprocess.run(comando, cwd=root, capture_output=True, text=True, timeout=60)
            (resultados / f"v{versao}_exec{rodada}.txt").write_text(
                "$ " + shlex.join(comando) + "\n" + processo.stdout,
                encoding="utf-8",
            )
            (resultados / f"v{versao}_exec{rodada}.stderr.txt").write_text(processo.stderr, encoding="utf-8")
            processo.check_returncode()
            dado = json.loads((root / arquivo).read_text(encoding="utf-8"))
            registros.append({
                "versao": versao, "execucao": rodada,
                **{chave: dado[chave] for chave in (
                    "N", "planejadas", "produzidas", "consumidas", "unicas", "perdidas",
                    "duplicadas", "invalidas", "inversoes_ordem", "travou", "duracao_s",
                )},
            })
            print(f"V{versao}/{rodada}: consumidas={dado['consumidas']} "
                  f"perdidas={dado['perdidas']} duplicadas={dado['duplicadas']} "
                  f"travou={dado['travou']}", flush=True)
    with (resultados / "resumo.csv").open("w", encoding="utf-8", newline="") as arquivo_csv:
        writer = csv.DictWriter(arquivo_csv, fieldnames=list(registros[0]))
        writer.writeheader()
        writer.writerows(registros)
    for argumentos, nome in ((["lscpu"], "lscpu.txt"), (["lscpu", "--caches"], "lscpu-caches.txt")):
        saida = subprocess.run(argumentos, capture_output=True, text=True, check=True)
        (resultados / nome).write_text("$ " + shlex.join(argumentos) + "\n" + saida.stdout, encoding="utf-8")
    fontes = ["experimento.py", "versao1.py", "versao2.py", "versao3.py", "executar_experimentos.py"]
    hashes = {"ponderada/codigo/" + nome: hashlib.sha256((root / "ponderada/codigo" / nome).read_bytes()).hexdigest()
              for nome in fontes}
    hashes["ponderada/parametros.json"] = hashlib.sha256((root / "ponderada/parametros.json").read_bytes()).hexdigest()
    manifesto = {
        "data": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "python": platform.python_version(), "executavel": sys.executable,
        "sistema": platform.platform(), "diretorio_de_execucao": str(root),
        "hashes_sha256": hashes,
        "metodo": "9 subprocessos reais; 20.000 amostras; watchdog de 1 s; sem resultados simulados",
    }
    (resultados / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
