/* ==========================================================================
   CMMC Readiness Check — app logic
   Customize the CONFIG block below (company name + optional platform tips).
   Everything else drives itself off the QUESTIONS / DYNAMIC_QUESTIONS data.
   ========================================================================== */

const CONFIG = {
  companyName: "Your Company",
  toolName: "CMMC Readiness Check",
  // Set to true and fill in copy below if you offer a compliant hosting /
  // platform option you want to reference in the dynamic follow-up tips.
  showPlatformTips: false,
  platformName: "our compliant hosting environment",
};

// Base questions, always shown. Mirrors the 14 CMMC Level 2 / NIST SP 800-171
// control families at a plain-language level.
const QUESTIONS = [
  {
    id: "boundary",
    cat: "Know your CUI boundary",
    text: "Can you point to a current document showing where CUI enters your business, where it is stored, and which systems can reach it?",
    help: "A clear boundary keeps the assessment focused on the systems that actually handle or protect CUI.",
  },
  {
    id: "access",
    cat: "Limit access",
    text: "Do only approved people receive the CUI access they need, with regular access reviews and prompt removal when someone changes roles or leaves?",
    help: "Access should follow job duties and be removed as soon as it is no longer needed.",
  },
  {
    id: "identity",
    cat: "Verify every user",
    text: "Does every person use an individual account with multi-factor authentication, protected passwords, and no shared logins for CUI work?",
    help: "Individual accounts and strong sign-in controls make access traceable and harder to misuse.",
  },
  {
    id: "people",
    cat: "Prepare your people",
    text: "Are employees and administrators screened as appropriate, trained on CUI handling, and covered by a documented onboarding and offboarding process?",
    help: "People need to understand their responsibilities before receiving access and after their role changes.",
  },
  {
    id: "systems",
    cat: "Keep systems secure",
    text: "Are computers and services used for CUI approved, securely configured, kept up to date, protected from malware, and monitored for problems?",
    help: "A known, maintained baseline reduces preventable weaknesses and unexpected changes.",
  },
  {
    id: "logging",
    cat: "Keep a reliable history",
    text: "Could you produce a reliable history showing who signed in, viewed, or changed CUI, and what important administrative actions occurred?",
    help: "Useful logs support investigations, accountability, and proof that safeguards are operating.",
  },
  {
    id: "encryption",
    cat: "Protect stored and moving CUI",
    text: "Is CUI encrypted while stored and while moving between users and systems, using approved protections that your organization can document?",
    help: "CUI needs confidentiality protections both at rest and while traveling across connections.",
  },
  {
    id: "media",
    cat: "Control copies and backups",
    text: "Are downloads, backups, removable drives, printed copies, disposal, and transportation of CUI limited and handled under documented rules?",
    help: "Copies outside the primary system can expand the CUI boundary and create hard-to-track exposure.",
  },
  {
    id: "incident",
    cat: "Be ready for an incident",
    text: "Do you have a tested plan for detecting, containing, documenting, and reporting a cyber incident involving CUI?",
    help: "A written and practiced response reduces confusion and supports required reporting timelines.",
  },
  {
    id: "maintenance",
    cat: "Control maintenance",
    text: "Are maintenance tools, support connections, service providers, and administrator activities approved and supervised when they can reach CUI systems?",
    help: "Maintenance access is powerful and needs the same authorization and protection as normal access.",
  },
  {
    id: "physical",
    cat: "Protect physical access",
    text: "Are offices, equipment, visitors, and physical access records controlled anywhere people can reach systems or media containing CUI?",
    help: "Physical access can bypass technical controls and must be limited and recorded.",
  },
];

