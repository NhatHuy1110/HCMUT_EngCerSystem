const state = {
    files: [],
    currentIndex: -1,
    currentResult: null,
    currentDetailId: null,
    previewZoom: 1,
    restoringQueue: false,
};

const $ = (id) => document.getElementById(id);

const QUEUE_DB_NAME = "hcmut-engcer-queue";
const QUEUE_STORE = "files";
const QUEUE_META_INDEX = "hcmut-engcer-current-index";
let queueDbPromise = null;
let queueSaveTimer = null;

const sections = {
    workspace: $("workspace-section"),
    history: $("history-section"),
    analytics: $("analytics-section"),
};

async function api(url, options = {}) {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Request failed");
    return data;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
}

function percent(value, digits = 0) {
    return `${((Number(value) || 0) * 100).toFixed(digits)}%`;
}

function clampPercent(value) {
    return Math.max(0, Math.min(100, Number(value) || 0));
}

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

function openQueueDb() {
    if (queueDbPromise) return queueDbPromise;
    queueDbPromise = new Promise((resolve, reject) => {
        const request = indexedDB.open(QUEUE_DB_NAME, 1);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(QUEUE_STORE)) {
                db.createObjectStore(QUEUE_STORE, { keyPath: "id" });
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
    return queueDbPromise;
}

async function saveQueueNow() {
    if (state.restoringQueue) return;
    const db = await openQueueDb();
    const tx = db.transaction(QUEUE_STORE, "readwrite");
    const store = tx.objectStore(QUEUE_STORE);
    store.clear();
    state.files.forEach((item, order) => {
        store.put({
            id: item.id,
            order,
            file: item.file,
            name: item.file.name,
            type: item.file.type,
            size: item.file.size,
            lastModified: item.file.lastModified,
            status: item.status === "processing" ? "queued" : item.status,
            result: item.result,
            error: item.error,
            requestedEngine: item.requestedEngine,
            actualEngine: item.actualEngine,
        });
    });
    localStorage.setItem(QUEUE_META_INDEX, String(state.currentIndex));
    await new Promise((resolve, reject) => {
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
    });
}

function scheduleQueueSave() {
    if (state.restoringQueue) return;
    window.clearTimeout(queueSaveTimer);
    queueSaveTimer = window.setTimeout(() => {
        saveQueueNow().catch((error) => console.warn("Could not persist queue", error));
    }, 120);
}

async function clearPersistedQueue() {
    const db = await openQueueDb();
    const tx = db.transaction(QUEUE_STORE, "readwrite");
    tx.objectStore(QUEUE_STORE).clear();
    localStorage.removeItem(QUEUE_META_INDEX);
    await new Promise((resolve, reject) => {
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
    });
}

async function restoreQueue() {
    state.restoringQueue = true;
    try {
        const db = await openQueueDb();
        const tx = db.transaction(QUEUE_STORE, "readonly");
        const request = tx.objectStore(QUEUE_STORE).getAll();
        const records = await new Promise((resolve, reject) => {
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });

        state.files = records
            .sort((a, b) => (a.order || 0) - (b.order || 0))
            .map((record) => {
                const file = record.file instanceof File
                    ? record.file
                    : new File([record.file], record.name, {
                        type: record.type,
                        lastModified: record.lastModified,
                    });
                return {
                    id: record.id,
                    file,
                    status: record.status || "queued",
                    result: record.result || null,
                    error: record.error || "",
                    requestedEngine: record.requestedEngine || "",
                    actualEngine: record.actualEngine || "",
                };
            });

        const savedIndex = Number(localStorage.getItem(QUEUE_META_INDEX));
        state.currentIndex = state.files.length
            ? clamp(Number.isFinite(savedIndex) ? savedIndex : 0, 0, state.files.length - 1)
            : -1;
    } catch (error) {
        console.warn("Could not restore queue", error);
    } finally {
        state.restoringQueue = false;
    }
}

function setSection(name) {
    Object.entries(sections).forEach(([key, el]) => el.classList.toggle("active", key === name));
    document.querySelectorAll(".nav-item[data-section]").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.section === name);
    });
    if (name === "history") loadHistory();
    if (name === "analytics") loadAnalytics();
}

