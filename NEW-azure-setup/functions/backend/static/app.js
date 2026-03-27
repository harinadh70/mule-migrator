// ============================================================
// MuleSoft to Spring Boot Migrator - Enhanced Interactive UI
// With Multi-XML, LLM Validation, and Multi-Provider Support
// ============================================================

let migrationResult = null;
let dwScripts = {};
let activeDwScript = null;
let llmProviders = {};
let uploadedXmlFiles = [];  // {name, content} pairs
let currentFilePath = null; // tracks which file is displayed

// ==================== Toast Notification System ====================

function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;

    var container = document.getElementById('toastContainer');
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;

    var icons = { success: '&#10004;', error: '&#10060;', warning: '&#9888;', info: '&#8505;' };

    toast.innerHTML =
        '<span class="toast-icon">' + (icons[type] || icons.info) + '</span>' +
        '<span class="toast-body">' + message + '</span>' +
        '<button class="toast-close" onclick="dismissToast(this.parentElement)">&times;</button>' +
        '<div class="toast-progress"></div>';

    container.appendChild(toast);

    // Slide in after a frame
    requestAnimationFrame(function() {
        requestAnimationFrame(function() {
            toast.classList.add('show');
        });
    });

    // Animate progress bar
    var progress = toast.querySelector('.toast-progress');
    progress.style.width = '100%';
    requestAnimationFrame(function() {
        progress.style.transitionDuration = duration + 'ms';
        progress.style.width = '0%';
    });

    // Auto-dismiss
    var timer = setTimeout(function() { dismissToast(toast); }, duration);
    toast._timer = timer;

    // Pause on hover
    toast.addEventListener('mouseenter', function() {
        clearTimeout(toast._timer);
        var prog = toast.querySelector('.toast-progress');
        prog.style.transitionDuration = '0ms';
    });
    toast.addEventListener('mouseleave', function() {
        toast._timer = setTimeout(function() { dismissToast(toast); }, 2000);
        var prog = toast.querySelector('.toast-progress');
        prog.style.transitionDuration = '2000ms';
        prog.style.width = '0%';
    });

    return toast;
}

function dismissToast(toast) {
    if (!toast || !toast.parentElement) return;
    toast.classList.remove('show');
    toast.classList.add('hiding');
    setTimeout(function() {
        if (toast.parentElement) toast.parentElement.removeChild(toast);
    }, 350);
}

// ==================== Tab Switching ====================

function switchInputTab(btn) {
    var tabId = btn.dataset.tab;
    document.querySelectorAll('.input-panel .tab').forEach(function(t) { t.classList.remove('active'); });
    document.querySelectorAll('.input-panel .tab-content').forEach(function(c) { c.classList.remove('active'); });
    btn.classList.add('active');
    document.getElementById('tab-' + tabId).classList.add('active');
}

function switchOutputTab(btn) {
    var tabId = btn.dataset.tab;
    document.querySelectorAll('.output-panel .tab').forEach(function(t) { t.classList.remove('active'); });
    document.querySelectorAll('.output-panel .tab-content').forEach(function(c) { c.classList.remove('active'); });
    btn.classList.add('active');
    document.getElementById('tab-' + tabId).classList.add('active');
}

// ==================== Multi-File Upload ====================

function handleFileUpload(event) {
    var files = event.target.files;
    if (!files || files.length === 0) return;

    var count = 0;
    for (var i = 0; i < files.length; i++) {
        (function(file) {
            var reader = new FileReader();
            reader.onload = function(e) {
                uploadedXmlFiles.push({ name: file.name, content: e.target.result });
                count++;
                renderUploadedFiles();
                document.getElementById('muleXmlEditor').value = e.target.result;
                updateEditorInfo();
                if (count === files.length) {
                    showToast('Loaded ' + files.length + ' file(s) successfully', 'success');
                }
                setStatus('Loaded ' + uploadedXmlFiles.length + ' file(s)');
            };
            reader.readAsText(file);
        })(files[i]);
    }
}

function handleDrop(event) {
    event.preventDefault();
    event.currentTarget.classList.remove('dragover');
    var files = event.dataTransfer.files;
    if (files.length > 0) {
        handleFileUpload({ target: { files: files } });
    }
}

function renderUploadedFiles() {
    var list = document.getElementById('uploadedFilesList');
    if (uploadedXmlFiles.length === 0) {
        list.innerHTML = '';
        return;
    }
    var html = '<div class="uploaded-files-header">Uploaded Files (' + uploadedXmlFiles.length + ')</div>';
    for (var i = 0; i < uploadedXmlFiles.length; i++) {
        html += '<div class="uploaded-file-chip" onclick="previewUploadedFile(' + i + ')">' +
            '<span class="uploaded-file-icon">&lt;/&gt;</span>' +
            '<span class="uploaded-file-name">' + escapeHtml(uploadedXmlFiles[i].name) + '</span>' +
            '<span class="uploaded-file-remove" onclick="removeUploadedFile(' + i + ', event)">&times;</span>' +
            '</div>';
    }
    list.innerHTML = html;
}

function previewUploadedFile(index) {
    if (uploadedXmlFiles[index]) {
        document.getElementById('muleXmlEditor').value = uploadedXmlFiles[index].content;
        updateEditorInfo();
        setStatus('Viewing: ' + uploadedXmlFiles[index].name);
    }
}

function removeUploadedFile(index, event) {
    event.stopPropagation();
    var name = uploadedXmlFiles[index].name;
    uploadedXmlFiles.splice(index, 1);
    renderUploadedFiles();
    showToast('Removed ' + name, 'info', 2000);
    setStatus(uploadedXmlFiles.length + ' file(s) remaining');
}

// ==================== Editor Info Badge ====================

function updateEditorInfo() {
    var editor = document.getElementById('muleXmlEditor');
    var text = editor.value;
    var lines = text ? text.split('\n').length : 0;
    var chars = text.length;
    var badge = document.getElementById('editorInfoBadge');
    if (!badge) {
        badge = document.createElement('div');
        badge.id = 'editorInfoBadge';
        badge.className = 'editor-info';
        editor.parentElement.appendChild(badge);
    }
    badge.textContent = lines + ' lines | ' + chars + ' chars';
}

// ==================== DataWeave Scripts ====================

function addDwScript() {
    var nameInput = document.getElementById('dwScriptName');
    var name = nameInput.value.trim();
    if (!name) {
        showToast('Enter a script name first', 'warning');
        return;
    }
    if (!dwScripts[name]) dwScripts[name] = '';
    nameInput.value = '';
    renderDwScripts();
    selectDwScript(name);
    showToast('Added script: ' + name, 'success', 2000);
}

function selectDwScript(name) {
    if (activeDwScript) {
        dwScripts[activeDwScript] = document.getElementById('dwEditor').value;
    }
    activeDwScript = name;
    document.getElementById('dwEditor').value = dwScripts[name] || '';
    renderDwScripts();
}

function removeDwScript(name, event) {
    event.stopPropagation();
    delete dwScripts[name];
    if (activeDwScript === name) {
        activeDwScript = null;
        document.getElementById('dwEditor').value = '';
    }
    renderDwScripts();
    showToast('Removed script: ' + name, 'info', 2000);
}

function renderDwScripts() {
    var list = document.getElementById('dwScriptList');
    list.innerHTML = '';
    for (var name in dwScripts) {
        if (!dwScripts.hasOwnProperty(name)) continue;
        var chip = document.createElement('div');
        chip.className = 'dw-chip' + (name === activeDwScript ? ' active' : '');
        (function(n) {
            chip.onclick = function() { selectDwScript(n); };
        })(name);
        chip.innerHTML = name + ' <span class="remove" onclick="removeDwScript(\'' + name + '\', event)">&times;</span>';
        list.appendChild(chip);
    }
}