// Follow-up questions revealed based on the "Where is CUI handled today?" answers.
const DYNAMIC_QUESTIONS = [
  {
    id: "dyn-onprem",
    triggersOn: (b) => b.location === "onprem" || b.location === "several",
    cat: "Account for on-premises systems",
    text: "Are all on-premises systems that store, process, transmit, or protect CUI identified, managed, and included in the system security plan?",
    help: "On-premises systems remain in scope even when a cloud system is also used, including identity, security, backup, and administrative components.",
    tip: "Moving your system of record to a managed, compliant platform can reduce on-premises infrastructure scope, but any remaining CUI copies and security dependencies stay in your assessment boundary.",
  },
  {
    id: "dyn-downloads",
    triggersOn: (b) => b.downloads && b.downloads !== "none",
    cat: "Protect downloaded CUI",
    text: "Are local copies limited to approved, managed, encrypted devices with access controls, monitoring, retention rules, and secure deletion?",
    help: "Downloading CUI extends the assessment boundary beyond the hosted application to endpoints, local storage, backups, printing, and removable media.",
    tip: "Keeping CUI inside an approved hosted workflow can reduce the need for local copies; anything downloaded or printed remains your responsibility to protect.",
  },
  {
    id: "dyn-connected",
    triggersOn: (b) => b.connected === "yes",
    cat: "Approve connected systems",
    text: "Is every connected system and data transfer documented, approved for its CUI role, and included in the security boundary where required?",
    help: "Integrations, APIs, email, file transfer, identity services, and exports can all create additional CUI paths and assessment scope.",
    tip: "Documenting supported integrations and data paths helps, but every connected system that receives CUI still needs an approved role and appropriate safeguards.",
  },
];

const ANSWER_OPTIONS = ["Yes", "Partly", "No", "Not sure"];
const ANSWER_SCORE = { Yes: 1, Partly: 0.5, No: 0, "Not sure": 0 };

const state = {
  view: "overview",
  client: { name: "", preparedBy: "", area: "" },
  boundary: { location: "", downloads: "", connected: "" },
  answers: {},          // questionId -> "Yes" | "Partly" | "No" | "Not sure"
  openTips: {},         // questionId -> bool
  submitted: false,
};

function activeDynamicQuestions() {
  return DYNAMIC_QUESTIONS.filter((q) => q.triggersOn(state.boundary));
}

function allActiveQuestions() {
  return [...QUESTIONS, ...activeDynamicQuestions()];
}

function requiredTotal() {
  return allActiveQuestions().length;
}

function requiredComplete() {
  return allActiveQuestions().filter((q) => state.answers[q.id]).length;
}

function setView(view) {
  state.view = view;
  render();
  window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });
}

function setAnswer(id, value) {
  state.answers[id] = state.answers[id] === value ? undefined : value;
  render();
}

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderNav() {
  const items = [
    ["overview", "Overview"],
    ["questionnaire", "Questionnaire"],
    ["results", "Results"],
    ["matrix", "Shared Responsibility Matrix"],
  ];
  return `
    <div class="sidebar-title">${escapeHtml(CONFIG.toolName)}</div>
    <div class="sidebar-sub">Single-use assessment</div>
    <ul class="nav-list">
      ${items.map(([id, label]) => `
        <li class="nav-item ${state.view === id ? "active" : ""}" data-nav="${id}">${label}</li>
      `).join("")}
    </ul>
  `;
}

function renderOverview() {
  return `
    <div class="panel">
      <h2 style="margin-top:0;">Before you start</h2>
      <p style="color:var(--color-text-muted);">
        This tool walks through ${QUESTIONS.length} core practice areas covering how your organization
        handles Controlled Unclassified Information (CUI), plus a few follow-up questions
        depending on where your CUI lives today. It takes about 10&ndash;15 minutes.
      </p>
      <p style="color:var(--color-text-muted);">
        Answer honestly and at a high level &mdash; do not enter actual CUI, credentials,
        export-controlled data, or sensitive evidence anywhere in this tool.
      </p>
      <button class="btn btn-primary" data-nav="questionnaire">Start readiness check &rarr;</button>
    </div>
  `;
}

function renderBoundaryField(id, label, options, current) {
  return `
    <div class="field">
      <label for="${id}">${label}</label>
      <select id="${id}" data-boundary="${id}">
        ${options.map(([val, text]) => `
          <option value="${val}" ${current === val ? "selected" : ""}>${text}</option>
        `).join("")}
      </select>
    </div>
  `;
}

