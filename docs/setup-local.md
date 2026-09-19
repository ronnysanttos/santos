# Setup local — IA Financeira (Windows + Ollama + MT5 demo)

Guia curto para Rony Santos. Decisões travadas: **Ollama `qwen2.5:7b`**, busca **DuckDuckGo (`ddgs`)**, MT5 com **dry-run por padrão**.

---

## Onde roda o programa

| Forma | Caminho / comando |
|-------|-------------------|
| **CLI (entrada principal)** | `python -m ia_financeira` |
| Health | `python -m ia_financeira health` |
| Busca | `python -m ia_financeira search PETR4` |
| Análise | `python -m ia_financeira analyze PETR4 --pretty` |
| **GUI (duplo clique)** | `python -m ia_financeira.gui` ou `python -m ia_financeira gui` |
| **Launcher Windows** | [`scripts/launch_ia_financeira.bat`](../../scripts/launch_ia_financeira.bat) |
| **Ícone do app** | [`assets/ia_financeira.ico`](../../assets/ia_financeira.ico) (cópia em `src/ia_financeira/assets/`) |
| **Atalho na Área de Trabalho** | rode `scripts/install_desktop_shortcut.ps1` uma vez |

O `.bat` usa o `.venv` do repo (se existir), define `PYTHONPATH=src` e abre a janela gráfica.

---

## Ícone na Área de Trabalho (um comando)

No PowerShell, na pasta do repositório `santos`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_desktop_shortcut.ps1
```

Isso cria **`IA Financeira.lnk`** no Desktop, apontando para `scripts\launch_ia_financeira.bat` com o ícone `assets\ia_financeira.ico`. Depois é só dar duplo clique no atalho.

---

## 1. Pré-requisitos

| Item | Detalhe |
|------|---------|
| SO | Windows 10/11 (MT5 oficial) |
| Python | 3.10+ |
| Ollama | [ollama.com](https://ollama.com) |
| MetaTrader 5 | Terminal da corretora + **conta DEMO** |
| Repo | clone de `ronnysanttos/santos`, branch do PR |

---

## 2. Ollama (`qwen2.5:7b`)

```powershell
ollama pull qwen2.5:7b
ollama run qwen2.5:7b
```

API esperada: `http://localhost:11434`.

---

## 3. Python + projeto

```powershell
cd santos
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install MetaTrader5
copy .env.example .env
```

Edite `.env` (conta **demo**): `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`. Mantenha `MT5_DRY_RUN=true` e `MT5_ALLOW_DEMO_ORDERS=false`.

Instale o atalho:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_desktop_shortcut.ps1
```

---

## 4. MetaTrader 5 (demo)

1. Abra o MT5 e faça login na **conta demonstração**.
2. Confirme o símbolo no Market Watch (nome exato do broker).
3. Mantenha o terminal aberto enquanto usa o agente.
4. Trading automatizado só é necessário quando for testar envio real (não em dry-run).

---

## 5. Comandos do dia a dia

```powershell
# Duplo clique / GUI
.\scripts\launch_ia_financeira.bat
# ou
python -m ia_financeira gui

# CLI
python -m ia_financeira health
python -m ia_financeira search PETR4 --pretty
python -m ia_financeira analyze PETR4 --pretty
```

Em dry-run, o JSON inclui `order.status = "dry_run"` — nada é enviado ao MT5.

---

## 6. Dry-run vs envio em demo

| Modo | `.env` | Comportamento |
|------|--------|----------------|
| **Dry-run (default)** | `MT5_DRY_RUN=true` | Só registra intenção de ordem |
| **Demo send** | `MT5_DRY_RUN=false` **e** `MT5_ALLOW_DEMO_ORDERS=true` | Envia ordem a mercado |
| Bloqueado | Qualquer outro combo | Continua dry-run |

Guardrails: confiança ≥ 70%, stop diário R$ 300, pausa alto impacto. **Nunca** use conta live nesta fase.

---

## 7. Linux / CI

Sem terminal MT5: stub + dry-run. A GUI precisa de display (`tkinter`). Testes:

```bash
pip install -r requirements.txt
pytest -q
```

---

## 8. Problemas comuns

| Sintoma | Ação |
|---------|------|
| `ollama_available: false` | Subir Ollama; `ollama pull qwen2.5:7b` |
| `MetaTrader5 package unavailable` | `pip install MetaTrader5` no Windows |
| Atalho não abre | Confirme `.venv` criado e `pip install -r requirements.txt` |
| GUI não sobe | `python -m ia_financeira gui` no terminal para ver o erro |
| Símbolo não encontrado | Nome exato no Market Watch |