// ==================== DataWeave Playground ====================

async function convertDataWeave() {
    var script = document.getElementById('dwEditor').value.trim();
    if (!script) {
        showToast('Enter a DataWeave script first', 'warning');
        return;
    }
    try {
        var res = await fetch('/api/convert/dataweave', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script: script }),
        });
        var data = await res.json();
        if (data.error) {
            showToast('Error: ' + data.error, 'error');
            return;
        }
        var content = document.getElementById('fileContent');
        var java = data.result.java_code || '';
        var imports = (data.result.imports || []).join('\n');
        var warnings = (data.result.warnings || []).join('\n');
        content.innerHTML =
            '<button class="copy-btn" onclick="copyFileContent()">Copy</button>' +
            '<pre><code>// === DataWeave to Java Conversion ===\n\n' +
            (imports ? '// Imports needed:\n' + escapeHtml(imports) + '\n\n' : '') +
            escapeHtml(java) +
            (warnings ? '\n\n// Warnings:\n' + escapeHtml(warnings) : '') +
            '</code></pre>';
        showToast('DataWeave converted to Java', 'success');
        setStatus('DataWeave converted successfully');
    } catch (err) {
        showToast('Conversion failed: ' + err.message, 'error');
    }
}

// ==================== LLM Settings ====================

async function loadLLMProviders() {
    try {
        var res = await fetch('/api/llm/providers');
        llmProviders = await res.json();
        populateProviderSelect();
        restoreLLMSettings();
    } catch (err) {
        console.error('Failed to load LLM providers:', err);
    }
}

function populateProviderSelect() {
    var select = document.getElementById('llmProvider');
    select.innerHTML = '<option value="">Select a provider...</option>';
    for (var key in llmProviders) {
        if (!llmProviders.hasOwnProperty(key)) continue;
        var opt = document.createElement('option');
        opt.value = key;
        opt.textContent = llmProviders[key].name;
        select.appendChild(opt);
    }
}

function onProviderChange() {
    var provider = document.getElementById('llmProvider').value;
    var modelSelect = document.getElementById('llmModel');
    var apiKeyGroup = document.getElementById('llmApiKeyGroup');
    var baseUrlGroup = document.getElementById('llmBaseUrlGroup');
    var docsLink = document.getElementById('llmDocsLink');
    var providerInfo = document.getElementById('llmProviderInfo');

    modelSelect.innerHTML = '<option value="">Select a model...</option>';

    if (!provider || !llmProviders[provider]) {
        apiKeyGroup.style.display = '';
        baseUrlGroup.style.display = 'none';
        docsLink.innerHTML = '';
        providerInfo.innerHTML = '';
        return;
    }

    var p = llmProviders[provider];

    for (var i = 0; i < p.models.length; i++) {
        var opt = document.createElement('option');
        opt.value = p.models[i].id;
        opt.textContent = p.models[i].name + ' (' + p.models[i].tier + ')';
        modelSelect.appendChild(opt);
    }
    if (p.models.length > 0) {
        modelSelect.value = p.models[0].id;
    }

    if (provider === 'ollama') {
        apiKeyGroup.style.display = 'none';
        baseUrlGroup.style.display = '';
        document.getElementById('llmBaseUrl').placeholder = p.base_url || 'http://localhost:11434';
    } else {
        apiKeyGroup.style.display = '';
        baseUrlGroup.style.display = 'none';
        docsLink.innerHTML = 'Get your API key at <a href="' + p.docs_url + '" target="_blank" style="color:var(--primary)">' + p.docs_url + '</a>';
    }

    var tierBadges = p.models.map(function(m) {
        var colors = { free: '#22c55e', standard: '#3b82f6', premium: '#f59e0b' };
        return '<span class="tier-badge" style="background:' + (colors[m.tier] || '#64748b') + '">' + m.tier + '</span>';
    });
    providerInfo.innerHTML =
        '<div class="provider-card">' +
            '<strong>' + p.name + '</strong>' +
            '<div class="provider-tiers">' + ([...new Set(tierBadges)].join(' ')) + '</div>' +
            '<div class="provider-models">' + p.models.length + ' models available</div>' +
        '</div>';

    saveLLMSettings();
}

function toggleLLM() {
    var checkbox = document.getElementById('llmEnabled');
    checkbox.checked = !checkbox.checked;
    var panel = document.getElementById('llmSettingsPanel');
    panel.classList.toggle('disabled', !checkbox.checked);
    showToast(checkbox.checked ? 'LLM Code Review enabled' : 'LLM Code Review disabled', 'info', 2000);
    saveLLMSettings();
}

function toggleApiKeyVisibility() {
    var input = document.getElementById('llmApiKey');
    input.type = input.type === 'password' ? 'text' : 'password';
}

function getLLMConfig() {
    var enabled = document.getElementById('llmEnabled').checked;
    if (!enabled) return { enabled: false };
    return {
        enabled: true,
        provider: document.getElementById('llmProvider').value,
        model: document.getElementById('llmModel').value,
        apiKey: document.getElementById('llmApiKey').value,
        baseUrl: document.getElementById('llmBaseUrl').value,
    };
}

function saveLLMSettings() {
    var config = getLLMConfig();
    localStorage.setItem('llm_enabled', config.enabled ? '1' : '0');
    localStorage.setItem('llm_provider', config.provider || '');
    localStorage.setItem('llm_model', config.model || '');
    localStorage.setItem('llm_base_url', config.baseUrl || '');
}

function restoreLLMSettings() {
    var enabled = localStorage.getItem('llm_enabled') === '1';
    var provider = localStorage.getItem('llm_provider') || '';
    var model = localStorage.getItem('llm_model') || '';
    var baseUrl = localStorage.getItem('llm_base_url') || '';

    document.getElementById('llmEnabled').checked = enabled;
    document.getElementById('llmSettingsPanel').classList.toggle('disabled', !enabled);

    if (provider) {
        document.getElementById('llmProvider').value = provider;
        onProviderChange();
        if (model) {
            document.getElementById('llmModel').value = model;
        }
    }
    if (baseUrl) {
        document.getElementById('llmBaseUrl').value = baseUrl;
    }
}

async function testLLMConnection() {
    var config = getLLMConfig();
    if (!config.enabled || !config.provider) {
        showToast('Enable LLM and select a provider first', 'warning');
        return;
    }

    var btn = document.getElementById('testLlmBtn');
    btn.disabled = true;
    btn.textContent = 'Testing...';
    document.getElementById('llmTestResult').textContent = '';

    try {
        var res = await fetch('/api/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: { 'Test.java': 'public class Test { public static void main(String[] args) {} }' },
                summary: { flowsConverted: 1 },
                llmConfig: config,
            }),
        });
        var data = await res.json();
        if (data.error) {
            document.getElementById('llmTestResult').textContent = 'Failed: ' + data.error;
            document.getElementById('llmTestResult').className = 'llm-test-result error';
            showToast('Connection failed: ' + data.error, 'error');
        } else if (data.validation && data.validation.overallScore > 0) {
            document.getElementById('llmTestResult').textContent = 'Connected! Score: ' + data.validation.overallScore + '/10';
            document.getElementById('llmTestResult').className = 'llm-test-result success';
            showToast('LLM connection successful!', 'success');
        } else if (data.validation && data.validation.issues && data.validation.issues.length > 0) {
            var msg = data.validation.issues[0].message || 'Unknown error';
            document.getElementById('llmTestResult').textContent = 'Issue: ' + msg;
            document.getElementById('llmTestResult').className = 'llm-test-result error';
        } else {
            document.getElementById('llmTestResult').textContent = 'Connected (no score returned)';
            document.getElementById('llmTestResult').className = 'llm-test-result success';
            showToast('LLM connection established', 'success');
        }
    } catch (err) {
        document.getElementById('llmTestResult').textContent = 'Error: ' + err.message;
        document.getElementById('llmTestResult').className = 'llm-test-result error';
        showToast('Connection error: ' + err.message, 'error');
    }

    btn.disabled = false;
    btn.textContent = 'Test Connection';
}

