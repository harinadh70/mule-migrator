// ═══════════════════════════════════════════════════════════════
// Migration Page — Full migration tool with inline editing
// ═══════════════════════════════════════════════════════════════

var migrationResult = null;
var dwScripts = {};
var activeDwScript = null;
var llmProviders = {};
var uploadedXmlFiles = [];
var currentFilePath = null;
var modifiedFiles = {};  // Track inline edits: {filepath: editedContent}
var editingMode = {};    // Track which files are in edit mode

// ── Tab Switching ──────────────────────────────────────────────
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

// ── Multi-File Upload ──────────────────────────────────────────
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
    if (files.length > 0) handleFileUpload({ target: { files: files } });
}

function renderUploadedFiles() {
    var list = document.getElementById('uploadedFilesList');
    if (uploadedXmlFiles.length === 0) { list.innerHTML = ''; return; }
    var html = '';
    for (var i = 0; i < uploadedXmlFiles.length; i++) {
        html += '<div class="uploaded-file-item" onclick="previewUploadedFile(' + i + ')">' +
            '<span class="file-name">' + escapeHtml(uploadedXmlFiles[i].name) + '</span>' +
            '<button class="remove-btn" onclick="removeUploadedFile(' + i + ', event)">&times;</button>' +
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
}

// ── Editor Info Badge ──────────────────────────────────────────
function updateEditorInfo() {
    var editor = document.getElementById('muleXmlEditor');
    var text = editor.value;
    var lines = text ? text.split('\n').length : 0;
    var chars = text.length;
    var badge = document.getElementById('editorInfoBadge');
    if (!badge) {
        badge = document.createElement('div');
        badge.id = 'editorInfoBadge';
        badge.style.cssText = 'position:absolute;bottom:8px;right:12px;font-size:11px;color:var(--text-muted);pointer-events:none;';
        editor.parentElement.style.position = 'relative';
        editor.parentElement.appendChild(badge);
    }
    badge.textContent = lines + ' lines | ' + chars + ' chars';
}

// ── DataWeave Scripts ──────────────────────────────────────────
function addDwScript() {
    var nameInput = document.getElementById('dwScriptName');
    var name = nameInput.value.trim();
    if (!name) { showToast('Enter a script name first', 'warning'); return; }
    if (!dwScripts[name]) dwScripts[name] = '';
    nameInput.value = '';
    renderDwScripts();
    selectDwScript(name);
    showToast('Added script: ' + name, 'success', 2000);
}

function selectDwScript(name) {
    if (activeDwScript) dwScripts[activeDwScript] = document.getElementById('dwEditor').value;
    activeDwScript = name;
    document.getElementById('dwEditor').value = dwScripts[name] || '';
    renderDwScripts();
}

function removeDwScript(name, event) {
    event.stopPropagation();
    delete dwScripts[name];
    if (activeDwScript === name) { activeDwScript = null; document.getElementById('dwEditor').value = ''; }
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
        (function(n) { chip.onclick = function() { selectDwScript(n); }; })(name);
        chip.innerHTML = name + ' <span style="cursor:pointer;margin-left:4px" onclick="removeDwScript(\'' + name + '\', event)">&times;</span>';
        list.appendChild(chip);
    }
}

// ── DataWeave Playground ───────────────────────────────────────
async function convertDataWeave() {
    var script = document.getElementById('dwEditor').value.trim();
    if (!script) { showToast('Enter a DataWeave script first', 'warning'); return; }
    try {
        var res = await fetch('/api/convert/dataweave', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ script: script }),
        });
        var data = await res.json();
        if (data.error) { showToast('Error: ' + data.error, 'error'); return; }
        var content = document.getElementById('fileContent');
        var java = data.result.java_code || '';
        var imports = (data.result.imports || []).join('\n');
        content.innerHTML =
            '<div class="file-content-header"><span class="file-path">DataWeave Conversion Result</span>' +
            '<div class="file-content-actions"><button class="btn btn-sm btn-ghost" onclick="copyToClipboard(document.querySelector(\'#fileContent pre\').textContent, \'Java code\')">Copy</button></div></div>' +
            '<div class="file-content-body"><pre>' +
            (imports ? '// Imports:\n' + escapeHtml(imports) + '\n\n' : '') +
            escapeHtml(java) + '</pre></div>';
        showToast('DataWeave converted to Java', 'success');
    } catch (err) {
        showToast('Conversion failed: ' + err.message, 'error');
    }
}

// ── LLM Settings ───────────────────────────────────────────────
async function loadLLMProviders() {
    try {
        var res = await fetch('/api/llm/providers');
        llmProviders = await res.json();
        populateProviderSelect();
        restoreLLMSettings();
    } catch (err) { /* providers not available */ }
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
    modelSelect.innerHTML = '<option value="">Select a model...</option>';

    if (!provider || !llmProviders[provider]) return;

    var p = llmProviders[provider];
    for (var i = 0; i < p.models.length; i++) {
        var opt = document.createElement('option');
        opt.value = p.models[i].id;
        opt.textContent = p.models[i].name + ' (' + p.models[i].tier + ')';
        modelSelect.appendChild(opt);
    }
    if (p.models.length > 0) modelSelect.value = p.models[0].id;

    if (provider === 'ollama') {
        document.getElementById('llmApiKeyGroup').style.display = 'none';
        document.getElementById('llmBaseUrlGroup').style.display = '';
    } else {
        document.getElementById('llmApiKeyGroup').style.display = '';
        document.getElementById('llmBaseUrlGroup').style.display = 'none';
        document.getElementById('llmDocsLink').innerHTML = p.docs_url ? 'Get your API key at <a href="' + p.docs_url + '" target="_blank" style="color:var(--accent)">' + p.docs_url + '</a>' : '';
    }

    document.getElementById('llmProviderInfo').innerHTML =
        '<strong>' + p.name + '</strong> &mdash; ' + p.models.length + ' models available';

    saveLLMSettings();
}

function toggleLLM() {
    var cb = document.getElementById('llmEnabled');
    cb.checked = !cb.checked;
    document.getElementById('llmSettingsPanel').classList.toggle('disabled', !cb.checked);
    showToast(cb.checked ? 'LLM Code Review enabled' : 'LLM Code Review disabled', 'info', 2000);
    saveLLMSettings();
}

function toggleApiKeyVisibility() {
    var input = document.getElementById('llmApiKey');
    input.type = input.type === 'password' ? 'text' : 'password';
}

function getMigrationLLMConfig() {
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
    var config = getMigrationLLMConfig();
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
        if (model) document.getElementById('llmModel').value = model;
    }
    if (baseUrl) document.getElementById('llmBaseUrl').value = baseUrl;
}

async function testLLMConnection() {
    var config = getMigrationLLMConfig();
    if (!config.enabled || !config.provider) {
        showToast('Enable LLM and select a provider first', 'warning');
        return;
    }
    var btn = document.getElementById('testLlmBtn');
    btn.disabled = true; btn.textContent = 'Testing...';
    document.getElementById('llmTestResult').textContent = '';

    try {
        var res = await fetch('/api/validate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                files: { 'Test.java': 'public class Test { public static void main(String[] args) {} }' },
                summary: { flowsConverted: 1 },
                llmConfig: config,
            }),
        });
        var data = await res.json();
        var result = document.getElementById('llmTestResult');
        if (data.error) {
            result.textContent = 'Failed: ' + data.error;
            result.style.color = 'var(--error)';
        } else {
            result.textContent = 'Connected!';
            result.style.color = 'var(--success)';
            showToast('LLM connection successful!', 'success');
        }
    } catch (err) {
        document.getElementById('llmTestResult').textContent = 'Error: ' + err.message;
    }
    btn.disabled = false; btn.textContent = 'Test Connection';
}

