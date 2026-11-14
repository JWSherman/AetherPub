/**
 * AetherPub Reactive Application Controller
 * Cyberpunk Obsidian & Dark Glassmorphism - Hyper-Optimized 120fps Engine
 */

const API_BASE = '/api/v1';

const DEFAULT_AGE_PRESET = [
    { x: 0.0, y: 5.0 },
    { x: 2.0, y: 3.0 },
    { x: 7.0, y: 0.0 },
    { x: 14.0, y: -3.0 },
    { x: 30.0, y: -8.0 }
];

const DEFAULT_LENGTH_PRESET = [
    { x: 0.0, y: -5.0 },
    { x: 400.0, y: 0.0 },
    { x: 1200.0, y: 4.0 },
    { x: 2500.0, y: 6.0 },
    { x: 6000.0, y: 3.0 },
    { x: 12000.0, y: -2.0 }
];

const GRAPH_LAYOUT = {
    width: 600,
    height: 240,
    left: 45,
    right: 25,
    top: 20,
    bottom: 30,
    plotWidth: 530,
    plotHeight: 190
};

const state = {
    currentTab: 'dashboard',
    sources: [],
    keywords: [],
    articles: [],
    editions: [],
    settings: {},
    curves: {
        age_curve: JSON.parse(JSON.stringify(DEFAULT_AGE_PRESET)),
        length_curve: JSON.parse(JSON.stringify(DEFAULT_LENGTH_PRESET))
    },
    curvesInitialized: {
        age: false,
        length: false
    },
    isCrawling: false,
    isCompiling: false,
    terminalLogs: [],
    editionsViewMode: 'list',
    selectedEditions: new Set(),
    editionsSearchQuery: '',
    editionsSortBy: 'created_desc',
    expandedDownloadHistory: new Set()
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initSSE();
    fetchAllData();
    setupEventListeners();
    initGraphGlobalListeners();
});

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-btn');
    navItems.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchTab(tab);
        });
    });
}

function switchTab(tabId) {
    if (tabId === 'sources' || tabId === 'keywords') {
        tabId = 'curation';
    }
    state.currentTab = tabId;
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    const target = document.getElementById(`tab-${tabId}`);
    if (target) target.classList.remove('hidden');

    document.querySelectorAll('.nav-btn').forEach(btn => {
        if (btn.dataset.tab === tabId || (tabId === 'curation' && (btn.dataset.tab === 'sources' || btn.dataset.tab === 'keywords'))) {
            btn.classList.add('bg-zinc-800', 'text-cyan-400', 'border-cyan-500/40');
            btn.classList.remove('text-zinc-400', 'border-transparent');
        } else {
            btn.classList.remove('bg-zinc-800', 'text-cyan-400', 'border-cyan-500/40');
            btn.classList.add('text-zinc-400', 'border-transparent');
        }
    });

    if (tabId === 'curation') {
        renderSources();
        renderKeywords();
        renderCurves();
        populateSandboxSources();
    }
    if (tabId === 'editions') renderEditions();
    if (tabId === 'settings') loadSettingsForm();
    if (tabId === 'articles') renderArticles();
}

// --- SSE Real-Time Telemetry Stream ---
function initSSE() {
    const eventSource = new EventSource(`${API_BASE}/events/stream`);

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleIncomingEvent(data.event, data.payload);
        } catch (e) {
            console.error('Error parsing SSE event:', e);
        }
    };

    eventSource.onerror = (err) => {
        appendLog('warn', 'Telemetry SSE disconnected. Reconnecting...');
    };
}

function handleIncomingEvent(eventType, payload) {
    const timestamp = new Date().toLocaleTimeString();
    
    switch (eventType) {
        case 'connected':
            appendLog('info', `[${timestamp}] ⚡ Telemetry Stream Connected`);
            break;
        case 'crawler:source_started':
            appendLog('info', `[${timestamp}] 🔍 Crawling source: ${payload.name}`);
            setPulseState('crawling');
            break;
        case 'crawler:candidates_found':
            appendLog('info', `[${timestamp}] 📡 Discovered ${payload.count} candidate articles`);
            break;
        case 'article:ingested':
            appendLog('success', `[${timestamp}] 📄 Ingested "${payload.title}" (Score: ${payload.score})`);
            fetchArticles();
            break;
        case 'crawler:source_completed':
            appendLog('success', `[${timestamp}] ✅ Finished source ${payload.name} (+${payload.new_articles} articles)`);
            setPulseState('idle');
            fetchSources();
            break;
        case 'crawler:source_failed':
            appendLog('error', `[${timestamp}] ❌ Source crawl failed: ${payload.error}`);
            setPulseState('idle');
            fetchSources();
            break;
        case 'compiler:started':
            appendLog('info', `[${timestamp}] 📚 Compiling Daily EPUB (${payload.article_count} articles)...`);
            setPulseState('compiling');
            break;
        case 'compiler:completed':
            appendLog('success', `[${timestamp}] 🎉 Generated EPUB "${payload.file_name}" (${(payload.file_size / 1024 / 1024).toFixed(2)} MB)`);
            setPulseState('idle');
            showToast('Daily EPUB Edition Compiled!', 'success');
            fetchEditions();
            fetchArticles();
            break;
        case 'compiler:empty':
            appendLog('warn', `[${timestamp}] ⚠️ Compilation skipped: No unbundled articles found.`);
            setPulseState('idle');
            showToast('No unbundled articles available to compile.', 'warn');
            break;
        case 'smtp:sent':
            appendLog('success', `[${timestamp}] 📧 Sent edition to ${payload.recipient} via SMTP`);
            showToast(`Edition sent to ${payload.recipient}`, 'success');
            fetchEditions();
            break;
        case 'smtp:failed':
            appendLog('error', `[${timestamp}] ❌ SMTP dispatch failed: ${payload.error}`);
            showToast(`SMTP Error: ${payload.error}`, 'error');
            break;
        case 'curation:scores_recalculated':
            appendLog('success', `[${timestamp}] ⚡ Recalculated scores for ${payload.updated_articles} unbundled articles`);
            fetchArticles();
            break;
        case 'curation:curves_updated':
            appendLog('info', `[${timestamp}] 📈 Curation curves updated`);
            break;
        case 'edition:downloaded':
            appendLog('info', `[${timestamp}] 📥 Downloaded "${payload.file_name}" (Total: ${payload.download_count}x)`);
            fetchEditions();
            break;
        case 'edition:deleted':
            appendLog('warn', `[${timestamp}] 🗑️ Deleted EPUB "${payload.file_name}"`);
            fetchEditions();
            break;
        case 'articles:bundled_reset':
            appendLog('info', `[${timestamp}] 🔄 Cleared 'Bundled' flag on ${payload.reset_count} articles (Clean Slate Ready)`);
            fetchArticles();
            break;
        default:
            appendLog('info', `[${timestamp}] [${eventType}] ${JSON.stringify(payload)}`);
    }
}

function appendLog(level, message) {
    const consoleEl = document.getElementById('telemetry-console');
    if (!consoleEl) return;

    const line = document.createElement('div');
    line.className = 'font-mono text-xs leading-relaxed transition-all';
    if (level === 'info') line.className += ' text-zinc-300';
    if (level === 'success') line.className += ' text-cyan-400 font-medium';
    if (level === 'warn') line.className += ' text-amber-400';
    if (level === 'error') line.className += ' text-rose-400 font-medium';

    line.textContent = message;
    consoleEl.appendChild(line);

    while (consoleEl.children.length > 200) {
        consoleEl.removeChild(consoleEl.firstChild);
    }

    consoleEl.scrollTop = consoleEl.scrollHeight;
}

function setPulseState(mode) {
    const pulseDot = document.getElementById('system-status-dot');
    const pulseText = document.getElementById('system-status-text');
    if (!pulseDot || !pulseText) return;

    if (mode === 'crawling') {
        pulseDot.className = 'w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping';
        pulseText.textContent = 'Crawling Sources...';
        pulseText.className = 'text-xs font-mono text-cyan-400';
    } else if (mode === 'compiling') {
        pulseDot.className = 'w-2.5 h-2.5 rounded-full bg-violet-400 animate-ping';
        pulseText.textContent = 'Compiling EPUB 3...';
        pulseText.className = 'text-xs font-mono text-violet-400';
    } else {
        pulseDot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-400';
        pulseText.textContent = 'System Active (Idle)';
        pulseText.className = 'text-xs font-mono text-emerald-400';
    }
}

// --- Data Fetching ---
async function fetchAllData() {
    await Promise.all([
        fetchSources(),
        fetchKeywords(),
        fetchCurves(),
        fetchArticles(),
        fetchEditions(),
        fetchSettings()
    ]);
    updateDashboardKPIs();
}

async function fetchSources() {
    try {
        const res = await fetch(`${API_BASE}/sources`);
        state.sources = await res.json();
        if (state.currentTab === 'curation') {
            renderSources();
            populateSandboxSources();
        }
        updateDashboardKPIs();
    } catch (e) {
        console.error('Failed to fetch sources:', e);
    }
}

async function fetchKeywords() {
    try {
        const res = await fetch(`${API_BASE}/keywords`);
        state.keywords = await res.json();
        if (state.currentTab === 'curation') renderKeywords();
        updateDashboardKPIs();
    } catch (e) {
        console.error('Failed to fetch keywords:', e);
    }
}

async function fetchCurves() {
    try {
        const res = await fetch(`${API_BASE}/curation/curves`);
        if (res.ok) {
            const data = await res.json();
            if (data.age_curve && data.age_curve.length) state.curves.age_curve = data.age_curve;
            if (data.length_curve && data.length_curve.length) state.curves.length_curve = data.length_curve;
            if (state.currentTab === 'curation') renderCurves();
        }
    } catch (e) {
        console.error('Failed to fetch curation curves:', e);
    }
}

async function fetchArticles() {
    try {
        const res = await fetch(`${API_BASE}/articles?limit=50`);
        state.articles = await res.json();
        if (state.currentTab === 'articles') renderArticles();
        updateDashboardKPIs();
    } catch (e) {
        console.error('Failed to fetch articles:', e);
    }
}

async function fetchEditions() {
    try {
        const res = await fetch(`${API_BASE}/editions`);
        state.editions = await res.json();
        if (state.currentTab === 'editions' || state.currentTab === 'dashboard') {
            renderEditions();
            renderDashboardEditions();
        }
        updateDashboardKPIs();
    } catch (e) {
        console.error('Failed to fetch editions:', e);
    }
}

