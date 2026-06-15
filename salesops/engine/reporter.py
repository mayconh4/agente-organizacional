"""Camadas 5-7 — Diagnóstico, decisão e comunicação executiva.

Recebe os achados estruturados (problemas, métricas, anomalias, ações recentes)
e produz o relatório executivo diário em Markdown. O raciocínio (hipóteses +
ações priorizadas) é feito pelo Claude; se não houver ANTHROPIC_API_KEY ou a
chamada falhar, cai para um gerador determinístico por regras — o agente nunca
fica sem entregar relatório.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from ..config import Settings
from ..models import Anomaly, Channel, Issue, Metric, Severity, StoreSnapshot

SYSTEM_PROMPT = """\
Você é o SalesOps AI, o gestor operacional de e-commerce da empresa — um COO \
digital obcecado por lucro e crescimento. Você acompanha continuamente todas \
as lojas em marketplaces (Shopee, Mercado Livre, Amazon).

Você recebe dados JÁ COLETADOS E ANALISADOS de um dia: problemas técnicos \
encontrados, métricas (com comparação ao dia anterior), anomalias detectadas e \
o que já foi feito recentemente. Seu trabalho NÃO é repetir os dados — é pensar \
como gestor:

1. Identificar o que está quebrado, piorando, melhorando e o que vira venda rápida.
2. Levantar HIPÓTESES de causa para cada problema relevante.
3. Recomendar AÇÕES concretas e priorizadas (alta/média/baixa).
4. Ser direto e executivo. Falar em português do Brasil.

Regras rígidas:
- Use APENAS os números fornecidos no contexto. NUNCA invente métricas, valores \
  ou fatos que não estejam nos dados.
- Conecte os pontos entre canais quando fizer sentido.
- Cada ação deve ser específica e acionável (não "melhorar o anúncio", e sim \
  "subir foto em fundo branco no SKU X").

Responda SOMENTE com o relatório em Markdown, seguindo exatamente esta estrutura:

# Relatório diário — {data}
**Cliente:** {cliente}

## Situação geral
(2-4 frases + a saúde operacional já informada)

## 🚨 Alertas críticos
(lista priorizada; se não houver, diga que não há)

## 📈 Oportunidades
(o que está indo bem e dá para escalar/aproveitar hoje)

## 🔍 Diagnóstico e hipóteses
(para os principais problemas: hipóteses de causa)

## ✅ Ações recomendadas hoje
**Prioridade alta**
- ...
**Prioridade média**
- ...
**Prioridade baixa**
- ...
"""


# --------------------------------------------------------------------------- #
def build_context(
    store: StoreSnapshot,
    issues: list[Issue],
    metrics: list[Metric],
    anomalies: list[Anomaly],
    health: int,
    channel_health: dict[str, int],
    recent_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Monta o dicionário estruturado entregue ao cérebro."""
    return {
        "cliente": store.client,
        "data": store.snapshot_date,
        "saude_operacional": health,
        "saude_por_canal": {Channel.label(c): h for c, h in channel_health.items()},
        "metricas": [m.to_dict() for m in metrics],
        "problemas": [i.to_dict() for i in issues],
        "anomalias": [a.to_dict() for a in anomalies],
        "acoes_recentes": recent_actions,
        "canais_analisados": [Channel.label(c.channel) for c in store.channels],
    }


def generate_report(settings: Settings, context: dict[str, Any]) -> tuple[str, str]:
    """Gera o relatório. Retorna (markdown, motor) onde motor ∈ {'claude','regras'}."""
    if settings.anthropic_api_key:
        try:
            return _claude_report(settings, context), "claude"
        except Exception as exc:  # rede, SDK, autenticação...
            fallback = _rule_based_report(context)
            note = (f"\n\n> ⚠️ Diagnóstico por regras (a chamada ao Claude falhou: "
                    f"{type(exc).__name__}). Confira ANTHROPIC_API_KEY/SALESOPS_MODEL.")
            return fallback + note, "regras"
    return _rule_based_report(context), "regras"