// ── Progress Stepper ───────────────────────────────────────────
var stepTimers = [];

function startProgressStepper(withLLM) {
    var stepper = document.getElementById('progressStepper');
    stepper.querySelectorAll('.step-row').forEach(function(s) { s.className = 'step-row pending'; });
    var reviewStep = stepper.querySelector('[data-step="review"]');
    reviewStep.style.display = withLLM ? '' : 'none';

    var stepNames = ['parse', 'connectors', 'dataweave', 'generate'];
    if (withLLM) stepNames.push('review');

    stepTimers = [];
    var delay = 0;
    for (var i = 0; i < stepNames.length; i++) {
        (function(name) {
            stepTimers.push(setTimeout(function() { advanceStep(name); }, delay));
        })(stepNames[i]);
        delay += 800 + Math.random() * 600;
    }
}

function advanceStep(stepName) {
    var stepper = document.getElementById('progressStepper');
    var prev = stepper.querySelector('.step-row.active');
    if (prev) { prev.className = 'step-row done'; prev.querySelector('.step-icon').innerHTML = '&#10003;'; }
    var current = stepper.querySelector('[data-step="' + stepName + '"]');
    if (current) current.className = 'step-row active';
}

function completeAllSteps() {
    stepTimers.forEach(function(t) { clearTimeout(t); });
    stepTimers = [];
    document.getElementById('progressStepper').querySelectorAll('.step-row').forEach(function(s) {
        if (s.style.display !== 'none') {
            s.className = 'step-row done';
            s.querySelector('.step-icon').innerHTML = '&#10003;';
        }
    });
}

function resetStepper() {
    document.getElementById('progressStepper').querySelectorAll('.step-row').forEach(function(s) {
        s.className = 'step-row pending';
    });
}

// ── Migration ──────────────────────────────────────────────────
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
    if (activeDwScript) dwScripts[activeDwScript] = document.getElementById('dwEditor').value;

    var projectName = document.getElementById('projectName').value || 'migrated-app';
    var groupId = document.getElementById('groupId').value || 'com.example';
    var javaVersion = document.getElementById('javaVersion').value || '17';
    var llmConfig = getMigrationLLMConfig();

    showLoading(llmConfig.enabled ? 'Migrating + LLM Code Review...' : 'Migrating MuleSoft to Spring Boot...');
    startProgressStepper(llmConfig.enabled);
    setStatus('Migrating...');

    try {
        var response = await fetch('/api/migrate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                muleXmlFiles: xmlFiles, dataweaveScripts: dwScripts,
                projectName: projectName, groupId: groupId,
                javaVersion: javaVersion, llmConfig: llmConfig,
            }),
        });
        var data = await response.json();
        if (data.error) {
            showToast('Migration error: ' + data.error, 'error', 6000);
            setStatus('Error: ' + data.error);
            hideLoading(); resetStepper();
            return;
        }

        completeAllSteps();
        migrationResult = data;
        modifiedFiles = {};
        editingMode = {};

        // Save to cross-page store
        MigrationStore.save(data);

        // Auto-generate Swagger spec and store it
        if (data.files && data.summary) {
            fetch('/api/swagger/from-migration', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    parsedData: data.parsed || data.summary,
                    projectName: projectName
                })
            }).then(function(r) { return r.json(); })
            .then(function(swaggerData) {
                if (swaggerData.success && swaggerData.spec) {
                    localStorage.setItem('msb_swagger_spec', JSON.stringify(swaggerData.spec));
                }
            }).catch(function() { /* silent - swagger is optional */ });
        }

        renderFileTree(data.files);
        renderSummary(data.summary);
        document.getElementById('downloadBtn').disabled = false;

        if (data.llmValidation) {
            renderValidationResults(data.llmValidation);
            document.getElementById('validationTabBtn').style.display = '';
            document.getElementById('revalidateBtn').style.display = '';
        }

        var fileCount = Object.keys(data.files).length;
        setStatus('Migration complete — ' + fileCount + ' files generated');
        document.querySelector('.output-panel .tab[data-tab="output-files"]').click();
        showToast('Migration successful! ' + fileCount + ' files generated', 'success', 5000);

    } catch (err) {
        showToast('Migration failed: ' + err.message, 'error', 6000);
        setStatus('Error: ' + err.message);
        resetStepper();
    }
    setTimeout(function() { hideLoading(); resetStepper(); }, 800);
}

// ── Re-validate ────────────────────────────────────────────────
async function revalidateWithLLM() {
    if (!migrationResult) return;
    var llmConfig = getMigrationLLMConfig();
    if (!llmConfig.enabled || !llmConfig.provider) {
        showToast('Enable LLM and select a provider first', 'warning');
        return;
    }
    showLoading('Running LLM code review...');
    try {
        var filesToValidate = Object.assign({}, migrationResult.files, modifiedFiles);
        var res = await fetch('/api/validate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: filesToValidate, summary: migrationResult.summary, llmConfig: llmConfig }),
        });
        var data = await res.json();
        if (data.error) {
            showToast('Validation error: ' + data.error, 'error');
        } else if (data.validation) {
            migrationResult.llmValidation = data.validation;
            renderValidationResults(data.validation);
            document.getElementById('validationTabBtn').style.display = '';
            document.querySelector('.output-panel .tab[data-tab="output-validation"]').click();
            showToast('Code review complete! Score: ' + data.validation.overallScore + '/10', 'success');
        }
    } catch (err) {
        showToast('Validation failed: ' + err.message, 'error');
    }
    hideLoading();
}

// Validate only modified files
async function validateAllModified() {
    if (!migrationResult || Object.keys(modifiedFiles).length === 0) {
        showToast('No modified files to validate', 'info');
        return;
    }
    var llmConfig = getMigrationLLMConfig();
    if (!llmConfig.enabled || !llmConfig.provider) {
        showToast('Enable LLM and select a provider first', 'warning');
        return;
    }
    showLoading('Validating edited files...');
    try {
        var res = await fetch('/api/validate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: modifiedFiles, summary: migrationResult.summary, llmConfig: llmConfig }),
        });
        var data = await res.json();
        if (data.validation) {
            renderValidationResults(data.validation);
            document.querySelector('.output-panel .tab[data-tab="output-validation"]').click();
            showToast('Edited files validated! Score: ' + data.validation.overallScore + '/10', 'success');
        }
    } catch (err) {
        showToast('Validation failed: ' + err.message, 'error');
    }
    hideLoading();
}

