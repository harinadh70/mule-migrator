// ═══════════════════════════════════════════════════════════════
// GitHub Integration — JS
// Connects, lists repos/orgs, creates repos, pushes files,
// creates branches.
// Depends on base.js: apiCall, showToast, escapeHtml,
//                     MigrationStore, SettingsStore
// ═══════════════════════════════════════════════════════════════

/* ── State ──────────────────────────────────────────────────── */
var GitHub = {
    connected: false,
    user: null,
    orgs: [],
    repos: [],
    filteredRepos: [],
    selectedRepo: null,   // { owner, name, full_name }
    branches: []
};

/* ── Token helpers ──────────────────────────────────────────── */
function getToken() {
    return SettingsStore.get('github_token', '');
}

function authHeaders() {
    return { 'X-GitHub-Token': getToken() };
}

/* ── Connect / Disconnect ───────────────────────────────────── */
function connectGitHub() {
    var token = document.getElementById('githubToken').value.trim();
    if (!token) {
        showToast('Please enter a Personal Access Token', 'warning');
        return;
    }

    var btn = document.getElementById('btnConnect');
    btn.disabled = true;
    btn.textContent = 'Connecting…';

    apiCall('/api/github/connect', {
        method: 'POST',
        headers: { 'X-GitHub-Token': token },
        body: { token: token }
    }).then(function (data) {
        SettingsStore.set('github_token', token);
        GitHub.connected = true;
        GitHub.user = data.user;
        renderConnectedUser(data.user);
        document.getElementById('btnRefresh').style.display = '';
        showToast('Connected as ' + data.user.login, 'success');
        loadOrgsAndRepos();
    }).catch(function (err) {
        showToast(err.message || 'Connection failed', 'error');
    }).finally(function () {
        btn.disabled = false;
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg> Connect';
    });
}

function disconnectGitHub() {
    SettingsStore.remove('github_token');
    GitHub.connected = false;
    GitHub.user = null;
    GitHub.repos = [];
    GitHub.filteredRepos = [];
    GitHub.orgs = [];
    GitHub.selectedRepo = null;

    document.getElementById('connectedUser').style.display = 'none';
    document.getElementById('connectForm').style.display = '';
    document.getElementById('githubToken').value = '';
    document.getElementById('githubColumns').style.display = 'none';
    document.getElementById('btnRefresh').style.display = 'none';
    renderRepoList([]);
    showToast('Disconnected from GitHub', 'info');
    setStatus('Disconnected from GitHub');
}

function renderConnectedUser(user) {
    document.getElementById('connectForm').style.display = 'none';
    var cu = document.getElementById('connectedUser');
    cu.style.display = 'flex';
    document.getElementById('userAvatar').src = user.avatar_url || '';
    document.getElementById('userAvatar').alt = user.login;
    document.getElementById('userName').textContent = user.name || user.login;
    document.getElementById('userLogin').textContent = '@' + user.login;
}

/* ── Orgs + Repos ───────────────────────────────────────────── */
function loadOrgsAndRepos() {
    document.getElementById('githubColumns').style.display = 'grid';
    renderRepoSkeletons();

    apiCall('/api/github/orgs', { headers: authHeaders() })
        .then(function (data) {
            GitHub.orgs = data.orgs || [];
            populateOrgDropdowns();
        })
        .catch(function () {
            /* orgs are optional — silently ignore */
        });

    fetchRepos('');
}

function populateOrgDropdowns() {
    var orgSel = document.getElementById('orgSelector');
    var newRepoOrgSel = document.getElementById('newRepoOrg');

    // preserve selection
    var currentOrg = orgSel.value;

    // clear & repopulate
    orgSel.innerHTML = '<option value="">Your repos</option>';
    newRepoOrgSel.innerHTML = '<option value="">Your account</option>';

    GitHub.orgs.forEach(function (org) {
        var o1 = document.createElement('option');
        o1.value = org.login;
        o1.textContent = org.login;
        orgSel.appendChild(o1);

        var o2 = document.createElement('option');
        o2.value = org.login;
        o2.textContent = org.login;
        newRepoOrgSel.appendChild(o2);
    });

    if (currentOrg) orgSel.value = currentOrg;
}

