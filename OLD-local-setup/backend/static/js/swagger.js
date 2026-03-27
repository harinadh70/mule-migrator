// ═══════════════════════════════════════════════════════════════
// Swagger / OpenAPI Generator Page
// ═══════════════════════════════════════════════════════════════

var swaggerState = {
    activeTab: 'xml',
    generatedSpec: null,   // raw YAML string from server
    specObject: null       // parsed spec data from server response
};

var specEditor = null;     // CodeMirror instance for output

// ── Tab Switching ──────────────────────────────────────────────
function switchSwaggerTab(btn) {
    var tabId = btn.dataset.tab;
    swaggerState.activeTab = tabId;

    document.querySelectorAll('.input-panel .tab').forEach(function (t) {
        t.classList.remove('active');
    });
    document.querySelectorAll('.input-panel .tab-content').forEach(function (c) {
        c.classList.remove('active');
    });

    btn.classList.add('active');
    var panel = document.getElementById('tab-' + tabId);
    if (panel) panel.classList.add('active');
}

// ── Generate from XML ──────────────────────────────────────────
function generateFromXml() {
    var xmlContent = (document.getElementById('xmlEditor') || {}).value || '';
    if (!xmlContent.trim()) {
        showToast('Please paste MuleSoft XML content first', 'warning');
        return;
    }

    var projectName = (document.getElementById('xmlProjectName') || {}).value || 'my-api';

    setGeneratingState(true);
    setStatus('Generating OpenAPI spec from XML...');

    apiCall('/api/swagger/from-xml', {
        method: 'POST',
        body: { xmlContent: xmlContent, projectName: projectName }
    }).then(function (data) {
        setGeneratingState(false);
        if (data && data.success && data.spec) {
            displaySpec(data.spec);
            showToast('OpenAPI specification generated from XML', 'success', 3000);
            setStatus('Spec generated — ready to download');
        } else {
            showToast(data && data.error ? escapeHtml(data.error) : 'Unexpected response from server', 'error');
            setStatus('Generation failed');
        }
    }).catch(function (err) {
        setGeneratingState(false);
        showToast('Generation failed: ' + escapeHtml(err.message || String(err)), 'error');
        setStatus('Generation failed');
    });
}

// ── Generate from RAML ─────────────────────────────────────────
function generateFromRaml() {
    var ramlContent = (document.getElementById('ramlEditor') || {}).value || '';
    if (!ramlContent.trim()) {
        showToast('Please paste a RAML definition first', 'warning');
        return;
    }

    setGeneratingState(true);
    setStatus('Generating OpenAPI spec from RAML...');

    apiCall('/api/swagger/from-raml', {
        method: 'POST',
        body: { ramlContent: ramlContent }
    }).then(function (data) {
        setGeneratingState(false);
        if (data && data.success && data.spec) {
            displaySpec(data.spec);
            showToast('OpenAPI specification generated from RAML', 'success', 3000);
            setStatus('Spec generated — ready to download');
        } else {
            showToast(data && data.error ? escapeHtml(data.error) : 'Unexpected response from server', 'error');
            setStatus('Generation failed');
        }
    }).catch(function (err) {
        setGeneratingState(false);
        showToast('Generation failed: ' + escapeHtml(err.message || String(err)), 'error');
        setStatus('Generation failed');
    });
}

// ── Load from Migration Store ──────────────────────────────────
function loadFromMigration() {
    var migrationData = null;
    if (typeof MigrationStore !== 'undefined' && MigrationStore.hasMigration()) {
        migrationData = MigrationStore.load();
    }

    if (!migrationData) {
        showToast('No migration data found — run a migration first', 'warning');
        return;
    }

    var parsedData = migrationData.parsed || migrationData;
    var projectName = migrationData.projectName || 'migrated-app';

    setGeneratingState(true);
    setStatus('Generating OpenAPI spec from migration data...');

    apiCall('/api/swagger/from-migration', {
        method: 'POST',
        body: { parsedData: parsedData, projectName: projectName }
    }).then(function (data) {
        setGeneratingState(false);
        if (data && data.success && data.spec) {
            displaySpec(data.spec);
            showToast('OpenAPI specification generated from migration result', 'success', 3000);
            setStatus('Spec generated — ready to download');
        } else {
            showToast(data && data.error ? escapeHtml(data.error) : 'Unexpected response from server', 'error');
            setStatus('Generation failed');
        }
    }).catch(function (err) {
        setGeneratingState(false);
        showToast('Failed to generate from migration: ' + escapeHtml(err.message || String(err)), 'error');
        setStatus('Generation failed');
    });
}

