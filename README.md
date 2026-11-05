# Ponderada CC08 — Lorenzo Ferrari Aggio

Análise da pulseira Tato: desempenho, pipeline, processos/threads, semáforos e deadlock, com experimentos reais e decisão de plataforma.

**Entrega:** [ponderada/ponderada-tato.md](ponderada/ponderada-tato.md).
Parâmetros: **D1=7, D2=9, N=7**, derivados de Lorenzo (7) + Ferrari (7) + Aggio (5) = 19 letras.

## Executar cada versão

Requisito: **Python 3.9 ou superior** com biblioteca padrão e base de fusos horários
disponível (testado em Python 3.13.12 no Linux). Abra um terminal na raiz desta pasta.

```bash
python3 ponderada/codigo/versao1.py
python3 ponderada/codigo/versao2.py
python3 ponderada/codigo/versao3.py
```

Cada comando executa uma rodada de 20.000 amostras, buffer de 7 posições e timeout
de 1 segundo sem recepção. A V1 contém uma corrida e a V3 contém uma ordem de
aquisição que permite deadlock, ambas intencionais. O processo termina após
registrar o timeout; não é necessário matar o terminal. V2 deve receber os IDs
de 0 a 19.999 exatamente uma vez e em ordem.

Opções para inspeção rápida ou registro independente:

```bash
python3 ponderada/codigo/versao2.py --amostras 1000 --buffer 3
python3 ponderada/codigo/versao1.py --json resultado-local.json
```

Os valores da V1 variam com o escalonamento. Uma execução sem duplicações não
significa que esteja correta: verifique perdas, leituras inválidas e ordem.
O watchdog é um mecanismo externo de observação, não corrige a sincronização.

## Reproduzir as nove medições

```bash
python3 ponderada/codigo/executar_experimentos.py
```

O executor cria três subprocessos por versão e salva JSON com todos os valores
observados, stdout/stderr, tabela CSV e manifesto com SHA-256 dos arquivos medidos.
Também captura `lscpu` e `lscpu --caches`: esta etapa requer Linux/util-linux.
**Executar novamente substitui as evidências brutas anteriores.** Faça uma cópia
se desejar preservar a coleta entregue e atualize a tabela do relatório se refizer as medições.

## Testes

```bash
python3 -m unittest discover -s ponderada/codigo/tests -v
```

Verificam contagem de perdas/duplicações/leituras inválidas, FIFO da V2 com N=1,3,7,
contenção de V1/V3 e rejeição de buffer inválido. As nove execuções do relatório
também verificam V2 com uma carga de 20.000 amostras por execução.

## Evidências e diagramas

- `ponderada/img/`: captura de caches, captura de cada versão e diagramas analíticos.
- `ponderada/resultados/`: saídas reais, observações, manifesto, CSV e páginas HTML
  que exibem os logs para captura no navegador, sem simular valores.
- `ponderada/docs/enunciado.pdf`: especificação recebida.
- `ponderada/docs/memorando-cto.pdf`: Parte B em uma página.
- `ponderada/docs/PLANO.md`: plano e continuidade da elaboração.

O utilitário opcional `python3 ponderada/codigo/gerar_apoio.py` regenera diagramas
e páginas de evidência a partir dos logs existentes. Ele requer Pillow e fontes
DejaVu (não são necessários para executar as três versões nem os testes).
As capturas do navegador e a versão paginada do memorando não são refeitas por ele.