// ==================== Migration Progress Stepper ====================

var stepTimers = [];

function startProgressStepper(withLLM) {
    var stepper = document.getElementById('progressStepper');
    stepper.classList.add('active');

    var steps = stepper.querySelectorAll('.step-row');
    steps.forEach(function(s) {
        s.className = 'step-row pending';
    });

    // Hide the review step if LLM is off
    var reviewStep = stepper.querySelector('[data-step="review"]');
    reviewStep.style.display = withLLM ? '' : 'none';

    // Simulate step progression
    var stepNames = ['parse', 'connectors', 'dataweave', 'generate'];
    if (withLLM) stepNames.push('review');

    stepTimers = [];
    var delay = 0;
    for (var i = 0; i < stepNames.length; i++) {
        (function(idx, name) {
            var t = setTimeout(function() {
                advanceStep(name);
            }, delay);
            stepTimers.push(t);
        })(i, stepNames[i]);
        delay += 800 + Math.random() * 600;
    }
}

function advanceStep(stepName) {
    var stepper = document.getElementById('progressStepper');
    // Mark previous active as completed
    var prev = stepper.querySelector('.step-row.active-step');
    if (prev) {
        prev.className = 'step-row completed';
        prev.querySelector('.step-icon').innerHTML = '&#10003;';
    }
    // Mark current as active
    var current = stepper.querySelector('[data-step="' + stepName + '"]');
    if (current) {
        current.className = 'step-row active-step';
    }
}

function completeAllSteps() {
    stepTimers.forEach(function(t) { clearTimeout(t); });
    stepTimers = [];

    var stepper = document.getElementById('progressStepper');
    stepper.querySelectorAll('.step-row').forEach(function(s) {
        if (s.style.display !== 'none') {
            s.className = 'step-row completed';
            s.querySelector('.step-icon').innerHTML = '&#10003;';
        }
    });
    var doneStep = stepper.querySelector('[data-step="done"]');
    doneStep.className = 'step-row completed';
    doneStep.querySelector('.step-icon').innerHTML = '&#10003;';
}

function resetStepper() {
    var stepper = document.getElementById('progressStepper');
    stepper.classList.remove('active');
    stepper.querySelectorAll('.step-row').forEach(function(s) {
        s.className = 'step-row pending';
    });
}

// ==================== Migration ====================

async function migrate() {
    var xmlFiles = [];

    if (uploadedXmlFiles.length > 0) {
        xmlFiles = uploadedXmlFiles.map(function(f) { return { name: f.name, content: f.content }; });
    }

    var editorContent = document.getElementById('muleXmlEditor').value.trim();
    if (editorContent && uploadedXmlFiles.length === 0) {
        xmlFiles.push({ name: 'main.xml', content: editorContent });
    }

    if (xmlFiles.length === 0) {
        showToast('Please provide MuleSoft XML configuration', 'warning');
        return;
    }

    if (activeDwScript) {
        dwScripts[activeDwScript] = document.getElementById('dwEditor').value;
    }

    var projectName = document.getElementById('projectName').value || 'migrated-app';
    var groupId = document.getElementById('groupId').value || 'com.example';
    var javaVersion = document.getElementById('javaVersion').value || '17';
    var llmConfig = getLLMConfig();

    var loadingMsg = llmConfig.enabled
        ? 'Migrating MuleSoft to Spring Boot + LLM Code Review...'
        : 'Migrating MuleSoft to Spring Boot...';
    showLoading(true, loadingMsg);
    startProgressStepper(llmConfig.enabled);
    setStatus('Migrating...');

    try {
        var response = await fetch('/api/migrate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                muleXmlFiles: xmlFiles,
                dataweaveScripts: dwScripts,
                projectName: projectName,
                groupId: groupId,
                javaVersion: javaVersion,
                llmConfig: llmConfig,
            }),
        });

        var data = await response.json();
        if (data.error) {
            showToast('Migration error: ' + data.error, 'error', 6000);
            setStatus('Error: ' + data.error);
            showLoading(false);
            resetStepper();
            return;
        }

        completeAllSteps();

        migrationResult = data;
        renderFileTree(data.files);
        renderSummary(data.summary);
        document.getElementById('downloadBtn').disabled = false;

        if (data.llmValidation) {
            renderValidationResults(data.llmValidation);
            document.getElementById('validationTabBtn').style.display = '';
            document.getElementById('revalidateBtn').style.display = '';
        }

        var fileCount = Object.keys(data.files).length;
        var xmlCount = data.summary.xmlFilesProcessed || xmlFiles.length;
        var statusMsg = 'Migration complete \u2014 ' + fileCount + ' files generated from ' + xmlCount + ' XML file(s)';
        if (data.llmValidation) {
            statusMsg += ' | Review Score: ' + data.llmValidation.overallScore + '/10';
        }
        setStatus(statusMsg);
        document.querySelector('.output-panel .tab[data-tab="output-files"]').click();

        showToast('Migration successful! ' + fileCount + ' files generated', 'success', 5000);
        triggerConfetti();

    } catch (err) {
        showToast('Migration failed: ' + err.message, 'error', 6000);
        setStatus('Error: ' + err.message);
        resetStepper();
    }
    setTimeout(function() {
        showLoading(false);
        resetStepper();
    }, 800);
}

// ==================== Re-validate with LLM ====================

async function revalidateWithLLM() {
    if (!migrationResult) return;
    var llmConfig = getLLMConfig();
    if (!llmConfig.enabled || !llmConfig.provider) {
        showToast('Enable LLM Validation and select a provider first', 'warning');
        return;
    }

    showLoading(true, 'Running LLM code review on generated code...');

    try {
        var res = await fetch('/api/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: migrationResult.files,
                summary: migrationResult.summary,
                llmConfig: llmConfig,
            }),
        });
        var data = await res.json();
        if (data.error) {
            showToast('Validation error: ' + data.error, 'error');
        } else if (data.validation) {
            migrationResult.llmValidation = data.validation;
            renderValidationResults(data.validation);
            document.getElementById('validationTabBtn').style.display = '';
            document.querySelector('.output-panel .tab[data-tab="output-validation"]').click();
            setStatus('Code review complete \u2014 Score: ' + data.validation.overallScore + '/10');
            showToast('Code review complete! Score: ' + data.validation.overallScore + '/10', 'success');
        }
    } catch (err) {
        showToast('Validation failed: ' + err.message, 'error');
    }
    showLoading(false);
}

// ==================== Validation Results Renderer ====================