// ── Validation Results ─────────────────────────────────────────
function renderValidationResults(validation) {
    var el = document.getElementById('validationResults');
    if (!validation) {
        el.innerHTML = '<div class="empty-state"><p>No validation data available</p></div>';
        return;
    }
    var score = validation.overallScore || 0;
    var scoreClass = score >= 8 ? 'score-high' : score >= 5 ? 'score-mid' : 'score-low';
    var scoreLabel = score >= 8 ? 'Excellent' : score >= 6 ? 'Good' : score >= 4 ? 'Needs Work' : 'Poor';

    var issues = validation.issues || [];
    var issuesHtml = '';
    if (issues.length > 0) {
        issuesHtml = '<h3 style="margin:16px 0 8px;font-size:14px;">Issues (' + issues.length + ')</h3>';
        issues.forEach(function(i) {
            var sev = i.severity || 'info';
            issuesHtml += '<div class="validation-issue severity-' + sev + '">' +
                (i.file ? '<div class="issue-file">' + escapeHtml(i.file) + '</div>' : '') +
                '<div class="issue-message">' + escapeHtml(i.message) + '</div>' +
                (i.suggestion ? '<div class="issue-suggestion">Suggestion: ' + escapeHtml(i.suggestion) + '</div>' : '') +
                '</div>';
        });
    }

    var sections = '';
    var listSections = [
        { key: 'securityIssues', title: 'Security Concerns' },
        { key: 'improvements', title: 'Improvements' },
        { key: 'bestPractices', title: 'Best Practices' },
        { key: 'missingItems', title: 'Manual Implementation Needed' },
    ];
    listSections.forEach(function(sec) {
        var items = validation[sec.key] || [];
        if (items.length > 0) {
            sections += '<h3 style="margin:16px 0 8px;font-size:14px;">' + sec.title + ' (' + items.length + ')</h3><ul style="padding-left:20px;color:var(--text-secondary);font-size:13px;">';
            items.forEach(function(item) {
                var text = typeof item === 'string' ? item : (item.description || item.message || JSON.stringify(item));
                sections += '<li style="margin-bottom:4px">' + escapeHtml(text) + '</li>';
            });
            sections += '</ul>';
        }
    });

    el.innerHTML =
        '<div class="validation-score">' +
            '<div class="score-circle ' + scoreClass + '">' + score + '</div>' +
            '<div><div style="font-size:16px;font-weight:600;">' + scoreLabel + '</div>' +
            '<div style="font-size:13px;color:var(--text-secondary);margin-top:4px;">' + escapeHtml(validation.summary || '') + '</div></div>' +
        '</div>' + issuesHtml + sections;
}

// ── File Tree ──────────────────────────────────────────────────
function renderFileTree(files) {
    var tree = document.getElementById('fileTree');
    tree.innerHTML = '';
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
            folderEl.innerHTML = '<span class="folder-icon">&#9660;</span> ' + dir;
            folderEl.onclick = (function(el) {
                return function(e) { e.stopPropagation(); el.classList.toggle('collapsed'); };
            })(folderEl);
            tree.appendChild(folderEl);
        }
        var childrenWrapper = document.createElement('div');
        childrenWrapper.className = 'tree-folder-children';

        dirs[dir].forEach(function(filePath) {
            var filename = filePath.split('/').pop();
            var item = document.createElement('div');
            item.className = 'tree-file';
            item.dataset.path = filePath;
            item.dataset.name = filename.toLowerCase();
            (function(path, el) {
                el.onclick = function() { selectFile(path, el); };
                el.oncontextmenu = function(e) { e.preventDefault(); showFileContextMenu(e, path); };
            })(filePath, item);
            var modifiedIndicator = modifiedFiles[filePath] ? '<span class="modified-dot"></span>' : '';
            item.innerHTML = '<span class="file-icon">' + getFileIcon(filename) + '</span>' + filename + modifiedIndicator;
            childrenWrapper.appendChild(item);
        });
        tree.appendChild(childrenWrapper);
    }

    var firstItem = tree.querySelector('.tree-file');
    if (firstItem) firstItem.click();
}

function filterFileTree(query) {
    query = query.toLowerCase();
    document.querySelectorAll('.tree-file').forEach(function(item) {
        item.style.display = (!query || item.dataset.name.indexOf(query) >= 0 || item.dataset.path.toLowerCase().indexOf(query) >= 0) ? '' : 'none';
    });
    document.querySelectorAll('.tree-folder-children').forEach(function(wrapper) {
        var hasVisible = false;
        wrapper.querySelectorAll('.tree-file').forEach(function(item) { if (item.style.display !== 'none') hasVisible = true; });
        wrapper.style.display = hasVisible ? '' : 'none';
        var folder = wrapper.previousElementSibling;
        if (folder && folder.classList.contains('tree-folder')) {
            folder.style.display = hasVisible ? '' : 'none';
            if (query) folder.classList.remove('collapsed');
        }
    });
}

// ── File Viewer with Inline Editing ────────────────────────────
function selectFile(filepath, item) {
    document.querySelectorAll('.tree-file').forEach(function(i) { i.classList.remove('active'); });
    if (item) item.classList.add('active');
    currentFilePath = filepath;

    var content = modifiedFiles[filepath] || migrationResult.files[filepath] || '';
    var isEditing = editingMode[filepath] || false;
    var isModified = !!modifiedFiles[filepath];

    var headerHtml =
        '<div class="file-content-header">' +
            '<span class="file-path">' + escapeHtml(filepath) + '</span>' +
            '<div class="file-content-actions">' +
                (isModified ? '<span class="edit-badge saved">Modified</span>' : '') +
                '<button class="btn btn-sm btn-ghost" onclick="toggleEditMode(\'' + filepath + '\')">' +
                    (isEditing ? 'View' : 'Edit') +
                '</button>' +
                '<button class="btn btn-sm btn-ghost" onclick="copyToClipboard(getFileContent(\'' + filepath + '\'), \'' + filepath.split('/').pop() + '\')">Copy</button>' +
                '<button class="btn btn-sm btn-ghost" onclick="downloadSingleFile(\'' + filepath + '\')">Download</button>' +
            '</div>' +
        '</div>';

    if (isEditing) {
        document.getElementById('fileContent').innerHTML = headerHtml +
            '<div class="file-content-body">' +
            '<textarea id="inlineEditor" style="width:100%;height:100%;background:var(--bg-primary);color:var(--text-primary);border:none;padding:16px;font-family:var(--font-mono);font-size:13px;line-height:1.5;resize:none;outline:none;">' +
            escapeHtml(content) + '</textarea>' +
            '<div style="padding:8px 12px;background:var(--bg-secondary);border-top:1px solid var(--border);display:flex;gap:8px;">' +
                '<button class="btn btn-sm btn-primary" onclick="saveInlineEdit(\'' + filepath + '\')">Save Changes</button>' +
                '<button class="btn btn-sm btn-ghost" onclick="discardInlineEdit(\'' + filepath + '\')">Discard</button>' +
                '<button class="btn btn-sm" onclick="validateSingleFile(\'' + filepath + '\')">Validate This File</button>' +
            '</div></div>';
    } else {
        document.getElementById('fileContent').innerHTML = headerHtml +
            '<div class="file-content-body"><pre>' + escapeHtml(content) + '</pre></div>';
    }
}

function toggleEditMode(filepath) {
    editingMode[filepath] = !editingMode[filepath];
    var item = document.querySelector('.tree-file[data-path="' + filepath + '"]');
    selectFile(filepath, item);
}

