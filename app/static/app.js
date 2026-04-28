import { API, COPY, OPTIONS, PAGES } from "./js/core/config.js";
import { els, persistPage, persistSelection, state } from "./js/core/state.js";
import { request as rawRequest } from "./js/api/client.js";
import { escapeHtml, readError, showToast as baseShowToast } from "./js/utils/ui.js";
import { createNavigationController } from "./js/shell/navigation.js";
import { createSidebarController } from "./js/shell/sidebar.js";
import { createAssistantRenderer } from "./js/assistant/render.js";
import { createAssistantWorkspace } from "./js/assistant/workspace.js";

let navigationController;
let sidebarController;
let assistantRenderer;
let assistantWorkspace;

document.addEventListener("DOMContentLoaded", boot);

async function boot() {
  bindElements();
  initializeControllers();
  bindBaseEvents();
  if (localStorage.getItem("he_session_token")) {
    try {
      await refreshAllData();
    } catch (error) {
      showToast(readError(error), "error");
    }
  }
  render();
}

function initializeControllers() {
  assistantWorkspace = createAssistantWorkspace({
    API,
    state,
    request,
    render: () => render(),
    showToast: (message, tone = "success") => showToast(message, tone),
    readError,
    selectedHousehold,
    refreshAllData,
  });

  navigationController = createNavigationController({
    PAGES,
    state,
    els,
    persistPage,
    render: () => render(),
    loadAssistantWorkspace: assistantWorkspace.loadAssistantWorkspace,
  });

  sidebarController = createSidebarController({ state, els });

  assistantRenderer = createAssistantRenderer({
    state,
    escapeHtml,
    selectedHousehold,
    renderPageHeader,
    renderAssistantMarkdown,
  });
}

async function request(path, options = {}) {
  try {
    return await rawRequest(path, options);
  } catch (error) {
    if (error instanceof Error && error.message.includes("Sessionen har gått ut")) {
      state.selectedHouseholdId = null;
      render();
    }
    throw error;
  }
}

function showToast(message, tone = "success") {
  baseShowToast(els, message, tone);
}

async function ensureSummaryLoaded() {
  if (!state.selectedHouseholdId) {
    state.summary = null;
    return;
  }
  state.summary = await request(`/households/${state.selectedHouseholdId}/summary`);
}

async function loadHousingEvaluation(scenarioId) {
  state.housingEvaluation = await request(`/housing_scenarios/${scenarioId}/evaluate`);
}

function households() {
  return state.data.households;
}

function selectedHousehold() {
  return households().find((item) => item.id === state.selectedHouseholdId) || null;
}

function peopleForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.persons.filter((item) => item.household_id === householdId);
}

function incomesForHousehold(householdId = state.selectedHouseholdId) {
  const personIds = new Set(peopleForHousehold(householdId).map((item) => item.id));
  return state.data.incomes.filter((item) => personIds.has(item.person_id));
}

function recurringCostsForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.recurringCosts.filter((item) => item.household_id === householdId);
}

function normalizeRecurringCostCategory(category) {
  const normalized = String(category || "").trim().toLowerCase();
  if (normalized === "housing") return "boende";
  return normalized;
}

function isHousingRecurringCategory(category) {
  return normalizeRecurringCostCategory(category) === "boende";
}

function recurringCostFormValue(item = {}) {
  if (!item || !item.category) return item;
  return { ...item, category: normalizeRecurringCostCategory(item.category) };
}

function loansForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.loans.filter((item) => item.household_id === householdId);
}

function subscriptionsForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.subscriptions.filter((item) => item.household_id === householdId);
}

function insuranceForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.insurancePolicies.filter((item) => item.household_id === householdId);
}

function vehiclesForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.vehicles.filter((item) => item.household_id === householdId);
}

function assetsForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.assets.filter((item) => item.household_id === householdId);
}

function housingForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.housing.filter((item) => item.household_id === householdId);
}

function documentsForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.documents.filter((item) => item.household_id === householdId);
}

function opportunitiesForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.opportunities.filter((item) => item.household_id === householdId);
}

function currentEdit(moduleKey) {
  return state.editing[moduleKey] || null;
}

function setEdit(moduleKey, item) {
  state.editing[moduleKey] = item ? { ...item } : null;
}

function clearEdits() {
  Object.keys(state.editing).forEach((key) => {
    state.editing[key] = null;
  });
}

function money(value) {
  return new Intl.NumberFormat("sv-SE", {
    style: "currency",
    currency: "SEK",
    maximumFractionDigits: 0,
  }).format(Number(value || 0));
}

function number(value, digits = 0) {
  return new Intl.NumberFormat("sv-SE", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  }).format(Number(value || 0));
}

function dateLabel(value) {
  if (!value) return "Ej angivet";
  return new Intl.DateTimeFormat("sv-SE").format(new Date(value));
}

function optionLabel(options, value) {
  return options.find(([optionValue]) => String(optionValue) === String(value))?.[1] || value || "Ej angivet";
}

function personName(personId) {
  return state.data.persons.find((item) => item.id === personId)?.name || "Ingen koppling";
}

function assetName(assetId) {
  const item = state.data.assets.find((asset) => asset.id === assetId);
  return item ? escapeHtml(item.label || item.institution || optionLabel(OPTIONS.assetType, item.type)) : "Ingen koppling";
}

function loanName(loanId) {
  const item = state.data.loans.find((loan) => loan.id === loanId);
  if (!item) return "Ingen koppling";
  return `${optionLabel(OPTIONS.loanType, item.type)}${item.lender ? ` · ${escapeHtml(item.lender)}` : ""}`;
}

function policyName(policyId) {
  const item = state.data.insurancePolicies.find((policy) => policy.id === policyId);
  return item ? `${escapeHtml(item.provider)} · ${money(item.premium_monthly)}` : "Ingen koppling";
}

function selectedSummary() {
  return state.summary;
}

function onboardingSteps() {
  if (!selectedHousehold()) {
    return [{ page: "household", title: "Skapa hushåll", text: "Börja här så kan resten kopplas rätt automatiskt." }];
  }

  const steps = [];
  if (incomesForHousehold().length === 0 && recurringCostsForHousehold().length === 0) {
    steps.push({ page: "assistant", title: "Importera bankunderlag", text: "Slipp mata in allt manuellt. Ladda upp filer eller klistra in utdrag i assistenten så drar vi fram allt åt dig." });
  }

  if (!peopleForHousehold().length) {
    steps.push({ page: "household", title: "Lägg till personer", text: "Behövs för att koppla inkomster och fordon." });
  }
  if (!incomesForHousehold().length) {
    steps.push({ page: "incomes", title: "Saknas autodata?", text: "Får vi inte in lön via bankfilen kan du lägga in nettolön manuellt här." });
  }
  if (!loansForHousehold().length) {
    steps.push({ page: "loans", title: "Säkerställ lån", text: "Avbetalningar från banken hanteras delvis, men specifika räntor kan behöva matas in." });
  }
  if (!subscriptionsForHousehold().length) {
    steps.push({ page: "subscriptions", title: "Granska löpande avtal", text: "Bankimporten hittar ofta många av dessa. Granska dem därefter." });
  }
  if (!housingForHousehold().length) {
    steps.push({ page: "housing", title: "Skapa boendekalkyl", text: "Bra för att se kvar att leva på och räntestress." });
  }
  return steps;
}

function warningsFromSummary(summary) {
  if (!summary) return [];
  const warnings = [];
  if (summary.monthly_net_cashflow < 0) {
    warnings.push("Hushållet går back varje månad. Börja med inkomster, avtal och lån.");
  }
  if (summary.gross_income_only_entries > 0) {
    warnings.push("Minst en inkomst saknar nettobelopp. Kassaflödet använder brutto tills du fyller i netto.");
  }
  if (summary.monthly_income > 0 && summary.monthly_loan_payments > summary.monthly_income * 0.35) {
    warnings.push("Lånekostnaden är hög i förhållande till hushållets inkomster.");
  }
  if (summary.monthly_subscriptions > 0 && summary.monthly_income > 0 && summary.monthly_subscriptions > summary.monthly_income * 0.05) {
    warnings.push("Abonnemang och avtal tar en ovanligt stor del av hushållets pengar.");
  }
  return warnings;
}

function dueForReviewCount() {
  return subscriptionsForHousehold().filter((item) => item.next_review_at && daysUntil(item.next_review_at) <= 30).length;
}

function priceJumpCount() {
  return subscriptionsForHousehold().filter((item) => Number(item.ordinary_cost || 0) > Number(item.current_monthly_cost || 0)).length;
}

function optionalContractsCount() {
  return subscriptionsForHousehold().filter((item) => ["optional", "dead_weight"].includes(item.household_criticality)).length;
}