function renderValidationResults(validation) {
    var el = document.getElementById('validationResults');
    if (!validation || (validation.overallScore === 0 && validation.issues.length === 0)) {
        el.innerHTML = '<div class="empty-state"><p>No validation data available</p></div>';
        return;
    }

    var score = validation.overallScore || 0;
    var scoreColor = score >= 8 ? '#22c55e' : score >= 5 ? '#f59e0b' : '#ef4444';
    var scoreLabel = score >= 8 ? 'Excellent' : score >= 6 ? 'Good' : score >= 4 ? 'Needs Work' : 'Poor';

    var issues = validation.issues || [];
    var critical = issues.filter(function(i) { return i.severity === 'critical'; });
    var warnings = issues.filter(function(i) { return i.severity === 'warning'; });
    var infos = issues.filter(function(i) { return i.severity === 'info'; });

    var issuesHtml = '';
    if (issues.length > 0) {
        var severityIcon = { critical: '&#10060;', warning: '&#9888;', info: '&#8505;' };
        var severityColor = { critical: '#ef4444', warning: '#f59e0b', info: '#3b82f6' };
        var issueItems = issues.map(function(i) {
            return '<div class="issue-item" style="border-left: 3px solid ' + (severityColor[i.severity] || '#64748b') + '">' +
                '<div class="issue-header">' +
                    '<span>' + (severityIcon[i.severity] || '') + ' <strong>' + i.severity.toUpperCase() + '</strong></span>' +
                    (i.file ? '<span class="issue-file">' + escapeHtml(i.file) + '</span>' : '') +
                '</div>' +
                '<div class="issue-message">' + escapeHtml(i.message) + '</div>' +
                (i.suggestion ? '<div class="issue-suggestion">Fix: ' + escapeHtml(i.suggestion) + '</div>' : '') +
            '</div>';
        }).join('');

        issuesHtml =
            '<div class="summary-card">' +
                '<h3>Issues Found (' + issues.length + ')</h3>' +
                '<div class="issue-stats">' +
                    (critical.length ? '<span class="issue-badge" style="background:#ef4444">' + critical.length + ' Critical</span>' : '') +
                    (warnings.length ? '<span class="issue-badge" style="background:#f59e0b">' + warnings.length + ' Warnings</span>' : '') +
                    (infos.length ? '<span class="issue-badge" style="background:#3b82f6">' + infos.length + ' Info</span>' : '') +
                '</div>' +
                '<div class="issues-list">' + issueItems + '</div>' +
            '</div>';
    }

    var improvementsHtml = '';
    var improvements = validation.improvements || [];
    if (improvements.length > 0) {
        var impItems = improvements.map(function(imp) {
            return '<div class="improvement-item">' +
                (imp.file ? '<div class="improvement-file">' + escapeHtml(imp.file) + '</div>' : '') +
                '<div class="improvement-desc">' + escapeHtml(imp.description) + '</div>' +
                (imp.code ? '<pre class="improvement-code"><code>' + escapeHtml(imp.code) + '</code></pre>' : '') +
            '</div>';
        }).join('');
        improvementsHtml =
            '<div class="summary-card">' +
                '<h3>Suggested Improvements (' + improvements.length + ')</h3>' +
                '<div class="improvements-list">' + impItems + '</div>' +
            '</div>';
    }

    var securityHtml = '';
    var security = validation.securityIssues || [];
    if (security.length > 0) {
        securityHtml =
            '<div class="summary-card">' +
                '<h3>&#128274; Security Concerns (' + security.length + ')</h3>' +
                '<ul class="warning-list">' + security.map(function(s) { return '<li>' + escapeHtml(s) + '</li>'; }).join('') + '</ul>' +
            '</div>';
    }

    var practicesHtml = '';
    var practices = validation.bestPractices || [];
    if (practices.length > 0) {
        practicesHtml =
            '<div class="summary-card">' +
                '<h3>Best Practice Notes (' + practices.length + ')</h3>' +
                '<ul class="warning-list">' + practices.map(function(p) { return '<li>' + escapeHtml(p) + '</li>'; }).join('') + '</ul>' +
            '</div>';
    }

    var missingHtml = '';
    var missing = validation.missingItems || [];
    if (missing.length > 0) {
        missingHtml =
            '<div class="summary-card">' +
                '<h3>Needs Manual Implementation (' + missing.length + ')</h3>' +
                '<ul class="warning-list">' + missing.map(function(m) { return '<li>' + escapeHtml(m) + '</li>'; }).join('') + '</ul>' +
            '</div>';
    }

    el.innerHTML =
        '<div class="validation-score-card" style="border-color: ' + scoreColor + '">' +
            '<div class="score-circle" style="border-color: ' + scoreColor + '; color: ' + scoreColor + '">' +
                '<span class="score-number">' + score + '</span>' +
                '<span class="score-max">/10</span>' +
            '</div>' +
            '<div class="score-details">' +
                '<div class="score-label" style="color: ' + scoreColor + '">' + scoreLabel + '</div>' +
                '<div class="score-summary">' + escapeHtml(validation.summary || '') + '</div>' +
            '</div>' +
        '</div>' +
        issuesHtml + securityHtml + improvementsHtml + practicesHtml + missingHtml;
}

// ==================== File Tree with Search & Collapsible Folders ====================

function renderFileTree(files) {
    var tree = document.getElementById('fileTree');
    tree.innerHTML = '';

    // Show search bar
    document.getElementById('treeSearchWrapper').style.display = '';
    document.getElementById('treeSearch').value = '';

    var dirs = {};
    var sortedPaths = Object.keys(files).sort();
    for (var i = 0; i < sortedPaths.length; i++) {
        var fp = sortedPaths[i];
        var parts = fp.split('/');
        var dir = parts.length > 1 ? parts.slice(0, -1).join('/') : '';
        if (!dirs[dir]) dirs[dir] = [];
        dirs[dir].push(fp);
    }

    for (var dir in dirs) {
        if (!dirs.hasOwnProperty(dir)) continue;
        if (dir) {
            var folderEl = document.createElement('div');
            folderEl.className = 'tree-folder';
            folderEl.innerHTML = '<span class="folder-chevron">&#9660;</span> ' + dir;
            folderEl.onclick = (function(el) {
                return function(e) {
                    e.stopPropagation();
                    el.classList.toggle('collapsed');
                };
            })(folderEl);
            tree.appendChild(folderEl);
        }

        var childrenWrapper = document.createElement('div');
        childrenWrapper.className = 'tree-folder-children';

        var filePaths = dirs[dir];
        for (var j = 0; j < filePaths.length; j++) {
            var filePath = filePaths[j];
            var filename = filePath.split('/').pop();
            var item = document.createElement('div');
            item.className = 'tree-item';
            item.dataset.path = filePath;
            item.dataset.name = filename.toLowerCase();
            (function(path, el) {
                el.onclick = function() { selectFile(path, el); };
                // Right-click context menu
                el.oncontextmenu = function(e) {
                    e.preventDefault();
                    showFileContextMenu(e, path);
                };
            })(filePath, item);
            item.innerHTML = '<span class="icon">' + getFileIcon(filename) + '</span> ' + filename;
            childrenWrapper.appendChild(item);
        }
        tree.appendChild(childrenWrapper);
    }

    var firstItem = tree.querySelector('.tree-item');
    if (firstItem) firstItem.click();
}

function filterFileTree(query) {
    query = query.toLowerCase();
    var items = document.querySelectorAll('.tree-item');
    var folders = document.querySelectorAll('.tree-folder');
    var childrenWrappers = document.querySelectorAll('.tree-folder-children');

    items.forEach(function(item) {
        var match = !query || item.dataset.name.indexOf(query) >= 0 || item.dataset.path.toLowerCase().indexOf(query) >= 0;
        item.style.display = match ? '' : 'none';
    });

    // Show/hide folders based on whether they have visible children
    childrenWrappers.forEach(function(wrapper) {
        var hasVisible = false;
        wrapper.querySelectorAll('.tree-item').forEach(function(item) {
            if (item.style.display !== 'none') hasVisible = true;
        });
        wrapper.style.display = hasVisible ? '' : 'none';
        var folder = wrapper.previousElementSibling;
        if (folder && folder.classList.contains('tree-folder')) {
            folder.style.display = hasVisible ? '' : 'none';
            // Expand folders when searching
            if (query) folder.classList.remove('collapsed');
        }
    });
}

