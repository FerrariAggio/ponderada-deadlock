"""Testes comportamentais das métricas, FIFO e contenção dos experimentos CC08."""

import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CODIGO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODIGO))
try:
    experimento = importlib.import_module("experimento")
except ModuleNotFoundError:
    experimento = None


class TestExperimento(unittest.TestCase):
    """Verifica resultados reais, sem exigir uma intercalação específica da V1."""

    def setUp(self):
        """Sem parâmetros; falha explicitamente se a implementação não existir."""
        self.assertIsNotNone(experimento, "Motor de experimentos ainda não implementado")

    def rodar_cli(self, versao, n=7, total=600, timeout=0.3):
        """Executa versão/n/total/timeout reais; retorna JSON salvo pelo processo."""
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "resultado.json"
            process = subprocess.run(
                [sys.executable, str(CODIGO / f"versao{versao}.py"),
                 "--buffer", str(n), "--amostras", str(total),
                 "--timeout", str(timeout), "--json", str(output)],
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertTrue(output.is_file(), process.stdout)
            return json.loads(output.read_text(encoding="utf-8"))

    def test_metricas_diferenciam_perda_duplicacao_e_leitura_invalida(self):
        """Detecta erro ao contar IDs únicos, repetições ou entradas fora do domínio."""
        result = experimento.medir([0, 1, 1, 4, None, 99], 5)
        self.assertEqual(result["consumidas"], 4)
        self.assertEqual(result["unicas"], 3)
        self.assertEqual(result["perdidas"], 2)
        self.assertEqual(result["duplicadas"], 1)
        self.assertEqual(result["invalidas"], 2)

    def test_v2_preserva_todos_os_ids_em_ordem_com_buffer_minimo(self):
        """Detecta remoção de proteção/sinalização: N=1 deve manter FIFO completo."""
        result = self.rodar_cli(2, n=1)
        self.assertEqual(result["observacoes"], list(range(600)))
        self.assertEqual(result["produzidas"], 600)
        self.assertEqual(result["perdidas"], 0)
        self.assertEqual(result["duplicadas"], 0)
        self.assertFalse(result["travou"])

    def test_v2_preserva_fifo_apos_varias_voltas_do_buffer(self):
        """Detecta índice circular errado ou sobrescrita de item ainda não consumido."""
        for n in (3, 7):
            with self.subTest(n=n):
                result = self.rodar_cli(2, n=n)
                self.assertEqual(result["observacoes"], list(range(600)))
                self.assertEqual(result["invalidas"], 0)
                self.assertFalse(result["travou"])

    def test_v1_encerra_e_contabiliza_a_execucao_real(self):
        """Detecta ausência de watchdog; a corrida não precisa ocorrer em todo teste."""
        result = self.rodar_cli(1, n=3, total=200, timeout=0.1)
        expected = experimento.medir(result["observacoes"], 200)
        for key in ("consumidas", "unicas", "perdidas", "duplicadas", "invalidas"):
            self.assertEqual(result[key], expected[key])
        self.assertLess(result["duracao_s"], 5)

    def test_v3_nao_prende_o_processo_que_registra_o_resultado(self):
        """Detecta join infinito quando as threads adquirem semáforos na ordem errada."""
        result = self.rodar_cli(3, n=1, total=200, timeout=0.1)
        self.assertLess(result["duracao_s"], 5)
        self.assertIn(result["motivo"], ("concluido", "timeout_sem_amostra"))
        if result["travou"]:
            self.assertLess(result["consumidas"], 200)

    def test_cli_rejeita_buffer_zero(self):
        """Detecta aceitação de capacidade inválida, que levaria a divisão por zero."""
        process = subprocess.run(
            [sys.executable, str(CODIGO / "versao2.py"), "--buffer", "0"],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(process.returncode, 2)
        self.assertIn("positivo", process.stderr)


if __name__ == "__main__":
    unittest.main()