function daysUntil(dateValue) {
  const target = new Date(dateValue);
  const now = new Date();
  return Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

function riskLabel(value) {
  const map = { low: "Låg", medium: "Medel", high: "Hög" };
  return map[value] || "Okänd";
}

function effortLabel(value) {
  const map = { low: "Liten insats", medium: "Måttlig insats", high: "Hög insats" };
  return map[value] || "Måttlig insats";
}

function badgeTone(value) {
  if (value === "high") return "danger";
  if (value === "medium") return "warning";
  if (value === "open") return "success";
  return "muted";
}

function subscriptionSignals(item) {
  const signals = [];
  if (Number(item.ordinary_cost || 0) > Number(item.current_monthly_cost || 0)) {
    signals.push({ tone: "warning", label: `Ordinarie pris ${money(item.ordinary_cost)}` });
  }
  if (item.binding_end_date) {
    signals.push({ tone: "muted", label: `Bindning till ${dateLabel(item.binding_end_date)}` });
  }
  if (item.next_review_at) {
    signals.push({
      tone: daysUntil(item.next_review_at) <= 30 ? "warning" : "muted",
      label: `Nästa granskning ${dateLabel(item.next_review_at)}`,
    });
  }
  if (["optional", "dead_weight"].includes(item.household_criticality)) {
    signals.push({ tone: "danger", label: "Kan sannolikt sänkas eller avslutas" });
  }
  return signals;
}

function opportunityAction(kind) {
  const map = {
    cancel: "Överväg att avsluta avtalet om hushållet klarar sig utan det.",
    renegotiate: "Kontakta leverantören och be om bättre pris eller villkor.",
    switch_provider: "Jämför med alternativ leverantör innan nästa förnyelse.",
    reduce_usage: "Se om kostnaden går att pressa genom lägre användning.",
    consolidate_debt: "Undersök om lån kan samlas eller göras om.",
  };
  return map[kind] || "Gå igenom förslaget och avgör om det passar hushållet.";
}

function reportTypeLabel(type) {
  const map = {
    monthly_overview: "Månadsrapport",
    optimization_report: "Förbättringsrapport",
    bank_calc: "Bankkalkyl",
  };
  return map[type] || type || "Rapport";
}

function opportunityTitleLabel(item) {
  const title = String(item?.title || "").trim();
  if (item?.kind === "renegotiate" && title.startsWith("Review ") && title.endsWith(" pricing")) {
    return `Granska priset för ${title.slice("Review ".length, -" pricing".length).trim()}`;
  }
  if (item?.kind === "cancel" && title.startsWith("Cancel optional subscription:")) {
    return `Överväg att avsluta abonnemanget: ${title.slice("Cancel optional subscription:".length).trim()}`;
  }
  if (item?.kind === "reduce_usage" && title.startsWith("Reduce ")) {
    return `Minska kostnaden för ${recurringCostLabel(title.slice("Reduce ".length).trim())}`;
  }
  return title || "Förbättringsförslag";
}

function opportunityRationaleLabel(item) {
  const rationale = String(item?.rationale || "").trim();
  if (!rationale) return opportunityAction(item?.kind);
  if (rationale === "Ordinary price is above current price and likely worth renegotiating.") {
    return "Ordinarie pris ligger över nuvarande pris och bör sannolikt omförhandlas.";
  }
  if (rationale === "Marked optional and contributes recurring monthly cost.") {
    return "Posten är markerad som valbar och påverkar hushållets månadskostnad.";
  }
  if (rationale === "Cost is marked reducible/discretionary.") {
    return "Posten är markerad som möjlig att sänka eller valbar.";
  }
  return rationale;
}

// Removed duplicate render function
function renderAuthPage() {
  return `
    <div class="auth-container">
      <div class="auth-shell">
        <section class="auth-brand-panel">
          <span class="auth-mark">HE</span>
          <span class="page-eyebrow">Svensk hushållsekonomi</span>
          <h2>Logga in till hushållets ekonomi</h2>
          <p class="page-subtitle">Auth-gaten ligger kvar framför all data. Ingen hushållsdata visas utan giltig session, och inloggningen är fortsatt ett separat skyddslager före ekonomin.</p>
          <div class="badge-row">
            <span class="badge success">Session-skyddad</span>
            <span class="badge muted">Read-only AI</span>
            <span class="badge warning">Dokument review krävs</span>
          </div>
        </section>
        <section class="panel auth-panel">
          <div class="auth-section">
            <span class="section-eyebrow">Logga in</span>
            <h3>Fortsatt arbete i samma hushåll</h3>
            <form id="loginForm" class="auth-form">
              <div class="field">
                <label>Användarnamn</label>
                <input type="text" name="username" required />
              </div>
              <div class="field">
                <label>Lösenord</label>
                <input type="password" name="password" required />
              </div>
              <button type="submit" class="primary">Logga in</button>
            </form>
          </div>
          <div class="auth-divider"><span>eller</span></div>
          <div class="auth-section">
            <span class="section-eyebrow">Skapa konto</span>
            <h3>Ny inloggning med eget hushåll</h3>
            <form id="registerForm" class="auth-form">
              <div class="field">
                <label>Nytt användarnamn</label>
                <input type="text" name="username" required />
              </div>
              <div class="field">
                <label>Lösenord</label>
                <input type="password" name="password" required />
              </div>
              <div class="field">
                <label>Hushållets namn (valfritt)</label>
                <input type="text" name="household_name" />
              </div>
              <button type="submit" class="primary">Registrera</button>
            </form>
          </div>
        </section>
      </div>
    </div>
  `;
}

async function handleLogin(form) {
  const data = new URLSearchParams();
  data.append("username", form.querySelector('[name="username"]').value);
  data.append("password", form.querySelector('[name="password"]').value);
  try {
    const res = await request("/auth/token", {
      method: "POST",
      body: data
    });
    localStorage.setItem("he_session_token", res.access_token);
    await refreshAllData();
    render();
  } catch (error) {
    alert("Inloggning misslyckades: " + error.message);
  }
}

async function handleRegister(form) {
  const payload = {
    username: form.querySelector('[name="username"]').value,
    password: form.querySelector('[name="password"]').value,
    household_name: form.querySelector('[name="household_name"]').value
  };
  try {
    const registered = await request("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    // Auto-login after registration
    const loginData = new URLSearchParams();
    loginData.append("username", payload.username);
    loginData.append("password", payload.password);
    const res = await request("/auth/token", {
      method: "POST",
      body: loginData
    });
    localStorage.setItem("he_session_token", res.access_token);
    if (registered.household_id) {
      state.selectedHouseholdId = Number(registered.household_id);
      persistSelection();
    }
    await refreshAllData();
    render();
  } catch (error) {
    alert("Registrering misslyckades: " + error.message);
  }
}

function renderHouseholdSelect() {
  const items = households();
  if (!items.length) {
    els.householdSelect.innerHTML = `<option value="">Inget hushåll ännu</option>`;
    els.householdSelect.disabled = true;
    return;
  }

  els.householdSelect.disabled = false;
  els.householdSelect.innerHTML = items
    .map((item) => `<option value="${item.id}" ${item.id === state.selectedHouseholdId ? "selected" : ""}>${escapeHtml(item.name)}</option>`)
    .join("");
}

function renderPageActions() {
  if (state.page === "overview") {
    return `
      <button class="ghost" type="button" data-nav="subscriptions">Granska avtal</button>
      <button class="primary" type="button" data-nav="household">Hantera hushåll</button>
    `;
  }
  if (state.page === "improvements") {
    return `<button class="primary" type="button" data-action="scan-opportunities" ${selectedHousehold() ? "" : "disabled"}>Analysera hushållet</button>`;
  }
  if (["incomes", "loans", "costs", "subscriptions", "vehicles", "assets", "housing"].includes(state.page)) {
    return `<button class="primary" type="button" data-action="new-record" data-module="${moduleKeyForPage(state.page)}" ${selectedHousehold() ? "" : "disabled"}>Ny post</button>`;
  }
  return "";
}

function renderPageBody() {
  switch (state.page) {
    case "overview":
      return renderOverviewPage();
    case "household":
      return renderHouseholdPage();
    case "incomes":
      return renderCollectionLayout({
        moduleKey: "income",
        items: incomesForHousehold(),
        title: "Inkomster",
        emptyTitle: "Inga inkomster ännu",
        emptyCopy: peopleForHousehold().length
          ? "Lägg in lön, CSN, pension eller bidrag för att få en begriplig översikt."
          : "Lägg först till minst en person i hushållet så att inkomsten kan kopplas rätt.",
        stats: renderIncomeStats(),
        renderCard: renderIncomeCard,
        renderFormBlock: renderIncomeFormBlock,
      });
    case "loans":
      return renderCollectionLayout({
        moduleKey: "loan",
        items: loansForHousehold(),
        title: "Lån",
        emptyTitle: "Inga lån ännu",
        emptyCopy: "Lägg in bolån, billån, CSN eller kreditkort för att se månadskostnaden tydligt.",
        stats: renderLoanStats(),
        renderCard: renderLoanCard,
        renderFormBlock: renderLoanFormBlock,
      });
    case "costs":
      return renderCostsPage();
    case "subscriptions":
      return renderSubscriptionsPage();
    case "vehicles":
      return renderCollectionLayout({
        moduleKey: "vehicle",
        items: vehiclesForHousehold(),
        title: "Fordon",
        emptyTitle: "Inga fordon ännu",
        emptyCopy: "Lägg in bil eller annat fordon för att samla bränsle, service, skatt och parkering.",
        stats: renderVehicleStats(),
        renderCard: renderVehicleCard,
        renderFormBlock: renderVehicleFormBlock,
      });
    case "assets":
      return renderCollectionLayout({
        moduleKey: "asset",
        items: assetsForHousehold(),
        title: "Tillgångar",
        emptyTitle: "Inga tillgångar ännu",
        emptyCopy: "Lägg in konton, sparande, fonder och andra tillgångar för en tydligare nettobild.",
        stats: renderAssetStats(),
        renderCard: renderAssetCard,
        renderFormBlock: renderAssetFormBlock,
      });
    case "housing":
      return renderHousingPage();
    case "documents":
      return renderDocumentsPage();
    case "improvements":
      return renderImprovementsPage();
    default:
      return "";
  }
}

function renderOverviewPage() {
  const household = selectedHousehold();
  if (!household) {
    return `
      <section class="panel">
        <div class="empty-state">
          <h3>Börja med att skapa hushållet</h3>
          <p class="empty-copy">Skapa ett hushåll först så kan du lägga in personer, inkomster och kostnader.</p>
          <div class="button-row">
            <button class="primary" type="button" data-nav="household">Skapa hushåll</button>
          </div>
        </div>
      </section>
    `;
  }

  const summary = selectedSummary();
  const warnings = warningsFromSummary(summary);
  const steps = onboardingSteps();
  const improvements = opportunitiesForHousehold()
    .slice()
    .sort((a, b) => Number(b.estimated_monthly_saving || 0) - Number(a.estimated_monthly_saving || 0))
    .slice(0, 3);
  const fixedCosts = Number(summary?.monthly_recurring_costs || 0) + Number(summary?.monthly_insurance || 0);

  return `
    <section class="summary-hero">
      <article class="panel">
        <span class="eyebrow">Nuläge</span>
        <h3>${escapeHtml(household.name)}</h3>
        <p class="meta-text">Inkomster, fasta kostnader, avtal, lån och fordon i en vy.</p>
        <div class="metrics-grid">
          ${renderMetricCard("Inkomst", money(summary?.monthly_income), "Månadsinkomst enligt nuvarande data.")}
          ${renderMetricCard("Fasta kostnader", money(fixedCosts), "Återkommande kostnader och försäkringar.", "warning")}
          ${renderMetricCard("Avtal", money(summary?.monthly_subscriptions), `${subscriptionsForHousehold().length} avtal.`)}
          ${renderMetricCard("Lån", money(summary?.monthly_loan_payments), `${loansForHousehold().length} lån.`)}
          ${renderMetricCard("Fordon", money(summary?.monthly_vehicle_costs), `${vehiclesForHousehold().length} fordon.`)}
          ${renderMetricCard("Kvar", money(summary?.monthly_net_cashflow), "Efter allt som ligger inne.", summary?.monthly_net_cashflow >= 0 ? "positive" : "danger")}
        </div>
      </article>

      <article class="spotlight-card">
        <span class="eyebrow">Nästa steg</span>
        <h3>Det som saknas</h3>
        ${steps.length
          ? `<div class="journey-grid">${steps.map((step) => `
              <article class="journey-card">
                <h4>${escapeHtml(step.title)}</h4>
                <p class="meta-text">${escapeHtml(step.text)}</p>
                <button class="ghost" type="button" data-nav="${step.page}">Öppna</button>
              </article>
            `).join("")}</div>`
          : `<div class="empty-state"><p class="empty-copy">Grunden finns på plats.</p></div>`}
      </article>
    </section>

    <section class="overview-grid">
      <article class="panel">
        <div class="section-head">
          <div>
            <span class="kicker">Kontrollpunkter</span>
            <h3>Så ser läget ut just nu</h3>
          </div>
        </div>
        ${warnings.length
          ? `<ul class="warning-list">${warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
          : `<p class="empty-copy">Inga tydliga varningssignaler just nu.</p>`}
        <div class="card-grid">
          <article class="record-card">
            <span class="mini-label">Tillgångar</span>
            <div class="spotlight-number">${money(summary?.asset_market_value)}</div>
            <p class="meta-text">Likvida medel: ${money(summary?.asset_liquid_value)}</p>
          </article>
          <article class="record-card">
            <span class="mini-label">Uppskattad nettoställning</span>
            <div class="spotlight-number">${money(summary?.net_worth_estimate)}</div>
            <p class="meta-text">Tillgångar minus registrerade lån.</p>
          </article>
        </div>
      </article>

      <article class="panel">
        <div class="section-head">
          <div>
            <span class="kicker">Förslag</span>
            <h3>Besparingar att titta på</h3>
          </div>
          <button class="ghost" type="button" data-nav="improvements">Visa alla</button>
        </div>
        ${improvements.length
          ? `<div class="card-stack">${improvements.map(renderOpportunityCard).join("")}</div>`
          : `<div class="empty-state">
              <p class="empty-copy">Det finns inga färdiga förslag ännu för det här hushållet.</p>
              <button class="primary" type="button" data-action="scan-opportunities">Hitta förbättringsförslag</button>
            </div>`}
      </article>
    </section>

    <section class="card-grid">
      <article class="panel">
        <span class="kicker">Avtal som bör granskas</span>
        <h3>Abonnemang och avtal</h3>
        <div class="stats-strip">
          ${renderStatPill("Avtal", subscriptionsForHousehold().length)}
          ${renderStatPill("Snart dags att granska", dueForReviewCount())}
          ${renderStatPill("Kan höjas till ordinarie pris", priceJumpCount())}
          ${renderStatPill("Kan ifrågasättas", optionalContractsCount())}
        </div>
        <div class="card-stack">
          ${subscriptionsForHousehold().slice(0, 3).map(renderSubscriptionCard).join("") || `<p class="empty-copy">Lägg in hushållets avtal här för att få bättre kontroll.</p>`}
        </div>
      </article>

      <article class="panel">
        <span class="kicker">Fasta kostnader</span>
        <h3>Det som drar pengar varje månad</h3>
        <div class="card-stack">
          ${renderFixedCostCards()}
        </div>
      </article>
    </section>
  `;
}

function renderHouseholdPage() {
  const household = selectedHousehold();
  const people = peopleForHousehold();
  return `
    <section class="split-layout">
      <article class="panel">
        <span class="kicker">Hushållets grund</span>
        <h3>${household ? escapeHtml(household.name) : "Skapa första hushållet"}</h3>
        <p class="meta-text">All annan data kopplas hit. Du ska inte behöva fylla i hushålls-id manuellt.</p>
        ${renderForm("householdForm", householdFields(), household || {}, {
          submitLabel: household ? "Spara hushåll" : "Skapa hushåll",
          canDelete: Boolean(household),
          deleteLabel: "Ta bort hushåll",
        })}
      </article>

      <article class="panel">
        <div class="section-head">
          <div>
            <span class="kicker">Personer i hushållet</span>
            <h3>${people.length ? `${people.length} personer registrerade` : "Lägg till första personen"}</h3>
          </div>
          ${selectedHousehold() ? `<button class="ghost" type="button" data-action="new-record" data-module="person">Ny person</button>` : ""}
        </div>
        <div class="card-stack">
          ${people.length ? people.map(renderPersonCard).join("") : `<div class="empty-state"><p class="empty-copy">Här lägger du in vuxna och barn som ekonomin rör.</p></div>`}
        </div>
        ${selectedHousehold() ? renderForm("personForm", personFields(), currentEdit("person") || {}, {
          submitLabel: currentEdit("person")?.id ? "Spara person" : "Lägg till person",
          canDelete: Boolean(currentEdit("person")?.id),
          deleteLabel: "Ta bort person",
        }) : ""}
      </article>
    </section>
  `;
}

function renderCollectionLayout({ moduleKey, items, title, emptyTitle, emptyCopy, stats, renderCard, renderFormBlock }) {
  return `
    ${stats}
    <section class="split-layout">
      <article class="panel">
        <div class="section-head">
          <div>
            <span class="kicker">${escapeHtml(title)}</span>
            <h3>${items.length ? `${items.length} poster` : escapeHtml(emptyTitle)}</h3>
          </div>
          ${selectedHousehold() ? `<button class="ghost" type="button" data-action="new-record" data-module="${moduleKey}">Ny post</button>` : ""}
        </div>
        <div class="card-stack">
          ${items.length ? items.map(renderCard).join("") : `<div class="empty-state"><p class="empty-copy">${escapeHtml(emptyCopy)}</p></div>`}
        </div>
      </article>

      <article class="panel">
        ${selectedHousehold()
          ? renderFormBlock()
          : `<div class="empty-state"><p class="empty-copy">Skapa eller välj först ett hushåll högst upp.</p></div>`}
      </article>
    </section>
  `;
}

function renderSubscriptionsPage() {
  const items = subscriptionsForHousehold();
  return `
    <section class="panel">
      <span class="kicker">Avtal som påverkar vardagen</span>
      <h3>Håll koll på pris, bindning och nästa granskning</h3>
      <div class="stats-strip">
        ${renderStatPill("Avtal", items.length)}
        ${renderStatPill("Månadskostnad", money(sum(items.map((item) => item.current_monthly_cost))))}
        ${renderStatPill("Snart att granska", dueForReviewCount())}
        ${renderStatPill("Möjliga att ifrågasätta", optionalContractsCount())}
      </div>
    </section>

    <section class="split-layout">
      <article class="panel">
        <div class="section-head">
          <div>
            <span class="kicker">Avtalslista</span>
            <h3>${items.length ? `${items.length} avtal sparade` : "Lägg till första avtalet"}</h3>
          </div>
          ${selectedHousehold() ? `<button class="ghost" type="button" data-action="new-record" data-module="subscription">Nytt avtal</button>` : ""}
        </div>
        <div class="card-stack">
          ${items.length ? items.map(renderSubscriptionCard).join("") : `<div class="empty-state"><p class="empty-copy">Mobil, bredband, el, streaming, gym och försäkringar hör hemma här.</p></div>`}
        </div>
      </article>

      <article class="panel">
        <span class="kicker">Avtalsformulär</span>
        <h3>${currentEdit("subscription")?.id ? "Redigera avtal" : "Lägg till avtal"}</h3>
        <p class="meta-text">Här är det viktigaste tydligt: leverantör, nuvarande pris, ordinarie pris, bindningstid och nästa granskning.</p>
        ${selectedHousehold()
          ? renderForm("subscriptionForm", subscriptionFields(), currentEdit("subscription") || {}, {
              submitLabel: currentEdit("subscription")?.id ? "Spara avtal" : "Skapa avtal",
              canDelete: Boolean(currentEdit("subscription")?.id),
              deleteLabel: "Ta bort avtal",
            })
          : ""}
      </article>
    </section>
  `;
}

function renderCostsPage() {
  const recurring = recurringCostsForHousehold();
  const policies = insuranceForHousehold();
  const totalRecurring = sum(recurring.map((item) => amountToMonthlyCost(item)));
  const totalInsurance = sum(policies.map((item) => item.premium_monthly));

  return `
    <section class="panel">
      <div class="section-head">
        <div>
          <span class="kicker">Fasta kostnader</span>
          <h3>Återkommande kostnader och försäkringar</h3>
          <p class="meta-text">Här lägger du in hushållets fasta månadsposter. För avbetalningar kan du skriva återstående belopp i anteckningen tills backend har ett eget fält.</p>
        </div>
        <button class="primary" type="button" data-action="new-record" data-module="cost" ${selectedHousehold() ? "" : "disabled"}>Ny kostnad</button>
      </div>
      <div class="stats-strip">
        ${renderStatPill("Kostnader", recurring.length)}
        ${renderStatPill("Försäkringar", policies.length)}
        ${renderStatPill("Totalt per månad", money(totalRecurring + totalInsurance))}
        ${renderStatPill("Avbetalning/övrigt", money(sum(recurring.filter((item) => String(item.category) === "debt").map((item) => amountToMonthlyCost(item)))))}
      </div>
    </section>

    <section class="split-layout">
      <article class="panel">
        <div class="section-head">
          <div>
            <span class="kicker">Återkommande kostnader</span>
            <h3>${recurring.length ? `${recurring.length} poster` : "Lägg till första kostnaden"}</h3>
          </div>
          ${selectedHousehold() ? `<button class="ghost" type="button" data-action="new-record" data-module="cost">Ny post</button>` : ""}
        </div>
        <div class="card-stack">
          ${recurring.length ? recurring.map(renderRecurringCostCard).join("") : `<div class="empty-state"><p class="empty-copy">Lägg in exempelvis avbetalning, daglig kostnad eller annan fast post.</p></div>`}
        </div>
      </article>

      <article class="panel">
        <span class="kicker">Kostnadsformulär</span>
        <h3>${currentEdit("cost")?.id ? "Redigera kostnad" : "Lägg till kostnad"}</h3>
        <p class="meta-text">Här fungerar avbetalningar också. Skriv gärna kvarvarande belopp i anteckningen om posten är en skuld som ska följas upp.</p>
        ${selectedHousehold()
          ? renderForm("costForm", recurringCostFields(), recurringCostFormValue(currentEdit("cost") || {}), {
              submitLabel: currentEdit("cost")?.id ? "Spara kostnad" : "Skapa kostnad",
              canDelete: Boolean(currentEdit("cost")?.id),
              deleteLabel: "Ta bort kostnad",
            })
          : `<div class="empty-state"><p class="empty-copy">Välj hushåll först.</p></div>`}
      </article>
    </section>

    <section class="split-layout">
      <article class="panel">
        <div class="section-head">
          <div>
            <span class="kicker">Försäkringar</span>
            <h3>${policies.length ? `${policies.length} försäkringar` : "Lägg till första försäkringen"}</h3>
          </div>
          ${selectedHousehold() ? `<button class="ghost" type="button" data-action="new-record" data-module="insurance">Ny försäkring</button>` : ""}
        </div>
        <div class="card-stack">
          ${policies.length ? policies.map(renderInsuranceCard).join("") : `<div class="empty-state"><p class="empty-copy">Lägg in hem-, bil- eller personförsäkringar här.</p></div>`}
        </div>
      </article>

      <article class="panel">
        <span class="kicker">Försäkringsformulär</span>
        <h3>${currentEdit("insurance")?.id ? "Redigera försäkring" : "Lägg till försäkring"}</h3>
        ${selectedHousehold()
          ? renderForm("insuranceForm", insuranceFields(), currentEdit("insurance") || {}, {
              submitLabel: currentEdit("insurance")?.id ? "Spara försäkring" : "Skapa försäkring",
              canDelete: Boolean(currentEdit("insurance")?.id),
              deleteLabel: "Ta bort försäkring",
            })
          : `<div class="empty-state"><p class="empty-copy">Välj hushåll först.</p></div>`}
      </article>
    </section>
  `;
}

function renderHousingPage() {
  const items = housingForHousehold();
  const current = currentEdit("housing") || {};
  const evaluation = state.housingEvaluation;
  const stress = evaluation ? stressScenarioTotal(current, evaluation) : null;

  return `
    <section class="summary-hero">
      <article class="panel">
        <span class="kicker">Boendekalkyl</span>
        <h3>Vad kostar bostaden per månad?</h3>
        <p class="meta-text">Här ser du ränta, amortering, drift/avgift, försäkring och kvar att leva på i samma vy.</p>
        ${evaluation
          ? `<div class="metrics-grid">
              ${renderMetricCard("Månadskostnad", money(evaluation.monthly_total_cost), "Total månadskostnad för scenariot.", "warning")}
              ${renderMetricCard("Årskostnad", money(evaluation.yearly_total_cost), "Årligt utfall om läget håller i sig.")}
              ${renderMetricCard("Ränta per månad", money(evaluation.monthly_interest), "Baserat på angiven ränta.")}
              ${renderMetricCard("Amortering per månad", money(evaluation.monthly_amortization), "Baserat på angiven amortering.")}
              ${renderMetricCard("Kvar efter boendet", money(Number(selectedSummary()?.monthly_net_cashflow || 0) - Number(evaluation.monthly_total_cost || 0)), "En enkel indikation mot nuvarande hushållsöversikt.", Number(selectedSummary()?.monthly_net_cashflow || 0) - Number(evaluation.monthly_total_cost || 0) >= 0 ? "positive" : "danger")}
              ${renderMetricCard("Stresscenario (+2 % ränta)", money(stress), "Snabb stresstest för ränteläget.", "danger")}
            </div>`
          : `<div class="empty-state"><p class="empty-copy">Skapa eller välj ett scenario för att få kalkylen här.</p></div>`}
      </article>

      <article class="panel">
        <div class="section-head">
          <div>
            <span class="kicker">Sparade scenarier</span>
            <h3>${items.length ? `${items.length} scenarier` : "Inga scenarier ännu"}</h3>
          </div>
          ${selectedHousehold() ? `<button class="ghost" type="button" data-action="new-record" data-module="housing">Nytt scenario</button>` : ""}
        </div>
        <div class="card-stack">
          ${items.length ? items.map(renderHousingCard).join("") : `<div class="empty-state"><p class="empty-copy">Skapa ett scenario för att jämföra boendekostnader och stressnivåer.</p></div>`}
        </div>
      </article>
    </section>

    <section class="panel">
      <span class="kicker">Scenarioformulär</span>
      <h3>${current.id ? "Redigera boendescenario" : "Skapa nytt boendescenario"}</h3>
      ${selectedHousehold()
        ? renderForm("housingForm", housingFields(), current, {
            submitLabel: current.id ? "Spara scenario" : "Skapa scenario",
            canDelete: Boolean(current.id),
            deleteLabel: "Ta bort scenario",
          })
        : `<div class="empty-state"><p class="empty-copy">Välj hushåll först.</p></div>`}
    </section>
  `;
}

function renderDocumentsPage() {
  const items = documentsForHousehold();
  return `
    <section class="split-layout">
      <article class="panel">
        <span class="kicker">Ladda upp dokument</span>
        <h3>Avtal, kvitton, fakturor och låneavier</h3>
        <p class="meta-text">Dokumenten kopplas till hushållet och kan laddas ner igen när du behöver dem.</p>
        ${selectedHousehold()
          ? renderDocumentUploadForm()
          : `<div class="empty-state"><p class="empty-copy">Välj hushåll först så att dokumentet hamnar rätt.</p></div>`}
      </article>

      <article class="panel">
        <div class="section-head">
          <div>
            <span class="kicker">Uppladdade dokument</span>
            <h3>${items.length ? `${items.length} dokument` : "Inga dokument ännu"}</h3>
          </div>
        </div>
        <div class="card-stack">
          ${items.length ? items.map(renderDocumentCard).join("") : `<div class="empty-state"><p class="empty-copy">När du laddar upp avtal eller kvitton visas de här med tydliga etiketter.</p></div>`}
        </div>
      </article>
    </section>
  `;
}

function renderImprovementsPage() {
  const items = opportunitiesForHousehold();
  return `
    <section class="panel">
      <div class="section-head">
        <div>
          <span class="kicker">Förbättringsförslag</span>
          <h3>Vad kan hushållet göra härnäst?</h3>
          <p class="meta-text">Förslagen översätts till begripligt språk: besparingspotential, risk och arbetsinsats.</p>
        </div>
        <button class="primary" type="button" data-action="scan-opportunities" ${selectedHousehold() ? "" : "disabled"}>Analysera hushållet</button>
      </div>
      <div class="card-stack">
        ${items.length ? items.map(renderOpportunityCard).join("") : `<div class="empty-state"><p class="empty-copy">Det finns ännu inga förbättringsförslag sparade för det här hushållet.</p></div>`}
      </div>
    </section>
  `;
}

function renderMetricCard(label, value, text, tone = "") {
  return `
    <article class="metric-card ${tone}">
      <span class="metric-label">${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      <p class="subtle">${escapeHtml(text)}</p>
    </article>
  `;
}

function renderStatPill(label, value) {
  return `
    <article class="stat-pill">
      <span class="mini-label">${escapeHtml(label)}</span>
      <strong>${escapeHtml(String(value))}</strong>
    </article>
  `;
}

function renderFixedCostCards() {
  const cards = [
    ...recurringCostsForHousehold().map((item) => `
      <article class="record-card">
        <div class="record-header">
          <div>
            <h4 class="record-title">${escapeHtml(item.vendor || item.category || "Återkommande kostnad")}</h4>
            <p class="meta-text">${escapeHtml(recurringCostLabel(item.category))}${item.person_id ? ` · ${escapeHtml(personName(item.person_id))}` : ""}</p>
          </div>
          <div class="record-value">${money(amountToMonthlyCost(item))}</div>
        </div>
      </article>
    `),
    ...insuranceForHousehold().map((item) => `
      <article class="record-card">
        <div class="record-header">
          <div>
            <h4 class="record-title">${escapeHtml(item.provider)}</h4>
            <p class="meta-text">${escapeHtml(optionLabel(OPTIONS.insuranceType, item.type))}</p>
          </div>
          <div class="record-value">${money(item.premium_monthly)}</div>
        </div>
      </article>
    `),
  ].slice(0, 6);
  return cards.join("") || `<p class="empty-copy">Inga fasta kostnader eller försäkringar finns registrerade ännu.</p>`;
}

function renderPersonCard(item) {
  return `
    <article class="record-card ${currentEdit("person")?.id === item.id ? "is-active" : ""}">
      <div class="record-header">
        <div>
          <h4 class="record-title">${escapeHtml(item.name)}</h4>
          <p class="meta-text">${optionLabel(OPTIONS.role, item.role)} · ${item.active ? "Aktiv" : "Vilande"}</p>
        </div>
        <div class="card-actions">
          <button class="ghost" type="button" data-edit="person" data-id="${item.id}">Redigera</button>
        </div>
      </div>
    </article>
  `;
}

function renderIncomeCard(item) {
  return `
    <article class="record-card ${currentEdit("income")?.id === item.id ? "is-active" : ""}">
      <div class="record-header">
        <div>
          <h4 class="record-title">${optionLabel(OPTIONS.incomeType, item.type)}${item.source ? ` · ${escapeHtml(item.source)}` : ""}</h4>
          <p class="meta-text">${escapeHtml(personName(item.person_id))} · ${optionLabel(OPTIONS.frequency, item.frequency)}</p>
        </div>
        <div class="record-value">${money(item.net_amount || item.gross_amount)}</div>
      </div>
      <div class="card-actions">
        <button class="ghost" type="button" data-edit="income" data-id="${item.id}">Redigera</button>
      </div>
    </article>
  `;
}

function renderLoanCard(item) {
  return `
    <article class="record-card ${currentEdit("loan")?.id === item.id ? "is-active" : ""}">
      <div class="record-header">
        <div>
          <h4 class="record-title">${escapeHtml(item.purpose || optionLabel(OPTIONS.loanType, item.type))}${item.lender ? ` · ${escapeHtml(item.lender)}` : ""}</h4>
          <p class="meta-text">${item.person_id ? `${escapeHtml(personName(item.person_id))} · ` : ""}${optionLabel(OPTIONS.loanStatus, item.status)}</p>
        </div>
        <div class="record-value">${money(item.required_monthly_payment)}</div>
      </div>
      <div class="badge-row">
        <span class="badge">Skuld ${money(item.current_balance)}</span>
        ${item.remaining_term_months ? `<span class="badge muted">${number(item.remaining_term_months)} mån kvar</span>` : ""}
        ${item.nominal_rate ? `<span class="badge">${number(item.nominal_rate, 2)} % ränta</span>` : ""}
      </div>
      <div class="card-actions">
        <button class="ghost" type="button" data-edit="loan" data-id="${item.id}">Redigera</button>
      </div>
    </article>
  `;
}

function renderSubscriptionCard(item) {
  return `
    <article class="record-card ${currentEdit("subscription")?.id === item.id ? "is-active" : ""}">
      <div class="record-header">
        <div>
          <h4 class="record-title">${escapeHtml(item.provider)}${item.product_name ? ` · ${escapeHtml(item.product_name)}` : ""}</h4>
          <p class="meta-text">${optionLabel(OPTIONS.subscriptionCategory, item.category)}${item.person_id ? ` · ${escapeHtml(personName(item.person_id))}` : ""}</p>
        </div>
        <div class="record-value">${money(item.current_monthly_cost)}</div>
      </div>
      <div class="badge-row">
        <span class="badge">${optionLabel(OPTIONS.subscriptionCriticality, item.household_criticality)}</span>
        ${subscriptionSignals(item).map((signal) => `<span class="badge ${signal.tone}">${escapeHtml(signal.label)}</span>`).join("")}
        ${item.notice_period_days ? `<span class="badge muted">${item.notice_period_days} dagars uppsägning</span>` : ""}
      </div>
      <div class="card-actions">
        <button class="ghost" type="button" data-edit="subscription" data-id="${item.id}">Redigera</button>
      </div>
    </article>
  `;
}

function renderVehicleCard(item) {
  return `
    <article class="record-card ${currentEdit("vehicle")?.id === item.id ? "is-active" : ""}">
      <div class="record-header">
        <div>
          <h4 class="record-title">${escapeHtml([item.make, item.model].filter(Boolean).join(" ") || "Fordon")}</h4>
          <p class="meta-text">${item.owner_person_id ? `${escapeHtml(personName(item.owner_person_id))} · ` : ""}${item.year || "År ej angivet"}</p>
        </div>
        <div class="record-value">${money(vehicleMonthlyCost(item))}</div>
      </div>
      <div class="badge-row">
        <span class="badge">${optionLabel(OPTIONS.fuelType, item.fuel_type)}</span>
        ${item.loan_id ? `<span class="badge muted">Lån kopplat</span>` : ""}
      </div>
      <div class="card-actions">
        <button class="ghost" type="button" data-edit="vehicle" data-id="${item.id}">Redigera</button>
      </div>
    </article>
  `;
}

function renderAssetCard(item) {
  return `
    <article class="record-card ${currentEdit("asset")?.id === item.id ? "is-active" : ""}">
      <div class="record-header">
        <div>
          <h4 class="record-title">${escapeHtml(item.label || item.institution || optionLabel(OPTIONS.assetType, item.type))}</h4>
          <p class="meta-text">${optionLabel(OPTIONS.assetType, item.type)}${item.person_id ? ` · ${escapeHtml(personName(item.person_id))}` : ""}</p>
        </div>
        <div class="record-value">${money(item.market_value)}</div>
      </div>
      <div class="badge-row">
        <span class="badge">Likvid del ${money(item.liquid_value)}</span>
        ${item.pledged ? `<span class="badge warning">Pantsatt</span>` : ""}
      </div>
      <div class="card-actions">
        <button class="ghost" type="button" data-edit="asset" data-id="${item.id}">Redigera</button>
      </div>
    </article>
  `;
}

function renderHousingCard(item) {
  const active = currentEdit("housing")?.id === item.id;
  return `
    <article class="record-card ${active ? "is-active" : ""}">
      <div class="record-header">
        <div>
          <h4 class="record-title">${escapeHtml(item.label)}</h4>
          <p class="meta-text">${money(item.purchase_price)} i bostadspris · ${number(item.rate_assumption, 2)} % ränta</p>
        </div>
        <div class="card-actions">
          <button class="ghost" type="button" data-edit="housing" data-id="${item.id}">Redigera</button>
          <button class="primary" type="button" data-evaluate-housing="${item.id}">Visa kalkyl</button>
        </div>
      </div>
    </article>
  `;
}

function renderDocumentCard(item) {
  return `
    <article class="record-card document-inbox-card ${state.ui.selectedDocumentId === item.id ? "is-active" : ""}">
      <div class="record-title-row">
        <div>
          <h4 class="record-title">${escapeHtml(item.file_name)}</h4>
          <p class="muted">${escapeHtml(optionLabel(OPTIONS.documentType, item.document_type))}${item.issuer ? ` · ${escapeHtml(item.issuer)}` : ""}</p>
        </div>
        <span class="badge ${documentExtractionMeta(item.extraction_status).tone}">${documentExtractionMeta(item.extraction_status).label}</span>
      </div>
      <p class="muted">${item.extracted_text ? escapeHtml(item.extracted_text.trim().slice(0, 130)) : "Ingen extraherad text ännu."}</p>
      <div class="badge-row">
        <span class="badge muted">${dateLabel(item.uploaded_at)}</span>
        ${item.processing_error ? `<span class="badge danger">Fel i tolkning</span>` : ""}
      </div>
      <div class="actions-row">
        <button class="primary compact" type="button" data-action="select-document" data-document-id="${item.id}">Öppna</button>
        <button class="ghost compact" type="button" data-action="analyze-document" data-document-id="${item.id}" ${item.extracted_text ? "" : "disabled"}>Tolka igen</button>
        <a class="ghost compact" href="/documents/${item.id}/download">Ladda ned</a>
      </div>
    </article>
  `;
}

function renderOpportunityCard(item) {
  return `
    <article class="record-card">
      <div class="record-header">
        <div>
          <h4 class="record-title">${escapeHtml(opportunityTitleLabel(item))}</h4>
          <p class="meta-text">${escapeHtml(opportunityRationaleLabel(item))}</p>
        </div>
        <div class="record-value">${money(item.estimated_monthly_saving)}</div>
      </div>
      <div class="badge-row">
        <span class="badge success">Besparing ${money(item.estimated_monthly_saving)} / mån</span>
        <span class="badge ${badgeTone(item.risk_level)}">Risk: ${riskLabel(item.risk_level)}</span>
        <span class="badge muted">${effortLabel(item.effort_level)}</span>
      </div>
      <p class="meta-text"><strong>Vad du kan göra:</strong> ${escapeHtml(opportunityAction(item.kind))}</p>
    </article>
  `;
}

function recurringCostLabel(value) {
  const map = Object.fromEntries(OPTIONS.recurringCostCategory);
  const normalized = normalizeRecurringCostCategory(value);
  return map[normalized] || normalized || "Återkommande kostnad";
}

function amountToMonthlyCost(item) {
  const amount = Number(item.amount || 0);
  const frequency = item.frequency || "monthly";
  if (frequency === "yearly") return amount / 12;
  if (frequency === "weekly") return amount * (52 / 12);
  if (frequency === "biweekly") return amount * (26 / 12);
  if (frequency === "daily") return amount * (365 / 12);
  return amount;
}

function renderIncomeStats() {
  const items = incomesForHousehold();
  const summary = selectedSummary();
  return `
    <section class="panel">
      <div class="stats-strip">
        ${renderStatPill("Inkomstkällor", items.length)}
        ${renderStatPill("Summa per månad", money(summary?.monthly_income))}
        ${renderStatPill("Personer med inkomst", new Set(items.map((item) => item.person_id)).size)}
        ${renderStatPill("Netto ifyllt", items.filter((item) => item.net_amount != null).length)}
      </div>
    </section>
  `;
}

function renderRecurringCostCard(item) {
  return `
    <article class="record-card ${currentEdit("cost")?.id === item.id ? "is-active" : ""}">
      <div class="record-header">
        <div>
          <h4 class="record-title">${escapeHtml(item.vendor || recurringCostLabel(item.category))}</h4>
          <p class="meta-text">${escapeHtml(recurringCostLabel(item.category))}${item.person_id ? ` · ${escapeHtml(personName(item.person_id))}` : ""}</p>
        </div>
        <div class="record-value">${money(amountToMonthlyCost(item))}</div>
      </div>
      <div class="badge-row">
        <span class="badge">${optionLabel(OPTIONS.frequency, item.frequency)}</span>
        <span class="badge muted">${optionLabel(OPTIONS.variabilityClass, item.variability_class || "fixed")}</span>
        ${item.mandatory === false ? `<span class="badge warning">Inte nödvändig</span>` : `<span class="badge success">Fast post</span>`}
        ${item.note ? `<span class="badge muted">${escapeHtml(item.note)}</span>` : ""}
      </div>
      <div class="card-actions">
        <button class="ghost" type="button" data-edit="cost" data-id="${item.id}">Redigera</button>
      </div>
    </article>
  `;
}

function renderInsuranceCard(item) {
  return `
    <article class="record-card ${currentEdit("insurance")?.id === item.id ? "is-active" : ""}">
      <div class="record-header">
        <div>
          <h4 class="record-title">${escapeHtml(item.provider)}</h4>
          <p class="meta-text">${escapeHtml(optionLabel(OPTIONS.insuranceType, item.type))}</p>
        </div>
        <div class="record-value">${money(item.premium_monthly)}</div>
      </div>
      <div class="badge-row">
        <span class="badge">${escapeHtml(item.type || "Försäkring")}</span>
        ${item.deductible ? `<span class="badge muted">Självrisk ${money(item.deductible)}</span>` : ""}
      </div>
      <div class="card-actions">
        <button class="ghost" type="button" data-edit="insurance" data-id="${item.id}">Redigera</button>
      </div>
    </article>
  `;
}

function renderLoanStats() {
  const items = loansForHousehold();
  return `
    <section class="panel">
      <div class="stats-strip">
        ${renderStatPill("Lån", items.length)}
        ${renderStatPill("Total skuld", money(sum(items.map((item) => item.current_balance))))}
        ${renderStatPill("Månadskostnad", money(sum(items.map((item) => item.required_monthly_payment))))}
        ${renderStatPill("Aktiva lån", items.filter((item) => item.status === "active").length)}
      </div>
    </section>
  `;
}

function renderVehicleStats() {
  const items = vehiclesForHousehold();
  return `
    <section class="panel">
      <div class="stats-strip">
        ${renderStatPill("Fordon", items.length)}
        ${renderStatPill("Månadskostnad", money(sum(items.map(vehicleMonthlyCost))))}
        ${renderStatPill("Kopplade lån", items.filter((item) => item.loan_id).length)}
        ${renderStatPill("Bilvärde", money(sum(items.map((item) => item.estimated_value))))}
      </div>
    </section>
  `;
}

function renderAssetStats() {
  const items = assetsForHousehold();
  return `
    <section class="panel">
      <div class="stats-strip">
        ${renderStatPill("Tillgångar", items.length)}
        ${renderStatPill("Marknadsvärde", money(sum(items.map((item) => item.market_value))))}
        ${renderStatPill("Likvida medel", money(sum(items.map((item) => item.liquid_value))))}
        ${renderStatPill("Pantsatta", items.filter((item) => item.pledged).length)}
      </div>
    </section>
  `;
}

function renderIncomeFormBlock() {
  return `
    <span class="kicker">Inkomstformulär</span>
    <h3>${currentEdit("income")?.id ? "Redigera inkomst" : "Lägg till inkomst"}</h3>
    <p class="meta-text">Person väljs i listan i stället för via internt id. Minst netto eller brutto bör fyllas i.</p>
    ${renderForm("incomeForm", incomeFields(), currentEdit("income") || {}, {
      submitLabel: currentEdit("income")?.id ? "Spara inkomst" : "Skapa inkomst",
      canDelete: Boolean(currentEdit("income")?.id),
      deleteLabel: "Ta bort inkomst",
    })}
  `;
}

function renderLoanFormBlock() {
  return `
    <span class="kicker">Låneformulär</span>
    <h3>${currentEdit("loan")?.id ? "Redigera lån" : "Lägg till lån"}</h3>
    <p class="meta-text">Använd även för avbetalningar som bil, säng och ögonlaser.</p>
    ${renderForm("loanForm", loanFields(), currentEdit("loan") || {}, {
      submitLabel: currentEdit("loan")?.id ? "Spara lån" : "Skapa lån",
      canDelete: Boolean(currentEdit("loan")?.id),
      deleteLabel: "Ta bort lån",
    })}
  `;
}

function renderVehicleFormBlock() {
  return `
    <span class="kicker">Fordonsformulär</span>
    <h3>${currentEdit("vehicle")?.id ? "Redigera fordon" : "Lägg till fordon"}</h3>
    <p class="meta-text">Det viktigaste är vad fordonet kostar varje månad: skatt, bränsle, service och parkering.</p>
    ${renderForm("vehicleForm", vehicleFields(), currentEdit("vehicle") || {}, {
      submitLabel: currentEdit("vehicle")?.id ? "Spara fordon" : "Skapa fordon",
      canDelete: Boolean(currentEdit("vehicle")?.id),
      deleteLabel: "Ta bort fordon",
    })}
  `;
}

function renderAssetFormBlock() {
  return `
    <span class="kicker">Tillgångsformulär</span>
    <h3>${currentEdit("asset")?.id ? "Redigera tillgång" : "Lägg till tillgång"}</h3>
    <p class="meta-text">Lägg in typ, namn och värde. Om det är sparade pengar kan du även ange likvid del.</p>
    ${renderForm("assetForm", assetFields(), currentEdit("asset") || {}, {
      submitLabel: currentEdit("asset")?.id ? "Spara tillgång" : "Skapa tillgång",
      canDelete: Boolean(currentEdit("asset")?.id),
      deleteLabel: "Ta bort tillgång",
    })}
  `;
}

function renderDocumentUploadForm() {
  return `
    <form id="documentUploadForm" class="form-grid">
      ${renderField({ key: "document_type", label: "Dokumenttyp", type: "select", options: OPTIONS.documentType, required: true }, state.ui.ingestResult?.document_summary?.document_type || "invoice")}
      ${renderField({ key: "issuer", label: "Avsändare eller leverantör", type: "text", placeholder: "Till exempel banken eller Tele2" }, state.ui.ingestSourceName || "")}
      ${renderField({ key: "currency", label: "Valuta", type: "text", placeholder: "SEK", default: "SEK" }, "SEK")}
      <div class="field full">
        <label for="document_file">Ladda upp PDF, bild, foto, textfil, .xlsx eller .xls</label>
        <div class="upload-box upload-box-compact">
          <input id="document_file" name="file" type="file" accept="image/*,application/pdf,text/plain,text/csv,text/*,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,.txt,.text,.csv,.json,.xml,.yaml,.yml,.md,.xlsx,.xls" capture="environment" required />
          <p class="helper-text">Fotografera dokumentet med mobilen, välj en PDF eller ladda upp en textfil/CSV. Förhandsvisning visas direkt när filen valts.</p>
        </div>
      </div>
      <div class="field full">
        <label for="document_extracted_text">Valfri notis</label>
        <textarea id="document_extracted_text" name="extracted_text" placeholder="Om du vill kan du lägga till en kort notis, men den extraherade texten ska komma från filen."></textarea>
      </div>
      <div class="field full">
        <div class="form-actions upload-actions">
          <button class="primary" type="submit">Ladda upp och tolka</button>
          <button class="ghost" type="button" data-action="clear-ingest">Rensa</button>
        </div>
      </div>
      <div id="documentUploadPreviewSlot" class="field full">
        ${renderDocumentUploadPreview()}
      </div>
    </form>
  `;
}

function renderDocumentUploadPreview() {
  const preview = state.ui.documentUploadPreview;
  if (!preview) {
    return `
      <article class="workflow-callout subtle">
        <strong>Förhandsvisning</strong>
        <p class="muted">När du väljer en fil visas den här direkt. Det gör att du ser att du valde rätt dokument innan du laddar upp det.</p>
      </article>
    `;
  }

  return `
    <article class="document-preview-card">
      <div class="record-title-row">
        <div>
          <h4 class="record-title">${escapeHtml(preview.name)}</h4>
          <p class="muted">${preview.category === "image" ? "Bild / foto" : preview.category === "pdf" ? "PDF" : "Fil"}${preview.size ? ` · ${number(preview.size / 1024, 0)} KB` : ""}</p>
        </div>
        <span class="badge info">Vald lokalt</span>
      </div>
      ${preview.category === "image"
        ? `<img class="document-preview-image" src="${escapeHtml(preview.objectUrl)}" alt="Förhandsvisning av vald fil" />`
        : preview.category === "pdf"
          ? `<iframe class="document-preview-frame" src="${escapeHtml(preview.objectUrl)}" title="Förhandsvisning av vald PDF"></iframe>`
          : `<p class="muted">Den här filtypen förhandsvisas efter uppladdning.</p>`}
    </article>
  `;
}

function renderForm(formId, fields, values, { submitLabel, canDelete, deleteLabel }) {
  return `
    <form id="${formId}" class="form-grid">
      ${fields.map((field) => renderField(field, values[field.key])).join("")}
      <div class="field full">
        <div class="form-actions">
          <button class="primary" type="submit">${submitLabel}</button>
          <button class="ghost" type="button" data-reset-form="${formId}">Rensa</button>
          ${canDelete ? `<button class="danger" type="button" data-delete-form="${formId}">${deleteLabel}</button>` : ""}
        </div>
      </div>
    </form>
  `;
}

function renderField(field, value = null) {
  const selectedValue = value ?? field.default ?? "";
  if (field.type === "checkbox") {
    return `
      <div class="field checkbox-field ${field.full ? "full" : ""}">
        <input id="${field.key}" name="${field.key}" type="checkbox" ${selectedValue ? "checked" : ""} />
        <label for="${field.key}">${field.label}</label>
      </div>
    `;
  }

  if (field.type === "select") {
    return `
      <div class="field ${field.full ? "full" : ""}">
        <label for="${field.key}">${field.label}</label>
        <select id="${field.key}" name="${field.key}" ${field.required ? "required" : ""}>
          <option value="">Välj...</option>
          ${field.options.map(([optionValue, optionLabel]) => `<option value="${escapeHtml(optionValue)}" ${String(optionValue) === String(selectedValue) ? "selected" : ""}>${escapeHtml(optionLabel)}</option>`).join("")}
        </select>
      </div>
    `;
  }

  if (field.type === "textarea") {
    return `
      <div class="field ${field.full ? "full" : ""}">
        <label for="${field.key}">${field.label}</label>
        <textarea id="${field.key}" name="${field.key}" placeholder="${escapeHtml(field.placeholder || "")}">${escapeHtml(selectedValue)}</textarea>
      </div>
    `;
  }

  return `
    <div class="field ${field.full ? "full" : ""}">
      <label for="${field.key}">${field.label}</label>
      <input
        id="${field.key}"
        name="${field.key}"
        type="${field.type || "text"}"
        value="${escapeHtml(selectedValue)}"
        placeholder="${escapeHtml(field.placeholder || "")}"
        ${field.required ? "required" : ""}
        ${field.step ? `step="${field.step}"` : ""}
      />
    </div>
  `;
}

function householdFields() {
  return [
    { key: "name", label: "Namn på hushållet", type: "text", required: true, placeholder: "Till exempel Familjen Andersson" },
    { key: "currency", label: "Valuta", type: "text", placeholder: "SEK", default: "SEK" },
    { key: "primary_country", label: "Land", type: "text", placeholder: "SE", default: "SE" },
  ];
}

function personFields() {
  return [
    { key: "name", label: "Namn", type: "text", required: true },
    { key: "role", label: "Roll i hushållet", type: "select", options: OPTIONS.role, required: true },
    { key: "income_share_mode", label: "Hur ekonomin delas", type: "select", options: [["pooled", "Gemensamt"], ["exact", "Exakt fördelning"], ["split", "Delad"]], required: true, default: "pooled" },
    { key: "active", label: "Aktiv person i hushållet", type: "checkbox", full: true, default: true },
  ];
}

function incomeFields() {
  return [
    { key: "person_id", label: "Person", type: "select", options: peopleOptions(), required: true },
    { key: "type", label: "Typ av inkomst", type: "select", options: OPTIONS.incomeType, required: true },
    { key: "net_amount", label: "Belopp efter skatt", type: "number", step: "0.01", placeholder: "Till exempel 28000" },
    { key: "gross_amount", label: "Belopp före skatt", type: "number", step: "0.01", placeholder: "Fyll i om du hellre vill lagra brutto" },
    { key: "frequency", label: "Hur ofta", type: "select", options: OPTIONS.frequency, required: true, default: "monthly" },
    { key: "regularity", label: "Stabilitet", type: "select", options: OPTIONS.regularity, required: true, default: "fixed" },
    { key: "source", label: "Arbetsgivare eller källa", type: "text", placeholder: "Till exempel Arbetsgivare AB" },
    { key: "start_date", label: "Startdatum", type: "date" },
    { key: "end_date", label: "Slutdatum", type: "date" },
    { key: "verified", label: "Verifierad inkomst", type: "checkbox", full: true, default: false },
    { key: "note", label: "Anteckning", type: "textarea", full: true, placeholder: "Till exempel extra timlön eller oregelbunden del." },
  ];
}

function loanFields() {
  return [
    { key: "type", label: "Typ av lån", type: "select", options: OPTIONS.loanType, required: true },
    { key: "purpose", label: "Vad gäller lånet?", type: "text", placeholder: "Till exempel Säng eller Bil" },
    { key: "lender", label: "Bank eller långivare", type: "text", placeholder: "Till exempel SEB" },
    { key: "person_id", label: "Koppla till person", type: "select", options: [["", "Ingen särskild person"], ...peopleOptions()] },
    { key: "current_balance", label: "Kvar att betala", type: "number", step: "0.01", placeholder: "Till exempel 12000" },
    { key: "remaining_term_months", label: "Månader kvar", type: "number", placeholder: "Till exempel 8" },
    { key: "planned_end_date", label: "Planerat slutdatum", type: "date" },
    { key: "nominal_rate", label: "Ränta (%)", type: "number", step: "0.01", placeholder: "Till exempel 4.29" },
    { key: "required_monthly_payment", label: "Månadskostnad", type: "number", step: "0.01", placeholder: "Till exempel 7200" },
    { key: "status", label: "Status", type: "select", options: OPTIONS.loanStatus, required: true, default: "active" },
    { key: "repayment_model", label: "Amorteringsmodell", type: "select", options: OPTIONS.repaymentModel, required: true, default: "annuity" },
    { key: "linked_asset_id", label: "Kopplad tillgång", type: "select", options: [["", "Ingen koppling"], ...assetOptions()] },
    { key: "secured", label: "Säkrat lån", type: "checkbox", default: false },
    { key: "autopay", label: "Autogiro", type: "checkbox", default: false },
    { key: "note", label: "Anteckning", type: "textarea", full: true },
  ];
}

function recurringCostFields() {
  return [
    { key: "category", label: "Kategori", type: "select", options: OPTIONS.recurringCostCategory, required: true },
    { key: "vendor", label: "Leverantör eller namn", type: "text", placeholder: "Till exempel Resurs Bank" },
    { key: "person_id", label: "Koppla till person", type: "select", options: [["", "Ingen särskild person"], ...peopleOptions()] },
    { key: "amount", label: "Belopp", type: "number", required: true, step: "0.01" },
    { key: "frequency", label: "Hur ofta", type: "select", options: OPTIONS.frequency, required: true, default: "monthly" },
    { key: "mandatory", label: "Nödvändig", type: "checkbox", default: true },
    { key: "variability_class", label: "Typ", type: "select", options: OPTIONS.variabilityClass, required: true, default: "fixed" },
    { key: "controllability", label: "Kontroll", type: "select", options: [["locked", "Låst"], ["negotiable", "Förhandlingsbar"], ["reducible", "Kan sänkas"], ["discretionary", "Valbar"]], required: true, default: "locked" },
    { key: "due_day", label: "Förfallodag", type: "number" },
    { key: "start_date", label: "Startdatum", type: "date" },
    { key: "end_date", label: "Slutdatum", type: "date" },
    { key: "note", label: "Anteckning", type: "textarea", full: true, placeholder: "Skriv gärna kvarvarande avbetalning här, till exempel 12 000 kr kvar." },
  ];
}

function insuranceFields() {
  return [
    { key: "type", label: "Typ", type: "select", options: OPTIONS.insuranceType, required: true },
    { key: "provider", label: "Försäkringsbolag", type: "text", required: true, placeholder: "Till exempel Folksam" },
    { key: "premium_monthly", label: "Premie per månad", type: "number", required: true, step: "0.01" },
    { key: "deductible", label: "Självrisk", type: "number", step: "0.01" },
    { key: "coverage_tier", label: "Omfattning", type: "text", placeholder: "Till exempel Bas eller Plus" },
    { key: "renewal_date", label: "Förnyas", type: "date" },
    { key: "binding_end_date", label: "Bindningstid till", type: "date" },
    { key: "linked_asset_id", label: "Koppla tillgång", type: "select", options: [["", "Ingen koppling"], ...assetOptions()] },
    { key: "note", label: "Anteckning", type: "textarea", full: true },
  ];
}

function subscriptionFields() {
  return [
    { key: "category", label: "Typ av avtal", type: "select", options: OPTIONS.subscriptionCategory, required: true },
    { key: "provider", label: "Leverantör", type: "text", required: true, placeholder: "Till exempel Telia" },
    { key: "product_name", label: "Produkt eller plan", type: "text", placeholder: "Till exempel Mobilabonnemang 20 GB" },
    { key: "person_id", label: "Koppla till person", type: "select", options: [["", "Ingen särskild person"], ...peopleOptions()] },
    { key: "current_monthly_cost", label: "Nuvarande pris per månad", type: "number", required: true, step: "0.01" },
    { key: "ordinary_cost", label: "Ordinarie pris per månad", type: "number", step: "0.01" },
    { key: "promotional_cost", label: "Kampanjpris", type: "number", step: "0.01" },
    { key: "promotional_end_date", label: "Kampanjen slutar", type: "date" },
    { key: "binding_end_date", label: "Bindningstid till", type: "date" },
    { key: "notice_period_days", label: "Uppsägningstid i dagar", type: "number" },
    { key: "household_criticality", label: "Hur viktigt är avtalet?", type: "select", options: OPTIONS.subscriptionCriticality, required: true, default: "optional" },
    { key: "next_review_at", label: "Nästa granskning", type: "date" },
    { key: "auto_renew", label: "Förnyas automatiskt", type: "checkbox", default: true },
    { key: "market_checkable", label: "Går lätt att jämföra mot marknaden", type: "checkbox", default: true },
    { key: "note", label: "Anteckning", type: "textarea", full: true, placeholder: "Till exempel uppsägningsväg, lojalitetspris eller vad ni använder avtalet till." },
  ];
}

function vehicleFields() {
  return [
    { key: "owner_person_id", label: "Ägare", type: "select", options: [["", "Ingen särskild person"], ...peopleOptions()] },
    { key: "make", label: "Märke", type: "text", placeholder: "Volvo" },
    { key: "model", label: "Modell", type: "text", placeholder: "V60" },
    { key: "year", label: "Årsmodell", type: "number" },
    { key: "fuel_type", label: "Drivmedel", type: "select", options: OPTIONS.fuelType },
    { key: "estimated_value", label: "Uppskattat värde", type: "number", step: "0.01" },
    { key: "loan_id", label: "Kopplat lån", type: "select", options: [["", "Inget lån"], ...loanOptions()] },
    { key: "insurance_policy_id", label: "Kopplad försäkring", type: "select", options: [["", "Ingen försäkring"], ...insuranceOptions()] },
    { key: "tax_monthly_estimate", label: "Skatt per månad", type: "number", step: "0.01" },
    { key: "fuel_monthly_estimate", label: "Bränsle/el per månad", type: "number", step: "0.01" },
    { key: "service_monthly_estimate", label: "Service per månad", type: "number", step: "0.01" },
    { key: "parking_monthly_estimate", label: "Parkering per månad", type: "number", step: "0.01" },
    { key: "note", label: "Anteckning", type: "textarea", full: true },
  ];
}

function assetFields() {
  return [
    { key: "type", label: "Typ av tillgång", type: "select", options: OPTIONS.assetType, required: true },
    { key: "label", label: "Namn eller etikett", type: "text", placeholder: "Till exempel Buffertsparande" },
    { key: "institution", label: "Bank eller aktör", type: "text", placeholder: "Till exempel Avanza eller Handelsbanken" },
    { key: "person_id", label: "Koppla till person", type: "select", options: [["", "Ingen särskild person"], ...peopleOptions()] },
    { key: "market_value", label: "Marknadsvärde", type: "number", step: "0.01" },
    { key: "liquid_value", label: "Likvid del", type: "number", step: "0.01" },
    { key: "pledged", label: "Pantsatt", type: "checkbox", default: false },
    { key: "note", label: "Anteckning", type: "textarea", full: true },
  ];
}

function housingFields() {
  return [
    { key: "label", label: "Namn på scenario", type: "text", required: true, placeholder: "Till exempel Lägenhet i Solna" },
    { key: "purchase_price", label: "Bostadspris", type: "number", step: "0.01" },
    { key: "down_payment", label: "Kontantinsats", type: "number", step: "0.01" },
    { key: "mortgage_needed", label: "Bolån", type: "number", step: "0.01" },
    { key: "rate_assumption", label: "Ränta (%)", type: "number", step: "0.01" },
    { key: "amortization_rate", label: "Amortering (%)", type: "number", step: "0.01" },
    { key: "monthly_fee_or_operating_cost", label: "Avgift eller drift per månad", type: "number", step: "0.01" },
    { key: "monthly_insurance", label: "Försäkring per månad", type: "number", step: "0.01" },
    { key: "monthly_property_cost_estimate", label: "Övriga boendekostnader per månad", type: "number", step: "0.01" },
    { key: "note", label: "Anteckning", type: "textarea", full: true },
  ];
}

function peopleOptions() {
  return peopleForHousehold().map((item) => [item.id, item.name]);
}

function assetOptions() {
  return assetsForHousehold().map((item) => [item.id, item.label || item.institution || optionLabel(OPTIONS.assetType, item.type)]);
}

function loanOptions() {
  return loansForHousehold().map((item) => [item.id, loanName(item.id)]);
}

function insuranceOptions() {
  return insuranceForHousehold().map((item) => [item.id, `${item.provider} · ${money(item.premium_monthly)}`]);
}

function vehicleMonthlyCost(item) {
  return sum([
    item.tax_monthly_estimate,
    item.fuel_monthly_estimate,
    item.service_monthly_estimate,
    item.parking_monthly_estimate,
    item.toll_monthly_estimate,
    item.tire_monthly_estimate,
  ]);
}

function stressScenarioTotal(current, evaluation) {
  const mortgage = Number(current.mortgage_needed || evaluation.mortgage_needed || 0);
  const rate = Number(current.rate_assumption || 0) + 2;
  const interest = mortgage * (rate / 100) / 12;
  return interest
    + Number(evaluation.monthly_amortization || 0)
    + Number(evaluation.monthly_operating_cost || 0)
    + Number(evaluation.monthly_insurance || 0)
    + Number(evaluation.monthly_property_cost_estimate || 0);
}

function sum(values) {
  return values.reduce((total, value) => total + Number(value || 0), 0);
}

async function deleteRecord(moduleKey, endpoint, item) {
  if (!item?.id) return;
  await request(`${endpoint}/${item.id}`, { method: "DELETE" });
  setEdit(moduleKey, null);
}

function serializeForm(form, fields) {
  const payload = {};
  fields.forEach((field) => {
    const element = form.elements[field.key];
    if (!element) return;

    if (field.type === "checkbox") {
      payload[field.key] = element.checked;
      return;
    }

    const rawValue = element.value.trim();
    if (!rawValue) return;

    if (field.type === "number") {
      payload[field.key] = Number(rawValue);
      return;
    }

    payload[field.key] = rawValue;
  });
  return payload;
}

async function saveHousehold(form) {
  const payload = serializeForm(form, householdFields());
  const current = currentEdit("household") || selectedHousehold();
  const result = current?.id
    ? await request(`/households/${current.id}`, { method: "PUT", body: JSON.stringify(payload) })
    : await request(API.households, { method: "POST", body: JSON.stringify(payload) });
  state.selectedHouseholdId = result.id;
  persistSelection();
  setEdit("household", result);
  await refreshAllData();
  render();
  showToast(current?.id ? "Hushållet sparades." : "Hushållet skapades.");
}

async function savePerson(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const payload = serializeForm(form, personFields());
  payload.household_id = state.selectedHouseholdId;
  const current = currentEdit("person");
  await saveByMode(current, API.persons, payload);
  setEdit("person", null);
  await refreshAllData();
  render();
  showToast(current?.id ? "Personen sparades." : "Personen lades till.");
}

async function saveIncome(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  if (!peopleForHousehold().length) throw new Error("Lägg först till minst en person.");
  const payload = serializeForm(form, incomeFields());
  const current = currentEdit("income");
  await saveByMode(current, API.incomes, payload);
  setEdit("income", null);
  await refreshAllData();
  render();
  showToast(current?.id ? "Inkomsten sparades." : "Inkomsten skapades.");
}

async function saveLoan(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const payload = serializeForm(form, loanFields());
  payload.household_id = state.selectedHouseholdId;
  const current = currentEdit("loan");
  await saveByMode(current, API.loans, payload);
  setEdit("loan", null);
  await refreshAllData();
  render();
  showToast(current?.id ? "Lånet sparades." : "Lånet skapades.");
}

async function saveRecurringCost(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const payload = serializeForm(form, recurringCostFields());
  payload.household_id = state.selectedHouseholdId;
  const current = currentEdit("cost");
  await saveByMode(current, API.recurringCosts, payload);
  setEdit("cost", null);
  await refreshAllData();
  render();
  showToast(current?.id ? "Kostnaden sparades." : "Kostnaden skapades.");
}

async function saveInsurance(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const payload = serializeForm(form, insuranceFields());
  payload.household_id = state.selectedHouseholdId;
  const current = currentEdit("insurance");
  await saveByMode(current, API.insurancePolicies, payload);
  setEdit("insurance", null);
  await refreshAllData();
  render();
  showToast(current?.id ? "Försäkringen sparades." : "Försäkringen skapades.");
}

async function saveSubscription(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const payload = serializeForm(form, subscriptionFields());
  payload.household_id = state.selectedHouseholdId;
  const current = currentEdit("subscription");
  await saveByMode(current, API.subscriptions, payload);
  setEdit("subscription", null);
  await refreshAllData();
  render();
  showToast(current?.id ? "Avtalet sparades." : "Avtalet skapades.");
}

async function saveVehicle(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const payload = serializeForm(form, vehicleFields());
  payload.household_id = state.selectedHouseholdId;
  const current = currentEdit("vehicle");
  await saveByMode(current, API.vehicles, payload);
  setEdit("vehicle", null);
  await refreshAllData();
  render();
  showToast(current?.id ? "Fordonet sparades." : "Fordonet skapades.");
}

async function saveAsset(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const payload = serializeForm(form, assetFields());
  payload.household_id = state.selectedHouseholdId;
  const current = currentEdit("asset");
  await saveByMode(current, API.assets, payload);
  setEdit("asset", null);
  await refreshAllData();
  render();
  showToast(current?.id ? "Tillgången sparades." : "Tillgången skapades.");
}

async function saveHousing(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const payload = serializeForm(form, housingFields());
  payload.household_id = state.selectedHouseholdId;
  const current = currentEdit("housing");
  const result = await saveByMode(current, API.housing, payload);
  setEdit("housing", result);
  await refreshAllData();
  await loadHousingEvaluation(result.id);
  render();
  showToast(current?.id ? "Boendescenariot sparades." : "Boendescenariot skapades.");
}

async function uploadDocument(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const formData = new FormData(form);
  formData.set("household_id", String(state.selectedHouseholdId));
  const document = await request("/documents/upload", { method: "POST", body: formData, headers: {} });
  form.reset();
  clearDocumentUploadPreview();
  state.ui.documentApplySummary = null;
  await refreshAllData();
  state.ui.selectedDocumentId = document.id;
  await loadSelectedDocumentWorkflow(document.id);
  render();
  const extraction = documentExtractionMeta(document.extraction_status);
  showToast(`Dokumentet laddades upp. ${extraction.label}.`);
}

async function saveByMode(current, endpoint, payload) {
  if (current?.id) {
    return request(`${endpoint}/${current.id}`, { method: "PUT", body: JSON.stringify(payload) });
  }
  return request(endpoint, { method: "POST", body: JSON.stringify(payload) });
}

async function scanOpportunities() {
  if (!selectedHousehold()) {
    showToast("Välj hushåll först.", "error");
    return;
  }
  try {
    await request(`/households/${state.selectedHouseholdId}/optimization_scan`, { method: "POST" });
    await refreshAllData();
    render();
    showToast("Förbättringsförslag uppdaterades.");
  } catch (error) {
    showToast(readError(error), "error");
  }
}

function moduleKeyForPage(pageKey) {
  const map = {
    incomes: "income",
    loans: "loan",
    costs: "cost",
    insurance: "insurance",
    subscriptions: "subscription",
    vehicles: "vehicle",
    assets: "asset",
    housing: "housing",
  };
  return map[pageKey];
}


function pageConfigByKey(key) {
  return navigationController.pageConfigByKey(key);
}

function pageConfigByPath(pathname) {
  return navigationController.pageConfigByPath(pathname);
}

function navigateTo(pageKey, historyMode = "push") {
  navigationController.navigateTo(pageKey, historyMode);
}

function bindElements() {
  els.nav = document.getElementById("mainNav");
  els.pageContent = document.getElementById("pageContent");
  els.householdSelect = document.getElementById("householdSelect");
  els.refreshButton = document.getElementById("refreshButton");
  els.toast = document.getElementById("toast");
  els.menuButton = document.getElementById("menuButton");
  els.closeSidebarButton = document.getElementById("closeSidebarButton");
  els.sidebar = document.getElementById("sidebar");
  els.sidebarOverlay = document.getElementById("sidebarOverlay");
  els.assistantNav = document.getElementById("assistantNav");
  els.dateStamp = document.getElementById("dateStamp");
}

function bindBaseEvents() {
  els.nav.addEventListener("click", handlePageClick);
  els.assistantNav.addEventListener("click", handlePageClick);
  els.pageContent.addEventListener("click", handlePageClick);
  els.pageContent.addEventListener("submit", handlePageSubmit);
  els.pageContent.addEventListener("input", handlePageInput);
  els.pageContent.addEventListener("change", handlePageInput);

  els.refreshButton.addEventListener("click", async () => {
    await refreshAllData();
    render();
    showToast("Data uppdaterades.");
  });

  els.householdSelect.addEventListener("change", async (event) => {
    state.selectedHouseholdId = Number(event.target.value) || null;
    persistSelection();
    clearEdits();
    clearDocumentUploadPreview();
    state.ui.documentApplySummary = null;
    assistantWorkspace.resetAssistantWorkspaceState(Boolean(state.selectedHouseholdId));
    state.ui.ingestInput = "";
    state.ui.ingestDocumentId = null;
    state.ui.ingestResult = null;
    state.ui.documentDraftSelections = {};
    state.ui.selectedDocumentWorkflow = null;
    state.ui.documentApplySummary = null;
    await ensureSummaryLoaded();
    await assistantWorkspace.loadAssistantWorkspace();
    render();
  });

  if (els.menuButton) {
    els.menuButton.addEventListener("click", () => toggleSidebar(true));
  }
  if (els.closeSidebarButton) {
    els.closeSidebarButton.addEventListener("click", () => toggleSidebar(false));
  }
  if (els.sidebarOverlay) {
    els.sidebarOverlay.addEventListener("click", () => toggleSidebar(false));
  }

  window.addEventListener("popstate", () => {
    state.page = pageConfigByPath(location.pathname).key;
    persistPage();
    render();
    if (state.page === "assistant" && state.selectedHouseholdId) {
      void assistantWorkspace.loadAssistantWorkspace({ renderAfter: true });
    }
  });
}

function toggleSidebar(open) {
  sidebarController.toggleSidebar(open);
}

async function refreshAllData() {
  const entries = await Promise.all([
    request(`${API.households}?skip=0&limit=200`).then((value) => ["households", value]),
    request(`${API.persons}?skip=0&limit=200`).then((value) => ["persons", value]),
    request(`${API.incomes}?skip=0&limit=200`).then((value) => ["incomes", value]),
    request(`${API.recurringCosts}?skip=0&limit=200`).then((value) => ["recurringCosts", value]),
    request(`${API.loans}?skip=0&limit=200`).then((value) => ["loans", value]),
    request(`${API.subscriptions}?skip=0&limit=200`).then((value) => ["subscriptions", value]),
    request(`${API.insurancePolicies}?skip=0&limit=200`).then((value) => ["insurancePolicies", value]),
    request(`${API.vehicles}?skip=0&limit=200`).then((value) => ["vehicles", value]),
    request(`${API.assets}?skip=0&limit=200`).then((value) => ["assets", value]),
    request(`${API.housing}?skip=0&limit=200`).then((value) => ["housing", value]),
    request(`${API.documents}?skip=0&limit=200`).then((value) => ["documents", value]),
    request(`${API.opportunities}?skip=0&limit=200`).then((value) => ["opportunities", value]),
    request(`${API.drafts}?skip=0&limit=200`).then((value) => ["drafts", value]),
    request(`${API.scenarios}?skip=0&limit=200`).then((value) => ["scenarios", value]),
    request(`${API.scenarioResults}?skip=0&limit=200`).then((value) => ["scenarioResults", value]),
    request(`${API.reports}?skip=0&limit=200`).then((value) => ["reports", value]),
  ]);

  state.data = { ...state.data, ...Object.fromEntries(entries) };
  if (!selectedHousehold() && households().length) {
    state.selectedHouseholdId = households()[0].id;
    persistSelection();
  }
  await ensureSummaryLoaded();
  if (state.selectedHouseholdId) {
    try {
      state.data.merchantAliases = await request(`/households/${state.selectedHouseholdId}/merchant_aliases`);
    } catch (_err) {
      state.data.merchantAliases = [];
    }
  }
  const visibleDocumentIds = documentsForHousehold().map((item) => item.id);
  if (state.ui.selectedDocumentId && !visibleDocumentIds.includes(state.ui.selectedDocumentId)) {
    state.ui.selectedDocumentId = null;
    state.ui.selectedDocumentWorkflow = null;
  }
  if (!state.ui.selectedDocumentId && visibleDocumentIds.length) {
    state.ui.selectedDocumentId = visibleDocumentIds[0];
    state.ui.documentApplySummary = null;
  }
  await loadSelectedDocumentWorkflow();
  await assistantWorkspace.loadAssistantWorkspace();
}

async function loadAssistantThread({ renderAfter = false } = {}) {
  return assistantWorkspace.loadAssistantThread({ renderAfter });
}

async function loadAssistantAnalysis({ renderAfter = false } = {}) {
  return assistantWorkspace.loadAssistantAnalysis({ renderAfter });
}

async function loadAssistantWorkspace({ renderAfter = false } = {}) {
  return assistantWorkspace.loadAssistantWorkspace({ renderAfter });
}

function render() {
  if (!localStorage.getItem("he_session_token")) {
    document.body.classList.add("auth-mode");
    els.pageContent.innerHTML = renderAuthPage();
    return;
  }
  document.body.classList.remove("auth-mode");

  const routePage = pageConfigByPath(location.pathname);
  if (routePage.key !== state.page) {
    state.page = routePage.key;
    persistPage();
  }
  renderHouseholdSelect();
  renderNav();
  renderTopbar();
  els.pageContent.innerHTML = renderPage();
  if (state.page === "assistant") {
    assistantWorkspace.updateAssistantLogBottomOffset();
  }
  toggleSidebar(false);
}

function renderTopbar() {
  navigationController.renderTopbar(currentMonthLabel);
}

function renderNav() {
  navigationController.renderNav(selectedHousehold);
}

function navGlyph(key) {
  const icons = {
    overview: "◫",
    register: "✎",
    household: "⌂",
    persons: "☺",
    incomes: "₿",
    loans: "¤",
    costs: "≈",
    subscriptions: "☰",
    insurance: "⛨",
    vehicles: "▣",
    assets: "◌",
    housing: "▤",
    documents: "☷",
    improvements: "✷",
    scenarios: "△",
    reports: "☱",
    assistant: "✦",
  };
  return icons[key] || "•";
}

function renderPage() {
  switch (state.page) {
    case "overview":
      return renderOverviewPageV2();
    case "register":
      return renderRegisterPage();
    case "household":
      return renderHouseholdPageV2();
    case "persons":
      return renderPersonsPage();
    case "incomes":
      return renderIncomesPage();
    case "loans":
      return renderLoansPage();
    case "costs":
      return renderRecurringCostsPageV2();
    case "subscriptions":
      return renderSubscriptionsPageV2();
    case "insurance":
      return renderInsurancePageV2();
    case "vehicles":
      return renderVehiclesPageV2();
    case "assets":
      return renderAssetsPageV2();
    case "housing":
      return renderHousingPageV2();
    case "documents":
      return renderDocumentsPageV2();
    case "improvements":
      return renderImprovementsPageV2();
    case "scenarios":
      return renderScenariosPageV2();
    case "reports":
      return renderReportsPageV2();
    case "assistant":
      return renderAssistantPageV2();
    default:
      return renderOverviewPageV2();
  }
}

function renderPageHeader(title, description, actions = "") {
  const activePage = PAGES.find((page) => page.key === state.page)?.label || "Ekonomi";
  return `
    <section class="page-head">
      <div class="page-head-copy">
        <span class="page-eyebrow">${escapeHtml(activePage)}</span>
        <h2>${escapeHtml(title)}</h2>
        <p class="page-subtitle">${escapeHtml(description)}</p>
      </div>
      <div class="top-actions">${actions}</div>
    </section>
  `;
}

function renderStatCard(label, value, note = "") {
  return `
    <article class="stats-card metric-card">
      <label class="metric-label">${escapeHtml(label)}</label>
      <strong class="metric-value">${escapeHtml(String(value))}</strong>
      ${note ? `<span class="metric-note">${escapeHtml(note)}</span>` : ""}
    </article>
  `;
}

function currentMonthLabel() {
  const today = new Intl.DateTimeFormat("sv-SE", { year: "numeric", month: "long" }).format(new Date());
  return today.charAt(0).toUpperCase() + today.slice(1);
}

function ownershipText(personId, sharedLabel = "Gemensamt") {
  return personId ? `Personligt · ${personName(personId)}` : sharedLabel;
}

function ownershipBadge(personId, sharedLabel = "Gemensamt") {
  return `<span class="badge ${personId ? "info" : "muted"}">${escapeHtml(ownershipText(personId, sharedLabel))}</span>`;
}

function canonicalBadge(label = "Verifierat") {
  return `<span class="badge success">${escapeHtml(label)}</span>`;
}

function reviewDrafts(items = []) {
  return items.filter((item) => ["pending_review", "deferred", "apply_failed"].includes(String(item.status || "")));
}

function isApproximateCost(item) {
  const basis = `${item?.note || ""} ${item?.vendor || ""}`.toLowerCase();
  return basis.includes("approx") || basis.includes("ungef") || basis.includes("osaker") || basis.includes("approximer");
}

function renderOverviewPageV2() {
  const household = selectedHousehold();
  if (!household) {
    return `
      <section class="page-wrap">
        ${renderPageHeader("Översikt", "Börja med att skapa ett hushåll så att overview, dokument och assistent kan bindas till riktiga dataflöden.")}
        <article class="panel">
          <div class="empty-state">
            <p>Inget hushåll är valt ännu.</p>
            <div class="actions-row">
              <button class="primary" type="button" data-route="/hushall">Skapa hushåll</button>
              <button class="ghost" type="button" data-route="/registrera">Guidad registrering</button>
            </div>
          </div>
        </article>
      </section>
    `;
  }

  const summary = selectedSummary() || {};
  const opportunities = opportunitiesForHousehold().slice().sort((a, b) => Number(b.estimated_monthly_saving || 0) - Number(a.estimated_monthly_saving || 0)).slice(0, 3);
  const subscriptions = subscriptionsForHousehold().slice().sort((a, b) => Number(b.current_monthly_cost || 0) - Number(a.current_monthly_cost || 0)).slice(0, 4);
  const drafts = draftsForHousehold();
  const reviewQueue = reviewDrafts(drafts);
  const reports = reportsForHousehold().slice().sort((a, b) => new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime()).slice(0, 2);
  const documents = documentsForHousehold().slice(0, 3);
  const housingItem = recurringCostsForHousehold().filter((item) => isHousingRecurringCategory(item.category)).sort((a, b) => amountToMonthlyCost(b) - amountToMonthlyCost(a))[0] || null;
  const summaryWarnings = [
    ...(summary.risk_signals || []).map((sig) => sig.message_sv).filter(Boolean),
    ...warningsFromSummary(summary),
  ].slice(0, 4);
  const nextSteps = onboardingSteps().slice(0, 3);
  return `
    <section class="page-wrap page-overview">
      ${renderPageHeader("Översikt", `Verifierad nulägesbild för ${household.name}. Backend äger ekonomimatematiken, den här sidan fokuserar på status, ägande och nästa steg.`, `
        <button class="ghost" type="button" data-route="/abonnemang">Granska avtal</button>
        <button class="primary" type="button" data-route="/ekonomiassistent">Öppna assistenten</button>
      `)}
      <article class="panel overview-hero">
        <div class="overview-hero-copy">
          <span class="section-eyebrow">Månadsöversikt</span>
          <h3>${escapeHtml(household.name)}</h3>
          <p class="muted">Verkliga sammanfattningssiffror för ${escapeHtml(currentMonthLabel().toLowerCase())}. Osäkra poster visas separat och boende ligger kvar som en samlad hushållspost.</p>
        </div>
        <div class="overview-month-chip">${escapeHtml(currentMonthLabel())}</div>
      </article>
      <section class="stats-grid overview-kpi-grid">
        ${renderStatCard("Nettoinkomst / månad", money(summary.monthly_income), `${summary.counts?.income_sources || 0} inkomstkällor`)}
        ${renderStatCard("Totala kostnader / månad", money(summary.monthly_total_expenses), `${summary.counts?.recurring_costs || 0} kostnader, ${summary.counts?.subscription_contracts || 0} avtal`)}
        ${renderStatCard("Kvar efter kostnader", money(summary.monthly_net_cashflow), summary.monthly_net_cashflow >= 0 ? "Positivt kassaflöde" : "Negativt kassaflöde")}
        ${renderStatCard("Nettoförmögenhet", money(summary.net_worth_estimate), `${money(summary.asset_market_value)} tillgångar minus ${money(summary.loan_balance_total)} lån`)}
      </section>
      <section class="overview-focus-grid">
        <article class="panel overview-housing-panel">
          <div class="record-title-row">
            <div>
              <span class="section-eyebrow">Boende</span>
              <h3>${escapeHtml(housingItem?.vendor || "Samlad hushållspost")}</h3>
              <p class="muted">Boende presenteras fortsatt som en egen hushållspost och får inte blandas ihop med vardagskonsumtion eller interna överföringar.</p>
            </div>
            <div class="overview-hero-value">${money(housingItem ? amountToMonthlyCost(housingItem) : 0)}</div>
          </div>
          <div class="badge-row">
            ${housingItem ? ownershipBadge(housingItem.person_id, "Gemensamt") : `<span class="badge muted">Ingen aktiv post</span>`}
            ${housingItem && isApproximateCost(housingItem) ? `<span class="badge warning">Approximerad nivå</span>` : ""}
            ${housingItem ? canonicalBadge("Verifierad hushållspost") : ""}
          </div>
          ${housingItem?.note ? `<p class="muted">${escapeHtml(housingItem.note)}</p>` : `<p class="muted">Aktiv boendekostnad visas separat så att overview och assistent kan tala sant om hushållets nuläge.</p>`}
        </article>
        <article class="panel overview-status-panel">
          <span class="section-eyebrow">Osäkert och att hantera</span>
          <h3>Separat från verifierad ekonomi</h3>
          <div class="overview-status-stack">
            <article class="overview-status-card">
              <strong>${reviewQueue.length}</strong>
              <span>reviewutkast som fortfarande kräver beslut</span>
            </article>
            <article class="overview-status-card">
              <strong>${dueForReviewCount()}</strong>
              <span>avtal med nära granskningsdatum</span>
            </article>
            <article class="overview-status-card">
              <strong>${documents.length}</strong>
              <span>dokument i hushållets arbetsyta</span>
            </article>
          </div>
          ${summaryWarnings.length ? `
            <ul class="summary-list">
              ${summaryWarnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
            </ul>
          ` : `<p class="muted">Inga extra risksignaler just nu. Verifierad nulägesbild är lugnare, men reviewkö och dokumentflöde är fortfarande separata arbetsytor.</p>`}
          <div class="actions-row">
            <button class="ghost compact" type="button" data-route="/dokument">Öppna dokument</button>
            <button class="primary compact" type="button" data-route="/ekonomiassistent">Fråga assistenten</button>
          </div>
        </article>
      </section>
      <section class="overview-focus-grid">
        <article class="panel">
          <span class="section-eyebrow">Nästa steg</span>
          <h3>Arbetsyta för vardagen</h3>
          <div class="overview-action-list">
            ${nextSteps.map((step, index) => `
              <article class="record-card action-card">
                <div class="record-title-row">
                  <div>
                    <span class="badge info">Steg ${index + 1}</span>
                    <h4 class="record-title">${escapeHtml(step.title)}</h4>
                  </div>
                  <button class="ghost compact" type="button" data-nav="${step.page}">Öppna</button>
                </div>
                <p class="muted">${escapeHtml(step.text)}</p>
              </article>
            `).join("") || `<div class="empty-state"><p>Grunden är på plats och hushållet är redo för löpande underhåll.</p></div>`}
          </div>
        </article>
        <article class="panel">
          <span class="section-eyebrow">Verifierade avtal</span>
          <h3>Abonnemang att hålla koll på</h3>
          <div class="record-grid">
            ${subscriptions.map((item) => renderSubscriptionRowV2(item)).join("") || `<div class="empty-state"><p>Det finns inga abonnemang registrerade än.</p></div>`}
          </div>
        </article>
      </section>
      <section class="overview-focus-grid">
        <article class="panel">
          <span class="section-eyebrow">Dokumentflöde</span>
          <h3>Senaste underlag och arbetsläge</h3>
          <div class="record-grid">
            ${documents.map((item) => renderDocumentRowV2(item)).join("") || `<div class="empty-state"><p>Inga dokument uppladdade än.</p></div>`}
          </div>
        </article>
        <article class="panel">
          <span class="section-eyebrow">Rapporter</span>
          <h3>Kanoniska snapshots</h3>
          <div class="record-grid">
            ${reports.map((item) => renderReportRowV2(item)).join("") || `<div class="empty-state"><p>Inga sparade rapporter än.</p></div>`}
          </div>
          <div class="record-grid" style="margin-top:16px;">
            ${opportunities.length ? opportunities.map((item) => renderOpportunityCardV2(item)).join("") : ""}
          </div>
        </article>
      </section>
    </section>
  `;
}

function renderEventCard(label, value, tone) {
  return `<article class="record-card"><div class="badge ${tone}">${escapeHtml(value)}</div><h4 class="record-title">${escapeHtml(label)}</h4></article>`;
}

function renderHouseholdPageV2() {
  const householdsList = households();
  const household = selectedHousehold();
  return `
    <section class="page-wrap">
      ${renderPageHeader("Hushåll", "Er gemensamma ekonomi", `
        <button class="primary" type="button" data-action="new-household">Nytt hushåll</button>
      `)}
      <section class="split-layout">
        <article class="panel">
          <span class="section-eyebrow">Hushåll</span>
          <h3>${household ? escapeHtml(household.name) : "Skapa första hushållet"}</h3>
          <div class="record-grid">
            ${householdsList.map((item) => `
              <article class="record-card">
                <div class="record-title-row">
                  <div>
                    <h4 class="record-title">${escapeHtml(item.name)}</h4>
                    <p class="muted">${escapeHtml(item.primary_country || "SE")} · ${escapeHtml(item.currency || "SEK")}</p>
                  </div>
                  <div class="actions-row">
                    <button class="ghost compact" type="button" data-select-household="${item.id}">Välj</button>
                    <button class="ghost compact" type="button" data-edit-household="${item.id}">Redigera</button>
                  </div>
                </div>
              </article>
            `).join("") || `<div class="empty-state"><p>Inga hushåll finns ännu.</p></div>`}
          </div>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Hushållets grund</span>
          <h3>${household ? "Redigera hushåll" : "Skapa hushåll"}</h3>
          ${renderForm("householdForm", householdFields(), currentEdit("household") || household || {}, {
            submitLabel: household ? "Spara hushåll" : "Skapa hushåll",
            canDelete: Boolean((currentEdit("household") || household)?.id),
            deleteLabel: "Ta bort hushåll",
          })}
        </article>
      </section>
    </section>
  `;
}

function renderPersonsPage() {
  const items = peopleForHousehold();
  return `
    <section class="page-wrap">
      ${renderPageHeader("Personer", "Personerna i ert hushåll", `<button class="primary" type="button" data-action="new-record" data-module="person">Lägg till person</button>`)}
      <section class="split-layout">
        <article class="panel">
          <div class="record-grid two">
            ${items.map((item) => `
              <article class="record-card">
                <div class="record-title-row">
                  <div>
                    <h4 class="record-title">${escapeHtml(item.name)}</h4>
                    <p class="muted">${optionLabel(OPTIONS.role, item.role)} · ${item.active ? "Aktiv" : "Vilande"}</p>
                  </div>
                  <button class="ghost compact" type="button" data-edit="person" data-id="${item.id}">Redigera</button>
                </div>
              </article>
            `).join("") || `<div class="empty-state"><p>Inga personer registrerade ännu.</p></div>`}
          </div>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Person</span>
          <h3>${currentEdit("person")?.id ? "Redigera person" : "Lägg till person"}</h3>
          ${selectedHousehold() ? renderForm("personForm", personFields(), currentEdit("person") || {}, {
            submitLabel: currentEdit("person")?.id ? "Spara person" : "Lägg till person",
            canDelete: Boolean(currentEdit("person")?.id),
            deleteLabel: "Ta bort person",
          }) : `<div class="empty-state"><p>Välj hushåll först.</p></div>`}
        </article>
      </section>
    </section>
  `;
}

function renderIncomesPage() {
  const items = incomesForHousehold();
  return `
    <section class="page-wrap">
      ${renderPageHeader("Inkomster", "Alla inkomstkällor i hushållet", `<button class="primary" type="button" data-action="new-record" data-module="income">Lägg till inkomst</button>`)}
      <section class="stats-grid three">
        ${renderStatCard("Inkomstkällor", items.length)}
        ${renderStatCard("Netto / månad", money(selectedSummary()?.monthly_income_net || 0))}
        ${renderStatCard("Poster med netto", items.filter((item) => item.net_amount != null).length)}
      </section>
      <section class="split-layout">
        <article class="table-card">
          <table class="data-table">
            <thead>
              <tr>
                <th>Person</th>
                <th>Typ</th>
                <th class="align-right">Netto / mån</th>
                <th class="align-right">Brutto</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${items.map((item) => `
                <tr>
                  <td>${escapeHtml(personName(item.person_id))}</td>
                  <td>${escapeHtml(optionLabel(OPTIONS.incomeType, item.type))}</td>
                  <td class="align-right">${money(item.net_amount || 0)}</td>
                  <td class="align-right">${money(item.gross_amount || 0)}</td>
                  <td><span class="badge ${item.verified ? "success" : "muted"}">${item.verified ? "Verifierad" : "Ej verifierad"}</span></td>
                  <td class="align-right"><button class="ghost compact" type="button" data-edit="income" data-id="${item.id}">Redigera</button></td>
                </tr>
              `).join("") || `<tr><td colspan="6"><div class="empty-state"><p>Inga inkomster registrerade ännu.</p></div></td></tr>`}
            </tbody>
          </table>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Inkomst</span>
          <h3>${currentEdit("income")?.id ? "Redigera inkomst" : "Lägg till inkomst"}</h3>
          ${renderForm("incomeForm", incomeFields(), currentEdit("income") || {}, {
            submitLabel: currentEdit("income")?.id ? "Spara inkomst" : "Lägg till inkomst",
            canDelete: Boolean(currentEdit("income")?.id),
            deleteLabel: "Ta bort inkomst",
          })}
        </article>
      </section>
    </section>
  `;
}

function renderLoansPage() {
  const items = loansForHousehold();
  return `
    <section class="page-wrap">
      ${renderPageHeader("Lån", "Verifierade lån och krediter i hushållet", `<button class="primary" type="button" data-action="new-record" data-module="loan">Lägg till lån</button>`)}
      <section class="stats-grid three">
        ${renderStatCard("Lån", items.length)}
        ${renderStatCard("Total skuld", money(sum(items.map((item) => item.current_balance))))}
        ${renderStatCard("Månadskostnad", money(sum(items.map((item) => item.required_monthly_payment))))}
      </section>
      <section class="split-layout">
        <article class="panel">
          <div class="section-head">
            <div>
              <span class="section-eyebrow">Lånlista</span>
              <h3>${items.length ? `${items.length} poster i nuläget` : "Lägg till första lånet"}</h3>
              <p class="meta-text">Kanoniska lån visas här med ägarskap, månadskostnad och skuld. Eventuella dokumentutkast granskas separat under Dokument.</p>
            </div>
          </div>
          <div class="record-grid">
            ${items.map((item) => `
              <article class="record-card ledger-card">
                <div class="ledger-row">
                  <div class="ledger-icon">${escapeHtml(String(item.lender || optionLabel(OPTIONS.loanType, item.type)).charAt(0).toUpperCase())}</div>
                  <div class="ledger-copy">
                    <div class="ledger-title-row">
                      <h4 class="record-title">${escapeHtml(item.lender || optionLabel(OPTIONS.loanType, item.type))}</h4>
                      ${canonicalBadge()}
                    </div>
                    <p class="muted">${escapeHtml(item.purpose || optionLabel(OPTIONS.loanType, item.type))}</p>
                  </div>
                  <div class="ledger-aside">
                    <div class="record-value">${money(item.required_monthly_payment)}</div>
                    <button class="ghost compact" type="button" data-edit="loan" data-id="${item.id}">Redigera</button>
                  </div>
                </div>
                <div class="badge-row">
                  ${ownershipBadge(item.person_id)}
                  <span class="badge">${escapeHtml(optionLabel(OPTIONS.loanStatus, item.status))}</span>
                  <span class="badge muted">${escapeHtml(optionLabel(OPTIONS.loanType, item.type))}</span>
                </div>
                <div class="detail-grid four">
                  ${detailCell("Skuld", money(item.current_balance))}
                  ${detailCell("Ränta", `${number(item.nominal_rate, 2)} %`)}
                  ${detailCell("Månadskostnad", money(item.required_monthly_payment))}
                  ${detailCell("Månader kvar", item.remaining_term_months || "Ej angivet")}
                </div>
              </article>
            `).join("") || `<div class="empty-state"><p>Inga lån registrerade ännu.</p></div>`}
          </div>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Lån</span>
          <h3>${currentEdit("loan")?.id ? "Redigera lån" : "Lägg till lån"}</h3>
          ${renderForm("loanForm", loanFields(), currentEdit("loan") || {}, {
            submitLabel: currentEdit("loan")?.id ? "Spara lån" : "Lägg till lån",
            canDelete: Boolean(currentEdit("loan")?.id),
            deleteLabel: "Ta bort lån",
          })}
        </article>
      </section>
    </section>
  `;
}

function renderRecurringCostsPageV2() {
  const items = recurringCostsForHousehold();
  const housingItem = items
    .filter((item) => isHousingRecurringCategory(item.category))
    .sort((a, b) => amountToMonthlyCost(b) - amountToMonthlyCost(a))[0] || null;
  const listItems = housingItem ? items.filter((item) => item.id !== housingItem.id) : items;
  const monthlyTotal = sum(items.map((item) => amountToMonthlyCost(item)));
  const mandatoryCount = items.filter((item) => item.mandatory !== false).length;
  const reducibleMonthly = sum(
    items
      .filter((item) => ["negotiable", "reducible", "discretionary"].includes(String(item.controllability)))
      .map((item) => amountToMonthlyCost(item))
  );
  return `
    <section class="page-wrap">
      ${renderPageHeader(
        "Kostnader",
        "Samlad hushållskostnad, boende och andra återkommande poster utan lokal omräkning i frontend.",
        `<button class="primary" type="button" data-action="new-record" data-module="cost">Lägg till kostnad</button>`
      )}
      ${housingItem ? `
        <article class="panel housing-hero">
          <div class="record-title-row">
            <div>
              <span class="section-eyebrow">Boende som hushållspost</span>
              <h3>${escapeHtml(housingItem.vendor || "Boende")}</h3>
              <p class="muted">Boende ligger kvar som en enda aktiv hushållspost. Den ska inte delas upp till privat konsumtion eller återföras som huskonto.</p>
            </div>
            <div class="overview-hero-value">${money(amountToMonthlyCost(housingItem))}</div>
          </div>
          <div class="badge-row">
            ${ownershipBadge(housingItem.person_id)}
            ${canonicalBadge("Aktiv post")}
            ${isApproximateCost(housingItem) ? `<span class="badge warning">Approximerad nivå</span>` : ""}
          </div>
          ${housingItem.note ? `<p class="muted">${escapeHtml(housingItem.note)}</p>` : `<p class="muted">Beloppet visas separat för att ge en sanningsbunden bild av hushållets boendeåtagande.</p>`}
        </article>
      ` : ""}
      <section class="stats-grid">
        ${renderStatCard("Poster", items.length)}
        ${renderStatCard("Total kostnad / månad", money(monthlyTotal))}
        ${renderStatCard("Nödvändiga poster", mandatoryCount)}
        ${renderStatCard("Möjliga att påverka", money(reducibleMonthly))}
      </section>
      <section class="split-layout">
        <article class="panel">
          <div class="section-head">
            <div>
              <span class="section-eyebrow">Löpande kostnader</span>
              <h3>${listItems.length ? `${listItems.length} poster utom boende` : housingItem ? "Boende är enda aktiva posten just nu" : "Lägg till första återkommande kostnaden"}</h3>
              <p class="meta-text">Här ligger avbetalningar, familjeposter och övriga återkommande kostnader. Försäkringar har fortsatt en egen modul.</p>
            </div>
          </div>
          <div class="record-grid">
            ${(listItems.length ? listItems : (!housingItem ? items : [])).map((item) => renderRecurringCostCard(item)).join("") || `<div class="empty-state"><p>Inga andra återkommande kostnader registrerade än.</p></div>`}
          </div>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Kostnad</span>
          <h3>${currentEdit("cost")?.id ? "Redigera återkommande kostnad" : "Lägg till återkommande kostnad"}</h3>
          <p class="muted">Backend fortsätter äga summeringen. Här registrerar ni bara posten, inte själva ekonomimatematiken.</p>
          ${renderForm("costForm", recurringCostFields(), recurringCostFormValue(currentEdit("cost") || {}), {
            submitLabel: currentEdit("cost")?.id ? "Spara kostnad" : "Lägg till kostnad",
            canDelete: Boolean(currentEdit("cost")?.id),
            deleteLabel: "Ta bort kostnad",
          })}
        </article>
      </section>
    </section>
  `;
}

function renderSubscriptionsPageV2() {
  const items = subscriptionsForHousehold();
  return `
    <section class="page-wrap">
      ${renderPageHeader("Abonnemang och avtal", "Verifierade löpande avtal med tydlig ägarskap, granskningsdatum och prisnivå.", `<button class="primary" type="button" data-action="new-record" data-module="subscription">Lägg till abonnemang</button>`)}
      <section class="stats-grid">
        ${renderStatCard("Antal avtal", items.length)}
        ${renderStatCard("Total kostnad / månad", money(sum(items.map((item) => item.current_monthly_cost))))}
        ${renderStatCard("Att granska", dueForReviewCount())}
        ${renderStatCard("Möjlig prisökning", money(sum(items.map((item) => Math.max(0, Number(item.ordinary_cost || 0) - Number(item.current_monthly_cost || 0))))))}
      </section>
      <section class="split-layout">
        <article class="panel">
          <div class="section-head">
            <div>
              <span class="section-eyebrow">Avtalslista</span>
              <h3>${items.length ? `${items.length} kanoniska avtal` : "Lägg till första avtalet"}</h3>
              <p class="meta-text">Verifierade avtal visas med ägarskap, prisnivå och granskningsstatus.</p>
            </div>
          </div>
          <div class="record-grid">
            ${items.map((item) => renderSubscriptionRowV2(item)).join("") || `<div class="empty-state"><p>Inga abonnemang registrerade ännu.</p></div>`}
          </div>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Avtal</span>
          <h3>${currentEdit("subscription")?.id ? "Redigera avtal" : "Lägg till avtal"}</h3>
          ${renderForm("subscriptionForm", subscriptionFields(), currentEdit("subscription") || {}, {
            submitLabel: currentEdit("subscription")?.id ? "Spara avtal" : "Lägg till avtal",
            canDelete: Boolean(currentEdit("subscription")?.id),
            deleteLabel: "Ta bort avtal",
          })}
        </article>
      </section>
    </section>
  `;
}

function renderSubscriptionRowV2(item) {
  return `
    <article class="record-card ledger-card">
      <div class="ledger-row">
        <div class="ledger-icon">${escapeHtml(String(item.provider || "?").charAt(0).toUpperCase())}</div>
        <div class="ledger-copy">
          <div class="ledger-title-row">
            <h4 class="record-title">${escapeHtml(item.provider)}${item.product_name ? ` · ${escapeHtml(item.product_name)}` : ""}</h4>
            ${canonicalBadge()}
          </div>
          <p class="muted">${escapeHtml(optionLabel(OPTIONS.subscriptionCategory, item.category))}${item.next_review_at ? ` · nästa granskning ${dateLabel(item.next_review_at)}` : ""}</p>
        </div>
        <div class="ledger-aside">
          <span class="record-value">${money(item.current_monthly_cost)}</span>
          <button class="ghost compact" type="button" data-edit="subscription" data-id="${item.id}">Redigera</button>
        </div>
      </div>
      <div class="badge-row">
        ${ownershipBadge(item.person_id)}
        <span class="badge">${escapeHtml(optionLabel(OPTIONS.subscriptionCriticality, item.household_criticality))}</span>
        ${item.ordinary_cost ? `<span class="badge warning">Ordinarie pris ${money(item.ordinary_cost)}</span>` : ""}
        ${item.binding_end_date ? `<span class="badge muted">Bindning till ${dateLabel(item.binding_end_date)}</span>` : ""}
      </div>
    </article>
  `;
}

function renderInsurancePageV2() {
  const items = insuranceForHousehold();
  return `
    <section class="page-wrap">
      ${renderPageHeader("Försäkringar", "Alla försäkringar i hushållet", `<button class="primary" type="button" data-action="new-record" data-module="insurance">Lägg till försäkring</button>`)}
      <section class="split-layout">
        <article class="panel">
          <div class="record-grid two">
            ${items.map((item) => `
              <article class="record-card">
                <div class="record-title-row">
                  <div>
                    <h4 class="record-title">${escapeHtml(item.provider)}</h4>
                    <p class="muted">${escapeHtml(optionLabel(OPTIONS.insuranceType, item.type))}</p>
                  </div>
                  <button class="ghost compact" type="button" data-edit="insurance" data-id="${item.id}">Redigera</button>
                </div>
                <div class="detail-grid">
                  ${detailCell("Premie", money(item.premium_monthly))}
                  ${detailCell("Självrisk", money(item.deductible))}
                  ${detailCell("Förnyelse", dateLabel(item.renewal_date))}
                  ${detailCell("Täckning", item.coverage_tier || "Ej angiven")}
                </div>
              </article>
            `).join("") || `<div class="empty-state"><p>Inga försäkringar registrerade ännu.</p></div>`}
          </div>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Försäkring</span>
          <h3>${currentEdit("insurance")?.id ? "Redigera försäkring" : "Lägg till försäkring"}</h3>
          ${renderForm("insuranceForm", insuranceFields(), currentEdit("insurance") || {}, {
            submitLabel: currentEdit("insurance")?.id ? "Spara försäkring" : "Lägg till försäkring",
            canDelete: Boolean(currentEdit("insurance")?.id),
            deleteLabel: "Ta bort försäkring",
          })}
        </article>
      </section>
    </section>
  `;
}

function renderVehiclesPageV2() {
  const items = vehiclesForHousehold();
  return `
    <section class="page-wrap">
      ${renderPageHeader("Fordon", "Fordon i hushållet och deras kostnader", `<button class="primary" type="button" data-action="new-record" data-module="vehicle">Lägg till fordon</button>`)}
      <section class="split-layout">
        <article class="panel">
          <div class="record-grid">
            ${items.map((item) => `
              <article class="record-card">
                <div class="record-title-row">
                  <div>
                    <h4 class="record-title">${escapeHtml([item.make, item.model, item.year].filter(Boolean).join(" ") || "Fordon")}</h4>
                    <p class="muted">${item.owner_person_id ? escapeHtml(personName(item.owner_person_id)) : "Ingen specifik ägare"}</p>
                  </div>
                  <button class="ghost compact" type="button" data-edit="vehicle" data-id="${item.id}">Redigera</button>
                </div>
                <div class="detail-grid four">
                  ${detailCell("Lån", item.loan_id ? loanName(item.loan_id) : "Inget")}
                  ${detailCell("Försäkring", item.insurance_policy_id ? policyName(item.insurance_policy_id) : "Ingen")}
                  ${detailCell("Bränsle", money(item.fuel_monthly_estimate))}
                  ${detailCell("Total / månad", money(vehicleMonthlyCost(item)))}
                </div>
              </article>
            `).join("") || `<div class="empty-state"><p>Inga fordon registrerade ännu.</p></div>`}
          </div>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Fordon</span>
          <h3>${currentEdit("vehicle")?.id ? "Redigera fordon" : "Lägg till fordon"}</h3>
          ${renderForm("vehicleForm", vehicleFields(), currentEdit("vehicle") || {}, {
            submitLabel: currentEdit("vehicle")?.id ? "Spara fordon" : "Lägg till fordon",
            canDelete: Boolean(currentEdit("vehicle")?.id),
            deleteLabel: "Ta bort fordon",
          })}
        </article>
      </section>
    </section>
  `;
}

function renderAssetsPageV2() {
  const items = assetsForHousehold();
  return `
    <section class="page-wrap">
      ${renderPageHeader("Tillgångar", "Sparande, investeringar och andra tillgångar", `<button class="primary" type="button" data-action="new-record" data-module="asset">Lägg till tillgång</button>`)}
      <section class="split-layout">
        <article class="table-card">
          <table class="data-table">
            <thead>
              <tr>
                <th>Namn</th>
                <th>Typ</th>
                <th>Institution</th>
                <th class="align-right">Marknadsvärde</th>
                <th>Pantsatt</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              ${items.map((item) => `
                <tr>
                  <td>${escapeHtml(item.label || item.institution || optionLabel(OPTIONS.assetType, item.type))}</td>
                  <td>${escapeHtml(optionLabel(OPTIONS.assetType, item.type))}</td>
                  <td>${escapeHtml(item.institution || "Ej angiven")}</td>
                  <td class="align-right">${money(item.market_value)}</td>
                  <td>${item.pledged ? "Ja" : "Nej"}</td>
                  <td class="align-right"><button class="ghost compact" type="button" data-edit="asset" data-id="${item.id}">Redigera</button></td>
                </tr>
              `).join("") || `<tr><td colspan="6"><div class="empty-state"><p>Inga tillgångar registrerade ännu.</p></div></td></tr>`}
            </tbody>
          </table>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Tillgång</span>
          <h3>${currentEdit("asset")?.id ? "Redigera tillgång" : "Lägg till tillgång"}</h3>
          ${renderForm("assetForm", assetFields(), currentEdit("asset") || {}, {
            submitLabel: currentEdit("asset")?.id ? "Spara tillgång" : "Lägg till tillgång",
            canDelete: Boolean(currentEdit("asset")?.id),
            deleteLabel: "Ta bort tillgång",
          })}
        </article>
      </section>
    </section>
  `;
}

function renderHousingPageV2() {
  const items = housingForHousehold();
  const evaluation = state.housingEvaluation;
  return `
    <section class="page-wrap">
      ${renderPageHeader("Boendekalkyl", "Beräkna och jämför boendekostnader", `<button class="primary" type="button" data-action="new-record" data-module="housing">Ny boendekalkyl</button>`)}
      ${evaluation ? `
        <section class="stats-grid">
          ${renderStatCard("Boendekostnad / månad", money(evaluation.monthly_total_cost))}
          ${renderStatCard("Årskostnad", money(evaluation.yearly_total_cost))}
          ${renderStatCard("Ränta / månad", money(evaluation.monthly_interest))}
          ${renderStatCard("Kvar efter boendet", money((selectedSummary()?.monthly_net_cashflow || 0) - evaluation.monthly_total_cost))}
        </section>
      ` : ""}
      <section class="split-layout">
        <article class="panel">
          <div class="record-grid">
            ${items.map((item) => `
              <article class="record-card">
                <div class="record-title-row">
                  <div>
                    <h4 class="record-title">${escapeHtml(item.label)}</h4>
                    <p class="muted">${money(item.purchase_price)} · ${number(item.rate_assumption, 2)} % ränta</p>
                  </div>
                  <div class="actions-row">
                    <button class="ghost compact" type="button" data-edit="housing" data-id="${item.id}">Redigera</button>
                    <button class="primary compact" type="button" data-evaluate-housing="${item.id}">Utvärdera</button>
                  </div>
                </div>
              </article>
            `).join("") || `<div class="empty-state"><p>Inga boendescenarier registrerade ännu.</p></div>`}
          </div>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Scenario</span>
          <h3>${currentEdit("housing")?.id ? "Redigera boendescenario" : "Skapa boendescenario"}</h3>
          ${renderForm("housingForm", housingFields(), currentEdit("housing") || {}, {
            submitLabel: currentEdit("housing")?.id ? "Spara scenario" : "Skapa scenario",
            canDelete: Boolean(currentEdit("housing")?.id),
            deleteLabel: "Ta bort scenario",
          })}
        </article>
      </section>
    </section>
  `;
}

function ingestKindOptions() {
  return [
    ["text", "Klistrad text (faktura, avtal, kvitto)"],
    ["pdf_text", "Klistrad text från PDF"],
    ["bank_paste", "Bankrader / kontoutdrag (LF-format)"],
    ["image", "Bild eller screenshot (OCR)"],
  ];
}

function classificationLabel(docType) {
  return {
    subscription_contract: "Abonnemang / avtal",
    invoice: "Faktura",
    recurring_cost_candidate: "Återkommande kostnad",
    transfer_or_saving_candidate: "Överföring / sparande",
    bank_row_batch: "Bankrader / kontoutdrag",
    insurance_policy: "Försäkring",
    loan_or_credit: "Lån / kredit",
    financial_note: "Finansiell anteckning",
    unclear: "Oklart underlag",
  }[docType] || docType || "Oklart";
}

function classificationBadgeTone(docType) {
  return {
    subscription_contract: "info",
    invoice: "success",
    recurring_cost_candidate: "info",
    transfer_or_saving_candidate: "info",
    bank_row_batch: "info",
    insurance_policy: "info",
    loan_or_credit: "info",
    financial_note: "muted",
    unclear: "warning",
  }[docType] || "muted";
}

function confidenceBadge(confidence) {
  if (confidence == null) return `<span class="badge muted">Confidence ej angiven</span>`;
  const pct = Math.round(confidence * 100);
  if (pct >= 80) return `<span class="badge success">Confidence ${pct} %</span>`;
  if (pct >= 50) return `<span class="badge info">Confidence ${pct} %</span>`;
  return `<span class="badge warning">Confidence ${pct} %</span>`;
}

function relevanceBadge(relevance) {
  return {
    high: `<span class="badge success">Hög relevans</span>`,
    medium: `<span class="badge info">Medel relevans</span>`,
    low: `<span class="badge muted">Låg relevans</span>`,
  }[relevance] || `<span class="badge muted">${escapeHtml(relevance || "Okänd")}</span>`;
}

function normalizeIngestResult(result) {
  const documentSummary = result?.document_summary;
  const safeKeys = Array.isArray(documentSummary?.confirmed_fields) ? documentSummary.confirmed_fields : [];
  const safeFields = {};
  const uncertainFields = {};
  const summaryFactSource = {
    provider_name: documentSummary?.provider_name,
    title: documentSummary?.label,
    amount: documentSummary?.amount,
    currency: documentSummary?.currency,
    due_date: documentSummary?.due_date,
    cadence: documentSummary?.cadence,
    category_hint: documentSummary?.category_hint,
    household_relevance: documentSummary?.household_relevance,
  };

  Object.entries(summaryFactSource).forEach(([key, value]) => {
    if (value === null || value === undefined || String(value).trim() === "") return;
    if (safeKeys.includes(key)) {
      safeFields[key] = value;
    } else {
      uncertainFields[key] = value;
    }
  });

  if (Array.isArray(documentSummary?.notes) && documentSummary.notes.length) {
    uncertainFields.notes = documentSummary.notes;
  }

  const suggestions = Array.isArray(result?.suggestions) ? result.suggestions : [];
  const inferredRecommendation = documentSummary?.suggested_target_entity_type
    || {
      subscription_contract: "subscription_contract",
      recurring_cost_candidate: "recurring_cost",
      invoice: "document",
      financial_note: "document",
      unclear: "unclear",
    }[documentSummary?.document_type || "unclear"]
    || "unclear";
  return {
    analysisResultId: result?.analysis_result_id || null,
    inputKind: result?.source_channel || result?.input_kind || "text",
    inputDetails: result?.input_details || {},
    documentId: result?.document_id || result?.input_details?.document_id || null,
    documentType: documentSummary?.document_type || result?.detected_kind || "unclear",
    recommendation: inferredRecommendation,
    summary: result?.summary || result?.analysis_summary || result?.overview || "Ingen sammanfattning finns ännu.",
    confidence: documentSummary?.confidence ?? result?.confidence ?? null,
    rawSource: result?.input_details?.source_name || result?.source_name || null,
    providerName: documentSummary?.provider_name || null,
    title: documentSummary?.label || null,
    amount: documentSummary?.amount ?? null,
    currency: documentSummary?.currency || null,
    dueDate: documentSummary?.due_date || null,
    cadence: documentSummary?.cadence || null,
    householdRelevance: documentSummary?.household_relevance || null,
    notes: documentSummary?.notes || null,
    safeFields,
    uncertainFields,
    uncertaintyReasons: documentSummary?.uncertainty_reasons || [],
    guidance: result?.guidance || result?.review_notes || [],
    reviewGroups: Array.isArray(result?.review_groups) ? result.review_groups : [],
    suggestions,
    model: result?.model || null,
    provider: result?.provider || null,
    usage: result?.usage || null,
    imageReadiness: result?.image_readiness || null,
  };
}

function formatIngestAmount(value, currency) {
  if (value === null || value === undefined || value === "") return "Ej angivet";
  const amount = Number(value);
  if (Number.isNaN(amount)) return `${value}${currency ? ` ${currency}` : ""}`;
  const formatted = new Intl.NumberFormat("sv-SE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
  return currency ? `${formatted} ${currency}` : formatted;
}

function renderIngestFactGrid(review) {
  const facts = [
    ["Leverantör", review.providerName],
    ["Titel", review.title],
    ["Belopp", formatIngestAmount(review.amount, review.currency)],
    ["Förfallodatum", review.dueDate ? dateLabel(review.dueDate) : null],
    ["Frekvens", review.cadence],
    ["Hushållsrelevans", review.householdRelevance],
    ["Anteckning", review.notes],
  ].filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== "");

  if (!facts.length) {
    return `<div class="empty-state compact"><p>Inga säkra kärnfakta gick att extrahera. Det är bättre än att gissa.</p></div>`;
  }

  return `
    <div class="detail-grid three fact-grid">
      ${facts.map(([label, value]) => detailCell(label, value)).join("")}
    </div>
  `;
}

function renderIngestPipelineStrip() {
  return `
    <section class="record-grid four workflow-pipeline">
      <article class="workflow-step-card">
        <span class="badge info">1. Input</span>
        <h4>Text, PDF, bild eller kontoutdrag</h4>
        <p class="muted">Klistra in text, ladda upp underlag eller anvand OCR nar dokumentet bara finns som bild.</p>
      </article>
      <article class="workflow-step-card">
        <span class="badge info">2. Analyze</span>
        <h4>Extraktion och klassificering</h4>
        <p class="muted">Text normaliseras och AI analyserar typ, fakta och osakerhet utan att skriva till kanonisk ekonomi.</p>
      </article>
      <article class="workflow-step-card">
        <span class="badge info">3. Promote</span>
        <h4>Workflow-artefakter</h4>
        <p class="muted">Promote skapar dokument och reviewutkast. Det är fortfarande inte kanonisk data.</p>
      </article>
      <article class="workflow-step-card">
        <span class="badge info">4. Review + Apply</span>
        <h4>Manuell bekraftelse</h4>
        <p class="muted">Review och apply är separata steg. Bara explicit apply skriver till kanonisk hushållsekonomi.</p>
      </article>
    </section>
  `;
}

function renderIngestImageReadiness() {
  return `
    <article class="workflow-callout future-readiness">
      <div class="record-title-row">
        <div>
          <h4 class="record-title">Bild- och screenshot-avläsning (OCR)</h4>
          <p class="muted">Tesseract OCR (svenska + engelska) stöds för bilder, screenshots och skannade PDF:er.</p>
        </div>
        <span class="badge success">Implementerad</span>
      </div>
      <p class="muted">Ladda upp en bild eller skannad PDF via uppladdningsformuläret. Text extraheras via OCR innan AI-analys. Observera att OCR-text kan innehålla felläsningar.</p>
    </article>
  `;
}

function labelizeIngestKey(key) {
  return String(key || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatIngestSummaryValue(value) {
  if (Array.isArray(value)) {
    return value.map((item) => formatIngestSummaryValue(item)).join(" · ");
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return value == null ? "" : String(value);
}

function renderIngestSummaryBlock(value, fallbackText) {
  if (!value || (typeof value === "object" && !Array.isArray(value) && !Object.keys(value).length)) {
    return `<p class="muted">${escapeHtml(fallbackText)}</p>`;
  }

  if (Array.isArray(value)) {
    return `<ul class="summary-list">${value.map((item) => `<li>${escapeHtml(formatIngestSummaryValue(item))}</li>`).join("")}</ul>`;
  }

  if (typeof value === "object") {
    const entries = Object.entries(value).filter(([, item]) => item !== null && item !== undefined && String(formatIngestSummaryValue(item)).trim() !== "");
    if (!entries.length) {
      return `<p class="muted">${escapeHtml(fallbackText)}</p>`;
    }
    return `
      <div class="detail-grid three fact-grid">
        ${entries.map(([key, item]) => detailCell(labelizeIngestKey(key), formatIngestSummaryValue(item))).join("")}
      </div>
    `;
  }

  return `<p class="muted">${escapeHtml(formatIngestSummaryValue(value))}</p>`;
}

function ingestSourceChannelLabel(value) {
  return {
    text: "Klistrad text",
    pdf_text: "Klistrad PDF-text",
    uploaded_document: "Uppladdat dokument",
    uploaded_pdf: "Uppladdad PDF",
    image: "Bild / screenshot (OCR)",
    bank_paste: "Bankrader / kontoutdrag",
  }[value] || "Okänd källa";
}

function documentExtractionMeta(status) {
  return {
    uploaded: { tone: "muted", label: "Uppladdad" },
    interpreted: { tone: "success", label: "Tolkad" },
    pending_review: { tone: "warning", label: "Väntar granskning" },
    applied: { tone: "success", label: "Applicerad" },
    deferred: { tone: "muted", label: "Skjuten upp" },
    rejected: { tone: "muted", label: "Avvisad" },
    failed: { tone: "danger", label: "Misslyckad" },
  }[status || "uploaded"] || { tone: "muted", label: status || "uploaded" };
}

function documentWorkflowStatusLabel(status) {
  return {
    uploaded: "Uppladdad",
    interpreted: "Tolkad",
    pending_review: "Väntar på granskning",
    applied: "Applicerad",
    failed: "Misslyckad",
    deferred: "Skjuten upp",
    rejected: "Avvisad",
    approved: "Godkänd",
    apply_failed: "Misslyckad",
    manual_link: "Kräver manuell koppling",
    manual_link_required: "Kräver manuell koppling",
  }[status || "uploaded"] || status || "Uppladdad";
}

function documentWorkflowStatusTone(status) {
  return {
    uploaded: "muted",
    interpreted: "success",
    pending_review: "warning",
    applied: "success",
    failed: "danger",
    deferred: "muted",
    rejected: "muted",
    approved: "success",
    apply_failed: "danger",
    manual_link: "info",
    manual_link_required: "info",
  }[status || "uploaded"] || "muted";
}

function documentPreviewUrl(document) {
  return document ? `/documents/${document.id}/download` : "";
}

function documentMimeCategory(document) {
  const mimeType = String(document?.mime_type || "").toLowerCase();
  if (mimeType.startsWith("image/")) return "image";
  if (mimeType === "application/pdf") return "pdf";
  return "file";
}

function documentUploadMeta(file) {
  if (!file) return null;
  return {
    name: file.name,
    size: file.size,
    type: file.type,
    category: file.type.startsWith("image/") ? "image" : file.type === "application/pdf" ? "pdf" : "file",
    objectUrl: URL.createObjectURL(file),
  };
}

function clearDocumentUploadPreview() {
  const current = state.ui.documentUploadPreview;
  if (current?.objectUrl?.startsWith("blob:")) {
    URL.revokeObjectURL(current.objectUrl);
  }
  state.ui.documentUploadPreview = null;
  syncDocumentUploadPreviewDom();
}

function setDocumentUploadPreview(file) {
  clearDocumentUploadPreview();
  if (!file) {
    syncDocumentUploadPreviewDom();
    return;
  }
  state.ui.documentUploadPreview = documentUploadMeta(file);
  syncDocumentUploadPreviewDom();
}

function syncDocumentUploadPreviewDom() {
  const slot = document.getElementById("documentUploadPreviewSlot");
  if (slot) {
    slot.innerHTML = renderDocumentUploadPreview();
  }
}

function setDocumentDraftSelection(draftId, key, value) {
  const current = state.ui.documentDraftSelections?.[draftId] || {};
  state.ui.documentDraftSelections = {
    ...state.ui.documentDraftSelections,
    [draftId]: {
      ...current,
      [key]: value,
    },
  };
}

function documentDraftSelectionFor(draftId) {
  return state.ui.documentDraftSelections?.[draftId] || {};
}

function documentSummaryPayload(draft) {
  return draft?.review_json || draft?.proposed_json || {};
}

function formatDocumentFactValue(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") return formatIngestAmount(value, "");
  if (Array.isArray(value)) return value.map((item) => formatDocumentFactValue(item)).filter(Boolean).join(" · ");
  return String(value);
}

function formatDocumentPercent(value) {
  const amount = Number(value);
  if (Number.isNaN(amount)) return String(value);
  return `${new Intl.NumberFormat("sv-SE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount)} %`;
}

function formatDocumentFact(label, value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") {
    if (/ränta/i.test(label)) return formatDocumentPercent(value);
    return money(value);
  }
  const isDateField = /datum/i.test(label);
  const parsedDate = typeof value === "string" ? new Date(value) : null;
  if (isDateField && parsedDate && !Number.isNaN(parsedDate.getTime())) {
    return dateLabel(parsedDate);
  }
  return String(value);
}

function documentConfidenceForWorkflow(workflow) {
  const draft = workflow?.drafts?.find((item) => item.status === "pending_review") || workflow?.drafts?.[0];
  return draft?.confidence ?? workflow?.document?.confidence ?? null;
}

function documentFactsForWorkflow(workflow) {
  const draft = workflow?.drafts?.[0];
  const payload = documentSummaryPayload(draft);
  const facts = [
    ["Dokumenttyp", classificationLabel(payload.document_type || workflow?.document?.document_type)],
    ["Långivare", payload.lender || workflow?.document?.issuer],
    ["Objekt / fordon", payload.object_vehicle || payload.purpose],
    ["Faktureringsdatum", payload.billing_date || payload.issue_date],
    ["Förfallodatum", payload.payment_due_date || payload.due_date],
    ["Att betala", payload.payment_amount ?? payload.required_monthly_payment],
    ["Ränta", payload.interest_rate ?? payload.nominal_rate],
    ["Skuld före amortering", payload.debt_before_amortization ?? payload.current_balance],
    ["Amortering", payload.amortization ?? payload.amortization_amount_monthly],
    ["Räntekostnad", payload.interest_cost ?? payload.interest_cost_amount],
    ["Administrationsavgift", payload.fees ?? payload.fee_amount],
  ];
  return facts
    .map(([label, value]) => [label, formatDocumentFact(label, value)])
    .filter(([, value]) => value);
}

function documentSimilarText(value) {
  return String(value || "").toLowerCase().trim();
}

function scoreDocumentMatch(source, candidate) {
  const sourceText = documentSimilarText(source);
  const candidateText = documentSimilarText(candidate);
  if (!sourceText || !candidateText) return 0;
  if (candidateText === sourceText) return 4;
  if (candidateText.includes(sourceText) || sourceText.includes(candidateText)) return 3;
  const sourceParts = sourceText.split(/\s+/).filter(Boolean);
  const candidateParts = candidateText.split(/\s+/).filter(Boolean);
  const overlap = sourceParts.filter((part) => candidateParts.includes(part)).length;
  return overlap;
}

function documentVehicleMatches(workflow) {
  const draft = workflow?.drafts?.[0];
  const payload = documentSummaryPayload(draft);
  const hint = payload.object_vehicle || payload.purpose || workflow?.document?.issuer || "";
  return vehiclesForHousehold()
    .map((vehicle) => {
      const label = [vehicle.make, vehicle.model, vehicle.label].filter(Boolean).join(" ");
      return { vehicle, score: scoreDocumentMatch(hint, label) };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);
}

function documentLoanMatches(workflow) {
  const draft = workflow?.drafts?.[0];
  const payload = documentSummaryPayload(draft);
  const hint = payload.lender || workflow?.document?.issuer || "";
  return loansForHousehold()
    .map((loan) => {
      const label = [loan.lender, loan.purpose].filter(Boolean).join(" ");
      return { loan, score: scoreDocumentMatch(hint, label) };
    })
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3);
}

function documentConnectionHint(workflow) {
  const facts = documentFactsForWorkflow(workflow);
  const vehicleMatches = documentVehicleMatches(workflow);
  const loanMatches = documentLoanMatches(workflow);
  const hasDraft = Boolean(workflow?.drafts?.length);
  const draft = workflow?.drafts?.[0];
  const payload = documentSummaryPayload(draft);
  return {
    facts,
    vehicleMatches,
    loanMatches,
    needsManualLink: Boolean(payload.object_vehicle) && !vehicleMatches.length,
    hasDraft,
  };
}

function groupIngestSuggestions(suggestions) {
  const groups = new Map();
  suggestions.forEach((item) => {
    const bucket = item.review_bucket || item.recommended_direction || item.suggested_path || item.target_entity_type || item.document_type || "unclear";
    if (!groups.has(bucket)) {
      groups.set(bucket, []);
    }
    groups.get(bucket).push(item);
  });
  return Array.from(groups.entries()).map(([bucket, items]) => ({ bucket, items }));
}

function renderIngestSuggestionCard(item) {
  const confidence = item.confidence == null ? "Ej angiven" : number(item.confidence, 2);
  const documentType = item.document_type || item.detected_kind || item.classification || "unclear";
  const direction = item.recommended_direction || item.review_bucket || item.suggested_path || item.target_entity_type || "unclear";
  const uncertainty = item.uncertainty_reasons || item.uncertainty_notes || [];
  const fields = item.document_summary || item.extracted_fields || item.fields || item.core_facts || {};
  return `
    <article class="record-card">
      <div class="record-title-row">
        <div>
          <h4 class="record-title">${escapeHtml(item.title || item.provider_name || item.target_entity_type || "Förslag")}</h4>
          <p class="muted">${escapeHtml(documentType)} · ${escapeHtml(direction)} · confidence ${escapeHtml(confidence)}</p>
        </div>
        <span class="badge ${item.validation_status === "valid" ? "success" : "warning"}">${escapeHtml(item.validation_status)}</span>
      </div>
      <div class="detail-grid three fact-grid">
        ${fields.provider_name || item.provider_name ? detailCell("Leverantör", fields.provider_name || item.provider_name) : ""}
        ${fields.title || item.title ? detailCell("Titel", fields.title || item.title) : ""}
        ${(fields.amount ?? item.amount) !== undefined && (fields.amount ?? item.amount) !== null ? detailCell("Belopp", formatIngestAmount(fields.amount ?? item.amount, fields.currency || item.currency)) : ""}
        ${fields.due_date || item.due_date ? detailCell("Förfallodatum", dateLabel(fields.due_date || item.due_date)) : ""}
        ${fields.cadence || item.cadence ? detailCell("Frekvens", fields.cadence || item.cadence) : ""}
        ${fields.household_relevance || item.household_relevance ? detailCell("Hushållsrelevans", fields.household_relevance || item.household_relevance) : ""}
      </div>
      ${item.why_suggested ? `<p class="muted">💡 ${escapeHtml(item.why_suggested)}</p>` : `<p class="muted">${escapeHtml(item.rationale || "Ingen rationale angiven.")}</p>`}
      ${item.ownership_candidate ? `<span class="badge ${item.ownership_candidate === "shared" ? "info" : item.ownership_candidate === "private" ? "muted" : "warning"}">${item.ownership_candidate === "shared" ? "Gemensam" : item.ownership_candidate === "private" ? "Privat" : "Oklar ägare"}</span>` : ""}
      ${item.duplicate_indicator ? `<p class="muted" style="color:var(--clr-warning,#eab308)">⚠ ${escapeHtml(item.duplicate_indicator)}</p>` : ""}
      ${uncertainty?.length ? `<p class="muted">Osäkerhet: ${escapeHtml(uncertainty.join(" · "))}</p>` : ""}
      ${item.validation_errors?.length ? `<p class="muted">Validering: ${escapeHtml(item.validation_errors.join(" · "))}</p>` : ""}
      <details class="raw-json">
        <summary>Visa strukturerad payload</summary>
        <pre>${escapeHtml(JSON.stringify(item.proposed_json, null, 2))}</pre>
      </details>
    </article>
  `;
}

function renderIngestResult() {
  const result = state.ui.ingestResult;
  if (!result) {
    return `<div class="empty-state"><p>Ingen AI-analys körd ännu. Klistra in underlag eller ladda in extraherad text från ett dokument och kör analys när du vill skapa reviewutkast utan tysta databasskrivningar.</p></div>`;
  }

  const review = normalizeIngestResult(result);
  const validSuggestions = review.suggestions.filter((item) => item.validation_status === "valid");
  const suggestionGroups = review.reviewGroups.length
    ? review.reviewGroups.map((group) => ({ bucket: group.group_type, title: group.title, summary: group.summary, items: group.suggestions || [] }))
    : groupIngestSuggestions(review.suggestions);
  const rawPreview = (state.ui.ingestInput || "").trim();
  const rawPreviewText = rawPreview.length > 1200 ? `${rawPreview.slice(0, 1200)}...` : rawPreview;
  return `
    <div class="workflow-stack">
      <article class="record-card ingest-classification-card">
        <div class="record-title-row">
          <div>
            <span class="badge ${classificationBadgeTone(review.documentType)}">${escapeHtml(classificationLabel(review.documentType))}</span>
            <h4 class="record-title">${escapeHtml(review.summary)}</h4>
            <p class="muted">${escapeHtml(ingestSourceChannelLabel(review.inputKind))}${review.provider ? ` · ${escapeHtml(review.provider)}` : ""}${review.model ? ` · ${escapeHtml(review.model)}` : ""}</p>
          </div>
          <span class="badge muted">${review.usage?.total_tokens ? `${review.usage.total_tokens} tokens` : "utan usage"}</span>
        </div>
        <div class="badge-row">
          ${confidenceBadge(review.confidence)}
          ${relevanceBadge(review.householdRelevance)}
          <span class="badge muted">Riktning: ${escapeHtml(review.recommendation)}</span>
        </div>
        ${review.guidance?.length ? `<div class="ingest-guidance"><ul class="summary-list">${review.guidance.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}
        <div class="workflow-callout">
          <strong>AI-tolkningen är inte kanonisk data.</strong>
          <p class="muted">Promote skapar bara dokument- och reviewutkast. Inget skrivs tyst till hushållets slutgiltiga poster.</p>
        </div>
      </article>
      <article class="record-card">
        <div class="record-title-row">
          <div>
            <h4 class="record-title">Extraherade kärnfakta</h4>
            <p class="muted">Säkra fält (bekräftade i texten) visas med grön markering, osäkra med gul.</p>
          </div>
        </div>
        ${renderIngestFactGrid(review)}
        <div class="summary-panels">
          <article class="workflow-callout subtle safe-fields">
            <strong>✓ Bekräftade fält</strong>
            ${renderIngestSummaryBlock(review.safeFields, "Inga fält kunde bekräftas direkt ur texten.")}
          </article>
          <article class="workflow-callout subtle uncertain-fields">
            <strong>? Osäkra fält</strong>
            ${renderIngestSummaryBlock(review.uncertainFields, "Inga osäkra fält.")}
          </article>
        </div>
      </article>
      ${review.uncertaintyReasons?.length ? `
      <article class="record-card">
        <div class="record-title-row">
          <div>
            <h4 class="record-title">⚠ Osäkerhet och varningar</h4>
            <p class="muted">Modellen flaggar dessa punkter som osäkra. Granska innan du skapar utkast.</p>
          </div>
        </div>
        <ul class="summary-list uncertainty-list">${review.uncertaintyReasons.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </article>` : ""}
      <article class="record-card">
        <div class="record-title-row">
          <div>
            <h4 class="record-title">Reviewförslag</h4>
            <p class="muted">Validerade förslag grupperade efter typ.</p>
          </div>
          <span class="badge">${validSuggestions.length} validerade</span>
        </div>
        ${suggestionGroups.length ? suggestionGroups.map((group) => `
          <section class="workflow-group">
            <div class="record-title-row">
              <div>
                <h5 class="group-title">${escapeHtml(group.title || group.bucket)}</h5>
                <p class="muted">${group.items.length} förslag</p>
              </div>
              <span class="badge muted">${group.items.filter((item) => item.validation_status === "valid").length} validerade</span>
            </div>
            <div class="record-grid">
              ${group.items.map((item) => renderIngestSuggestionCard(item)).join("")}
            </div>
          </section>
        `).join("") : `<div class="empty-state compact"><p>Inga strukturerade förslag hittades.</p></div>`}
        <div class="actions-row" style="margin-top:var(--space-m)">
          <button class="primary" type="button" data-action="promote-ingest" ${validSuggestions.length ? "" : "disabled"}>
            ${state.ui.ingestPromoting ? "Skapar utkast..." : `Skapa ${validSuggestions.length} reviewutkast`}
          </button>
          <span class="chat-disclaimer">Detta skapar bara reviewutkast i workflow-lagret. Inget skrivs direkt till kanonisk ekonomi.</span>
        </div>
      </article>
      <details class="raw-json">
        <summary>Visa rå input (${review.inputDetails?.text_length || 0} tecken)</summary>
        <article class="record-card">
          <div class="detail-grid three fact-grid">
            ${detailCell("Källa", review.rawSource || "Ej angiven")}
            ${detailCell("Dokument", review.documentId ? `#${review.documentId}` : "Ingen")}
            ${detailCell("Extraktion", review.inputDetails?.extraction_mode || "manuell")}
          </div>
          ${rawPreviewText ? `<pre class="raw-preview">${escapeHtml(rawPreviewText)}</pre>` : `<div class="empty-state compact"><p>Ingen råtext.</p></div>`}
        </article>
      </details>
    </div>
  `;
}

function renderDocumentsPageV2() {
  const items = documentsForHousehold();
  const drafts = draftsForHousehold();
  const pendingDrafts = reviewDrafts(drafts);
  return `
    <section class="page-wrap">
      ${renderPageHeader("Dokument", "Arbetsyta för uppladdning, analys, review och apply. Dokumentflödet är den starkaste sanningsbarriären före kanonisk ekonomi.")}
      ${renderIngestPipelineStrip()}
      <section class="hero-grid document-hero">
        <article class="panel document-primary-panel">
          <span class="section-eyebrow">Dokumentinkorg</span>
          <h3>En väg in för underlag, tolkning och review</h3>
          <p class="muted">Välj fil, fotografera eller klistra in råtext. Samma arbetsyta visar preview, analys, workflowstatus och vad som faktiskt går vidare till review.</p>
          ${selectedHousehold()
            ? `
              ${renderDocumentUploadForm()}
              <div class="workflow-callout subtle">
                <strong>Råtext som fallback</strong>
                <p class="muted">Klistra in text från ett underlag när du inte har filen till hands. Analyze är fortsatt read-only mot kanoniska tabeller.</p>
              </div>
              <form id="ingestAnalyzeForm" class="form-grid document-manual-analyze">
                ${renderField({ key: "ingest_input_kind", label: "Underlagstyp", type: "select", options: ingestKindOptions(), required: true }, state.ui.ingestKind || "text")}
                ${renderField({ key: "ingest_source_name", label: "Källa eller avsändare", type: "text" }, state.ui.ingestSourceName || "")}
                ${renderField({ key: "ingest_input_text", label: "Råtext", type: "textarea", full: true, required: true, placeholder: "Klistra in text från faktura, abonnemang eller PDF här." }, state.ui.ingestInput || "")}
                <div class="field full">
                  <div class="form-actions upload-actions">
                    <button class="primary" type="submit">${state.ui.ingestPending ? "Analyserar..." : "Analysera text"}</button>
                    <button class="ghost" type="button" data-action="clear-ingest">Rensa</button>
                  </div>
                </div>
              </form>
              ${state.ui.ingestResult ? renderIngestResult() : `<article class="workflow-callout subtle"><strong>Senaste tolkning</strong><p class="muted">När du analyserar text visas tolkning, confidence, fält och förslag här.</p></article>`}
              ${renderIngestImageReadiness()}
            `
            : `<div class="empty-state"><p class="empty-copy">Välj hushåll först så att uppladdningen hamnar rätt.</p></div>`}
        </article>
        ${renderDocumentWorkflowPanel()}
      </section>
      <section class="split-layout">
        <article class="panel">
          <span class="section-eyebrow">Dokumentinkorg</span>
          <h3>${items.length ? `${items.length} dokument` : "Inga dokument ännu"}</h3>
          <p class="muted">Här ser du vad som är uppladdat, vad som är tolkat och vilket dokument som just nu är aktivt i workbenchen.</p>
          <div class="record-grid">
            ${items.map((item) => renderDocumentRowV2(item)).join("") || `<div class="empty-state"><p>Inga dokument uppladdade ännu.</p></div>`}
          </div>
        </article>
        <article class="panel">
          <span class="section-eyebrow">Granska och applicera</span>
          <h3>${pendingDrafts.length ? `${pendingDrafts.length} utkast kräver review` : "Inga utkast kräver review"}</h3>
          <p class="muted">Bara utkast som fortfarande väntar på beslut visas här. Varje apply visar efteråt exakt vad som skrevs till kanonisk data.</p>
          <div class="record-grid">
            ${pendingDrafts.map((draft) => renderDocumentDraftReviewCard(draft)).join("") || `<div class="empty-state"><p>Det finns inga väntande reviewutkast.</p></div>`}
          </div>
        </article>
      </section>
      <article class="panel">
        <span class="section-eyebrow">Leverantörsnormalisering</span>
        <h3>Kända leverantörsnamn</h3>
        <p class="muted">Lägg till alias → kanoniskt namn. Dessa tillämpas automatiskt på ingest-text innan AI-analys.</p>
        <div class="record-grid">
          ${(state.data.merchantAliases || []).map((a) => `
            <article class="record-card">
              <div class="record-title-row">
                <div>
                  <h4 class="record-title">${escapeHtml(a.alias)} → ${escapeHtml(a.canonical_name)}</h4>
                  <p class="muted">${a.category_hint ? escapeHtml(a.category_hint) : "Ingen kategori"}</p>
                </div>
                <button class="danger compact" type="button" data-action="delete-alias" data-alias-id="${a.id}">Ta bort</button>
              </div>
            </article>
          `).join("") || `<div class="empty-state compact"><p>Inga alias registrerade. Lägg till för att förbättra ingest.</p></div>`}
        </div>
        <form id="merchantAliasForm" class="form-grid" style="margin-top:var(--space-m)">
          ${renderField({ key: "alias_name", label: "Alias (t.ex. NETFLIX.COM)", type: "text", required: true }, "")}
          ${renderField({ key: "canonical_name", label: "Kanoniskt namn (t.ex. Netflix)", type: "text", required: true }, "")}
          ${renderField({ key: "category_hint", label: "Kategori (valfritt)", type: "text" }, "")}
          <div class="field full">
            <div class="form-actions">
              <button class="primary" type="submit" ${selectedHousehold() ? "" : "disabled"}>Lägg till alias</button>
            </div>
          </div>
        </form>
      </article>
    </section>
  `;
}

function draftTargetLabel(targetType) {
  return {
    recurring_cost: "Återkommande kostnad",
    subscription_contract: "Abonnemang",
    loan: "Lån",
    income_source: "Inkomstkälla",
  }[targetType] || targetType;
}

function draftStatusBadge(status) {
  return {
    pending_review: `<span class="badge warning">Väntar på granskning</span>`,
    deferred: `<span class="badge muted">Uppskjuten</span>`,
    approved: `<span class="badge success">Godkänd</span>`,
    rejected: `<span class="badge muted">Avvisad</span>`,
    apply_failed: `<span class="badge danger">Misslyckades</span>`,
  }[status] || `<span class="badge muted">${escapeHtml(status)}</span>`;
}

function renderDraftCard(draft) {
  const proposed = draft.proposed_json || {};
  const reviewPayload = draft.review_json || proposed;
  const title = proposed.provider || proposed.vendor || proposed.lender || proposed.source || draftTargetLabel(draft.target_entity_type);
  const amount = proposed.amount || proposed.current_monthly_cost || proposed.net_amount || proposed.required_monthly_payment;
  const freq = proposed.frequency || proposed.billing_frequency;
  const isEditing = state.ui.editingDraftId === draft.id;
  const editJson = isEditing ? (state.ui.editingDraftJson ?? JSON.stringify(proposed, null, 2)) : JSON.stringify(proposed, null, 2);
  return `
    <article class="record-card">
      <div class="record-title-row">
        <div>
          <span class="badge ${classificationBadgeTone(draft.target_entity_type)}">${escapeHtml(draftTargetLabel(draft.target_entity_type))}</span>
          <h4 class="record-title">${escapeHtml(title)}</h4>
          <p class="muted">Dokument #${draft.document_id}${draft.confidence != null ? ` · confidence ${Math.round(draft.confidence * 100)}%` : ""}</p>
        </div>
        <div>
          ${draftStatusBadge(draft.status)}
        </div>
      </div>
      ${draft.review_error ? `<p class="muted" style="color:var(--clr-danger)">Misslyckades: ${escapeHtml(draft.review_error)}</p>` : ""}
      ${draft.canonical_target_entity_id ? `<p class="muted">Kanonisk koppling: ${escapeHtml(draft.canonical_target_entity_type)} #${escapeHtml(draft.canonical_target_entity_id)}</p>` : ""}
      ${amount != null && !isEditing ? `<div class="detail-grid three fact-grid">${detailCell("Belopp", formatIngestAmount(amount, proposed.currency))}${freq ? detailCell("Frekvens", freq) : ""}${proposed.category ? detailCell("Kategori", proposed.category) : ""}</div>` : ""}
      ${draft.target_entity_type === "loan" && !isEditing ? renderLoanReviewFields(reviewPayload) : ""}
      ${isEditing ? `
        <div class="field full">
          <label>Redigera förslag (JSON)</label>
          <textarea class="draft-edit-area" name="draft_edit_json_${draft.id}" rows="8">${escapeHtml(editJson)}</textarea>
        </div>
        <div class="actions-row">
          <button class="primary compact" type="button" data-action="save-draft-edit" data-draft-id="${draft.id}">Spara ändringar</button>
          <button class="ghost compact" type="button" data-action="cancel-draft-edit">Avbryt</button>
        </div>
      ` : `
        <div class="actions-row">
          <button class="primary compact" type="button" data-apply-draft="${draft.id}">Applicera</button>
          <button class="ghost compact" type="button" data-action="edit-draft" data-draft-id="${draft.id}">Redigera</button>
          <button class="ghost compact" type="button" data-action="defer-draft" data-draft-id="${draft.id}">Skjut upp</button>
          <button class="danger compact" type="button" data-delete-draft="${draft.id}">Avvisa</button>
        </div>
      `}
      ${!isEditing ? `<details class="raw-json"><summary>Visa rå JSON</summary><pre>${escapeHtml(JSON.stringify(proposed, null, 2))}</pre></details>` : ""}
    </article>
  `;
}

function renderDocumentRowV2(item) {
  const snippet = item.extracted_text ? item.extracted_text.trim().slice(0, 180) : "";
  const extraction = documentExtractionMeta(item.extraction_status);
  return `
    <article class="record-card ${state.ui.selectedDocumentId === item.id ? "is-active" : ""}">
      <div class="record-title-row">
        <div>
          <h4 class="record-title">${escapeHtml(item.file_name)}</h4>
          <p class="muted">${escapeHtml(optionLabel(OPTIONS.documentType, item.document_type))}${item.issuer ? ` · ${escapeHtml(item.issuer)}` : ""}</p>
        </div>
        <div class="actions-row">
          <span class="badge ${escapeHtml(extraction.tone)}">${escapeHtml(extraction.label)}</span>
          <button class="ghost compact" type="button" data-action="select-document" data-document-id="${item.id}">Detaljer</button>
          <a class="ghost compact" href="/documents/${item.id}/download">Ladda ned</a>
          <button class="primary compact" type="button" data-action="analyze-document" data-document-id="${item.id}" ${item.extracted_text ? "" : "disabled"}>Analysera text</button>
        </div>
      </div>
      ${snippet ? `<p class="muted">${escapeHtml(snippet)}${item.extracted_text && item.extracted_text.trim().length > 180 ? "..." : ""}</p>` : `<p class="muted">Ingen extraherad text ännu.</p>`}
      ${item.processing_error ? `<p class="muted" style="color:var(--clr-danger)">Fel: ${escapeHtml(item.processing_error)}</p>` : ""}
    </article>
  `;
}

function renderLoanReviewFields(payload) {
  const pairs = [
    ["Långivare", payload.lender],
    ["Ränta", payload.interest_rate ?? payload.nominal_rate],
    ["Skuld före amortering", payload.debt_before_amortization ?? payload.current_balance],
    ["Belopp att betala", payload.payment_amount ?? payload.required_monthly_payment],
    ["Förfallodatum", payload.payment_due_date ?? payload.due_date],
    ["Objekt / bil", payload.object_vehicle ?? payload.purpose],
    ["Kontraktsnummer", payload.contract_number],
    ["Amortering", payload.amortization ?? payload.amortization_amount_monthly],
    ["Räntekostnad", payload.interest_cost ?? payload.interest_cost_amount],
    ["Avgifter", payload.fees ?? payload.fee_amount],
  ].filter(([, value]) => value !== undefined && value !== null && value !== "");
  if (!pairs.length) return "";
  return `
    <div class="detail-grid two fact-grid">
      ${pairs.map(([label, value]) => detailCell(label, value)).join("")}
    </div>
  `;
}

function selectedDocumentWorkflow() {
  return state.ui.selectedDocumentWorkflow;
}

function renderDocumentPreview(document) {
  if (!document) {
    return `<div class="empty-state"><p>Välj ett dokument för att se preview här.</p></div>`;
  }

  const src = documentPreviewUrl(document);
  const kind = documentMimeCategory(document);
  if (kind === "image") {
    return `<img class="document-preview-image document-preview-large" src="${escapeHtml(src)}" alt="Förhandsvisning av dokumentet" />`;
  }
  if (kind === "pdf") {
    return `<iframe class="document-preview-frame document-preview-large" src="${escapeHtml(src)}" title="Förhandsvisning av dokumentet"></iframe>`;
  }
  return `
    <article class="workflow-callout subtle">
      <strong>Förhandsvisning</strong>
      <p class="muted">Den här filtypen förhandsvisas som nedladdningslänk.</p>
      <a class="ghost compact" href="${escapeHtml(src)}" target="_blank" rel="noreferrer">Öppna filen</a>
    </article>
  `;
}

function renderDocumentStatusRail(workflow, document) {
  const currentStatus = workflow?.workflow_status || document?.extraction_status || "uploaded";
  const steps = workflow?.status_steps?.length
    ? workflow.status_steps
    : [
        { key: "uploaded", label_sv: "Uppladdad", active: currentStatus === "uploaded", completed: false },
        { key: "interpreted", label_sv: "Tolkad", active: currentStatus === "interpreted", completed: currentStatus !== "uploaded" },
        { key: "pending_review", label_sv: "Väntar på granskning", active: currentStatus === "pending_review", completed: ["approved", "applied"].includes(currentStatus) },
        { key: "approved", label_sv: "Godkänd", active: currentStatus === "approved", completed: currentStatus === "applied" },
        { key: "applied", label_sv: "Applicerad", active: currentStatus === "applied", completed: false },
      ];
  return `
    <div class="document-status-rail">
      ${steps.map((step) => `
        <span class="status-chip ${(step.active || step.completed || step.key === currentStatus) ? "active" : ""} ${documentWorkflowStatusTone(step.key)}">${escapeHtml(step.label_sv || documentWorkflowStatusLabel(step.key))}</span>
      `).join("")}
    </div>
  `;
}

function renderDocumentApplySummary(workflow = null) {
  const summary = state.ui.documentApplySummary || workflow?.apply_summary;
  if (!summary) {
    return `
      <article class="workflow-callout subtle document-apply-summary">
        <strong>Appliceringsbekräftelse</strong>
        <p class="muted">När du godkänner ett förslag visas här exakt vad som skapades eller uppdaterades.</p>
      </article>
    `;
  }

  return `
    <article class="workflow-callout document-apply-summary">
      <div class="record-title-row">
        <div>
          <h4 class="record-title">Applicerat dokument</h4>
          <p class="muted">${escapeHtml(summary.message_sv || "")}</p>
        </div>
        <span class="badge ${summary.status === "applied" ? "success" : summary.status === "partial" ? "warning" : "muted"}">${escapeHtml(summary.status)}</span>
      </div>
      ${summary.mutations?.length ? `<ul class="summary-list">${summary.mutations.map((item) => `<li>${escapeHtml(item.summary_sv)}</li>`).join("")}</ul>` : ""}
      ${summary.manual_actions_required?.length ? `<ul class="summary-list">${summary.manual_actions_required.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    </article>
  `;
}

function resolutionActionLabel(action, entityType) {
  if (action === "create_new") return entityType === "vehicle" ? "Skapa nytt fordon" : "Skapa nytt lån";
  if (action === "link_existing") return entityType === "vehicle" ? "Koppla till befintligt fordon" : "Koppla till befintligt lån";
  return "Välj manuellt";
}

function renderDocumentResolutionCard(resolution, workflow) {
  const draft = (workflow?.drafts || []).find((item) => item.id === resolution.draft_id);
  if (!draft) return "";
  const reviewPayload = draft.review_json || draft.proposed_json || {};
  const selection = state.ui.documentDraftSelections?.[draft.id] || {};
  const hasVehicle = Boolean(reviewPayload.object_vehicle || reviewPayload.purpose);
  const loanLabel = reviewPayload.lender || reviewPayload.provider || "Lån";
  return `
    <article class="record-card document-resolution-card">
      <div class="record-title-row">
        <div>
          <h4 class="record-title">${escapeHtml(loanLabel)}</h4>
          <p class="muted">${escapeHtml(resolution.reason || "Systemet försöker avgöra om rätt objekt redan finns.")}</p>
        </div>
        ${draftStatusBadge(draft.status)}
      </div>
      ${renderLoanReviewFields(reviewPayload)}
      <div class="detail-grid two fact-grid">
        ${detailCell("Dokumenttyp", draftTargetLabel(draft.target_entity_type))}
        ${detailCell("Confidence", draft.confidence != null ? `${Math.round(draft.confidence * 100)} %` : "Ej angiven")}
      </div>
      <div class="detail-grid two fact-grid document-resolution-grid">
        <div class="detail-item">
          <label>Det här lånet</label>
          <select class="compact-select" name="document_resolution_loan_action_${draft.id}">
            <option value="">Välj hur lånet ska hanteras</option>
            <option value="create_new" ${selection.loanAction === "create_new" ? "selected" : ""}>Skapa nytt lån</option>
            <option value="link_existing" ${selection.loanAction === "link_existing" ? "selected" : ""}>Koppla till befintligt lån</option>
          </select>
          ${resolution.loan_candidates?.length ? `
            <select class="compact-select" name="document_resolution_loan_target_${draft.id}">
              <option value="">Välj befintligt lån</option>
              ${resolution.loan_candidates.map((item) => `<option value="${escapeHtml(item.entity_id)}" ${String(selection.loanTargetId || "") === String(item.entity_id) ? "selected" : ""}>${escapeHtml(item.label)}${item.confidence != null ? ` · ${Math.round(item.confidence * 100)} %` : ""}</option>`).join("")}
            </select>
          ` : `<p class="muted">Ingen tydlig lånmatchning hittades i hushållet.</p>`}
        </div>
        ${hasVehicle ? `
          <div class="detail-item">
            <label>Fordonskoppling</label>
            <select class="compact-select" name="document_resolution_vehicle_action_${draft.id}">
              <option value="">Välj hur fordonet ska hanteras</option>
              <option value="create_new" ${selection.vehicleAction === "create_new" ? "selected" : ""}>Skapa ny fordonspost</option>
              <option value="link_existing" ${selection.vehicleAction === "link_existing" ? "selected" : ""}>Koppla till befintligt fordon</option>
              <option value="skip" ${selection.vehicleAction === "skip" ? "selected" : ""}>Hoppa över fordonskoppling</option>
            </select>
            ${resolution.vehicle_candidates?.length ? `
              <select class="compact-select" name="document_resolution_vehicle_target_${draft.id}">
                <option value="">Välj befintligt fordon</option>
                ${resolution.vehicle_candidates.map((item) => `<option value="${escapeHtml(item.entity_id)}" ${String(selection.vehicleTargetId || "") === String(item.entity_id) ? "selected" : ""}>${escapeHtml(item.label)}${item.confidence != null ? ` · ${Math.round(item.confidence * 100)} %` : ""}</option>`).join("")}
              </select>
            ` : `<p class="muted">Ingen tydlig fordonsträff hittades. Systemet kan skapa ny post för ${escapeHtml(reviewPayload.object_vehicle || reviewPayload.purpose)}.</p>`}
          </div>
        ` : ""}
      </div>
      <div class="actions-row">
        <button class="primary compact" type="button" data-action="apply-document-resolution" data-draft-id="${draft.id}" ${state.ui.documentApplyPending ? "disabled" : ""}>${state.ui.documentApplyPending ? "Applicerar..." : "Applicera detta paket"}</button>
        <button class="ghost compact" type="button" data-action="defer-draft" data-draft-id="${draft.id}">Skjut upp</button>
        <button class="danger compact" type="button" data-delete-draft="${draft.id}">Avvisa</button>
      </div>
    </article>
  `;
}

function renderDocumentSnapshot(workflow) {
  const document = workflow?.document;
  const facts = documentFactsForWorkflow(workflow);
  const confidence = documentConfidenceForWorkflow(workflow);
  const connection = documentConnectionHint(workflow);
  const primaryDraft = workflow?.drafts?.[0];
  const statusLabel = documentWorkflowStatusLabel(workflow?.workflow_status || document?.extraction_status);
  const statusTone = documentWorkflowStatusTone(workflow?.workflow_status || document?.extraction_status);
  return `
    <div class="document-summary-stack">
      <div class="badge-row">
        <span class="badge ${statusTone}">${escapeHtml(statusLabel)}</span>
        ${confidenceBadge(confidence)}
        ${primaryDraft?.target_entity_type ? `<span class="badge info">${escapeHtml(draftTargetLabel(primaryDraft.target_entity_type))}</span>` : ""}
      </div>
      <p class="muted">${escapeHtml(workflow?.status_detail || "Det här dokumentet är redo för granskning eller väntar på att kopplas rätt.")}</p>
      <div class="detail-grid two fact-grid document-summary-grid">
        ${facts.length
          ? facts.map(([label, value]) => detailCell(label, value)).join("")
          : `<div class="empty-state compact"><p>Inga nyckelfält kunde ännu visas.</p></div>`}
      </div>
      <div class="badge-row">
        ${connection.loanMatches.length ? `<span class="badge success">${connection.loanMatches.length} lånmatchning${connection.loanMatches.length > 1 ? "ar" : ""}</span>` : `<span class="badge muted">Ingen lånmatchning</span>`}
        ${connection.vehicleMatches.length ? `<span class="badge success">${connection.vehicleMatches.length} fordonsmatchning${connection.vehicleMatches.length > 1 ? "ar" : ""}</span>` : `<span class="badge muted">Ingen fordonsmatchning</span>`}
        ${connection.needsManualLink ? `<span class="badge warning">Kräver manuell koppling</span>` : `<span class="badge muted">Automatisk koppling räcker</span>`}
      </div>
      ${connection.vehicleMatches.length || connection.loanMatches.length ? `
        <div class="document-match-list">
          ${connection.loanMatches.length ? `
            <article class="workflow-callout subtle">
              <strong>Matchat lån</strong>
              <div class="record-grid">
                ${connection.loanMatches.map((item) => `
                  <article class="record-card compact">
                    <strong>${escapeHtml(item.loan.lender || item.loan.purpose || "Lån")}</strong>
                    <p class="muted">${escapeHtml(item.loan.purpose || "Ingen specifik användning")} · ${money(item.loan.required_monthly_payment)}</p>
                  </article>
                `).join("")}
              </div>
            </article>
          ` : ""}
          ${connection.vehicleMatches.length ? `
            <article class="workflow-callout subtle">
              <strong>Matchat fordon</strong>
              <div class="record-grid">
                ${connection.vehicleMatches.map((item) => `
                  <article class="record-card compact">
                    <strong>${escapeHtml([item.vehicle.make, item.vehicle.model].filter(Boolean).join(" ") || "Fordon")}</strong>
                    <p class="muted">${escapeHtml(item.vehicle.note || "Befintlig fordonspost")}</p>
                  </article>
                `).join("")}
              </div>
            </article>
          ` : ""}
        </div>
      ` : ""}
      ${connection.needsManualLink ? `
        <article class="workflow-callout">
          <strong>Manuell fordonskoppling behövs</strong>
          <p class="muted">Dokumentet pekar mot ett fordon, men ingen tydlig post hittades ännu. Skapa eller koppla fordonet på fordonssidan när du vill låsa kedjan helt.</p>
          <div class="actions-row">
            <button class="ghost compact" type="button" data-action="prefill-vehicle-from-document" data-document-id="${document?.id || ""}">Förifyll fordon</button>
            <button class="ghost compact" type="button" data-nav="vehicles">Öppna fordon</button>
          </div>
        </article>
      ` : ""}
    </div>
  `;
}

function renderDocumentDraftReviewCard(draft) {
  const proposed = draft.proposed_json || {};
  const reviewPayload = draft.review_json || proposed;
  const loanSelectName = `document_link_loan_${draft.id}`;
  const workflowResolution = (state.ui.selectedDocumentWorkflow?.entity_resolutions || [])
    .find((resolution) => resolution.draft_id === draft.id);
  const currentTarget = draft.status === "approved" && draft.canonical_target_entity_id
    ? `${escapeHtml(draft.canonical_target_entity_type)} #${escapeHtml(draft.canonical_target_entity_id)}`
    : null;
  return `
    <article class="record-card document-draft-card">
      <div class="record-title-row">
        <div>
          <h4 class="record-title">${escapeHtml(draftTargetLabel(draft.target_entity_type))}</h4>
          <p class="muted">Utkast #${draft.id} · ${escapeHtml(draft.status)}${draft.confidence != null ? ` · confidence ${Math.round(draft.confidence * 100)}%` : ""}</p>
        </div>
        ${draftStatusBadge(draft.status)}
      </div>
      ${draft.target_entity_type === "loan" ? renderLoanReviewFields(reviewPayload) : ""}
      ${currentTarget ? `<p class="muted">Kanonisk koppling: ${currentTarget}</p>` : ""}
      ${draft.review_error ? `<p class="muted" style="color:var(--danger)">Misslyckades: ${escapeHtml(draft.review_error)}</p>` : ""}
      ${draft.status === "pending_review" && workflowResolution ? `
        <p class="muted">Det här utkastet har föreslagen objektkedja. Använd dokumentets apply-flöde ovan för att undvika dubbelregistrering.</p>
      ` : ""}
      ${draft.status === "pending_review" && !workflowResolution ? `
        <div class="actions-row">
          <button class="primary compact" type="button" data-action="apply-draft-create" data-draft-id="${draft.id}">Godkänn och skapa nytt ${escapeHtml(draftTargetLabel(draft.target_entity_type).toLowerCase())}</button>
          ${draft.target_entity_type === "loan" ? `
            <select name="${loanSelectName}" class="compact-select">
              <option value="">Välj befintligt lån</option>
              ${loanOptions().map(([id, label]) => `<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`).join("")}
            </select>
            <button class="ghost compact" type="button" data-action="apply-draft-link-loan" data-draft-id="${draft.id}" data-select-name="${loanSelectName}">Koppla till befintligt lån</button>
          ` : ""}
          <button class="ghost compact" type="button" data-action="defer-draft" data-draft-id="${draft.id}">Skjut upp</button>
          <button class="danger compact" type="button" data-delete-draft="${draft.id}">Avvisa</button>
        </div>
      ` : ""}
      <details class="raw-json">
        <summary>Visa reviewdata</summary>
        <pre>${escapeHtml(JSON.stringify(reviewPayload, null, 2))}</pre>
      </details>
    </article>
  `;
}

function renderDocumentWorkflowPanel() {
  const workflow = selectedDocumentWorkflow();
  const document = workflow?.document || selectedDocument();
  if (!document) {
    return `
      <section class="panel">
        <span class="section-eyebrow">Tolkning</span>
        <h3>Välj ett dokument</h3>
        <p class="muted">Här visas preview, extraherade fält, sannolik objektkedja och vad som ska appliceras när du godkänner.</p>
      </section>
    `;
  }
  const statusMeta = documentExtractionMeta(workflow?.workflow_status || document.extraction_status);
  const drafts = workflow?.drafts || [];
  const links = workflow?.canonical_links || [];
  return `
    <section class="panel document-workbench-panel">
      <div class="record-title-row">
        <div>
          <span class="section-eyebrow">Tolkning</span>
          <h3>${escapeHtml(document.file_name)}</h3>
          <p class="muted">${escapeHtml(optionLabel(OPTIONS.documentType, document.document_type))}${document.issuer ? ` · ${escapeHtml(document.issuer)}` : ""}</p>
        </div>
        <span class="badge ${statusMeta.tone}">${statusMeta.label}</span>
      </div>
      <p class="muted">${escapeHtml(workflow?.status_detail || "Dokumentet är laddat men behöver fortfarande din bekräftelse.")}</p>
      ${document.processing_error ? `<p class="muted" style="color:var(--danger)">Fel: ${escapeHtml(document.processing_error)}</p>` : ""}
      ${renderDocumentPreview(document)}
      ${renderDocumentStatusRail(workflow, document)}
      ${renderDocumentApplySummary(workflow)}
      ${renderDocumentSnapshot(workflow)}
      ${(workflow?.entity_resolutions || []).length ? `
        <article class="workflow-callout subtle">
          <strong>Föreslagen objektkedja</strong>
          <p class="muted">Bekräfta hur dokumentet ska kopplas i systemet. Du ser direkt om det gäller lån, fordon eller båda.</p>
          <div class="record-grid">
            ${workflow.entity_resolutions.map((resolution) => renderDocumentResolutionCard(resolution, workflow)).join("")}
          </div>
        </article>
      ` : ""}
      ${links.length ? `
        <article class="workflow-callout subtle">
          <strong>Applikerad koppling</strong>
          <div class="record-grid">
            ${links.map((link) => `
              <article class="record-card compact">
                <strong>${escapeHtml(link.target_label)}</strong>
                <p class="muted">${escapeHtml(link.target_entity_type)} #${escapeHtml(link.target_entity_id)} · utkast #${escapeHtml(link.draft_id)}</p>
              </article>
            `).join("")}
          </div>
        </article>
      ` : ""}
      <article class="workflow-callout subtle">
        <strong>Vad händer vid apply</strong>
        <p class="muted">Du godkänner först ett förslag, därefter skrivs det till kanonisk data. Om något behöver justeras kan du redigera, skjuta upp eller avvisa innan du applicerar.</p>
      </article>
      ${drafts.length ? `<div class="actions-row">
        <button class="ghost compact" type="button" data-action="prefill-loan-from-document" data-document-id="${document.id}">Förifyll lån</button>
        <button class="ghost compact" type="button" data-action="prefill-vehicle-from-document" data-document-id="${document.id}">Förifyll fordon</button>
      </div>` : ""}
      ${drafts.length ? `<p class="muted">Det finns ${drafts.length} utkast kopplade till dokumentet nedan.</p>` : ""}
    </section>
  `;
}

function renderImprovementsPageV2() {
  const items = opportunitiesForHousehold().slice().sort((a, b) => Number(b.estimated_monthly_saving || 0) - Number(a.estimated_monthly_saving || 0));
  return `
    <section class="page-wrap">
      ${renderPageHeader("Förbättringsförslag", "Konkreta åtgärder för att förbättra er ekonomi", `<button class="primary" type="button" data-action="scan-opportunities">Kör ny skanning</button>`)}
      <section class="record-grid">
        ${items.map((item) => renderOpportunityCardV2(item)).join("") || `<div class="empty-state"><p>Det finns ännu inga förbättringsförslag.</p></div>`}
      </section>
    </section>
  `;
}

function renderOpportunityCardV2(item) {
  return `
    <article class="record-card">
      <div class="record-title-row">
        <div>
          <h4 class="record-title">${escapeHtml(opportunityTitleLabel(item))}</h4>
          <p class="muted">${escapeHtml(opportunityRationaleLabel(item))}</p>
        </div>
        <div class="record-value">${money(item.estimated_monthly_saving)}</div>
      </div>
      <div class="badge-row">
        <span class="badge success">Besparing ${money(item.estimated_monthly_saving)} / mån</span>
        <span class="badge ${badgeTone(item.risk_level)}">Risk: ${riskLabel(item.risk_level)}</span>
        <span class="badge muted">${effortLabel(item.effort_level)}</span>
      </div>
    </article>
  `;
}

function renderScenariosPageV2() {
  const items = scenariosForHousehold();
  return `
    <section class="page-wrap">
      ${renderPageHeader("Scenarier", "Utforska vad som händer om ekonomin förändras", `<button class="primary" type="button" data-action="new-record" data-module="scenario">Skapa scenario</button>`)}
      <section class="split-layout">
        <article class="panel">
          <div class="record-grid">
            ${items.map((item) => {
              const result = latestScenarioResult(item.id);
              return `
                <article class="record-card">
                  <div class="record-title-row">
                    <div>
                      <h4 class="record-title">${escapeHtml(item.label)}</h4>
                      <p class="muted">${escapeHtml(JSON.stringify(item.change_set_json))}</p>
                    </div>
                    <div class="actions-row">
                      <button class="ghost compact" type="button" data-edit="scenario" data-id="${item.id}">Redigera</button>
                      <button class="primary compact" type="button" data-run-scenario="${item.id}">Kör</button>
                    </div>
                  </div>
                  ${result ? `<div class="detail-grid">${detailCell("Månadsdelta", money(result.monthly_delta))}${detailCell("Årsdelta", money(result.yearly_delta))}${detailCell("Likviditet", money(result.liquidity_delta))}</div>` : `<p class="muted">Scenariot är inte kört ännu.</p>`}
                </article>
              `;
            }).join("") || `<div class="empty-state"><p>Inga scenarier registrerade ännu.</p></div>`}
          </div>
        </article>
        <article class="panel form-card">
          <span class="section-eyebrow">Scenario</span>
          <h3>${currentEdit("scenario")?.id ? "Redigera scenario" : "Skapa scenario"}</h3>
          ${renderScenarioForm()}
        </article>
      </section>
    </section>
  `;
}

function renderScenarioForm() {
  const item = currentEdit("scenario") || {};
  const raw = item.change_set_json ? JSON.stringify(item.change_set_json, null, 2) : JSON.stringify({ adjustments: [] }, null, 2);
  return `
    <form id="scenarioForm" class="form-grid">
      ${renderField({ key: "label", label: "Namn", type: "text", required: true }, item.label)}
      ${renderField({ key: "change_set_json", label: "Ändringar (JSON)", type: "textarea", full: true }, raw)}
      <div class="field full">
        <div class="form-actions">
          <button class="primary" type="submit">${item.id ? "Spara scenario" : "Skapa scenario"}</button>
          <button class="ghost" type="button" data-reset-form="scenarioForm">Rensa</button>
          ${item.id ? `<button class="danger" type="button" data-delete-form="scenarioForm">Ta bort scenario</button>` : ""}
        </div>
      </div>
    </form>
  `;
}

function renderReportsPageV2() {
  const items = reportsForHousehold().slice().sort((a, b) => new Date(b.generated_at).getTime() - new Date(a.generated_at).getTime());
  const openReport = items.find((item) => item.id === state.ui.openReportId) || items[0] || null;
  return `
    <section class="page-wrap">
      ${renderPageHeader("Rapporter", "Kanoniska snapshots, bankkalkyl och exporter baserade på registrerad hushållsdata.", `
        <a class="primary" href="/households/${state.selectedHouseholdId}/export/bank_pdf" target="_blank" ${selectedHousehold() ? "" : "disabled"}>Ladda ned bankkalkyl</a>
      `)}
      <section class="split-layout">
        <article class="panel form-card">
          <span class="section-eyebrow">Ny snapshot</span>
          <h3>Generera rapport med samma sanning som overview</h3>
          <p class="muted">Bankkalkyl och snapshots bygger bara på registrerad hushållsdata. Reviewutkast räknas inte in förrän de applicerats.</p>
          ${renderReportGenerateForm()}
        </article>
        <article class="panel">
          <span class="section-eyebrow">Rapporter</span>
          <h3>${items.length ? `${items.length} sparade snapshots` : "Inga rapporter an"}</h3>
          <div class="record-grid">
            ${items.map((item) => renderReportRowV2(item)).join("") || `<div class="empty-state"><p>Inga rapporter sparade ännu.</p></div>`}
          </div>
        </article>
      </section>
      ${openReport ? `
        <article class="panel">
          <span class="section-eyebrow">Rapportdetalj</span>
          <h3 class="report-detail-title">${escapeHtml(reportTypeLabel(openReport.type))} · ${dateLabel(openReport.as_of_date)}</h3>
          <pre>${escapeHtml(JSON.stringify(openReport.result_json, null, 2))}</pre>
        </article>
      ` : ""}
    </section>
  `;
}

function renderReportRowV2(item) {
  const baseline = item.result_json?.baseline || item.result_json || {};
  const income = baseline.monthly_income ?? baseline.monthly_income_net;
  const net = baseline.monthly_net_cashflow;
  return `
    <article class="record-card report-row-card">
      <div class="record-title-row">
        <div>
          <h4 class="record-title">${escapeHtml(reportTypeLabel(item.type))}</h4>
          <p class="muted">${dateLabel(item.as_of_date)} · genererad ${dateLabel(item.generated_at)}</p>
        </div>
        <div class="actions-row">
          <button class="ghost compact" type="button" data-open-report="${item.id}">Öppna</button>
          <button class="danger compact" type="button" data-delete-report="${item.id}">Ta bort</button>
        </div>
      </div>
      <div class="detail-grid ${income != null && net != null ? "two" : ""}">
        ${income != null ? detailCell("Inkomst / manad", money(income)) : ""}
        ${net != null ? detailCell("Netto / manad", money(net)) : ""}
      </div>
      <p class="report-summary">${escapeHtml(JSON.stringify(item.result_json).slice(0, 180))}...</p>
    </article>
  `;
}

function renderReportGenerateForm() {
  return `
    <form id="reportGenerateForm" class="form-grid">
      ${renderField({ key: "type", label: "Typ", type: "select", options: [["monthly_overview", "Månadsrapport"], ["optimization_report", "Förbättringsrapport"], ["bank_calc", "Bankkalkyl"]], required: true }, "monthly_overview")}
      ${renderField({ key: "as_of_date", label: "Per datum", type: "date", required: true }, new Date().toISOString().slice(0, 10))}
      ${renderField({ key: "assumption_json", label: "Antaganden (JSON, valfritt)", type: "textarea", full: true }, "{}")}
      <div class="field full">
        <div class="form-actions">
          <button class="primary" type="submit">Generera rapport</button>
        </div>
      </div>
    </form>
  `;
}

function renderAssistantDeterministicOverview() {
  return assistantRenderer.renderAssistantDeterministicOverview();
}

function renderAssistantPageV2() {
  return assistantRenderer.renderAssistantPage();
}

function renderAssistantMessage(message) {
  return assistantRenderer.renderAssistantMessage(message);
}

async function applyAssistantIntentById(messageId) {
  return assistantWorkspace.applyAssistantIntentById(messageId);
}

function renderAssistantMarkdown(text) {
  return escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/^### (.*)$/gm, "<p><strong>$1</strong></p>")
    .replace(/^- (.*)$/gm, "<p>• $1</p>")
    .replace(/\n/g, "<br>");
}

function renderRegisterPage() {
  const steps = onboardingSteps();
  return `
    <section class="page-wrap">
      ${renderPageHeader("Registrera ekonomi", "Guidad onboarding mot riktiga backendflöden")}
      <article class="wizard-card">
        <div class="wizard-progress">
          <div class="wizard-steps">
            ${["Hushåll", "Personer", "Inkomster", "Lån", "Kostnader", "Abonnemang", "Tillgångar", "Boende", "Rapport", "Klart"].map((_, index) => `<div class="wizard-step ${index < steps.length ? "active" : "done"}"></div>`).join("")}
          </div>
          <p class="muted">Den här guidade vyn använder samma riktiga CRUD-flöden som övriga appen. Lägg först grunden, sedan resten stegvis.</p>
        </div>
        <div class="step-cards">
          <button class="choice-card" type="button" data-route="/hushall"><strong>1. Skapa hushåll</strong><br><span class="muted">Skapa eller välj hushåll med riktiga data.</span></button>
          <button class="choice-card" type="button" data-route="/personer"><strong>2. Lägg till personer</strong><br><span class="muted">Koppla hushållets personer.</span></button>
          <button class="choice-card" type="button" data-route="/inkomster"><strong>3. Fyll inkomster</strong><br><span class="muted">Skapa riktiga inkomster per person.</span></button>
          <button class="choice-card" type="button" data-route="/lan"><strong>4. Lägg till lån</strong><br><span class="muted">Samla skulder och månadskostnader.</span></button>
          <button class="choice-card" type="button" data-route="/kostnader"><strong>5. Lägg till återkommande kostnader</strong><br><span class="muted">Fasta poster och avbetalningar som inte är abonnemang.</span></button>
          <button class="choice-card" type="button" data-route="/abonnemang"><strong>6. Lägg till abonnemang</strong><br><span class="muted">Avtal, bindningar och granskningsdatum.</span></button>
          <button class="choice-card" type="button" data-route="/tillgangar"><strong>7. Lägg till tillgångar</strong><br><span class="muted">Konton, sparande och investeringar.</span></button>
          <button class="choice-card" type="button" data-route="/boendekalkyl"><strong>8. Skapa boendekalkyl</strong><br><span class="muted">Kalkyl mot riktiga kostnader.</span></button>
          <button class="choice-card" type="button" data-route="/rapporter"><strong>9. Generera rapport</strong><br><span class="muted">Skapa första riktiga snapshoten.</span></button>
        </div>
      </article>
    </section>
  `;
}

function detailCell(label, value) {
  return `<div class="detail-item"><label>${escapeHtml(label)}</label><div>${escapeHtml(String(value || "Ej angivet"))}</div></div>`;
}

function scenariosForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.scenarios.filter((item) => item.household_id === householdId);
}

function scenarioResultsForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.scenarioResults.filter((item) => item.household_id === householdId);
}

function reportsForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.reports.filter((item) => item.household_id === householdId);
}

function draftsForHousehold(householdId = state.selectedHouseholdId) {
  return state.data.drafts.filter((item) => item.household_id === householdId);
}

function selectedDocument() {
  return documentsForHousehold().find((item) => item.id === state.ui.selectedDocumentId) || null;
}

async function loadSelectedDocumentWorkflow(documentId = state.ui.selectedDocumentId) {
  if (!documentId) {
    state.ui.selectedDocumentWorkflow = null;
    state.ui.documentDraftSelections = {};
    return;
  }
  try {
    state.ui.selectedDocumentWorkflow = await request(`/documents/${documentId}/review`);
    syncDocumentDraftSelections();
  } catch (_err) {
    state.ui.selectedDocumentWorkflow = null;
    state.ui.documentDraftSelections = {};
  }
}

function syncDocumentDraftSelections() {
  const workflow = state.ui.selectedDocumentWorkflow;
  const selections = {};
  (workflow?.entity_resolutions || []).forEach((resolution) => {
    const draft = (workflow?.drafts || []).find((item) => item.id === resolution.draft_id);
    const reviewPayload = draft?.review_json || draft?.proposed_json || {};
    const hasVehicle = Boolean(reviewPayload.object_vehicle || reviewPayload.purpose);
    const bestLoan = resolution.loan_candidates?.[0];
    const bestVehicle = resolution.vehicle_candidates?.[0];
    selections[resolution.draft_id] = {
      loanAction: resolution.recommended_action === "manual_review" ? "" : (bestLoan?.recommended_action === "link_existing" ? "link_existing" : "create_new"),
      loanTargetId: bestLoan?.entity_id ? String(bestLoan.entity_id) : "",
      vehicleAction: hasVehicle ? (bestVehicle?.recommended_action === "link_existing" ? "link_existing" : (resolution.recommended_action === "manual_review" && bestVehicle ? "" : "create_new")) : "skip",
      vehicleTargetId: bestVehicle?.entity_id ? String(bestVehicle.entity_id) : "",
    };
  });
  state.ui.documentDraftSelections = selections;
}

function latestScenarioResult(scenarioId) {
  return scenarioResultsForHousehold()
    .filter((item) => item.scenario_id === scenarioId)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] || null;
}

function buildDocumentApplySummary(draft, action, response, document) {
  const payload = documentSummaryPayload(draft);
  const items = [];
  if (action === "link_existing") {
    items.push(`Kopplade till befintligt lån #${response.target_entity_id}.`);
  } else {
    items.push(`Skapade ny kanonisk post för ${draftTargetLabel(draft.target_entity_type).toLowerCase()}.`);
  }
  if (payload.lender || document?.issuer) {
    items.push(`Långivare: ${payload.lender || document.issuer}.`);
  }
  if (payload.object_vehicle || payload.purpose) {
    items.push(`Objekt / fordon: ${payload.object_vehicle || payload.purpose}.`);
  }
  if (payload.required_monthly_payment || payload.payment_amount) {
    items.push(`Månadskostnad: ${money(payload.required_monthly_payment || payload.payment_amount)}.`);
  }
  if (payload.current_balance || payload.debt_before_amortization) {
    items.push(`Skuld före amortering: ${money(payload.current_balance || payload.debt_before_amortization)}.`);
  }
  if (response.target_entity_type && response.target_entity_id) {
    items.push(`Kanonisk koppling: ${response.target_entity_type} #${response.target_entity_id}.`);
  }
  items.push(`Dokumentstatus: ${documentWorkflowStatusLabel(selectedDocumentWorkflow()?.workflow_status || document?.extraction_status || "applied")}.`);
  return {
    title: `${draftTargetLabel(draft.target_entity_type)} applicerat`,
    description: document?.file_name || `Dokument #${draft.document_id}`,
    items,
  };
}

function summarizeDocumentDraftForConfirm(draft, action, targetEntityId = null) {
  const payload = documentSummaryPayload(draft);
  const selection = documentDraftSelectionFor(draft.id);
  const lines = [
    `Dokument: ${payload.provider || payload.lender || draft.document_id}`,
    `Objekt: ${payload.object_vehicle || payload.purpose || "inget objekt angivet"}`,
  ];
  if (action === "link_existing" && targetEntityId) {
    lines.push(`Koppla till lån #${targetEntityId}`);
  } else {
    lines.push(`Skapa ny ${draftTargetLabel(draft.target_entity_type).toLowerCase()}`);
  }
  if (selection.vehicleAction === "link_existing" && selection.vehicleTargetId) {
    lines.push(`Fordonskoppling: befintligt fordon #${selection.vehicleTargetId}`);
  } else if (selection.vehicleAction === "create_new") {
    lines.push("Fordonskoppling: skapa ny fordonspost");
  } else if (selection.vehicleAction === "skip") {
    lines.push("Fordonskoppling: hoppa över");
  }
  if (payload.required_monthly_payment || payload.payment_amount) {
    lines.push(`Månadskostnad: ${money(payload.required_monthly_payment || payload.payment_amount)}`);
  }
  if (payload.debt_before_amortization || payload.current_balance) {
    lines.push(`Skuld: ${money(payload.debt_before_amortization || payload.current_balance)}`);
  }
  return lines.join("\n");
}

function buildDocumentResolutionApplyPayload(workflow, draftId) {
  const draft = (workflow?.drafts || []).find((item) => item.id === draftId);
  if (!draft) {
    throw new Error("Utkastet hittades inte i dokumentflödet.");
  }
  const selection = documentDraftSelectionFor(draftId);
  if (!selection.loanAction) {
    throw new Error("Välj hur lånet ska hanteras innan du applicerar.");
  }
  if (selection.loanAction === "link_existing" && !selection.loanTargetId) {
    throw new Error("Välj vilket befintligt lån dokumentet ska kopplas till.");
  }
  if (selection.vehicleAction === "link_existing" && !selection.vehicleTargetId) {
    throw new Error("Välj vilket befintligt fordon dokumentet ska kopplas till.");
  }

  const payload = {
    draft_ids: [draftId],
    draft_actions: [
      {
        draft_id: draftId,
        action: selection.loanAction,
        ...(selection.loanAction === "link_existing" && selection.loanTargetId
          ? { target_entity_id: Number(selection.loanTargetId) }
          : {}),
      },
    ],
    related_actions: [],
  };

  if (selection.vehicleAction) {
    payload.related_actions.push({
      source_draft_id: draftId,
      entity_type: "vehicle",
      action: selection.vehicleAction,
      ...(selection.vehicleAction === "link_existing" && selection.vehicleTargetId
        ? { target_entity_id: Number(selection.vehicleTargetId) }
        : {}),
    });
  }

  return payload;
}

async function applyDocumentResolutionPackage(draftId) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const workflow = selectedDocumentWorkflow();
  const document = workflow?.document || selectedDocument();
  if (!workflow || !document) {
    throw new Error("Dokumentets granskningsvy kunde inte läsas in.");
  }
  const draft = (workflow.drafts || []).find((item) => item.id === draftId);
  if (!draft) {
    throw new Error("Utkastet hittades inte.");
  }

  const selection = documentDraftSelectionFor(draftId);
  const action = selection.loanAction === "link_existing" && selection.loanTargetId ? "link_existing" : "create_new";
  const targetId = action === "link_existing" ? Number(selection.loanTargetId) : null;
  const summaryLines = summarizeDocumentDraftForConfirm(draft, action, targetId);
  const confirmed = window.confirm(`Applicera följande?\n\n${summaryLines}`);
  if (!confirmed) return;

  const requestBody = buildDocumentResolutionApplyPayload(workflow, draftId);
  state.ui.documentApplyPending = true;
  render();

  try {
    const response = await request(`/documents/${document.id}/apply`, {
      method: "POST",
      body: JSON.stringify(requestBody),
    });
    await refreshAllData();
    state.ui.selectedDocumentId = document.id;
    state.ui.documentApplySummary = response.apply_summary;
    state.ui.selectedDocumentWorkflow = response.workflow;
    syncDocumentDraftSelections();
    state.ui.ingestResult = null;
    showToast("Dokumentpaketet applicerades.", "success");
    render();
  } finally {
    state.ui.documentApplyPending = false;
  }
}

