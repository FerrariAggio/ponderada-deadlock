"""CC08: buffer circular produtor–consumidor, corrida e deadlock deliberados.

O código representa um experimento de concorrência, não firmware de tempo real.
V1 não sincroniza os dados; V2 usa três semáforos; V3 troca duas aquisições.
O watchdog observa progresso, sem liberar os recursos que causaram o bloqueio.
"""

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import platform
import sys
import threading
import time
from zoneinfo import ZoneInfo


def medir(observacoes, total):
    """Recebe IDs observados e total planejado; retorna métricas de integridade.

    Perdidas são IDs de 0..total-1 não recebidos, inclusive os não produzidos
    quando há interrupção. Duplicadas são ocorrências excedentes de IDs válidos.
    None ou IDs fora do intervalo são leituras inválidas, não amostras consumidas.
    """
    validas = [x for x in observacoes if isinstance(x, int) and 0 <= x < total]
    contagem = Counter(validas)
    return {
        "consumidas": len(validas),
        "unicas": len(contagem),
        "perdidas": total - len(contagem),
        "duplicadas": sum(n - 1 for n in contagem.values()),
        "invalidas": len(observacoes) - len(validas),
        "inversoes_ordem": sum(b < a for a, b in zip(validas, validas[1:])),
    }


class Experimento:
    """Estado de uma execução; índices pertencem a um produtor e um consumidor."""

    def __init__(self, versao, capacidade, total, timeout):
        """Recebe versão 1..3, capacidade, total e timeout em segundos; cria estado."""
        if versao not in (1, 2, 3) or capacidade <= 0 or total <= 0 or timeout <= 0:
            raise ValueError("Versão inválida ou parâmetro não positivo")
        self.versao = versao
        self.n = capacidade
        self.total = total
        self.timeout = timeout
        self.buffer = [None] * capacidade
        self.escrita = 0
        self.leitura = 0
        self.ocupados = 0
        self.produzidas = 0
        self.observacoes = []
        self.validas = 0
        self.ultimo_recebimento = time.monotonic()
        self.parar = threading.Event()
        self.consumidor_terminou = threading.Event()
        self.erros = []
        self.vazio = threading.Semaphore(capacidade)
        self.cheio = threading.Semaphore(0)
        self.mutex = threading.Semaphore(1)
        self.esperando = {"produtor": "iniciando", "consumidor": "iniciando"}
        self.dono_mutex = None

    def inserir(self, amostra):
        """Insere o ID recebido; sem proteção própria, exige a política da versão."""
        self.buffer[self.escrita] = amostra
        self.escrita = (self.escrita + 1) % self.n
        anterior = self.ocupados
        if self.versao == 1:
            time.sleep(0)  # cessão entre ler e escrever: atualização não atômica
        self.ocupados = anterior + 1
        self.produzidas += 1

    def retirar(self):
        """Remove a posição atual; retorna ID ou None quando a corrida corrompe o fluxo."""
        amostra = self.buffer[self.leitura]
        self.buffer[self.leitura] = None
        self.leitura = (self.leitura + 1) % self.n
        anterior = self.ocupados
        if self.versao == 1:
            time.sleep(0)
        self.ocupados = anterior - 1
        return amostra

    def adquirir(self, nome, ator):
        """Recebe nome do semáforo e ator; bloqueia na aquisição e registra a espera."""
        self.esperando[ator] = nome
        getattr(self, nome).acquire()
        self.esperando[ator] = "executando"
        if nome == "mutex":
            self.dono_mutex = ator

    def liberar_mutex(self):
        """Sem argumentos; registra devolução e libera o semáforo binário."""
        self.dono_mutex = None
        self.mutex.release()

    def produzir(self):
        """Sem argumentos/retorno; publica IDs sequenciais conforme a versão escolhida."""
        try:
            for amostra in range(self.total):
                if self.parar.is_set():
                    break
                if self.versao == 1:
                    self.esperando["produtor"] = "polling_buffer_cheio"
                    while self.ocupados >= self.n and not self.parar.is_set():
                        time.sleep(0)
                    if self.parar.is_set():
                        break
                    self.inserir(amostra)
                else:
                    # A única diferença operacional entre V2 e V3 é esta ordem.
                    ordem = ("mutex", "vazio") if self.versao == 3 else ("vazio", "mutex")
                    for nome in ordem:
                        self.adquirir(nome, "produtor")
                    self.inserir(amostra)
                    self.liberar_mutex()
                    self.cheio.release()
            self.esperando["produtor"] = "terminou"
        except Exception as error:
            self.erros.append(f"produtor: {type(error).__name__}: {error}")
            self.parar.set()

    def consumir(self):
        """Sem argumentos/retorno; registra valores reais até receber o total ou parar."""
        try:
            while self.validas < self.total and not self.parar.is_set():
                if self.versao == 1:
                    self.esperando["consumidor"] = "polling_buffer_vazio"
                    while self.ocupados <= 0 and not self.parar.is_set():
                        time.sleep(0)
                    if self.parar.is_set():
                        break
                    amostra = self.retirar()
                else:
                    self.adquirir("cheio", "consumidor")
                    self.adquirir("mutex", "consumidor")
                    amostra = self.retirar()
                    self.liberar_mutex()
                    self.vazio.release()
                self.observacoes.append(amostra)
                if isinstance(amostra, int) and 0 <= amostra < self.total:
                    self.validas += 1
                    self.ultimo_recebimento = time.monotonic()
            self.esperando["consumidor"] = "terminou"
        except Exception as error:
            self.erros.append(f"consumidor: {type(error).__name__}: {error}")
            self.parar.set()
        finally:
            self.consumidor_terminou.set()

    def executar(self):
        """Sem argumentos; retorna métricas e observações, contendo bloqueios por watchdog.

        Threads são daemon para o processo experimental poder terminar após registrar
        um deadlock. A execução em subprocesso evita acumular essas threads entre rodadas.
        Instrumentação tem um escritor por campo; não protege a região crítica da V1.
        """
        inicio = time.monotonic()
        self.ultimo_recebimento = inicio
        produtor = threading.Thread(target=self.produzir, name="sensor", daemon=True)
        consumidor = threading.Thread(target=self.consumir, name="motor", daemon=True)
        produtor.start()
        consumidor.start()
        motivo = "concluido"
        while not self.consumidor_terminou.is_set() and not self.erros:
            if time.monotonic() - self.ultimo_recebimento >= self.timeout:
                motivo = "timeout_sem_amostra"
                break
            self.parar.wait(0.005)
        self.parar.set()
        # Não liberar artificialmente mutex/vazio: isso apagaria o deadlock observado.
        produtor.join(0.05)
        consumidor.join(0.05)
        if self.erros:
            motivo = "erro"
        observacoes = self.observacoes.copy()
        return {
            "versao": self.versao, "N": self.n, "planejadas": self.total,
            "timeout_s": self.timeout,
            "data": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
            "python": platform.python_version(), "sistema": platform.platform(),
            "produzidas": self.produzidas,
            **medir(observacoes, self.total),
            "travou": motivo == "timeout_sem_amostra", "motivo": motivo,
            "duracao_s": round(time.monotonic() - inicio, 6),
            "estado_final": {
                "ocupados": self.ocupados, "escrita": self.escrita,
                "leitura": self.leitura, "dono_mutex": self.dono_mutex,
                "esperando": self.esperando.copy(),
                "produtor_vivo": produtor.is_alive(),
                "consumidor_vivo": consumidor.is_alive(),
            },
            "erros": self.erros.copy(), "observacoes": observacoes,
        }


