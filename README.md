---
title: SalesOps AI
emoji: 📊
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# SalesOps AI — Agente de Operações Comerciais Multicanal

Um **COO digital** para operações de e-commerce: monitora suas lojas em
diferentes marketplaces (Shopee, Mercado Livre, Amazon), audita os anúncios,
acompanha as métricas, detecta o que mudou desde ontem e te entrega um
**relatório executivo diário** com diagnóstico, hipóteses de causa e **ações
priorizadas** — em português, no terminal e em arquivo Markdown.

O raciocínio (diagnóstico + decisão) é feito pelo **Claude**; toda a coleta e
análise de dados é determinística, então o modelo recebe números reais e não
inventa métricas.

> Estado: **MVP funcional**. Conectores reais já fazem as chamadas às APIs dos
> marketplaces quando há credenciais; sem credenciais, o agente roda com **dados
> de exemplo** para você ver o resultado de imediato.

---

## As 7 camadas do agente

| # | Camada | Módulo | O que faz |
|---|--------|--------|-----------|
| 1 | Memória histórica | `engine/memory.py` | Guarda a foto de cada dia e o que já foi feito; responde "o que mudou em 24h?" |
| 2 | Auditor de marketplace | `engine/auditor.py` | Acha anúncio sem foto, estoque zerado, Buy Box perdida, reputação ruim, campanha no prejuízo… |
| 3 | Motor de métricas | `engine/metrics.py` | Receita, pedidos, ticket médio, ROAS por canal e consolidado + score de saúde |
| 4 | Detector de anomalias | `engine/detector.py` | Quedas bruscas de receita/vendas vs. o histórico |
| 5+6 | Diagnóstico + decisão | `engine/reporter.py` | Hipóteses de causa e ações priorizadas (via Claude) |
| 7 | Comunicação executiva | relatório `.md` | Relatório diário no terminal e em `data/reports/` |

O orquestrador (`brain.py`) executa as camadas em sequência a cada rodada.

---

## Instalação

```bash
pip install -r requirements.txt
cp .env.example .env   # edite com suas credenciais (opcional)
```

Requer Python 3.10+.

---

## Uso

```bash
# Relatório do dia (usa dados de exemplo se não houver credenciais)
python run.py run

# Um dia específico
python run.py run --date 2026-06-15

# Registrar uma ação tomada (alimenta a memória do agente)
python run.py log-action "Reposto estoque do SKU SHP-001" --channel shopee

# Ver os dias já analisados
python run.py history
```

Equivalente: `python -m salesops run`.

O relatório é impresso no terminal e salvo em
`data/reports/<cliente>/<data>.md`. O histórico fica em
`data/history/<cliente>/`.

### Rodada diária automática (cron)

```bash
# Todo dia às 8h
0 8 * * *  cd /caminho/agente-organizacional && python run.py run >> /var/log/salesops.log 2>&1
```

---

## Painel web (GitHub Pages)

O agente tem um **painel web estático** em `docs/` que roda no GitHub Pages —
igual a um site comum. Como o GitHub Pages só serve arquivos estáticos, o
"cérebro" Python **não roda no navegador**: ele gera um `docs/report.json` que
o painel lê. Esses dados são produzidos pelo agente (na sua máquina ou via
GitHub Actions) e publicados como arquivo estático.

```bash
# Gera/atualiza os dados do painel
python run.py build-web

# Pré-visualiza localmente
python -m http.server -d docs
# abra http://localhost:8000
```

### Publicar no GitHub Pages (automático)

1. Faça merge desta branch na `main`.
2. No GitHub: **Settings → Pages → Source: GitHub Actions**.
3. (Opcional) Em **Settings → Secrets and variables → Actions**, cadastre as
   credenciais como *secrets* (`ANTHROPIC_API_KEY`, `ML_ACCESS_TOKEN`, etc.) e
   o nome do cliente como *variable* (`SALESOPS_CLIENT`).

O workflow `.github/workflows/pages.yml` roda o agente (todo dia às 8h UTC, ou
manualmente) e publica o painel em `https://<usuário>.github.io/agente-organizacional/`.
Sem credenciais, ele publica com **dados de exemplo**; com credenciais, com
**dados reais + diagnóstico do Claude**.

> Por que não roda 100% no Pages como o outro site? Porque este agente precisa
> de um backend (Python) e de chaves secretas — que não podem ficar no
> navegador. O GitHub Actions faz o papel desse backend e publica o resultado.

---

## App completo com painel glass (Hugging Face Spaces)

Além do painel estático, o projeto inclui um **app full-stack** (backend FastAPI
+ front *glassmorphism*) onde você **cadastra cada loja com a API dela**, com
**uma aba por loja** e **dados reais**. Como precisa de backend (guardar
credenciais e chamar as APIs com segurança), ele **não roda no GitHub Pages** —
roda num **Hugging Face Space (Docker)**.