async function applyDocumentDraft(draftId, action, targetEntityId = null) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const draft = state.data.drafts.find((item) => item.id === draftId);
  if (!draft) throw new Error("Utkastet hittades inte.");
  const document = state.data.documents.find((item) => item.id === draft.document_id) || null;
  const summaryLines = summarizeDocumentDraftForConfirm(draft, action, targetEntityId);
  const confirmed = window.confirm(`Applicera följande?\n\n${summaryLines}`);
  if (!confirmed) return;

  state.ui.documentApplyPending = true;
  render();

  const body = action === "link_existing"
    ? { action, target_entity_id: targetEntityId }
    : { action: "create_new" };

  try {
    const response = await request(`/extraction_drafts/${draftId}/apply`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    await refreshAllData();
    if (document?.id) {
      state.ui.selectedDocumentId = document.id;
      await loadSelectedDocumentWorkflow(document.id);
    }
    state.ui.documentApplySummary = buildDocumentApplySummary(draft, action, response, document);
    state.ui.ingestResult = null;
    showToast(action === "link_existing" ? "Utkastet kopplades till befintligt lån." : "Utkastet applicerades.", "success");
    render();
  } finally {
    state.ui.documentApplyPending = false;
  }
}

async function handlePageClick(event) {
  const routeTarget = event.target.closest("[data-route]");
  if (routeTarget) {
    navigateTo(pageConfigByPath(routeTarget.dataset.route).key);
    return;
  }

  if (await assistantWorkspace.handleAssistantClick(event)) {
    return;
  }

  const selectHouseholdTarget = event.target.closest("[data-select-household]");
  if (selectHouseholdTarget) {
    state.selectedHouseholdId = Number(selectHouseholdTarget.dataset.selectHousehold);
    persistSelection();
    await ensureSummaryLoaded();
    await loadAssistantWorkspace();
    render();
    return;
  }

  const editHouseholdTarget = event.target.closest("[data-edit-household]");
  if (editHouseholdTarget) {
    setEdit("household", households().find((item) => item.id === Number(editHouseholdTarget.dataset.editHousehold)) || selectedHousehold());
    render();
    return;
  }

  const openReportTarget = event.target.closest("[data-open-report]");
  if (openReportTarget) {
    state.ui.openReportId = Number(openReportTarget.dataset.openReport);
    render();
    return;
  }

  const deleteReportTarget = event.target.closest("[data-delete-report]");
  if (deleteReportTarget) {
    await request(`/report_snapshots/${Number(deleteReportTarget.dataset.deleteReport)}`, { method: "DELETE" });
    await refreshAllData();
    render();
    showToast("Rapporten togs bort.");
    return;
  }

  const applyDraftTarget = event.target.closest("[data-apply-draft]");
  if (applyDraftTarget) {
    await applyDocumentDraft(Number(applyDraftTarget.dataset.applyDraft), "create_new");
    return;
  }

  const selectDocumentTarget = event.target.closest("[data-action='select-document']");
  if (selectDocumentTarget) {
    state.ui.selectedDocumentId = Number(selectDocumentTarget.dataset.documentId);
    state.ui.documentApplySummary = null;
    await loadSelectedDocumentWorkflow();
    render();
    return;
  }

  const applyDraftCreateTarget = event.target.closest("[data-action='apply-draft-create']");
  if (applyDraftCreateTarget) {
    await applyDocumentDraft(Number(applyDraftCreateTarget.dataset.draftId), "create_new");
    return;
  }

  const applyDocumentResolutionTarget = event.target.closest("[data-action='apply-document-resolution']");
  if (applyDocumentResolutionTarget) {
    await applyDocumentResolutionPackage(Number(applyDocumentResolutionTarget.dataset.draftId));
    return;
  }

  const applyDraftLinkLoanTarget = event.target.closest("[data-action='apply-draft-link-loan']");
  if (applyDraftLinkLoanTarget) {
    const draftId = Number(applyDraftLinkLoanTarget.dataset.draftId);
    const select = document.querySelector(`select[name="${applyDraftLinkLoanTarget.dataset.selectName}"]`);
    const loanId = Number(select?.value || 0);
    if (!loanId) {
      showToast("Välj ett befintligt lån först.", "error");
      return;
    }
    await applyDocumentDraft(draftId, "link_existing", loanId);
    return;
  }

  const deleteDraftTarget = event.target.closest("[data-delete-draft]");
  if (deleteDraftTarget) {
    await request(`/extraction_drafts/${Number(deleteDraftTarget.dataset.deleteDraft)}`, { method: "DELETE" });
    await refreshAllData();
    render();
    showToast("Utkastet togs bort.");
    return;
  }

  const editDraftTarget = event.target.closest("[data-action='edit-draft']");
  if (editDraftTarget) {
    const draftId = Number(editDraftTarget.dataset.draftId);
    const draft = state.data.drafts.find((d) => d.id === draftId);
    state.ui.editingDraftId = draftId;
    state.ui.editingDraftJson = JSON.stringify(draft?.proposed_json || {}, null, 2);
    render();
    return;
  }

  const cancelEditTarget = event.target.closest("[data-action='cancel-draft-edit']");
  if (cancelEditTarget) {
    state.ui.editingDraftId = null;
    state.ui.editingDraftJson = null;
    render();
    return;
  }

  const saveEditTarget = event.target.closest("[data-action='save-draft-edit']");
  if (saveEditTarget) {
    const draftId = Number(saveEditTarget.dataset.draftId);
    const textarea = document.querySelector(`textarea[name="draft_edit_json_${draftId}"]`);
    if (!textarea) return;
    try {
      const newJson = JSON.parse(textarea.value);
      await request(`/extraction_drafts/${draftId}`, {
        method: "PUT",
        body: JSON.stringify({ proposed_json: newJson }),
      });
      state.ui.editingDraftId = null;
      state.ui.editingDraftJson = null;
      await refreshAllData();
      render();
      showToast("Utkastet uppdaterades.");
    } catch (err) {
      showToast(readError(err), "error");
    }
    return;
  }

  const deferDraftTarget = event.target.closest("[data-action='defer-draft']");
  if (deferDraftTarget) {
    const draftId = Number(deferDraftTarget.dataset.draftId);
    await request(`/extraction_drafts/${draftId}`, {
      method: "PUT",
      body: JSON.stringify({ status: "deferred" }),
    });
    await refreshAllData();
    render();
    showToast("Utkastet sköts upp.");
    return;
  }

  const deleteAliasTarget = event.target.closest("[data-action='delete-alias']");
  if (deleteAliasTarget) {
    const aliasId = Number(deleteAliasTarget.dataset.aliasId);
    await request(`/households/${state.selectedHouseholdId}/merchant_aliases/${aliasId}`, { method: "DELETE" });
    await refreshAllData();
    render();
    showToast("Alias borttaget.");
    return;
  }

  const runScenarioTarget = event.target.closest("[data-run-scenario]");
  if (runScenarioTarget) {
    await request(`/scenarios/${Number(runScenarioTarget.dataset.runScenario)}/run`, { method: "POST" });
    await refreshAllData();
    render();
    showToast("Scenariot kördes.");
    return;
  }

  const newHouseholdTarget = event.target.closest("[data-action='new-household']");
  if (newHouseholdTarget) {
    setEdit("household", null);
    navigateTo("household");
    return;
  }

  const navTarget = event.target.closest("[data-nav]");
  if (navTarget) {
    navigateTo(navTarget.dataset.nav);
    return;
  }

  const editTarget = event.target.closest("[data-edit]");
  if (editTarget) {
    const moduleKey = editTarget.dataset.edit;
    const item = findItemByModuleAndId(moduleKey, Number(editTarget.dataset.id));
    setEdit(moduleKey, item);
    if (moduleKey === "housing" && item) {
      await loadHousingEvaluation(item.id);
    }
    if (moduleKey === "scenario") {
      setEdit("scenario", state.data.scenarios.find((item) => item.id === Number(editTarget.dataset.id)) || null);
    }
    render();
    return;
  }

  const evaluateTarget = event.target.closest("[data-evaluate-housing]");
  if (evaluateTarget) {
    const scenarioId = Number(evaluateTarget.dataset.evaluateHousing);
    const item = housingForHousehold().find((scenario) => scenario.id === scenarioId);
    setEdit("housing", item);
    await loadHousingEvaluation(scenarioId);
    render();
    return;
  }

  const newTarget = event.target.closest("[data-action='new-record']");
  if (newTarget) {
    setEdit(newTarget.dataset.module, null);
    render();
    return;
  }

  const scanTarget = event.target.closest("[data-action='scan-opportunities']");
  if (scanTarget) {
    await scanOpportunities();
    return;
  }

  const promoteIngestTarget = event.target.closest("[data-action='promote-ingest']");
  if (promoteIngestTarget) {
    await promoteIngestSuggestions();
    return;
  }

  const clearIngestTarget = event.target.closest("[data-action='clear-ingest']");
  if (clearIngestTarget) {
    state.ui.ingestInput = "";
    state.ui.ingestKind = "text";
    state.ui.ingestDocumentId = null;
    state.ui.ingestSourceName = "";
    state.ui.ingestResult = null;
    state.ui.documentApplySummary = null;
    clearDocumentUploadPreview();
    render();
    return;
  }

  const prefillLoanTarget = event.target.closest("[data-action='prefill-loan-from-document']");
  if (prefillLoanTarget) {
    const document = state.data.documents.find((item) => item.id === Number(prefillLoanTarget.dataset.documentId));
    const workflow = state.ui.selectedDocumentWorkflow;
    const draft = workflow?.drafts?.[0];
    const payload = documentSummaryPayload(draft);
    setEdit("loan", {
      household_id: state.selectedHouseholdId,
      type: "car",
      purpose: payload.object_vehicle || payload.purpose || document?.issuer || "",
      lender: payload.lender || document?.issuer || "",
      current_balance: payload.current_balance ?? payload.debt_before_amortization ?? null,
      required_monthly_payment: payload.required_monthly_payment ?? payload.payment_amount ?? null,
      nominal_rate: payload.nominal_rate ?? payload.interest_rate ?? null,
      amortization_amount_monthly: payload.amortization_amount_monthly ?? payload.amortization ?? null,
      due_day: payload.payment_due_date ? new Date(payload.payment_due_date).getDate() : null,
      note: document?.file_name ? `Förifylld från ${document.file_name}` : "",
    });
    navigateTo("loans");
    return;
  }

  const prefillVehicleTarget = event.target.closest("[data-action='prefill-vehicle-from-document']");
  if (prefillVehicleTarget) {
    const document = state.data.documents.find((item) => item.id === Number(prefillVehicleTarget.dataset.documentId));
    const workflow = state.ui.selectedDocumentWorkflow;
    const draft = workflow?.drafts?.[0];
    const payload = documentSummaryPayload(draft);
    setEdit("vehicle", {
      household_id: state.selectedHouseholdId,
      make: payload.object_vehicle || payload.purpose || document?.issuer || "",
      model: "",
      note: document?.file_name ? `Förifylld från ${document.file_name}` : "",
    });
    navigateTo("vehicles");
    return;
  }

  const analyzeDocumentTarget = event.target.closest("[data-action='analyze-document']");
  if (analyzeDocumentTarget) {
    await analyzeStoredDocument(Number(analyzeDocumentTarget.dataset.documentId));
    return;
  }

  const resetTarget = event.target.closest("[data-reset-form]");
  if (resetTarget) {
    resetFormState(resetTarget.dataset.resetForm);
    render();
    return;
  }

  const deleteTarget = event.target.closest("[data-delete-form]");
  if (deleteTarget) {
    await deleteFromForm(deleteTarget.dataset.deleteForm);
  }
}

