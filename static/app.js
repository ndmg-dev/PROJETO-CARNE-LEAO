/**
 * Carnê-Leão 2024 — Frontend Application Logic
 * Handles API calls, SSE processing, DOM rendering, inline editing.
 */

// ═══ State ═══════════════════════════════════════════════
let allDocuments = [];
let currentMonth = "all";
let currentStatus = "all";
let currentSearch = "";
let selectedDocId = null;

// ═══ DOM Elements ════════════════════════════════════════
const $ = (id) => document.getElementById(id);

const els = {
    apiKey: $("apiKey"),
    btnProcess: $("btnProcess"),
    btnExport: $("btnExport"),
    btnAllMonths: $("btnAllMonths"),
    monthCards: $("monthCards"),
    filterStatus: $("filterStatus"),
    searchInput: $("searchInput"),
    documentsBody: $("documentsBody"),
    resultCount: $("resultCount"),
    emptyState: $("emptyState"),
    tableWrapper: document.querySelector(".table-wrapper"),
    // Stats
    statTotal: $("statTotal"),
    statOk: $("statOk"),
    statReview: $("statReview"),
    statError: $("statError"),
    statPending: $("statPending"),
    countAll: $("countAll"),
    // Modal
    processModal: $("processModal"),
    progressFill: $("progressFill"),
    progressText: $("progressText"),
    progressPercent: $("progressPercent"),
    progressFile: $("progressFile"),
    progressLog: $("progressLog"),
    // Fullscreen
    fullscreenModal: $("fullscreenModal"),
    fullscreenImg: $("fullscreenImg"),
    btnCloseFullscreen: $("btnCloseFullscreen"),
    // Overlay
    overlay: $("overlay"),
    toastContainer: $("toastContainer"),
};


// ═══ Initialization ══════════════════════════════════════
document.addEventListener("DOMContentLoaded", () => {
    // Try loading API key from localStorage
    const savedKey = localStorage.getItem("openai_api_key");
    if (savedKey) els.apiKey.value = savedKey;

    // Save API key on change
    els.apiKey.addEventListener("input", () => {
        localStorage.setItem("openai_api_key", els.apiKey.value);
    });

    // Event listeners
    els.btnProcess.addEventListener("click", startProcessing);
    els.btnExport.addEventListener("click", exportExcel);
    
    // Fullscreen Modal Listeners
    els.btnCloseFullscreen.addEventListener("click", closeFullscreen);
    els.fullscreenModal.addEventListener("click", (e) => {
        if (e.target === els.fullscreenModal) closeFullscreen();
    });

    els.filterStatus.addEventListener("change", () => {
        currentStatus = els.filterStatus.value;
        renderTable();
    });
    els.searchInput.addEventListener("input", () => {
        currentSearch = els.searchInput.value.toLowerCase();
        renderTable();
    });
    els.btnAllMonths.addEventListener("click", () => selectMonth("all"));

    // Initial data load
    loadScan();
    loadDocuments();
});


// ═══ API Calls ═══════════════════════════════════════════

async function loadScan() {
    try {
        const res = await fetch("/api/scan");
        const data = await res.json();
        if (data.error) {
            toast(data.error, "error");
            return;
        }
        renderMonthCards(data.months);
    } catch (e) {
        toast("Erro ao escanear pastas: " + e.message, "error");
    }
}

async function loadDocuments() {
    try {
        const res = await fetch("/api/documents");
        const data = await res.json();
        allDocuments = data.documents || [];
        renderTable();
        loadStats();
    } catch (e) {
        // DB might be empty on first run, that's OK
    }
}

async function loadStats() {
    try {
        const res = await fetch("/api/stats");
        const stats = await res.json();
        els.statTotal.textContent = stats.total || 0;
        els.statOk.textContent = stats.ok || 0;
        els.statReview.textContent = stats.review || 0;
        els.statError.textContent = stats.error || 0;
        els.statPending.textContent = stats.pending || 0;
        els.countAll.textContent = stats.total || 0;
    } catch (e) { /* ignore */ }
}