def inteiro_positivo(texto):
    """Converte texto em inteiro positivo; retorna int ou erro legível do argparse."""
    numero = int(texto)
    if numero <= 0:
        raise argparse.ArgumentTypeError("O valor deve ser um inteiro positivo")
    return numero


def main(versao):
    """Recebe versão fixa da entrada CLI; executa, imprime resumo e salva JSON opcional."""
    parametros = json.loads((Path(__file__).resolve().parents[1] / "parametros.json").read_text())
    parser = argparse.ArgumentParser(description=f"CC08 — versão {versao} do buffer circular")
    parser.add_argument("--buffer", type=inteiro_positivo, default=parametros["N"])
    parser.add_argument("--amostras", type=inteiro_positivo, default=parametros["amostras"])
    parser.add_argument("--timeout", type=float, default=1.0, help="segundos sem amostra (padrão: 1)")
    parser.add_argument("--json", type=Path, help="arquivo de resultados brutos, incluindo IDs")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("O timeout deve ser positivo")
    result = Experimento(versao, args.buffer, args.amostras, args.timeout).executar()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"CC08 | V{versao} | N={args.buffer} | amostras={args.amostras}")
    print(f"Data: {result['data']} | Python {result['python']}")
    for label in ("produzidas", "consumidas", "unicas", "perdidas", "duplicadas", "invalidas", "inversoes_ordem"):
        print(f"{label}: {result[label]}")
    print(f"travou: {'sim' if result['travou'] else 'nao'} | motivo: {result['motivo']}")
    print(f"duracao_s: {result['duracao_s']}")
    print("estado_final:", json.dumps(result["estado_final"], ensure_ascii=False))
    if result["erros"]:
        print("erros:", result["erros"], file=sys.stderr)
        raise SystemExit(1)

