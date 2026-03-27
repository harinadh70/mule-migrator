// ===================================================================
// Settings page -- save/restore from localStorage via SettingsStore
// ===================================================================

var llmProvidersList = [];
var llmProvidersMap = {};
var _hasUnsavedChanges = false;

// ── Eye icon SVGs ────────────────────────────────────────────────
var EYE_OPEN_SVG = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
var EYE_CLOSED_SVG = '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>';

// ── Scroll-spy navigation ────────────────────────────────────────

function scrollToSection(sectionId, linkEl) {
    var section = document.getElementById(sectionId);
    if (!section) return;
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });

    document.querySelectorAll('.settings-nav-item').forEach(function (item) {
        item.classList.remove('active');
    });
    if (linkEl) linkEl.classList.add('active');
}

function initScrollSpy() {
    var content = document.getElementById('settingsContent');
    if (!content) return;
    content.addEventListener('scroll', function () {
        var sections = content.querySelectorAll('.settings-section');
        var scrollTop = content.scrollTop + 80;
        var active = null;
        sections.forEach(function (s) {
            if (s.offsetTop <= scrollTop) active = s;
        });
        if (!active) return;
        document.querySelectorAll('.settings-nav-item').forEach(function (item) {
            var href = item.getAttribute('href');
            if (href && href === '#' + active.id) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    });
}

// ── Load providers from API ──────────────────────────────────────

function loadProviders() {
    apiCall('/api/llm/providers')
        .then(function (data) {
            llmProvidersList = data.providers || [];
            llmProvidersMap = {};
            llmProvidersList.forEach(function (p) {
                llmProvidersMap[p.id] = p;
            });
            buildProviderSelect();
            loadSettings();
        })
        .catch(function () {
            llmProvidersList = [];
            llmProvidersMap = {};
            buildProviderSelect();
            loadSettings();
        });
}

function buildProviderSelect() {
    var select = document.getElementById('llmProvider');
    if (!select) return;
    select.innerHTML = '<option value="">Select a provider...</option>';
    llmProvidersList.forEach(function (p) {
        var opt = document.createElement('option');
        opt.value = p.id;
        opt.textContent = p.name;
        select.appendChild(opt);
    });
}

// ── Provider / model change handlers ─────────────────────────────

function onProviderChange() {
    var providerId = document.getElementById('llmProvider').value;
    var modelSelect = document.getElementById('llmModel');
    var providerInfo = document.getElementById('llmProviderInfo');
    var modelInfo = document.getElementById('llmModelInfo');
    var docsLink = document.getElementById('llmDocsLink');

    modelSelect.innerHTML = '<option value="">Select a model...</option>';
    if (providerInfo) providerInfo.textContent = '\u00a0';
    if (modelInfo) modelInfo.textContent = '\u00a0';
    if (docsLink) docsLink.innerHTML = '\u00a0';

    if (!providerId || !llmProvidersMap[providerId]) {
        document.getElementById('llmApiKeyGroup').style.display = '';
        document.getElementById('llmBaseUrlGroup').style.display = 'none';
        onLLMFieldChange();
        return;
    }

    var provider = llmProvidersMap[providerId];

    // Populate models
    (provider.models || []).forEach(function (m) {
        var opt = document.createElement('option');
        opt.value = m.id;
        opt.textContent = m.name;
        modelSelect.appendChild(opt);
    });
    if (provider.models && provider.models.length > 0) {
        modelSelect.value = provider.models[0].id;
    }

    // Provider hint
    if (providerInfo) {
        var count = provider.models ? provider.models.length : 0;
        providerInfo.textContent = count + ' model' + (count !== 1 ? 's' : '') + ' available';
    }

    // Docs link
    if (docsLink) {
        var url = provider.docsUrl || provider.docs_url || '';
        if (url) {
            docsLink.innerHTML = 'Get your API key at <a href="' + escapeHtml(url) +
                '" target="_blank" rel="noopener">' + escapeHtml(url) + '</a>';
        }
    }

    // Show/hide base URL vs API key based on provider
    if (providerId === 'ollama') {
        document.getElementById('llmApiKeyGroup').style.display = 'none';
        document.getElementById('llmBaseUrlGroup').style.display = '';
    } else {
        document.getElementById('llmApiKeyGroup').style.display = '';
        document.getElementById('llmBaseUrlGroup').style.display = 'none';
    }

    onModelChange();
    onLLMFieldChange();
}

function onModelChange() {
    var modelInfo = document.getElementById('llmModelInfo');
    if (!modelInfo) return;

    var providerId = document.getElementById('llmProvider').value;
    var modelId = document.getElementById('llmModel').value;

    if (!providerId || !llmProvidersMap[providerId] || !modelId) {
        modelInfo.textContent = '\u00a0';
        return;
    }

    var models = llmProvidersMap[providerId].models || [];
    var found = null;
    for (var i = 0; i < models.length; i++) {
        if (models[i].id === modelId) {
            found = models[i];
            break;
        }
    }

    if (found && found.tier) {
        modelInfo.textContent = found.tier.charAt(0).toUpperCase() + found.tier.slice(1) + ' tier';
    } else if (found && found.name) {
        modelInfo.textContent = found.name;
    } else {
        modelInfo.textContent = '\u00a0';
    }

    onLLMFieldChange();
}

// ── Toggle handlers ──────────────────────────────────────────────

function onLLMToggle() {
    var enabled = document.getElementById('llmEnabled').checked;
    var body = document.getElementById('llmSettingsBody');
    if (body) body.classList.toggle('disabled', !enabled);
    onLLMFieldChange();
}

function toggleApiKeyVisibility() {
    var input = document.getElementById('llmApiKey');
    var icon = document.getElementById('eyeIcon');
    if (!input) return;
    var isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    if (icon) icon.innerHTML = isPassword ? EYE_CLOSED_SVG : EYE_OPEN_SVG;
}

function toggleGithubTokenVisibility() {
    var input = document.getElementById('githubToken');
    var icon = document.getElementById('githubEyeIcon');
    if (!input) return;
    var isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    if (icon) icon.innerHTML = isPassword ? EYE_CLOSED_SVG : EYE_OPEN_SVG;
}

// ── LLM field change handler ─────────────────────────────────────

function onLLMFieldChange() {
    _hasUnsavedChanges = true;
    var result = document.getElementById('testResult');
    if (result) {
        result.textContent = '';
        result.className = 'test-result';
    }
}

// ── Test Connection ──────────────────────────────────────────────

function testConnection() {
    var btn = document.getElementById('testConnectionBtn');
    var resultEl = document.getElementById('testResult');

    var provider = document.getElementById('llmProvider').value;
    var model = document.getElementById('llmModel').value;
    var apiKey = document.getElementById('llmApiKey').value;
    var baseUrl = document.getElementById('llmBaseUrl').value;
    var enabled = document.getElementById('llmEnabled').checked;

    if (!enabled) {
        showToast('Enable LLM integration first', 'warning', 3000);
        return;
    }
    if (!provider) {
        showToast('Select a provider before testing', 'warning', 3000);
        return;
    }
    if (!model) {
        showToast('Select a model before testing', 'warning', 3000);
        return;
    }

    btn.disabled = true;
    btn.innerHTML =
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> Testing\u2026';
    resultEl.textContent = 'Connecting\u2026';
    resultEl.className = 'test-result testing';

    apiCall('/api/validate', {
        method: 'POST',
        body: {
            files: { 'Test.java': 'public class Test {}' },
            summary: { flowsConverted: 1 },
            llmConfig: {
                enabled: true,
                provider: provider,
                model: model,
                apiKey: apiKey,
                baseUrl: baseUrl
            }
        }
    })
    .then(function (data) {
        resultEl.textContent = 'Connected successfully';
        resultEl.className = 'test-result success';
        showToast('LLM connection verified', 'success', 3000);
    })
    .catch(function (err) {
        resultEl.textContent = 'Connection failed: ' + err.message;
        resultEl.className = 'test-result error';
        showToast('Connection failed: ' + err.message, 'error');
    })
    .finally(function () {
        btn.disabled = false;
        btn.innerHTML =
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg> Test Connection';
    });
}

// ── GitHub token helpers ─────────────────────────────────────────

function clearGithubToken() {
    var input = document.getElementById('githubToken');
    if (input) input.value = '';
    SettingsStore.remove('github_token');
    updateGithubStatus();
    showToast('GitHub token cleared', 'info', 2500);
}

function updateGithubStatus() {
    var statusEl = document.getElementById('githubTokenStatus');
    if (!statusEl) return;
    var input = document.getElementById('githubToken');
    var val = input ? input.value.trim() : '';
    if (val) {
        statusEl.textContent = 'Token saved (' + val.length + ' characters)';
        statusEl.className = 'token-status has-token';
    } else {
        statusEl.textContent = 'No token configured';
        statusEl.className = 'token-status';
    }
}

// ── Save all settings ────────────────────────────────────────────

function saveAllSettings() {
    // Project defaults
    var projectName = (document.getElementById('defaultProjectName').value || '').trim();
    var groupId = (document.getElementById('defaultGroupId').value || '').trim();
    var javaVersion = document.getElementById('defaultJavaVersion').value;
    var springBootVersion = document.getElementById('defaultSpringBootVersion').value;
    var packaging = document.getElementById('defaultPackaging').value;

    SettingsStore.set('project_name', projectName);
    SettingsStore.set('group_id', groupId);
    SettingsStore.set('java_version', javaVersion);
    SettingsStore.set('spring_boot_version', springBootVersion);
    SettingsStore.set('packaging', packaging);

    // LLM config
    var llmConfig = {
        enabled: document.getElementById('llmEnabled').checked,
        provider: document.getElementById('llmProvider').value,
        model: document.getElementById('llmModel').value,
        apiKey: document.getElementById('llmApiKey').value,
        baseUrl: document.getElementById('llmBaseUrl').value
    };
    setLLMConfig(llmConfig);

    // GitHub token
    var githubToken = (document.getElementById('githubToken').value || '').trim();
    setGitHubToken(githubToken);

    updateGithubStatus();
    _hasUnsavedChanges = false;
    showToast('Settings saved', 'success', 2500);
    setStatus('Settings saved');
}

// ── Load settings into form ──────────────────────────────────────

function loadSettings() {
    // Project defaults
    document.getElementById('defaultProjectName').value = SettingsStore.get('project_name', '');
    document.getElementById('defaultGroupId').value = SettingsStore.get('group_id', '');

    var javaSelect = document.getElementById('defaultJavaVersion');
    if (javaSelect) javaSelect.value = SettingsStore.get('java_version', '17');

    var sbSelect = document.getElementById('defaultSpringBootVersion');
    if (sbSelect) sbSelect.value = SettingsStore.get('spring_boot_version', '3.3.0');

    var packagingSelect = document.getElementById('defaultPackaging');
    if (packagingSelect) packagingSelect.value = SettingsStore.get('packaging', 'jar');

    // LLM config
    var llmConfig = getLLMConfig();
    var enabled = !!llmConfig.enabled;
    document.getElementById('llmEnabled').checked = enabled;
    document.getElementById('llmSettingsBody').classList.toggle('disabled', !enabled);

    if (llmConfig.provider) {
        var providerSelect = document.getElementById('llmProvider');
        if (providerSelect) {
            providerSelect.value = llmConfig.provider;
            onProviderChange();
            if (llmConfig.model) {
                document.getElementById('llmModel').value = llmConfig.model;
                onModelChange();
            }
        }
    }

    if (llmConfig.apiKey) {
        document.getElementById('llmApiKey').value = llmConfig.apiKey;
    }
    if (llmConfig.baseUrl) {
        document.getElementById('llmBaseUrl').value = llmConfig.baseUrl;
    }

    // GitHub token
    var tokenInput = document.getElementById('githubToken');
    if (tokenInput) {
        tokenInput.value = getGitHubToken();
    }
    updateGithubStatus();

    _hasUnsavedChanges = false;
}

// ── Reset to defaults ────────────────────────────────────────────

function resetAllSettings() {
    showModal(
        'Reset Settings',
        '<p style="color:var(--text-secondary);font-size:14px;line-height:1.6;">' +
        'This will clear all saved settings including your LLM API key and GitHub token. ' +
        'This action cannot be undone.</p>',
        '<button class="btn btn-ghost btn-sm" onclick="closeModal()">Cancel</button>' +
        '<button class="btn btn-danger btn-sm" onclick="doResetSettings()">Reset All Settings</button>'
    );
}

function doResetSettings() {
    var keys = [
        'project_name', 'group_id', 'java_version',
        'spring_boot_version', 'packaging',
        'llm_config', 'github_token'
    ];
    keys.forEach(function (k) { SettingsStore.remove(k); });

    closeModal();
    loadSettings();
    showToast('Settings reset to defaults', 'info', 3000);
    setStatus('Settings reset');
}

// ── Init ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    loadProviders();
    initScrollSpy();

    // Live update GitHub token status on input
    var tokenInput = document.getElementById('githubToken');
    if (tokenInput) {
        tokenInput.addEventListener('input', updateGithubStatus);
    }

    // Warn on unsaved changes before leaving
    window.addEventListener('beforeunload', function (e) {
        if (_hasUnsavedChanges) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    setStatus('Settings');
});
