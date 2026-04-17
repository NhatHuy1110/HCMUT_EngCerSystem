const state = {
    files: [],
    currentIndex: -1,
    currentResult: null,
    currentDetailId: null,
};

const $ = (id) => document.getElementById(id);

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
        return;
    }
    $("user-box").textContent = `${data.user.fullname || data.user.username}\n${data.user.email}`;
}

function addFiles(fileList) {
    const incoming = Array.from(fileList || []);
    incoming.forEach((file) => {
        state.files.push({ file, status: "queued", result: null, error: "" });
    });
    if (state.currentIndex === -1 && state.files.length) state.currentIndex = 0;
    renderQueue();
    renderCurrent();
}

function renderQueue() {
    $("upload-note").textContent = state.files.length
        ? `${state.files.length} file trong queue.`
        : "Chưa có file nào trong queue.";
    $("queue-list").innerHTML = "";

    state.files.forEach((item, index) => {
        const row = document.createElement("div");
        row.className = `queue-item ${index === state.currentIndex ? "active" : ""}`;
        row.innerHTML = `
            <button class="queue-select" type="button">
                <strong>${item.file.name}</strong>
                <span class="queue-status">${item.status}${item.error ? ` - ${item.error}` : ""}</span>
            </button>
            <button class="queue-remove" type="button" title="Xoa file nay" aria-label="Xoa ${escapeAttr(item.file.name)}">&times;</button>
        `;
        row.querySelector(".queue-select").onclick = () => {
            state.currentIndex = index;
            renderQueue();
            renderCurrent();
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
}

function clearQueue() {
    state.files = [];
    state.currentIndex = -1;
    state.currentResult = null;
    renderQueue();
    renderCurrent();
}

async function processItem(index) {
    const item = state.files[index];
    if (!item || item.status === "processing") return;

    item.status = "processing";
    item.error = "";
    renderQueue();

    const form = new FormData();
    form.append("file", item.file);
    form.append("engine", $("engine").value);

    try {
        item.result = await api("/api/process", { method: "POST", body: form });
        item.status = "ready";
        if (state.currentIndex === index) renderCurrent();
    } catch (err) {
        item.status = "error";
        item.error = err.message;
    }
    renderQueue();
}

async function processAll() {
    for (let i = 0; i < state.files.length; i += 1) {
        if (!state.files[i].result) await processItem(i);
    }
}

function renderCurrent() {
    const item = state.files[state.currentIndex];
    state.currentResult = item?.result || null;
    $("save-btn").disabled = !state.currentResult;
    $("bbox-layer").innerHTML = "";
    $("fields-container").innerHTML = "";
    $("warnings").classList.add("hidden");

    if (!item) {
        $("preview-img").style.display = "none";
        $("empty-preview").style.display = "block";
        $("doc-meta").textContent = "Chưa chọn tài liệu";
        $("result-summary").textContent = "Chưa có kết quả";
        updateQuality();
        return;
    }

    $("preview-img").src = URL.createObjectURL(item.file);
    $("preview-img").style.display = "block";
    $("empty-preview").style.display = "none";
    $("doc-meta").textContent = item.file.name;

    if (!item.result) {
        $("result-summary").textContent = `Trạng thái: ${item.status}`;
        updateQuality();
        return;
    }

    const result = item.result;
    $("result-summary").textContent = `${result.ocr.engine} - ${result.processingMs}ms - ${result.ocr.word_count} words`;
    $("ocr-preview").textContent = result.ocr.text_preview || "";
    updateQuality(result);
    renderWarnings(result.warnings || []);
    renderFields(result.fields || []);
}

function updateQuality(result = null) {
    const boxes = $("quality-strip").querySelectorAll("strong");
    boxes[0].textContent = result?.certType || "-";
    boxes[1].textContent = result ? `${Math.round((result.confidence || 0) * 100)}%` : "-";
    boxes[2].textContent = result ? `${result.quality.valid_fields}/${result.quality.total_fields}` : "-";
    boxes[3].textContent = result ? result.quality.review_fields : "-";
}

function renderWarnings(warnings) {
    if (!warnings.length) return;
    $("warnings").classList.remove("hidden");
    $("warnings").innerHTML = warnings.map((warning) => `<div>${warning}</div>`).join("");
}

function renderFields(fields) {
    fields.forEach((field, index) => {
        const card = document.createElement("div");
        card.className = "field-card";
        card.dataset.index = index;
        card.innerHTML = `
            <div class="field-top">
                <div class="field-label">${field.label}</div>
                <span class="field-badge ${field.status}">${field.status}</span>
            </div>
            <input value="${escapeAttr(field.value || "")}" data-key="${field.key}" />
            <div class="field-meta">
                confidence ${Math.round((field.confidence || 0) * 100)}% - ${field.source}
                ${field.warnings?.length ? `<br>${field.warnings.join("<br>")}` : ""}
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

function escapeAttr(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll('"', "&quot;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function highlightField(field, index) {
    document.querySelectorAll(".field-card").forEach((el) => el.classList.toggle("active", Number(el.dataset.index) === index));
    drawBbox();
}

function drawBbox() {
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
    alert(`Đã lưu chứng chỉ #${out.id}`);
    loadHistory();
}

async function loadHistory() {
    const rows = await api("/api/my-certificates");
    $("history-body").innerHTML = rows.map((row) => `
        <tr>
            <td>${row.created_at}</td>
            <td>${row.file_name}</td>
            <td>${row.cert_type}</td>
            <td>${Math.round((row.confidence || 0) * 100)}%</td>
            <td>${row.valid_fields}/${row.total_fields} valid, ${row.review_fields} review</td>
            <td><button class="ghost-btn" data-id="${row.id}">Xem</button></td>
        </tr>
    `).join("");
}

async function openDetail(id) {
    const data = await api(`/api/get-certificate/${id}`);
    state.currentDetailId = id;
    const payload = data.payload || {};
    $("modal-title").textContent = `${data.file_name} - ${data.cert_type}`;
    $("modal-content").innerHTML = (payload.fields || []).map((field, index) => `
        <div class="field-card">
            <div class="field-top">
                <div class="field-label">${field.label}</div>
                <span class="field-badge ${field.status}">${field.status}</span>
            </div>
            <input value="${escapeAttr(field.value || "")}" data-index="${index}" />
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
}

async function deleteDetail() {
    if (!confirm("Xóa chứng chỉ này?")) return;
    await api(`/api/delete-certificate/${state.currentDetailId}`, { method: "DELETE" });
    $("detail-modal").classList.add("hidden");
    loadHistory();
}

async function loadAnalytics() {
    const data = await api("/api/analytics");
    const types = Object.entries(data.byType || {}).map(([key, value]) => `${key}: ${value}`).join("<br>") || "-";
    $("analytics-grid").innerHTML = `
        <div><span>Tổng chứng chỉ</span><strong>${data.totalCertificates}</strong></div>
        <div><span>Field hợp lệ</span><strong>${data.validFields}/${data.totalFields}</strong></div>
        <div><span>Cần review</span><strong>${data.reviewFields}</strong></div>
        <div><span>Theo loại</span><strong style="font-size:18px">${types}</strong></div>
    `;
}

document.querySelectorAll(".nav-item[data-section]").forEach((btn) => {
    btn.onclick = () => setSection(btn.dataset.section);
});

$("file-input").onchange = (event) => addFiles(event.target.files);
$("folder-input").onchange = (event) => addFiles(event.target.files);
$("process-all-btn").onclick = processAll;
$("clear-queue-btn").onclick = clearQueue;
$("save-btn").onclick = saveCurrent;
$("refresh-history-btn").onclick = loadHistory;
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

loadSession();
renderQueue();
renderCurrent();
