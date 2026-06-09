(() => {
  const configElement = document.getElementById("product-list-config");
  if (!configElement) {
    return;
  }

  let config = {};
  try {
    config = JSON.parse(configElement.textContent || "{}");
  } catch (error) {
    config = {};
  }

  const selectAll = document.querySelector("[data-bulk-select-all]");
  const checkboxes = Array.from(document.querySelectorAll("[data-bulk-product-id]"));
  const bulkConfirmButtons = Array.from(document.querySelectorAll("[data-bulk-confirm]"));
  const bulkForm = document.getElementById("product-bulk-form");
  const bulkActionFeedback = document.querySelector("[data-bulk-action-feedback]");
  const selectedCount = () => checkboxes.filter((checkbox) => checkbox.checked).length;
  const showBulkActionFeedback = (message) => {
    if (!bulkActionFeedback) {
      return;
    }
    bulkActionFeedback.textContent = message;
    bulkActionFeedback.hidden = false;
  };
  const updateBulkConfirmMessages = () => {
    const count = selectedCount();
    if (count && bulkActionFeedback) {
      bulkActionFeedback.hidden = true;
    }
    bulkConfirmButtons.forEach((button) => {
      const action = button.dataset.confirmAction || "操作";
      button.dataset.confirm = count
        ? `确认对选中的 ${count} 个产品执行${action}？`
        : "";
    });
  };
  selectAll?.addEventListener("change", () => {
    checkboxes.forEach((checkbox) => {
      checkbox.checked = selectAll.checked;
    });
    updateBulkConfirmMessages();
  });
  checkboxes.forEach((checkbox) => {
    checkbox.addEventListener("change", updateBulkConfirmMessages);
  });
  updateBulkConfirmMessages();
  bulkForm?.addEventListener("submit", (event) => {
    if (event.submitter instanceof HTMLElement && event.submitter.matches("[data-bulk-confirm]") && !selectedCount()) {
      event.preventDefault();
      showBulkActionFeedback("请先选择要操作的产品。");
    }
  });

  const storageKey = config.storageKey || "productListColumnState";
  const serverColumnState = config.columnState || {};
  const filterViewState = Array.isArray(config.filterViewState) ? config.filterViewState : [];
  const defaultExportFields = Array.isArray(config.defaultExportFields) ? config.defaultExportFields : [];
  const savedExportFields = Array.isArray(config.savedExportFields) ? config.savedExportFields : defaultExportFields;
  const table = document.querySelector("[data-product-list-table]");
  const exportDownload = document.querySelector("[data-export-download]");
  const exportFieldsModal = document.querySelector("[data-export-fields-modal]");
  const exportFieldsConfirm = document.querySelector("[data-export-fields-confirm]");
  const exportFieldsReset = document.querySelector("[data-export-fields-reset]");
  const settingsButton = document.querySelector("[data-column-settings-button]");
  const settingsPanel = document.querySelector("[data-column-settings-panel]");
  const settingsList = document.querySelector("[data-column-settings-list]");
  const resetButton = document.querySelector("[data-column-reset]");
  const pageStatus = document.querySelector("[data-page-status]");
  const allKeys = Array.from(document.querySelectorAll("[data-column-toggle]")).map((toggle) => toggle.dataset.columnToggle);
  const resizers = Array.from(document.querySelectorAll("[data-resize-column]"));
  const filterForm = document.querySelector("form.filter-panel");
  const filterViewNameInput = document.querySelector("[data-filter-view-name]");
  const filterViewSave = document.querySelector("[data-filter-view-save]");
  const widthWeights = {
    id: 0.5,
    product_name: 1.8,
    label_name: 1.8,
    msku_shipping_remark: 2,
    transfer_remark: 1.6,
    created_at: 1.2,
    updated_at: 1.2,
  };

  if (!table || !settingsButton || !settingsPanel || !settingsList) {
    return;
  }

  let preferenceFeedbackTimer = null;
  const showPreferenceFeedback = (message, type = "info", timeout = 2200) => {
    if (!pageStatus) {
      return;
    }
    window.clearTimeout(preferenceFeedbackTimer);
    pageStatus.textContent = message;
    pageStatus.hidden = false;
    pageStatus.classList.remove("page-status-success", "page-status-error");
    if (type === "success") {
      pageStatus.classList.add("page-status-success");
    }
    if (type === "error") {
      pageStatus.classList.add("page-status-error");
    }
    if (timeout > 0) {
      preferenceFeedbackTimer = window.setTimeout(() => {
        pageStatus.hidden = true;
        pageStatus.classList.remove("page-status-success", "page-status-error");
      }, timeout);
    }
  };

  const savePreference = (request, successMessage = "已保存。") => {
    showPreferenceFeedback("正在保存...", "info", 0);
    return request
      .then((response) => {
        if (response.ok) {
          showPreferenceFeedback(successMessage, "success");
        } else {
          showPreferenceFeedback("保存失败，请稍后重试。", "error");
        }
        return response;
      })
      .catch((error) => {
        showPreferenceFeedback("保存失败，请稍后重试。", "error");
        throw error;
      });
  };

  const selectedExportFields = () => {
    return Array.from(document.querySelectorAll("[data-export-field]:checked"))
      .map((field) => field.value);
  };

  const saveExportFields = () => {
    savePreference(fetch("/products/preferences/export-fields", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({fields: selectedExportFields()}),
    })).catch(() => {});
  };

  const buildExportUrl = () => {
    const url = new URL(exportDownload?.getAttribute("href") || "/products/export", window.location.origin);
    url.searchParams.delete("export_fields");
    selectedExportFields().forEach((field) => {
      url.searchParams.append("export_fields", field);
    });
    return `${url.pathname}${url.search}`;
  };

  let exportFieldsReturnFocus = null;

  const openExportFieldsModal = (trigger) => {
    if (!exportFieldsModal) {
      return;
    }
    exportFieldsReturnFocus = trigger instanceof HTMLElement ? trigger : null;
    exportFieldsModal.classList.remove("hidden");
    exportFieldsModal.setAttribute("aria-hidden", "false");
    document.body.classList.add("is-modal-open");
    exportFieldsConfirm?.focus();
  };

  const closeExportFieldsModal = () => {
    if (!exportFieldsModal) {
      return;
    }
    exportFieldsModal.classList.add("hidden");
    exportFieldsModal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("is-modal-open");
    exportFieldsReturnFocus?.focus();
    exportFieldsReturnFocus = null;
  };

  exportFieldsReset?.addEventListener("click", () => {
    document.querySelectorAll("[data-export-field]").forEach((field) => {
      field.checked = defaultExportFields.includes(field.value);
    });
    saveExportFields();
  });

  document.querySelectorAll("[data-export-field]").forEach((field) => {
    field.checked = savedExportFields.includes(field.value);
    field.addEventListener("change", saveExportFields);
  });

  exportDownload?.addEventListener("click", (event) => {
    event.preventDefault();
    openExportFieldsModal(exportDownload);
  });

  exportFieldsConfirm?.addEventListener("click", () => {
    if (!selectedExportFields().length) {
      showPreferenceFeedback("请至少选择一个导出字段。", "error");
      return;
    }
    showPreferenceFeedback("正在准备导出...", "info", 0);
    window.location.href = buildExportUrl();
  });

  document.querySelectorAll("[data-export-fields-cancel], [data-export-fields-dismiss]").forEach((element) => {
    element.addEventListener("click", closeExportFieldsModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && exportFieldsModal && !exportFieldsModal.classList.contains("hidden")) {
      closeExportFieldsModal();
    }
  });

  const filterKeys = [
    "q",
    "store_site",
    "brand",
    "sales_status",
    "listing",
    "listing_owner",
    "listing_owner_status",
    "project_group",
    "page_size",
  ];

  const currentFilters = () => {
    const formData = new FormData(filterForm);
    const filters = {};
    filterKeys.forEach((key) => {
      const value = String(formData.get(key) || "").trim();
      if (value) {
        filters[key] = key === "page_size" ? Number(value) : value;
      }
    });
    return filters;
  };

  const saveFilterViews = (views) => {
    return savePreference(fetch("/products/preferences/filter-views", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({views}),
    }));
  };

  filterViewSave?.addEventListener("click", () => {
    const name = String(filterViewNameInput?.value || "").trim();
    const filters = currentFilters();
    if (!name || !Object.keys(filters).length) {
      return;
    }
    const views = [
      ...filterViewState.filter((view) => view.name !== name),
      {name, filters},
    ];
    saveFilterViews(views).then((response) => {
      if (response.ok) {
        window.setTimeout(() => window.location.reload(), 600);
      }
    }).catch(() => {
      // savePreference has already shown the recovery hint.
    });
  });

  document.querySelectorAll("[data-filter-view-delete]").forEach((button) => {
    button.addEventListener("click", () => {
      const name = button.dataset.filterViewDelete;
      const views = filterViewState.filter((view) => view.name !== name);
      savePreference(fetch("/products/preferences/filter-views", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({views}),
      }), "已删除。").then((response) => {
        if (response.ok) {
          window.setTimeout(() => window.location.reload(), 600);
        }
      }).catch(() => {
        // savePreference has already shown the recovery hint.
      });
    });
  });

  const readState = () => {
    if (serverColumnState && Object.keys(serverColumnState).length) {
      return serverColumnState;
    }
    try {
      return JSON.parse(localStorage.getItem(storageKey)) || {};
    } catch (error) {
      return {};
    }
  };

  let state = readState();

  const saveState = () => {
    localStorage.setItem(storageKey, JSON.stringify(state));
    savePreference(fetch("/products/preferences/columns", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(state),
    })).catch(() => {});
  };

  const applyColumnVisibility = (key, visible) => {
    document.querySelectorAll(`[data-column="${key}"]`).forEach((element) => {
      element.classList.toggle("hidden", !visible);
    });
  };

  const applyColumnWidth = (key, width) => {
    const nextWidth = `${width}px`;
    document.querySelectorAll(`[data-column="${key}"]`).forEach((element) => {
      element.style.width = nextWidth;
      element.style.minWidth = nextWidth;
    });
  };

  const isColumnVisible = (key) => {
    const toggle = document.querySelector(`[data-column-toggle="${key}"]`);
    const defaultVisible = toggle?.dataset.defaultVisible !== "false";
    return state.visible?.[key] ?? defaultVisible;
  };

  const clearColumnWidth = (key) => {
    document.querySelectorAll(`[data-column="${key}"]`).forEach((element) => {
      element.style.width = "";
      element.style.minWidth = "";
    });
  };

  const orderedKeys = () => {
    const saved = Array.isArray(state.order) ? state.order : [];
    return [
      ...saved.filter((key) => allKeys.includes(key)),
      ...allKeys.filter((key) => !saved.includes(key)),
    ];
  };

  const autoFitColumnWidths = () => {
    const visibleKeys = orderedKeys().filter((key) => isColumnVisible(key));
    if (!visibleKeys.length) {
      return;
    }

    allKeys.forEach((key) => {
      if (!state.widths?.[key]) {
        clearColumnWidth(key);
      }
    });

    const containerWidth = table.parentElement?.clientWidth || table.getBoundingClientRect().width || 960;
    const actionsWidth = 132;
    const availableWidth = Math.max(containerWidth - actionsWidth, 240);
    const manualWidths = state.widths || {};
    const manualTotal = visibleKeys.reduce((total, key) => total + (Number(manualWidths[key]) || 0), 0);
    const autoKeys = visibleKeys.filter((key) => !manualWidths[key]);
    const autoWeightTotal = autoKeys.reduce((total, key) => total + (widthWeights[key] || 1), 0) || 1;
    const shouldFitScreen = visibleKeys.length <= 10;
    const minAutoWidth = shouldFitScreen ? 88 : 96;
    const baseAutoWidth = shouldFitScreen
      ? Math.max(availableWidth - manualTotal, autoKeys.length * minAutoWidth)
      : Math.max(availableWidth - manualTotal, autoKeys.length * minAutoWidth);
    let assignedWidth = actionsWidth;

    visibleKeys.forEach((key) => {
      const manualWidth = Number(manualWidths[key]);
      if (manualWidth >= 40) {
        applyColumnWidth(key, manualWidth);
        assignedWidth += manualWidth;
        return;
      }

      const width = Math.max(
        minAutoWidth,
        Math.round(baseAutoWidth * ((widthWeights[key] || 1) / autoWeightTotal)),
      );
      applyColumnWidth(key, width);
      assignedWidth += width;
    });

    table.style.width = `${Math.max(containerWidth, Math.ceil(assignedWidth))}px`;
  };

  const reorderColumns = () => {
    const order = orderedKeys();
    const colGroup = table.querySelector("colgroup");
    const headerRow = table.querySelector("thead tr");
    const rows = Array.from(table.querySelectorAll("tbody tr"));

    order.forEach((key) => {
      const settingItem = document.querySelector(`[data-column-setting-item="${key}"]`);
      if (settingItem) {
        settingsList.appendChild(settingItem);
      }

      const column = colGroup?.querySelector(`col[data-column="${key}"]`);
      const actionsColumn = colGroup?.querySelector('col[data-column="actions"]');
      if (column && actionsColumn) {
        colGroup.insertBefore(column, actionsColumn);
      }

      const header = headerRow?.querySelector(`th[data-column="${key}"]`);
      const actionsHeader = headerRow?.querySelector('th[data-column="actions"]');
      if (header && actionsHeader) {
        headerRow.insertBefore(header, actionsHeader);
      }

      rows.forEach((row) => {
        const cell = row.querySelector(`td[data-column="${key}"]`);
        const actionsCell = row.querySelector('td[data-column="actions"]');
        if (cell && actionsCell) {
          row.insertBefore(cell, actionsCell);
        }
      });
    });
  };

  const applyState = () => {
    reorderColumns();

    const toggles = Array.from(document.querySelectorAll("[data-column-toggle]"));
    toggles.forEach((toggle) => {
      const key = toggle.dataset.columnToggle;
      const defaultVisible = toggle.dataset.defaultVisible !== "false";
      const visible = state.visible?.[key] ?? defaultVisible;
      toggle.checked = visible;
      applyColumnVisibility(key, visible);
    });

    autoFitColumnWidths();
  };

  settingsButton.addEventListener("click", () => {
    const isHidden = settingsPanel.classList.toggle("hidden");
    settingsButton.setAttribute("aria-expanded", String(!isHidden));
  });

  document.querySelectorAll("[data-column-toggle]").forEach((toggle) => {
    toggle.addEventListener("change", () => {
      const key = toggle.dataset.columnToggle;
      state.visible = state.visible || {};
      state.visible[key] = toggle.checked;
      applyColumnVisibility(key, toggle.checked);
      saveState();
      autoFitColumnWidths();
    });
  });

  let draggedKey = null;

  const moveDraggedItem = (clientX, clientY, draggedItem) => {
    const target = document.elementFromPoint(clientX, clientY)?.closest("[data-column-setting-item]");
    if (!target || !draggedItem || target === draggedItem || !settingsList.contains(target)) {
      return;
    }
    const targetRect = target.getBoundingClientRect();
    const insertAfter = clientY > targetRect.top + targetRect.height / 2;
    settingsList.insertBefore(draggedItem, insertAfter ? target.nextSibling : target);
  };

  const saveColumnOrder = () => {
    state.order = Array.from(settingsList.querySelectorAll("[data-column-setting-item]"))
      .map((item) => item.dataset.columnSettingItem);
    saveState();
    applyState();
  };

  settingsList.addEventListener("dragstart", (event) => {
    const item = event.target.closest("[data-column-setting-item]");
    if (!item) {
      return;
    }
    draggedKey = item.dataset.columnSettingItem;
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", draggedKey);
    item.classList.add("opacity-50");
  });

  settingsList.addEventListener("dragover", (event) => {
    event.preventDefault();
    const draggedItem = draggedKey ? document.querySelector(`[data-column-setting-item="${draggedKey}"]`) : null;
    moveDraggedItem(event.clientX, event.clientY, draggedItem);
  });

  settingsList.addEventListener("dragend", () => {
    document.querySelectorAll("[data-column-setting-item]").forEach((item) => {
      item.classList.remove("opacity-50");
    });
    draggedKey = null;
    saveColumnOrder();
  });

  document.querySelectorAll("[data-column-drag-handle]").forEach((handle) => {
    handle.addEventListener("mousedown", (event) => {
      event.preventDefault();
      const item = handle.closest("[data-column-setting-item]");
      if (!item) {
        return;
      }

      item.classList.add("opacity-50");

      const onMove = (moveEvent) => {
        moveDraggedItem(moveEvent.clientX, moveEvent.clientY, item);
      };

      const onUp = () => {
        item.classList.remove("opacity-50");
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        saveColumnOrder();
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  });

  resizers.forEach((handle) => {
    handle.addEventListener("mousedown", (event) => {
      event.preventDefault();
      const key = handle.dataset.resizeColumn;
      const column = document.querySelector(`col[data-column="${key}"]`);
      const header = document.querySelector(`th[data-column="${key}"]`);
      const startX = event.clientX;
      const startWidth = column?.getBoundingClientRect().width || header?.getBoundingClientRect().width || 120;

      const onMove = (moveEvent) => {
        const nextWidth = Math.max(80, Math.round(startWidth + moveEvent.clientX - startX));
        applyColumnWidth(key, nextWidth);
        table.style.width = `${Math.max(table.parentElement?.clientWidth || 0, table.getBoundingClientRect().width)}px`;
      };

      const onUp = () => {
        const width = header?.getBoundingClientRect().width;
        if (width) {
          state.widths = state.widths || {};
          state.widths[key] = Math.round(width);
          saveState();
        }
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  });

  resetButton?.addEventListener("click", () => {
    localStorage.removeItem(storageKey);
    state = {};
    table.style.width = "";
    document.querySelectorAll("col[data-column]").forEach((column) => {
      column.style.width = "";
      column.style.minWidth = "";
    });
    document.querySelectorAll("th[data-column], td[data-column]").forEach((cell) => {
      cell.style.width = "";
      cell.style.minWidth = "";
    });
    applyState();
    saveState();
  });

  window.addEventListener("resize", () => {
    autoFitColumnWidths();
  });

  applyState();
})();
