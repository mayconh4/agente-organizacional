"use strict";

const CHANNELS = {
  shopee: "Shopee",
  mercado_livre: "Mercado Livre",
  amazon: "Amazon",
};
const SEV = {
  critica: { label: "Crítico", cls: "critica" },
  alta: { label: "Alta", cls: "alta" },
  media: { label: "Média", cls: "media" },
  baixa: { label: "Baixa", cls: "baixa" },
};

const channelLabel = (c) => CHANNELS[c] || (c === "geral" ? "Geral" : c);
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function fmtMetricValue(m) {
  const v = m.value ?? 0;
  if (m.unit === "R$") return brl.format(v);
  if (m.unit === "x") return v.toFixed(2) + "x";
  if (m.unit === "%") return v.toFixed(1) + "%";
  if (m.unit === "un") return Math.round(v).toLocaleString("pt-BR");
  return String(v);
}

function deltaSpan(delta) {
  if (delta === null || delta === undefined) return "";
  const cls = delta > 1 ? "up" : delta < -1 ? "down" : "flat";
  const arrow = delta > 1 ? "▲" : delta < -1 ? "▼" : "■";
  return `<span class="delta ${cls}">${arrow} ${delta > 0 ? "+" : ""}${delta.toFixed(0)}% vs. ontem</span>`;
}

function gaugeColor(pct) {
  if (pct >= 75) return "var(--good)";
  if (pct >= 50) return "var(--med)";
  return "var(--crit)";
}

