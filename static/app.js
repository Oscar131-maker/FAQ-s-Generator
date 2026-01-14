document.addEventListener('DOMContentLoaded', () => {
    // State
    const state = {
        templates: [],
        currentTemplateIndex: 0,
        isGenerating: false,
        generatedCode: null,
        history: [],

        // Dirty State for "Generate" button logic
        lastSavedInputState: null,
        currentInputState: {},
    };

    // DOM Elements - Main
    const els = {
        btnGenerate: document.getElementById('btnGenerate'),
        btnView: document.getElementById('btnView'),
        btnRecet: document.getElementById('btnRecet'),
        btnSettings: document.querySelector('.settings-btn'),

        keywordInput: document.getElementById('keywordInput'),
        briefInput: document.getElementById('briefInput'),
        sourceRadios: document.querySelectorAll('input[name="sourceType"]'),
        urlContainer: document.getElementById('urlInputContainer'),
        textContainer: document.getElementById('textInputContainer'),
        urlInput: document.getElementById('urlInput'),
        textInput: document.getElementById('textInput'),

        // Template
        prevTemplate: document.getElementById('prevTemplate'),
        nextTemplate: document.getElementById('nextTemplate'),
        templateImg: document.getElementById('templateImg'),
        templateName: document.getElementById('templateName'),

        // Result Modal
        resultModal: document.getElementById('resultModal'),
        btnCloseResultModal: document.getElementById('btnCloseModal'),
        resultCode: document.getElementById('resultCode'),
        btnDownload: document.getElementById('btnDownload'),
        btnCopy: document.getElementById('btnCopy'),

        // History
        historyList: document.getElementById('historyList'),

        // Settings Modal
        settingsModal: document.getElementById('settingsModal'),
        btnCloseSettings: document.getElementById('btnCloseSettings'),
        tabBtns: document.querySelectorAll('.tab-btn'),
        tabContents: document.querySelectorAll('.tab-content'),

        // Settings - Prompts
        promptClaude: document.getElementById('promptClaude'),
        promptGemini: document.getElementById('promptGemini'),
        btnSavePrompts: document.getElementById('btnSavePrompts'),

        // Settings - Templates
        settingsTemplateList: document.getElementById('settingsTemplateList'),
        tmplHtml: document.getElementById('tmplHtml'),
        tmplImg: document.getElementById('tmplImg'),
        btnClearTmplForm: document.getElementById('btnClearTmplForm'),
        btnSaveTemplate: document.getElementById('btnSaveTemplate'),

        // Alert Modal
        alertModal: document.getElementById('alertModal'),
        alertTitle: document.getElementById('alertTitle'),
        alertMessage: document.getElementById('alertMessage'),
        alertActions: document.getElementById('alertActions'),
    };

    // --- UTILS: Custom Alert ---
    function showCustomAlert(title, message, buttons = []) {
        els.alertTitle.textContent = title;
        els.alertMessage.textContent = message;
        els.alertActions.innerHTML = '';

        buttons.forEach(btn => {
            const b = document.createElement('button');
            b.textContent = btn.text;
            b.className = btn.class || 'btn-primary';
            b.addEventListener('click', () => {
                els.alertModal.classList.remove('active');
                if (btn.onClick) btn.onClick();
            });
            els.alertActions.appendChild(b);
        });

        // Default close if no buttons
        if (buttons.length === 0) {
            const b = document.createElement('button');
            b.textContent = 'OK';
            b.className = 'btn-primary';
            b.addEventListener('click', () => els.alertModal.classList.remove('active'));
            els.alertActions.appendChild(b);
        }

        els.alertModal.classList.add('active');
    }



    // --- AUTH LOGIC ---
    function getToken() {
        return localStorage.getItem('accessToken');
    }

    function logout() {
        localStorage.removeItem('accessToken');
        window.location.href = '/login';
    }

    // Auth Interceptor / Wrapper
    async function authorizedFetch(url, options = {}) {
        const token = getToken();
        if (!token) {
            window.location.href = '/login';
            return;
        }

        const headers = options.headers || {};
        const authHeader = { 'Authorization': `Bearer ${token}` };

        // Handle Headers object vs plain object
        let finalHeaders;
        if (headers instanceof Headers) {
            headers.append('Authorization', `Bearer ${token}`);
            finalHeaders = headers;
        } else {
            finalHeaders = { ...headers, ...authHeader };
        }

        const finalOptions = { ...options, headers: finalHeaders };

        const response = await fetch(url, finalOptions);

        if (response.status === 401) {
            logout();
            return null;
        }

        return response;
    }

    // Verify Token on Load
    (async () => {
        const token = getToken();
        if (!token) {
            window.location.href = '/login';
            return;
        }
        try {
            const res = await authorizedFetch('/api/verify-token');
            if (!res || !res.ok) logout();
        } catch (e) { logout(); }
    })();


    // --- TEMPLATES LOGIC ---
    async function loadTemplates() {
        try {
            const res = await authorizedFetch('/api/templates');
            if (!res) return;
            const data = await res.json();
            state.templates = data;

            // UI Main view
            if (data.length > 0) {
                // Ensure index is valid
                if (state.currentTemplateIndex >= data.length) state.currentTemplateIndex = 0;
                updateTemplateView();
            } else {
                els.templateName.textContent = "No hay plantillas";
                els.templateImg.src = "";
            }

            // Settings List
            renderSettingsTemplateList();

        } catch (e) {
            console.error("Failed to load templates", e);
            els.templateName.textContent = "Error al cargar";
        }
    }

    function updateTemplateView() {
        if (state.templates.length === 0) return;
        const tmpl = state.templates[state.currentTemplateIndex];
        els.templateImg.src = tmpl.img_path;
        els.templateImg.alt = tmpl.name;
        els.templateName.textContent = tmpl.name;
    }

    els.prevTemplate.addEventListener('click', () => {
        if (state.templates.length === 0) return;
        state.currentTemplateIndex = (state.currentTemplateIndex - 1 + state.templates.length) % state.templates.length;
        updateTemplateView();
    });

    els.nextTemplate.addEventListener('click', () => {
        if (state.templates.length === 0) return;
        state.currentTemplateIndex = (state.currentTemplateIndex + 1) % state.templates.length;
        updateTemplateView();
    });

    // --- MAIN INTERACTION LOGIC ---
    function getSourceType() {
        return document.querySelector('input[name="sourceType"]:checked').value;
    }

    els.sourceRadios.forEach(radio => {
        radio.addEventListener('change', (e) => {
            if (e.target.value === 'url') {
                els.urlContainer.style.display = 'flex';
                els.textContainer.style.display = 'none';
            } else {
                els.urlContainer.style.display = 'none';
                els.textContainer.style.display = 'flex';
            }
            checkDirtyState();
        });
    });

    els.keywordInput.addEventListener('input', checkDirtyState);
    els.briefInput.addEventListener('input', checkDirtyState);
    els.urlInput.addEventListener('input', checkDirtyState);
    els.textInput.addEventListener('input', checkDirtyState);

    function getCurrentInputState() {
        return {
            keyword: els.keywordInput.value.trim(),
            brief: els.briefInput.value.trim(),
            sourceType: getSourceType(),
            url: els.urlInput.value.trim(),
            text: els.textInput.value.trim(),
        };
    }

    function checkDirtyState() {
        if (!state.lastSavedInputState) {
            // No history loaded, button enabled if valid
            els.btnGenerate.disabled = false;
            return;
        }

        const current = getCurrentInputState();
        const saved = state.lastSavedInputState;

        // Check equality
        const isSame =
            current.keyword === saved.keyword &&
            current.brief === saved.brief &&
            current.sourceType === saved.sourceType &&
            current.url === saved.url &&
            current.text === saved.text;

        if (isSame) {
            els.btnGenerate.disabled = true;
        } else {
            els.btnGenerate.disabled = false;
        }
    }

    els.btnRecet.addEventListener('click', () => {
        // Clear inputs
        els.keywordInput.value = '';
        els.briefInput.value = '';
        els.urlInput.value = '';
        els.textInput.value = '';
        state.generatedCode = null;
        els.btnView.disabled = true;

        state.lastSavedInputState = null;
        els.btnGenerate.disabled = false; // Fresh start
    });

    // --- GENERATION LOGIC ---
    els.btnGenerate.addEventListener('click', async () => {
        if (state.isGenerating || els.btnGenerate.disabled) return;

        const current = getCurrentInputState();
        const sourceContent = current.sourceType === 'url' ? current.url : current.text;

        if (!current.keyword || !sourceContent) {
            showCustomAlert('Campos Incompletos', 'Por favor rellena la palabra clave y la fuente de contenido.');
            return;
        }

        if (state.templates.length === 0) {
            showCustomAlert('Error', 'No hay plantillas disponibles.');
            return;
        }

        const templateId = state.templates[state.currentTemplateIndex].id;

        // UI State
        state.isGenerating = true;
        state.generatedCode = null;
        els.btnGenerate.disabled = true;
        els.btnView.disabled = true;

        // Open Modal Loading
        openResultModal(true);

        const payload = {
            keyword: current.keyword,
            brief: current.brief,
            source_type: current.sourceType,
            source_content: sourceContent,
            template_id: templateId
        };

        try {
            const response = await authorizedFetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response || !response.ok) throw new Error(await response?.text() || "Error");

            const data = await response.json();
            state.generatedCode = data.html_content;

            // Allow view results
            els.btnView.disabled = false;

            // Add to history (Full Snapshot)
            const historyItem = {
                id: Date.now(),
                date: new Date().toLocaleDateString('es-ES', { day: 'numeric', month: 'long', year: 'numeric' }),
                inputs: { ...current },
                result: state.generatedCode
            };
            addToHistory(historyItem);

            // Set as current saved state
            state.lastSavedInputState = { ...current };

            // Update Modal
            if (els.resultModal.classList.contains('active')) {
                els.resultCode.value = state.generatedCode;
            }

        } catch (e) {
            console.error(e);
            if (els.resultModal.classList.contains('active')) {
                els.resultCode.value = "Error: " + e.message;
            }
            showCustomAlert("Error", "Error al generar FAQ: " + e.message);
        } finally {
            state.isGenerating = false;
            // Button stays disabled as it matches lastSavedInputState 
            checkDirtyState();
        }
    });

    els.btnView.addEventListener('click', () => {
        if (state.generatedCode) {
            openResultModal(false);
        }
    });

    // --- MODAL RESULTS ---
    function openResultModal(isLoading) {
        els.resultModal.classList.add('active');
        if (isLoading) {
            els.resultCode.value = "Generando FAQs... Por favor espera. Esto puede tardar unos minutos.\n\nPuedes cerrar esta ventana, el proceso continuará en segundo plano.";
        } else {
            els.resultCode.value = state.generatedCode || "";
        }
    }

    els.btnCloseResultModal.addEventListener('click', () => {
        els.resultModal.classList.remove('active');
    });

    els.btnCopy.addEventListener('click', () => {
        if (!els.resultCode.value) return;
        navigator.clipboard.writeText(els.resultCode.value);
        const originalText = els.btnCopy.innerHTML;
        els.btnCopy.innerHTML = "¡Copiado!";
        setTimeout(() => els.btnCopy.innerHTML = originalText, 2000);
    });

    els.btnDownload.addEventListener('click', () => {
        if (!state.generatedCode) return;
        const blob = new Blob([state.generatedCode], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'faq-generated.html';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });

    // --- HISTORY LOGIC ---
    async function loadHistory() {
        try {
            const res = await authorizedFetch('/api/history');
            if (!res) return;
            const data = await res.json();
            state.history = data;
            renderHistory();
        } catch (e) { console.error("History load error", e); }
    }

    async function addToHistory(item) {
        // item has local temp ID, but we want server to save it
        // We call POST
        try {
            const res = await authorizedFetch('/api/history', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(item)
            });
            if (!res) return;
            // Reload history to get correct IDs ordering
            loadHistory();
        } catch (e) {
            showCustomAlert("Error", "Error al guardar en el historial.");
        }
    }

    // Deprecated Client-Side Save
    function saveHistory() {
        // No-op or call API update if implemented
    }

    function renderHistory() {
        els.historyList.innerHTML = '';
        state.history.forEach(item => {
            // Safety check for legacy or broken items
            if (!item || !item.inputs) return;

            const div = document.createElement('div');
            div.className = 'history-item';
            div.dataset.id = item.id;

            const displayKeyword = item.inputs.keyword || "(Sin nombre)";

            div.innerHTML = `
                <div class="history-info">
                    <div class="history-title" title="${displayKeyword}">${displayKeyword}</div>
                    <div class="history-date">${item.date}</div>
                </div>
                <button class="history-menu-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="1"></circle>
                        <circle cx="19" cy="12" r="1"></circle>
                        <circle cx="5" cy="12" r="1"></circle>
                    </svg>
                </button>
                <div class="history-dropdown">
                    <div class="dropdown-item action-edit">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                        Editar nombre
                    </div>
                    <div class="dropdown-item action-delete delete">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        Eliminar FAQ's
                    </div>
                </div>
            `;

            // Interaction: Click to Load
            div.querySelector('.history-info').addEventListener('click', () => loadHistoryItem(item));

            // Interaction: Menu
            const btnMenu = div.querySelector('.history-menu-btn');
            const dropdown = div.querySelector('.history-dropdown');

            btnMenu.addEventListener('click', (e) => {
                e.stopPropagation();
                // Close others
                document.querySelectorAll('.history-dropdown').forEach(d => {
                    if (d !== dropdown) d.classList.remove('show');
                });
                dropdown.classList.toggle('show');
                btnMenu.classList.toggle('active', dropdown.classList.contains('show'));
            });

            // Action: Edit Name
            div.querySelector('.action-edit').addEventListener('click', (e) => {
                e.stopPropagation();
                dropdown.classList.remove('show');
                startEditHistoryName(item, div.querySelector('.history-title'));
            });

            // Action: Delete
            div.querySelector('.action-delete').addEventListener('click', (e) => {
                e.stopPropagation();
                dropdown.classList.remove('show');
                confirmDeleteHistory(item.id);
            });

            els.historyList.appendChild(div);
        });
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', () => {
        document.querySelectorAll('.history-dropdown').forEach(d => d.classList.remove('show'));
        document.querySelectorAll('.history-menu-btn').forEach(b => b.classList.remove('active'));
    });

    function loadHistoryItem(item) {
        els.keywordInput.value = item.inputs.keyword;
        els.briefInput.value = item.inputs.brief;
        els.urlInput.value = item.inputs.url || '';
        els.textInput.value = item.inputs.text || '';

        // Radio logic
        const radio = document.querySelector(`input[name="sourceType"][value="${item.inputs.sourceType}"]`);
        if (radio) {
            radio.checked = true;
            radio.dispatchEvent(new Event('change')); // Trigger visibility
        }

        state.generatedCode = item.result;
        state.lastSavedInputState = { ...item.inputs };

        // Wait for UI update
        checkDirtyState();
        els.btnView.disabled = false;
    }

    function startEditHistoryName(item, titleEl) {
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'history-title-input';
        input.value = item.inputs.keyword;

        const saveEdit = async () => {
            const newVal = input.value.trim();
            if (newVal && newVal !== item.inputs.keyword) {
                // API Update
                try {
                    const res = await authorizedFetch(`/api/history/${item.id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ keyword: newVal })
                    });
                    if (res && res.ok) loadHistory();
                } catch (e) { alert("Error al actualizar"); }
            }
            renderHistory(); // Revert to text if failure or done
        };

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') saveEdit();
        });
        input.addEventListener('blur', saveEdit);

        setTimeout(() => {
            titleEl.replaceWith(input);
            input.focus();
        }, 50);
    }

    function confirmDeleteHistory(id) {
        showCustomAlert(
            'Eliminar Historial',
            '¿Estás seguro que quieres eliminar este item del historial?',
            [
                { text: 'Cancelar', class: 'btn-cancel', onClick: () => { } },
                {
                    text: 'Eliminar', class: 'btn-primary btn-danger', onClick: async () => {
                        try {
                            const res = await authorizedFetch(`/api/history/${id}`, { method: 'DELETE' });
                            if (res) loadHistory();
                        } catch (e) { alert("Error al eliminar"); }
                    }
                }
            ]
        );
    }

    // --- SETTINGS LOGIC ---
    els.btnSettings.addEventListener('click', async () => {
        els.settingsModal.classList.add('active');

        // Load Prompts
        try {
            const res = await authorizedFetch('/api/prompts');
            if (!res) return;
            const data = await res.json();
            els.promptClaude.value = data.system_prompt_claude;
            els.promptGemini.value = data.system_prompt_gemini;
        } catch (e) {
            console.error("Failed to fetch prompts");
        }
    });

    els.btnCloseSettings.addEventListener('click', () => {
        els.settingsModal.classList.remove('active');
    });

    // Tabs logic
    els.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            els.tabBtns.forEach(b => b.classList.remove('active'));
            els.tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
        });
    });

    // Save Prompts
    els.btnSavePrompts.addEventListener('click', async () => {
        const data = {
            system_prompt_claude: els.promptClaude.value,
            system_prompt_gemini: els.promptGemini.value
        };
        try {
            const res = await authorizedFetch('/api/prompts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            if (!res) return;
            showCustomAlert("Éxito", "Prompts guardados correctamente.");
        } catch (e) {
            showCustomAlert("Error", "Error al guardar prompts.");
        }
    });

    // Templates CRUD
    function renderSettingsTemplateList() {
        els.settingsTemplateList.innerHTML = '';
        state.templates.forEach(t => {
            const div = document.createElement('div');
            div.className = 'template-item';
            div.innerHTML = `
                <img src="${t.img_path}" alt="preview">
                <div class="template-item-info">
                    <div>${t.name}</div>
                    <small>${t.id}</small>
                </div>
                <div class="template-item-actions">
                    <button class="btn-icon btn-danger" onclick="window.deleteTemplate('${t.id}')">
                         <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                </div>
            `;
            els.settingsTemplateList.appendChild(div);
        });
    }

    // Expose delete function to window scope for onclick usage in innerHTML
    window.deleteTemplate = async (id) => {
        showCustomAlert(
            'Eliminar Plantilla',
            '¿Seguro que deseas eliminar esta plantilla?',
            [
                { text: 'Cancelar', class: 'btn-cancel' },
                {
                    text: 'Eliminar', class: 'btn-primary btn-danger', onClick: async () => {
                        try {
                            const res = await authorizedFetch(`/api/templates/${id}`, { method: 'DELETE' });
                            if (!res) return;
                            loadTemplates(); // Reloads all lists
                        } catch (e) {
                            alert("Error al eliminar");
                        }
                    }
                }
            ]
        );
    };

    els.btnSaveTemplate.addEventListener('click', async () => {
        const html = els.tmplHtml.value;
        const file = els.tmplImg.files[0];

        if (!html || !file) {
            showCustomAlert("Error", "Debes ingresar HTML y una imagen.");
            return;
        }

        const formData = new FormData();
        formData.append("html_content", html);
        formData.append("image", file);

        try {
            const res = await authorizedFetch('/api/templates', {
                method: 'POST',
                body: formData
            });
            if (!res || !res.ok) throw new Error();

            showCustomAlert("Éxito", "Plantilla creada.");
            els.tmplHtml.value = '';
            els.tmplImg.value = '';
            loadTemplates();
        } catch (e) {
            showCustomAlert("Error", "Error al guardar la plantilla.");
        }
    });

    els.btnClearTmplForm.addEventListener('click', () => {
        els.tmplHtml.value = '';
        els.tmplImg.value = '';
    });

    // Init Logic
    loadTemplates();
    loadHistory();
});
