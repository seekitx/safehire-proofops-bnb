"use strict";
(() => {
  const $ = id => document.getElementById(id);
  let market = null, examples = {}, category = "rebalancing", selected = new Set(), loading = false;
  const el = (tag, text, cls) => { const node = document.createElement(tag); if (text != null) node.textContent = String(text); if (cls) node.className = cls; return node; };
  async function request(path, body) {
    const response = await fetch(path, {method: body ? "POST" : "GET", headers: body ? {"Content-Type": "application/json"} : {}, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(30000)});
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `Request rejected (${response.status})`);
    return payload;
  }
  function updateInput() { $("previewInput").value = JSON.stringify(examples[category] || {}, null, 2); $("previewResult").textContent = "Synthetic example loaded. Nothing has been executed."; }
  function renderCategories() {
    $("categories").replaceChildren();
    market.categories.forEach(row => {
      const button = el("button", row.label); button.type = "button"; button.setAttribute("aria-pressed", String(row.category === category));
      button.append(el("small", `${row.listing_count} listing${row.listing_count === 1 ? "" : "s"} · ${row.proven_execution_count} proven execution`));
      button.addEventListener("click", () => { category = row.category; selected.clear(); $("comparison").hidden = true; updateInput(); renderCategories(); renderListings(); });
      $("categories").append(button);
    });
    const info = market.categories.find(row => row.category === category);
    $("categoryQuestion").textContent = info.question;
    $("categoryNeeds").textContent = "Evidence to ask for: " + info.evidence_needed.join(" / ");
  }
  function renderListings() {
    const term = $("search").value.trim().toLowerCase();
    const rows = market.listings.filter(row => row.category === category && `${row.name} ${row.description} ${row.operator_label}`.toLowerCase().includes(term));
    const group = market.listings.filter(row => row.category === category);
    $("choiceNote").textContent = group.length < 2 ? "Only one reviewed listing in this category. A competitive comparison needs another provider; we will not invent one." : "Select two or three in this category. No cross-category winner will be calculated.";
    const cards = $("listings"); cards.replaceChildren();
    if (!rows.length) cards.append(el("p", "No matching reviewed listing. Try another search; no synthetic agent will be substituted.", "muted"));
    rows.forEach(row => {
      const card = el("article", null, "card"); const header = el("div", null, "card-header");
      header.append(el("span", row.probe.callable ? "FRESH CALLABLE ANALYSIS" : "CURRENT CALLABILITY NOT PROVEN", "badge " + (row.probe.callable ? "good" : "warning")));
      const label = el("label", null, "muted"), checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.checked = selected.has(row.id); checkbox.disabled = group.length < 2; checkbox.setAttribute("aria-label", `Compare ${row.name}`);
      checkbox.addEventListener("change", () => { if (checkbox.checked) { if (selected.size >= 3) {checkbox.checked = false; return;} selected.add(row.id); } else selected.delete(row.id); $("compare").disabled = selected.size < 2; });
      label.append(checkbox, document.createTextNode(" Compare")); header.append(label); card.append(header, el("h3", row.name), el("p", row.description));
      const dl = document.createElement("dl");
      [["Registry", row.id], ["Owner (index)", row.owner_address_from_index || "Unresolved"], ["Reviewed service", row.capability.reviewed_scope.replaceAll("_", " ")], ["Official scope covered", row.capability.execution_proven ? "Proven" : "Execution not demonstrated"], ["Paid delivery quality", "Not replayed / unknown"], ["Hire price", "Fresh negotiation required"]].forEach(([key,value]) => dl.append(el("dt",key),el("dd",value)));
      card.append(dl, el("p", "Missing proof: " + row.evidence_gaps.join(" · ").replaceAll("_", " "), "gaps"));
      if (row.signal_disagreement) card.append(el("p", row.signal_disagreement, "warning"));
      const actions = el("div", null, "card-actions");
      if (row.analysis_hire_available && row.hire_url && row.hire_url.startsWith("/hire-live?skill_id=")) { const link = el("a", "Review & hire analysis", "cta"); link.href = row.hire_url; actions.append(link); }
      else actions.append(el("span", "Hiring paused until a fresh reviewed probe succeeds", "muted"));
      if (/^0x[0-9a-fA-F]{64}$/.test(row.registration_tx || "")) {const link=el("a","Registration ↗");link.href=`https://bscscan.com/tx/${row.registration_tx}`;link.target="_blank";link.rel="noopener noreferrer";actions.append(link);}
      card.append(actions); cards.append(card);
    });
    $("compare").disabled = selected.size < 2;
  }
  async function load() {
    if (loading) return;
    loading = true;
    $("refresh").disabled = true; $("marketStatus").textContent = "Checking reviewed sources. A cached original timestamp will not be rewritten as live.";
    try {
      market = await request("/api/decision/market"); selected.clear(); $("comparison").hidden = true;
      $("probeState").textContent = market.probe.status.toUpperCase();
      $("probeTime").textContent = market.probe.source_observed_at || "No valid source observation";
      $("listingCount").textContent = market.supplier_concentration.listing_count;
      $("supplierCount").textContent = `${market.supplier_concentration.distinct_owner_addresses_from_index} distinct indexed owners · ${market.supplier_concentration.unresolved_owner_listings} unresolved`;
      $("marketStatus").textContent = market.refresh_error ? `Source refresh failed (${market.refresh_error}). Old data is not enabled for hiring.` : "Registration, endpoint liveness and delivered outcomes remain separate. Rankings do not predict returns.";
      renderCategories(); renderListings();
    } catch (error) {
      market = null; selected.clear(); $("listings").replaceChildren(); $("categories").replaceChildren(); $("comparison").hidden = true; $("compare").disabled = true;
      $("probeState").textContent = "UNAVAILABLE"; $("marketStatus").textContent = `Market unavailable: ${error.message}. No demo fallback or stale hire action.`;
    } finally { loading = false; $("refresh").disabled = false; }
  }
  $("refresh").addEventListener("click", load);
  $("search").addEventListener("input", () => {if(market)renderListings();});
  $("compare").addEventListener("click", async () => {
    try {const result=await request("/api/decision/compare",{agent_ids:[...selected]});const out=$("compareContent");out.replaceChildren(el("p",result.reason,"muted"));const table=document.createElement("table");const heading=document.createElement("tr");["Agent","Fresh analysis","Category fit","Execution proven"].forEach(t=>heading.append(el("th",t)));table.append(heading);result.agents.forEach(row=>{const tr=document.createElement("tr");[row.name,row.analysis_hire_available,row.capability.category_analysis_fit,row.capability.execution_proven].forEach(t=>tr.append(el("td",t)));table.append(tr);});out.append(table);$("comparison").hidden=false;}catch(error){$("marketStatus").textContent=error.message;}
  });
  $("previewForm").addEventListener("submit", async event => {
    event.preventDefault(); try {const input=JSON.parse($("previewInput").value);if(JSON.stringify(input).length>16000)throw new Error("Preview input is too large");const result=await request("/api/decision/preview",{category,input});$("previewResult").textContent=JSON.stringify(result,null,2);}catch(error){$("previewResult").textContent="Preview rejected: "+error.message;}
  });
  request("/api/decision/examples").then(data=>{examples=data.examples;updateInput();}).catch(error=>{$("previewResult").textContent="Examples unavailable: "+error.message;});
  setInterval(() => { if (!document.hidden) load(); }, 45000);
  setInterval(() => {
    if (!market || market.probe.status !== "fresh") return;
    const stamp = Date.parse(market.probe.source_observed_at);
    if (!Number.isFinite(stamp) || Date.now() - stamp > 60000) {
      market.probe.status = "stale";
      market.listings.forEach(row => {row.probe.callable=false;row.analysis_hire_available=false;row.hire_url=null;});
      $("probeState").textContent = "STALE";
      $("marketStatus").textContent = "Probe expired while this page was open. Hiring is disabled until refreshed.";
      renderListings();
    }
  }, 1000);
  load();
})();