function selectFile(filepath, item) {
    document.querySelectorAll('.tree-item').forEach(function(i) { i.classList.remove('active'); });
    item.classList.add('active');
    currentFilePath = filepath;
    var content = migrationResult.files[filepath];
    document.getElementById('fileContent').innerHTML =
        '<button class="copy-btn" onclick="copyFileContent()">Copy</button>' +
        '<div class="file-path-bar">' + filepath + '</div>' +
        '<pre><code>' + escapeHtml(content) + '</code></pre>';
}

function getFileIcon(filename) {
    if (filename.endsWith('.java'))       return '<span style="color:#f59e0b">&#9672;</span>';
    if (filename.endsWith('.xml'))        return '<span style="color:#ef4444">&lt;/&gt;</span>';
    if (filename.endsWith('.properties')) return '<span style="color:#22c55e">&#9776;</span>';
    if (filename.endsWith('.yml'))        return '<span style="color:#6366f1">Y</span>';
    if (filename === '.gitignore')        return '<span style="color:#64748b">G</span>';
    if (filename === 'Dockerfile')        return '<span style="color:#2196f3">D</span>';
    if (filename.endsWith('.yml') && filename.indexOf('docker') >= 0)
        return '<span style="color:#2196f3">&#9881;</span>';
    return '<span style="color:#94a3b8">F</span>';
}

// ==================== Copy to Clipboard ====================

function copyFileContent() {
    var code = document.querySelector('#fileContent code');
    if (!code) return;

    var text = code.textContent;
    navigator.clipboard.writeText(text).then(function() {
        var btn = document.querySelector('.copy-btn');
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        showToast('Copied to clipboard', 'success', 2000);
        setTimeout(function() {
            btn.textContent = 'Copy';
            btn.classList.remove('copied');
        }, 2000);
    }).catch(function() {
        showToast('Failed to copy', 'error');
    });
}

function copyCurrentFile() {
    if (!migrationResult || !currentFilePath) return;
    var text = migrationResult.files[currentFilePath] || '';
    navigator.clipboard.writeText(text).then(function() {
        showToast('Copied: ' + currentFilePath, 'success', 2000);
    });
}

// ==================== File Context Menu ====================

function showFileContextMenu(event, filepath) {
    closeContextMenu();
    var menu = document.createElement('div');
    menu.className = 'ctx-menu';
    menu.id = 'ctxMenu';
    menu.style.left = event.clientX + 'px';
    menu.style.top = event.clientY + 'px';

    var filename = filepath.split('/').pop();
    menu.innerHTML =
        '<div class="ctx-item" onclick="copyFilePath(\'' + filepath + '\')">&#128203; Copy path</div>' +
        '<div class="ctx-item" onclick="copySpecificFile(\'' + filepath + '\')">&#128196; Copy contents</div>' +
        '<div class="ctx-divider"></div>' +
        '<div class="ctx-item" onclick="downloadSingleFile(\'' + filepath + '\')">&#11015; Download ' + escapeHtml(filename) + '</div>';

    document.body.appendChild(menu);

    // Keep menu in viewport
    var rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
        menu.style.left = (window.innerWidth - rect.width - 8) + 'px';
    }
    if (rect.bottom > window.innerHeight) {
        menu.style.top = (window.innerHeight - rect.height - 8) + 'px';
    }

    setTimeout(function() {
        document.addEventListener('click', closeContextMenu, { once: true });
    }, 10);
}

function closeContextMenu() {
    var menu = document.getElementById('ctxMenu');
    if (menu) menu.remove();
}

function copyFilePath(filepath) {
    navigator.clipboard.writeText(filepath).then(function() {
        showToast('Path copied: ' + filepath, 'info', 2000);
    });
    closeContextMenu();
}

function copySpecificFile(filepath) {
    if (!migrationResult) return;
    var text = migrationResult.files[filepath] || '';
    navigator.clipboard.writeText(text).then(function() {
        showToast('Copied: ' + filepath, 'success', 2000);
    });
    closeContextMenu();
}

