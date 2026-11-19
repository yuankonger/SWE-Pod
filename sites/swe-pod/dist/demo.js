const deployments = {
  base: {
    core: false,
    dashboard: false,
    title: "The workflow is unavailable.",
    detail: "The Dashboard has no attribute control, and the API has no customer-tier field.",
  },
  core: {
    core: true,
    dashboard: false,
    title: "The API can store the tier.",
    detail: "Staff still have no Dashboard controls to set the tier or filter by it.",
  },
  dashboard: {
    core: false,
    dashboard: true,
    title: "The Dashboard cannot save the tier.",
    detail: "The new controls send a field that the deployed API does not support.",
  },
  both: {
    core: true,
    dashboard: true,
    title: "Staff can save and find the tier.",
    detail: "The Dashboard sends the new attribute, Core persists it, and the customer appears in a filtered list.",
  },
};

const options = document.querySelector(".state-options");
const outcome = document.getElementById("outcome");
const coreStatus = document.getElementById("core-state");
const dashboardStatus = document.getElementById("dashboard-state");
const verdict = document.getElementById("outcome-status");
const title = document.getElementById("outcome-title");
const detail = document.getElementById("outcome-detail");

function showDeployment(selection) {
  const { core, dashboard, title: heading, detail: description } = deployments[selection];
  const passes = core && dashboard;
  coreStatus.textContent = core ? "Feature revision" : "Base revision";
  dashboardStatus.textContent = dashboard ? "Feature revision" : "Base revision";
  outcome.dataset.result = passes ? "pass" : "fail";
  verdict.textContent = passes ? "PASS" : "FAIL";
  verdict.classList.toggle("fn-hl-green", passes);
  verdict.classList.toggle("fn-hl-red", !passes);
  title.textContent = heading;
  detail.textContent = description;
}

options.addEventListener("change", (event) => showDeployment(event.target.value));
window.addEventListener("pageshow", () => showDeployment(options.querySelector(":checked").value));
