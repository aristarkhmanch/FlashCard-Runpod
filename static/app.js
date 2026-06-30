(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const form = $("card-form");
  const emailEl = $("email");
  const linkedinEl = $("linkedin_url");
  const eventEl = $("event");
  const submitBtn = $("submit-btn");
  const formError = $("form-error");

  const views = { form: $("view-form"), loading: $("view-loading"), result: $("view-result") };
  const resultImg = $("result-img");
  const downloadBtn = $("download-btn");
  let last = null;

  function show(view) {
    Object.entries(views).forEach(([k, el]) => (el.hidden = k !== view));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function setError(el, msg) {
    el.classList.toggle("invalid", Boolean(msg));
    const slot = document.querySelector(`[data-error-for="${el.id}"]`);
    if (slot) slot.textContent = msg || "";
    return !msg;
  }
  const validEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);

  function validate() {
    let ok = true;
    formError.hidden = true;
    const email = emailEl.value.trim();
    if (!email) ok = setError(emailEl, "Email is required") && ok;
    else if (!validEmail(email)) ok = setError(emailEl, "Enter a valid email") && ok;
    else setError(emailEl, "");

    const li = linkedinEl.value.trim();
    if (!li) ok = setError(linkedinEl, "LinkedIn URL is required for your QR") && ok;
    else if (!/linkedin\.com\/in\//i.test(li)) ok = setError(linkedinEl, "That isn't a profile URL") && ok;
    else setError(linkedinEl, "");
    return ok;
  }

  // animated step checklist while we wait
  let stepTimer = null;
  function runSteps() {
    const steps = [...document.querySelectorAll("#steps [data-step]")];
    steps.forEach((s) => (s.className = ""));
    let i = 0;
    const tick = () => {
      if (i > 0) steps[i - 1].className = "done";
      if (i < steps.length) {
        steps[i].className = "active";
        i++;
        stepTimer = setTimeout(tick, i < 3 ? 900 : 1600);
      }
    };
    tick();
  }
  function stopSteps() {
    clearTimeout(stepTimer);
    document.querySelectorAll("#steps [data-step]").forEach((s) => (s.className = "done"));
  }

  async function callBackend(payload) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 180000);
    try {
      const res = await fetch("/generate-card", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error(`Server ${res.status}`);
      return await res.json();
    } finally {
      clearTimeout(t);
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!validate()) return;
    submitBtn.classList.add("loading");
    show("loading");
    runSteps();
    try {
      const data = await callBackend({
        email: emailEl.value.trim(),
        linkedin_url: linkedinEl.value.trim(),
        event: eventEl.value.trim() || null,
      });
      if (!data || !data.image_url) throw new Error("No card came back");
      last = data;
      render(data);
      stopSteps();
      show("result");
    } catch (err) {
      console.error(err);
      stopSteps();
      show("form");
      formError.hidden = false;
      formError.textContent =
        err.name === "AbortError"
          ? "That took too long. Give it another shot."
          : "Something went sideways. Try again.";
    } finally {
      submitBtn.classList.remove("loading");
    }
  });

  function render(data) {
    resultImg.src = data.image_url;
    downloadBtn.href = data.image_url;
    $("result-name").textContent = data.name || "";
    $("result-title").textContent = [data.title, data.company].filter(Boolean).join(" · ");
    $("tweet-text").textContent = data.tweet || "";
    $("post-text").textContent = data.linkedin_post || "";
  }

  document.querySelectorAll(".copy").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const text = btn.dataset.copy === "tweet" ? last?.tweet : last?.linkedin_post;
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        const o = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => (btn.textContent = o), 1500);
      } catch {}
    });
  });

  $("again-btn").addEventListener("click", () => {
    formError.hidden = true;
    show("form");
  });

  // prefill email from a QR deep-link (?email=...)
  const qEmail = new URLSearchParams(location.search).get("email");
  if (qEmail) emailEl.value = qEmail;
})();
