"""Camada 2 — Auditor de marketplace.

Varre cada canal procurando problemas técnicos/operacionais: anúncios sem foto,
títulos fracos, estoque zerado, anúncios pausados, avaliações baixas, Buy Box
perdida, reputação ruim, perguntas não respondidas, campanhas no prejuízo, etc.
Produz uma lista de Issue ordenada por severidade.
"""
from __future__ import annotations

from ..models import (
    AdCampaign,
    Channel,
    ChannelSnapshot,
    Issue,
    Product,
    Severity,
    StoreSnapshot,
)

# Limiares configuráveis das regras.
MIN_TITLE_LEN = 20
MIN_DESCRIPTION_LEN = 200
LOW_RATING = 4.0
HIGH_LATE_RATE = 5.0          # % de envios atrasados
HIGH_CPA = 60.0               # R$ por conversão considerado caro
LOW_CTR = 1.0                 # % CTR baixo de anúncio


def audit(store: StoreSnapshot) -> list[Issue]:
    issues: list[Issue] = []
    for ch in store.channels:
        issues.extend(_audit_account(ch))
        for product in ch.products:
            issues.extend(_audit_product(ch, product))
        for campaign in ch.campaigns:
            issues.extend(_audit_campaign(ch, campaign))
    issues.sort(key=lambda i: Severity.ORDER.get(i.severity, 9))
    return issues


# --------------------------------------------------------------------------- #
def _audit_account(ch: ChannelSnapshot) -> list[Issue]:
    out: list[Issue] = []
    if ch.reputation in ("amarelo", "vermelho"):
        out.append(Issue(
            severity=Severity.ALTA if ch.reputation == "amarelo" else Severity.CRITICA,
            channel=ch.channel, area="conta", entity="conta",
            message=f"Reputação da conta está {ch.reputation}.",
            recommendation="Revisar cancelamentos, atrasos e reclamações recentes.",
        ))
    if ch.late_shipment_rate and ch.late_shipment_rate > HIGH_LATE_RATE:
        out.append(Issue(
            severity=Severity.ALTA, channel=ch.channel, area="conta", entity="conta",
            message=f"Taxa de atraso em {ch.late_shipment_rate:.1f}% "
                    f"(acima do limite de {HIGH_LATE_RATE:.0f}%).",
            recommendation="Acelerar expedição e revisar prazos de manuseio.",
        ))
    if ch.unanswered_questions > 0:
        out.append(Issue(
            severity=Severity.MEDIA if ch.unanswered_questions < 10 else Severity.ALTA,
            channel=ch.channel, area="atendimento", entity="conta",
            message=f"{ch.unanswered_questions} pergunta(s) sem resposta.",
            recommendation="Responder hoje — perguntas em aberto derrubam conversão.",
        ))
    return out


def _audit_product(ch: ChannelSnapshot, p: Product) -> list[Issue]:
    out: list[Issue] = []
    if p.status == "ativo" and p.stock <= 0:
        out.append(Issue(
            severity=Severity.CRITICA, channel=ch.channel, area="estoque", entity=p.sku,
            message=f"'{p.title}' está ativo com estoque zerado.",
            recommendation="Repor estoque ou pausar para não perder posicionamento.",
        ))
    if p.images == 0 and p.status == "ativo":
        out.append(Issue(
            severity=Severity.ALTA, channel=ch.channel, area="anúncio", entity=p.sku,
            message=f"'{p.title}' está sem foto principal.",
            recommendation="Subir ao menos 1 imagem em fundo branco de boa resolução.",
        ))
    if p.status == "ativo" and (len(p.title) < MIN_TITLE_LEN or p.title.islower()):
        out.append(Issue(
            severity=Severity.MEDIA, channel=ch.channel, area="anúncio", entity=p.sku,
            message=f"Título fraco/curto: '{p.title}'.",
            recommendation="Reescrever com marca, modelo e atributos buscados.",
        ))
    if p.rating is not None and p.rating < LOW_RATING and p.reviews >= 5:
        out.append(Issue(
            severity=Severity.ALTA, channel=ch.channel, area="reputação", entity=p.sku,
            message=f"'{p.title}' com avaliação baixa ({p.rating:.1f}).",
            recommendation="Investigar reviews negativas recentes e atacar a causa.",
        ))
    if p.status == "ativo" and 0 < p.description_length < MIN_DESCRIPTION_LEN:
        out.append(Issue(
            severity=Severity.BAIXA, channel=ch.channel, area="anúncio", entity=p.sku,
            message=f"Descrição curta em '{p.title}' ({p.description_length} caracteres).",
            recommendation="Detalhar benefícios, medidas e dúvidas frequentes.",
        ))
    if p.status == "pausado":
        out.append(Issue(
            severity=Severity.MEDIA, channel=ch.channel, area="anúncio", entity=p.sku,
            message=f"'{p.title}' está pausado.",
            recommendation="Confirmar se a pausa é intencional; reativar se possível.",
        ))
    if ch.channel == Channel.AMAZON and p.has_buybox is False and p.status == "ativo":
        out.append(Issue(
            severity=Severity.CRITICA, channel=ch.channel, area="anúncio", entity=p.sku,
            message=f"Buy Box perdida em '{p.title}'.",
            recommendation="Revisar preço vs. concorrência e condições de frete/prazo.",
        ))
    return out


def _audit_campaign(ch: ChannelSnapshot, c: AdCampaign) -> list[Issue]:
    out: list[Issue] = []
    if c.status == "pausada":
        out.append(Issue(
            severity=Severity.BAIXA, channel=ch.channel, area="campanha", entity=c.id,
            message=f"Campanha '{c.name}' está pausada.",
            recommendation="Confirmar se a pausa é intencional.",
        ))
        return out
    if c.roas is not None and c.roas < 1:
        out.append(Issue(
            severity=Severity.ALTA, channel=ch.channel, area="campanha", entity=c.id,
            message=f"Campanha '{c.name}' com ROAS {c.roas:.2f} (abaixo de 1 = prejuízo).",
            recommendation="Pausar ou refazer segmentação/criativo antes de seguir gastando.",
        ))
    if c.cpa is not None and c.cpa > HIGH_CPA:
        out.append(Issue(
            severity=Severity.MEDIA, channel=ch.channel, area="campanha", entity=c.id,
            message=f"Campanha '{c.name}' com CPA alto (R$ {c.cpa:.2f}).",
            recommendation="Cortar termos/segmentos caros e realocar para o que converte.",
        ))
    if c.ctr is not None and c.ctr < LOW_CTR:
        out.append(Issue(
            severity=Severity.BAIXA, channel=ch.channel, area="campanha", entity=c.id,
            message=f"Campanha '{c.name}' com CTR baixo ({c.ctr:.2f}%).",
            recommendation="Testar novo criativo/headline para subir o clique.",
        ))
    return out