function renderQuestion(q, num) {
  const answer = state.answers[q.id];
  const isOpen = !!state.openTips[q.id];
  return `
    <div class="question">
      <div class="q-num">${num}</div>
      <div class="q-body">
        <div class="q-cat">${escapeHtml(q.cat)}</div>
        <p class="q-text">${escapeHtml(q.text)}</p>
        <p class="q-help">${escapeHtml(q.help)}</p>
        ${q.tip ? `
          <div class="q-toggle" data-tip-toggle="${q.id}">
            ${isOpen ? "&#9660;" : "&#9654;"} Why this matters
          </div>
          ${isOpen ? `
            <div class="notice tip q-tip">${escapeHtml(q.tip)}</div>
          ` : ""}
        ` : ""}
      </div>
      <div class="answer-row">
        ${ANSWER_OPTIONS.map((opt) => `
          <button type="button" class="answer-btn ${answer === opt ? "selected-" + opt.toLowerCase().replace(" ", "") : ""}"
            data-answer="${q.id}" data-value="${opt}">${opt}</button>
        `).join("")}
      </div>
    </div>
  `;
}

function renderQuestionnaire() {
  const dyn = activeDynamicQuestions();
  const total = requiredTotal();
  const done = requiredComplete();
  const pct = total ? Math.round((done / total) * 100) : 0;

  return `
    <div class="notice caution no-print">
      &#9888; This is a readiness estimate only, not a certification decision or official score.
    </div>
    <div class="notice caution no-print" style="background:#fff8e1;">
      &#128274; Nothing is saved. Closing or refreshing this page clears the assessment.
    </div>

    <div class="panel">
      <div class="progress-head">
        <div>
          <div class="progress-label">Required checks complete</div>
          <div class="progress-count">${done} of ${total}</div>
        </div>
        <div class="progress-pct">${pct}%</div>
      </div>
      <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
    </div>

    <div class="panel">
      <div class="field-grid">
        <div class="field">
          <label for="clientName">Client name</label>
          <input id="clientName" type="text" placeholder="Company or organization" value="${escapeHtml(state.client.name)}" data-client="name">
        </div>
        <div class="field">
          <label for="preparedBy">Prepared by</label>
          <input id="preparedBy" type="text" placeholder="Name" value="${escapeHtml(state.client.preparedBy)}" data-client="preparedBy">
        </div>
        <div class="field">
          <label for="area">Business area</label>
          <input id="area" type="text" placeholder="Team, location, program, or contract" value="${escapeHtml(state.client.area)}" data-client="area">
        </div>
      </div>
    </div>

    <div class="panel">
      <div class="section-title">Where is CUI handled today?</div>
      <p class="section-desc">Your selections may reveal additional required checks below.</p>
      <div class="field-grid">
        ${renderBoundaryField("location", "Primary CUI location", [
          ["", "Select one"],
          ["compliant-cloud", "Dedicated compliant cloud environment"],
          ["standard-cloud", "Standard commercial cloud or software"],
          ["other-cloud", "Another cloud service"],
          ["onprem", "On-premises systems"],
          ["several", "Several locations, including cloud"],
          ["notsure", "Not sure"],
        ], state.boundary.location)}
        ${renderBoundaryField("downloads", "Local downloads or copies", [
          ["", "Select one"],
          ["none", "None"],
          ["rarely", "Rarely"],
          ["sometimes", "Sometimes"],
          ["frequently", "Frequently"],
          ["notsure", "Not sure"],
        ], state.boundary.downloads)}
        ${renderBoundaryField("connected", "Connected business systems", [
          ["", "Select one"],
          ["yes", "Yes"],
          ["no", "No"],
          ["notsure", "Not sure"],
        ], state.boundary.connected)}
      </div>
    </div>

    ${dyn.length ? `
      <div class="panel">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div>
            <div class="section-title">Additional boundary checks</div>
            <p class="section-desc">These questions appeared because of the CUI locations and data flows selected above.</p>
          </div>
          <span class="badge">${dyn.length} required</span>
        </div>
        ${dyn.map((q, i) => renderQuestion(q, "+")).join("")}
      </div>
    ` : ""}

    <div class="panel">
      <div class="section-title">Core practice areas</div>
      <p class="section-desc">${QUESTIONS.length} plain-language checks covering the CMMC Level 2 practice families.</p>
      ${QUESTIONS.map((q, i) => renderQuestion(q, i + 1)).join("")}
    </div>

    <div class="panel sticky-submit no-print">
      <div class="status">${done} of ${total} required checks complete</div>
      <button class="btn btn-primary" data-submit ${done < total ? "disabled" : ""}>Submit and view results &rarr;</button>
    </div>
  `;
}