function downloadSingleFile(filepath) {
    if (!migrationResult) return;
    var text = migrationResult.files[filepath] || '';
    var filename = filepath.split('/').pop();
    var blob = new Blob([text], { type: 'text/plain' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Downloaded: ' + filename, 'success', 2000);
    closeContextMenu();
}

// ==================== Summary with Animated Stats ====================

function renderSummary(summary) {
    var el = document.getElementById('migrationSummary');

    var stats = [
        { value: summary.flowsConverted || 0, label: 'Flows' },
        { value: summary.subFlowsConverted || 0, label: 'Sub-Flows' },
        { value: summary.dataweaveScriptsConverted || 0, label: 'DataWeave Scripts' },
        { value: (summary.connectorsFound || []).length, label: 'Connectors' },
        { value: (summary.dependencies || []).length, label: 'Dependencies' },
        { value: summary.xmlFilesProcessed || 1, label: 'XML Files' },
    ];

    var connectorMappings = {
        'http': 'Spring Web (REST Controllers)',
        'database': 'Spring Data JPA + JDBC',
        'jms': 'Spring JMS (ActiveMQ)',
        'amqp': 'Spring AMQP (RabbitMQ)',
        'kafka': 'Spring Kafka',
        'vm': 'Spring Events',
        'file': 'Java NIO (Files/Paths)',
        'sftp': 'Spring Integration SFTP',
        'ftp': 'Spring Integration FTP',
        'email': 'Spring Mail',
        'objectstore': 'Spring Data Redis + Cache',
        'batch': 'Spring Batch',
        'validation': 'Spring Validation',
        'ee': 'Java Streams + Jackson',
        'ws': 'Spring Web Services (SOAP)',
        'wsc': 'Spring Web Services (SOAP)',
        'salesforce': 'WebClient (REST API)',
        's3': 'AWS SDK S3',
        'sqs': 'AWS SDK SQS',
        'sns': 'AWS SDK SNS',
        'mongo': 'Spring Data MongoDB',
        'redis': 'Spring Data Redis',
        'elasticsearch': 'Spring Data Elasticsearch',
        'oauth': 'Spring Security OAuth2',
        'apikit': 'Spring Web MVC',
    };

    var multiFileHtml = '';
    if (summary.xmlFileNames && summary.xmlFileNames.length > 1) {
        multiFileHtml =
            '<div class="summary-card">' +
                '<h3>XML Files Processed (' + summary.xmlFileNames.length + ')</h3>' +
                '<ul class="dep-list">' +
                    summary.xmlFileNames.map(function(n) { return '<li>' + escapeHtml(n) + '</li>'; }).join('') +
                '</ul>' +
            '</div>';
    }

    var connectorMapHtml = '';
    var found = summary.connectorsFound || [];
    if (found.length > 0) {
        var rows = found.map(function(c) {
            return '<tr><td class="conn-mule">' + c + '</td><td class="conn-arrow">&rarr;</td><td class="conn-spring">' + (connectorMappings[c] || 'Custom integration needed') + '</td></tr>';
        }).join('');
        connectorMapHtml =
            '<div class="summary-card">' +
                '<h3>Connector Mapping</h3>' +
                '<table class="connector-table">' +
                    '<thead><tr><th>MuleSoft</th><th></th><th>Spring Boot</th></tr></thead>' +
                    '<tbody>' + rows + '</tbody>' +
                '</table>' +
            '</div>';
    }

    var warningsArr = (summary.warnings || []).filter(function(w) { return w; });
    var warningsHtml = '';
    if (warningsArr.length > 0) {
        warningsHtml =
            '<div class="summary-card">' +
                '<h3>&#9888; Warnings &amp; TODOs (' + warningsArr.length + ')</h3>' +
                '<ul class="warning-list">' +
                    warningsArr.map(function(w) { return '<li>' + escapeHtml(w) + '</li>'; }).join('') +
                '</ul>' +
            '</div>';
    }

    var depsHtml = '';
    if (summary.dependencies && summary.dependencies.length > 0) {
        depsHtml =
            '<div class="summary-card">' +
                '<h3>Maven Dependencies (' + summary.dependencies.length + ')</h3>' +
                '<ul class="dep-list">' +
                    summary.dependencies.map(function(d) {
                        return '<li>' + d.groupId + ':<strong>' + d.artifactId + '</strong>' + (d.scope ? ' <span class="dep-scope">(' + d.scope + ')</span>' : '') + '</li>';
                    }).join('') +
                '</ul>' +
            '</div>';
    }

    // LLM Conversion Summary
    var llmHtml = '';
    var autoConversions = summary.autoConversions || [];
    var conversionSkipped = summary.conversionSkipped || [];
    var llmAssisted = summary.llmAssisted || false;

    if (autoConversions.length > 0 || conversionSkipped.length > 0) {
        var conversionsHtml = '';
        if (autoConversions.length > 0) {
            conversionsHtml =
                '<div style="margin-top: 10px;">' +
                    '<h4 style="color: var(--success); font-size: 12px; margin-bottom: 6px;">Auto-Converted (' + autoConversions.length + ')</h4>' +
                    autoConversions.map(function(c) {
                        return '<div class="sc-item">' +
                            '<span class="element">' + escapeHtml(c.element) + '</span>' +
                            '<span class="sc-badge">LLM</span>' +
                            '<div class="detail">' + escapeHtml(c.prompt_summary) + '</div>' +
                        '</div>';
                    }).join('') +
                '</div>';
        }
        var skippedHtml = '';
        if (conversionSkipped.length > 0) {
            skippedHtml =
                '<div style="margin-top: 10px;">' +
                    '<h4 style="color: #fbbf24; font-size: 12px; margin-bottom: 6px;">Skipped (' + conversionSkipped.length + ')</h4>' +
                    conversionSkipped.map(function(s) {
                        return '<div class="sc-item">' +
                            '<span class="element">' + escapeHtml(s.element) + '</span>' +
                            '<div class="detail">' + escapeHtml(s.reason) + '</div>' +
                        '</div>';
                    }).join('') +
                '</div>';
        }
        llmHtml =
            '<div class="sc-summary-card">' +
                '<h4>&#9889; Smart Conversion</h4>' +
                '<div class="sc-stats">' +
                    '<div class="sc-stat"><div class="number">' + autoConversions.length + '</div><div class="label">Converted</div></div>' +
                    '<div class="sc-stat"><div class="number">' + conversionSkipped.length + '</div><div class="label">Skipped</div></div>' +
                '</div>' +
                conversionsHtml + skippedHtml +
            '</div>';
    } else if (!llmAssisted && warningsArr.some(function(w) { return w.indexOf('Enable LLM') >= 0; })) {
        llmHtml =
            '<div class="sc-enable-prompt">' +
                '&#9889; Some elements could not be converted. <a onclick="switchInputTab(document.querySelector(\'[data-tab=llm-settings]\'))">Enable LLM Validation</a> to auto-convert unknown MuleSoft elements.' +
            '</div>';
    }

    el.innerHTML =
        '<div class="summary-stats">' +
            stats.map(function(s, idx) {
                return '<div class="stat animate-in" style="animation-delay:' + (idx * 80) + 'ms">' +
                    '<div class="stat-value" data-target="' + s.value + '">0</div>' +
                    '<div class="stat-label">' + s.label + '</div>' +
                '</div>';
            }).join('') +
        '</div>' +
        llmHtml + multiFileHtml + connectorMapHtml + depsHtml + warningsHtml +
        '<div class="summary-card">' +
            '<h3>&#10003; Migration Complete</h3>' +
            '<p style="color: var(--text-secondary); font-size: 14px; line-height: 1.6;">' +
                'Your MuleSoft application has been migrated to Spring Boot 3.2. Review the generated ' +
                'files and download the complete project. Key areas to verify:' +
            '</p>' +
            '<ul style="color: var(--text-secondary); font-size: 13px; margin-top: 12px; padding-left: 20px; line-height: 1.8;">' +
                '<li><strong>Controllers</strong> &mdash; verify HTTP method mappings and path variables</li>' +
                '<li><strong>DataWeave &rarr; Java</strong> &mdash; complex transformations may need manual tuning</li>' +
                '<li><strong>Database queries</strong> &mdash; check SQL parameter bindings and entity mappings</li>' +
                '<li><strong>External APIs</strong> &mdash; update base URLs in application.properties</li>' +
                '<li><strong>Error handling</strong> &mdash; customize GlobalExceptionHandler as needed</li>' +
                '<li><strong>application.properties</strong> &mdash; fill in credentials and connection details</li>' +
                '<li><strong>Docker Compose</strong> &mdash; infrastructure services are pre-configured</li>' +
            '</ul>' +
        '</div>';

    // Animate stat counters
    animateStatCounters();
}

function animateStatCounters() {
    var statValues = document.querySelectorAll('.stat-value[data-target]');
    statValues.forEach(function(el) {
        var target = parseInt(el.dataset.target, 10);
        if (target === 0) { el.textContent = '0'; return; }

        var start = 0;
        var duration = 600;
        var startTime = null;

        function tick(timestamp) {
            if (!startTime) startTime = timestamp;
            var progress = Math.min((timestamp - startTime) / duration, 1);
            var eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
            var current = Math.round(eased * target);
            el.textContent = current;
            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        }
        requestAnimationFrame(tick);
    });
}

// ==================== Download ====================

async function downloadProject() {
    if (!migrationResult) return;
    var projectName = document.getElementById('projectName').value || 'migrated-app';

    try {
        var response = await fetch('/api/migrate/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: migrationResult.files,
                projectName: projectName,
            }),
        });
        var blob = await response.blob();
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = projectName + '.zip';
        a.click();
        URL.revokeObjectURL(url);
        showToast('Downloaded: ' + projectName + '.zip', 'success');
        setStatus('Downloaded: ' + projectName + '.zip');
    } catch (err) {
        showToast('Download failed: ' + err.message, 'error');
    }
}

// ==================== Enhanced Sample ====================

function loadSample() {
    document.getElementById('muleXmlEditor').value = SAMPLE_MULE_XML;
    uploadedXmlFiles = [{ name: 'sample-api.xml', content: SAMPLE_MULE_XML }];
    renderUploadedFiles();
    dwScripts['transform-response'] = SAMPLE_DATAWEAVE;
    activeDwScript = 'transform-response';
    document.getElementById('dwEditor').value = SAMPLE_DATAWEAVE;
    renderDwScripts();
    updateEditorInfo();
    showToast('Sample loaded with HTTP, DB, JMS, Scheduler, Choice, Transform, Error Handling', 'info', 4000);
    setStatus('Sample loaded \u2014 press Ctrl+Enter to migrate');
}