function handlePageInput(event) {
  if (assistantWorkspace.handleAssistantInput(event)) {
    return;
  }
  if (event.target.name === "ingest_input_text") {
    state.ui.ingestInput = event.target.value;
  } else if (event.target.name === "ingest_input_kind") {
    state.ui.ingestKind = event.target.value;
  } else if (event.target.name === "ingest_source_name") {
    state.ui.ingestSourceName = event.target.value;
  } else if (event.target.name && event.target.name.startsWith("document_resolution_loan_action_")) {
    const draftId = Number(event.target.name.replace("document_resolution_loan_action_", ""));
    setDocumentDraftSelection(draftId, "loanAction", event.target.value);
  } else if (event.target.name && event.target.name.startsWith("document_resolution_loan_target_")) {
    const draftId = Number(event.target.name.replace("document_resolution_loan_target_", ""));
    setDocumentDraftSelection(draftId, "loanTargetId", event.target.value);
  } else if (event.target.name && event.target.name.startsWith("document_resolution_vehicle_action_")) {
    const draftId = Number(event.target.name.replace("document_resolution_vehicle_action_", ""));
    setDocumentDraftSelection(draftId, "vehicleAction", event.target.value);
  } else if (event.target.name && event.target.name.startsWith("document_resolution_vehicle_target_")) {
    const draftId = Number(event.target.name.replace("document_resolution_vehicle_target_", ""));
    setDocumentDraftSelection(draftId, "vehicleTargetId", event.target.value);
  } else if (event.target.name === "file") {
    const file = event.target.files?.[0] || null;
    setDocumentUploadPreview(file);
  } else if (event.target.name && event.target.name.startsWith("draft_edit_json_")) {
    state.ui.editingDraftJson = event.target.value;
  }
}

