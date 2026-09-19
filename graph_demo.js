const board = document.getElementById("graphBoard");
const edgeLayer = document.getElementById("edgeLayer");
const runButton = document.getElementById("runButton");
const resetButton = document.getElementById("resetButton");
const sampleButton = document.getElementById("sampleButton");
const traceForm = document.getElementById("traceForm");
const problemInput = document.getElementById("problemInput");
const stepsInput = document.getElementById("stepsInput");
const inputFeedback = document.getElementById("inputFeedback");
const runState = document.getElementById("runState");
const logTitle = document.getElementById("logTitle");
const logText = document.getElementById("logText");
const logTime = document.getElementById("logTime");
const selectedNode = document.getElementById("selectedNode");
const stages = [...document.querySelectorAll(".stage")];
let nodeCards = [...document.querySelectorAll(".node-card")];
let graphEdges = [["problemNode", "n1"], ["n1", "n2"], ["n2", "n3"], ["problemNode", "n4"], ["n4", "n5"]];
let currentAnalysis = null;
let analysisTimer = null;

function nodeElement(id) {
  return id === "problemNode" ? document.getElementById(id) : document.querySelector(`[data-node="${id}"]`);
}

function centerPoint(element) {
  const boardRect = board.getBoundingClientRect();
  const rect = element.getBoundingClientRect();
  return { x: rect.left - boardRect.left + rect.width / 2, y: rect.top - boardRect.top + rect.height / 2 };
}

