export const state = {
  page: localStorage.getItem("he_page") || "overview",
  selectedHouseholdId: Number(localStorage.getItem("he_household_id") || "") || null,
  data: {
    households: [],
    persons: [],
    incomes: [],
    recurringCosts: [],
    loans: [],
    subscriptions: [],
    insurancePolicies: [],
    vehicles: [],
    assets: [],
    housing: [],
    documents: [],
    opportunities: [],
    drafts: [],
    scenarios: [],
    scenarioResults: [],
    reports: [],
    merchantAliases: [],
  },
  summary: null,
  housingEvaluation: null,
  editing: {
    household: null,
    person: null,
    income: null,
    loan: null,
    cost: null,
    insurance: null,
    subscription: null,
    vehicle: null,
    asset: null,
    housing: null,
    scenario: null,
  },
  ui: {
    sidebarOpen: false,
    openReportId: null,
    selectedDocumentId: null,
    selectedDocumentWorkflow: null,
    documentDraftSelections: {},
    documentApplyPending: false,
    documentLinkLoanId: "",
    documentUploadPreview: null,
    documentApplySummary: null,
    assistantMessages: [],
    assistantThreadLoading: false,
    assistantAnalysis: null,
    assistantAnalysisLoading: false,
    assistantInput: "",
    assistantPending: false,
    assistantMobileSummaryOpen: false,
    assistantDismissedIntentIds: [],
    ingestInput: "",
    ingestKind: "text",
    ingestDocumentId: null,
    ingestSourceName: "",
    ingestPending: false,
    ingestPromoting: false,
    ingestResult: null,
    editingDraftId: null,
    editingDraftJson: null,
  },
};

export const els = {};

export function persistSelection() {
  if (state.selectedHouseholdId) {
    localStorage.setItem("he_household_id", String(state.selectedHouseholdId));
  } else {
    localStorage.removeItem("he_household_id");
  }
}

export function persistPage() {
  localStorage.setItem("he_page", state.page);
}