function startProcessing() {
    const apiKey = els.apiKey.value.trim();
    if (!apiKey) {
        toast("Cole sua chave de API da OpenAI acima antes de processar.", "error");
        els.apiKey.focus();
        return;
    }

    // Open modal
    els.processModal.classList.add("open");
    els.overlay.classList.add("open");
    els.btnProcess.disabled = true;
    els.progressLog.innerHTML = "";
    els.progressFill.style.width = "0%";
    els.progressPercent.textContent = "0%";
    els.progressText.textContent = "Conectando…";
    els.progressFile.textContent = "";

    const url = `/api/process?api_key=${encodeURIComponent(apiKey)}`;
    const source = new EventSource(url);

    source.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
            case "start":
                els.progressText.textContent = `Processando ${msg.total} documentos…`;
                logEntry(`Iniciando processamento de ${msg.total} arquivos…`, "");
                break;

            case "processing":
                updateProgress(msg.current, msg.total);
                els.progressFile.textContent = `${msg.month} → ${msg.file}`;
                break;

            case "processed":
                updateProgress(msg.current, msg.total);
                const doc = msg.document;
                const statusClass = doc.status === "ok" ? "log-ok"
                    : doc.status === "review" ? "log-review" : "log-error";
                const icon = doc.status === "ok" ? "✅"
                    : doc.status === "review" ? "⚠️" : "❌";
                logEntry(`${icon} ${doc.filename}`, statusClass);
                break;

            case "skipped":
                updateProgress(msg.current, msg.total);
                logEntry(`⏭️ ${msg.file} (já processado)`, "log-skip");
                break;

            case "error":
                toast(msg.message, "error");
                logEntry(`❌ ERRO: ${msg.message}`, "log-error");
                break;

            case "done":
                els.progressText.textContent = "✅ Concluído!";
                els.progressPercent.textContent = "100%";
                els.progressFill.style.width = "100%";
                els.progressFile.textContent = "";
                logEntry(`\n✅ Processamento finalizado! ${msg.total} documentos.`, "log-ok");

                // Refresh data
                setTimeout(() => {
                    els.processModal.classList.remove("open");
                    els.overlay.classList.remove("open");
                    els.btnProcess.disabled = false;
                    loadDocuments();
                    toast("Processamento concluído com sucesso!", "success");
                }, 2000);

                source.close();
                break;
        }
    };

    source.onerror = () => {
        source.close();
        els.processModal.classList.remove("open");
        els.overlay.classList.remove("open");
        els.btnProcess.disabled = false;
        loadDocuments();
    };
}

function updateProgress(current, total) {
    const pct = Math.round((current / total) * 100);
    els.progressFill.style.width = pct + "%";
    els.progressPercent.textContent = pct + "%";
    els.progressText.textContent = `${current} de ${total}`;
}

function logEntry(text, className) {
    const line = document.createElement("div");
    line.className = className;
    line.textContent = text;
    els.progressLog.appendChild(line);
    els.progressLog.scrollTop = els.progressLog.scrollHeight;
}

async function exportExcel() {
    try {
        toast("Gerando planilha...", "info");
        const res = await fetch("/api/export", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ documents: allDocuments })
        });
        if (!res.ok) throw new Error("Erro ao gerar Excel");
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "despesas_carne_leao_2024.xlsx";
        a.click();
        URL.revokeObjectURL(url);
        toast("📊 Excel exportado com sucesso!", "success");
    } catch (e) {
        toast("Erro ao exportar: " + e.message, "error");
    }
}


// ═══ Rendering ═══════════════════════════════════════════

function renderMonthCards(months) {
    els.monthCards.innerHTML = "";
    months.forEach((m) => {
        const btn = document.createElement("button");
        btn.className = "month-card";
        btn.dataset.month = m.month_num;
        btn.innerHTML = `
            <span class="month-dot dot-none"></span>
            <span class="month-name">${m.name.replace(/^\d+\s*-\s*/, "")}</span>
            <span class="month-count">${m.total_files}</span>
        `;
        btn.addEventListener("click", () => selectMonth(m.month_num));
        els.monthCards.appendChild(btn);
    });
}

function selectMonth(month) {
    currentMonth = month;
    // Update active state
    document.querySelectorAll(".month-card").forEach((c) => c.classList.remove("active"));
    if (month === "all") {
        els.btnAllMonths.classList.add("active");
    } else {
        const card = document.querySelector(`.month-card[data-month="${month}"]`);
        if (card) card.classList.add("active");
    }
    renderTable();
}