async function handlePageSubmit(event) {
  event.preventDefault();
  const form = event.target;
  try {
    switch (form.id) {
      case "householdForm":
        await saveHousehold(form);
        break;
      case "personForm":
        await savePerson(form);
        break;
      case "incomeForm":
        await saveIncome(form);
        break;
      case "loanForm":
        await saveLoan(form);
        break;
      case "costForm":
        await saveRecurringCost(form);
        break;
      case "insuranceForm":
        await saveInsurance(form);
        break;
      case "subscriptionForm":
        await saveSubscription(form);
        break;
      case "vehicleForm":
        await saveVehicle(form);
        break;
      case "assetForm":
        await saveAsset(form);
        break;
      case "housingForm":
        await saveHousing(form);
        break;
      case "documentUploadForm":
        await uploadDocument(form);
        break;
      case "ingestAnalyzeForm":
        await analyzeIngestForm(form);
        break;
      case "merchantAliasForm":
        await saveMerchantAlias(form);
        break;
      case "scenarioForm":
        await saveScenario(form);
        break;
      case "reportGenerateForm":
        await generateReportSnapshot(form);
        break;
      case "assistantForm":
        await assistantWorkspace.askAssistant(form);
        break;
      case "loginForm":
        await handleLogin(form);
        break;
      case "registerForm":
        await handleRegister(form);
        break;
      default:
        return;
    }
  } catch (error) {
    showToast(readError(error), "error");
  }
}

