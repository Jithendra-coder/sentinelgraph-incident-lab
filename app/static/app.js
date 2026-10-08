const state = {
  scenarios: [],
  incidents: [],
  selectedId: null,
  role: "viewer",
  failedSources: [],
};
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-ID": "demo",
      "X-Role": state.role,
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.status === 204 ? null : response.json();
}

function toast(message, error = false) {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast show${error ? " error" : ""}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => {
    el.className = "toast";
  }, 3200);
}

function scenarioIcon(id) {
  return (
    {
      "database-saturation": ["database", "▤"],
      "deployment-regression": ["deployment", "↗"],
      "cache-outage": ["cache", "▧"],
      "upstream-timeout": ["upstream", "⇢"],
    }[id] || ["database", "◈"]
  );
}

function renderScenarios() {
  $("#scenarios").innerHTML = state.scenarios
    .map((scenario, index) => {
      const [tone, symbol] = scenarioIcon(scenario.id);
      return `<button class="scenario-card" data-scenario="${escapeHtml(scenario.id)}" title="Run ${escapeHtml(scenario.title)}">
      <div class="scenario-top"><span class="scenario-icon ${tone}">${symbol}</span><span class="scenario-code">SG-0${index + 1}</span><span class="plus">+</span></div>
      <h3>${escapeHtml(scenario.title)}</h3><p>${escapeHtml(scenario.symptom)}</p>
    </button>`;
    })
    .join("");
}

function statusLabel(status) {
  return (
    {
      investigating: "Collecting evidence",
      awaiting_approval: "Approval required",
      applying: "Applying approved action",
      blocked: "Blocked safely",
      recovered: "Recovered",
    }[status] || status
  );
}

function renderIncidentList() {
  const query = $("#search").value.trim().toLowerCase();
  const rows = state.incidents.filter((item) =>
    `${item.title} ${item.service} ${item.status}`
      .toLowerCase()
      .includes(query),
  );
  $("#incident-count").textContent = state.incidents.length;
  if (!rows.length) {
    $("#incident-list").innerHTML =
      `<div class="empty-list"><span>◉</span><strong>${query ? "No matching incidents" : "No incidents yet"}</strong><small>${query ? "Try a different filter." : "Choose a scenario above to begin the lab."}</small></div>`;
    return;
  }
  $("#incident-list").innerHTML = rows
    .map(
      (
        item,
      ) => `<button class="incident-row ${item.id === state.selectedId ? "selected" : ""}" data-incident="${escapeHtml(item.id)}">
    <span class="incident-row-title">${escapeHtml(item.title)}</span><span class="incident-row-meta"><span><i class="status-dot ${escapeHtml(item.status)}"></i>${escapeHtml(statusLabel(item.status))}</span><span>${new Date(item.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span></span>
  </button>`,
    )
    .join("");
}