# --------------------------------------------------------------------------- #
def _claude_report(settings: Settings, context: dict[str, Any]) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user_msg = (
        "Aqui estão os dados já coletados e analisados do dia. "
        "Gere o relatório executivo seguindo a estrutura definida.\n\n"
        "```json\n" + json.dumps(context, ensure_ascii=False, indent=2) + "\n```"
    )
    # Streaming + get_final_message protege contra timeouts em respostas longas.
    with client.messages.stream(
        model=settings.model,
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        message = stream.get_final_message()

    parts = [b.text for b in message.content if b.type == "text"]
    text = "\n".join(parts).strip()
    if not text:
        raise RuntimeError("resposta vazia do modelo")
    return text


# --------------------------------------------------------------------------- #
# Gerador determinístico (fallback / modo offline)
# --------------------------------------------------------------------------- #
_SEV_LABEL = {
    Severity.CRITICA: "🔴 Crítico",
    Severity.ALTA: "🟠 Alta",
    Severity.MEDIA: "🟡 Média",
    Severity.BAIXA: "⚪ Baixa",
}


def _fmt_metric(m: dict[str, Any]) -> str:
    unit = m["unit"]
    val = m["value"]
    if unit == "R$":
        value = f"R$ {val:,.2f}"
    elif unit == "x":
        value = f"{val:.2f}x"
    elif unit == "%":
        value = f"{val:.1f}%"
    else:
        value = f"{val:g} {unit}".strip()
    delta = m.get("delta_pct")
    if delta is None:
        return value
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "■")
    return f"{value} ({arrow} {delta:+.0f}% vs. ontem)"


def _rule_based_report(ctx: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Relatório diário — {ctx['data']}")
    lines.append(f"**Cliente:** {ctx['cliente']}")
    lines.append("")

    # Situação geral
    lines.append("## Situação geral")
    lines.append(f"Saúde operacional: **{ctx['saude_operacional']}%**.")
    saude_canal = ctx.get("saude_por_canal") or {}
    if saude_canal:
        parts = ", ".join(f"{c}: {h}%" for c, h in saude_canal.items())
        lines.append(f"Por canal — {parts}.")
    geral = next((m for m in ctx["metricas"]
                  if m["name"] == "receita" and m["channel"] == "geral"), None)
    if geral:
        lines.append(f"Receita do dia: **{_fmt_metric(geral)}**.")
    lines.append("")

    # Alertas críticos
    lines.append("## 🚨 Alertas críticos")
    criticos = [i for i in ctx["problemas"] if i["severity"] in (Severity.CRITICA, Severity.ALTA)]
    anomalias = ctx["anomalias"]
    if not criticos and not anomalias:
        lines.append("Sem alertas críticos hoje. ✅")
    else:
        for a in anomalias:
            ch = Channel.label(a["channel"]) if a["channel"] != "geral" else "Geral"
            lines.append(f"- {_SEV_LABEL.get(a['severity'], '')} [{ch}] {a['message']}")
        for i in criticos:
            lines.append(f"- {_SEV_LABEL.get(i['severity'], '')} "
                         f"[{Channel.label(i['channel'])}] {i['message']}")
    lines.append("")

    # Oportunidades
    lines.append("## 📈 Oportunidades")
    ups = [m for m in ctx["metricas"]
           if m.get("delta_pct") and m["delta_pct"] >= 10 and m["channel"] == "geral"]
    if ups:
        for m in ups:
            lines.append(f"- {m['label']} {_fmt_metric(m)} — considere escalar o que puxou.")
    else:
        lines.append("- Revisar produtos com CTR/conversão altos para escalar verba.")
    lines.append("")

    # Diagnóstico e hipóteses
    lines.append("## 🔍 Diagnóstico e hipóteses")
    if anomalias:
        for a in anomalias[:5]:
            lines.append(f"- **{a['message']}** → possíveis causas: preço da "
                         f"concorrência, anúncio pausado/sem foto, queda de CTR, "
                         f"estoque ou mudança no algoritmo do canal.")
    else:
        lines.append("- Sem anomalias relevantes vs. o dia anterior.")
    lines.append("")

    # Ações priorizadas
    lines.append("## ✅ Ações recomendadas hoje")
    for sev, titulo in ((Severity.ALTA, "Prioridade alta"),
                        (Severity.MEDIA, "Prioridade média"),
                        (Severity.BAIXA, "Prioridade baixa")):
        bucket = [i for i in ctx["problemas"] if i["severity"] == sev]
        # Críticos entram junto com a prioridade alta.
        if sev == Severity.ALTA:
            bucket = [i for i in ctx["problemas"]
                      if i["severity"] in (Severity.CRITICA, Severity.ALTA)]
        lines.append(f"**{titulo}**")
        if not bucket:
            lines.append("- (nada nesta faixa)")
        for i in bucket[:8]:
            rec = i.get("recommendation") or i["message"]
            lines.append(f"- [{Channel.label(i['channel'])}] {rec}")
        lines.append("")

    if ctx.get("acoes_recentes"):
        lines.append("## 🧠 Contexto (o que já foi feito)")
        for a in ctx["acoes_recentes"][-8:]:
            ch = Channel.label(a["channel"]) if a["channel"] != "geral" else "Geral"
            lines.append(f"- {a['date']} [{ch}] {a['description']}")
        lines.append("")

    return "\n".join(lines).strip()