function scoreSummary() {
  const qs = allActiveQuestions();
  const answered = qs.filter((q) => state.answers[q.id]);
  const scoreSum = answered.reduce((sum, q) => sum + ANSWER_SCORE[state.answers[q.id]], 0);
  const pct = qs.length ? Math.round((scoreSum / qs.length) * 100) : 0;
  const gaps = qs.filter((q) => {
    const a = state.answers[q.id];
    return a === "Partly" || a === "No" || a === "Not sure";
  });
  return { qs, pct, gaps };
}

function ringColor(pct) {
  if (pct >= 80) return "#1a7f4f";
  if (pct >= 50) return "#b9860a";
  return "#c0392b";
}

function renderResults() {
  const total = requiredTotal();
  const done = requiredComplete();
  if (done < total) {
    return `
      <div class="panel">
        <h2 style="margin-top:0;">Results aren't ready yet</h2>
        <p style="color:var(--color-text-muted);">Answer the remaining ${total - done} required check(s) in the questionnaire to see your estimate.</p>
        <button class="btn btn-primary" data-nav="questionnaire">Go to questionnaire</button>
      </div>
    `;
  }
  const { pct, gaps } = scoreSummary();
  return `
    <div class="notice caution no-print">
      &#9888; Readiness guidance only. This estimate does not determine or guarantee certification.
    </div>
    <div class="panel">
      <div class="score-wrap">
        <div class="score-ring" style="background:${ringColor(pct)};">${pct}%</div>
        <div>
          <h2 style="margin:0 0 6px;">Estimated readiness</h2>
          <p style="color:var(--color-text-muted); margin:0;">
            ${escapeHtml(state.client.name || "This organization")} answered "Yes" on
            ${allActiveQuestions().length - gaps.length} of ${allActiveQuestions().length} checks.
            ${gaps.length ? `${gaps.length} area${gaps.length === 1 ? "" : "s"} may need attention before a formal assessment.` : "No gaps were flagged &mdash; nice work."}
          </p>
        </div>
      </div>
    </div>

    ${gaps.length ? `
      <div class="panel">
        <div class="section-title">Likely gaps</div>
        <p class="section-desc">Areas answered "Partly," "No," or "Not sure."</p>
        <ul class="gap-list">
          ${gaps.map((q) => `
            <li class="gap-item">
              <span class="gap-status" style="color:${state.answers[q.id] === "No" ? "#c0392b" : "#8a6408"};">${state.answers[q.id]}</span>
              <span><strong>${escapeHtml(q.cat)}</strong><br><span style="color:var(--color-text-muted);">${escapeHtml(q.text)}</span></span>
            </li>
          `).join("")}
        </ul>
      </div>
    ` : ""}

    <div class="panel no-print" style="display:flex; gap:12px;">
      <button class="btn btn-primary" onclick="window.print()">Print / save results</button>
      <button class="btn btn-secondary" data-nav="matrix">View shared responsibility matrix</button>
    </div>
  `;
}