function renderIncidentDetail(item) {
  if (!item) {
    $("#incident-detail").innerHTML =
      `<div class="detail-empty"><div class="empty-orbit">◈</div><h3>Evidence before answers.</h3><p>Start a scenario to watch the investigator gather read-only evidence, cite its findings, and request approval before recovery.</p><div class="empty-steps"><span>01 <b>Collect</b></span><i>→</i><span>02 <b>Validate</b></span><i>→</i><span>03 <b>Approve</b></span></div></div>`;
    return;
  }
  const [tone, symbol] = scenarioIcon(item.scenario_id);
  const evidenceById = Object.fromEntries(item.evidence.map((e) => [e.id, e]));
  const qualityText =
    item.status === "investigating"
      ? "Read-only evidence collection is in progress. Findings wait for required sources."
      : item.quality === "complete"
        ? "All required evidence sources returned. Root cause citations were validated."
        : item.quality === "partial"
          ? `Partial evidence: ${item.failed_sources.length} source failure(s) shown in the timeline. Confidence is reduced.`
          : "Insufficient trusted evidence. The system blocked the root cause and remediation.";
  const timeline = item.timeline
    .slice(-9)
    .map(
      (event) =>
        `<div class="timeline-item ${event.kind === "failure" ? "failure" : event.kind === "tool" ? "tool" : ""}"><p>${escapeHtml(event.message)}</p><time>${new Date(event.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</time></div>`,
    )
    .join("");
  const tools = item.tool_trace
    .map(
      (call) =>
        `<div class="tool-row ${escapeHtml(call.status)}"><span class="tool-state"></span><span class="tool-name">${escapeHtml(call.tool)}</span><span class="tool-permission">${escapeHtml(call.permission)} · ${escapeHtml(call.status)}</span></div>`,
    )
    .join("");
  const evidence = item.evidence
    .map(
      (row) =>
        `<article class="evidence-card" id="evidence-${escapeHtml(encodeURIComponent(row.id))}"><div class="evidence-meta"><span>${escapeHtml(row.source)}</span><span class="provenance">${escapeHtml(row.provenance)}</span></div><p>${escapeHtml(row.observed_value)}</p><div class="citations"><span class="citation">${escapeHtml(row.id)}</span></div></article>`,
    )
    .join("");
  let finding = `<div class="finding-card"><div class="finding-top"><strong>ROOT CAUSE</strong><span class="confidence">${Math.round((item.root_cause?.confidence || 0) * 100)}% ${item.root_cause?.supported ? "CONFIDENCE" : "· UNSUPPORTED"}</span></div><p>${escapeHtml(item.root_cause?.summary || "Investigation is still running.")}</p>${item.root_cause?.citations?.length ? `<div class="citations">${item.root_cause.citations.map((id) => `<a class="citation" href="#evidence-${encodeURIComponent(id)}" title="Open cited evidence">${escapeHtml(id)}</a>`).join("")}</div>` : ""}${item.runbook ? `<div class="runbook-line"><span>RETRIEVED RUNBOOK · UNTRUSTED GUIDANCE</span><br>${escapeHtml(item.runbook.title)} <span>(${escapeHtml(item.runbook.id)} · ${Number(item.runbook.score).toFixed(2)})</span></div>` : ""}</div>`;
  if (!item.root_cause)
    finding = `<div class="finding-card"><div class="finding-top"><strong>ROOT CAUSE</strong><span class="confidence">INVESTIGATING</span></div><p>Waiting for required evidence and citation validation.</p></div>`;
  const advisory = item.advisory
    ? `<div class="finding-card"><div class="finding-top"><strong>OPENAI ADVISORY · HUMAN REVIEW</strong><span class="confidence">${escapeHtml(item.advisory.model)}</span></div><p>${escapeHtml(item.advisory.summary)}</p><div class="citations">${item.advisory.citations.map((id) => `<a class="citation" href="#evidence-${encodeURIComponent(id)}" title="Open cited evidence">${escapeHtml(id)}</a>`).join("")}</div></div>`
    : "";
  let remediation = "";
  if (item.remediation) {
    remediation = `<div class="recommendation"><h4>REMEDIATION · ${escapeHtml(item.remediation.status)}</h4><p>${escapeHtml(item.remediation.description)}</p><p class="risk-line">Risk: ${escapeHtml(item.remediation.risk)}</p>${item.status === "awaiting_approval" ? `<label class="role-note" for="role-select">DEMO ROLE · This local selector demonstrates the RBAC gate</label><br><select class="role-select" id="role-select"><option value="viewer" ${state.role === "viewer" ? "selected" : ""}>Viewer</option><option value="sre" ${state.role === "sre" ? "selected" : ""}>SRE approver</option></select><div class="button-row"><button class="button" data-approval="approve">Approve controlled ${escapeHtml(item.remediation.action)}</button><button class="button button-quiet" data-approval="deny">Deny</button></div>` : ""}</div>`;
  }
  const detailMeta = `<div class="detail-submeta"><span>⌖ ${escapeHtml(item.service)}</span><span>◎ RUN ${escapeHtml(item.agent_run_id.slice(0, 10))}</span><span>◷ ${item.metrics.latency_ms ? `${Number(item.metrics.latency_ms).toFixed(0)} ms` : "in progress"}</span><span>⌗ ${item.metrics.tool_calls} tool calls</span></div>`;
  const apiSpend = item.metrics.api_cost_usd === null
    ? "Unknown API spend"
    : `$${Number(item.metrics.api_cost_usd).toFixed(2)} API spend`;
  $("#incident-detail").innerHTML =
    `<div class="detail-header"><div class="detail-title"><span class="detail-symbol ${tone}">${symbol}</span><div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.symptom)}</p></div></div><span class="status-label ${escapeHtml(item.status)}"><i class="status-dot ${escapeHtml(item.status)}"></i>${escapeHtml(statusLabel(item.status))}</span></div>
    ${detailMeta}<div class="quality-banner ${item.quality}"><span>◈</span>${escapeHtml(qualityText)}</div>
    <div class="detail-columns"><div><div class="subhead">Evidence timeline</div><div class="timeline">${timeline}</div><div class="subhead">Collected evidence · ${item.evidence.length}</div><div class="evidence-list">${evidence || `<span class="metric-foot">Evidence appears here as adapters complete.</span>`}</div></div>
    <div><div class="subhead">Tool trace · ${item.tool_trace.length}</div><div class="tool-list">${tools || `<span class="metric-foot">Waiting for the first read-only call.</span>`}</div><div class="subhead">Investigation result</div>${finding}${advisory}${remediation}<div class="subhead">RUN METRICS · ${escapeHtml(item.metrics.latency_label)}</div><div class="detail-submeta"><span>${Number(item.metrics.latency_ms).toFixed(0)} ms</span><span>${item.metrics.model_tokens} tokens</span><span>${apiSpend} · ${escapeHtml(item.metrics.cost_label)}</span></div></div></div>`;
}