function saveInlineEdit(filepath) {
    var editor = document.getElementById('inlineEditor');
    if (!editor) return;
    var newContent = editor.value;
    modifiedFiles[filepath] = newContent;
    migrationResult.files[filepath] = newContent;
    MigrationStore.save(migrationResult);

    editingMode[filepath] = false;
    renderFileTree(migrationResult.files);  // Refresh to show modified dots
    var item = document.querySelector('.tree-file[data-path="' + filepath + '"]');
    if (item) selectFile(filepath, item);
    showToast('Saved changes to ' + filepath.split('/').pop(), 'success', 2000);
    document.getElementById('validateModifiedBtn').style.display = '';
}

function discardInlineEdit(filepath) {
    editingMode[filepath] = false;
    var item = document.querySelector('.tree-file[data-path="' + filepath + '"]');
    selectFile(filepath, item);
}

async function validateSingleFile(filepath) {
    var llmConfig = getMigrationLLMConfig();
    if (!llmConfig.enabled || !llmConfig.provider) {
        showToast('Enable LLM and select a provider first', 'warning');
        return;
    }
    showLoading('Validating ' + filepath.split('/').pop() + '...');
    try {
        var files = {};
        files[filepath] = modifiedFiles[filepath] || migrationResult.files[filepath];
        var res = await fetch('/api/validate', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: files, summary: migrationResult.summary || {}, llmConfig: llmConfig }),
        });
        var data = await res.json();
        if (data.validation) {
            renderValidationResults(data.validation);
            document.getElementById('validationTabBtn').style.display = '';
            document.querySelector('.output-panel .tab[data-tab="output-validation"]').click();
            showToast('File validated! Score: ' + data.validation.overallScore + '/10', 'success');
        }
    } catch (err) {
        showToast('Validation failed: ' + err.message, 'error');
    }
    hideLoading();
}

function getFileContent(filepath) {
    return modifiedFiles[filepath] || (migrationResult ? migrationResult.files[filepath] : '') || '';
}

function getFileIcon(filename) {
    if (filename.endsWith('.java'))       return '<span style="color:#f59e0b">J</span>';
    if (filename.endsWith('.xml'))        return '<span style="color:#ef4444">&lt;/&gt;</span>';
    if (filename.endsWith('.properties')) return '<span style="color:#22c55e">P</span>';
    if (filename.endsWith('.yml'))        return '<span style="color:#6366f1">Y</span>';
    if (filename === '.gitignore')        return '<span style="color:#64748b">G</span>';
    if (filename === 'Dockerfile')        return '<span style="color:#2196f3">D</span>';
    return '<span style="color:#94a3b8">F</span>';
}

// ── Context Menu ───────────────────────────────────────────────
function showFileContextMenu(event, filepath) {
    closeContextMenu();
    var menu = document.createElement('div');
    menu.className = 'context-menu';
    menu.id = 'ctxMenu';
    menu.style.left = event.clientX + 'px';
    menu.style.top = event.clientY + 'px';

    var filename = filepath.split('/').pop();
    menu.innerHTML =
        '<div class="context-menu-item" onclick="copyToClipboard(\'' + filepath + '\', \'Path\')">Copy path</div>' +
        '<div class="context-menu-item" onclick="copyToClipboard(getFileContent(\'' + filepath + '\'), \'' + filename + '\')">Copy contents</div>' +
        '<div class="context-menu-item" onclick="toggleEditMode(\'' + filepath + '\')">Edit file</div>' +
        '<div class="context-menu-item" onclick="downloadSingleFile(\'' + filepath + '\')">Download ' + escapeHtml(filename) + '</div>';

    document.body.appendChild(menu);

    var rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) menu.style.left = (window.innerWidth - rect.width - 8) + 'px';
    if (rect.bottom > window.innerHeight) menu.style.top = (window.innerHeight - rect.height - 8) + 'px';

    setTimeout(function() { document.addEventListener('click', closeContextMenu, { once: true }); }, 10);
}

function closeContextMenu() {
    var menu = document.getElementById('ctxMenu');
    if (menu) menu.remove();
}

