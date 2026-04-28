import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { createAssistantRenderer } from "../../app/static/js/assistant/render.js";
import { createAssistantWorkspace } from "../../app/static/js/assistant/workspace.js";
import { createNavigationController } from "../../app/static/js/shell/navigation.js";

test("assistant workspace maps persisted messages and applied confirmations", () => {
  const state = {
    selectedHouseholdId: 1,
    ui: {
      assistantMessages: [],
      assistantThreadLoading: false,
      assistantAnalysis: null,
      assistantAnalysisLoading: false,
      assistantInput: "",
      assistantPending: false,
    },
  };

  const workspace = createAssistantWorkspace({
    API: { assistantThread: "/assistant/thread", assistantAnalysis: "/analysis", assistantImportFiles: "/assistant/import_files", assistant: "/assistant/respond" },
    state,
    request: async () => { throw new Error("not needed"); },
    render: () => {},
    showToast: () => {},
    readError: (error) => error.message,
    selectedHousehold: () => ({ id: 1 }),
    refreshAllData: async () => {},
  });

  const mapped = workspace.mapAssistantThreadMessages([
    {
      id: 10,
      role: "assistant",
      message_type: "assistant_response",
      content_text: "Förslag",
      content_json: { write_intent: { intent: "create_expense", data: { amount: 400 } } },
    },
    {
      id: 11,
      role: "system",
      message_type: "system_confirmation",
      content_text: "Sparat",
      content_json: { applied: true, source_message_id: 10, result: { entity_type: "recurring_cost", entity_id: 7 } },
    },
  ]);

  assert.equal(mapped[0].intent_applied, true);
  assert.equal(mapped[1].content_json.result.entity_id, 7);
});

test("assistant workspace reset keeps persistent and transient assistant state separate", () => {
  const state = {
    selectedHouseholdId: 1,
    ui: {
      assistantMessages: [{ id: 1 }],
      assistantThreadLoading: false,
      assistantAnalysis: { household_id: 1 },
      assistantAnalysisLoading: false,
      assistantInput: "Hej",
      assistantPending: true,
    },
  };

  const workspace = createAssistantWorkspace({
    API: {},
    state,
    request: async () => null,
    render: () => {},
    showToast: () => {},
    readError: (error) => error.message,
    selectedHousehold: () => ({ id: 1 }),
    refreshAllData: async () => {},
  });

  workspace.resetAssistantWorkspaceState(true);

  assert.deepEqual(state.ui.assistantMessages, []);
  assert.equal(state.ui.assistantThreadLoading, true);
  assert.equal(state.ui.assistantAnalysis, null);
  assert.equal(state.ui.assistantPending, false);
});

test("assistant renderer emits deterministic rail and intent affordances", () => {
  const state = {
    ui: {
      assistantAnalysisLoading: false,
      assistantAnalysis: {
        alerts: [{ title: "Tryck fram till lön", message: "Marginalen är låg.", severity: "warning" }],
        action_primitives: [{ title: "Invänta löning", description: "Vänta med större köp." }],
        presentation: {
          headline_metrics: [{ label: "Kassaflöde", value: "3 000 kr", tone: "success", detail: "Spargrad 10 %" }],
          summary_primitives: [{ title: "Efter bundna kostnader", value: "5 000 kr", tone: "neutral" }],
        },
      },
      assistantMessages: [{
        id: 2,
        role: "assistant",
        message_type: "assistant_response",
        content: "Här är ett förslag.",
        questions: ["Vilken månad gäller det?"],
        write_intent: { intent: "create_expense", data: { vendor: "ICA", amount: 400 }, missing_fields: [] },
        provider: "openai",
        model: "gpt-test",
        usage: { total_tokens: 18 },
        content_json: {},
      }],
      assistantInput: "",
      assistantPending: false,
      assistantThreadLoading: false,
    },
  };

  const renderer = createAssistantRenderer({
    state,
    escapeHtml: (value) => String(value),
    selectedHousehold: () => ({ id: 1 }),
    renderPageHeader: (title) => `<header>${title}</header>`,
    renderAssistantMarkdown: (text) => `<p>${text}</p>`,
  });

  const pageHtml = renderer.renderAssistantPage();

  assert.match(pageHtml, /Deterministisk motor/);
  assert.doesNotMatch(pageHtml, /data-action="apply-assistant-intent"/);
  assert.match(pageHtml, /Vilken månad gäller det\?/);
  assert.match(pageHtml, /Besvara frågorna innan åtgärden kan sparas/);
});

test("assistant renderer shows apply CTA for complete intent", () => {
  const state = {
    ui: {
      assistantAnalysisLoading: false,
      assistantAnalysis: null,
      assistantMessages: [{
        id: 55,
        role: "assistant",
        message_type: "assistant_response",
        content: "Klar ändring.",
        questions: [],
        write_intent: { intent: "update_entity", target_entity_type: "recurring_cost", data: { entity_id: 9, updates: { amount: 10000 } }, missing_fields: [] },
        provider: "openai",
        model: "gpt-test",
        usage: null,
        content_json: {},
      }],
      assistantInput: "",
      assistantPending: false,
      assistantThreadLoading: false,
      assistantMobileSummaryOpen: false,
      assistantDismissedIntentIds: [],
    },
  };
  const renderer = createAssistantRenderer({
    state,
    escapeHtml: (value) => String(value),
    selectedHousehold: () => ({ id: 1 }),
    renderPageHeader: (title) => `<header>${title}</header>`,
    renderAssistantMarkdown: (text) => `<p>${text}</p>`,
  });
  const pageHtml = renderer.renderAssistantPage();
  assert.match(pageHtml, /Godkänn och spara/);
  assert.match(pageHtml, /Kräver godkännande/);
  assert.match(pageHtml, /Visa teknisk information/);
  assert.match(pageHtml, /Återkommande kostnad|Boende/);
});

