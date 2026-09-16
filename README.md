# Santos — EA / bot Python + MetaTrader 5

Projeto em Python para conectar ao **MetaTrader 5** e rodar um Expert Advisor com:

1. **Estratégia** Dual EMA + stops ATR  
2. **Gestão de risco** (sizing, filtros, limites)  
3. **Execução** separada (dry-run por padrão — sem ordens reais)  
4. **Backtest offline** (CSV / sintético; MT5 opcional)

## Requisitos

- **Python 3.10+**
- **Terminal MetaTrader 5** instalado e com a conta do broker configurada
- Pacote oficial [`MetaTrader5`](https://pypi.org/project/MetaTrader5/)

### Sistema operacional

| Ambiente | Suporte |
|----------|---------|
| **Windows** | Oficial e recomendado. O pacote `MetaTrader5` fala diretamente com o terminal. |
| **Linux / macOS** | O pacote oficial **não é suportado nativamente**. Em Linux, alguns usuários usam **Wine** + terminal MT5 Windows; isso é experimental. |
| **WSL** | Em geral **não funciona** de forma confiável. Prefira Python no Windows host. |

Antes de rodar o bot:

1. Abra o MetaTrader 5 e faça login na conta (**demo** recomendado).
2. Confirme que o símbolo (ex.: `EURUSD`) aparece no Market Watch.
3. Em **Ferramentas → Opções → Expert Advisors**, permita trading automatizado apenas se for testar modo live.

## Instalação

```bash
cd santos
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS (código/testes sem terminal)
source .venv/bin/activate

pip install -r requirements.txt
# ou
pip install -e .
```

## Configuração

```bash
copy .env.example .env      # Windows
# cp .env.example .env     # Linux/macOS
```

Edite `.env` com login, senha e servidor. O `.env` está no `.gitignore` — **nunca** commite senhas.

## Estratégia padrão: Dual EMA + ATR

Fluxo de decisão em cada ciclo:

```
barras/tick → DualEmaAtrStrategy → Signal
Signal + conta/posições/spread → RiskManager → TradeDecision
TradeDecision → ExecutionEngine → log (dry-run) ou order_send
```

### Regras de sinal

| Evento | Ação |
|--------|------|
| EMA rápida **cruza acima** da lenta (barra fechada) | `enter_long` |
| EMA rápida **cruza abaixo** da lenta | `enter_short` |
| Posição long + cruzamento bearish | `exit_long` |
| Posição short + cruzamento bullish | `exit_short` |
| Sem cruzamento | `hold` |

Stops sugeridos pela estratégia:

- **Long:** SL = ask − `ATR × STRATEGY_ATR_SL_MULT` · TP = ask + `ATR × STRATEGY_ATR_TP_MULT`
- **Short:** SL = bid + `ATR × STRATEGY_ATR_SL_MULT` · TP = bid − `ATR × STRATEGY_ATR_TP_MULT`

O cruzamento é avaliado na **última barra fechada** (penúltima do array), para reduzir sinais em candle incompleto.

### Regras de risco

| Regra | Comportamento |
|-------|----------------|
| **Sizing `%`** | volume ≈ (`equity × RISK_PERCENT%`) / (perda por lote até o SL) |
| **Sizing fixo** | usa `RISK_FIXED_LOTS` (respeitando min/step/max do símbolo) |
| **Max posições** | bloqueia novas entradas se `open >= RISK_MAX_POSITIONS` |
| **Perda diária** | bloqueia entradas se PnL realizado do dia (magic) ≤ −`RISK_MAX_DAILY_LOSS_PERCENT%` do balance |
| **Sessão** | fora de `[START, END)` só permite **saídas** |
| **Spread** | bloqueia entrada se `(ask−bid)/point > RISK_MAX_SPREAD_POINTS` |

Saídas por cruzamento contrário **não** são bloqueadas pelo filtro de sessão (ainda passam por dry-run).

## Variáveis de configuração

### Conexão / loop

| Variável | Descrição |
|----------|-----------|
| `MT5_PATH` | Caminho opcional do `terminal64.exe` |
| `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` | Credenciais |
| `MT5_SYMBOL` | Símbolo (ex.: `EURUSD`) |
| `MT5_TIMEFRAME_MINUTES` | Timeframe (padrão `15`) |
| `MT5_BARS` | Barras carregadas (padrão `120`) |
| `MT5_POLL_INTERVAL_SEC` | Intervalo do loop |
| `MT5_DRY_RUN` | `true` (padrão) = não envia ordens |

### Estratégia

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `STRATEGY_EMA_FAST` | `12` | Período EMA rápida |
| `STRATEGY_EMA_SLOW` | `26` | Período EMA lenta |
| `STRATEGY_ATR_PERIOD` | `14` | Período ATR (Wilder) |
| `STRATEGY_ATR_SL_MULT` | `1.5` | Multiplicador ATR → stop |
| `STRATEGY_ATR_TP_MULT` | `2.5` | Multiplicador ATR → take profit |

### Risco

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `RISK_MODE` | `percent` | `percent` ou `fixed` |
| `RISK_PERCENT` | `0.5` | % do equity arriscado por trade |
| `RISK_FIXED_LOTS` | `0.01` | Lote fixo se `RISK_MODE=fixed` |
| `RISK_MAX_POSITIONS` | `1` | Máximo de posições (mesmo magic/símbolo) |
| `RISK_MAX_DAILY_LOSS_PERCENT` | `2.0` | Limite de perda diária (`0` = off) |
| `RISK_MAX_SPREAD_POINTS` | `25` | Spread máximo (`0` = off) |
| `RISK_SESSION_START_HOUR` | `7` | Início da sessão (vazio = off) |
| `RISK_SESSION_END_HOUR` | `21` | Fim da sessão (exclusivo) |
| `RISK_MAGIC` | `9327001` | Magic number das ordens |

## Como executar

```bash
# Um ciclo: sinal + decisão + dry-run
python -m mt5_ea --once

# Loop contínuo (Ctrl+C)
python -m mt5_ea

# Outro símbolo
python -m mt5_ea --once --symbol XAUUSD

# PERIGOSO: permite order_send real
python -m mt5_ea --live
```

Após `pip install -e .`:

```bash
mt5-ea --once -v
```

## Backtest offline

O motor em `mt5_ea.backtest` replay OHLC com a **mesma** Dual EMA + ATR e o RiskManager do EA ao vivo (sizing, max posições, etc.). O backtest **nunca envia ordens** (inclusive ao usar `--mt5` só para baixar histórico).

Modelagem:

1. Sinal no **fechamento** da barra (com barra “em formação” sintética, como no live)
2. Entrada/saída por sinal no **open da barra seguinte** (com spread)
3. SL/TP checados no high/low das barras seguintes (se ambos na mesma barra, assume SL primeiro)

### Dados sintéticos / CSV (funcionam em qualquer SO)

```bash
# Demo com dados sintéticos (padrão)
python -m mt5_ea.backtest --synthetic --bars 500

# CSV local (colunas: time,open,high,low,close[,volume])
python -m mt5_ea.backtest --csv tests/fixtures/ohlc_eurusd_m15.csv --lots 0.10 --trades

# Parâmetros de estratégia / sizing %
python -m mt5_ea.backtest --synthetic --ema-fast 8 --ema-slow 21 --atr-sl 1.5 --atr-tp 2.5 --risk-percent 0.5
```

### Histórico real do MetaTrader 5 (`--mt5`)

Requisitos **obrigatórios**:

1. **Windows** (ou Wine experimental) — o pacote PyPI `MetaTrader5` **não instala em Linux nativo**
2. Terminal **MetaTrader 5 aberto** e logado na conta
3. Arquivo `.env` com `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` (veja `.env.example`)
4. Símbolo visível no Market Watch

```bash
# Últimas 5000 barras M15 (copy_rates_from_pos) — só leitura, sem ordens
python -m mt5_ea.backtest --mt5 --symbol EURUSD --timeframe M15 --bars 5000 --trades

# Range por data (copy_rates_range)
python -m mt5_ea.backtest --mt5 --symbol EURUSD --timeframe H1 --from 2024-01-01 --to 2024-12-31

# Salvar relatório JSON
python -m mt5_ea.backtest --mt5 --symbol EURUSD --timeframe M15 --bars 5000 \
  --output-json backtest_eurusd_m15.json
```

Timeframes aceitos: `M1`…`M30`, `H1`…`H12`, `D1`, `W1`, `MN1` (ou minutos: `15`, `60`).

Se o terminal não estiver disponível, use `--csv` / `--synthetic`. Em ambientes Linux/CI o comando `--mt5` deve falhar com mensagem clara (pacote/terminal ausente).

Métricas impressas: lucro líquido, win rate, max drawdown, profit factor, nº de trades e resumo da curva de equity.

## Estrutura

```
src/mt5_ea/
  config.py        # Settings (.env)
  connection.py    # MT5: login, ticks, barras, posições, ordens
  indicators.py    # EMA / ATR (puro, testável)
  strategy.py      # Dual EMA + ATR → Signal
  risk.py          # filtros + sizing → TradeDecision
  execution.py     # TradeDecision → dry-run / MT5
  ea.py            # loop do EA
  backtest/        # motor offline + CLI
    data.py        # CSV / sintético / MT5 copy_rates_*
    engine.py      # replay OHLC
    metrics.py     # lucro, DD, PF, equity curve
    __main__.py    # python -m mt5_ea.backtest
  timeframes.py    # parse M15/H1/…
tests/
  fixtures/        # OHLC de exemplo para CI
```

## Testes (sem MetaTrader)

```bash
pip install pytest python-dotenv
PYTHONPATH=src pytest -q
```

## Segurança

- `MT5_DRY_RUN=true` por padrão; `--live` é explícito e loga aviso.
- Use conta **demo** enquanto calibra EMA/ATR/risco.
- Não coloque senhas no código nem no Git — apenas em `.env` local.
- Backtest é simulação: resultados passados não garantem performance futura.

## Licença / uso

Scaffold para desenvolvimento. Trading envolve risco; você é responsável pelas ordens enviadas ao broker.