function downloadSingleFile(filepath) {
    var text = getFileContent(filepath);
    var filename = filepath.split('/').pop();
    var blob = new Blob([text], { type: 'text/plain' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = filename; a.click();
    URL.revokeObjectURL(url);
    showToast('Downloaded: ' + filename, 'success', 2000);
    closeContextMenu();
}

// ── Summary ────────────────────────────────────────────────────
function renderSummary(summary) {
    var el = document.getElementById('migrationSummary');
    var stats = [
        { value: summary.flowsConverted || 0, label: 'Flows' },
        { value: summary.subFlowsConverted || 0, label: 'Sub-Flows' },
        { value: summary.dataweaveScriptsConverted || 0, label: 'DataWeave' },
        { value: (summary.connectorsFound || []).length, label: 'Connectors' },
        { value: (summary.dependencies || []).length, label: 'Dependencies' },
        { value: summary.xmlFilesProcessed || 1, label: 'XML Files' },
    ];

    var statsHtml = '<div class="summary-stats">' + stats.map(function(s) {
        return '<div class="summary-stat"><div class="stat-value" data-target="' + s.value + '">0</div><div class="stat-label">' + s.label + '</div></div>';
    }).join('') + '</div>';

    var connectorsHtml = '';
    var found = summary.connectorsFound || [];
    if (found.length > 0) {
        connectorsHtml = '<div class="summary-section"><h3>Connector Mapping</h3><ul class="summary-list">';
        var connMap = { http: 'Spring Web', database: 'Spring Data JPA', jms: 'Spring JMS', amqp: 'Spring AMQP', kafka: 'Spring Kafka', vm: 'Spring Events', file: 'Java NIO', sftp: 'Spring SFTP', ftp: 'Spring FTP', email: 'Spring Mail', batch: 'Spring Batch', validation: 'Spring Validation', ee: 'Java Streams', ws: 'Spring WS', salesforce: 'WebClient', s3: 'AWS S3', sqs: 'AWS SQS', mongo: 'Spring MongoDB', redis: 'Spring Redis', oauth: 'Spring Security' };
        found.forEach(function(c) {
            connectorsHtml += '<li><strong>' + c + '</strong> &rarr; ' + (connMap[c] || 'Custom integration') + '</li>';
        });
        connectorsHtml += '</ul></div>';
    }

    var warningsHtml = '';
    var warnings = (summary.warnings || []).filter(Boolean);
    if (warnings.length > 0) {
        warningsHtml = '<div class="summary-section"><h3>Warnings (' + warnings.length + ')</h3><ul class="summary-list">';
        warnings.forEach(function(w) { warningsHtml += '<li>' + escapeHtml(w) + '</li>'; });
        warningsHtml += '</ul></div>';
    }

    var actionsHtml = '<div class="summary-section" style="margin-top:16px">' +
        '<h3>Next Steps</h3>' +
        '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">' +
        '<a href="/swagger" class="btn btn-sm" style="text-decoration:none">Generate Swagger</a>' +
        '<a href="/github" class="btn btn-sm" style="text-decoration:none">Push to GitHub</a>' +
        '<a href="/build" class="btn btn-sm" style="text-decoration:none">Build JAR</a>' +
        '<a href="/build" class="btn btn-sm" style="text-decoration:none">Run Tests</a>' +
        '</div></div>';

    el.innerHTML = statsHtml + connectorsHtml + warningsHtml + actionsHtml;

    // Animate stat counters
    el.querySelectorAll('.stat-value[data-target]').forEach(function(statEl) {
        var target = parseInt(statEl.dataset.target, 10);
        if (target === 0) { statEl.textContent = '0'; return; }
        var startTime = null;
        function tick(ts) {
            if (!startTime) startTime = ts;
            var progress = Math.min((ts - startTime) / 600, 1);
            statEl.textContent = Math.round((1 - Math.pow(1 - progress, 3)) * target);
            if (progress < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    });
}

// ── Download ───────────────────────────────────────────────────
async function downloadProject() {
    if (!migrationResult) return;
    var projectName = document.getElementById('projectName').value || 'migrated-app';
    try {
        var allFiles = Object.assign({}, migrationResult.files, modifiedFiles);
        var response = await fetch('/api/migrate/download', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: allFiles, projectName: projectName }),
        });
        var blob = await response.blob();
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a'); a.href = url; a.download = projectName + '.zip'; a.click();
        URL.revokeObjectURL(url);
        showToast('Downloaded: ' + projectName + '.zip', 'success');
    } catch (err) {
        showToast('Download failed: ' + err.message, 'error');
    }
}


// ── Resizable Panels ───────────────────────────────────────────
function initResizablePanels() {
    var divider = document.getElementById('panelDivider');
    if (!divider) return;
    var inputPanel = document.querySelector('.input-panel');
    var outputPanel = document.querySelector('.output-panel');
    var isDragging = false;

    divider.addEventListener('mousedown', function(e) {
        isDragging = true; divider.classList.add('dragging');
        document.body.style.cursor = 'col-resize'; document.body.style.userSelect = 'none';
        e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
        if (!isDragging) return;
        var container = document.querySelector('.migration-layout');
        var rect = container.getBoundingClientRect();
        var ratio = Math.max(0.2, Math.min(0.8, (e.clientX - rect.left) / rect.width));
        inputPanel.style.flex = 'none'; outputPanel.style.flex = 'none';
        inputPanel.style.width = (ratio * 100) + '%';
        outputPanel.style.width = ((1 - ratio) * 100 - 0.5) + '%';
    });
    document.addEventListener('mouseup', function() {
        if (isDragging) {
            isDragging = false; divider.classList.remove('dragging');
            document.body.style.cursor = ''; document.body.style.userSelect = '';
        }
    });
    divider.addEventListener('dblclick', function() {
        inputPanel.style.flex = '1'; outputPanel.style.flex = '1';
        inputPanel.style.width = ''; outputPanel.style.width = '';
        showToast('Panels reset to 50/50', 'info', 1500);
    });
}


// ── Utilities ──────────────────────────────────────────────────
function clearAll() {
    document.getElementById('muleXmlEditor').value = '';
    document.getElementById('dwEditor').value = '';
    dwScripts = {}; activeDwScript = null; migrationResult = null;
    currentFilePath = null; uploadedXmlFiles = []; modifiedFiles = {}; editingMode = {};
    document.getElementById('uploadedFilesList').innerHTML = '';
    document.getElementById('dwScriptList').innerHTML = '';
    document.getElementById('fileTree').innerHTML = '<div class="empty-state"><p>Run migration to see generated Spring Boot files</p></div>';
    document.getElementById('fileContent').innerHTML = '<div class="empty-state"><p>Select a file to view its contents</p></div>';
    document.getElementById('migrationSummary').innerHTML = '<div class="empty-state"><p>Migration summary will appear here</p></div>';
    document.getElementById('validationResults').innerHTML = '<div class="empty-state"><p>Enable LLM Code Review and run migration</p></div>';
    document.getElementById('downloadBtn').disabled = true;
    document.getElementById('validationTabBtn').style.display = 'none';
    document.getElementById('revalidateBtn').style.display = 'none';
    document.getElementById('validateModifiedBtn').style.display = 'none';
    document.getElementById('treeSearchWrapper').style.display = 'none';
    MigrationStore.clear();
    showToast('All cleared', 'info', 2000);
    setStatus('Cleared');
}

// ── Keyboard Shortcuts ─────────────────────────────────────────
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); migrate(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); if (migrationResult) downloadProject(); }

    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'K') { e.preventDefault(); clearAll(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
        var searchInput = document.getElementById('treeSearch');
        if (searchInput && searchInput.offsetParent !== null) { e.preventDefault(); searchInput.focus(); }
    }
});