function onOrgChange() {
    var org = document.getElementById('orgSelector').value;
    fetchRepos(org);
}

function fetchRepos(org) {
    renderRepoSkeletons();
    var url = '/api/github/repos' + (org ? '?org=' + encodeURIComponent(org) : '');

    apiCall(url, { headers: authHeaders() })
        .then(function (data) {
            GitHub.repos = data.repos || [];
            GitHub.filteredRepos = GitHub.repos.slice();
            renderRepoList(GitHub.filteredRepos);
            updateRepoFooter();
        })
        .catch(function (err) {
            showToast('Failed to load repositories: ' + err.message, 'error');
            renderRepoList([]);
        });
}

function refreshRepos() {
    if (!GitHub.connected) return;
    var org = document.getElementById('orgSelector').value;
    fetchRepos(org);
    showToast('Refreshing repositories…', 'info', 2000);
}

/* ── Filter ─────────────────────────────────────────────────── */
function filterRepos() {
    var q = (document.getElementById('repoSearch').value || '').toLowerCase();
    GitHub.filteredRepos = q
        ? GitHub.repos.filter(function (r) {
            return r.name.toLowerCase().includes(q) ||
                   (r.description || '').toLowerCase().includes(q);
        })
        : GitHub.repos.slice();
    renderRepoList(GitHub.filteredRepos);
    updateRepoFooter();
}

/* ── Render repo list ────────────────────────────────────────── */
function renderRepoSkeletons() {
    var list = document.getElementById('repoList');
    var html = '';
    for (var i = 0; i < 4; i++) {
        html += '<div class="repo-skeleton">' +
            '<div class="skel-line" style="width:60%"></div>' +
            '<div class="skel-line" style="width:90%"></div>' +
            '<div class="skel-line" style="width:40%"></div>' +
        '</div>';
    }
    list.innerHTML = html;
}

function renderRepoList(repos) {
    var list = document.getElementById('repoList');

    if (!repos || repos.length === 0) {
        list.innerHTML = '<div class="empty-state">' +
            '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M9 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V9"/>' +
            '<polyline points="9 3 9 9 15 9"/></svg>' +
            '<p>No repositories found</p></div>';
        return;
    }

    var html = '';
    repos.forEach(function (repo) {
        var isSelected = GitHub.selectedRepo &&
            GitHub.selectedRepo.full_name === repo.full_name;
        var langClass = 'lang-' + (repo.language || 'unknown').replace(/[^a-zA-Z]/g, '');
        var updatedAt = repo.updated_at ? formatRelativeDate(repo.updated_at) : '';
        var starsHtml = (repo.stargazers_count > 0)
            ? '<span class="repo-meta-item">' +
              '<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>' +
              escapeHtml(String(repo.stargazers_count)) + '</span>'
            : '';

        html += '<div class="repo-card' + (isSelected ? ' selected' : '') + '" ' +
            'onclick="selectRepo(' + escapeHtml(JSON.stringify(repo)) + ')" ' +
            'data-full-name="' + escapeHtml(repo.full_name) + '">' +

            '<div class="repo-card-top">' +
            '<span class="repo-card-name">' + escapeHtml(repo.name) + '</span>' +
            '<span class="repo-card-visibility ' + (repo.private ? 'private' : 'public') + '">' +
            (repo.private ? 'Private' : 'Public') + '</span>' +
            '</div>' +

            (repo.description
                ? '<div class="repo-card-desc">' + escapeHtml(repo.description) + '</div>'
                : '') +

            '<div class="repo-card-meta">' +
            (repo.language
                ? '<span class="repo-meta-item"><span class="lang-dot ' + langClass + '"></span>' + escapeHtml(repo.language) + '</span>'
                : '') +
            starsHtml +
            (updatedAt
                ? '<span class="repo-meta-item">' +
                  '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' +
                  escapeHtml(updatedAt) + '</span>'
                : '') +
            '</div>' +
            '</div>';
    });

    list.innerHTML = html;
}