async function fetchSettings() {
    try {
        const res = await fetch(`${API_BASE}/settings`);
        state.settings = await res.json();
        if (state.currentTab === 'settings') loadSettingsForm();
    } catch (e) {
        console.error('Failed to fetch settings:', e);
    }
}

function updateDashboardKPIs() {
    const kpiSources = document.getElementById('kpi-sources');
    const kpiKeywords = document.getElementById('kpi-keywords');
    const kpiArticles = document.getElementById('kpi-articles');
    const kpiEditions = document.getElementById('kpi-editions');

    const unbundled = state.articles.filter(a => !a.is_bundled).length;
    const bundled = state.articles.length - unbundled;

    if (kpiSources) kpiSources.textContent = state.sources.length;
    if (kpiKeywords) kpiKeywords.textContent = state.keywords.length;
    if (kpiArticles) {
        kpiArticles.textContent = `${unbundled} (${state.articles.length} total)`;
    }
    if (kpiEditions) kpiEditions.textContent = state.editions.length;

    const edLabel = document.getElementById('ed-reset-bundled-label');
    const artLabel = document.getElementById('art-reset-bundled-label');
    const badgeText = bundled > 0 ? `Clear Bundled (${bundled})` : 'Clear Bundled';
    if (edLabel) edLabel.textContent = badgeText;
    if (artLabel) artLabel.textContent = badgeText;
}

// --- Renders ---

