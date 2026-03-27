// Dashboard page logic
document.addEventListener('DOMContentLoaded', function () {
    initDashboard();
});

function initDashboard() {
    // Set up intersection observer for stat animations
    setupStatObserver();
    // Set up ripple effects on action cards
    setupActionCardRipples();
    // Set up keyboard navigation for action cards
    setupKeyboardNav();
    // Show last migration timestamp
    showLastMigrationTimestamp();
}

/* ── Intersection Observer for Stats ─────────────────────────── */
function setupStatObserver() {
    var statsSection = document.querySelector('.status-section');
    if (!statsSection) {
        // Fallback: load immediately if section exists
        loadMigrationStats();
        return;
    }

    var hasAnimated = false;
    var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting && !hasAnimated) {
                hasAnimated = true;
                loadMigrationStats();
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.2 });

    observer.observe(statsSection);
}

/* ── Load Migration Stats ────────────────────────────────────── */
function loadMigrationStats() {
    var result = MigrationStore.load();
    if (!result) return;

    var summary = result.summary || {};
    var files = result.files || {};
    var validation = result.llmValidation || {};

    var flows = (summary.flowsConverted || 0) + (summary.subFlowsConverted || 0);
    var fileCount = Object.keys(files).length;
    var connectors = (summary.connectorsFound || []).length;
    var score = validation.overallScore;

    animateStat('statFlows', flows);
    animateStat('statFiles', fileCount);
    animateStat('statConnectors', connectors);

    if (score !== undefined && score !== null) {
        animateStatText('statScore', score + '/10');
    }
}

/* ── Animate Stat Counter (easeOutExpo) ─────────────────────── */
function animateStat(id, target) {
    var el = document.getElementById(id);
    if (!el || target === 0) {
        if (el) el.textContent = target || '0';
        return;
    }
    var current = 0;
    var duration = 800;
    var start = performance.now();

    function easeOutExpo(t) {
        return t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
    }

    function step(ts) {
        var progress = Math.min((ts - start) / duration, 1);
        var eased = easeOutExpo(progress);
        current = Math.round(eased * target);
        el.textContent = current;
        if (progress < 1) requestAnimationFrame(step);
    }

    requestAnimationFrame(step);
}

/* ── Animate Stat Text (for score) ──────────────────────────── */
function animateStatText(id, text) {
    var el = document.getElementById(id);
    if (!el) return;
    // Brief delay then set text with a subtle scale pop
    setTimeout(function () {
        el.textContent = text;
        el.style.transform = 'scale(1.15)';
        el.style.transition = 'transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1)';
        setTimeout(function () {
            el.style.transform = 'scale(1)';
        }, 200);
    }, 400);
}

/* ── Ripple Effect on Action Cards ──────────────────────────── */
function setupActionCardRipples() {
    var cards = document.querySelectorAll('.action-card');
    cards.forEach(function (card) {
        card.addEventListener('click', function (e) {
            var rect = card.getBoundingClientRect();
            var ripple = document.createElement('span');
            ripple.className = 'ripple';
            var size = Math.max(rect.width, rect.height);
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
            ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
            card.appendChild(ripple);
            ripple.addEventListener('animationend', function () {
                ripple.remove();
            });
        });
    });
}

/* ── Keyboard Navigation Between Action Cards ───────────────── */
function setupKeyboardNav() {
    var cards = Array.from(document.querySelectorAll('.action-card'));
    if (cards.length === 0) return;

    // Make action cards focusable
    cards.forEach(function (card, i) {
        if (!card.getAttribute('tabindex')) {
            card.setAttribute('tabindex', '0');
        }
        card.setAttribute('role', 'button');
    });

    document.addEventListener('keydown', function (e) {
        var active = document.activeElement;
        var idx = cards.indexOf(active);
        if (idx === -1) return;

        var nextIdx = -1;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            nextIdx = (idx + 1) % cards.length;
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            nextIdx = (idx - 1 + cards.length) % cards.length;
        } else if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            active.click();
            return;
        }

        if (nextIdx >= 0) {
            e.preventDefault();
            cards[nextIdx].focus();
        }
    });
}

/* ── Last Migration Timestamp ───────────────────────────────── */
function showLastMigrationTimestamp() {
    var result = MigrationStore.load();
    if (!result || !result.timestamp) return;

    var container = document.querySelector('.status-section');
    if (!container) return;

    var ts = new Date(result.timestamp);
    var now = new Date();
    var diffMs = now - ts;
    var diffMin = Math.floor(diffMs / 60000);
    var diffHr = Math.floor(diffMin / 60);
    var diffDay = Math.floor(diffHr / 24);

    var timeAgo;
    if (diffMin < 1) timeAgo = 'just now';
    else if (diffMin < 60) timeAgo = diffMin + ' minute' + (diffMin > 1 ? 's' : '') + ' ago';
    else if (diffHr < 24) timeAgo = diffHr + ' hour' + (diffHr > 1 ? 's' : '') + ' ago';
    else timeAgo = diffDay + ' day' + (diffDay > 1 ? 's' : '') + ' ago';

    var infoDiv = document.createElement('div');
    infoDiv.className = 'last-migration-info fade-in-up';
    infoDiv.innerHTML = 'Last migration: <span class="timestamp">' + timeAgo + '</span>';
    container.appendChild(infoDiv);
}
