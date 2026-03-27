// ═══════════════════════════════════════════════════════════════
// Base JS — Shared across all pages
// Toast, modal, MigrationStore, sidebar, utilities
// ═══════════════════════════════════════════════════════════════

// ── Toast Notification System ──────────────────────────────────
function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;
    var container = document.getElementById('toastContainer');
    if (!container) return;
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    var icons = { success: '&#10004;', error: '&#10060;', warning: '&#9888;', info: '&#8505;' };
    toast.innerHTML =
        '<span class="toast-icon">' + (icons[type] || icons.info) + '</span>' +
        '<span class="toast-body">' + message + '</span>' +
        '<button class="toast-close" onclick="dismissToast(this.parentElement)">&times;</button>' +
        '<div class="toast-progress"></div>';
    container.appendChild(toast);
    requestAnimationFrame(function () {
        requestAnimationFrame(function () { toast.classList.add('show'); });
    });
    var progress = toast.querySelector('.toast-progress');
    progress.style.width = '100%';
    requestAnimationFrame(function () {
        progress.style.transitionDuration = duration + 'ms';
        progress.style.width = '0%';
    });
    var timer = setTimeout(function () { dismissToast(toast); }, duration);
    toast._timer = timer;
    toast.addEventListener('mouseenter', function () {
        clearTimeout(toast._timer);
        toast.querySelector('.toast-progress').style.transitionDuration = '0ms';
    });
    toast.addEventListener('mouseleave', function () {
        toast._timer = setTimeout(function () { dismissToast(toast); }, 2000);
        var p = toast.querySelector('.toast-progress');
        p.style.transitionDuration = '2000ms';
        p.style.width = '0%';
    });
    return toast;
}

function dismissToast(toast) {
    if (!toast || !toast.parentElement) return;
    toast.classList.remove('show');
    toast.classList.add('hiding');
    setTimeout(function () {
        if (toast.parentElement) toast.parentElement.removeChild(toast);
    }, 350);
}

// ── Modal System ───────────────────────────────────────────────
function showModal(title, bodyHtml, footerHtml) {
    var overlay = document.getElementById('modalOverlay');
    if (!overlay) return;
    overlay.querySelector('.modal-title').textContent = title;
    overlay.querySelector('.modal-body').innerHTML = bodyHtml;
    var footer = overlay.querySelector('.modal-footer');
    if (footerHtml) {
        footer.innerHTML = footerHtml;
        footer.style.display = '';
    } else {
        footer.style.display = 'none';
    }
    overlay.classList.add('show');
}

function closeModal() {
    var overlay = document.getElementById('modalOverlay');
    if (overlay) overlay.classList.remove('show');
}

// ── MigrationStore (Cross-Page State via localStorage) ─────────
var MigrationStore = {
    _key: 'msb_migration_result',
    save: function (result) {
        try {
            localStorage.setItem(this._key, JSON.stringify(result));
        } catch (e) {
            console.warn('MigrationStore: failed to save', e);
        }
    },
    load: function () {
        try {
            return JSON.parse(localStorage.getItem(this._key) || 'null');
        } catch (e) {
            return null;
        }
    },
    getFiles: function () {
        var r = this.load();
        return r ? r.files : null;
    },
    getSummary: function () {
        var r = this.load();
        return r ? r.summary : null;
    },
    getValidation: function () {
        var r = this.load();
        return r ? r.llmValidation : null;
    },
    clear: function () {
        localStorage.removeItem(this._key);
    },
    hasMigration: function () {
        return !!this.load();
    }
};

// ── Settings Store ─────────────────────────────────────────────
var SettingsStore = {
    get: function (key, fallback) {
        var val = localStorage.getItem('msb_' + key);
        return val !== null ? val : (fallback || '');
    },
    set: function (key, val) {
        localStorage.setItem('msb_' + key, val);
    },
    getJSON: function (key, fallback) {
        try {
            return JSON.parse(localStorage.getItem('msb_' + key)) || fallback;
        } catch (e) {
            return fallback;
        }
    },
    setJSON: function (key, val) {
        localStorage.setItem('msb_' + key, JSON.stringify(val));
    },
    remove: function (key) {
        localStorage.removeItem('msb_' + key);
    }
};