function drawEdges() {
  edgeLayer.setAttribute("viewBox", `0 0 ${board.clientWidth} ${board.clientHeight}`);
  edgeLayer.innerHTML = '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,4 L0,8 Z" fill="#aebcc2"></path></marker></defs>';
  graphEdges.forEach(([from, to]) => {
    const startElement = nodeElement(from);
    const endElement = nodeElement(to);
    if (!startElement || !endElement) return;
    const start = centerPoint(startElement);
    const end = centerPoint(endElement);
    const midpoint = (start.y + end.y) / 2;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${start.x} ${start.y} C ${start.x} ${midpoint}, ${end.x} ${midpoint}, ${end.x} ${end.y}`);
    path.classList.add("edge-path");
    const target = nodeElement(to);
    if (target?.classList.contains("node-error")) path.classList.add("edge-error");
    else if (target?.classList.contains("node-affected")) path.classList.add("edge-affected");
    edgeLayer.appendChild(path);
  });
}

function updateLog(title, message, running = false) {
  logTitle.textContent = title;
  logText.textContent = message;
  logTime.textContent = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  runState.classList.toggle("running", running);
  runState.lastChild.textContent = running ? "Running" : "Ready";
}

function setStage(index) {
  stages.forEach((stage, i) => stage.classList.toggle("active", i === index));
}

function wireNodeEvents() {
  nodeCards = [...document.querySelectorAll(".node-card")];
  nodeCards.forEach((card) => {
    card.addEventListener("click", () => selectNode(card.dataset.node));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode(card.dataset.node);
      }
    });
  });
}

function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[character]));
}

function updateInspector(data) {
  const hasError = Boolean(data.error_node_id);
  document.getElementById("diagnosisTitle").textContent = hasError ? String(data.error_type || "Verification error").replaceAll("_", " ") : "No error detected";
  document.getElementById("diagnosisCopy").textContent = hasError ? `First invalid state: ${data.error_node_id}. ${data.repair_reason || "The verifier rejected this transformation."}` : "Every submitted state is equivalent to the problem or a valid transformation.";
  document.getElementById("answerText").textContent = data.correct_answer || "Not isolated";
  document.getElementById("repairText").textContent = data.suggested_repair || "No repair needed";
  document.getElementById("actionPill").textContent = data.repair_action || "CONTINUE";
  document.getElementById("policyReason").textContent = data.repair_reason || "The verified chain can continue.";
  document.getElementById("affectedCount").textContent = (data.affected_node_ids || []).length;
  document.getElementById("clearCount").textContent = data.nodes.filter((node) => node.status === "clear").length;
  document.getElementById("nodeCount").textContent = data.nodes.length;
  document.getElementById("edgeCount").textContent = data.nodes.reduce((total, node) => total + node.depends_on.length, 0);
  const allocationList = document.getElementById("allocationList");
  allocationList.innerHTML = "";
  data.allocation.forEach((item) => {
    const row = document.createElement("div");
    row.className = `allocation-row${item.allocated_calls === 0 ? " muted" : ""}`;
    const width = Math.min(100, Math.round(item.allocated_calls / 7 * 100));
    row.innerHTML = `<span class="allocation-id">${item.node_id}</span><div class="allocation-track"><i style="width: ${width}%"></i></div><b>${item.allocated_calls}</b>`;
    allocationList.appendChild(row);
  });
}

function draftAnalysis(problem, steps) {
  const nodes = steps.map((text, index) => ({
    id: `n${index + 1}`,
    text,
    depends_on: [index === 0 ? "problem" : `n${index}`],
    status: "draft",
  }));
  return {
    problem: problem || "Untitled problem",
    nodes,
    error_node_id: null,
    error_type: "",
    suggested_repair: "",
    repair_action: "DRAFT",
    repair_reason: "Draft preview. Analyze the trace to run symbolic verification.",
    correct_answer: "Pending verification",
    affected_node_ids: [],
    allocation: nodes.map((node) => ({ node_id: node.id, priority: 0, allocated_calls: 0 })),
  };
}

function renderDraftPreview() {
  const problem = problemInput.value.trim();
  const steps = stepsInput.value.split(/\r?\n/).map((step) => step.trim()).filter(Boolean);
  if (!problem && !steps.length) return;
  renderGraph(draftAnalysis(problem, steps));
  inputFeedback.classList.remove("feedback-error");
  inputFeedback.textContent = "Draft preview updated. Complete the trace or click Analyze trace for symbolic verification.";
}

function renderGraph(data) {
  document.getElementById("problemText").textContent = data.problem;
  document.querySelectorAll(".node-card, .problem-node").forEach((element) => element.remove());
  const problemNode = document.createElement("div");
  problemNode.className = "problem-node";
  problemNode.id = "problemNode";
  problemNode.innerHTML = `Problem<br><strong>${escapeHTML(data.problem)}</strong>`;
  board.appendChild(problemNode);
  const spacing = data.nodes.length > 1 ? 75 / (data.nodes.length - 1) : 0;
  data.nodes.forEach((node, index) => {
    const card = document.createElement("div");
    card.className = `node-card node-${node.status}`;
    card.dataset.node = node.id;
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `Node ${node.id}, ${node.status}`);
    card.style.left = "50%";
    card.style.top = `${18 + index * spacing}%`;
    card.innerHTML = `<div class="node-top"><span class="node-id">${escapeHTML(node.id)}</span><span class="node-status">${escapeHTML(node.status.toUpperCase())}</span></div><div class="equation">${escapeHTML(node.text)}</div><div class="node-foot">depends on ${escapeHTML(node.depends_on.join(", "))}</div>`;
    board.appendChild(card);
  });
  board.style.minHeight = `${Math.max(515, 180 + data.nodes.length * 125)}px`;
  graphEdges = data.nodes.flatMap((node) => node.depends_on.map((parent) => [parent === "problem" ? "problemNode" : parent, node.id]));
  currentAnalysis = data;
  wireNodeEvents();
  updateInspector(data);
  drawEdges();
  selectNode(data.error_node_id || data.nodes[0]?.id);
}

function selectNode(id) {
  if (!id) return;
  nodeCards.forEach((card) => card.classList.toggle("selected", card.dataset.node === id));
  selectedNode.textContent = id;
  const node = currentAnalysis?.nodes.find((item) => item.id === id);
  if (!node) return;
  const title = node.status === "error" ? "First invalid state" : node.status === "affected" ? "Affected descendant" : node.status === "draft" ? "Draft state" : "Verified state";
  const message = node.status === "error" ? (currentAnalysis.repair_reason || "The symbolic verifier rejected this state.") : node.status === "affected" ? `This state depends on ${node.depends_on.join(", ")} and inherits its status.` : node.status === "draft" ? "This state is a live preview of the text you entered; run Analyze trace to verify it." : "This state is outside the invalid dependency path.";
  document.getElementById("diagnosisTitle").textContent = title;
  document.getElementById("diagnosisCopy").textContent = message;
  updateLog(`Selected ${id}`, message);
}

function resetView() { window.location.reload(); }

async function analyzeTrace(event) {
  event?.preventDefault();
  const problem = problemInput.value.trim();
  const steps = stepsInput.value.split(/\r?\n/).map((step) => step.trim()).filter(Boolean);
  renderGraph(draftAnalysis(problem, steps));
  inputFeedback.classList.remove("feedback-error");
  inputFeedback.textContent = "Sending trace to the symbolic verifier...";
  try {
    const response = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ problem, steps }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Trace analysis failed.");
    renderGraph(data);
    setStage(0);
    inputFeedback.textContent = `Analyzed ${data.nodes.length} submitted states. Click Run verification for the staged presentation sequence.`;
    updateLog("Trace analyzed", "Graph constructed successfully. Run verification to present the full pipeline.");
  } catch (error) {
    inputFeedback.classList.add("feedback-error");
    inputFeedback.textContent = `${error.message} Start the Python Graph Lab server first.`;
    updateLog("Analysis unavailable", inputFeedback.textContent);
  }
}

function scheduleDraftAnalysis() {
  window.clearTimeout(analysisTimer);
  renderDraftPreview();
  const problem = problemInput.value.trim();
  const steps = stepsInput.value.split(/\r?\n/).map((step) => step.trim()).filter(Boolean);
  const complete = problem.includes("=") && steps.length > 0 && steps.every((step) => step.includes("="));
  if (!complete) {
    inputFeedback.classList.remove("feedback-error");
    inputFeedback.textContent = "Draft changed. Complete the equation and one equation per step, then click Analyze trace.";
    return;
  }
  inputFeedback.classList.remove("feedback-error");
  inputFeedback.textContent = "Draft changed. Updating the reasoning graph...";
  analysisTimer = window.setTimeout(() => analyzeTrace(), 450);
}

async function runVerification() {
  if (!currentAnalysis) return;
  runButton.disabled = true;
  resetButton.disabled = true;
  const errorNode = currentAnalysis.error_node_id || "none";
  const sequence = [
    [0, "Constructing dependency graph", `${currentAnalysis.nodes.length} submitted states and ${graphEdges.length} dependencies loaded.`],
    [1, "Verifying equation states", "Symbolic verifier is checking each node in topological order."],
    [2, "Localizing first error", `${errorNode} is the first invalid state; descendants are marked affected.`],
    [3, "Selecting repair", `${currentAnalysis.repair_action || "CONTINUE"} selected by the error-conditioned policy.`],
    [4, "Allocating compute", "Extra calls are concentrated on the invalid dependency path."],
  ];
  for (const [index, title, message] of sequence) {
    setStage(index);
    updateLog(title, message, true);
    await new Promise((resolve) => setTimeout(resolve, 620));
  }
  selectNode(errorNode !== "none" ? errorNode : currentAnalysis.nodes[0]?.id);
  updateLog("Verification complete", `Verified answer: ${currentAnalysis.correct_answer || "not isolated"}.`);
  runButton.disabled = false;
  resetButton.disabled = false;
}

sampleButton.addEventListener("click", () => {
  problemInput.value = "2(x + 3) = 14";
  stepsInput.value = "2x + 3 = 14\n2x = 11\nx = 5.5";
  inputFeedback.classList.remove("feedback-error");
  inputFeedback.textContent = "Sample loaded. Click Analyze trace.";
});
traceForm.addEventListener("submit", analyzeTrace);
problemInput.addEventListener("input", scheduleDraftAnalysis);
stepsInput.addEventListener("input", scheduleDraftAnalysis);
runButton.addEventListener("click", runVerification);
resetButton.addEventListener("click", resetView);
window.addEventListener("resize", drawEdges);
window.addEventListener("load", () => {
  wireNodeEvents();
  currentAnalysis = { problem: "2(x + 3) = 14", nodes: [
    { id: "n1", text: "2x + 3 = 14", depends_on: ["problem"], status: "error" },
    { id: "n2", text: "2x = 11", depends_on: ["n1"], status: "affected" },
    { id: "n3", text: "x = 5.5", depends_on: ["n2"], status: "affected" },
    { id: "n4", text: "14 = 2(x + 3)", depends_on: ["problem"], status: "clear" },
    { id: "n5", text: "x = 4", depends_on: ["n4"], status: "clear" },
  ], error_node_id: "n1", error_type: "algebraic_transformation_error", repair_reason: "Expand or simplify the equation in symbolic form.", suggested_repair: "2x + 6 = 14", repair_action: "REFORMALIZE", correct_answer: "x = 4", affected_node_ids: ["n2", "n3"], allocation: [
    { node_id: "n1", allocated_calls: 7 }, { node_id: "n2", allocated_calls: 2 }, { node_id: "n3", allocated_calls: 1 }, { node_id: "n4", allocated_calls: 0 }, { node_id: "n5", allocated_calls: 0 },
  ] };
  updateInspector(currentAnalysis);
  selectNode("n1");
  drawEdges();
});