// ---- escape + mini markdown ------------------------------------------------
function esc(s) {
  return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
function inline(s) {
  return esc(s).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}
function renderMarkdown(md) {
  const out = [];
  let list = false;
  const closeList = () => { if (list) { out.push("</ul>"); list = false; } };
  for (const raw of (md || "").split("\n")) {
    const line = raw.trimEnd();
    if (/^#\s+/.test(line)) { closeList(); out.push(`<h1>${inline(line.replace(/^#\s+/, ""))}</h1>`); }
    else if (/^##\s+/.test(line)) { closeList(); out.push(`<h2>${inline(line.replace(/^##\s+/, ""))}</h2>`); }
    else if (/^###\s+/.test(line)) { closeList(); out.push(`<h3>${inline(line.replace(/^###\s+/, ""))}</h3>`); }
    else if (/^[-*]\s+/.test(line)) { if (!list) { out.push("<ul>"); list = true; } out.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`); }
    else if (line.startsWith(">")) { closeList(); out.push(`<p class="empty">${inline(line.replace(/^>\s?/, ""))}</p>`); }
    else if (line === "") { closeList(); }
    else { closeList(); out.push(`<p>${inline(line)}</p>`); }
  }
  closeList();
  return out.join("\n");
}

// ---- rendering -------------------------------------------------------------
function renderMeta(data) {
  const engine = data.engine === "claude"
    ? `<span class="badge">Claude</span>`
    : `<span class="badge rules">regras (offline)</span>`;
  const gen = data.generated_at ? new Date(data.generated_at).toLocaleString("pt-BR") : "";
  document.getElementById("meta").innerHTML =
    `<div><strong>${esc(data.client || "")}</strong> · ${esc(data.date || "")}</div>
     <div>Motor: ${engine}</div>
     <div>Atualizado: ${esc(gen)}</div>`;
}

function renderHealth(data) {
  const pct = data.health ?? 0;
  const gauge = document.getElementById("gauge");
  gauge.style.setProperty("--pct", pct);
  gauge.style.setProperty("--gauge-color", gaugeColor(pct));
  document.getElementById("health-value").textContent = pct + "%";

  const ch = data.channel_health || {};
  document.getElementById("channels").innerHTML = Object.entries(ch).map(([name, score]) => `
    <div class="chan">
      <h3>${esc(name)}</h3>
      <div class="score">${score}%</div>
      <div class="bar"><span style="width:${score}%;background:${gaugeColor(score)}"></span></div>
      <small>saúde do canal</small>
    </div>`).join("") || `<div class="chan"><small>Sem dados de canal.</small></div>`;
}

function renderKpis(data) {
  const wanted = [
    ["receita", "Receita"],
    ["pedidos", "Pedidos"],
    ["ticket_medio", "Ticket médio"],
    ["roas", "ROAS"],
  ];
  const general = (data.metrics || []).filter((m) => m.channel === "geral");
  const cards = wanted.map(([name]) => general.find((m) => m.name === name)).filter(Boolean);
  document.getElementById("kpis").innerHTML = cards.map((m) => `
    <div class="kpi">
      <div class="label">${esc(m.label)}</div>
      <div class="value">${fmtMetricValue(m)}</div>
      ${deltaSpan(m.delta_pct)}
    </div>`).join("");
}

function alertItem(sev, channel, msg) {
  const s = SEV[sev] || SEV.baixa;
  return `<li>
    <span class="dot bg-${s.cls}"></span>
    <div>
      <span class="tag sev-${s.cls}">${s.label}</span>
      <span class="chan-tag">${esc(channelLabel(channel))}</span><br/>
      ${esc(msg)}
    </div>
  </li>`;
}

function renderAlerts(data) {
  const items = [];
  for (const a of data.anomalies || []) items.push(alertItem(a.severity, a.channel, a.message));
  for (const i of (data.issues || []).filter((x) => x.severity === "critica" || x.severity === "alta")) {
    items.push(alertItem(i.severity, i.channel, i.message));
  }
  document.getElementById("alerts").innerHTML =
    items.join("") || `<li class="empty">Sem alertas críticos hoje. ✅</li>`;
}

function renderOps(data) {
  const ups = (data.metrics || []).filter((m) => m.delta_pct >= 10);
  const items = ups.map((m) =>
    `<li><div><b>${esc(m.label)} (${esc(channelLabel(m.channel))})</b> ${fmtMetricValue(m)} · ${deltaSpan(m.delta_pct)}<br/>Considere escalar o que puxou esse crescimento.</div></li>`);
  if (!items.length) {
    items.push(`<li><div>Revise produtos com CTR/conversão altos para escalar verba de mídia.</div></li>`);
  }
  document.getElementById("ops").innerHTML = items.join("");
}

function renderActions(data) {
  const issues = data.issues || [];
  const high = issues.filter((i) => i.severity === "critica" || i.severity === "alta");
  const med = issues.filter((i) => i.severity === "media");
  const low = issues.filter((i) => i.severity === "baixa");
  const col = (cls, title, list) => `
    <div class="col ${cls}">
      <h3>${title}</h3>
      <ul>${list.slice(0, 8).map((i) =>
        `<li><b>[${esc(channelLabel(i.channel))}]</b> ${esc(i.recommendation || i.message)}</li>`).join("")
        || `<li class="empty">—</li>`}</ul>
    </div>`;
  document.getElementById("actions").innerHTML =
    col("alta", "Prioridade alta", high) + col("media", "Prioridade média", med) + col("baixa", "Prioridade baixa", low);
}

function renderMetrics(data) {
  const rows = (data.metrics || []).map((m) => `
    <tr>
      <td>${esc(channelLabel(m.channel))}</td>
      <td>${esc(m.label)}</td>
      <td class="num">${fmtMetricValue(m)}</td>
      <td class="num">${m.delta_pct === null || m.delta_pct === undefined ? "—" : deltaSpan(m.delta_pct)}</td>
    </tr>`).join("");
  document.getElementById("metrics").innerHTML =
    `<thead><tr><th>Canal</th><th>Métrica</th><th class="num">Valor</th><th class="num">Variação</th></tr></thead>
     <tbody>${rows}</tbody>`;
}

function renderReport(data) {
  document.getElementById("report").innerHTML = renderMarkdown(data.report_markdown);
}

function render(data) {
  document.getElementById("loading").remove();
  const tpl = document.getElementById("tpl-dashboard").content.cloneNode(true);
  document.getElementById("app").appendChild(tpl);
  renderMeta(data);
  renderHealth(data);
  renderKpis(data);
  renderAlerts(data);
  renderOps(data);
  renderActions(data);
  renderMetrics(data);
  renderReport(data);
}

fetch("./report.json", { cache: "no-store" })
  .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
  .then(render)
  .catch((err) => {
    document.getElementById("loading").innerHTML =
      `Não foi possível carregar <code>report.json</code> (${esc(String(err))}).<br/>
       Gere os dados com <code>python run.py build-web</code> e publique a pasta <code>docs/</code>.`;
  });