function resetFormState(formId) {
  const map = {
    householdForm: "household",
    personForm: "person",
    incomeForm: "income",
    loanForm: "loan",
    costForm: "cost",
    insuranceForm: "insurance",
    subscriptionForm: "subscription",
    vehicleForm: "vehicle",
    assetForm: "asset",
    housingForm: "housing",
    scenarioForm: "scenario",
  };
  if (map[formId]) setEdit(map[formId], null);
}

async function deleteFromForm(formId) {
  const map = {
    householdForm: async () => {
      const household = currentEdit("household") || selectedHousehold();
      if (!household) return;
      await request(`/households/${household.id}`, { method: "DELETE" });
      state.selectedHouseholdId = null;
      persistSelection();
      clearEdits();
    },
    personForm: async () => deleteRecord("person", API.persons, currentEdit("person")),
    incomeForm: async () => deleteRecord("income", API.incomes, currentEdit("income")),
    loanForm: async () => deleteRecord("loan", API.loans, currentEdit("loan")),
    costForm: async () => deleteRecord("cost", API.recurringCosts, currentEdit("cost")),
    insuranceForm: async () => deleteRecord("insurance", API.insurancePolicies, currentEdit("insurance")),
    subscriptionForm: async () => deleteRecord("subscription", API.subscriptions, currentEdit("subscription")),
    vehicleForm: async () => deleteRecord("vehicle", API.vehicles, currentEdit("vehicle")),
    assetForm: async () => deleteRecord("asset", API.assets, currentEdit("asset")),
    housingForm: async () => deleteRecord("housing", API.housing, currentEdit("housing")),
    scenarioForm: async () => deleteRecord("scenario", API.scenarios, currentEdit("scenario")),
  };
  if (!map[formId]) return;
  await map[formId]();
  await refreshAllData();
  render();
  showToast("Posten togs bort.");
}