async function loadSession() {
    const data = await api("/api/session");
    if (!data.authenticated) {
        window.location.href = "/";
        return false;
    }
    $("user-box").textContent = `${data.user.fullname || data.user.username}\n${data.user.email}`;
    return true;
}

function addFiles(fileList) {
    const incoming = Array.from(fileList || []);
    incoming.forEach((file) => {
        state.files.push({
            id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
            file,
            status: "queued",
            result: null,
            error: "",
        });
    });
    if (state.currentIndex === -1 && state.files.length) state.currentIndex = 0;
    renderQueue();
    renderCurrent();
    scheduleQueueSave();
}

function renderQueue() {
    $("upload-note").textContent = state.files.length
        ? `${state.files.length} file(s) in queue.`
        : "No files in queue.";
    $("queue-list").innerHTML = "";

    state.files.forEach((item, index) => {
        const row = document.createElement("div");
        row.className = `queue-item ${index === state.currentIndex ? "active" : ""}`;
        const actualEngine = item.result?.ocr?.engine || item.actualEngine || "";
        const requestedEngine = item.requestedEngine || "";
        const engineNote = actualEngine
            ? ` - engine: ${escapeHtml(actualEngine)}`
            : requestedEngine
                ? ` - requested: ${escapeHtml(requestedEngine)}`
                : "";
        row.innerHTML = `
            <button class="queue-select" type="button">
                <strong>${escapeHtml(item.file.name)}</strong>
                <span class="queue-status">${escapeHtml(item.status)}${engineNote}${item.error ? ` - ${escapeHtml(item.error)}` : ""}</span>
            </button>
            <button class="queue-run" type="button" title="Run selected engine for this file">Run</button>
            <button class="queue-remove" type="button" title="Remove file" aria-label="Remove ${escapeHtml(item.file.name)}">&times;</button>
        `;
        row.querySelector(".queue-select").onclick = () => {
            state.currentIndex = index;
            renderQueue();
            renderCurrent();
            scheduleQueueSave();
        };
        row.querySelector(".queue-run").onclick = (event) => {
            event.stopPropagation();
            state.currentIndex = index;
            processItem(index, { force: true });
        };
        row.querySelector(".queue-remove").onclick = () => removeQueueItem(index);
        $("queue-list").appendChild(row);
    });
}

function removeQueueItem(index) {
    if (index < 0 || index >= state.files.length) return;
    const removingCurrent = index === state.currentIndex;
    state.files.splice(index, 1);

    if (!state.files.length) {
        state.currentIndex = -1;
        state.currentResult = null;
    } else if (removingCurrent) {
        state.currentIndex = Math.min(index, state.files.length - 1);
    } else if (index < state.currentIndex) {
        state.currentIndex -= 1;
    }

    renderQueue();
    renderCurrent();
    scheduleQueueSave();
}

function clearQueue() {
    state.files = [];
    state.currentIndex = -1;
    state.currentResult = null;
    renderQueue();
    renderCurrent();
    clearPersistedQueue().catch((error) => console.warn("Could not clear persisted queue", error));
}

async function processItem(index, { force = true } = {}) {
    const item = state.files[index];
    if (!item || item.status === "processing") return;
    if (!force && item.result) return;

    item.status = "processing";
    item.error = "";
    item.result = force ? null : item.result;
    item.requestedEngine = $("engine").value;
    renderQueue();
    if (state.currentIndex === index) renderCurrent();
    scheduleQueueSave();

    const form = new FormData();
    form.append("file", item.file);
    form.append("engine", item.requestedEngine);
    form.append("preprocessing", "full");

    try {
        item.result = await api("/api/process", { method: "POST", body: form });
        item.actualEngine = item.result?.ocr?.engine || item.result?.actualEngine || item.requestedEngine;
        item.status = "ready";
        if (state.currentIndex === index) renderCurrent();
    } catch (err) {
        item.status = "error";
        item.error = err.message;
    }
    renderQueue();
    scheduleQueueSave();
}