// ── Display Spec ───────────────────────────────────────────────
function displaySpec(spec) {
    // spec can be a string (YAML) or an object; normalise to YAML string
    var yamlStr = '';
    if (typeof spec === 'string') {
        yamlStr = spec;
    } else if (typeof spec === 'object') {
        // Convert object to a YAML-like JSON fallback (server should return YAML string)
        yamlStr = JSON.stringify(spec, null, 2);
    }

    swaggerState.generatedSpec = yamlStr;
    swaggerState.specObject = spec;

    // Show the CodeMirror editor, hide the empty state
    var emptyState = document.getElementById('specEmptyState');
    var editorContainer = document.getElementById('specEditor');

    if (emptyState) emptyState.style.display = 'none';
    if (editorContainer) editorContainer.style.display = 'flex';

    if (!specEditor) {
        initSpecEditor();
    }

    if (specEditor) {
        specEditor.setValue(yamlStr);
        specEditor.scrollTo(0, 0);
        specEditor.refresh();
    }

    enableOutputButtons(true);
}

// ── Download Spec ──────────────────────────────────────────────
function downloadSpec(format) {
    if (!swaggerState.generatedSpec) {
        showToast('Generate a specification first', 'warning');
        return;
    }

    setStatus('Preparing download...');

    apiCall('/api/swagger/download', {
        method: 'POST',
        body: {
            spec: swaggerState.generatedSpec,
            format: format
        },
        responseType: 'blob'
    }).then(function (blob) {
        var ext = format === 'json' ? 'json' : 'yaml';
        var mimeType = format === 'json' ? 'application/json' : 'text/yaml';
        var filename = 'openapi.' + ext;

        // If apiCall returns parsed JSON instead of a blob, handle both cases
        if (blob instanceof Blob) {
            triggerBlobDownload(blob, filename);
        } else if (blob && blob.content) {
            triggerTextDownload(blob.content, filename, mimeType);
        } else if (typeof blob === 'string') {
            triggerTextDownload(blob, filename, mimeType);
        } else {
            // Fallback: download the local spec directly
            var content = format === 'json'
                ? JSON.stringify(swaggerState.specObject || swaggerState.generatedSpec, null, 2)
                : swaggerState.generatedSpec;
            triggerTextDownload(content, filename, mimeType);
        }

        showToast('Downloaded ' + filename, 'success', 2500);
        setStatus('Ready');
    }).catch(function (err) {
        // Fallback: download locally without server round-trip
        var ext = format === 'json' ? 'json' : 'yaml';
        var mimeType = format === 'json' ? 'application/json' : 'text/yaml';
        var filename = 'openapi.' + ext;
        var content = format === 'json'
            ? JSON.stringify(swaggerState.specObject || swaggerState.generatedSpec, null, 2)
            : swaggerState.generatedSpec;
        triggerTextDownload(content, filename, mimeType);
        showToast('Downloaded ' + filename, 'success', 2500);
        setStatus('Ready');
    });
}

function triggerTextDownload(content, filename, mimeType) {
    var blob = new Blob([content], { type: mimeType });
    triggerBlobDownload(blob, filename);
}

function triggerBlobDownload(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, 100);
}

// ── Copy Spec to Clipboard ─────────────────────────────────────
function copySpec() {
    if (!swaggerState.generatedSpec) {
        showToast('Nothing to copy — generate a spec first', 'warning');
        return;
    }
    copyToClipboard(swaggerState.generatedSpec, 'OpenAPI YAML');
}

// ── CodeMirror Initialisation ──────────────────────────────────
function initSpecEditor() {
    var container = document.getElementById('specEditor');
    if (!container || specEditor) return;

    specEditor = CodeMirror(container, {
        mode: 'yaml',
        theme: 'dracula',
        lineNumbers: true,
        readOnly: true,
        lineWrapping: false,
        tabSize: 2,
        indentWithTabs: false,
        extraKeys: { 'Ctrl-F': 'findPersistent' }
    });
}