// ── Sample MuleSoft XMLs ──────────────────────────────────────
var MULE_SAMPLES = {
    'http-hello': {
        name: 'http-hello-world.xml',
        xml: '<?xml version="1.0" encoding="UTF-8"?>\n' +
'<mule xmlns="http://www.mulesoft.org/schema/mule/core"\n' +
'      xmlns:http="http://www.mulesoft.org/schema/mule/http"\n' +
'      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n' +
'      xsi:schemaLocation="http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd">\n' +
'\n' +
'    <http:listener-config name="HTTP_Listener_config">\n' +
'        <http:listener-connection host="0.0.0.0" port="8081"/>\n' +
'    </http:listener-config>\n' +
'\n' +
'    <flow name="helloWorldFlow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/api/hello"/>\n' +
'        <logger level="INFO" message="Received request from #[attributes.remoteAddress]"/>\n' +
'        <set-payload value=\'#[output application/json --- { "message": "Hello World", "timestamp": now() }]\'/>\n' +
'    </flow>\n' +
'\n' +
'    <flow name="healthCheckFlow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/api/health"/>\n' +
'        <set-payload value=\'#[output application/json --- { "status": "UP", "version": "1.0.0" }]\'/>\n' +
'    </flow>\n' +
'</mule>'
    },

    'rest-crud': {
        name: 'customer-api.xml',
        xml: '<?xml version="1.0" encoding="UTF-8"?>\n' +
'<mule xmlns="http://www.mulesoft.org/schema/mule/core"\n' +
'      xmlns:http="http://www.mulesoft.org/schema/mule/http"\n' +
'      xmlns:apikit="http://www.mulesoft.org/schema/mule/mule-apikit"\n' +
'      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core"\n' +
'      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n' +
'      xsi:schemaLocation="http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/mule-apikit http://www.mulesoft.org/schema/mule/mule-apikit/current/mule-apikit.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd">\n' +
'\n' +
'    <http:listener-config name="httpListenerConfig">\n' +
'        <http:listener-connection host="0.0.0.0" port="8081"/>\n' +
'    </http:listener-config>\n' +
'\n' +
'    <apikit:config name="api-config" raml="api/customer-api.raml" outboundHeadersMapName="outboundHeaders"/>\n' +
'\n' +
'    <flow name="api-main">\n' +
'        <http:listener config-ref="httpListenerConfig" path="/api/v1/*"/>\n' +
'        <apikit:router config-ref="api-config"/>\n' +
'        <error-handler>\n' +
'            <on-error-propagate type="APIKIT:BAD_REQUEST">\n' +
'                <set-payload value=\'#[output application/json --- { "error": "Bad Request", "message": error.description }]\'/>\n' +
'            </on-error-propagate>\n' +
'            <on-error-propagate type="APIKIT:NOT_FOUND">\n' +
'                <set-payload value=\'#[output application/json --- { "error": "Not Found" }]\'/>\n' +
'            </on-error-propagate>\n' +
'        </error-handler>\n' +
'    </flow>\n' +
'\n' +
'    <flow name="get:\\customers:api-config">\n' +
'        <logger level="INFO" message="GET /customers — listing all customers"/>\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-payload><![CDATA[%dw 2.0\n' +
'output application/json\n' +
'---\n' +
'[\n' +
'  { "id": 1, "name": "Acme Corp", "email": "contact@acme.com", "status": "active" },\n' +
'  { "id": 2, "name": "Globex Inc", "email": "info@globex.com", "status": "active" }\n' +
']]]></ee:set-payload>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'    </flow>\n' +
'\n' +
'    <flow name="get:\\customers\\(customerId):api-config">\n' +
'        <logger level="INFO" message="GET /customers/#[attributes.uriParams.customerId]"/>\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-payload><![CDATA[%dw 2.0\n' +
'output application/json\n' +
'---\n' +
'{ "id": attributes.uriParams.customerId, "name": "Acme Corp", "email": "contact@acme.com" }]]></ee:set-payload>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'    </flow>\n' +
'\n' +
'    <flow name="post:\\customers:application\\json:api-config">\n' +
'        <logger level="INFO" message="POST /customers — creating customer"/>\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-payload><![CDATA[%dw 2.0\n' +
'output application/json\n' +
'---\n' +
'payload ++ { "id": randomInt(10000), "createdAt": now() }]]></ee:set-payload>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'    </flow>\n' +
'\n' +
'    <flow name="put:\\customers\\(customerId):application\\json:api-config">\n' +
'        <logger level="INFO" message="PUT /customers/#[attributes.uriParams.customerId]"/>\n' +
'        <set-payload value=\'#[output application/json --- payload ++ { "updatedAt": now() }]\'/>\n' +
'    </flow>\n' +
'\n' +
'    <flow name="delete:\\customers\\(customerId):api-config">\n' +
'        <logger level="INFO" message="DELETE /customers/#[attributes.uriParams.customerId]"/>\n' +
'        <set-payload value=\'#[output application/json --- { "deleted": true }]\'/>\n' +
'    </flow>\n' +
'</mule>'
    },

    'db-operations': {
        name: 'database-service.xml',
        xml: '<?xml version="1.0" encoding="UTF-8"?>\n' +
'<mule xmlns="http://www.mulesoft.org/schema/mule/core"\n' +
'      xmlns:http="http://www.mulesoft.org/schema/mule/http"\n' +
'      xmlns:db="http://www.mulesoft.org/schema/mule/db"\n' +
'      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core"\n' +
'      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n' +
'      xsi:schemaLocation="http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/db http://www.mulesoft.org/schema/mule/db/current/mule-db.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd">\n' +
'\n' +
'    <http:listener-config name="HTTP_Listener_config">\n' +
'        <http:listener-connection host="0.0.0.0" port="8081"/>\n' +
'    </http:listener-config>\n' +
'\n' +
'    <db:config name="MySQL_Database_Config">\n' +
'        <db:my-sql-connection host="${db.host}" port="3306" user="${db.user}" password="${db.password}" database="${db.name}"/>\n' +
'    </db:config>\n' +
'\n' +
'    <flow name="getOrdersFlow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/api/orders" allowedMethods="GET"/>\n' +
'        <db:select config-ref="MySQL_Database_Config">\n' +
'            <db:sql>SELECT o.id, o.order_date, o.total_amount, o.status, c.name as customer_name FROM orders o JOIN customers c ON o.customer_id = c.id WHERE o.status = :status ORDER BY o.order_date DESC LIMIT 100</db:sql>\n' +
'            <db:input-parameters>#[{ "status": attributes.queryParams.status default "active" }]</db:input-parameters>\n' +
'        </db:select>\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-payload><![CDATA[%dw 2.0\n' +
'output application/json\n' +
'---\n' +
'payload map (order) -> {\n' +
'    id: order.id,\n' +
'    orderDate: order.order_date as String { format: "yyyy-MM-dd" },\n' +
'    totalAmount: order.total_amount as Number { format: "#,##0.00" },\n' +
'    status: order.status,\n' +
'    customerName: order.customer_name\n' +
'}]]></ee:set-payload>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'    </flow>\n' +
'\n' +
'    <flow name="createOrderFlow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/api/orders" allowedMethods="POST"/>\n' +
'        <logger level="INFO" message="Creating order for customer #[payload.customerId]"/>\n' +
'        <db:insert config-ref="MySQL_Database_Config">\n' +
'            <db:sql>INSERT INTO orders (customer_id, order_date, total_amount, status) VALUES (:customerId, NOW(), :totalAmount, \'pending\')</db:sql>\n' +
'            <db:input-parameters>#[{ "customerId": payload.customerId, "totalAmount": payload.totalAmount }]</db:input-parameters>\n' +
'        </db:insert>\n' +
'        <set-payload value=\'#[output application/json --- { "success": true, "orderId": payload.generatedKeys.GENERATED_KEY }]\'/>\n' +
'    </flow>\n' +
'\n' +
'    <flow name="updateOrderStatusFlow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/api/orders/{orderId}/status" allowedMethods="PUT"/>\n' +
'        <db:update config-ref="MySQL_Database_Config">\n' +
'            <db:sql>UPDATE orders SET status = :status, updated_at = NOW() WHERE id = :orderId</db:sql>\n' +
'            <db:input-parameters>#[{ "orderId": attributes.uriParams.orderId, "status": payload.status }]</db:input-parameters>\n' +
'        </db:update>\n' +
'        <choice>\n' +
'            <when expression="#[payload.affectedRows > 0]">\n' +
'                <set-payload value=\'#[output application/json --- { "success": true, "message": "Order status updated" }]\'/>\n' +
'            </when>\n' +
'            <otherwise>\n' +
'                <set-payload value=\'#[output application/json --- { "success": false, "message": "Order not found" }]\'/>\n' +
'            </otherwise>\n' +
'        </choice>\n' +
'    </flow>\n' +
'</mule>'
    },

    'salesforce-sync': {
        name: 'salesforce-account-sync.xml',
        xml: '<?xml version="1.0" encoding="UTF-8"?>\n' +
'<mule xmlns="http://www.mulesoft.org/schema/mule/core"\n' +
'      xmlns:http="http://www.mulesoft.org/schema/mule/http"\n' +
'      xmlns:salesforce="http://www.mulesoft.org/schema/mule/salesforce"\n' +
'      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core"\n' +
'      xmlns:batch="http://www.mulesoft.org/schema/mule/batch"\n' +
'      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n' +
'      xsi:schemaLocation="http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/salesforce http://www.mulesoft.org/schema/mule/salesforce/current/mule-salesforce.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/batch http://www.mulesoft.org/schema/mule/batch/current/mule-batch.xsd">\n' +
'\n' +
'    <http:listener-config name="HTTP_Listener_config">\n' +
'        <http:listener-connection host="0.0.0.0" port="8081"/>\n' +
'    </http:listener-config>\n' +
'\n' +
'    <salesforce:sfdc-config name="Salesforce_Config">\n' +
'        <salesforce:basic-connection username="${sf.username}" password="${sf.password}" securityToken="${sf.token}"/>\n' +
'    </salesforce:sfdc-config>\n' +
'\n' +
'    <flow name="syncAccountsFlow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/api/sync/accounts" allowedMethods="POST"/>\n' +
'        <logger level="INFO" message="Starting Salesforce account sync"/>\n' +
'        <salesforce:query config-ref="Salesforce_Config">\n' +
'            <salesforce:salesforce-query>SELECT Id, Name, Industry, AnnualRevenue, BillingCity, BillingState, Phone, Website, CreatedDate FROM Account WHERE LastModifiedDate > :lastSync</salesforce:salesforce-query>\n' +
'            <salesforce:parameters>#[{ "lastSync": payload.lastSyncDate default (now() - |P1D|) }]</salesforce:parameters>\n' +
'        </salesforce:query>\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-payload><![CDATA[%dw 2.0\n' +
'output application/json\n' +
'---\n' +
'payload map (account) -> {\n' +
'    sfId: account.Id,\n' +
'    name: account.Name,\n' +
'    industry: account.Industry default "Unknown",\n' +
'    revenue: account.AnnualRevenue default 0,\n' +
'    city: account.BillingCity,\n' +
'    state: account.BillingState,\n' +
'    phone: account.Phone,\n' +
'    website: account.Website,\n' +
'    syncedAt: now()\n' +
'}]]></ee:set-payload>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'        <logger level="INFO" message="Synced #[sizeOf(payload)] accounts from Salesforce"/>\n' +
'    </flow>\n' +
'\n' +
'    <flow name="createSalesforceAccountFlow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/api/accounts" allowedMethods="POST"/>\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-payload><![CDATA[%dw 2.0\n' +
'output application/java\n' +
'---\n' +
'[{\n' +
'    Name: payload.name,\n' +
'    Industry: payload.industry,\n' +
'    Phone: payload.phone,\n' +
'    Website: payload.website,\n' +
'    BillingCity: payload.city,\n' +
'    BillingState: payload.state\n' +
'}]]]></ee:set-payload>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'        <salesforce:create config-ref="Salesforce_Config" type="Account"/>\n' +
'        <set-payload value=\'#[output application/json --- { "success": true, "salesforceId": payload[0].id }]\'/>\n' +
'        <error-handler>\n' +
'            <on-error-propagate type="SALESFORCE:CONNECTIVITY">\n' +
'                <logger level="ERROR" message="Salesforce connection error: #[error.description]"/>\n' +
'                <set-payload value=\'#[output application/json --- { "error": "Salesforce connectivity issue", "details": error.description }]\'/>\n' +
'            </on-error-propagate>\n' +
'        </error-handler>\n' +
'    </flow>\n' +
'</mule>'
    },

    'file-processing': {
        name: 'csv-batch-processor.xml',
        xml: '<?xml version="1.0" encoding="UTF-8"?>\n' +
'<mule xmlns="http://www.mulesoft.org/schema/mule/core"\n' +
'      xmlns:http="http://www.mulesoft.org/schema/mule/http"\n' +
'      xmlns:file="http://www.mulesoft.org/schema/mule/file"\n' +
'      xmlns:ftp="http://www.mulesoft.org/schema/mule/ftp"\n' +
'      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core"\n' +
'      xmlns:batch="http://www.mulesoft.org/schema/mule/batch"\n' +
'      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n' +
'      xsi:schemaLocation="http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/file http://www.mulesoft.org/schema/mule/file/current/mule-file.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/ftp http://www.mulesoft.org/schema/mule/ftp/current/mule-ftp.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/batch http://www.mulesoft.org/schema/mule/batch/current/mule-batch.xsd">\n' +
'\n' +
'    <http:listener-config name="HTTP_Listener_config">\n' +
'        <http:listener-connection host="0.0.0.0" port="8081"/>\n' +
'    </http:listener-config>\n' +
'\n' +
'    <file:config name="File_Config">\n' +
'        <file:connection workingDir="${file.input.dir}"/>\n' +
'    </file:config>\n' +
'\n' +
'    <ftp:config name="FTP_Config">\n' +
'        <ftp:connection host="${ftp.host}" port="21" username="${ftp.user}" password="${ftp.password}"/>\n' +
'    </ftp:config>\n' +
'\n' +
'    <flow name="csvFilePollerFlow">\n' +
'        <file:listener config-ref="File_Config" directory="input" autoDelete="true" recursive="false">\n' +
'            <scheduling-strategy>\n' +
'                <fixed-frequency frequency="30" timeUnit="SECONDS"/>\n' +
'            </scheduling-strategy>\n' +
'            <file:matcher filenamePattern="*.csv"/>\n' +
'        </file:listener>\n' +
'        <logger level="INFO" message="Processing CSV file: #[attributes.fileName]"/>\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-payload><![CDATA[%dw 2.0\n' +
'output application/json\n' +
'---\n' +
'payload map (row, index) -> {\n' +
'    lineNumber: index + 1,\n' +
'    firstName: trim(row.first_name),\n' +
'    lastName: trim(row.last_name),\n' +
'    email: lower(trim(row.email)),\n' +
'    amount: row.amount as Number { format: "#,##0.00" },\n' +
'    date: row.transaction_date as Date { format: "MM/dd/yyyy" } as String { format: "yyyy-MM-dd" },\n' +
'    valid: not isEmpty(row.email) and (row.amount as Number > 0)\n' +
'}]]></ee:set-payload>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'        <set-variable variableName="processedCount" value="#[sizeOf(payload)]"/>\n' +
'        <foreach>\n' +
'            <choice>\n' +
'                <when expression="#[payload.valid]">\n' +
'                    <logger level="DEBUG" message="Valid record: #[payload.email]"/>\n' +
'                </when>\n' +
'                <otherwise>\n' +
'                    <logger level="WARN" message="Invalid record at line #[payload.lineNumber]"/>\n' +
'                </otherwise>\n' +
'            </choice>\n' +
'        </foreach>\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-payload><![CDATA[%dw 2.0\n' +
'output application/csv\n' +
'---\n' +
'payload filter (item) -> item.valid]]></ee:set-payload>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'        <ftp:write config-ref="FTP_Config" path=\'#["output/" ++ attributes.fileName]\'/>  \n' +
'        <logger level="INFO" message="Uploaded #[vars.processedCount] records to FTP"/>\n' +
'    </flow>\n' +
'\n' +
'    <flow name="manualUploadFlow">\n' +
'        <http:listener config-ref="HTTP_Listener_config" path="/api/upload/csv" allowedMethods="POST"/>\n' +
'        <file:write config-ref="File_Config" path=\'#["input/upload-" ++ now() as String { format: "yyyyMMddHHmmss" } ++ ".csv"]\'/>  \n' +
'        <set-payload value=\'#[output application/json --- { "success": true, "message": "File queued for processing" }]\'/>\n' +
'    </flow>\n' +
'</mule>'
    },

    'api-proxy': {
        name: 'api-gateway-proxy.xml',
        xml: '<?xml version="1.0" encoding="UTF-8"?>\n' +
'<mule xmlns="http://www.mulesoft.org/schema/mule/core"\n' +
'      xmlns:http="http://www.mulesoft.org/schema/mule/http"\n' +
'      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core"\n' +
'      xmlns:os="http://www.mulesoft.org/schema/mule/os"\n' +
'      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\n' +
'      xsi:schemaLocation="http://www.mulesoft.org/schema/mule/core http://www.mulesoft.org/schema/mule/core/current/mule.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/http http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/ee/core http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd\n' +
'                          http://www.mulesoft.org/schema/mule/os http://www.mulesoft.org/schema/mule/os/current/mule-os.xsd">\n' +
'\n' +
'    <http:listener-config name="proxyListenerConfig">\n' +
'        <http:listener-connection host="0.0.0.0" port="8081"/>\n' +
'    </http:listener-config>\n' +
'\n' +
'    <http:request-config name="backendRequestConfig">\n' +
'        <http:request-connection host="${backend.host}" port="${backend.port}" protocol="HTTPS">\n' +
'            <http:authentication>\n' +
'                <http:basic-authentication username="${backend.user}" password="${backend.password}"/>\n' +
'            </http:authentication>\n' +
'        </http:request-connection>\n' +
'    </http:request-config>\n' +
'\n' +
'    <os:object-store name="rateLimitStore" entryTtl="60" entryTtlUnit="SECONDS" maxEntries="10000"/>\n' +
'\n' +
'    <flow name="apiProxyMainFlow">\n' +
'        <http:listener config-ref="proxyListenerConfig" path="/gateway/*"/>\n' +
'        <logger level="INFO" message="Proxy request: #[attributes.method] #[attributes.requestPath] from #[attributes.remoteAddress]"/>\n' +
'        <!-- CORS Headers -->\n' +
'        <set-variable variableName="origin" value="#[attributes.headers.origin default \'*\']"/>\n' +
'        <!-- Rate Limiting -->\n' +
'        <os:retrieve key="#[attributes.remoteAddress]" objectStore="rateLimitStore" target="requestCount">\n' +
'            <os:default-value>0</os:default-value>\n' +
'        </os:retrieve>\n' +
'        <choice>\n' +
'            <when expression="#[vars.requestCount as Number > 100]">\n' +
'                <logger level="WARN" message="Rate limit exceeded for #[attributes.remoteAddress]"/>\n' +
'                <set-payload value=\'#[output application/json --- { "error": "Rate limit exceeded", "retryAfter": 60 }]\'/>\n' +
'                <raise-error type="APP:RATE_LIMIT"/>\n' +
'            </when>\n' +
'        </choice>\n' +
'        <os:store key="#[attributes.remoteAddress]" objectStore="rateLimitStore">\n' +
'            <os:value>#[(vars.requestCount as Number) + 1]</os:value>\n' +
'        </os:store>\n' +
'        <!-- Forward to Backend -->\n' +
'        <http:request config-ref="backendRequestConfig" method="#[attributes.method]" path="#[attributes.requestPath replace \'/gateway\' with \'\']">\n' +
'            <http:headers>#[{\n' +
'                "X-Forwarded-For": attributes.remoteAddress,\n' +
'                "X-Request-Id": uuid(),\n' +
'                "Authorization": attributes.headers.authorization default ""\n' +
'            }]</http:headers>\n' +
'            <http:query-params>#[attributes.queryParams]</http:query-params>\n' +
'        </http:request>\n' +
'        <!-- Add CORS response headers -->\n' +
'        <ee:transform>\n' +
'            <ee:message>\n' +
'                <ee:set-attributes><![CDATA[%dw 2.0\n' +
'output application/java\n' +
'---\n' +
'attributes ++ {\n' +
'    headers: attributes.headers ++ {\n' +
'        "Access-Control-Allow-Origin": vars.origin,\n' +
'        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",\n' +
'        "Access-Control-Allow-Headers": "Content-Type, Authorization",\n' +
'        "X-Proxy-By": "MuleSoft Gateway"\n' +
'    }\n' +
'}]]></ee:set-attributes>\n' +
'            </ee:message>\n' +
'        </ee:transform>\n' +
'        <error-handler>\n' +
'            <on-error-propagate type="HTTP:CONNECTIVITY">\n' +
'                <logger level="ERROR" message="Backend unreachable: #[error.description]"/>\n' +
'                <set-payload value=\'#[output application/json --- { "error": "Service Unavailable", "message": "Backend service is not responding" }]\'/>\n' +
'            </on-error-propagate>\n' +
'            <on-error-propagate type="HTTP:TIMEOUT">\n' +
'                <set-payload value=\'#[output application/json --- { "error": "Gateway Timeout", "message": "Backend did not respond in time" }]\'/>\n' +
'            </on-error-propagate>\n' +
'            <on-error-propagate type="APP:RATE_LIMIT">\n' +
'                <set-payload value=\'#[output application/json --- { "error": "Too Many Requests", "retryAfter": 60 }]\'/>\n' +
'            </on-error-propagate>\n' +
'        </error-handler>\n' +
'    </flow>\n' +
'</mule>'
    }
};

