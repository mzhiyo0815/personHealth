(() => {
  const nutritionSection = document.querySelector('[data-optional-section="nutrition"]');
  document.addEventListener("health:draft-restored", () => {
    if (nutritionSection?.querySelector('input:not([type="hidden"])')) {
      nutritionSection.open = [...nutritionSection.querySelectorAll("input")]
        .some((field) => field.value !== "");
    }
  });
  const section = document.querySelector("[data-strength-section]");
  const container = document.querySelector("[data-strength-formset]");
  const typeField = document.querySelector("#id_exercise_type");
  if (!container || !section) return;

  const prefix = container.dataset.strengthFormset;
  const rows = container.querySelector("[data-formset-rows]");
  const template = container.querySelector("[data-formset-template]");
  const totalField = document.querySelector(`#id_${prefix}-TOTAL_FORMS`);
  const addButton = container.querySelector("[data-add-row]");
  const limitMessage = container.querySelector("[data-formset-limit]");
  const maxForms = Number(container.dataset.maxForms);
  const allRows = () => [...rows.querySelectorAll("[data-formset-row]")];
  const activeRows = () => allRows().filter((row) => !row.hidden);

  const sync = () => {
    activeRows().forEach((row, index) => {
      row.querySelector("[data-row-number]").textContent = index + 1;
      const order = row.querySelector(`[name$="-order"]`);
      if (order) order.value = index;
    });
    const atLimit = activeRows().length >= maxForms;
    addButton.disabled = atLimit;
    limitMessage.hidden = !atLimit;
  };

  const addRow = () => {
    if (activeRows().length >= maxForms) return null;
    const index = Number(totalField.value);
    const wrapper = document.createElement("div");
    wrapper.innerHTML = template.innerHTML
      .replaceAll("__prefix__", index)
      .replaceAll("__number__", activeRows().length + 1);
    const row = wrapper.firstElementChild;
    rows.append(row);
    totalField.value = index + 1;
    sync();
    row.querySelector('[name$="-exercise_name"]')?.focus();
    container.dispatchEvent(new Event("input", {bubbles: true}));
    return row;
  };

  const ensureTotal = (requestedPrefix, count) => {
    if (requestedPrefix !== prefix) return;
    while (allRows().length < Math.min(Number(count) || 0, maxForms)) addRow();
  };

  addButton.addEventListener("click", addRow);
  rows.addEventListener("click", (event) => {
    const button = event.target.closest("[data-remove-row]");
    if (!button) return;
    const row = button.closest("[data-formset-row]");
    const deleteField = row.querySelector('[name$="-DELETE"]');
    if (deleteField) deleteField.checked = true;
    row.hidden = true;
    if (!activeRows().length) addRow();
    sync();
    container.dispatchEvent(new Event("input", {bubbles: true}));
  });
  typeField?.addEventListener("change", () => {
    section.open = typeField.value === "strength";
  });
  document.addEventListener("health:draft-restored", () => {
    allRows().forEach((row) => {
      const deleteField = row.querySelector('[name$="-DELETE"]');
      row.hidden = Boolean(deleteField?.checked);
    });
    if (!activeRows().length) addRow();
    if (typeField?.value === "strength") section.open = true;
    sync();
  });
  window.healthRecordForms = {ensureTotal, syncAll: sync};
  sync();
})();