function renderTable() {
    let filtered = allDocuments;

    // Filter by month
    if (currentMonth !== "all") {
        filtered = filtered.filter((d) => d.month_num === currentMonth);
    }

    // Filter by status
    if (currentStatus !== "all") {
        filtered = filtered.filter((d) => d.status === currentStatus);
    }

    // Filter by search
    if (currentSearch) {
        filtered = filtered.filter((d) =>
            (d.filename || "").toLowerCase().includes(currentSearch) ||
            (d.description || "").toLowerCase().includes(currentSearch)
        );
    }

    // Show/hide empty state
    if (filtered.length === 0 && allDocuments.length === 0) {
        els.emptyState.classList.remove("hidden");
        els.tableWrapper.style.display = "none";
    } else {
        els.emptyState.classList.add("hidden");
        els.tableWrapper.style.display = "";
    }

    // Update result count
    els.resultCount.textContent = `${filtered.length} documento(s)`;

    // Render rows
    els.documentsBody.innerHTML = "";
    filtered.forEach((doc) => {
        const tr = document.createElement("tr");
        tr.className = `row-${doc.status}`;
        tr.dataset.id = doc.id;

        const statusBadge = getStatusBadge(doc.status);
        const confBadge = getConfidenceBadge(doc.confidence);
        const dateDisplay = doc.date || "—";
        const valueDisplay = doc.value != null ? formatCurrency(doc.value) : "—";
        const monthShort = (doc.month || "").replace(/^\d+\s*-\s*/, "");

        tr.innerHTML = `
            <td><span class="text-muted">${monthShort}</span></td>
            <td title="${doc.filename}">${truncate(doc.description || doc.filename, 35)}</td>
            <td>${dateDisplay}</td>
            <td class="td-value">${valueDisplay}</td>
            <td>${confBadge}</td>
            <td>${statusBadge}</td>
            <td>
                <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation(); openPreview(${doc.id})">
                    👁️ Ver
                </button>
            </td>
        `;

        tr.addEventListener("click", () => toggleDrillDown(tr, doc));
        els.documentsBody.appendChild(tr);
    });

    // Update month dots based on document statuses
    updateMonthDots();
}

function updateMonthDots() {
    document.querySelectorAll(".month-card[data-month]").forEach((card) => {
        const month = card.dataset.month;
        if (month === "all") return;
        const docs = allDocuments.filter((d) => d.month_num === month);
        const dot = card.querySelector(".month-dot");

        if (docs.length === 0) {
            dot.className = "month-dot dot-none";
        } else if (docs.every((d) => d.status === "ok")) {
            dot.className = "month-dot dot-ok";
        } else if (docs.some((d) => d.status === "error")) {
            dot.className = "month-dot dot-error";
        } else if (docs.some((d) => d.status === "review")) {
            dot.className = "month-dot dot-review";
        } else if (docs.some((d) => d.status === "pending")) {
            dot.className = "month-dot dot-pending";
        } else {
            dot.className = "month-dot dot-ok";
        }
    });
}


// ═══ Drill Down ═════════════════════════════════════════

async function toggleDrillDown(tr, doc) {
    const isAlreadyOpen = tr.nextElementSibling && tr.nextElementSibling.classList.contains("drill-down-row");
    
    // Fecha qualquer drill-down aberto
    document.querySelectorAll(".drill-down-row").forEach(el => el.remove());
    selectedDocId = null;

    // Se clicou na mesma linha que já estava aberta, apenas fecha (comportamento de toggle)
    if (isAlreadyOpen) {
        return;
    }

    selectedDocId = doc.id;

    // Clonar template
    const template = document.getElementById("drillDownTemplate");
    const clone = template.content.cloneNode(true);
    const drillDownRow = clone.querySelector(".drill-down-row");

    // Preencher formulário
    clone.querySelector(".previewTitle").textContent = doc.filename || "Documento";
    const editDate = clone.querySelector(".editDate");
    const editValue = clone.querySelector(".editValue");
    editDate.value = doc.date || "";
    editValue.value = doc.value != null ? doc.value : "";
    clone.querySelector(".editDescription").value = doc.description || "";
    clone.querySelector(".editType").textContent = doc.observation || "—";
    clone.querySelector(".editConfidence").innerHTML = getConfidenceBadge(doc.confidence);

    const img = clone.querySelector(".previewImg");
    const loading = clone.querySelector(".previewLoading");
    const btnClose = clone.querySelector(".btnClosePreview");
    const btnSave = clone.querySelector(".btnSaveEdit");

    // Eventos
    btnClose.addEventListener("click", () => drillDownRow.remove());
    btnSave.addEventListener("click", () => saveDrillDownEdit(doc.id, editDate.value, editValue.value, drillDownRow));
    img.addEventListener("click", () => openFullscreen(img.src));

    // Inserir após a linha clicada
    tr.parentNode.insertBefore(clone, tr.nextSibling);

    // Carregar preview da imagem
    img.style.display = "none";
    try {
        const res = await fetch(`/api/preview/${doc.id}`);
        if (res.ok) {
            const blob = await res.blob();
            img.src = URL.createObjectURL(blob);
            img.style.display = "block";
        }
    } catch (e) {
        /* preview failed */
    }
    loading.classList.add("hidden");
}