function toggleSampleMenu(event) {
    event.stopPropagation();
    var menu = document.getElementById('sampleMenu');
    menu.classList.toggle('open');
}

function loadSample(key) {
    var sample = MULE_SAMPLES[key];
    if (!sample) return;
    var editor = document.getElementById('muleXmlEditor');
    editor.value = sample.xml;
    updateEditorInfo();
    // Add to uploaded files list
    uploadedXmlFiles = [{ name: sample.name, content: sample.xml }];
    renderUploadedFiles();
    // Close menu
    document.getElementById('sampleMenu').classList.remove('open');
    setStatus('Loaded sample: ' + sample.name);
}

// Close sample menu on outside click
document.addEventListener('click', function(e) {
    var menu = document.getElementById('sampleMenu');
    if (menu && !e.target.closest('.sample-dropdown')) {
        menu.classList.remove('open');
    }
});

// ── Initialize ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    var editor = document.getElementById('muleXmlEditor');
    if (editor) {
        editor.addEventListener('input', updateEditorInfo);
        editor.addEventListener('focus', updateEditorInfo);
    }
    document.getElementById('dwEditor').addEventListener('blur', function() {
        if (activeDwScript) dwScripts[activeDwScript] = this.value;
    });
    ['llmProvider', 'llmModel', 'llmApiKey', 'llmBaseUrl'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.addEventListener('change', saveLLMSettings);
    });

    loadLLMProviders();
    initResizablePanels();

    // Restore from cross-page store if available
    var stored = MigrationStore.load();
    if (stored && stored.files) {
        migrationResult = stored;
        renderFileTree(stored.files);
        if (stored.summary) renderSummary(stored.summary);
        if (stored.llmValidation) {
            renderValidationResults(stored.llmValidation);
            document.getElementById('validationTabBtn').style.display = '';
            document.getElementById('revalidateBtn').style.display = '';
        }
        document.getElementById('downloadBtn').disabled = false;
        setStatus('Previous migration restored — ' + Object.keys(stored.files).length + ' files');
    } else {
        setStatus('Ready — Paste MuleSoft XML (Ctrl+Enter to migrate)');
    }

});