async function processAll() {
    for (let i = 0; i < state.files.length; i += 1) {
        await processItem(i, { force: true });
    }
}

function renderCurrent() {
    const item = state.files[state.currentIndex];
    state.currentResult = item?.result || null;
    $("save-btn").disabled = !state.currentResult;
    $("bbox-layer").innerHTML = "";
    $("fields-container").innerHTML = "";
    $("warnings").classList.add("hidden");
    $("ocr-preview").textContent = "";

    if (!item) {
        $("preview-img").style.display = "none";
        $("empty-preview").style.display = "block";
        $("doc-meta").textContent = "No document selected";
        $("result-summary").textContent = "No result yet";
        updateQuality();
        return;
    }

    $("preview-img").src = URL.createObjectURL(item.file);
    $("preview-img").style.display = "block";
    $("empty-preview").style.display = "none";
    $("doc-meta").textContent = item.file.name;
    applyPreviewZoom();

    if (!item.result) {
        $("result-summary").textContent = `Status: ${item.status}`;
        updateQuality();
        return;
    }

    const result = item.result;
    const requested = result.requestedEngine
        && String(result.requestedEngine).toLowerCase() !== String(result.ocr.engine).toLowerCase()
        ? `requested ${result.requestedEngine}, `
        : "";
    $("result-summary").textContent = `${requested}${result.ocr.engine} - ${result.processingMs}ms - ${result.ocr.word_count} OCR units`;
    $("ocr-preview").textContent = result.ocr.text_preview || "";
    updateQuality(result);
    renderWarnings(result.warnings || []);
    renderFields(result.fields || []);
}

function applyPreviewZoom() {
    const image = $("preview-img");
    const stage = $("image-stage");
    const zoom = clamp(state.previewZoom, 0.5, 3);
    state.previewZoom = zoom;
    $("zoom-label").textContent = `${Math.round(zoom * 100)}%`;
    $("zoom-out-btn").disabled = zoom <= 0.5;
    $("zoom-in-btn").disabled = zoom >= 3;
    stage.style.setProperty("--preview-zoom", zoom);
    image.style.width = `${Math.round(zoom * 100)}%`;
}

function changePreviewZoom(delta) {
    state.previewZoom = clamp(Math.round((state.previewZoom + delta) * 100) / 100, 0.5, 3);
    applyPreviewZoom();
}

function updateQuality(result = null) {
    const boxes = $("quality-strip").querySelectorAll("strong");
    boxes[0].textContent = result?.certType || "-";
    boxes[1].textContent = result ? percent(result.confidence || 0) : "-";
    boxes[2].textContent = result ? `${result.quality.valid_fields}/${result.quality.total_fields}` : "-";
    boxes[3].textContent = result ? result.quality.review_fields : "-";
}

function renderWarnings(warnings) {
    if (!warnings.length) return;
    $("warnings").classList.remove("hidden");
    $("warnings").innerHTML = warnings.map((warning) => `<div>${escapeHtml(warning)}</div>`).join("");
}

function renderFields(fields) {
    fields.forEach((field, index) => {
        const card = document.createElement("div");
        card.className = "field-card";
        card.dataset.index = index;
        card.innerHTML = `
            <div class="field-top">
                <div class="field-label">${escapeHtml(field.label)}</div>
                <span class="field-badge ${escapeHtml(field.status)}">${escapeHtml(field.status)}</span>
            </div>
            <input value="${escapeHtml(field.value || "")}" data-key="${escapeHtml(field.key)}" />
            <div class="field-meta">
                confidence ${percent(field.confidence || 0)} - ${escapeHtml(field.source || "unknown")}
                ${field.warnings?.length ? `<br>${field.warnings.map(escapeHtml).join("<br>")}` : ""}
            </div>
        `;
        card.onclick = () => highlightField(field, index);
        card.querySelector("input").oninput = (event) => {
            field.value = event.target.value;
            state.currentResult.entries[field.key] = field.value;
        };
        $("fields-container").appendChild(card);
    });
}