var SAMPLE_MULE_XML = '<?xml version="1.0" encoding="UTF-8"?>\n' +
'<mule xmlns="http://www.mulesoft.org/schema/mule/core"\n' +
'      xmlns:http="http://www.mulesoft.org/schema/mule/http"\n' +
'      xmlns:db="http://www.mulesoft.org/schema/mule/db"\n' +
'      xmlns:jms="http://www.mulesoft.org/schema/mule/jms"\n' +
'      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core"\n' +
'      xmlns:validation="http://www.mulesoft.org/schema/mule/validation"\n' +
'      xmlns:os="http://www.mulesoft.org/schema/mule/os"\n' +
'      xmlns:file="http://www.mulesoft.org/schema/mule/file"\n' +
'      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n' +
'      xsi:schemaLocation="\n' +
'        http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd\n' +
'        http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\n' +
'        http://www.mulesoft.org/schema/mule/db http://www.mulesoft.org/schema/mule/db/current/mule-db.xsd\n' +
'        http://www.mulesoft.org/schema/mule/jms http://www.mulesoft.org/schema/mule/jms/current/mule-jms.xsd\n' +
'        http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\n' +
'        http://www.mulesoft.org/schema/mule/validation http://www.mulesoft.org/schema/mule/validation/current/mule-validation.xsd\n' +
'        http://www.mulesoft.org/schema/mule/os http://www.mulesoft.org/schema/mule/os/current/mule-os.xsd\n' +
'        http://www.mulesoft.org/schema/mule/file http://www.mulesoft.org/schema/mule/file/current/mule-file.xsd">\n' +
'\n' +
'    <!-- Global Configurations -->\n' +
'    <http:listener-config name="HTTP_Listener_config" host="0.0.0.0" port="8081" basePath="/api"/>\n' +
'\n' +
'    <http:request-config name="External_API_config">\n' +
'        <http:request-connection host="jsonplaceholder.typicode.com" port="443" protocol="HTTPS" basePath="/"/>\n' +
'    </http:request-config>\n' +
'\n' +
'    <db:config name="Database_Config">\n' +
'        <db:my-sql-connection host="localhost" port="3306" user="root" password="secret" database="myapp"/>\n' +
'    </db:config>\n' +
'\n' +
'    <jms:config name="JMS_Config">\n' +
'        <jms:active-mq-connection/>\n' +
'    </jms:config>\n' +
'\n' +
'    <!-- GET /users - List all users -->\n' +
'    <flow name="get-users-flow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/users" method="GET"/>\n' +
'        <logger level="INFO" message="Fetching all users"/>\n' +
'        <db:select config-ref="Database_Config">\n' +
'            <db:sql>SELECT id, first_name, last_name, email FROM users WHERE active = true</db:sql>\n' +
'        </db:select>\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-payload>\n' +
'                    %dw 2.0\n' +
'                    output application/json\n' +
'                    ---\n' +
'                    payload map (user) -> {\n' +
'                        id: user.id,\n' +
'                        name: user.first_name ++ " " ++ user.last_name,\n' +
'                        email: user.email\n' +
'                    }\n' +
'                </ee:set-payload>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'        <logger level="INFO" message="Returning #[sizeOf(payload)] users"/>\n' +
'    </flow>\n' +
'\n' +
'    <!-- POST /users - Create user with validation -->\n' +
'    <flow name="create-user-flow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/users" method="POST"/>\n' +
'        <logger level="INFO" message="Creating new user"/>\n' +
'        <validation:is-not-null value="#[payload.email]" message="Email is required"/>\n' +
'        <validation:is-email value="#[payload.email]" message="Invalid email format"/>\n' +
'        <set-variable variableName="userName" value="#[payload.firstName ++ \' \' ++ payload.lastName]"/>\n' +
'        <db:insert config-ref="Database_Config">\n' +
'            <db:sql>INSERT INTO users (first_name, last_name, email) VALUES (:firstName, :lastName, :email)</db:sql>\n' +
'            <db:input-parameters>\n' +
'                #[{\n' +
'                    firstName: payload.firstName,\n' +
'                    lastName: payload.lastName,\n' +
'                    email: payload.email\n' +
'                }]\n' +
'            </db:input-parameters>\n' +
'        </db:insert>\n' +
'        <jms:publish config-ref="JMS_Config" destination="user.created">\n' +
'        </jms:publish>\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-payload>\n' +
'                    %dw 2.0\n' +
'                    output application/json\n' +
'                    ---\n' +
'                    {\n' +
'                        message: "User created successfully",\n' +
'                        name: vars.userName,\n' +
'                        status: "201"\n' +
'                    }\n' +
'                </ee:set-payload>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'    </flow>\n' +
'\n' +
'    <!-- GET /users/{id} - With choice router -->\n' +
'    <flow name="get-user-by-id-flow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/users/{id}" method="GET"/>\n' +
'        <logger level="INFO" message="Fetching user #[attributes.uriParams.id]"/>\n' +
'        <db:select config-ref="Database_Config">\n' +
'            <db:sql>SELECT * FROM users WHERE id = :id</db:sql>\n' +
'            <db:input-parameters>\n' +
'                #[{ id: attributes.uriParams.id }]\n' +
'            </db:input-parameters>\n' +
'        </db:select>\n' +
'        <choice>\n' +
'            <when expression="#[sizeOf(payload) > 0]">\n' +
'                <ee:transform>\n' +
'                    <ee:message>\n' +
'                        <ee:set-payload>\n' +
'                            %dw 2.0\n' +
'                            output application/json\n' +
'                            ---\n' +
'                            payload[0]\n' +
'                        </ee:set-payload>\n' +
'                    </ee:message>\n' +
'                </ee:transform>\n' +
'            </when>\n' +
'            <otherwise>\n' +
'                <raise-error type="HTTP:NOT_FOUND" description="User not found"/>\n' +
'            </otherwise>\n' +
'        </choice>\n' +
'    </flow>\n' +
'\n' +
'    <!-- GET /external/posts - Call external API -->\n' +
'    <flow name="get-external-posts-flow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/external/posts" method="GET"/>\n' +
'        <http:request config-ref="External_API_config" method="GET" path="/posts"/>\n' +
'        <logger level="INFO" message="Received external API response"/>\n' +
'    </flow>\n' +
'\n' +
'    <!-- Scheduler - Cleanup old records -->\n' +
'    <flow name="cleanup-scheduler">\n' +
'        <scheduler>\n' +
'            <scheduling-strategy>\n' +
'                <cron expression="0 0 2 * * *"/>\n' +
'            </scheduling-strategy>\n' +
'        </scheduler>\n' +
'        <logger level="INFO" message="Running nightly cleanup"/>\n' +
'        <db:delete config-ref="Database_Config">\n' +
'            <db:sql>DELETE FROM audit_logs WHERE created_at &lt; DATE_SUB(NOW(), INTERVAL 90 DAY)</db:sql>\n' +
'        </db:delete>\n' +
'        <logger level="INFO" message="Cleanup complete"/>\n' +
'    </flow>\n' +
'\n' +
'    <!-- JMS Listener - Process user events -->\n' +
'    <flow name="process-user-event">\n' +
'        <jms:listener config-ref="JMS_Config" destination="user.created"/>\n' +
'        <logger level="INFO" message="Processing user event"/>\n' +
'        <try>\n' +
'            <file:write path="/tmp/user-events.log"/>\n' +
'            <error-handler>\n' +
'                <on-error-continue type="ANY">\n' +
'                    <logger level="ERROR" message="Failed to write event log: #[error.description]"/>\n' +
'                </on-error-continue>\n' +
'            </error-handler>\n' +
'        </try>\n' +
'    </flow>\n' +
'\n' +
'    <!-- Sub-flow: common validation -->\n' +
'    <sub-flow name="validate-user-input">\n' +
'        <validation:is-not-null value="#[payload.firstName]" message="First name is required"/>\n' +
'        <validation:is-not-null value="#[payload.lastName]" message="Last name is required"/>\n' +
'        <validation:is-email value="#[payload.email]" message="Invalid email"/>\n' +
'    </sub-flow>\n' +
'\n' +
'    <!-- Error Handler -->\n' +
'    <error-handler>\n' +
'        <on-error-propagate type="HTTP:NOT_FOUND">\n' +
'            <set-payload value=\'{"error": "Resource not found"}\'/>\n' +
'        </on-error-propagate>\n' +
'        <on-error-propagate type="VALIDATION:INVALID_BOOLEAN">\n' +
'            <set-payload value=\'{"error": "Validation failed"}\'/>\n' +
'        </on-error-propagate>\n' +
'        <on-error-propagate type="ANY">\n' +
'            <logger level="ERROR" message="Unexpected error: #[error.description]"/>\n' +
'            <set-payload value=\'{"error": "Internal server error"}\'/>\n' +
'        </on-error-propagate>\n' +
'    </error-handler>\n' +
'</mule>';

