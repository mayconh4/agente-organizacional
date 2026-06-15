"use strict";

// ----------------------------------------------------------------------------
// Estado e utilidades
// ----------------------------------------------------------------------------
const state = { channels: [], channelMap: {}, stores: [], active: null };

const SEV = { critica: "Crítico", alta: "Alta", media: "Média", baixa: "Baixa" };
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const $ = (sel, root = document) => root.querySelector(sel);
const el = (id) => document.getElementById(id);

function channelLabel(c) {
  if (c === "geral") return "Geral";
  return state.channelMap[c] || c;
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" }, ...opts,
  });
  if (!res.ok) {
    let msg = `Erro ${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

function fmtMetric(m) {
  const v = m.value ?? 0;
  if (m.unit === "R$") return brl.format(v);
  if (m.unit === "x") return v.toFixed(2) + "x";
  if (m.unit === "%") return v.toFixed(1) + "%";
  if (m.unit === "un") return Math.round(v).toLocaleString("pt-BR");
  return String(v);
}
function deltaHtml(d) {
  if (d === null || d === undefined) return "";
  const cls = d > 1 ? "up" : d < -1 ? "down" : "flat";
  const arrow = d > 1 ? "▲" : d < -1 ? "▼" : "■";
  return `<span class="delta ${cls}">${arrow} ${d > 0 ? "+" : ""}${d.toFixed(0)}% vs. ontem</span>`;
}
function gaugeColor(p) { return p >= 75 ? "var(--good)" : p >= 50 ? "var(--med)" : "var(--crit)"; }

// Mini markdown (títulos, negrito, listas)
function md(src) {
  const out = []; let inList = false;
  const closeList = () => { if (inList) { out.push("</ul>"); inList = false; } };
  for (const raw of (src || "").split("\n")) {
    const line = raw.trimEnd();
    const inline = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
    if (/^#\s+/.test(line)) { closeList(); out.push(`<h1>${inline(line.replace(/^#\s+/, ""))}</h1>`); }
    else if (/^##\s+/.test(line)) { closeList(); out.push(`<h2>${inline(line.replace(/^##\s+/, ""))}</h2>`); }
    else if (/^###\s+/.test(line)) { closeList(); out.push(`<h3>${inline(line.replace(/^###\s+/, ""))}</h3>`); }
    else if (/^[-*]\s+/.test(line)) { if (!inList) { out.push("<ul>"); inList = true; } out.push(`<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`); }
    else if (line.startsWith(">")) { closeList(); out.push(`<p class="muted">${inline(line.replace(/^>\s?/, ""))}</p>`); }
    else if (line === "") { closeList(); }
    else { closeList(); out.push(`<p>${inline(line)}</p>`); }
  }
  closeList();
  return out.join("\n");
}

// ----------------------------------------------------------------------------
// Abas
// ----------------------------------------------------------------------------
function renderTabs() {
  const tabs = el("tabs");
  tabs.innerHTML = "";
  for (const s of state.stores) {
    const t = document.createElement("button");
    t.className = "tab" + (state.active === s.id ? " active" : "");
    t.innerHTML = `<span class="dot"></span>${esc(s.name)}
      <span class="muted">· ${esc(channelLabel(s.channel))}</span>`;
    t.onclick = () => openStore(s.id);
    tabs.appendChild(t);
  }
  const add = document.createElement("button");
  add.className = "tab add" + (state.active === "__new__" ? " active" : "");
  add.innerHTML = "➕ Nova loja";
  add.onclick = openNewForm;
  tabs.appendChild(add);
}

// ----------------------------------------------------------------------------
// Dashboard de uma loja
// ----------------------------------------------------------------------------
async function openStore(id) {
  state.active = id;
  renderTabs();
  const store = state.stores.find((s) => s.id === id);
  if (!store) return;

  const tpl = el("tpl-store").content.cloneNode(true);
  $('[data-bind="name"]', tpl).textContent = store.name;
  $('[data-bind="channel"]', tpl).textContent = channelLabel(store.channel);
  const body = $('[data-bind="body"]', tpl);
  body.innerHTML = `<div class="loader glass card"><span class="spin"></span><p class="muted">Buscando dados reais…</p></div>`;

  $('[data-act="delete"]', tpl).onclick = () => removeStore(store);
  $('[data-act="edit"]', tpl).onclick = () => openEditForm(store);
  $('[data-act="report"]', tpl).onclick = () => openReport(store);

  const view = el("view");
  view.innerHTML = "";
  view.appendChild(tpl);
  const updated = view.querySelector('[data-bind="updated"]');

  try {
    const ctx = await api(`/api/stores/${id}/dashboard`);
    updated.textContent = "· " + (ctx.data || "");
    view.querySelector('[data-bind="body"]').innerHTML = dashboardHtml(ctx);
    const g = el("gauge");
    if (g) { g.style.setProperty("--pct", ctx.saude_operacional); g.style.setProperty("--gc", gaugeColor(ctx.saude_operacional)); }
  } catch (err) {
    view.querySelector('[data-bind="body"]').innerHTML = `
      <div class="error-card glass">
        <h3>⚠️ Não foi possível carregar dados reais</h3>
        <p class="muted">${esc(err.message)}</p>
        <p>Verifique as credenciais da API desta loja.</p>
        <button class="btn primary" id="err-edit">Editar credenciais</button>
      </div>`;
    const b = el("err-edit");
    if (b) b.onclick = () => openEditForm(store);
  }
}

function dashboardHtml(ctx) {
  const general = (ctx.metricas || []).filter((m) => m.channel === "geral");
  const kpiNames = ["receita", "pedidos", "ticket_medio", "roas"];
  const kpis = kpiNames.map((n) => general.find((m) => m.name === n)).filter(Boolean);

  const alerts = [];
  for (const a of ctx.anomalias || [])
    alerts.push(alertLi(a.severity, a.channel, a.message));
  for (const i of (ctx.problemas || []).filter((x) => x.severity === "critica" || x.severity === "alta"))
    alerts.push(alertLi(i.severity, i.channel, i.message));

  const ups = (ctx.metricas || []).filter((m) => m.delta_pct >= 10);
  const opsItems = ups.length
    ? ups.map((m) => `<li><span class="sev baixa"></span><div><b>${esc(m.label)}</b> ${fmtMetric(m)} ${deltaHtml(m.delta_pct)}<br/><span class="muted">Considere escalar o que puxou esse crescimento.</span></div></li>`)
    : [`<li><span class="sev baixa"></span><div>Revise produtos com CTR/conversão altos para escalar verba.</div></li>`];

  const issues = ctx.problemas || [];
  const actionCol = (title, list) => `<div><h4>${title}</h4><ul class="list">${
    list.length ? list.slice(0, 6).map((i) => `<li><div><b>[${esc(channelLabel(i.channel))}]</b> ${esc(i.recommendation || i.message)}</div></li>`).join("") : `<li class="empty">—</li>`
  }</ul></div>`;

  const metricsRows = (ctx.metricas || []).map((m) => `
    <tr><td>${esc(channelLabel(m.channel))}</td><td>${esc(m.label)}</td>
    <td class="num">${fmtMetric(m)}</td>
    <td class="num">${m.delta_pct == null ? "—" : deltaHtml(m.delta_pct)}</td></tr>`).join("");

  return `
    <div class="grid hero">
      <div class="card glass gauge-wrap">
        <div class="gauge" id="gauge"><b>${ctx.saude_operacional}%</b><span>saúde</span></div>
      </div>
      <div class="card glass">
        <h3>Situação geral</h3>
        <p>Saúde operacional do canal: <b>${ctx.saude_operacional}%</b>.</p>
        ${kpis.length ? `<div class="grid kpis" style="margin-top:.6rem">${kpis.map((m) => `
          <div class="kpi"><div class="label">${esc(m.label)}</div>
          <div class="value">${fmtMetric(m)}</div>${deltaHtml(m.delta_pct)}</div>`).join("")}</div>` : ""}
      </div>
    </div>

    <div class="grid cols-2">
      <div class="card glass"><h3>🚨 Alertas críticos</h3>
        <ul class="list">${alerts.length ? alerts.join("") : '<li class="empty">Sem alertas críticos hoje. ✅</li>'}</ul>
      </div>
      <div class="card glass"><h3>📈 Oportunidades</h3>
        <ul class="list">${opsItems.join("")}</ul>
      </div>
    </div>

    <div class="card glass" style="margin-bottom:1rem">
      <h3>✅ Ações recomendadas hoje</h3>
      <div class="actions-cols">
        ${actionCol("Prioridade alta", issues.filter((i) => i.severity === "critica" || i.severity === "alta"))}
        ${actionCol("Prioridade média", issues.filter((i) => i.severity === "media"))}
        ${actionCol("Prioridade baixa", issues.filter((i) => i.severity === "baixa"))}
      </div>
    </div>

    <div class="card glass">
      <h3>📑 Métricas</h3>
      <table><thead><tr><th>Canal</th><th>Métrica</th><th class="num">Valor</th><th class="num">Variação</th></tr></thead>
      <tbody>${metricsRows}</tbody></table>
    </div>`;
}

function alertLi(sev, channel, msg) {
  return `<li><span class="sev ${sev}"></span><div>
    <span class="tag">${SEV[sev] || ""}</span>
    <span class="muted">${esc(channelLabel(channel))}</span><br/>${esc(msg)}</div></li>`;
}

async function openReport(store) {
  const body = $('[data-bind="body"]') || el("view");
  // Renderiza loader dentro da área da loja, se a loja estiver aberta.
  const target = document.querySelector('#view [data-bind="body"]');
  if (target) target.innerHTML = `<div class="loader glass card"><span class="spin"></span><p class="muted">Gerando relatório executivo…</p></div>`;
  try {
    const rep = await api(`/api/stores/${store.id}/report`);
    if (target) target.innerHTML = `
      <div class="card glass">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:1rem">
          <h3>🧠 Relatório executivo <span class="chip">${rep.engine === "claude" ? "Claude" : "regras"}</span></h3>
          <button class="btn" id="rep-back">← Voltar ao painel</button>
        </div>
        <div class="report-md">${md(rep.markdown)}</div>
      </div>`;
    const back = el("rep-back");
    if (back) back.onclick = () => openStore(store.id);
  } catch (err) {
    if (target) target.innerHTML = `<div class="error-card glass"><h3>⚠️ Erro</h3><p class="muted">${esc(err.message)}</p>
      <button class="btn" id="rep-back2">← Voltar</button></div>`;
    const b = el("rep-back2"); if (b) b.onclick = () => openStore(store.id);
  }
}

// ----------------------------------------------------------------------------
// Formulários (nova loja / editar credenciais)
// ----------------------------------------------------------------------------
function credFieldsHtml(channelId, values = {}) {
  const ch = state.channels.find((c) => c.id === channelId);
  if (!ch) return "";
  return ch.fields.map((f) => `
    <label class="field">
      <span>${esc(f.label)}${f.required ? " *" : ""}</span>
      <input name="cred:${f.key}" ${f.required ? "required" : ""}
        value="${esc(values[f.key] || "")}"
        placeholder="${f.required ? "" : "opcional"}" autocomplete="off" />
    </label>`).join("");
}

function renderForm({ title, subtitle, store }) {
  state.active = store ? store.id : "__new__";
  renderTabs();
  const tpl = el("tpl-form").content.cloneNode(true);
  $('[data-bind="title"]', tpl).textContent = title;
  $('[data-bind="subtitle"]', tpl).textContent = subtitle;

  const view = el("view");
  view.innerHTML = "";
  view.appendChild(tpl);

  const form = el("store-form");
  const sel = el("channel-select");
  sel.innerHTML = state.channels.map((c) => `<option value="${c.id}">${esc(c.label)}</option>`).join("");

  if (store) {
    // Editar credenciais: nome e canal fixos.
    form.querySelector('input[name="name"]').value = store.name;
    form.querySelector('input[name="name"]').readOnly = true;
    sel.value = store.channel;
    sel.disabled = true;
  }
  const renderCreds = () => { el("cred-fields").innerHTML = credFieldsHtml(sel.value); };
  sel.onchange = renderCreds;
  renderCreds();

  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const data = new FormData(form);
    const credentials = {};
    for (const [k, v] of data.entries())
      if (k.startsWith("cred:") && v.trim()) credentials[k.slice(5)] = v.trim();
    const msg = el("form-msg");
    msg.className = "form-msg";
    msg.textContent = "Salvando…";
    try {
      let saved;
      if (store) {
        saved = await api(`/api/stores/${store.id}`, {
          method: "PUT", body: JSON.stringify({ credentials }),
        });
      } else {
        saved = await api("/api/stores", {
          method: "POST",
          body: JSON.stringify({ name: data.get("name"), channel: sel.value, credentials }),
        });
      }
      await loadStores();
      openStore(saved.id || store.id);
    } catch (err) {
      msg.className = "form-msg error";
      msg.textContent = err.message;
    }
  };
}

function openNewForm() {
  renderForm({
    title: "Nova loja",
    subtitle: "Cadastre a loja e as credenciais da API do marketplace.",
  });
}
function openEditForm(store) {
  renderForm({
    title: `Credenciais — ${store.name}`,
    subtitle: "Atualize os tokens de API desta loja.",
    store,
  });
}

async function removeStore(store) {
  if (!confirm(`Remover a loja "${store.name}"?`)) return;
  await api(`/api/stores/${store.id}`, { method: "DELETE" });
  await loadStores();
  if (state.stores.length) openStore(state.stores[0].id);
  else openNewForm();
}

// ----------------------------------------------------------------------------
// Boot
// ----------------------------------------------------------------------------
async function loadStores() {
  state.stores = await api("/api/stores");
  renderTabs();
}

async function init() {
  try {
    state.channels = await api("/api/channels");
    state.channelMap = Object.fromEntries(state.channels.map((c) => [c.id, c.label]));
    const health = await api("/api/health");
    el("brand-meta").innerHTML = health.claude
      ? "Diagnóstico: <b>Claude</b> ativo"
      : "Diagnóstico: regras (defina ANTHROPIC_API_KEY)";
    await loadStores();
  } catch (err) {
    el("view").innerHTML = `<div class="error-card glass"><h3>⚠️ Backend indisponível</h3><p class="muted">${esc(err.message)}</p></div>`;
    return;
  }
  if (state.stores.length) openStore(state.stores[0].id);
  else openNewForm();
}

init();
