export function createNavigationController({
  PAGES,
  state,
  els,
  persistPage,
  render,
  loadAssistantWorkspace,
}) {
  const pages = Array.isArray(PAGES) ? PAGES : [];
  const pageByKey = new Map(pages.map((page) => [page.key, page]));

  function pageConfigByKey(key) {
    return pageByKey.get(key) || pages[0] || { key: "overview", path: "/" };
  }

  function pageConfigByPath(pathname) {
    const path = typeof pathname === "string" && pathname ? pathname : "/";
    const direct = pages.find((page) => page.path === path);
    if (direct) return direct;
    return pageConfigByKey("overview");
  }

  function navigateTo(pageKey, historyMode = "push") {
    const target = pageConfigByKey(pageKey);
    if (!target) return;
    state.page = target.key;
    persistPage();
    if (target.key === "assistant" && typeof loadAssistantWorkspace === "function") {
      Promise.resolve(loadAssistantWorkspace({ renderAfter: false })).catch(() => {});
    }
    if (historyMode !== "none" && typeof window !== "undefined" && window.history) {
      const method = historyMode === "replace" ? "replaceState" : "pushState";
      window.history[method]({}, "", target.path || "/");
    }
    render();
  }

  function renderTopbar(currentMonthLabel = "") {
    if (els?.dateStamp) {
      els.dateStamp.textContent = currentMonthLabel || "";
    }
  }

  function renderNav(selectedHousehold) {
    const canUsePages = Boolean(selectedHousehold);
    const html = pages
      .map((page) => {
        const active = state.page === page.key ? "active" : "";
        const disabled = !canUsePages && page.key !== "overview" ? "disabled" : "";
        return `<button type="button" class="nav-item ${active}" data-page="${page.key}" ${disabled}>${page.label}</button>`;
      })
      .join("");
    if (els?.nav) {
      els.nav.innerHTML = html;
    }
    if (els?.assistantNav) {
      els.assistantNav.innerHTML = "";
    }
  }

  return {
    pageConfigByKey,
    pageConfigByPath,
    navigateTo,
    renderTopbar,
    renderNav,
  };
}