// Render Website Sources with specific weight bias
function renderSources() {
    const container = document.getElementById('sources-list');
    if (!container) return;

    if (state.sources.length === 0) {
        container.innerHTML = `
            <div class="col-span-full py-12 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40">
                <i data-lucide="globe" class="w-10 h-10 text-zinc-600 mx-auto mb-3"></i>
                <p class="text-zinc-400 font-medium">No website sources registered yet</p>
                <p class="text-zinc-600 text-xs mt-1">Add your favorite blogs, news sites, or RSS feeds to begin tracking and scoring articles.</p>
                <button onclick="openAddSourceModal()" class="mt-4 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-semibold text-xs transition-all shadow-lg shadow-cyan-500/20">
                    + Add First Source
                </button>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    container.innerHTML = state.sources.map(src => {
        const statusColors = {
            idle: 'bg-zinc-800 text-zinc-400 border-zinc-700',
            crawling: 'bg-cyan-950/60 text-cyan-400 border-cyan-800 animate-pulse',
            success: 'bg-emerald-950/60 text-emerald-400 border-emerald-800',
            error: 'bg-rose-950/60 text-rose-400 border-rose-800'
        };

        const lastCrawled = src.last_crawled_at ? new Date(src.last_crawled_at).toLocaleString() : 'Never';
        const weightVal = (src.weight !== undefined && src.weight !== null) ? Number(src.weight) : 0.0;
        const weightDisplay = (weightVal > 0 ? `+${weightVal}` : `${weightVal}`);
        const weightColor = weightVal > 0 ? 'text-cyan-400' : (weightVal < 0 ? 'text-rose-400' : 'text-zinc-400');

        return `
            <div class="glass-panel p-5 rounded-xl flex flex-col justify-between group relative overflow-hidden border border-white/5 hover:border-cyan-500/30">
                <div class="absolute top-0 left-0 w-1 h-full bg-cyan-500 opacity-60"></div>
                <div>
                    <div class="flex items-start justify-between gap-2">
                        <h3 class="font-semibold text-base text-white group-hover:text-cyan-400 transition-colors truncate" title="${src.name}">
                            ${src.name}
                        </h3>
                        <span class="px-2 py-0.5 text-[10px] font-mono rounded border uppercase ${statusColors[src.last_status] || statusColors.idle}">
                            ${src.last_status}
                        </span>
                    </div>
                    <p class="text-xs text-zinc-400 font-mono mt-1 truncate" title="${src.base_url}">${src.base_url}</p>
                    
                    <div class="mt-3 flex flex-wrap gap-2 text-xs">
                        <span class="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 font-mono text-[11px]">
                            Mode: <span class="text-cyan-400 font-bold uppercase">${src.crawl_mode}</span>
                        </span>
                        <span class="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 font-mono text-[11px]">
                            Articles: <span class="text-white font-bold">${src.article_count}</span>
                        </span>
                    </div>

                    ${src.feed_url ? `
                        <div class="mt-2 text-[11px] text-zinc-500 truncate font-mono">
                            Feed: <a href="${src.feed_url}" target="_blank" class="text-zinc-400 hover:text-cyan-400 underline">${src.feed_url}</a>
                        </div>
                    ` : ''}

                    <!-- Source Weight Bias Adjustment -->
                    <div class="mt-4 p-2.5 rounded-lg bg-zinc-950/90 border border-zinc-800 flex items-center justify-between gap-2">
                        <div>
                            <span class="text-[11px] font-mono text-zinc-400 block">Source Priority:</span>
                            <span id="src-bias-badge-${src.id}" class="text-[10px] ${weightColor} font-mono font-bold">${weightDisplay} pts bias</span>
                        </div>
                        <div class="flex items-center gap-1.5">
                            <input 
                                type="number" 
                                step="0.5" 
                                min="-10" 
                                max="10" 
                                value="${weightVal}" 
                                id="src-weight-input-${src.id}"
                                class="w-16 bg-zinc-900 border border-zinc-700 focus:border-cyan-500 rounded px-2 py-1 text-xs text-right font-mono font-bold text-white transition-colors"
                                onchange="updateSourceWeight('${src.id}', this.value, this)"
                                onkeydown="if(event.key==='Enter') updateSourceWeight('${src.id}', this.value, this)"
                            >
                            <button 
                                onclick="updateSourceWeight('${src.id}', document.getElementById('src-weight-input-${src.id}').value, document.getElementById('src-weight-input-${src.id}'))" 
                                class="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-cyan-400 text-xs font-mono font-medium transition-all"
                                title="Save weight bias">
                                Save
                            </button>
                        </div>
                    </div>

                    <div class="mt-3 text-[10px] text-zinc-500 font-mono">
                        Last Crawled: ${lastCrawled}
                    </div>
                </div>

                <div class="mt-4 pt-3 border-t border-zinc-800/80 flex items-center justify-between">
                    <button onclick="crawlSource('${src.id}')" class="px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-cyan-400 text-xs font-mono font-medium flex items-center gap-1.5 transition-all">
                        <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i> Crawl Now
                    </button>
                    <button onclick="deleteSource('${src.id}')" class="p-1.5 text-zinc-500 hover:text-rose-400 hover:bg-rose-950/40 rounded transition-all" title="Delete Source">
                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    lucide.createIcons();
}

async function updateSourceWeight(sourceId, newWeight, inputEl = null) {
    const weightVal = parseFloat(newWeight) || 0.0;
    try {
        const res = await fetch(`${API_BASE}/sources/${sourceId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ weight: weightVal })
        });
        if (!res.ok) throw new Error('Failed to update source weight');
        const updated = await res.json();
        
        const src = state.sources.find(s => s.id === sourceId);
        if (src) src.weight = updated.weight;
        
        // Targeted DOM feedback without expensive full re-render
        const badge = document.getElementById(`src-bias-badge-${sourceId}`);
        if (badge) {
            badge.textContent = `${weightVal > 0 ? '+' : ''}${weightVal} pts bias`;
            badge.className = `text-[10px] font-mono font-bold ${weightVal > 0 ? 'text-cyan-400' : (weightVal < 0 ? 'text-rose-400' : 'text-zinc-400')}`;
        }
        if (inputEl) {
            inputEl.classList.add('border-emerald-500', 'text-emerald-400');
            setTimeout(() => inputEl.classList.remove('border-emerald-500', 'text-emerald-400'), 1200);
        }
        populateSandboxSources();
        showToast(`Source bias updated to ${weightVal > 0 ? '+' : ''}${weightVal} pts`, 'success');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// Render Keywords in an Informational Layout with Inline Editable Weights
function renderKeywords() {
    const container = document.getElementById('keywords-list');
    const countBadge = document.getElementById('kw-count-badge');
    if (!container) return;

    if (countBadge) countBadge.textContent = `${state.keywords.length} rules active`;

    if (state.keywords.length === 0) {
        container.innerHTML = `
            <div class="p-8 text-center text-zinc-500 font-mono text-xs">
                No active keyword rules defined. Add a phrase above to curate incoming articles.
            </div>
        `;
        return;
    }

    container.innerHTML = state.keywords.map(kw => {
        let typeBadge = '';
        if (kw.is_required) {
            typeBadge = '<span class="px-2 py-0.5 rounded bg-emerald-950/70 border border-emerald-800 text-emerald-300 font-mono text-[10px] font-semibold tracking-wider">[+] REQUIRED</span>';
        } else if (kw.is_excluded) {
            typeBadge = '<span class="px-2 py-0.5 rounded bg-rose-950/70 border border-rose-800 text-rose-300 font-mono text-[10px] font-semibold tracking-wider">[-] EXCLUDED</span>';
        } else {
            typeBadge = '<span class="px-2 py-0.5 rounded bg-cyan-950/70 border border-cyan-800 text-cyan-300 font-mono text-[10px] font-semibold tracking-wider">WEIGHTED</span>';
        }

        const dateStr = kw.created_at ? new Date(kw.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' }) : '';

        return `
            <div class="p-3.5 sm:px-5 sm:py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-zinc-900/40 transition-colors">
                <div class="flex items-center gap-3 min-w-0">
                    <div class="shrink-0">${typeBadge}</div>
                    <div class="min-w-0">
                        <div class="text-sm font-semibold text-white truncate" title="${kw.term}">
                            ${kw.term}
                        </div>
                        <div class="text-[11px] font-mono text-zinc-500 flex items-center gap-2 mt-0.5">
                            <span>Match: <span class="text-zinc-400 uppercase">${kw.match_type}</span></span>
                            ${dateStr ? `<span>&bull; Added ${dateStr}</span>` : ''}
                        </div>
                    </div>
                </div>

                <div class="flex items-center gap-3 shrink-0 self-end sm:self-auto">
                    ${(!kw.is_required && !kw.is_excluded) ? `
                        <div class="flex items-center gap-2">
                            <span class="text-[11px] font-mono text-zinc-400">Weight:</span>
                            <input 
                                type="number" 
                                step="0.5" 
                                min="-10" 
                                max="10" 
                                value="${kw.weight}" 
                                id="kw-weight-input-${kw.id}"
                                class="w-20 bg-zinc-900 border border-zinc-700 focus:border-cyan-500 rounded px-2 py-1 text-xs text-right font-mono font-bold text-cyan-400 transition-colors"
                                onchange="updateKeywordWeight('${kw.id}', this.value, this)"
                                onkeydown="if(event.key==='Enter') updateKeywordWeight('${kw.id}', this.value, this)"
                            >
                            <button 
                                onclick="updateKeywordWeight('${kw.id}', document.getElementById('kw-weight-input-${kw.id}').value, document.getElementById('kw-weight-input-${kw.id}'))" 
                                class="px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-cyan-400 text-xs font-mono font-medium transition-all"
                                title="Save weight multiplier">
                                Save
                            </button>
                        </div>
                    ` : `
                        <div class="text-xs font-mono text-zinc-500 px-3 py-1 bg-zinc-900/60 rounded border border-zinc-800">
                            ${kw.is_required ? 'Mandatory (+5.0 pts)' : 'Instant Discard (-1.0)'}
                        </div>
                    `}

                    <button onclick="deleteKeyword('${kw.id}')" class="p-1.5 text-zinc-500 hover:text-rose-400 hover:bg-rose-950/40 rounded transition-all ml-1" title="Delete Rule">
                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>
        `;
    }).join('');

    lucide.createIcons();
}

async function updateKeywordWeight(keywordId, newWeight, inputEl = null) {
    const weightVal = parseFloat(newWeight) || 0.0;
    try {
        const res = await fetch(`${API_BASE}/keywords/${keywordId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ weight: weightVal })
        });
        if (!res.ok) throw new Error('Failed to update keyword weight');
        const updated = await res.json();
        
        const kw = state.keywords.find(k => k.id === keywordId);
        if (kw) kw.weight = updated.weight;

        // Targeted visual feedback without stealing input focus or full re-render
        if (inputEl) {
            inputEl.classList.add('border-emerald-500', 'text-emerald-400');
            setTimeout(() => inputEl.classList.remove('border-emerald-500', 'text-emerald-400'), 1200);
        }
        showToast(`Rule "${kw ? kw.term : ''}" weight updated to ${weightVal > 0 ? '+' : ''}${weightVal}x`, 'success');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// --- Hyper-Optimized Interactive Curves Engine (Article Age & Length) ---
const graphConfigs = {
    age: {
        containerId: 'age-graph-container',
        svgId: 'age-graph-svg',
        tooltipId: 'age-graph-tooltip',
        editorId: 'age-points-editor',
        curveKey: 'age_curve',
        xMin: 0,
        xMax: 30,
        yMin: -10,
        yMax: 10,
        xUnit: 'd',
        xLabel: 'Days',
        xStep: 0.5,
        yStep: 0.5,
        accentColor: '#06b6d4',
        gradientId: 'cyan-curve-grad',
        xTicks: [0, 5, 10, 15, 20, 25, 30]
    },
    length: {
        containerId: 'length-graph-container',
        svgId: 'length-graph-svg',
        tooltipId: 'length-graph-tooltip',
        editorId: 'length-points-editor',
        curveKey: 'length_curve',
        xMin: 0,
        xMax: 12000,
        yMin: -10,
        yMax: 10,
        xUnit: 'w',
        xLabel: 'Words',
        xStep: 50,
        yStep: 0.5,
        accentColor: '#8b5cf6',
        gradientId: 'violet-curve-grad',
        xTicks: [0, 2000, 4000, 6000, 8000, 10000, 12000]
    }
};

function mapGraphCoords(config, p) {
    const { left, top, plotWidth, plotHeight } = GRAPH_LAYOUT;
    const x = left + ((p.x - config.xMin) / (config.xMax - config.xMin)) * plotWidth;
    const y = top + ((config.yMax - p.y) / (config.yMax - config.yMin)) * plotHeight;
    return { x, y };
}

function unmapGraphCoords(config, pt) {
    const { left, top, plotWidth, plotHeight } = GRAPH_LAYOUT;
    let dataX = config.xMin + ((pt.x - left) / plotWidth) * (config.xMax - config.xMin);
    let dataY = config.yMax - ((pt.y - top) / plotHeight) * (config.yMax - config.yMin);

    dataX = Math.round(dataX / config.xStep) * config.xStep;
    dataY = Math.round(dataY / config.yStep) * config.yStep;
    dataX = Math.max(config.xMin, Math.min(config.xMax, dataX));
    dataY = Math.max(config.yMin, Math.min(config.yMax, dataY));
    return { x: dataX, y: dataY };
}

function renderCurves() {
    initSingleCurveGraph('age');
    initSingleCurveGraph('length');
}

// Builds the SVG DOM skeleton once
function initSingleCurveGraph(type) {
    const config = graphConfigs[type];
    const svg = document.getElementById(config.svgId);
    if (!svg) return;

    const { width, height, left, right, top, bottom, plotWidth, plotHeight } = GRAPH_LAYOUT;
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

    const svgSkeleton = `
        <defs>
            <linearGradient id="${config.gradientId}" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="${config.accentColor}" stop-opacity="0.35" />
                <stop offset="100%" stop-color="${config.accentColor}" stop-opacity="0.0" />
            </linearGradient>
        </defs>

        <!-- Static Grid Lines (Y-Axis) -->
        <g class="grid-group">
            ${[-10, -5, 0, 5, 10].map(yVal => {
                const yPos = top + ((config.yMax - yVal) / (config.yMax - config.yMin)) * plotHeight;
                const isZero = (yVal === 0);
                return `
                    <line x1="${left}" y1="${yPos}" x2="${left + plotWidth}" y2="${yPos}" class="${isZero ? 'curve-zero-line' : 'curve-grid-line'}" />
                    <text x="${left - 8}" y="${yPos + 3}" text-anchor="end" class="curve-axis-label font-mono">${yVal > 0 ? '+' : ''}${yVal}</text>
                `;
            }).join('')}

            <!-- Static Grid Lines (X-Axis) -->
            ${config.xTicks.map(xVal => {
                const xPos = left + ((xVal - config.xMin) / (config.xMax - config.xMin)) * plotWidth;
                const label = type === 'length' && xVal >= 1000 ? `${xVal / 1000}k` : `${xVal}${config.xUnit}`;
                return `
                    <line x1="${xPos}" y1="${top}" x2="${xPos}" y2="${top + plotHeight}" class="curve-grid-line" />
                    <text x="${xPos}" y="${top + plotHeight + 16}" text-anchor="middle" class="curve-axis-label font-mono">${label}</text>
                `;
            }).join('')}
        </g>

        <!-- Ghost background capture for adding points -->
        <rect x="${left}" y="${top}" width="${plotWidth}" height="${plotHeight}" fill="transparent" class="curve-handle-ghost" data-type="${type}" />

        <!-- Dynamic elements layer (Fast attribute updates) -->
        <polygon id="${type}-curve-area" class="curve-area" fill="url(#${config.gradientId})" />
        <path id="${type}-curve-glow" class="curve-path-glow" stroke="${config.accentColor}" stroke-opacity="0.25" stroke-width="6" />
        <path id="${type}-curve-core" class="curve-path-core" stroke="${config.accentColor}" stroke-width="2.5" />
        <g id="${type}-points-group"></g>
    `;

    svg.innerHTML = svgSkeleton;
    state.curvesInitialized[type] = true;

    updateCurveVisuals(type);
    renderCurvePointsEditor(type);
}

// High-speed attribute updater: mutates SVG paths/circles directly in < 0.05ms
function updateCurveVisuals(type) {
    const config = graphConfigs[type];
    const pts = state.curves[config.curveKey] || [];
    if (pts.length === 0) return;

    const { top, plotHeight } = GRAPH_LAYOUT;
    const zeroY = top + ((config.yMax - 0) / (config.yMax - config.yMin)) * plotHeight;
    const svgPts = pts.map(p => mapGraphCoords(config, p));

    const pathD = `M ${svgPts[0].x} ${svgPts[0].y} ` + svgPts.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ');
    const areaPoints = `${svgPts[0].x},${zeroY} ` + svgPts.map(p => `${p.x},${p.y}`).join(' ') + ` ${svgPts[svgPts.length - 1].x},${zeroY}`;

    const areaEl = document.getElementById(`${type}-curve-area`);
    const glowEl = document.getElementById(`${type}-curve-glow`);
    const coreEl = document.getElementById(`${type}-curve-core`);
    const pointsGroup = document.getElementById(`${type}-points-group`);

    if (areaEl) areaEl.setAttribute('points', areaPoints);
    if (glowEl) glowEl.setAttribute('d', pathD);
    if (coreEl) coreEl.setAttribute('d', pathD);

    if (pointsGroup) {
        let circles = pointsGroup.querySelectorAll('circle');
        if (circles.length !== pts.length) {
            pointsGroup.innerHTML = pts.map((p, i) => `
                <circle 
                    cx="${svgPts[i].x}" 
                    cy="${svgPts[i].y}" 
                    r="6" 
                    fill="#09090b" 
                    stroke="${config.accentColor}" 
                    stroke-width="2.5" 
                    class="curve-point" 
                    data-type="${type}" 
                    data-index="${i}"
                ></circle>
            `).join('');
        } else {
            for (let i = 0; i < circles.length; i++) {
                circles[i].setAttribute('cx', svgPts[i].x);
                circles[i].setAttribute('cy', svgPts[i].y);
                circles[i].dataset.index = i;
            }
        }
    }
}

function renderCurvePointsEditor(type) {
    const config = graphConfigs[type];
    const editor = document.getElementById(config.editorId);
    if (!editor) return;

    const points = state.curves[config.curveKey] || [];

    editor.innerHTML = points.map((p, idx) => `
        <div class="flex items-center gap-2 p-1.5 px-2.5 rounded bg-zinc-900/60 border border-zinc-800 text-xs font-mono">
            <span class="text-zinc-500 w-5 shrink-0">#${idx + 1}</span>
            <span class="text-zinc-400">X:</span>
            <input 
                type="number" 
                step="${config.xStep}" 
                min="${config.xMin}" 
                max="${config.xMax}" 
                value="${p.x}" 
                class="w-20 bg-zinc-950 border border-zinc-700 focus:border-cyan-500 rounded px-1.5 py-0.5 text-right text-white font-mono"
                onchange="manualUpdateCurvePoint('${config.curveKey}', ${idx}, 'x', this.value)"
            >
            <span class="text-zinc-500 shrink-0">${config.xUnit}</span>
            
            <span class="text-zinc-400 ml-2">Y:</span>
            <input 
                type="number" 
                step="${config.yStep}" 
                min="${config.yMin}" 
                max="${config.yMax}" 
                value="${p.y}" 
                class="w-16 bg-zinc-950 border border-zinc-700 focus:border-cyan-500 rounded px-1.5 py-0.5 text-right font-bold ${p.y > 0 ? 'text-cyan-400' : (p.y < 0 ? 'text-rose-400' : 'text-zinc-400')}"
                onchange="manualUpdateCurvePoint('${config.curveKey}', ${idx}, 'y', this.value)"
            >
            <span class="text-zinc-500 shrink-0">pts</span>

            <button onclick="removeCurvePoint('${config.curveKey}', ${idx})" class="ml-auto text-zinc-500 hover:text-rose-400 p-1 transition-colors" title="Remove point">
                &times;
            </button>
        </div>
    `).join('');
}

function manualUpdateCurvePoint(curveKey, index, field, value) {
    const pts = state.curves[curveKey];
    if (!pts || !pts[index]) return;

    const num = parseFloat(value);
    if (isNaN(num)) return;

    pts[index][field] = num;
    pts.sort((a, b) => a.x - b.x);

    const type = curveKey === 'age_curve' ? 'age' : 'length';
    updateCurveVisuals(type);
}

function removeCurvePoint(curveKey, index) {
    const pts = state.curves[curveKey];
    if (!pts) return;
    if (pts.length <= 2) {
        showToast('A minimum of 2 control points is required.', 'warn');
        return;
    }
    pts.splice(index, 1);
    const type = curveKey === 'age_curve' ? 'age' : 'length';
    updateCurveVisuals(type);
    renderCurvePointsEditor(type);
}

function addCurvePointPrompt(type) {
    const config = graphConfigs[type];
    const pts = state.curves[config.curveKey];
    let newX = config.xMin + (config.xMax - config.xMin) / 2;
    if (pts.length >= 2) {
        newX = Math.round((pts[0].x + pts[pts.length - 1].x) / 2);
    }
    pts.push({ x: newX, y: 0.0 });
    pts.sort((a, b) => a.x - b.x);
    updateCurveVisuals(type);
    renderCurvePointsEditor(type);
    showToast(`Added point at ${newX}${config.xUnit}. Drag to adjust.`, 'info');
}

function resetAgeCurve() {
    state.curves.age_curve = JSON.parse(JSON.stringify(DEFAULT_AGE_PRESET));
    updateCurveVisuals('age');
    renderCurvePointsEditor('age');
    showToast('Reset article age curve to default decay.', 'info');
}

function resetLengthCurve() {
    state.curves.length_curve = JSON.parse(JSON.stringify(DEFAULT_LENGTH_PRESET));
    updateCurveVisuals('length');
    renderCurvePointsEditor('length');
    showToast('Reset article length curve to default.', 'info');
}

async function saveCurvesToServer() {
    try {
        const payload = {
            age_curve: state.curves.age_curve,
            length_curve: state.curves.length_curve
        };
        const res = await fetch(`${API_BASE}/curation/curves`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Failed to save curves');
        showToast('Curation curves saved successfully!', 'success');
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// 60-120fps Batched Pointer Move Engine via requestAnimationFrame
function initGraphGlobalListeners() {
    let activeDrag = null;
    let pendingEvt = null;
    let rafScheduled = false;

    const getSvgCoords = (svg, evt) => {
        const pt = svg.createSVGPoint();
        const clientX = evt.touches ? evt.touches[0].clientX : evt.clientX;
        const clientY = evt.touches ? evt.touches[0].clientY : evt.clientY;
        pt.x = clientX;
        pt.y = clientY;
        return pt.matrixTransform(svg.getScreenCTM().inverse());
    };

    const processPointerMove = () => {
        rafScheduled = false;
        if (!activeDrag || !pendingEvt) return;

        const { type, idx, config, svg } = activeDrag;
        const pt = getSvgCoords(svg, pendingEvt);
        const { x: dataX, y: dataY } = unmapGraphCoords(config, pt);

        state.curves[config.curveKey][idx] = { x: dataX, y: dataY };
        updateCurveVisuals(type);

        // Hardware-accelerated tooltip positioning via transform3d
        const tooltip = document.getElementById(config.tooltipId);
        if (tooltip) {
            tooltip.classList.remove('hidden');
            const posX = Math.max(10, Math.min(500, pt.x - 25));
            const posY = Math.max(5, pt.y - 35);
            tooltip.style.transform = `translate3d(${posX}px, ${posY}px, 0)`;
            tooltip.textContent = `${dataX}${config.xUnit} → ${dataY > 0 ? '+' : ''}${dataY} pts`;
        }
    };

    const handlePointerDown = (e) => {
        if (e.target && e.target.classList.contains('curve-point')) {
            const type = e.target.dataset.type;
            const idx = parseInt(e.target.dataset.index, 10);
            const config = graphConfigs[type];
            const svg = document.getElementById(config.svgId);
            activeDrag = { type, idx, config, svg, element: e.target };
            e.target.classList.add('dragging');
            e.preventDefault();
        } else if (e.target && e.target.classList.contains('curve-handle-ghost')) {
            const type = e.target.dataset.type;
            const config = graphConfigs[type];
            const svg = document.getElementById(config.svgId);
            const pt = getSvgCoords(svg, e);
            const { x: dataX, y: dataY } = unmapGraphCoords(config, pt);

            state.curves[config.curveKey].push({ x: dataX, y: dataY });
            state.curves[config.curveKey].sort((a, b) => a.x - b.x);
            updateCurveVisuals(type);
            renderCurvePointsEditor(type);
            showToast(`Added point at ${dataX}${config.xUnit}, ${dataY > 0 ? '+' : ''}${dataY} pts`, 'info');
        }
    };

    const handlePointerMove = (e) => {
        if (!activeDrag) return;
        pendingEvt = e;
        if (!rafScheduled) {
            rafScheduled = true;
            requestAnimationFrame(processPointerMove);
        }
    };

    const handlePointerUp = () => {
        if (activeDrag) {
            const { type, config } = activeDrag;
            state.curves[config.curveKey].sort((a, b) => a.x - b.x);
            updateCurveVisuals(type);
            renderCurvePointsEditor(type);

            const tooltip = document.getElementById(config.tooltipId);
            if (tooltip) tooltip.classList.add('hidden');

            activeDrag = null;
            pendingEvt = null;
        }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('mousemove', handlePointerMove, { passive: true });
    document.addEventListener('mouseup', handlePointerUp);

    document.addEventListener('touchstart', handlePointerDown, { passive: false });
    document.addEventListener('touchmove', handlePointerMove, { passive: true });
    document.addEventListener('touchend', handlePointerUp);

    document.addEventListener('dblclick', (e) => {
        if (e.target && e.target.classList.contains('curve-point')) {
            const type = e.target.dataset.type;
            const idx = parseInt(e.target.dataset.index, 10);
            const config = graphConfigs[type];
            removeCurvePoint(config.curveKey, idx);
        }
    });
}

// --- Recalculate Scores Trigger ---
async function recalculateScores() {
    const btn = document.getElementById('btn-recalculate-scores');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i data-lucide="refresh-cw" class="w-3.5 h-3.5 animate-spin"></i> Recalculating...';
    }
    showToast('Recalculating article scores across active curation weights...', 'info');
    try {
        const res = await fetch(`${API_BASE}/curation/recalculate-scores`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message, 'success');
            appendLog('success', `⚡ Recalculated scores for ${data.updated_articles} unbundled articles.`);
            fetchArticles();
        } else {
            throw new Error(data.detail || 'Recalculation failed');
        }
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i data-lucide="refresh-cw" class="w-3.5 h-3.5 text-violet-400"></i> Recalculate Scores';
            lucide.createIcons();
        }
    }
}

// --- Daily Editions File Manager ---
function extractFileName(filePath) {
    if (!filePath) return 'edition.epub';
    const parts = filePath.split(/[/\\]/);
    return parts[parts.length - 1] || 'edition.epub';
}

function parseIsoTimestamp(isoStr) {
    if (!isoStr) return null;
    const normalized = (typeof isoStr === 'string' && !isoStr.endsWith('Z') && !isoStr.includes('+') && !/\-\d{2}:\d{2}$/.test(isoStr))
        ? `${isoStr}Z`
        : isoStr;
    const dt = new Date(normalized);
    return isNaN(dt.getTime()) ? null : dt;
}

function formatDateTimeFull(isoStr) {
    const dt = parseIsoTimestamp(isoStr);
    if (!dt) return '—';
    return dt.toLocaleString([], {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function formatFileSize(bytes) {
    const num = Number(bytes) || 0;
    if (num < 1024 * 1024) {
        return `${Math.max(1, Math.round(num / 1024))} KB`;
    }
    return `${(num / 1024 / 1024).toFixed(2)} MB`;
}

function setEditionsViewMode(mode) {
    state.editionsViewMode = mode === 'grid' ? 'grid' : 'list';
    const listBtn = document.getElementById('ed-view-list-btn');
    const gridBtn = document.getElementById('ed-view-grid-btn');
    if (listBtn && gridBtn) {
        if (state.editionsViewMode === 'list') {
            listBtn.className = 'px-2.5 py-1 rounded-md text-xs font-mono flex items-center gap-1 bg-zinc-800 text-cyan-400 transition-all';
            gridBtn.className = 'px-2.5 py-1 rounded-md text-xs font-mono flex items-center gap-1 text-zinc-400 hover:text-zinc-200 transition-all';
        } else {
            gridBtn.className = 'px-2.5 py-1 rounded-md text-xs font-mono flex items-center gap-1 bg-zinc-800 text-cyan-400 transition-all';
            listBtn.className = 'px-2.5 py-1 rounded-md text-xs font-mono flex items-center gap-1 text-zinc-400 hover:text-zinc-200 transition-all';
        }
    }
    renderEditions();
}

function handleEditionsFilterChange() {
    const searchInput = document.getElementById('ed-search-input');
    const sortSelect = document.getElementById('ed-sort-select');
    if (searchInput) state.editionsSearchQuery = searchInput.value.trim().toLowerCase();
    if (sortSelect) state.editionsSortBy = sortSelect.value;
    renderEditions();
}

function getFilteredAndSortedEditions() {
    const q = state.editionsSearchQuery || '';
    const filtered = state.editions.filter(ed => {
        if (!q) return true;
        const fname = extractFileName(ed.file_path).toLowerCase();
        const title = (ed.title || '').toLowerCase();
        const date = (ed.edition_date || '').toLowerCase();
        return fname.includes(q) || title.includes(q) || date.includes(q);
    });

    const sortMode = state.editionsSortBy || 'created_desc';
    filtered.sort((a, b) => {
        const createdA = parseIsoTimestamp(a.created_at)?.getTime() || 0;
        const createdB = parseIsoTimestamp(b.created_at)?.getTime() || 0;
        const dlA = parseIsoTimestamp(a.last_downloaded_at || (a.download_timestamps && a.download_timestamps[0]))?.getTime() || 0;
        const dlB = parseIsoTimestamp(b.last_downloaded_at || (b.download_timestamps && b.download_timestamps[0]))?.getTime() || 0;

        switch (sortMode) {
            case 'created_asc':
                return createdA - createdB;
            case 'downloaded_desc':
                return dlB - dlA || createdB - createdA;
            case 'downloads_desc':
                return ((b.download_count || 0) - (a.download_count || 0)) || createdB - createdA;
            case 'size_desc':
                return ((b.file_size_bytes || 0) - (a.file_size_bytes || 0));
            case 'size_asc':
                return ((a.file_size_bytes || 0) - (b.file_size_bytes || 0));
            case 'created_desc':
            default:
                return createdB - createdA;
        }
    });

    return filtered;
}

function updateEditionsVaultStats() {
    const countEl = document.getElementById('ed-stat-count');
    const sizeEl = document.getElementById('ed-stat-size');
    const dlEl = document.getElementById('ed-stat-downloads');
    const lastDlEl = document.getElementById('ed-stat-last-dl');

    const totalFiles = state.editions.length;
    const totalBytes = state.editions.reduce((acc, ed) => acc + (ed.file_size_bytes || 0), 0);
    const totalDownloads = state.editions.reduce((acc, ed) => acc + (ed.download_count || 0), 0);

    let latestDlTime = 0;
    let latestDlStr = 'Never';
    state.editions.forEach(ed => {
        const rawTs = ed.last_downloaded_at || (ed.download_timestamps && ed.download_timestamps[0]);
        const dt = parseIsoTimestamp(rawTs);
        if (dt && dt.getTime() > latestDlTime) {
            latestDlTime = dt.getTime();
            latestDlStr = formatDateTimeFull(rawTs);
        }
    });

    if (countEl) countEl.textContent = `${totalFiles} ${totalFiles === 1 ? 'file' : 'files'}`;
    if (sizeEl) sizeEl.textContent = `${(totalBytes / 1024 / 1024).toFixed(2)} MB`;
    if (dlEl) dlEl.textContent = `${totalDownloads}`;
    if (lastDlEl) {
        lastDlEl.textContent = latestDlStr;
        lastDlEl.title = latestDlStr;
    }

    // Prune any selected IDs that no longer exist
    const validIds = new Set(state.editions.map(e => e.id));
    for (const id of state.selectedEditions) {
        if (!validIds.has(id)) state.selectedEditions.delete(id);
    }
    updateEditionSelectionToolbar();
}

function updateEditionSelectionToolbar() {
    const selCount = state.selectedEditions.size;
    const countBadge = document.getElementById('ed-selected-count');
    const bulkBtn = document.getElementById('ed-bulk-delete-btn');
    const bulkLabel = document.getElementById('ed-bulk-delete-label');
    const selectAllCb = document.getElementById('ed-select-all');

    if (countBadge) countBadge.textContent = `${selCount} selected`;
    if (bulkBtn) {
        if (selCount > 0) {
            bulkBtn.classList.remove('hidden');
            if (bulkLabel) bulkLabel.textContent = `Delete Selected (${selCount})`;
        } else {
            bulkBtn.classList.add('hidden');
        }
    }
    if (selectAllCb) {
        const visible = getFilteredAndSortedEditions();
        selectAllCb.checked = visible.length > 0 && visible.every(ed => state.selectedEditions.has(ed.id));
    }
}

function toggleSelectEdition(editionId, checked) {
    if (checked) {
        state.selectedEditions.add(editionId);
    } else {
        state.selectedEditions.delete(editionId);
    }
    updateEditionSelectionToolbar();
}

function toggleSelectAllEditions(checked) {
    const visible = getFilteredAndSortedEditions();
    visible.forEach(ed => {
        if (checked) {
            state.selectedEditions.add(ed.id);
        } else {
            state.selectedEditions.delete(ed.id);
        }
    });
    renderEditions();
}

function toggleDownloadHistoryDrawer(editionId) {
    if (state.expandedDownloadHistory.has(editionId)) {
        state.expandedDownloadHistory.delete(editionId);
    } else {
        state.expandedDownloadHistory.add(editionId);
    }
    renderEditions();
}

function onEditionDownloadClick(editionId) {
    setTimeout(() => {
        fetchEditions();
    }, 500);
}

async function deleteEdition(editionId, editionTitle = 'this digest') {
    if (!confirm(`Delete "${editionTitle}" and permanently remove its EPUB file from storage?`)) return;
    try {
        const res = await fetch(`${API_BASE}/editions/${editionId}`, { method: 'DELETE' });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Failed to delete edition');
        }
        state.selectedEditions.delete(editionId);
        state.expandedDownloadHistory.delete(editionId);
        showToast(`Deleted "${editionTitle}"`, 'info');
        fetchEditions();
    } catch (e) {
        showToast(`Delete failed: ${e.message}`, 'error');
    }
}

async function bulkDeleteSelectedEditions() {
    const ids = Array.from(state.selectedEditions);
    if (ids.length === 0) return;
    if (!confirm(`Permanently delete ${ids.length} selected EPUB ${ids.length === 1 ? 'file' : 'files'} from storage?`)) return;

    try {
        const res = await fetch(`${API_BASE}/editions/bulk-delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ edition_ids: ids })
        });
        if (!res.ok) throw new Error('Bulk delete failed');
        const data = await res.json();
        state.selectedEditions.clear();
        showToast(`Deleted ${data.deleted_count} EPUB ${data.deleted_count === 1 ? 'file' : 'files'}`, 'info');
        fetchEditions();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

function renderDownloadTimestampsBlock(ed) {
    const timestamps = Array.isArray(ed.download_timestamps) && ed.download_timestamps.length > 0
        ? ed.download_timestamps
        : (ed.last_downloaded_at ? [ed.last_downloaded_at] : []);
    const dlCount = ed.download_count || timestamps.length || 0;

    if (dlCount === 0 || timestamps.length === 0) {
        return `
            <div class="font-mono text-xs text-zinc-500 flex items-center gap-1.5">
                <i data-lucide="minus-circle" class="w-3.5 h-3.5 text-zinc-600"></i>
                <span>Never downloaded</span>
            </div>
        `;
    }

    const latestFormatted = formatDateTimeFull(timestamps[0]);
    const isExpanded = state.expandedDownloadHistory.has(ed.id);
    const hasMultiple = timestamps.length > 1;

    return `
        <div class="space-y-1">
            <div class="flex items-center gap-1.5 flex-wrap">
                <span class="font-mono text-xs text-emerald-400 flex items-center gap-1" title="Last downloaded at ${latestFormatted}">
                    <i data-lucide="download-cloud" class="w-3.5 h-3.5 shrink-0"></i>
                    <span>${latestFormatted}</span>
                </span>
                <span class="px-1.5 py-0.5 rounded bg-emerald-950/60 border border-emerald-800/70 text-[10px] font-mono text-emerald-300">
                    ${dlCount}x
                </span>
                ${hasMultiple ? `
                    <button onclick="toggleDownloadHistoryDrawer('${ed.id}')" class="text-[10px] font-mono text-cyan-400 hover:underline ml-0.5">
                        ${isExpanded ? 'Hide log' : `All (${timestamps.length})`}
                    </button>
                ` : ''}
            </div>
            ${(isExpanded && hasMultiple) ? `
                <div class="mt-1.5 p-2 rounded-lg bg-zinc-950/90 border border-zinc-800 space-y-1 max-h-28 overflow-y-auto">
                    <div class="text-[10px] font-mono text-zinc-400 uppercase tracking-wider">Download Timestamps:</div>
                    ${timestamps.map((ts, idx) => `
                        <div class="text-[11px] font-mono text-zinc-300 flex items-center justify-between gap-2">
                            <span class="text-zinc-500">#${timestamps.length - idx}</span>
                            <span>${formatDateTimeFull(ts)}</span>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
        </div>
    `;
}

function renderEditions() {
    const container = document.getElementById('editions-list');
    if (!container) return;

    updateEditionsVaultStats();

    if (state.editions.length === 0) {
        container.className = '';
        container.innerHTML = `
            <div class="py-16 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40">
                <i data-lucide="folder-open" class="w-10 h-10 text-zinc-600 mx-auto mb-3"></i>
                <p class="text-zinc-400 font-medium">EPUB Vault is empty</p>
                <p class="text-zinc-600 text-xs font-mono mt-1">Click "Compile New Digest" to bundle available articles into your first EPUB 3 file.</p>
                <button onclick="triggerCompileNow()" class="mt-4 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-mono font-semibold text-xs transition-all shadow-lg shadow-violet-600/30">
                    📚 Compile Edition Now
                </button>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    const filtered = getFilteredAndSortedEditions();
    if (filtered.length === 0) {
        container.className = '';
        container.innerHTML = `
            <div class="py-12 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40">
                <i data-lucide="search-x" class="w-8 h-8 text-zinc-600 mx-auto mb-2"></i>
                <p class="text-zinc-400 text-xs font-mono">No EPUB files match "${state.editionsSearchQuery}"</p>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    if (state.editionsViewMode === 'grid') {
        container.className = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5';
        container.innerHTML = filtered.map(ed => {
            const downloadUrl = `${API_BASE}/editions/${ed.id}/download`;
            const fileName = extractFileName(ed.file_path);
            const sizeFormatted = formatFileSize(ed.file_size_bytes);
            const compiledFormatted = formatDateTimeFull(ed.created_at);
            const coverImg = ed.cover_path ? `${API_BASE}/editions/${ed.id}/cover` : null;
            const isChecked = state.selectedEditions.has(ed.id);
            const safeTitle = (ed.title || '').replace(/'/g, "\\'");

            return `
                <div class="glass-panel rounded-xl overflow-hidden flex flex-col justify-between group border ${isChecked ? 'border-cyan-500/60' : 'border-white/5'} hover:border-cyan-500/30 transition-all">
                    <div>
                        <div class="relative w-full h-40 bg-zinc-950 overflow-hidden border-b border-zinc-800">
                            ${coverImg ? `
                                <img src="${coverImg}" alt="${ed.title} Cover" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500">
                            ` : `
                                <div class="w-full h-full flex items-center justify-center text-zinc-700">
                                    <i data-lucide="book" class="w-10 h-10"></i>
                                </div>
                            `}
                            <div class="absolute top-3 left-3 flex items-center gap-2 bg-zinc-950/85 backdrop-blur-md px-2.5 py-1 rounded-lg border border-white/10">
                                <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleSelectEdition('${ed.id}', this.checked)" class="rounded bg-zinc-900 border-zinc-700 text-cyan-500 focus:ring-0 cursor-pointer">
                                <span class="text-[10px] font-mono text-cyan-400 truncate max-w-[160px]" title="${fileName}">${fileName}</span>
                            </div>
                            <span class="absolute top-3 right-3 px-2 py-0.5 rounded bg-zinc-950/85 border border-white/10 text-[10px] font-mono text-zinc-200">
                                ${sizeFormatted}
                            </span>
                        </div>

                        <div class="p-4 space-y-3">
                            <div>
                                <div class="flex items-center justify-between gap-2">
                                    <span class="text-[11px] font-mono text-cyan-400">${ed.edition_date}</span>
                                    ${ed.sent_via_smtp ? `
                                        <span class="px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-400 text-[10px] font-mono flex items-center gap-1">
                                            <i data-lucide="check" class="w-3 h-3"></i> Sent to Kindle
                                        </span>
                                    ` : ''}
                                </div>
                                <h3 class="font-bold text-base text-white mt-0.5 group-hover:text-cyan-400 transition-colors truncate" title="${ed.title}">
                                    ${ed.title}
                                </h3>
                            </div>

                            <div class="flex flex-wrap gap-1.5 text-[11px] font-mono">
                                <span class="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">
                                    ${ed.article_count} Articles
                                </span>
                                <span class="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400">
                                    ${(ed.total_word_count || 0).toLocaleString()} words
                                </span>
                            </div>

                            <div class="p-2.5 rounded-lg bg-zinc-950/80 border border-zinc-800/90 space-y-1.5 text-xs">
                                <div class="flex items-center justify-between gap-2 font-mono text-[11px]">
                                    <span class="text-zinc-500">Compiled:</span>
                                    <span class="text-zinc-300">${compiledFormatted}</span>
                                </div>
                                <div class="pt-1 border-t border-zinc-800/70">
                                    <span class="text-[10px] font-mono text-zinc-500 block mb-0.5">Downloaded:</span>
                                    ${renderDownloadTimestampsBlock(ed)}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="p-4 pt-0">
                        <div class="flex items-center gap-1.5 border-t border-zinc-800/80 pt-3">
                            <button onclick="readEditionInBrowser('${ed.id}')" class="flex-1 py-1.5 px-2.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono font-medium flex items-center justify-center gap-1.5 transition-all" title="Read In Browser">
                                <i data-lucide="book-open" class="w-3.5 h-3.5 text-cyan-400"></i> Read
                            </button>
                            <a href="${downloadUrl}" download onclick="onEditionDownloadClick('${ed.id}')" class="py-1.5 px-2.5 rounded-lg bg-cyan-500/15 hover:bg-cyan-500/25 border border-cyan-500/30 text-cyan-300 text-xs font-mono flex items-center gap-1 transition-all" title="Download EPUB File">
                                <i data-lucide="download" class="w-3.5 h-3.5"></i>
                            </a>
                            <button onclick="sendEditionEmail('${ed.id}')" class="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-violet-400 hover:text-violet-300 transition-all" title="Send to Kindle via SMTP">
                                <i data-lucide="send" class="w-4 h-4"></i>
                            </button>
                            <button onclick="deleteEdition('${ed.id}', '${safeTitle}')" class="p-1.5 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-950/40 transition-all" title="Delete EPUB File">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        lucide.createIcons();
        return;
    }

    // Default File Manager Table View ('list')
    container.className = 'glass-panel rounded-xl overflow-hidden border border-white/10';
    container.innerHTML = `
        <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse">
                <thead>
                    <tr class="bg-zinc-900/90 border-b border-zinc-800 text-[11px] font-mono uppercase tracking-wider text-zinc-400">
                        <th class="py-3 pl-4 pr-2 w-8"></th>
                        <th class="py-3 px-3">Publication / EPUB File</th>
                        <th class="py-3 px-3">Specs &amp; Size</th>
                        <th class="py-3 px-3">Compiled Date-Time</th>
                        <th class="py-3 px-3">Downloaded Date-Time(s)</th>
                        <th class="py-3 px-3">Delivery</th>
                        <th class="py-3 pl-3 pr-4 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-zinc-800/80 text-xs">
                    ${filtered.map(ed => {
                        const downloadUrl = `${API_BASE}/editions/${ed.id}/download`;
                        const fileName = extractFileName(ed.file_path);
                        const sizeFormatted = formatFileSize(ed.file_size_bytes);
                        const compiledFormatted = formatDateTimeFull(ed.created_at);
                        const coverImg = ed.cover_path ? `${API_BASE}/editions/${ed.id}/cover` : null;
                        const isChecked = state.selectedEditions.has(ed.id);
                        const safeTitle = (ed.title || '').replace(/'/g, "\\'");

                        return `
                            <tr class="hover:bg-zinc-900/50 transition-colors ${isChecked ? 'bg-cyan-950/15' : ''}">
                                <td class="py-3.5 pl-4 pr-2 align-top">
                                    <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleSelectEdition('${ed.id}', this.checked)" class="mt-1 rounded bg-zinc-900 border-zinc-700 text-cyan-500 focus:ring-0 cursor-pointer">
                                </td>
                                <td class="py-3.5 px-3 align-top">
                                    <div class="flex items-start gap-3">
                                        <div onclick="readEditionInBrowser('${ed.id}')" class="w-10 h-14 rounded bg-zinc-950 border border-zinc-800 overflow-hidden shrink-0 cursor-pointer flex items-center justify-center hover:border-cyan-500/50 transition-all" title="Click to Read In Browser">
                                            ${coverImg ? `
                                                <img src="${coverImg}" alt="Cover" class="w-full h-full object-cover">
                                            ` : `
                                                <i data-lucide="file-text" class="w-4 h-4 text-cyan-400"></i>
                                            `}
                                        </div>
                                        <div class="min-w-0">
                                            <div class="font-semibold text-sm text-white hover:text-cyan-400 cursor-pointer transition-colors truncate max-w-xs" onclick="readEditionInBrowser('${ed.id}')" title="${ed.title}">
                                                ${ed.title}
                                            </div>
                                            <div class="font-mono text-[11px] text-cyan-400/90 flex items-center gap-1.5 mt-0.5 truncate max-w-xs" title="${ed.file_path}">
                                                <i data-lucide="file-archive" class="w-3 h-3 shrink-0"></i>
                                                <span class="truncate">${fileName}</span>
                                            </div>
                                            <div class="font-mono text-[10px] text-zinc-500 mt-0.5">
                                                Issue Date: ${ed.edition_date}
                                            </div>
                                        </div>
                                    </div>
                                </td>
                                <td class="py-3.5 px-3 align-top font-mono">
                                    <div class="text-white font-semibold">${sizeFormatted}</div>
                                    <div class="text-[11px] text-zinc-400 mt-0.5">${ed.article_count} ${ed.article_count === 1 ? 'chapter' : 'chapters'}</div>
                                    <div class="text-[10px] text-zinc-500">${(ed.total_word_count || 0).toLocaleString()} words</div>
                                </td>
                                <td class="py-3.5 px-3 align-top font-mono">
                                    <div class="text-zinc-200 flex items-center gap-1.5">
                                        <i data-lucide="calendar-clock" class="w-3.5 h-3.5 text-violet-400 shrink-0"></i>
                                        <span>${compiledFormatted}</span>
                                    </div>
                                </td>
                                <td class="py-3.5 px-3 align-top">
                                    ${renderDownloadTimestampsBlock(ed)}
                                </td>
                                <td class="py-3.5 px-3 align-top font-mono">
                                    ${ed.sent_via_smtp ? `
                                        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-950/60 border border-emerald-800 text-emerald-400 text-[11px]">
                                            <i data-lucide="check" class="w-3 h-3"></i> Kindle Sent
                                        </span>
                                    ` : `
                                        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-400 text-[11px]">
                                            <i data-lucide="hard-drive" class="w-3 h-3 text-cyan-400"></i> Local Vault
                                        </span>
                                    `}
                                </td>
                                <td class="py-3.5 pl-3 pr-4 align-top text-right">
                                    <div class="inline-flex items-center justify-end gap-1.5">
                                        <button onclick="readEditionInBrowser('${ed.id}')" class="px-2.5 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono flex items-center gap-1 transition-all" title="Read In Browser">
                                            <i data-lucide="book-open" class="w-3.5 h-3.5 text-cyan-400"></i>
                                            <span class="hidden xl:inline">Read</span>
                                        </button>
                                        <a href="${downloadUrl}" download onclick="onEditionDownloadClick('${ed.id}')" class="px-2.5 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-mono font-semibold text-xs flex items-center gap-1 transition-all shadow-sm shadow-cyan-500/20" title="Download EPUB">
                                            <i data-lucide="download" class="w-3.5 h-3.5"></i>
                                            <span class="hidden xl:inline">Download</span>
                                        </a>
                                        <button onclick="sendEditionEmail('${ed.id}')" class="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-violet-400 hover:text-violet-300 transition-all" title="Send to Kindle via SMTP">
                                            <i data-lucide="send" class="w-3.5 h-3.5"></i>
                                        </button>
                                        <button onclick="deleteEdition('${ed.id}', '${safeTitle}')" class="p-1.5 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-950/40 transition-all" title="Delete EPUB File">
                                            <i data-lucide="trash-2" class="w-4 h-4"></i>
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;

    lucide.createIcons();
}

function renderDashboardEditions() {
    const container = document.getElementById('dashboard-latest-edition');
    if (!container) return;

    if (state.editions.length === 0) {
        container.innerHTML = `
            <div class="p-6 text-center text-zinc-500 text-sm font-mono">
                No editions compiled yet today. Click "Compile Digest Now" to generate your first issue.
            </div>
        `;
        return;
    }

    const latest = state.editions[0];
    const downloadUrl = `${API_BASE}/editions/${latest.id}/download`;
    const compiledStr = formatDateTimeFull(latest.created_at);
    const lastDlRaw = latest.last_downloaded_at || (latest.download_timestamps && latest.download_timestamps[0]);
    const lastDlStr = lastDlRaw ? formatDateTimeFull(lastDlRaw) : 'Not downloaded yet';
    const safeTitle = (latest.title || '').replace(/'/g, "\\'");

    container.innerHTML = `
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
                <div class="flex items-center gap-2">
                    <span class="text-xs font-mono text-cyan-400 uppercase tracking-wider">Latest Digest</span>
                    <span class="text-[11px] font-mono text-zinc-500">&bull; ${extractFileName(latest.file_path)}</span>
                </div>
                <h4 class="text-lg font-bold text-white mt-0.5">${latest.title}</h4>
                <p class="text-xs text-zinc-400 font-mono mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span>${latest.article_count} Articles</span>
                    <span>&bull; ${formatFileSize(latest.file_size_bytes)}</span>
                    <span>&bull; Compiled: <strong class="text-zinc-200">${compiledStr}</strong></span>
                    <span>&bull; Downloaded: <strong class="${lastDlRaw ? 'text-emerald-400' : 'text-zinc-500'}">${lastDlStr}</strong></span>
                </p>
            </div>
            <div class="flex items-center gap-2 shrink-0">
                <button onclick="readEditionInBrowser('${latest.id}')" class="px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono flex items-center gap-1.5 transition-all" title="Read In Browser">
                    <i data-lucide="book-open" class="w-4 h-4 text-cyan-400"></i> Read
                </button>
                <a href="${downloadUrl}" download onclick="onEditionDownloadClick('${latest.id}')" class="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-semibold text-xs flex items-center gap-2 transition-all shadow-lg shadow-cyan-500/20">
                    <i data-lucide="download" class="w-4 h-4"></i> Download
                </a>
                <button onclick="sendEditionEmail('${latest.id}')" class="px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs flex items-center gap-1.5 transition-all" title="Send to Device">
                    <i data-lucide="send" class="w-4 h-4 text-violet-400"></i>
                </button>
                <button onclick="deleteEdition('${latest.id}', '${safeTitle}')" class="p-2 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-950/40 transition-all" title="Delete Edition">
                    <i data-lucide="trash-2" class="w-4 h-4"></i>
                </button>
            </div>
        </div>
    `;
    lucide.createIcons();
}

function renderArticles() {
    const container = document.getElementById('articles-list');
    if (!container) return;

    if (state.articles.length === 0) {
        container.innerHTML = `
            <div class="py-16 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40">
                <p class="text-zinc-400 font-medium">No articles ingested yet</p>
                <p class="text-zinc-600 text-sm mt-1">Trigger a crawl on one of your sources to pull in recent posts.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = state.articles.map(art => {
        return `
            <div class="glass-panel p-4 rounded-xl flex items-start justify-between gap-4 border border-zinc-800/80 hover:border-cyan-500/30 transition-all">
                <div class="flex-1">
                    <div class="flex items-center gap-2">
                        <span class="px-2 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-[11px] font-mono text-cyan-400">
                            ${art.source_name || 'Web'}
                        </span>
                        <span class="px-2 py-0.5 rounded ${art.is_bundled ? 'bg-zinc-800 text-zinc-400' : 'bg-violet-950/60 text-violet-300 border border-violet-800'} text-[11px] font-mono">
                            ${art.is_bundled ? 'Bundled' : 'Ready for Daily Edition'}
                        </span>
                        <span class="text-xs font-mono text-zinc-400 ml-auto">
                            Score: <strong class="text-white">${art.relevance_score}</strong>
                        </span>
                    </div>

                    <h4 class="text-base font-semibold text-white mt-2 hover:text-cyan-400 transition-colors">
                        <a href="${art.url}" target="_blank">${art.title}</a>
                    </h4>

                    ${art.excerpt ? `<p class="text-xs text-zinc-400 mt-1 line-clamp-2">${art.excerpt}</p>` : ''}

                    <div class="mt-3 flex items-center gap-4 text-[11px] text-zinc-500 font-mono">
                        ${(art.published_at || art.created_at) ? `<span>${new Date(art.published_at || art.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</span>` : ''}
                        <span>~${Math.max(1, Math.round(art.word_count / 220))} min read</span>
                        <span>${art.word_count} words</span>
                        ${art.author ? `<span>Author: ${art.author}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// --- Action Triggers ---
async function triggerCrawlAll() {
    showToast('Starting ingestion across all active sources...', 'info');
    appendLog('info', '⚡ Ingestion triggered for all active sources');
    try {
        await fetch(`${API_BASE}/settings/run-pipeline`, { method: 'POST' });
    } catch (e) {
        showToast('Failed to trigger pipeline', 'error');
    }
}

async function triggerCompileNow() {
    showToast('Compiling Daily EPUB edition...', 'info');
    appendLog('info', '📚 Compiling Daily EPUB edition now...');
    try {
        await fetch(`${API_BASE}/editions/build-now`, { method: 'POST' });
    } catch (e) {
        showToast('Compilation request failed', 'error');
    }
}

async function resetBundledArticles() {
    try {
        const res = await fetch(`${API_BASE}/articles/reset-bundled`, { method: 'POST' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to clear bundled state');
        showToast(data.message || `Cleared bundled flag on ${data.reset_count} articles.`, 'success');
        await fetchArticles();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function crawlSource(sourceId) {
    showToast('Crawling source in background...', 'info');
    try {
        await fetch(`${API_BASE}/sources/${sourceId}/crawl`, { method: 'POST' });
    } catch (e) {
        showToast('Failed to start crawl', 'error');
    }
}

async function deleteSource(sourceId) {
    if (!confirm('Are you sure you want to remove this website repository?')) return;
    try {
        await fetch(`${API_BASE}/sources/${sourceId}`, { method: 'DELETE' });
        showToast('Source deleted', 'success');
        fetchSources();
    } catch (e) {
        showToast('Delete failed', 'error');
    }
}

async function deleteKeyword(keywordId) {
    try {
        await fetch(`${API_BASE}/keywords/${keywordId}`, { method: 'DELETE' });
        showToast('Keyword rule removed', 'info');
        fetchKeywords();
    } catch (e) {
        showToast('Failed to delete keyword', 'error');
    }
}

async function sendEditionEmail(editionId) {
    showToast('Dispatching EPUB via SMTP...', 'info');
    try {
        const res = await fetch(`${API_BASE}/editions/${editionId}/send-email`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast(data.message || 'Sent successfully!', 'success');
        } else {
            showToast(data.detail || 'SMTP failed', 'error');
        }
    } catch (e) {
        showToast(`Send error: ${e.message}`, 'error');
    }
}

// --- Add Source Modal & Discovery ---
function openAddSourceModal() {
    document.getElementById('add-source-modal').classList.remove('hidden');
    document.getElementById('source-url-input').focus();
}

function closeAddSourceModal() {
    document.getElementById('add-source-modal').classList.add('hidden');
    document.getElementById('source-preview-box').classList.add('hidden');
    document.getElementById('source-url-input').value = '';
    const weightInput = document.getElementById('preview-source-weight-input');
    if (weightInput) weightInput.value = '0.0';
}

async function probeSourceUrl() {
    const url = document.getElementById('source-url-input').value.trim();
    if (!url) return;

    const probeBtn = document.getElementById('probe-btn');
    probeBtn.disabled = true;
    probeBtn.textContent = 'Probing...';

    try {
        const res = await fetch(`${API_BASE}/sources/probe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Probe failed');

        const previewBox = document.getElementById('source-preview-box');
        previewBox.classList.remove('hidden');

        const nameInput = document.getElementById('preview-site-name-input');
        if (nameInput) nameInput.value = data.name;

        const feedInput = document.getElementById('preview-feed-url-input');
        if (feedInput) feedInput.value = data.feed_url || data.base_url;

        const modeBadge = document.getElementById('preview-mode');
        if (modeBadge) modeBadge.textContent = (data.crawl_mode === 'rss' ? 'RSS / XML Feed' : 'HTML Crawl');

        const previewList = document.getElementById('preview-articles-list');
        previewList.innerHTML = (data.preview && data.preview.length > 0) ? data.preview.map(p => `
            <li class="truncate text-xs text-zinc-300 py-0.5">• ${p.title}</li>
        `).join('') : '<li class="text-xs text-zinc-500 italic">No article preview available</li>';

        document.getElementById('confirm-add-source-btn').onclick = () => {
            const customName = nameInput ? nameInput.value.trim() : data.name;
            const targetFeed = data.feed_url || null;
            const weightInput = document.getElementById('preview-source-weight-input');
            const customWeight = weightInput ? (parseFloat(weightInput.value) || 0.0) : 0.0;
            submitAddSource(url, customName, targetFeed, customWeight);
        };
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        probeBtn.disabled = false;
        probeBtn.textContent = 'Inspect Link';
    }
}

async function submitAddSource(url, name, feedUrl, weight = 0.0) {
    try {
        const payload = { url, weight: weight || 0.0 };
        if (name) payload.name = name;
        if (feedUrl) payload.feed_url = feedUrl;

        const res = await fetch(`${API_BASE}/sources`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to add source');

        showToast(`Added source: ${data.name} (Weight: ${data.weight > 0 ? '+' : ''}${data.weight})`, 'success');
        closeAddSourceModal();
        fetchSources();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// --- Keyword Form Handler ---
async function handleAddKeyword(e) {
    e.preventDefault();
    const term = document.getElementById('kw-term-input').value.trim();
    const weight = parseFloat(document.getElementById('kw-weight-input').value);
    const type = document.getElementById('kw-type-select').value;

    if (!term) return;

    const payload = {
        term: term,
        weight: weight,
        is_required: type === 'required',
        is_excluded: type === 'excluded'
    };

    try {
        const res = await fetch(`${API_BASE}/keywords`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            document.getElementById('kw-term-input').value = '';
            showToast('Keyword rule saved', 'success');
            fetchKeywords();
        }
    } catch (e) {
        showToast('Error saving keyword', 'error');
    }
}

// Populate Sandbox Source Selection Dropdown
function populateSandboxSources() {
    const select = document.getElementById('sandbox-source-select');
    if (!select) return;

    const currentVal = select.value;
    select.innerHTML = '<option value="">No Source (Neutral 0.0)</option>' + state.sources.map(s => {
        const w = s.weight || 0.0;
        return `<option value="${s.id}">${s.name} (${w > 0 ? '+' : ''}${w} pts)</option>`;
    }).join('');

    if (currentVal) select.value = currentVal;
}

// Dry-Run Sandbox Evaluation
async function evaluateSandbox() {
    const url = document.getElementById('sandbox-url-input').value.trim();
    const title = document.getElementById('sandbox-title-input').value.trim();
    const content = document.getElementById('sandbox-content-input').value.trim();
    const sourceId = document.getElementById('sandbox-source-select').value || null;
    const ageDays = parseFloat(document.getElementById('sandbox-age-input').value) || 0.0;
    const wordsVal = parseInt(document.getElementById('sandbox-words-input').value, 10);
    const wordCount = !isNaN(wordsVal) && wordsVal > 0 ? wordsVal : null;

    const outputEl = document.getElementById('sandbox-results');
    outputEl.innerHTML = '<p class="text-zinc-500 font-mono text-xs">Evaluating matching rules and dimension curves...</p>';

    const publishedAt = new Date(Date.now() - ageDays * 86400 * 1000).toISOString();

    try {
        const res = await fetch(`${API_BASE}/keywords/evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url,
                title,
                content,
                source_id: sourceId,
                published_at: publishedAt,
                word_count: wordCount
            })
        });
        const data = await res.json();

        let statusBanner = '';
        if (data.is_excluded_match) {
            statusBanner = '<div class="p-2.5 rounded bg-rose-950/80 border border-rose-800 text-rose-300 font-bold text-xs">⛔ Discarded: Excluded keyword matched! (Score: -1)</div>';
        } else if (data.is_required_missing) {
            statusBanner = '<div class="p-2.5 rounded bg-amber-950/80 border border-amber-800 text-amber-300 font-bold text-xs">⚠️ Skipped: A required keyword was not found. (Score: 0)</div>';
        } else {
            statusBanner = `<div class="p-2.5 rounded bg-cyan-950/80 border border-cyan-800 text-cyan-300 font-bold text-xs">✅ Approved! Total Composite Score: ${data.score}</div>`;
        }

        const breakdownList = data.breakdown.map(b => {
            const contribStr = b.contribution > 0 ? `+${b.contribution}` : `${b.contribution}`;
            const contribColor = b.contribution > 0 ? 'text-cyan-400' : (b.contribution < 0 ? 'text-rose-400' : 'text-zinc-400');
            
            let desc = '';
            if (b.type === 'weighted') {
                desc = `Title: ${b.title_hits} | Body: ${b.body_hits}`;
            } else if (b.type === 'source') {
                desc = `Feed Bias`;
            } else if (b.type === 'age') {
                desc = `Recency Curve`;
            } else if (b.type === 'length') {
                desc = `Word Length Curve`;
            } else {
                desc = b.type;
            }

            return `
                <li class="flex justify-between items-center text-xs font-mono py-1.5 border-b border-zinc-800/60">
                    <span class="text-zinc-300"><strong>${b.term}</strong> <span class="text-zinc-500 text-[10px]">(${desc})</span></span>
                    <strong class="${contribColor}">${contribStr}</strong>
                </li>
            `;
        }).join('');

        outputEl.innerHTML = `
            ${statusBanner}
            <ul class="mt-3 space-y-1">
                ${breakdownList || '<li class="text-xs text-zinc-500 font-mono">No keyword or weight contributions calculated.</li>'}
            </ul>
        `;
    } catch (e) {
        outputEl.innerHTML = `<p class="text-rose-400 font-mono text-xs">Evaluation error: ${e.message}</p>`;
    }
}

// --- Settings Form ---
function loadSettingsForm() {
    const s = state.settings;
    if (!s) return;

    const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.value = val || '';
    };

    setVal('cfg-cron-hour', s.DAILY_CRON_HOUR);
    setVal('cfg-cron-minute', s.DAILY_CRON_MINUTE);
    setVal('cfg-daily-limit', s.DAILY_ARTICLE_LIMIT);
    setVal('cfg-kindle-email', s.DEFAULT_KINDLE_EMAIL);
    setVal('cfg-smtp-host', s.SMTP_HOST);
    setVal('cfg-smtp-port', s.SMTP_PORT);
    setVal('cfg-smtp-user', s.SMTP_USER);
    setVal('cfg-smtp-pass', s.SMTP_PASS);
    setVal('cfg-smtp-from', s.SMTP_FROM);

    const autoSendCb = document.getElementById('cfg-auto-send');
    if (autoSendCb) autoSendCb.checked = (s.AUTO_SEND_SMTP === 'true');
}

async function saveSettingsForm(e) {
    e.preventDefault();
    const getVal = (id) => document.getElementById(id)?.value.trim() || '';

    const payload = {
        DAILY_CRON_HOUR: getVal('cfg-cron-hour'),
        DAILY_CRON_MINUTE: getVal('cfg-cron-minute'),
        DAILY_ARTICLE_LIMIT: getVal('cfg-daily-limit'),
        DEFAULT_KINDLE_EMAIL: getVal('cfg-kindle-email'),
        AUTO_SEND_SMTP: document.getElementById('cfg-auto-send')?.checked ? 'true' : 'false',
        SMTP_HOST: getVal('cfg-smtp-host'),
        SMTP_PORT: getVal('cfg-smtp-port'),
        SMTP_USER: getVal('cfg-smtp-user'),
        SMTP_PASS: getVal('cfg-smtp-pass'),
        SMTP_FROM: getVal('cfg-smtp-from'),
        SMTP_USE_TLS: 'true'
    };

    try {
        const res = await fetch(`${API_BASE}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            showToast('Settings saved successfully', 'success');
            fetchSettings();
        }
    } catch (e) {
        showToast('Failed to save settings', 'error');
    }
}

async function testSmtpSettings() {
    const host = document.getElementById('cfg-smtp-host').value.trim();
    const port = parseInt(document.getElementById('cfg-smtp-port').value.trim() || '587', 10);
    const username = document.getElementById('cfg-smtp-user').value.trim();
    const password = document.getElementById('cfg-smtp-pass').value.trim();

    if (!host) {
        showToast('Please enter an SMTP Host first', 'warn');
        return;
    }

    showToast('Testing SMTP connection...', 'info');

    try {
        const res = await fetch(`${API_BASE}/settings/test-smtp`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, port, username, password, use_tls: true })
        });
        const data = await res.json();
        if (res.ok) {
            showToast('✅ SMTP Handshake Successful!', 'success');
        } else {
            showToast(`❌ SMTP Test Failed: ${data.detail}`, 'error');
        }
    } catch (e) {
        showToast(`SMTP Connection error: ${e.message}`, 'error');
    }
}

// --- In-Browser Reader Modal ---
async function readEditionInBrowser(editionId) {
    const modal = document.getElementById('reader-modal');
    const contentBox = document.getElementById('reader-content-box');
    modal.classList.remove('hidden');
    contentBox.innerHTML = '<p class="text-zinc-500 font-mono text-center py-20">Loading edition chapters and color images...</p>';

    try {
        const res = await fetch(`${API_BASE}/editions/${editionId}`);
        const ed = await res.json();

        document.getElementById('reader-title').textContent = ed.title;

        const chaptersHtml = ed.articles.map((art, idx) => `
            <div class="mb-16 pb-12 border-b border-zinc-800 last:border-0">
                <span class="text-xs font-mono text-cyan-400">Chapter ${idx + 1}</span>
                <h2 class="text-2xl font-bold text-white mt-1">${art.title}</h2>
                <div class="mt-2 text-xs text-zinc-400 font-mono flex items-center gap-4">
                    ${art.author ? `<span>By ${art.author}</span>` : ''}
                    ${art.published_at ? `<span>${new Date(art.published_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</span>` : ''}
                    <span>${art.word_count} words</span>
                    <a href="${art.url}" target="_blank" class="text-cyan-400 hover:underline">Original Source &rarr;</a>
                </div>
                <div class="mt-6 reader-body">
                    ${art.excerpt ? `<p class="italic text-zinc-300 font-sans text-sm">${art.excerpt}</p>` : ''}
                    <div id="art-body-${art.id}">
                        <button onclick="loadArticleFullBody('${art.id}')" class="px-3 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-cyan-300 text-xs font-mono mt-3">
                            Click to View Full Extracted Article Body
                        </button>
                    </div>
                </div>
            </div>
        `).join('');

        contentBox.innerHTML = chaptersHtml;
    } catch (e) {
        contentBox.innerHTML = `<p class="text-rose-400">Failed to load edition: ${e.message}</p>`;
    }
}

async function loadArticleFullBody(articleId) {
    const container = document.getElementById(`art-body-${articleId}`);
    if (!container) return;
    container.innerHTML = '<span class="text-xs font-mono text-zinc-500">Loading formatted XHTML...</span>';
    try {
        const res = await fetch(`${API_BASE}/articles/${articleId}`);
        const art = await res.json();
        container.innerHTML = `<div class="mt-4 p-4 rounded-lg bg-zinc-900/60 border border-zinc-800">${art.clean_html}</div>`;
    } catch (e) {
        container.innerHTML = '<span class="text-xs text-rose-400">Error loading body</span>';
    }
}

function closeReaderModal() {
    document.getElementById('reader-modal').classList.add('hidden');
}

// --- Toast Notifications ---
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    const borderColors = {
        info: 'border-cyan-500/60 text-cyan-300 bg-zinc-900/90',
        success: 'border-emerald-500/60 text-emerald-300 bg-zinc-900/90',
        warn: 'border-amber-500/60 text-amber-300 bg-zinc-900/90',
        error: 'border-rose-500/60 text-rose-300 bg-zinc-900/90'
    };

    toast.className = `p-3 rounded-xl border backdrop-blur-md shadow-2xl text-xs font-mono flex items-center gap-2 transform transition-all duration-300 translate-y-2 opacity-0 ${borderColors[type] || borderColors.info}`;
    toast.textContent = message;

    container.appendChild(toast);
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    });

    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function setupEventListeners() {
    document.getElementById('btn-crawl-all')?.addEventListener('click', triggerCrawlAll);
    document.getElementById('btn-compile-now')?.addEventListener('click', triggerCompileNow);

    document.getElementById('btn-open-add-source')?.addEventListener('click', openAddSourceModal);
    document.getElementById('btn-close-source-modal')?.addEventListener('click', closeAddSourceModal);
    document.getElementById('probe-btn')?.addEventListener('click', probeSourceUrl);

    document.getElementById('btn-recalculate-scores')?.addEventListener('click', recalculateScores);

    document.getElementById('btn-save-age-curve')?.addEventListener('click', saveCurvesToServer);
    document.getElementById('btn-save-length-curve')?.addEventListener('click', saveCurvesToServer);
    document.getElementById('btn-reset-age-curve')?.addEventListener('click', resetAgeCurve);
    document.getElementById('btn-reset-length-curve')?.addEventListener('click', resetLengthCurve);
    document.getElementById('btn-add-age-point')?.addEventListener('click', () => addCurvePointPrompt('age'));
    document.getElementById('btn-add-length-point')?.addEventListener('click', () => addCurvePointPrompt('length'));

    document.getElementById('keyword-form')?.addEventListener('submit', handleAddKeyword);
    document.getElementById('sandbox-evaluate-btn')?.addEventListener('click', evaluateSandbox);

    document.getElementById('settings-form')?.addEventListener('submit', saveSettingsForm);
    document.getElementById('btn-test-smtp')?.addEventListener('click', testSmtpSettings);

    document.getElementById('btn-close-reader')?.addEventListener('click', closeReaderModal);
}