test("assistant workspace apply posts source_message_id", async () => {
  const requests = [];
  const state = {
    selectedHouseholdId: 1,
    ui: {
      assistantMessages: [{
        id: 42,
        role: "assistant",
        message_type: "assistant_response",
        content: "Förslag",
        questions: [],
        write_intent: { intent: "create_expense", target_entity_type: "recurring_cost", data: { category: "boende", amount: 10000, frequency: "monthly" }, missing_fields: [] },
      }],
      assistantThreadLoading: false,
      assistantAnalysis: null,
      assistantAnalysisLoading: false,
      assistantInput: "",
      assistantPending: false,
      assistantMobileSummaryOpen: false,
      assistantDismissedIntentIds: [],
    },
  };
  const workspace = createAssistantWorkspace({
    API: { assistantThread: "/assistant/thread", assistantAnalysis: "/analysis", assistantImportFiles: "/assistant/import_files", assistant: "/assistant/respond" },
    state,
    request: async (url, options = {}) => {
      requests.push({ url, options });
      if (url.endsWith("/assistant/apply_intent")) return { status: "success" };
      if (url.endsWith("/assistant/thread")) return { messages: [] };
      if (url.endsWith("/analysis")) return {};
      return {};
    },
    render: () => {},
    showToast: () => {},
    readError: (error) => error.message,
    selectedHousehold: () => ({ id: 1 }),
    refreshAllData: async () => {},
  });

  await workspace.applyAssistantIntentById(42);
  const applyCall = requests.find((entry) => entry.url.endsWith("/assistant/apply_intent"));
  assert.ok(applyCall);
  const payload = JSON.parse(applyCall.options.body);
  assert.equal(payload.source_message_id, 42);
  assert.equal(Object.prototype.hasOwnProperty.call(payload, "intent"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(payload, "data"), false);
});

test("assistant renderer keeps technical json collapsed by default", () => {
  const state = {
    ui: {
      assistantAnalysisLoading: false,
      assistantAnalysis: null,
      assistantMessages: [{
        id: 77,
        role: "assistant",
        message_type: "assistant_response",
        content: "Kolla diff",
        questions: [],
        write_intent: { intent: "update_entity", target_entity_type: "recurring_cost", data: { entity_id: 1, updates: { monthly_amount: 10000 } }, missing_fields: [] },
        provider: "openai",
        model: "gpt-test",
        usage: null,
        content_json: {},
      }],
      assistantInput: "",
      assistantPending: false,
      assistantThreadLoading: false,
      assistantMobileSummaryOpen: false,
      assistantDismissedIntentIds: [],
    },
  };
  const renderer = createAssistantRenderer({
    state,
    escapeHtml: (value) => String(value),
    selectedHousehold: () => ({ id: 1 }),
    renderPageHeader: (title) => `<header>${title}</header>`,
    renderAssistantMarkdown: (text) => `<p>${text}</p>`,
  });
  const html = renderer.renderAssistantPage();
  assert.match(html, /<details class="intent-json-details">/);
  assert.match(html, /Visa teknisk information/);
  assert.match(html, /Månadsbelopp/);
});

test("assistant renderer hides apply button when missing fields", () => {
  const state = {
    ui: {
      assistantAnalysisLoading: false,
      assistantAnalysis: null,
      assistantMessages: [{
        id: 78,
        role: "assistant",
        message_type: "assistant_response",
        content: "Behöver mer info",
        questions: [],
        write_intent: { intent: "create_expense", target_entity_type: "recurring_cost", data: { vendor: "Okänd" }, missing_fields: ["amount"] },
        provider: "openai",
        model: "gpt-test",
        usage: null,
        content_json: {},
      }],
      assistantInput: "",
      assistantPending: false,
      assistantThreadLoading: false,
      assistantMobileSummaryOpen: false,
      assistantDismissedIntentIds: [],
    },
  };
  const renderer = createAssistantRenderer({
    state,
    escapeHtml: (value) => String(value),
    selectedHousehold: () => ({ id: 1 }),
    renderPageHeader: (title) => `<header>${title}</header>`,
    renderAssistantMarkdown: (text) => `<p>${text}</p>`,
  });
  const html = renderer.renderAssistantPage();
  assert.doesNotMatch(html, /data-action="apply-assistant-intent"/);
  assert.match(html, /Behöver mer information/);
});

test("navigation controller resolves routes without split assistant ownership", () => {
  const controller = createNavigationController({
    PAGES: [
      { key: "assistant", label: "Ekonomiassistent", path: "/ekonomiassistent" },
      { key: "overview", label: "Översikt", path: "/" },
    ],
    state: { page: "overview", selectedHouseholdId: 1 },
    els: { nav: { innerHTML: "" }, assistantNav: { innerHTML: "" }, dateStamp: { textContent: "" } },
    persistPage: () => {},
    render: () => {},
    loadAssistantWorkspace: async () => {},
  });

  assert.equal(controller.pageConfigByPath("/ekonomiassistent").key, "assistant");
  assert.equal(controller.pageConfigByPath("/unknown").key, "overview");
});

test("mobile composer styles reserve bottom space for chat log", () => {
  const css = readFileSync(new URL("../../app/static/styles.css", import.meta.url), "utf8");
  assert.match(css, /--assistant-log-bottom-offset/);
  assert.match(css, /padding-bottom: var\(--assistant-log-bottom-offset/);
  assert.match(css, /@media \(max-width: 768px\)/);
});