function highlightField(field, index) {
    document.querySelectorAll(".field-card").forEach((el) => el.classList.toggle("active", Number(el.dataset.index) === index));
    $("bbox-layer").innerHTML = "";
}

async function saveCurrent() {
    if (!state.currentResult) return;
    const payload = state.currentResult;
    payload.reviewStatus = "confirmed";
    const out = await api("/api/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            file_name: payload.fileName,
            cert_type: payload.certType,
            confidence: payload.confidence,
            payload,
        }),
    });
    alert(`Saved certificate #${out.id}`);
    loadHistory();
}

function renderTypeBreakdown(byType = {}) {
    const entries = Object.entries(byType);
    if (!entries.length) return `<span class="muted">No saved certificates yet.</span>`;
    return entries
        .sort((a, b) => b[1] - a[1])
        .map(([key, value]) => `<span class="type-pill">${escapeHtml(key)} <strong>${value}</strong></span>`)
        .join("");
}

function renderIssueList(items = []) {
    if (!items.length) return `<div class="empty-state">No review or missing fields recorded.</div>`;
    return items
        .map((item) => `
            <div class="issue-row">
                <span>${escapeHtml(item.field)}</span>
                <strong>${item.total}</strong>
                <small>${item.review} review / ${item.missing} missing</small>
            </div>
        `)
        .join("");
}

function renderBarList(items = {}, { empty = "No records yet." } = {}) {
    const entries = Object.entries(items || {}).sort((a, b) => b[1] - a[1]);
    if (!entries.length) return `<div class="empty-state compact">${escapeHtml(empty)}</div>`;
    const maxValue = Math.max(...entries.map(([, value]) => Number(value) || 0), 1);
    const total = entries.reduce((sum, [, value]) => sum + (Number(value) || 0), 0);
    return `
        <div class="bar-list">
            ${entries.map(([label, value]) => {
                const width = clampPercent(((Number(value) || 0) / maxValue) * 100);
                const share = total ? ((Number(value) || 0) / total) * 100 : 0;
                return `
                    <div class="bar-row">
                        <div class="bar-label">
                            <strong>${escapeHtml(label)}</strong>
                            <span>${value} record(s) - ${share.toFixed(1)}%</span>
                        </div>
                        <div class="bar-track" aria-hidden="true">
                            <div class="bar-fill" style="width: ${width}%"></div>
                        </div>
                    </div>
                `;
            }).join("")}
        </div>
    `;
}

function renderStackedQuality(data) {
    const valid = Number(data.validFields) || 0;
    const review = Number(data.reviewFields) || 0;
    const missing = Number(data.missingFields) || 0;
    const total = Math.max(valid + review + missing, 1);
    const validWidth = clampPercent((valid / total) * 100);
    const reviewWidth = clampPercent((review / total) * 100);
    const missingWidth = clampPercent((missing / total) * 100);
    return `
        <div class="stacked-summary">
            <div class="stacked-bar" aria-label="Field status distribution">
                <span class="stack-segment valid" style="width: ${validWidth}%"></span>
                <span class="stack-segment review" style="width: ${reviewWidth}%"></span>
                <span class="stack-segment missing" style="width: ${missingWidth}%"></span>
            </div>
            <div class="chart-legend">
                <span><i class="legend-dot valid"></i>${valid} valid (${((valid / total) * 100).toFixed(1)}%)</span>
                <span><i class="legend-dot review"></i>${review} review (${((review / total) * 100).toFixed(1)}%)</span>
                <span><i class="legend-dot missing"></i>${missing} missing (${((missing / total) * 100).toFixed(1)}%)</span>
            </div>
        </div>
    `;
}