async function saveScenario(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const payload = {
    household_id: state.selectedHouseholdId,
    label: form.elements.label.value.trim(),
    change_set_json: JSON.parse(form.elements.change_set_json.value || "{}"),
  };
  const current = currentEdit("scenario");
  await saveByMode(current, API.scenarios, payload);
  setEdit("scenario", null);
  await refreshAllData();
  render();
  showToast(current?.id ? "Scenariot sparades." : "Scenariot skapades.");
}

async function generateReportSnapshot(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const assumptionRaw = form.elements.assumption_json.value.trim();
  const payload = {
    type: form.elements.type.value,
    as_of_date: form.elements.as_of_date.value,
    assumption_json: assumptionRaw ? JSON.parse(assumptionRaw) : {},
  };
  const report = await request(`/households/${state.selectedHouseholdId}/report_snapshots/generate`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.ui.openReportId = report.id;
  await refreshAllData();
  render();
  showToast("Rapporten genererades.");
}

async function analyzeStoredDocument(documentId) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const document = state.data.documents.find((item) => item.id === documentId);
  if (!document?.extracted_text) {
    throw new Error("Dokumentet saknar extraherbar text. För den här filen lyckades varken textlager eller OCR ge ett användbart underlag.");
  }
  const sourceChannel = (document.mime_type || "").toLowerCase() === "application/pdf" ? "uploaded_pdf" : "uploaded_document";
  state.ui.ingestPending = true;
  state.ui.ingestResult = null;
  state.ui.documentApplySummary = null;
  render();
  try {
    const response = await request(`/households/${state.selectedHouseholdId}${API.ingestAnalyze}`, {
      method: "POST",
      body: JSON.stringify({
        document_id: documentId,
        input_kind: sourceChannel,
        source_channel: sourceChannel,
        source_name: document.issuer || document.file_name || null,
      }),
    });
    state.ui.ingestDocumentId = documentId;
    state.ui.ingestKind = sourceChannel;
    state.ui.ingestSourceName = document.issuer || document.file_name || "";
    state.ui.ingestInput = document.extracted_text;
    state.ui.ingestResult = response;
    state.ui.selectedDocumentId = documentId;
    await loadSelectedDocumentWorkflow(documentId);
    showToast("Dokumenttexten analyserades i Data-In.");
  } finally {
    state.ui.ingestPending = false;
    render();
  }
}

