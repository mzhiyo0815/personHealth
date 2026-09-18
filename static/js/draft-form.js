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
    const safeFields = [...form.elements].filter((field) =>
      field.name && field.name !== "csrfmiddlewaretoken" &&
      !["password", "file", "submit"].includes(field.type)
    );
    try {
      const draft = JSON.parse(localStorage.getItem(key) || "{}");
      safeFields.forEach((field) => {
        if (!(field.name in draft)) return;
        if (field.type === "checkbox") field.checked = Boolean(draft[field.name]);
        else field.value = draft[field.name];
      });
    } catch (_) { localStorage.removeItem(key); }
    const saveDraft = () => {
      const draft = {};
      safeFields.forEach((field) => {
        draft[field.name] = field.type === "checkbox" ? field.checked : field.value;
      });
      localStorage.setItem(key, JSON.stringify(draft));
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
      sessionStorage.setItem(
        "health-pending-draft",
        JSON.stringify({key, token})
      );
    });
  });
})();