async function refreshSummary() {
  const [health, incidents, metricsText] = await Promise.all([
    api("/api/health"),
    api("/api/incidents"),
    fetch("/api/metrics", { headers: { "X-Tenant-ID": "demo" } }).then((r) =>
      r.text(),
    ),
  ]);
  state.incidents = incidents;
  const active = incidents.filter(
    (item) => item.status === "investigating",
  ).length;
  $("#metric-active").innerHTML = `${active} <em>running</em>`;
  $("#metric-total").textContent = `${incidents.length} TOTAL`;
  $("#health-label").textContent =
    health.status === "healthy" ? "Healthy" : "Degraded";
  $("#health-pill").classList.toggle("degraded", health.status !== "healthy");
  $("#metric-system").textContent =
    health.status === "healthy" ? "Operational" : "Incident active";
  const p95 = Number(
    metricsText.match(
      /sentinelgraph_investigation_latency_p95_ms ([\d.]+)/,
    )?.[1] || 0,
  );
  $("#metric-latency").innerHTML = `${p95 ? p95.toFixed(0) : "—"} <em>ms</em>`;
  renderIncidentList();
}

async function selectIncident(id) {
  state.selectedId = id;
  renderIncidentList();
  await refreshDetail();
}

async function refreshDetail() {
  if (!state.selectedId) return renderIncidentDetail(null);
  const item =
    state.incidents.find((row) => row.id === state.selectedId) ||
    (await api(`/api/incidents/${encodeURIComponent(state.selectedId)}`));
  renderIncidentDetail(item);
  if (item.status === "investigating") {
    clearTimeout(refreshDetail.timer);
    refreshDetail.timer = setTimeout(async () => {
      await refreshSummary();
      await refreshDetail();
    }, 450);
  }
}

async function loadChaos() {
  const { fail_sources: failures } = await api("/api/chaos");
  state.failedSources = failures;
  const sources = ["metrics", "traces", "logs", "deployments", "sql"];
  $("#chaos-controls").innerHTML = sources
    .map(
      (source) =>
        `<label class="chaos-chip"><input type="checkbox" value="${source}" ${failures.includes(source) ? "checked" : ""}>${source}</label>`,
    )
    .join("");
  $("#chaos-summary").textContent = failures.length
    ? `Will fail: ${failures.join(", ")}`
    : "All sources available";
  $("#chaos-summary").classList.toggle("active", failures.length > 0);
}

async function refreshAll() {
  try {
    const [scenarios] = await Promise.all([
      api("/api/scenarios"),
      refreshSummary(),
      loadChaos(),
      loadEvaluation(),
    ]);
    state.scenarios = scenarios;
    renderScenarios();
    if (!state.selectedId && state.incidents.length)
      state.selectedId = state.incidents[0].id;
    if (
      state.selectedId &&
      !state.incidents.some((row) => row.id === state.selectedId)
    )
      state.selectedId = null;
    renderIncidentList();
    await refreshDetail();
  } catch (error) {
    toast(error.message, true);
  }
}

async function loadEvaluation() {
  const report = await api("/api/evaluations");
  const recall = report.retrieval.recall_at_1;
  $("#retrieval-score").textContent = `${Math.round(recall * 100)}%`;
  $("#retrieval-bar").style.width = `${Math.round(recall * 100)}%`;
  $("#retrieval-runs").textContent =
    `${report.retrieval.queries} labeled queries`;
}

$("#scenarios").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-scenario]");
  if (!button) return;
  button.disabled = true;
  try {
    const incident = await api("/api/incidents", {
      method: "POST",
      body: JSON.stringify({ scenario_id: button.dataset.scenario }),
    });
    state.selectedId = incident.id;
    toast("Incident injected. Collecting evidence…");
    await refreshSummary();
    await refreshDetail();
  } catch (error) {
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
});

$("#incident-list").addEventListener("click", async (event) => {
  const row = event.target.closest("[data-incident]");
  if (row) await selectIncident(row.dataset.incident);
});

$("#incident-detail").addEventListener("change", (event) => {
  if (event.target.id === "role-select") state.role = event.target.value;
});

$("#incident-detail").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-approval]");
  if (!button || !state.selectedId) return;
  try {
    const item = await api(
      `/api/incidents/${encodeURIComponent(state.selectedId)}/approval`,
      {
        method: "POST",
        body: JSON.stringify({ decision: button.dataset.approval }),
      },
    );
    state.incidents = [
      item,
      ...state.incidents.filter((row) => row.id !== item.id),
    ];
    await refreshSummary();
    await refreshDetail();
    toast(
      item.status === "recovered"
        ? "Approved remediation applied. Simulation recovered."
        : "Remediation denied; no write action ran.",
    );
  } catch (error) {
    toast(error.message, true);
  }
});

$("#save-chaos").addEventListener("click", async () => {
  const fail_sources = [
    ...$("#chaos-controls").querySelectorAll("input:checked"),
  ].map((input) => input.value);
  try {
    await api("/api/chaos", {
      method: "PUT",
      body: JSON.stringify({ fail_sources }),
    });
    await loadChaos();
    toast("Chaos controls saved for the next investigation.");
  } catch (error) {
    toast(error.message, true);
  }
});

$("#search").addEventListener("input", renderIncidentList);
$("#refresh").addEventListener("click", refreshAll);
refreshAll();