async function analyzeIngestForm(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const inputText = form.elements.ingest_input_text.value.trim();
  if (!inputText) throw new Error("Klistra in råtext innan du kör AI-analysen.");
  const inputKind = form.elements.ingest_input_kind.value;
  state.ui.ingestPending = true;
  state.ui.ingestResult = null;
  state.ui.documentApplySummary = null;
  render();
  try {
    const response = await request(`/households/${state.selectedHouseholdId}${API.ingestAnalyze}`, {
      method: "POST",
      body: JSON.stringify({
        input_text: inputText,
        input_kind: inputKind,
        source_channel: inputKind,
        source_name: form.elements.ingest_source_name.value.trim() || null,
      }),
    });
    state.ui.ingestDocumentId = null;
    state.ui.ingestKind = inputKind;
    state.ui.ingestSourceName = form.elements.ingest_source_name.value.trim();
    state.ui.ingestInput = inputText;
    state.ui.ingestResult = response;
    showToast("AI-analysen är klar. Granska förslagen innan du skapar reviewutkast.");
  } finally {
    state.ui.ingestPending = false;
    render();
  }
}

async function promoteIngestSuggestions() {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  if (!state.ui.ingestResult) throw new Error("Kör en AI-analys först.");
  state.ui.ingestPromoting = true;
  render();
  try {
    const ingestResult = normalizeIngestResult(state.ui.ingestResult);
    const response = await request(`/households/${state.selectedHouseholdId}${API.ingestPromote}`, {
      method: "POST",
      body: JSON.stringify({
        analysis_result_id: ingestResult.analysisResultId,
        input_text: state.ui.ingestInput,
        input_kind: state.ui.ingestKind,
        source_channel: state.ui.ingestKind,
        document_id: state.ui.ingestDocumentId,
        source_name: state.ui.ingestSourceName || null,
        provider: ingestResult.provider,
        model: ingestResult.model,
        detected_kind: ingestResult.documentType,
        document_summary: state.ui.ingestResult.document_summary || null,
        suggestions: ingestResult.suggestions,
      }),
    });
    await refreshAllData();
    if (response.document_id) {
      state.ui.selectedDocumentId = response.document_id;
      await loadSelectedDocumentWorkflow(response.document_id);
    }
    state.ui.ingestResult = null;
    state.ui.ingestInput = "";
    state.ui.ingestDocumentId = null;
    state.ui.documentApplySummary = null;
    showToast(`Skapade ${response.created_drafts.length} reviewutkast.`);
  } finally {
    state.ui.ingestPromoting = false;
    render();
  }
}

async function saveMerchantAlias(form) {
  if (!selectedHousehold()) throw new Error("Välj hushåll först.");
  const alias = form.elements.alias_name.value.trim();
  const canonical = form.elements.canonical_name.value.trim();
  const hint = form.elements.category_hint.value.trim() || null;
  if (!alias || !canonical) throw new Error("Fyll i alias och kanoniskt namn.");
  await request(`/households/${state.selectedHouseholdId}/merchant_aliases`, {
    method: "POST",
    body: JSON.stringify({ household_id: state.selectedHouseholdId, alias, canonical_name: canonical, category_hint: hint }),
  });
  form.reset();
  await refreshAllData();
  render();
  showToast("Alias tillagt.");
}

async function askAssistant(form) {
  return assistantWorkspace.askAssistant(form);
}

function findItemByModuleAndId(moduleKey, id) {
  const collections = {
    person: peopleForHousehold(),
    income: incomesForHousehold(),
    loan: loansForHousehold(),
    cost: recurringCostsForHousehold(),
    insurance: insuranceForHousehold(),
    subscription: subscriptionsForHousehold(),
    vehicle: vehiclesForHousehold(),
    asset: assetsForHousehold(),
    housing: housingForHousehold(),
    scenario: scenariosForHousehold(),
  };
  return collections[moduleKey]?.find((item) => item.id === id) || null;
}