var SAMPLE_DATAWEAVE = '%dw 2.0\n' +
'output application/json\n' +
'var greeting = "Hello"\n' +
'---\n' +
'payload map (item, index) -> {\n' +
'    id: item.id,\n' +
'    fullName: item.firstName ++ " " ++ item.lastName,\n' +
'    email: lower(item.email),\n' +
'    greeting: greeting ++ " " ++ item.firstName,\n' +
'    active: item.status default "active",\n' +
'    createdAt: now(),\n' +
'    index: index\n' +
'}';

// ==================== Resizable Panels ====================

function initResizablePanels() {
    var divider = document.getElementById('panelDivider');
    if (!divider) return;

    var inputPanel = document.querySelector('.input-panel');
    var outputPanel = document.querySelector('.output-panel');
    var isDragging = false;

    divider.addEventListener('mousedown', function(e) {
        isDragging = true;
        divider.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        var container = document.querySelector('.main-content');
        var rect = container.getBoundingClientRect();
        var ratio = (e.clientX - rect.left) / rect.width;
        ratio = Math.max(0.2, Math.min(0.8, ratio));
        inputPanel.style.flex = 'none';
        outputPanel.style.flex = 'none';
        inputPanel.style.width = (ratio * 100) + '%';
        outputPanel.style.width = ((1 - ratio) * 100 - 0.5) + '%';
    });

    document.addEventListener('mouseup', function() {
        if (isDragging) {
            isDragging = false;
            divider.classList.remove('dragging');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });

    // Double-click to reset
    divider.addEventListener('dblclick', function() {
        inputPanel.style.flex = '1';
        outputPanel.style.flex = '1';
        inputPanel.style.width = '';
        outputPanel.style.width = '';
        showToast('Panels reset to 50/50', 'info', 1500);
    });
}

// ==================== Keyboard Shortcut Overlay ====================

function toggleShortcuts() {
    var overlay = document.getElementById('shortcutOverlay');
    overlay.classList.toggle('active');
}

// ==================== Confetti Celebration ====================

function triggerConfetti() {
    var colors = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];
    for (var i = 0; i < 40; i++) {
        (function(idx) {
            setTimeout(function() {
                var piece = document.createElement('div');
                piece.className = 'confetti-piece';
                piece.style.left = (Math.random() * 100) + 'vw';
                piece.style.top = '-10px';
                piece.style.background = colors[Math.floor(Math.random() * colors.length)];
                piece.style.animationDuration = (1.5 + Math.random()) + 's';
                piece.style.animationDelay = (Math.random() * 0.3) + 's';
                if (Math.random() > 0.5) {
                    piece.style.borderRadius = '50%';
                }
                document.body.appendChild(piece);
                setTimeout(function() { piece.remove(); }, 3000);
            }, idx * 30);
        })(i);
    }
}

// ==================== Utilities ====================

function clearAll() {
    document.getElementById('muleXmlEditor').value = '';
    document.getElementById('dwEditor').value = '';
    dwScripts = {};
    activeDwScript = null;
    migrationResult = null;
    currentFilePath = null;
    uploadedXmlFiles = [];
    document.getElementById('uploadedFilesList').innerHTML = '';
    document.getElementById('dwScriptList').innerHTML = '';
    document.getElementById('fileTree').innerHTML =
        '<div class="empty-state"><p>Run migration to see generated Spring Boot files</p></div>';
    document.getElementById('fileContent').innerHTML =
        '<div class="empty-state"><p>Select a file to view its contents</p></div>';
    document.getElementById('migrationSummary').innerHTML =
        '<div class="empty-state"><p>Migration summary will appear here</p></div>';
    document.getElementById('validationResults').innerHTML =
        '<div class="empty-state"><p>Enable LLM Code Review in settings and run migration to see results</p></div>';
    document.getElementById('downloadBtn').disabled = true;
    document.getElementById('validationTabBtn').style.display = 'none';
    document.getElementById('revalidateBtn').style.display = 'none';
    document.getElementById('treeSearchWrapper').style.display = 'none';
    var badge = document.getElementById('editorInfoBadge');
    if (badge) badge.textContent = '';
    showToast('All cleared', 'info', 2000);
    setStatus('Cleared');
}

function showLoading(show, text) {
    document.getElementById('loadingOverlay').classList.toggle('active', show);
    if (text) document.getElementById('loadingText').textContent = text;
}

function setStatus(text) {
    document.querySelector('.status-text').textContent = text;
}

function escapeHtml(str) {
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ==================== Keyboard Shortcuts ====================
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + Enter - Migrate
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        migrate();
    }
    // Ctrl/Cmd + S - Download
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (migrationResult) downloadProject();
    }
    // Ctrl/Cmd + L - Load sample
    if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
        e.preventDefault();
        loadSample();
    }
    // Ctrl/Cmd + Shift + K - Clear
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'K') {
        e.preventDefault();
        clearAll();
    }
    // Ctrl/Cmd + F - Focus file search (when output panel active)
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        var searchInput = document.getElementById('treeSearch');
        if (searchInput && searchInput.offsetParent !== null) {
            e.preventDefault();
            searchInput.focus();
        }
    }
    // Ctrl/Cmd + Shift + C - Copy current file
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'C') {
        e.preventDefault();
        copyCurrentFile();
    }
    // ? - Toggle shortcuts overlay (only when not in an input)
    if (e.key === '?' && !e.ctrlKey && !e.metaKey) {
        var tag = document.activeElement.tagName;
        if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
            e.preventDefault();
            toggleShortcuts();
        }
    }
    // Escape - close overlay/context menu
    if (e.key === 'Escape') {
        var overlay = document.getElementById('shortcutOverlay');
        if (overlay.classList.contains('active')) {
            toggleShortcuts();
        }
        closeContextMenu();
    }
});

// ==================== Initialize ====================
document.addEventListener('DOMContentLoaded', function() {
    // Editor info badge on input
    var editor = document.getElementById('muleXmlEditor');
    editor.addEventListener('input', updateEditorInfo);
    editor.addEventListener('focus', updateEditorInfo);

    document.getElementById('dwEditor').addEventListener('blur', function() {
        if (activeDwScript) {
            dwScripts[activeDwScript] = this.value;
        }
    });

    // Save LLM settings on change
    ['llmProvider', 'llmModel', 'llmApiKey', 'llmBaseUrl'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.addEventListener('change', saveLLMSettings);
    });

    loadLLMProviders();
    initResizablePanels();

    setStatus('Ready \u2014 Paste MuleSoft XML or load sample (Ctrl+Enter to migrate, ? for shortcuts)');

    // Welcome toast
    setTimeout(function() {
        showToast('Welcome! Paste XML or click "Load Sample" to get started', 'info', 5000);
    }, 500);
});
