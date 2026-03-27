// ═══════════════════════════════════════════════════════════════
// Build & Test page JS
// Prerequisites check, build triggers, SSE streaming, artifact download
// ═══════════════════════════════════════════════════════════════

(function () {
    'use strict';

    // ── State ────────────────────────────────────────────────────
    var state = {
        buildId: null,
        buildType: null,      // jar | war | docker | test
        eventSource: null,
        lineCount: 0,
        buildStatus: 'idle',  // idle | running | success | failed
        artifactAvailable: false,
        artifactPath: null,
        checking: false
    };

    // ── DOM helpers ───────────────────────────────────────────────
    function $(id) { return document.getElementById(id); }

    // ── Initialization ────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function () {
        checkMigrationState();
        bindButtons();
        renderTerminalIdle();
        updateBuildStatusBadge('idle');
        checkPrerequisites();
    });

    /**
     * Check if migration data exists in MigrationStore.
     * Show warning banner and disable build buttons if none.
     */
    function checkMigrationState() {
        var files = getProjectFiles(true);
        var banner = $('noMigrationBanner');
        var buildGrid = $('buildActionsGrid');
        if (!files) {
            if (banner) banner.style.display = 'flex';
            if (buildGrid) {
                buildGrid.querySelectorAll('.build-action-btn').forEach(function (b) {
                    b.disabled = true;
                });
            }
        } else {
            if (banner) banner.style.display = 'none';
        }
    }

    function bindButtons() {
        var checkBtn = $('checkPrereqsBtn');
        if (checkBtn) checkBtn.addEventListener('click', checkPrerequisites);

        var jarBtn = $('buildJarBtn');
        if (jarBtn) jarBtn.addEventListener('click', function () { buildJar(); });

        var warBtn = $('buildWarBtn');
        if (warBtn) warBtn.addEventListener('click', function () { buildWar(); });

        var dockerBtn = $('buildDockerBtn');
        if (dockerBtn) dockerBtn.addEventListener('click', function () { buildDocker(); });

        var testBtn = $('runTestsBtn');
        if (testBtn) testBtn.addEventListener('click', function () { runTests(); });

        var clearBtn = $('clearTerminalBtn');
        if (clearBtn) clearBtn.addEventListener('click', clearTerminal);

        var downloadBtn = $('downloadArtifactBtn');
        if (downloadBtn) downloadBtn.addEventListener('click', function () {
            downloadArtifact(state.buildId);
        });
    }

    // ── 1. checkPrerequisites() ─────────────────────────────────
    function checkPrerequisites() {
        if (state.checking) return;
        state.checking = true;

        var btn = $('checkPrereqsBtn');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML =
                '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Checking...';
        }
        setStatus('Checking prerequisites...');

        ['java', 'maven', 'docker'].forEach(function (tool) {
            setPrereqStatus(tool, 'unknown', 'Checking...');
        });

        apiCall('/api/build/check-prereqs', { method: 'POST' })
            .then(function (data) {
                renderPrereqs(data);
                setStatus('Prerequisites check complete');
                showToast('Prerequisites check complete', 'info', 3000);

                // Populate platform dropdown if platforms returned
                if (data.platforms) {
                    populatePlatforms(data.platforms);
                }
            })
            .catch(function (err) {
                showToast('Failed to check prerequisites: ' + err.message, 'error');
                setStatus('Prerequisites check failed');
                ['java', 'maven', 'docker'].forEach(function (tool) {
                    setPrereqStatus(tool, 'fail', 'Error');
                });
            })
            .finally(function () {
                state.checking = false;
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML =
                        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 12l2 2 4-4"/><path d="M21 12c0 4.97-4.03 9-9 9s-9-4.03-9-9 4.03-9 9-9c2.12 0 4.07.74 5.61 1.97"/></svg> Check Prerequisites';
                }
            });
    }

    // ── 11. renderPrereqs(data) ──────────────────────────────────
    function renderPrereqs(data) {
        var tools = ['java', 'maven', 'docker'];
        tools.forEach(function (tool) {
            var info = data[tool] || {};
            var available = info.available === true;
            var version = info.version || (available ? 'Available' : 'Not found');
            setPrereqStatus(tool, available ? 'ok' : 'fail', version, info);
        });

        // Disable build buttons based on prerequisite availability
        var javaInfo = data.java || {};
        var dockerInfo = data.docker || {};
        var jarBtn = $('buildJarBtn');
        var warBtn = $('buildWarBtn');
        var dockerBtn = $('buildDockerBtn');
        var hasFiles = !!getProjectFiles(true);

        if (jarBtn) {
            jarBtn.disabled = !javaInfo.available || !hasFiles;
            jarBtn.title = !javaInfo.available ? 'Java is required to build JAR files' : '';
        }
        if (warBtn) {
            warBtn.disabled = !javaInfo.available || !hasFiles;
            warBtn.title = !javaInfo.available ? 'Java is required to build WAR files' : '';
        }
        if (dockerBtn) {
            dockerBtn.disabled = !dockerInfo.available || !javaInfo.available || !hasFiles;
            dockerBtn.title = !dockerInfo.available
                ? 'Docker is required for container builds'
                : (!javaInfo.available ? 'Java is required to build the application' : '');
        }
    }

    function setPrereqStatus(tool, status, versionText, info) {
        var item = document.querySelector('.prereq-item[data-tool="' + tool + '"]');
        if (!item) return;
        item.classList.remove('status-ok', 'status-fail', 'status-unknown');
        item.classList.add('status-' + status);
        var versionEl = item.querySelector('.prereq-version');
        if (versionEl) versionEl.textContent = versionText || '';

        // Remove any existing help block
        var existingHelp = item.querySelector('.prereq-help');
        if (existingHelp) existingHelp.remove();

        // Show install hints when tool is not available
        if (status === 'fail' && info && info.install_hint) {
            var helpDiv = document.createElement('div');
            helpDiv.className = 'prereq-help';

            var hintSpan = document.createElement('span');
            hintSpan.className = 'prereq-hint';
            hintSpan.textContent = info.install_hint;
            helpDiv.appendChild(hintSpan);

            if (info.links) {
                var linksDiv = document.createElement('div');
                linksDiv.className = 'prereq-links';
                Object.keys(info.links).forEach(function (platform) {
                    var value = info.links[platform];
                    var isUrl = value.indexOf('http') === 0;
                    if (isUrl) {
                        var a = document.createElement('a');
                        a.href = value;
                        a.target = '_blank';
                        a.rel = 'noopener noreferrer';
                        a.className = 'prereq-link';
                        a.textContent = platform;
                        linksDiv.appendChild(a);
                    } else {
                        var code = document.createElement('span');
                        code.className = 'prereq-link prereq-link-cmd';
                        code.textContent = platform + ': ' + value;
                        code.title = 'Copy to clipboard';
                        code.addEventListener('click', function () {
                            if (navigator.clipboard) {
                                navigator.clipboard.writeText(value);
                                showToast('Copied: ' + value, 'info', 2000);
                            }
                        });
                        linksDiv.appendChild(code);
                    }
                });
                helpDiv.appendChild(linksDiv);
            }

            item.appendChild(helpDiv);
        }
    }

    function populatePlatforms(platforms) {
        var sel = $('dockerPlatformSelect');
        if (!sel) return;
        var currentVal = sel.value;
        sel.innerHTML = '';
        Object.keys(platforms).forEach(function (key) {
            var opt = document.createElement('option');
            opt.value = key;
            opt.textContent = platforms[key];
            sel.appendChild(opt);
        });
        // Restore selection if still valid
        if (sel.querySelector('option[value="' + currentVal + '"]')) {
            sel.value = currentVal;
        }
    }

    // ── 2. buildJar() ────────────────────────────────────────────
    function buildJar() {
        startBuild('jar');
    }

    // ── 3. buildWar() ────────────────────────────────────────────
    function buildWar() {
        startBuild('war');
    }

    // ── 4. buildDocker() ─────────────────────────────────────────
    function buildDocker() {
        var sel = $('dockerPlatformSelect');
        var platform = sel ? sel.value : 'linux/amd64';
        startBuild('docker', { platform: platform });
    }

    // ── 5. runTests() ────────────────────────────────────────────
    function runTests() {
        var files = getProjectFiles();
        if (!files) return;
        if (state.buildStatus === 'running') {
            showToast('A build is already running.', 'warning');
            return;
        }

        clearTerminal();
        setBuildRunning('test');
        setStatus('Running tests...');

        var result = MigrationStore.load() || {};
        var projectName = result.projectName || 'migrated-app';

        apiCall('/api/test/start', {
            method: 'POST',
            body: { files: files, projectName: projectName }
        })
            .then(function (data) {
                state.buildId = data.testId || data.buildId || data.build_id;
                state.buildType = 'test';
                appendTerminalLine('Test run started — ID: ' + state.buildId, 'info');
                appendTerminalLine('', 'default');
                streamBuildOutput(state.buildId);
            })
            .catch(function (err) {
                setBuildFailed();
                appendTerminalLine('[ERROR] Failed to start tests: ' + err.message, 'error');
                showToast('Test run failed to start: ' + err.message, 'error');
                setStatus('Test run failed to start');
            });
    }

    // ── 6. startBuild(type, extraData) ───────────────────────────
    function startBuild(type, extraData) {
        var files = getProjectFiles();
        if (!files) return;
        if (state.buildStatus === 'running') {
            showToast('A build is already running.', 'warning');
            return;
        }

        var result = MigrationStore.load() || {};
        var projectName = result.projectName || 'migrated-app';

        var payload = { files: files, projectName: projectName };
        if (extraData) {
            Object.keys(extraData).forEach(function (k) {
                payload[k] = extraData[k];
            });
        }

        clearTerminal();
        setBuildRunning(type);

        var label = type.toUpperCase();
        setStatus('Starting ' + label + ' build...');

        var urlMap = { jar: '/api/build/jar', war: '/api/build/war', docker: '/api/build/docker' };
        var url = urlMap[type];
        if (!url) {
            showToast('Unknown build type: ' + type, 'error');
            return;
        }

        apiCall(url, { method: 'POST', body: payload })
            .then(function (data) {
                state.buildId = data.buildId || data.build_id;
                state.buildType = type;
                appendTerminalLine('Build started — ID: ' + state.buildId, 'info');
                appendTerminalLine('Type: ' + label + (extraData && extraData.platform ? ' (' + extraData.platform + ')' : ''), 'info');
                appendTerminalLine('', 'default');
                streamBuildOutput(state.buildId);
            })
            .catch(function (err) {
                setBuildFailed();
                appendTerminalLine('[ERROR] Failed to start build: ' + err.message, 'error');
                showToast('Build failed to start: ' + err.message, 'error');
                setStatus('Build failed to start');
            });
    }

    // ── SSE Streaming ─────────────────────────────────────────────
    function streamBuildOutput(buildId) {
        if (state.eventSource) {
            state.eventSource.close();
            state.eventSource = null;
        }

        var url = '/api/build/' + buildId + '/stream';

        state.eventSource = connectSSE(url, {
            onMessage: function (data) {
                if (data.line !== undefined) {
                    appendTerminalLine(data.line, classifyLine(data.line));
                }
                if (data.status) {
                    handleBuildCompletion(data);
                }
            },
            onStatus: function (status) {
                // Called when data.status is present
            },
            onError: function () {
                state.eventSource = null;
                if (state.buildStatus === 'running') {
                    setBuildFailed();
                    appendTerminalLine('[ERROR] Connection to build stream lost.', 'error');
                }
            }
        });
    }

    function handleBuildCompletion(data) {
        var status = data.status;
        if (status === 'success' || status === 'completed') {
            setBuildSuccess(data.artifact);
        } else if (status === 'failed' || status === 'error') {
            setBuildFailed();
        }

        // Close SSE after completion
        if (state.eventSource) {
            state.eventSource.close();
            state.eventSource = null;
        }

        // Schedule cleanup after a delay
        if (state.buildId) {
            var id = state.buildId;
            setTimeout(function () { cleanupBuild(id); }, 30000);
        }
    }

    // ── Line Classification ────────────────────────────────────────
    function classifyLine(line) {
        if (/\[ERROR\]|ERROR:|^ERROR |BUILD FAILURE|FAILED/i.test(line)) {
            return 'error';
        }
        if (/\[WARNING\]|WARN:|^WARN |\[WARN\]/i.test(line)) {
            return 'warning';
        }
        if (/BUILD SUCCESS|Tests run:.*Failures: 0.*Errors: 0|PASSED|successfully built/i.test(line)) {
            return 'success';
        }
        if (/\[INFO\]|INFO:/i.test(line)) {
            return 'info';
        }
        if (/^\s*\$|^\s*>/.test(line)) {
            return 'cmd';
        }
        return 'default';
    }

    // ── 7. appendTerminalLine(line) ──────────────────────────────
    function appendTerminalLine(text, type) {
        var body = $('terminalBody');
        if (!body) return;

        // Remove idle placeholder if present
        var placeholder = body.querySelector('.term-empty');
        if (placeholder) placeholder.remove();

        var span = document.createElement('span');
        span.className = 'term-line term-line-' + (type || 'default');
        span.textContent = text;
        body.appendChild(span);
        body.appendChild(document.createElement('br'));

        state.lineCount++;
        updateLineCount();

        // Auto-scroll to bottom
        body.scrollTop = body.scrollHeight;
    }

    // ── 8. clearTerminal() ───────────────────────────────────────
    function clearTerminal() {
        renderTerminalIdle();
        hideDownloadBtn();
        updateBuildStatusBadge('idle');
        state.buildStatus = 'idle';
        state.artifactAvailable = false;
        state.artifactPath = null;
        clearCardStates();
        setStatus('Ready');
    }

    function renderTerminalIdle() {
        var body = $('terminalBody');
        if (!body) return;
        body.innerHTML = '<div class="term-empty">No build output yet — trigger a build or run tests to see output here.</div>';
        state.lineCount = 0;
        updateLineCount();
    }

    function updateLineCount() {
        var el = $('terminalStats');
        if (el) el.textContent = state.lineCount > 0 ? state.lineCount + ' lines' : '';
    }

    // ── 9. downloadArtifact(buildId) ─────────────────────────────
    function downloadArtifact(buildId) {
        if (!buildId || !state.artifactAvailable) return;
        var url = '/api/build/' + buildId + '/artifact';
        var a = document.createElement('a');
        a.href = url;
        a.download = '';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('Downloading artifact...', 'info', 2500);
    }

    // ── 10. cleanupBuild(buildId) ────────────────────────────────
    function cleanupBuild(buildId) {
        if (!buildId) return;
        apiCall('/api/build/' + buildId + '/cleanup', { method: 'POST' })
            .catch(function () {
                // Cleanup failures are non-critical
            });
    }

    // ── 12. getProjectFiles() ────────────────────────────────────
    function getProjectFiles(silent) {
        var files = MigrationStore.getFiles();
        if (!files || Object.keys(files).length === 0) {
            if (!silent) {
                showToast('No migration result found. Please run a migration first.', 'warning');
            }
            return null;
        }
        return files;
    }

    // ── 13. disableBuildButtons(disabled) ─────────────────────────
    function disableBuildButtons(disabled) {
        var noFiles = !getProjectFiles(true);
        ['buildJarBtn', 'buildWarBtn', 'buildDockerBtn', 'runTestsBtn'].forEach(function (id) {
            var btn = $(id);
            if (btn) btn.disabled = disabled || noFiles;
        });
    }

    // ── Build State Transitions ────────────────────────────────────
    function setBuildRunning(type) {
        state.buildStatus = 'running';
        state.artifactAvailable = false;
        state.artifactPath = null;
        hideDownloadBtn();
        updateBuildStatusBadge('running');
        disableBuildButtons(true);
        setCardState(type, 'building');

        var label = type === 'test' ? 'Running tests' : ('Building ' + type.toUpperCase());
        setStatus(label + '...');
    }

    function setBuildSuccess(artifactPath) {
        if (state.buildStatus !== 'running') return;
        state.buildStatus = 'success';
        updateBuildStatusBadge('success');
        disableBuildButtons(false);
        setCardState(state.buildType, 'build-success');

        var type = state.buildType;
        var msg = (type === 'test' ? 'Tests' : type.toUpperCase() + ' build') + ' completed successfully';
        setStatus(msg);
        showToast(msg, 'success');

        if (type === 'jar' || type === 'war' || type === 'docker') {
            state.artifactAvailable = true;
            state.artifactPath = artifactPath || null;
            showDownloadBtn(type, artifactPath);
        }
    }

    function setBuildFailed() {
        if (state.buildStatus !== 'running') return;
        state.buildStatus = 'failed';
        updateBuildStatusBadge('failed');
        disableBuildButtons(false);
        setCardState(state.buildType, 'build-failed');

        var type = state.buildType || 'build';
        var msg = (type === 'test' ? 'Test run' : type.toUpperCase() + ' build') + ' failed';
        setStatus(msg);
        showToast(msg, 'error');
    }

    // ── Build Card Visual States ──────────────────────────────────
    function setCardState(type, stateClass) {
        clearCardStates();
        var cardMap = { jar: 'cardJar', war: 'cardWar', docker: 'cardDocker', test: 'cardTest' };
        var cardId = cardMap[type];
        if (cardId) {
            var card = $(cardId);
            if (card) card.classList.add(stateClass);
        }
    }

    function clearCardStates() {
        document.querySelectorAll('.build-card').forEach(function (card) {
            card.classList.remove('building', 'build-success', 'build-failed', 'card-active');
        });
    }

    // ── Build Status Badge ─────────────────────────────────────────
    function updateBuildStatusBadge(status) {
        var badge = $('buildStatusBadge');
        if (!badge) return;
        badge.className = 'build-status-badge status-' + status;
        var labels = {
            idle: 'Idle',
            running: 'Running',
            success: 'Success',
            failed: 'Failed'
        };
        var spinnerHtml = status === 'running'
            ? '<span class="status-spinner"></span> '
            : '';
        badge.innerHTML = spinnerHtml + (labels[status] || status);
    }

    // ── Download / Artifact UI ─────────────────────────────────────
    function showDownloadBtn(type, artifactPath) {
        var btn = $('downloadArtifactBtn');
        if (!btn) return;
        btn.classList.add('visible');
        btn.innerHTML =
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
            '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>' +
            '<polyline points="7 10 12 15 17 10"/>' +
            '<line x1="12" y1="15" x2="12" y2="3"/></svg> Download ' + type.toUpperCase();

        // Show artifact info if available
        var infoEl = $('artifactInfo');
        if (infoEl && artifactPath) {
            var filename = artifactPath.split('/').pop() || artifactPath;
            infoEl.textContent = filename;
        }
    }

    function hideDownloadBtn() {
        var btn = $('downloadArtifactBtn');
        if (btn) btn.classList.remove('visible');
        var infoEl = $('artifactInfo');
        if (infoEl) infoEl.textContent = '';
    }

}());
