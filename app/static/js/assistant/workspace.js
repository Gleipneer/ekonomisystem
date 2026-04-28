export function createAssistantWorkspace({
  API,
  state,
  request,
  render,
  showToast,
  readError,
  selectedHousehold,
  refreshAllData,
}) {
  function friendlyApplyError(error) {
    const text = String(readError(error) || "");
    if (text.includes("Saknar entity_type, entity_id eller updates")) {
      return "Ändringen saknar tillräcklig information för att kunna sparas.";
    }
    if (text.includes("matchar flera entiteter")) {
      return "Förslaget matchar flera poster. Välj en mer specifik ändring.";
    }
    if (text.includes("redan applicerats")) {
      return "Den här ändringen är redan sparad.";
    }
    return text;
  }

  function scheduleAssistantScrollToBottom() {
    requestAnimationFrame(() => {
      const log = document.querySelector(".chat-log:not(.hidden)");
      if (!log) return;
      log.scrollTop = log.scrollHeight;
    });
  }

  function updateAssistantLogBottomOffset() {
    requestAnimationFrame(() => {
      const composer = document.querySelector(".central-composer");
      const log = document.querySelector(".chat-log:not(.hidden)");
      if (!composer || !log) return;
      const safeInset = 24;
      const targetPadding = Math.ceil(composer.offsetHeight + safeInset);
      log.style.setProperty("--assistant-log-bottom-offset", `${targetPadding}px`);
    });
  }

  function mapAssistantThreadMessages(messages) {
    const appliedSourceIds = new Set(
      messages
        .filter((message) => message.role === "system" && message.content_json?.applied && message.content_json?.source_message_id)
        .map((message) => message.content_json.source_message_id),
    );

    return messages.map((message) => {
      const meta = message.content_json || {};
      return {
        id: message.id,
        role: message.role,
        message_type: message.message_type,
        content: message.content_text,
        questions: Array.isArray(meta.questions) ? meta.questions : [],
        write_intent: meta.write_intent || null,
        provider: meta.provider || null,
        model: meta.model || null,
        usage: meta.usage || null,
        intent_applied: appliedSourceIds.has(message.id),
        content_json: meta,
      };
    });
  }

  async function loadAssistantThread({ renderAfter = false } = {}) {
    if (!state.selectedHouseholdId) {
      state.ui.assistantMessages = [];
      state.ui.assistantThreadLoading = false;
      if (renderAfter) render();
      return;
    }

    const householdId = state.selectedHouseholdId;
    state.ui.assistantThreadLoading = true;
    if (renderAfter) render();
    try {
      const thread = await request(`/households/${householdId}${API.assistantThread}`);
      if (state.selectedHouseholdId !== householdId) return;
      state.ui.assistantMessages = mapAssistantThreadMessages(thread.messages || []);
      updateAssistantLogBottomOffset();
      scheduleAssistantScrollToBottom();
    } catch (error) {
      if (state.selectedHouseholdId === householdId) {
        showToast(readError(error), "error");
      }
    } finally {
      if (state.selectedHouseholdId === householdId) {
        state.ui.assistantThreadLoading = false;
        if (renderAfter) render();
      }
    }
  }

  async function loadAssistantAnalysis({ renderAfter = false } = {}) {
    if (!state.selectedHouseholdId) {
      state.ui.assistantAnalysis = null;
      state.ui.assistantAnalysisLoading = false;
      if (renderAfter) render();
      return;
    }

    const householdId = state.selectedHouseholdId;
    state.ui.assistantAnalysisLoading = true;
    if (renderAfter) render();
    try {
      const analysis = await request(`/households/${householdId}${API.assistantAnalysis}`);
      if (state.selectedHouseholdId !== householdId) return;
      state.ui.assistantAnalysis = analysis;
    } catch (error) {
      if (state.selectedHouseholdId === householdId) {
        showToast(readError(error), "error");
      }
    } finally {
      if (state.selectedHouseholdId === householdId) {
        state.ui.assistantAnalysisLoading = false;
        if (renderAfter) render();
      }
    }
  }

  async function loadAssistantWorkspace({ renderAfter = false } = {}) {
    await Promise.all([
      loadAssistantThread({ renderAfter }),
      loadAssistantAnalysis({ renderAfter }),
    ]);
  }

  async function applyAssistantIntentById(messageId) {
    const msg = state.ui.assistantMessages.find((item) => item.id === messageId);
    if (!msg || !msg.write_intent) return;
    if (!Number.isInteger(msg.id) || (msg.questions || []).length || (msg.write_intent.missing_fields || []).length) {
      showToast("Förslaget kan inte sparas förrän det är komplett och hämtat från sparad chatthistorik.", "error");
      return;
    }
    msg.intent_applied = true;
    msg.intent_apply_loading = true;
    render();
    try {
      await request(`/households/${state.selectedHouseholdId}/assistant/apply_intent`, {
        method: "POST",
        body: JSON.stringify({ source_message_id: msg.id || null }),
      });
      await refreshAllData();
      await loadAssistantWorkspace();
      render();
      scheduleAssistantScrollToBottom();
      updateAssistantLogBottomOffset();
      showToast("Systemändringen sparades.");
    } catch (error) {
      msg.intent_applied = false;
      msg.intent_apply_loading = false;
      showToast(`Kunde inte spara: ${friendlyApplyError(error)}`, "error");
      render();
    } finally {
      msg.intent_apply_loading = false;
    }
  }

  async function resetAssistantThread() {
    if (!state.selectedHouseholdId) return;
    await request(`/households/${state.selectedHouseholdId}${API.assistantThread}/reset`, {
      method: "POST",
    });
    state.ui.assistantMessages = [];
    await loadAssistantWorkspace();
    render();
    showToast("Ny assistenttråd skapad.");
  }

  async function askAssistant(form) {
    if (!selectedHousehold()) throw new Error("Välj hushåll först.");
    const prompt = form.elements.prompt.value.trim();
    const files = Array.from(form.elements.files?.files || []);
    if (!prompt && !files.length) return;

    const pendingMessage = {
      role: "user",
      content: prompt || `Laddade upp ${files.length} fil${files.length === 1 ? "" : "er"} i assistenten.`,
      message_type: "user_prompt",
    };
    state.ui.assistantMessages.push(pendingMessage);
    state.ui.assistantPending = true;
    render();

    try {
      let response;
      if (files.length) {
        const formData = new FormData();
        if (prompt) formData.set("prompt", prompt);
        for (const file of files) {
          formData.append("files", file);
        }
        response = await request(`/households/${state.selectedHouseholdId}${API.assistantImportFiles}`, {
          method: "POST",
          body: formData,
          headers: {},
        });
      } else {
        response = await request(`/households/${state.selectedHouseholdId}${API.assistant}`, {
          method: "POST",
          body: JSON.stringify({ prompt, conversation: [] }),
        });
      }

      state.ui.assistantMessages.push({
        role: "assistant",
        content: response.answer,
        questions: response.questions,
        write_intent: response.write_intent,
        provider: response.provider,
        model: response.model,
        usage: response.usage,
      });
      state.ui.assistantInput = "";
      form.reset();
      await loadAssistantWorkspace();
      scheduleAssistantScrollToBottom();
      updateAssistantLogBottomOffset();
    } catch (error) {
      state.ui.assistantMessages = state.ui.assistantMessages.filter((message) => message !== pendingMessage);
      throw error;
    } finally {
      state.ui.assistantPending = false;
      render();
    }
  }

  function handleAssistantClick(event) {
    const summaryToggle = event.target.closest("[data-action='toggle-assistant-summary']");
    if (summaryToggle) {
      state.ui.assistantMobileSummaryOpen = !state.ui.assistantMobileSummaryOpen;
      render();
      return Promise.resolve(true);
    }

    const dismissTarget = event.target.closest("[data-action='dismiss-assistant-intent']");
    if (dismissTarget) {
      const messageId = Number(dismissTarget.dataset.messageId);
      const existing = Array.isArray(state.ui.assistantDismissedIntentIds) ? state.ui.assistantDismissedIntentIds : [];
      state.ui.assistantDismissedIntentIds = existing.includes(messageId)
        ? existing
        : [...existing, messageId];
      render();
      return Promise.resolve(true);
    }

    const resetTarget = event.target.closest("[data-action='reset-assistant-thread']");
    if (resetTarget) {
      return resetAssistantThread().then(() => true);
    }

    const applyTarget = event.target.closest("[data-action='apply-assistant-intent']");
    if (applyTarget) {
      const messageId = Number(applyTarget.dataset.messageId);
      return applyAssistantIntentById(messageId).then(() => true);
    }

    const promptTarget = event.target.closest("[data-prompt]");
    if (promptTarget) {
      state.ui.assistantInput = promptTarget.dataset.prompt;
      render();
      return Promise.resolve(true);
    }

    return Promise.resolve(false);
  }

  function handleAssistantInput(event) {
    if (event.target.name === "prompt") {
      state.ui.assistantInput = event.target.value;
      updateAssistantLogBottomOffset();
      return true;
    }
    return false;
  }

  function resetAssistantWorkspaceState(householdSelected) {
    state.ui.assistantMessages = [];
    state.ui.assistantThreadLoading = Boolean(householdSelected);
    state.ui.assistantAnalysis = null;
    state.ui.assistantAnalysisLoading = Boolean(householdSelected);
    state.ui.assistantInput = "";
    state.ui.assistantPending = false;
    state.ui.assistantMobileSummaryOpen = false;
    state.ui.assistantDismissedIntentIds = [];
  }

  return {
    askAssistant,
    applyAssistantIntentById,
    handleAssistantClick,
    handleAssistantInput,
    loadAssistantAnalysis,
    loadAssistantThread,
    loadAssistantWorkspace,
    mapAssistantThreadMessages,
    resetAssistantThread,
    resetAssistantWorkspaceState,
    updateAssistantLogBottomOffset,
  };
}