async function saveDrillDownEdit(docId, date, value, drillDownRow) {
    date = date.trim();
    value = value.trim();

    try {
        const res = await fetch(`/api/document/${docId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ date: date || null, value: value || null }),
        });
        
        let data = {};
        if (res.ok) {
            data = await res.json();
        }

        // Se falhou (ex: Vercel read-only db) ou deu sucesso, aplicamos as mudanças localmente!
        const idx = allDocuments.findIndex((d) => d.id === docId);
        if (idx >= 0) {
            if (data.success && data.document) {
                allDocuments[idx] = data.document;
            } else {
                // Fallback local
                allDocuments[idx].date = date || null;
                // Try to parse value to float, handles comma or dot
                let parsedValue = null;
                if (value) {
                    const cleanValue = value.replace(/\./g, "").replace(",", ".");
                    parsedValue = parseFloat(cleanValue);
                }
                allDocuments[idx].value = parsedValue;
                allDocuments[idx].status = "ok";
                allDocuments[idx].manually_edited = 1;
            }
        }
        
        toast("💾 Alterações salvas!", "success");
        drillDownRow.remove();
        selectedDocId = null;
        renderTable();
        loadStats();
    } catch (e) {
        toast("Erro ao salvar no servidor, mas aplicado na tela. Exporte para Excel antes de fechar!", "info");
        // Apply locally even on network error
        const idx = allDocuments.findIndex((d) => d.id === docId);
        if (idx >= 0) {
            allDocuments[idx].date = date || null;
            allDocuments[idx].value = value || null;
            allDocuments[idx].status = "ok";
        }
        drillDownRow.remove();
        selectedDocId = null;
        renderTable();
        loadStats();
    }
}


// ═══ Fullscreen Image ════════════════════════════════════

function openFullscreen(src) {
    if (!src || src.endsWith("undefined")) return;
    els.fullscreenImg.src = src;
    els.fullscreenModal.classList.add("open");
}

function closeFullscreen() {
    els.fullscreenModal.classList.remove("open");
    setTimeout(() => { els.fullscreenImg.src = ""; }, 300);
}


// ═══ Helpers ═════════════════════════════════════════════

function getStatusBadge(status) {
    const map = {
        ok: '<span class="badge badge-ok">✅ Extraído</span>',
        review: '<span class="badge badge-review">⚠️ Revisão</span>',
        error: '<span class="badge badge-error">❌ Falha</span>',
        pending: '<span class="badge badge-pending">⏳ Pendente</span>',
    };
    return map[status] || `<span class="badge">${status}</span>`;
}

function getConfidenceBadge(conf) {
    const map = {
        alta: '<span class="badge badge-conf-alta">Alta</span>',
        media: '<span class="badge badge-conf-media">Média</span>',
        baixa: '<span class="badge badge-conf-baixa">Baixa</span>',
    };
    return map[conf] || `<span class="badge">${conf || "—"}</span>`;
}

function formatCurrency(value) {
    if (value == null) return "—";
    return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
    }).format(value);
}

function truncate(text, maxLen) {
    if (!text) return "";
    return text.length > maxLen ? text.substring(0, maxLen) + "…" : text;
}

function toast(message, type = "info") {
    const div = document.createElement("div");
    div.className = `toast toast-${type}`;
    div.textContent = message;
    els.toastContainer.appendChild(div);
    setTimeout(() => div.remove(), 4000);
}