function renderQualityGauge(data) {
    const validity = clampPercent((Number(data.fieldValidityRate) || 0) * 100);
    const review = clampPercent((Number(data.reviewRate) || 0) * 100);
    const missing = clampPercent((Number(data.missingRate) || 0) * 100);
    return `
        <div class="gauge-grid">
            <div class="gauge-card">
                <div class="gauge-ring" style="--value: ${validity}; --ring-color: var(--green);">
                    <span>${validity.toFixed(1)}%</span>
                </div>
                <strong>Valid extraction rate</strong>
            </div>
            <div class="gauge-card">
                <div class="gauge-ring" style="--value: ${review}; --ring-color: #f59e0b;">
                    <span>${review.toFixed(1)}%</span>
                </div>
                <strong>Review burden</strong>
            </div>
            <div class="gauge-card">
                <div class="gauge-ring" style="--value: ${missing}; --ring-color: var(--red);">
                    <span>${missing.toFixed(1)}%</span>
                </div>
                <strong>Missing rate</strong>
            </div>
        </div>
    `;
}

function renderHistoryAnalysis(data) {
    $("history-analysis").innerHTML = `
        <div class="analysis-card accent-blue">
            <span>Total saved</span>
            <strong>${data.totalCertificates}</strong>
            <small>${renderTypeBreakdown(data.byType)}</small>
        </div>
        <div class="analysis-card accent-green">
            <span>Field validity</span>
            <strong>${percent(data.fieldValidityRate, 1)}</strong>
            <small>${data.validFields}/${data.totalFields} valid fields</small>
        </div>
        <div class="analysis-card accent-amber">
            <span>Review burden</span>
            <strong>${data.reviewFields}</strong>
            <small>${percent(data.reviewRate, 1)} of saved fields</small>
        </div>
        <div class="analysis-card accent-red">
            <span>Missing fields</span>
            <strong>${data.missingFields}</strong>
            <small>${percent(data.missingRate, 1)} of saved fields</small>
        </div>
        <div class="analysis-card wide">
            <span>Saved-record quality overview</span>
            ${renderStackedQuality(data)}
        </div>
        <div class="analysis-card wide">
            <span>Top fields needing attention</span>
            <div class="issue-list">${renderIssueList(data.topFieldIssues)}</div>
        </div>
    `;
}

async function loadHistory() {
    const [rows, analysis] = await Promise.all([
        api("/api/my-certificates"),
        api("/api/history-analysis"),
    ]);
    renderHistoryAnalysis(analysis);
    $("history-body").innerHTML = rows.map((row) => `
        <tr>
            <td>${escapeHtml(row.created_at)}</td>
            <td>${escapeHtml(row.file_name)}</td>
            <td>${escapeHtml(row.cert_type)}</td>
            <td>${percent(row.confidence || 0)}</td>
            <td>${row.valid_fields}/${row.total_fields} valid, ${row.review_fields} review</td>
            <td><button class="ghost-btn" data-id="${row.id}">Open</button></td>
        </tr>
    `).join("") || `<tr><td colspan="6" class="empty-state">No saved certificates yet.</td></tr>`;
}

async function openDetail(id) {
    const data = await api(`/api/get-certificate/${id}`);
    state.currentDetailId = id;
    const payload = data.payload || {};
    $("modal-title").textContent = `${data.file_name} - ${data.cert_type}`;
    $("modal-content").innerHTML = (payload.fields || []).map((field, index) => `
        <div class="field-card">
            <div class="field-top">
                <div class="field-label">${escapeHtml(field.label)}</div>
                <span class="field-badge ${escapeHtml(field.status)}">${escapeHtml(field.status)}</span>
            </div>
            <input value="${escapeHtml(field.value || "")}" data-index="${index}" />
            <div class="field-meta">${escapeHtml(field.key)} - ${escapeHtml(field.source || "unknown")}</div>
        </div>
    `).join("");
    $("detail-modal").dataset.payload = JSON.stringify(payload);
    $("detail-modal").classList.remove("hidden");
}

