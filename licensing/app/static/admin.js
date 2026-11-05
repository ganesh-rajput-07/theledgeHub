// Payment form: show the price-list total for the chosen plan, computers and periods, and prefill the amount.
(function () {
  const form = document.getElementById("payment-form");
  if (!form) return;
  const plans = JSON.parse(document.getElementById("plan-data").textContent);
  const gst = parseFloat(form.dataset.gst || "0");
  const out = document.getElementById("quote");
  const amount = form.querySelector("[name=amount]");
  let touched = false;
  amount.addEventListener("input", () => { touched = true; });
  const fmt = (paise) => "₹" + (paise / 100).toLocaleString("en-IN", { maximumFractionDigits: 2 });
  function update() {
    const p = plans[form.plan_id.value];
    if (!p) { out.textContent = "Choose a plan."; return; }
    const computers = Math.max(p.included, parseInt(form.computers.value || p.included, 10));
    const periods = Math.max(1, parseInt(form.periods.value || "1", 10));
    const extra = Math.max(0, computers - p.included);
    const subtotal = (p.price + extra * p.extra) * periods;
    const tax = Math.round(subtotal * gst / 100);
    out.textContent = `Price list: ${fmt(subtotal)} + GST ${gst}% ${fmt(tax)} = ${fmt(subtotal + tax)}` +
      ` for ${periods * p.months} month(s), ${computers} computer(s)` + (extra ? ` (${extra} extra)` : "");
    if (!touched) amount.value = ((subtotal + tax) / 100).toFixed(2);
  }
  form.addEventListener("change", (e) => {
    if (e.target.name === "plan_id") {
      const p = plans[form.plan_id.value];
      if (p) form.computers.value = Math.max(p.included, parseInt(form.computers.value || "0", 10));
    }
    update();
  });
  form.addEventListener("input", (e) => { if (e.target.name !== "amount") update(); });
  update();
})();
// Confirm dangerous buttons.
document.querySelectorAll("[data-confirm]").forEach((el) =>
  el.addEventListener("click", (e) => { if (!confirm(el.dataset.confirm)) e.preventDefault(); }));