const MATRIX_ROWS = [
  ["Access control & authentication", "Provides account, MFA, and role features to configure", "Standard configuration; not pre-hardened for CUI", "Configuring roles, MFA, and access reviews"],
  ["Audit logging", "Generates underlying activity logs", "Basic logs; extended retention may be limited", "Reviewing, retaining, and protecting log records"],
  ["Encryption in transit / at rest", "Platform-level transport and storage encryption", "Varies by plan; verify before relying on it", "Confirming encryption meets requirements; encrypting exports"],
  ["Backups & media handling", "Platform backup mechanisms, if offered", "Standard backup; not CUI-specific", "Approving, encrypting, and disposing of local copies"],
  ["Incident response", "Notifies of platform-level incidents affecting the service", "Standard support channels", "Detecting, containing, and reporting CUI incidents"],
  ["Physical security", "Data center physical controls, if cloud-hosted", "Data center physical controls, if cloud-hosted", "Office, device, and on-site media physical security"],
  ["Connected systems / integrations", "Documents supported integration points", "Documents supported integration points", "Approving, authorizing, and monitoring each connection"],
];

function renderMatrix() {
  return `
    <div class="panel">
      <div class="section-title">Shared responsibility matrix</div>
      <p class="section-desc">
        A general starting point for how responsibility is typically split between a hosted platform
        and your organization. Confirm the specifics against your actual vendor agreements and system
        security plan &mdash; this is not a substitute for that documentation.
      </p>
      <div class="table-scroll">
        <table class="matrix-table">
          <thead>
            <tr>
              <th>Control area</th>
              <th>Compliant hosted platform</th>
              <th>Standard commercial platform</th>
              <th>Your organization</th>
            </tr>
          </thead>
          <tbody>
            ${MATRIX_ROWS.map((r) => `<tr>${r.map((c) => `<td>${escapeHtml(c)}</td>`).join("")}</tr>`).join("")}
          </tbody>
        </table>
      </div>
      <div class="source-links">
        Reference: <a href="https://www.acquisition.gov/dfars/252.204-7012-safeguarding-covered-defense-information-and-cyber-incident-reporting." target="_blank" rel="noopener">DFARS 252.204-7012</a>
        <a href="https://dodcio.defense.gov/CMMC/FAQ/" target="_blank" rel="noopener">DoD CMMC FAQ</a>
      </div>
    </div>
  `;
}

function render() {
  const app = document.getElementById("app");
  const views = { overview: renderOverview, questionnaire: renderQuestionnaire, results: renderResults, matrix: renderMatrix };
  app.innerHTML = `
    <div class="app-shell">
      <nav class="sidebar">${renderNav()}</nav>
      <main class="main"><div class="main-inner">${views[state.view]()}</div></main>
    </div>
  `;
  bindEvents();
}

function bindEvents() {
  document.querySelectorAll("[data-nav]").forEach((n) => {
    n.addEventListener("click", () => setView(n.getAttribute("data-nav")));
  });
  document.querySelectorAll("[data-client]").forEach((input) => {
    input.addEventListener("input", (e) => {
      state.client[e.target.getAttribute("data-client")] = e.target.value;
    });
  });
  document.querySelectorAll("[data-boundary]").forEach((select) => {
    select.addEventListener("change", (e) => {
      state.boundary[e.target.getAttribute("data-boundary")] = e.target.value;
      render();
    });
  });
  document.querySelectorAll("[data-answer]").forEach((btn) => {
    btn.addEventListener("click", () => {
      setAnswer(btn.getAttribute("data-answer"), btn.getAttribute("data-value"));
    });
  });
  document.querySelectorAll("[data-tip-toggle]").forEach((t) => {
    t.addEventListener("click", () => {
      const id = t.getAttribute("data-tip-toggle");
      state.openTips[id] = !state.openTips[id];
      render();
    });
  });
  const submitBtn = document.querySelector("[data-submit]");
  if (submitBtn) {
    submitBtn.addEventListener("click", () => setView("results"));
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document.title = CONFIG.toolName + " — " + CONFIG.companyName;
  render();
});