async function saveDetail() {
    const payload = JSON.parse($("detail-modal").dataset.payload || "{}");
    $("modal-content").querySelectorAll("input").forEach((input) => {
        const field = payload.fields[Number(input.dataset.index)];
        field.value = input.value;
        payload.entries[field.key] = field.value;
    });
    await api(`/api/update-certificate/${state.currentDetailId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    $("detail-modal").classList.add("hidden");
    loadHistory();
    loadAnalytics();
}

async function deleteDetail() {
    if (!confirm("Delete this certificate?")) return;
    await api(`/api/delete-certificate/${state.currentDetailId}`, { method: "DELETE" });
    $("detail-modal").classList.add("hidden");
    loadHistory();
    loadAnalytics();
}

async function loadAnalytics() {
    const data = await api("/api/analytics");
    $("analytics-grid").innerHTML = `
        <div><span>Total certificates</span><strong>${data.totalCertificates}</strong></div>
        <div><span>Average confidence</span><strong>${percent(data.averageConfidence, 1)}</strong></div>
        <div><span>Field validity</span><strong>${percent(data.fieldValidityRate, 1)}</strong></div>
        <div><span>Need review</span><strong>${data.reviewFields}</strong></div>
    `;
    $("analytics-details").innerHTML = `
        <div class="analysis-panel wide-panel">
            <h2>Field quality distribution</h2>
            ${renderStackedQuality(data)}
        </div>
        <div class="analysis-panel wide-panel">
            <h2>Quality gauges</h2>
            ${renderQualityGauge(data)}
        </div>
        <div class="analysis-panel">
            <h2>OCR engine usage</h2>
            ${renderBarList(data.byEngine, { empty: "No OCR engine data yet." })}
        </div>
        <div class="analysis-panel">
            <h2>Certificate distribution</h2>
            ${renderBarList(data.byType, { empty: "No certificate data yet." })}
        </div>
        <div class="analysis-panel">
            <h2>Top fields needing attention</h2>
            <div class="issue-list">${renderIssueList(data.topFieldIssues)}</div>
        </div>
    `;
}

function exportHistoryCsv() {
    window.location.href = "/api/export-certificates.csv";
}

document.querySelectorAll(".nav-item[data-section]").forEach((btn) => {
    btn.onclick = () => setSection(btn.dataset.section);
});

$("file-input").onchange = (event) => addFiles(event.target.files);
$("folder-input").onchange = (event) => addFiles(event.target.files);
$("process-all-btn").onclick = processAll;
$("clear-queue-btn").onclick = clearQueue;
$("engine").onchange = renderQueue;
$("zoom-out-btn").onclick = () => changePreviewZoom(-0.15);
$("zoom-in-btn").onclick = () => changePreviewZoom(0.15);
$("save-btn").onclick = saveCurrent;
$("refresh-history-btn").onclick = loadHistory;
$("export-history-btn").onclick = exportHistoryCsv;
$("refresh-analytics-btn").onclick = loadAnalytics;
$("history-body").onclick = (event) => {
    const id = event.target.dataset.id;
    if (id) openDetail(id);
};
$("modal-close").onclick = () => $("detail-modal").classList.add("hidden");
$("modal-save").onclick = saveDetail;
$("modal-delete").onclick = deleteDetail;
$("logout-btn").onclick = async () => {
    await api("/api/logout", { method: "POST" });
    window.location.href = "/";
};

async function boot() {
    const authenticated = await loadSession();
    if (!authenticated) return;
    await restoreQueue();
    renderQueue();
    renderCurrent();
    applyPreviewZoom();
}

boot();