// ── Sidebar Toggle ─────────────────────────────────────────────
function toggleSidebar() {
    document.body.classList.toggle('sidebar-collapsed');
    SettingsStore.set('sidebar_collapsed', document.body.classList.contains('sidebar-collapsed') ? '1' : '0');
}

function initSidebar() {
    if (SettingsStore.get('sidebar_collapsed') === '1') {
        document.body.classList.add('sidebar-collapsed');
    }
    // Highlight active nav item
    var path = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(function (item) {
        var href = item.getAttribute('href');
        if (href === path || (href !== '/' && path.startsWith(href))) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

// ── Utility Functions ──────────────────────────────────────────
function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
}

function setStatus(text) {
    var el = document.querySelector('.status-bar .status-text');
    if (el) el.innerHTML = '<span class="status-dot"></span> ' + escapeHtml(text);
}

function showLoading(text) {
    var overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        var p = overlay.querySelector('p');
        if (p && text) p.textContent = text;
        overlay.classList.add('show');
    }
}

function hideLoading() {
    var overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.remove('show');
}

function copyToClipboard(text, label) {
    navigator.clipboard.writeText(text).then(function () {
        showToast((label || 'Content') + ' copied to clipboard', 'success', 2000);
    }).catch(function () {
        showToast('Failed to copy', 'error');
    });
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    var k = 1024;
    var sizes = ['B', 'KB', 'MB', 'GB'];
    var i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function debounce(fn, ms) {
    var timer;
    return function () {
        var args = arguments;
        var ctx = this;
        clearTimeout(timer);
        timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
}

// ── API Helper ─────────────────────────────────────────────────
function apiCall(url, options) {
    options = options || {};
    var method = options.method || 'GET';
    var body = options.body;
    var headers = options.headers || {};
    if (body && typeof body === 'object') {
        headers['Content-Type'] = 'application/json';
        body = JSON.stringify(body);
    }
    return fetch(url, {
        method: method,
        headers: headers,
        body: body
    }).then(function (res) {
        if (!res.ok) {
            return res.json().then(function (data) {
                throw new Error(data.error || 'Request failed with status ' + res.status);
            });
        }
        return res.json();
    });
}

// ── SSE Helper ─────────────────────────────────────────────────
function connectSSE(url, callbacks) {
    var es = new EventSource(url);
    es.onmessage = function (event) {
        try {
            var data = JSON.parse(event.data);
            if (callbacks.onMessage) callbacks.onMessage(data);
            if (data.status && callbacks.onStatus) callbacks.onStatus(data.status);
        } catch (e) {
            if (callbacks.onMessage) callbacks.onMessage({ line: event.data });
        }
    };
    es.onerror = function () {
        es.close();
        if (callbacks.onError) callbacks.onError();
    };
    return es;
}

// ── GitHub Token Helper ────────────────────────────────────────
function getGitHubToken() {
    return SettingsStore.get('github_token', '');
}

function setGitHubToken(token) {
    SettingsStore.set('github_token', token);
}

// ── LLM Config Helper ─────────────────────────────────────────
function getLLMConfig() {
    return SettingsStore.getJSON('llm_config', {
        enabled: false,
        provider: '',
        model: '',
        apiKey: '',
        baseUrl: ''
    });
}

function setLLMConfig(config) {
    SettingsStore.setJSON('llm_config', config);
}

// ── Initialize on DOM Ready ────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initSidebar();

    // Close modal on overlay click
    var modalOverlay = document.getElementById('modalOverlay');
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function (e) {
            if (e.target === modalOverlay) closeModal();
        });
    }

    // Close modal on Escape
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') closeModal();
    });

    // Mobile menu
    var mobileBtn = document.querySelector('.mobile-menu-btn');
    if (mobileBtn) {
        mobileBtn.addEventListener('click', function () {
            document.querySelector('.sidebar').classList.toggle('mobile-open');
        });
    }
});