function updateRepoFooter() {
    var footer = document.getElementById('repoFooter');
    var countEl = document.getElementById('repoCount');
    var total = GitHub.repos.length;
    var filtered = GitHub.filteredRepos.length;
    if (total > 0) {
        footer.style.display = '';
        countEl.textContent = (filtered < total)
            ? filtered + ' of ' + total + ' repositories'
            : total + ' ' + (total === 1 ? 'repository' : 'repositories');
    } else {
        footer.style.display = 'none';
    }
}

/* ── Select repo ────────────────────────────────────────────── */
function selectRepo(repo) {
    GitHub.selectedRepo = {
        owner: repo.owner ? repo.owner.login : repo.full_name.split('/')[0],
        name: repo.name,
        full_name: repo.full_name
    };

    // Update cards UI
    document.querySelectorAll('.repo-card').forEach(function (el) {
        el.classList.toggle('selected', el.dataset.fullName === repo.full_name);
    });

    // Banner
    var banner = document.getElementById('selectedRepoBanner');
    banner.style.display = 'flex';
    banner.querySelector('svg').style.display = 'none';
    document.getElementById('selectedRepoLabel').textContent = repo.full_name;

    updatePushButton();
    loadBranches(GitHub.selectedRepo.owner, GitHub.selectedRepo.name);

    setStatus('Selected: ' + repo.full_name);
}

function clearSelectedRepo() {
    GitHub.selectedRepo = null;
    GitHub.branches = [];
    document.getElementById('selectedRepoBanner').style.display = 'none';
    document.querySelectorAll('.repo-card').forEach(function (el) {
        el.classList.remove('selected');
    });
    updatePushButton();
    document.getElementById('noBranchRepoMsg').style.display = 'flex';
    document.getElementById('branchFormFields').style.display = 'none';
}

/* ── Branches ───────────────────────────────────────────────── */
function loadBranches(owner, repo) {
    apiCall('/api/github/repos/' + encodeURIComponent(owner) + '/' + encodeURIComponent(repo) + '/branches',
        { headers: authHeaders() })
        .then(function (data) {
            GitHub.branches = data.branches || [];
            populateBranchSelects(GitHub.branches);
            document.getElementById('noBranchRepoMsg').style.display = 'none';
            document.getElementById('branchFormFields').style.display = '';
        })
        .catch(function (err) {
            showToast('Could not load branches: ' + err.message, 'warning');
        });
}

function populateBranchSelects(branches) {
    var pushSel = document.getElementById('pushBranch');
    var sourceSel = document.getElementById('sourceBranch');
    var savedPush = pushSel.value;
    var savedSource = sourceSel.value;

    pushSel.innerHTML = '';
    sourceSel.innerHTML = '';

    var defaultBranches = ['main', 'master', 'develop'];
    var names = branches.map(function (b) { return b.name; });

    // include defaults that aren't in the list as fallbacks
    defaultBranches.forEach(function (d) {
        if (!names.includes(d)) names.unshift(d);
    });

    // actual branches first, then fallbacks
    (branches.length ? branches.map(function (b) { return b.name; }) : defaultBranches)
        .forEach(function (name) {
            var o1 = document.createElement('option');
            o1.value = name;
            o1.textContent = name;
            pushSel.appendChild(o1);

            var o2 = document.createElement('option');
            o2.value = name;
            o2.textContent = name;
            sourceSel.appendChild(o2);
        });

    if (savedPush && pushSel.querySelector('option[value="' + savedPush + '"]')) {
        pushSel.value = savedPush;
    }
    if (savedSource && sourceSel.querySelector('option[value="' + savedSource + '"]')) {
        sourceSel.value = savedSource;
    }
}

