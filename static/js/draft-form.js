(() => {
  const prefix = "health-draft:";
  const forms = [...document.querySelectorAll("form[data-draft-form]")];
  const userId = document.body.dataset.userId;
  if (!userId) return;
  forms.forEach((form) => {
    form.dataset.storageKey = `${prefix}${userId}:${location.pathname}`;
  });
  const pendingValue = sessionStorage.getItem("health-pending-draft");
  const savedToken = new URLSearchParams(location.search).get("draft_saved");
  let pendingSubmission;
  try { pendingSubmission = JSON.parse(pendingValue); } catch (_) {}
  if (savedToken && pendingSubmission?.token === savedToken) {
    localStorage.removeItem(pendingSubmission.key);
    sessionStorage.removeItem("health-pending-draft");
  }
  if (savedToken) {
    const cleanUrl = new URL(location.href);
    cleanUrl.searchParams.delete("draft_saved");
    history.replaceState(null, "", cleanUrl);
  }
  forms.forEach((form) => {
    const key = form.dataset.storageKey;
    const safeFields = () => [...form.elements].filter((field) =>
      field.name && field.name !== "csrfmiddlewaretoken" &&
      !/-(TOTAL_FORMS|INITIAL_FORMS|MIN_NUM_FORMS|MAX_NUM_FORMS)$/.test(field.name) &&
      !/-\d+-(id|exercise)$/.test(field.name) &&
      !["password", "file", "submit"].includes(field.type)
    );
    try {
      const draft = JSON.parse(localStorage.getItem(key) || "{}");
      Object.entries(draft.__formset_totals || {}).forEach(([formsetPrefix, count]) => {
        window.healthRecordForms?.ensureTotal(formsetPrefix, count);
      });
      safeFields().forEach((field) => {
        if (!(field.name in draft)) return;
        if (field.type === "checkbox") field.checked = Boolean(draft[field.name]);
        else field.value = draft[field.name];
      });
      document.dispatchEvent(new CustomEvent("health:draft-restored"));
    } catch (_) {
      try { localStorage.removeItem(key); } catch (_) {}
    }
    const saveDraft = () => {
      const draft = {};
      safeFields().forEach((field) => {
        draft[field.name] = field.type === "checkbox" ? field.checked : field.value;
      });
      draft.__formset_totals = {};
      form.querySelectorAll("[data-strength-formset]").forEach((formset) => {
        const formsetPrefix = formset.dataset.strengthFormset;
        draft.__formset_totals[formsetPrefix] = Number(
          form.querySelector(`#id_${formsetPrefix}-TOTAL_FORMS`).value
        );
      });
      try { localStorage.setItem(key, JSON.stringify(draft)); } catch (_) {}
    };
    let timer;
    form.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(saveDraft, 250);
    });
    form.addEventListener("submit", () => {
      clearTimeout(timer);
      saveDraft();
      const token = crypto.randomUUID();
      let tokenField = form.querySelector('input[name="draft_token"]');
      if (!tokenField) {
        tokenField = document.createElement("input");
        tokenField.type = "hidden";
        tokenField.name = "draft_token";
        form.append(tokenField);
      }
      tokenField.value = token;
      try {
        sessionStorage.setItem(
          "health-pending-draft",
          JSON.stringify({key, token})
        );
      } catch (_) {}
    });
  });
})();