### Rodar localmente

```bash
pip install -r requirements.txt
uvicorn server.app:app --reload --port 8000
# abra http://localhost:8000
```

Na tela: **➕ Nova loja** → escolha o marketplace → preencha os campos de API →
salvar. Cada loja vira uma aba com seu dashboard (saúde, alertas, oportunidades,
ações e métricas) e um botão **🧠 Relatório** (diagnóstico do Claude).

### Publicar no Hugging Face Spaces

1. Crie um Space em **https://huggingface.co/new-space**: SDK **Docker**, em
   branco, **Private** (recomendado, pois guarda credenciais).
2. Crie um token de escrita em **https://huggingface.co/settings/tokens**.
3. No GitHub: **Settings → Secrets and variables → Actions**:
   - *Secret* `HF_TOKEN` = o token.
   - *Variable* `HF_SPACE` = `SeuUsuario/nome-do-space` (ex.: `Maycaco/salesops-ai`).
4. O workflow `.github/workflows/hf-space.yml` publica o app no Space (a cada
   push ou via **Actions → Run workflow**).
5. *(Opcional)* No Space, em **Settings**: adicione o *secret* `ANTHROPIC_API_KEY`
   (para os relatórios do Claude) e habilite **Persistent storage** com
   `SALESOPS_STORE_FILE=/data/stores.json` para manter as lojas entre reinícios.

> As credenciais das lojas ficam **no servidor** (no Space), nunca no navegador
> nem no repositório (`data/` é ignorado pelo git).

---

## Configuração (.env)

| Variável | Para quê |
|----------|----------|
| `SALESOPS_CLIENT` | Nome do cliente/loja no relatório |
| `SALESOPS_CHANNELS` | Canais a analisar: `shopee,mercado_livre,amazon` |
| `ANTHROPIC_API_KEY` | Liga o diagnóstico pelo Claude (sem ela, usa regras) |
| `SALESOPS_MODEL` | Modelo do Claude (padrão `claude-opus-4-8`) |
| `SALESOPS_DROP_THRESHOLD` | % de queda que dispara alerta (padrão 20) |
| Credenciais por canal | Veja abaixo |

**Credenciais dos marketplaces** (cada canal sem credenciais usa dados de exemplo):

- **Mercado Livre** — `ML_ACCESS_TOKEN` (OAuth2). `ML_SELLER_ID` é descoberto sozinho.
- **Shopee** — `SHOPEE_PARTNER_ID`, `SHOPEE_PARTNER_KEY`, `SHOPEE_SHOP_ID`, `SHOPEE_ACCESS_TOKEN`.
- **Amazon SP-API** — `AMAZON_LWA_CLIENT_ID`, `AMAZON_LWA_CLIENT_SECRET`, `AMAZON_REFRESH_TOKEN`.

O modo de diagnóstico e as fontes de dados de cada canal são informados no
rodapé de cada execução.

---

## Exemplo de relatório

```markdown
# Relatório diário — 2026-06-15
**Cliente:** Loja XPTO

## Situação geral
Saúde operacional: 69%. Receita do dia: R$ 5.975,46 (▲ +9% vs. ontem).

## 🚨 Alertas críticos
- 🔴 [Shopee] 'Fone Bluetooth XYZ Pro' está ativo com estoque zerado.
- 🔴 [Amazon] Buy Box perdida em 'Liquidificador Power 1200W'.
- 🟠 [Mercado Livre] Reputação amarela e 14 perguntas sem resposta.

## ✅ Ações recomendadas hoje
**Prioridade alta**
- [Shopee] Repor estoque ou pausar para não perder posicionamento.
- [Amazon] Revisar preço vs. concorrência para recuperar a Buy Box.
```

---

## Testes

```bash
pip install pytest
pytest -q
```

Os testes rodam o pipeline inteiro com dados de exemplo (sem rede, sem chave).

---

## Arquitetura

```
run.py / python -m salesops
        │
        ▼
   salesops/brain.py  ── orquestra as 7 camadas
        │
        ├── connectors/      coleta (Shopee · Mercado Livre · Amazon · exemplo)
        ├── engine/memory    camada 1 — histórico
        ├── engine/auditor   camada 2 — problemas técnicos
        ├── engine/metrics   camada 3 — métricas + saúde
        ├── engine/detector  camada 4 — anomalias
        └── engine/reporter  camadas 5-7 — diagnóstico + relatório (Claude)
```

### Roadmap (próximos passos)

- Campanhas reais: Meta Ads, Google Ads e Ads dos marketplaces.
- Amazon: catálogo, Buy Box e preço da concorrência via Listings/Pricing.
- Entrega do relatório por WhatsApp / Telegram / e-mail.
- Dashboard e tendências de várias semanas.