// ── Generating State Indicator ─────────────────────────────────
function setGeneratingState(isGenerating) {
    var wrapper = document.getElementById('specOutputWrapper');
    var emptyState = document.getElementById('specEmptyState');
    var editorContainer = document.getElementById('specEditor');

    if (isGenerating) {
        if (editorContainer) editorContainer.style.display = 'none';
        if (emptyState) emptyState.style.display = 'none';

        var existing = wrapper && wrapper.querySelector('.generating-indicator');
        if (!existing && wrapper) {
            var ind = document.createElement('div');
            ind.className = 'generating-indicator';
            ind.innerHTML = '<div class="mini-spinner"></div><span>Generating specification&hellip;</span>';
            wrapper.appendChild(ind);
        }
        enableOutputButtons(false);
    } else {
        if (wrapper) {
            var ind = wrapper.querySelector('.generating-indicator');
            if (ind) wrapper.removeChild(ind);
        }
    }
}

// ── Enable / Disable Output Buttons ────────────────────────────
function enableOutputButtons(enabled) {
    var ids = [
        'copySpecBtn', 'downloadYamlBtn', 'downloadJsonBtn',
        'copyHeaderBtn', 'downloadYamlHeaderBtn', 'downloadJsonHeaderBtn'
    ];
    ids.forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.disabled = !enabled;
    });
}

// ── Resizable Panel Divider ────────────────────────────────────
function initPanelDivider() {
    var divider     = document.getElementById('swaggerPanelDivider');
    var inputPanel  = document.querySelector('.swagger-layout .input-panel');
    var outputPanel = document.querySelector('.swagger-layout .output-panel');
    if (!divider || !inputPanel || !outputPanel) return;

    var dragging = false;
    var startX   = 0;
    var startInputWidth = 0;

    divider.addEventListener('mousedown', function (e) {
        dragging = true;
        startX = e.clientX;
        startInputWidth = inputPanel.getBoundingClientRect().width;
        divider.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', function (e) {
        if (!dragging) return;
        var dx = e.clientX - startX;
        var totalWidth = inputPanel.parentElement.getBoundingClientRect().width;
        var newInputWidth = Math.max(280, Math.min(startInputWidth + dx, totalWidth - 340));
        var newOutputWidth = totalWidth - newInputWidth - divider.offsetWidth;
        inputPanel.style.flex  = 'none';
        inputPanel.style.width = newInputWidth + 'px';
        outputPanel.style.flex = 'none';
        outputPanel.style.width = newOutputWidth + 'px';
    });

    document.addEventListener('mouseup', function () {
        if (!dragging) return;
        dragging = false;
        divider.classList.remove('dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        if (specEditor) specEditor.refresh();
    });
}

// ── Check if migration data exists on load ─────────────────────
function checkMigrationData() {
    var hasData = typeof MigrationStore !== 'undefined' && MigrationStore.hasMigration();
    var hasSavedSpec = !!localStorage.getItem('msb_swagger_spec');
    var emptyEl = document.getElementById('migrationEmptyState');
    var availEl = document.getElementById('migrationAvailable');

    if (hasData) {
        if (emptyEl) emptyEl.style.display = 'none';
        if (availEl) {
            availEl.style.display = 'flex';
            // Show additional info about what is available
            var infoEl = availEl.querySelector('.migration-info');
            if (!infoEl) {
                infoEl = document.createElement('span');
                infoEl.className = 'migration-info';
                infoEl.style.cssText = 'font-size:0.85em;color:#8be9fd;margin-left:8px;';
                availEl.appendChild(infoEl);
            }
            var migrationData = MigrationStore.load();
            var flowCount = 0;
            if (migrationData) {
                var parsed = migrationData.parsed || migrationData.summary || {};
                var flows = parsed.flows || [];
                flowCount = flows.length;
            }
            infoEl.textContent = flowCount > 0
                ? '(' + flowCount + ' flows available' + (hasSavedSpec ? ', spec cached' : '') + ')'
                : (hasSavedSpec ? '(spec cached from last run)' : '');
        }
    } else {
        if (emptyEl) emptyEl.style.display = '';
        if (availEl) availEl.style.display = 'none';
    }
}

// ── Initialisation ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initPanelDivider();
    checkMigrationData();

    // Defer CodeMirror init so the DOM is fully painted
    setTimeout(function () {
        initSpecEditor();
    }, 50);

    // Check if a swagger spec was auto-generated from migration
    var savedSpec = localStorage.getItem('msb_swagger_spec');
    if (savedSpec) {
        try {
            var spec = JSON.parse(savedSpec);
            // Wait for CodeMirror to initialise before displaying
            setTimeout(function () {
                displaySpec(spec);
                showToast('OpenAPI spec loaded from last migration', 'info', 3000);
            }, 100);
        } catch(e) {}
    }

    setStatus('Ready');
});