/* ── Push migration ─────────────────────────────────────────── */
function updatePushButton() {
    var hasMigration = MigrationStore.hasMigration();
    var hasRepo = !!GitHub.selectedRepo;
    var btn = document.getElementById('btnPush');
    btn.disabled = !(hasMigration && hasRepo);

    var badge = document.getElementById('migrationBadge');
    var fileCount = document.getElementById('migrationFileCount');
    var subtitle = document.getElementById('pushSubtitle');

    if (hasMigration) {
        var files = MigrationStore.getFiles();
        var count = files ? Object.keys(files).length : 0;
        badge.className = 'badge badge-success';
        badge.textContent = 'Migration ready';
        fileCount.textContent = count + ' file' + (count !== 1 ? 's' : '');
    } else {
        badge.className = 'badge badge-warning';
        badge.textContent = 'No migration';
        fileCount.textContent = '';
    }

    if (!hasRepo) {
        subtitle.textContent = hasMigration
            ? 'Select a repository from the left'
            : 'Select a repository and run a migration first';
    } else if (!hasMigration) {
        subtitle.textContent = 'Run a migration to generate files';
    } else {
        subtitle.textContent = GitHub.selectedRepo.full_name;
    }
}

function pushMigration() {
    if (!GitHub.selectedRepo || !MigrationStore.hasMigration()) return;

    var files = MigrationStore.getFiles();
    if (!files || Object.keys(files).length === 0) {
        showToast('Migration contains no files to push', 'warning');
        return;
    }

    var branch = document.getElementById('pushBranch').value;
    var message = document.getElementById('commitMessage').value.trim() || 'chore: add Spring Boot migration output';

    var btn = document.getElementById('btnPush');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner" style="width:14px;height:14px;border-width:2px;margin:0"></span> Pushing…';

    apiCall('/api/github/push', {
        method: 'POST',
        headers: authHeaders(),
        body: {
            owner: GitHub.selectedRepo.owner,
            repo: GitHub.selectedRepo.name,
            branch: branch,
            message: message,
            files: files
        }
    }).then(function (data) {
        showToast('Pushed ' + Object.keys(files).length + ' files to ' + GitHub.selectedRepo.full_name + ' / ' + branch, 'success', 6000);
        setStatus('Pushed to ' + GitHub.selectedRepo.full_name);
        if (data.url) {
            showToast('<a href="' + escapeHtml(data.url) + '" target="_blank" rel="noopener" style="color:var(--accent-hover)">View commit on GitHub</a>', 'info', 8000);
        }
    }).catch(function (err) {
        showToast('Push failed: ' + err.message, 'error');
    }).finally(function () {
        btn.disabled = false;
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3"/></svg> Push to GitHub';
        updatePushButton();
    });
}

/* ── Create repo ────────────────────────────────────────────── */
function createRepo() {
    var name = document.getElementById('newRepoName').value.trim();
    if (!name) {
        showToast('Repository name is required', 'warning');
        document.getElementById('newRepoName').focus();
        return;
    }

    var orgVal = document.getElementById('newRepoOrg').value;
    var desc = document.getElementById('newRepoDesc').value.trim();
    var isPrivate = document.getElementById('newRepoPrivate').checked;

    var btn = document.getElementById('btnCreateRepo');
    btn.disabled = true;
    btn.textContent = 'Creating…';

    apiCall('/api/github/repos/create', {
        method: 'POST',
        headers: authHeaders(),
        body: {
            name: name,
            description: desc,
            private: isPrivate,
            org: orgVal || null
        }
    }).then(function (data) {
        showToast('Repository "' + name + '" created successfully', 'success');
        document.getElementById('newRepoName').value = '';
        document.getElementById('newRepoDesc').value = '';
        document.getElementById('newRepoPrivate').checked = false;
        document.getElementById('visibilityLabel').textContent = 'Public';
        // Reload repo list
        var org = document.getElementById('orgSelector').value;
        fetchRepos(org);
    }).catch(function (err) {
        showToast('Failed to create repository: ' + err.message, 'error');
    }).finally(function () {
        btn.disabled = false;
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Create Repository';
    });
}

