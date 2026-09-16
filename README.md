# Santos — EA / bot Python + MetaTrader 5

Projeto em Python para conectar ao **MetaTrader 5**, ler dados de conta/símbolo e rodar um loop estilo Expert Advisor (EA). Por padrão opera em **dry-run** (não envia ordens reais).

## Requisitos

- **Python 3.10+**
- **Terminal MetaTrader 5** instalado e com a conta do broker configurada
- Pacote oficial [`MetaTrader5`](https://pypi.org/project/MetaTrader5/)

### Sistema operacional

| Ambiente | Suporte |
|----------|---------|
| **Windows** | Oficial e recomendado. O pacote `MetaTrader5` fala diretamente com o terminal. |
| **Linux / macOS** | O pacote oficial **não é suportado nativamente**. Em Linux, alguns usuários usam **Wine** + terminal MT5 Windows; isso é experimental e fora do escopo deste scaffold. |
| **WSL** | Em geral **não funciona** de forma confiável (o bridge precisa do processo Windows do terminal). Prefira Python no Windows host. |

Antes de rodar o bot:

1. Abra o MetaTrader 5 e faça login na conta (demo recomendado).
2. Confirme que o símbolo desejado (ex.: `EURUSD`) aparece no Market Watch.
3. Em **Ferramentas → Opções → Expert Advisors**, permita trading automatizado se for testar modo live (não necessário para dry-run de leitura).

## Instalação

```bash
# Clone o repositório e entre na pasta
cd santos

# (opcional) ambiente virtual
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS (sem MT5 nativo — só para inspecionar o código)
source .venv/bin/activate

# Dependências
pip install -r requirements.txt

# Ou instalação editável do pacote
pip install -e .
```

## Configuração (sem segredos no Git)

```bash
copy .env.example .env      # Windows
# cp .env.example .env     # Linux/macOS
```

Edite `.env` com login, senha e servidor do broker. O arquivo `.env` está no `.gitignore` — **nunca** commite senhas.

Principais variáveis:

| Variável | Descrição |
|----------|-----------|
| `MT5_PATH` | Caminho opcional do `terminal64.exe` |
| `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` | Credenciais da conta |
| `MT5_SYMBOL` | Símbolo padrão (ex.: `EURUSD`) |
| `MT5_TIMEFRAME_MINUTES` | Timeframe das barras (5, 15, 60…) |
| `MT5_DRY_RUN` | `true` (padrão) = não envia ordens |

## Como executar

```bash
# Um ciclo: conecta, imprime conta + tick + barras + sinal da estratégia, e sai
python -m mt5_ea --once

# Loop contínuo (Ctrl+C para parar)
python -m mt5_ea

# Símbolo diferente
python -m mt5_ea --once --symbol XAUUSD

# PERIGOSO: desativa dry-run (ordens reais possíveis se a estratégia gerar buy/sell)
python -m mt5_ea --live
```

Após `pip install -e .` também funciona:

```bash
mt5-ea --once
```

## Estrutura

```
src/mt5_ea/
  config.py       # Settings a partir do .env
  connection.py   # initialize, login, account/symbol/tick/rates, shutdown
  strategy.py     # Hook placeholder (sempre hold)
  ea.py           # Loop do EA (dry-run por padrão)
  __main__.py     # python -m mt5_ea
```

## Segurança

- `MT5_DRY_RUN=true` por padrão; a estratégia placeholder só retorna `hold`.
- Use conta **demo** enquanto desenvolve.
- Não coloque senhas no código nem no repositório — apenas em `.env` local.

## Licença / uso

Projeto de scaffolding para desenvolvimento. Trading envolve risco; você é responsável pelas ordens enviadas ao broker.