/* ── Create branch ──────────────────────────────────────────── */
function createBranch() {
    if (!GitHub.selectedRepo) {
        showToast('Select a repository first', 'warning');
        return;
    }
    var source = document.getElementById('sourceBranch').value;
    var newName = document.getElementById('newBranchName').value.trim();
    if (!newName) {
        showToast('Branch name is required', 'warning');
        document.getElementById('newBranchName').focus();
        return;
    }

    var btn = document.getElementById('btnCreateBranch');
    btn.disabled = true;
    btn.textContent = 'Creating…';

    var owner = GitHub.selectedRepo.owner;
    var repo = GitHub.selectedRepo.name;

    apiCall('/api/github/repos/' + encodeURIComponent(owner) + '/' + encodeURIComponent(repo) + '/branches/create', {
        method: 'POST',
        headers: authHeaders(),
        body: {
            source: source,
            branch: newName
        }
    }).then(function () {
        showToast('Branch "' + newName + '" created from "' + source + '"', 'success');
        document.getElementById('newBranchName').value = '';
        loadBranches(owner, repo);
    }).catch(function (err) {
        showToast('Failed to create branch: ' + err.message, 'error');
    }).finally(function () {
        btn.disabled = false;
        btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 01-9 9"/></svg> Create Branch';
    });
}

/* ── Collapsible panels ─────────────────────────────────────── */
function toggleSection(id, toggleBtn) {
    var body = document.getElementById(id);
    if (!body) return;
    var isOpen = body.classList.contains('open');
    body.classList.toggle('open', !isOpen);
    if (toggleBtn) toggleBtn.classList.toggle('open', !isOpen);
}

/* ── Visibility label ───────────────────────────────────────── */
function initVisibilityToggle() {
    var chk = document.getElementById('newRepoPrivate');
    var lbl = document.getElementById('visibilityLabel');
    if (!chk || !lbl) return;
    chk.addEventListener('change', function () {
        lbl.textContent = chk.checked ? 'Private' : 'Public';
    });
}

/* ── Relative date helper ───────────────────────────────────── */
function formatRelativeDate(isoStr) {
    if (!isoStr) return '';
    var now = Date.now();
    var then = new Date(isoStr).getTime();
    var diff = Math.floor((now - then) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    if (diff < 2592000) return Math.floor(diff / 86400) + 'd ago';
    if (diff < 31536000) return Math.floor(diff / 2592000) + 'mo ago';
    return Math.floor(diff / 31536000) + 'y ago';
}

/* ── Init ───────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
    initVisibilityToggle();

    // Open collapsibles that are shown as collapsed by default
    // (they start closed — user must click toggle to open)

    // Check if already connected (token persisted)
    var token = getToken();
    if (token) {
        document.getElementById('githubToken').value = token;

        var btn = document.getElementById('btnConnect');
        btn.disabled = true;
        btn.textContent = 'Connecting…';

        apiCall('/api/github/connect', {
            method: 'POST',
            headers: { 'X-GitHub-Token': token },
            body: { token: token }
        }).then(function (data) {
            GitHub.connected = true;
            GitHub.user = data.user;
            renderConnectedUser(data.user);
            document.getElementById('btnRefresh').style.display = '';
            loadOrgsAndRepos();
        }).catch(function () {
            // Token is stale — show the form again
            SettingsStore.remove('github_token');
            document.getElementById('githubToken').value = '';
        }).finally(function () {
            btn.disabled = false;
            btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg> Connect';
        });
    }

    // Update push button state based on migration store
    updatePushButton();

    setStatus('GitHub Integration ready');
});
