/**
 * AetherPub Reactive Application Controller
 */

const API_BASE = '/api/v1';

const state = {
    currentTab: 'dashboard',
    sources: [],
    keywords: [],
    articles: [],
    editions: [],
    settings: {},
    isCrawling: false,
    isCompiling: false,
    terminalLogs: []
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initSSE();
    fetchAllData();
    setupEventListeners();
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
    state.currentTab = tabId;
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    const target = document.getElementById(`tab-${tabId}`);
    if (target) target.classList.remove('hidden');

    document.querySelectorAll('.nav-btn').forEach(btn => {
        if (btn.dataset.tab === tabId) {
            btn.classList.add('bg-zinc-800', 'text-cyan-400', 'border-cyan-500/40');
            btn.classList.remove('text-zinc-400', 'border-transparent');
        } else {
            btn.classList.remove('bg-zinc-800', 'text-cyan-400', 'border-cyan-500/40');
            btn.classList.add('text-zinc-400', 'border-transparent');
        }
    });

    if (tabId === 'sources') renderSources();
    if (tabId === 'keywords') renderKeywords();
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

    // Keep max 200 log lines
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
        if (state.currentTab === 'sources') renderSources();
        updateDashboardKPIs();
    } catch (e) {
        console.error('Failed to fetch sources:', e);
    }
}

async function fetchKeywords() {
    try {
        const res = await fetch(`${API_BASE}/keywords`);
        state.keywords = await res.json();
        if (state.currentTab === 'keywords') renderKeywords();
        updateDashboardKPIs();
    } catch (e) {
        console.error('Failed to fetch keywords:', e);
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

    if (kpiSources) kpiSources.textContent = state.sources.length;
    if (kpiKeywords) kpiKeywords.textContent = state.keywords.length;
    if (kpiArticles) {
        const unbundled = state.articles.filter(a => !a.is_bundled).length;
        kpiArticles.textContent = `${unbundled} (${state.articles.length} total)`;
    }
    if (kpiEditions) kpiEditions.textContent = state.editions.length;
}

// --- Renders ---
function renderSources() {
    const container = document.getElementById('sources-list');
    if (!container) return;

    if (state.sources.length === 0) {
        container.innerHTML = `
            <div class="col-span-full py-16 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40">
                <i data-lucide="globe" class="w-10 h-10 text-zinc-600 mx-auto mb-3"></i>
                <p class="text-zinc-400 font-medium">No website sources registered yet</p>
                <p class="text-zinc-600 text-sm mt-1">Add your favorite blogs, news sites, or RSS feeds to begin tracking.</p>
                <button onclick="openAddSourceModal()" class="mt-4 px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-medium text-sm transition-all shadow-lg shadow-cyan-500/20">
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

        return `
            <div class="glass-panel p-5 rounded-xl flex flex-col justify-between group relative overflow-hidden">
                <div class="absolute top-0 left-0 w-1 h-full bg-cyan-500 opacity-60"></div>
                <div>
                    <div class="flex items-start justify-between gap-2">
                        <h3 class="font-semibold text-lg text-white group-hover:text-cyan-400 transition-colors truncate" title="${src.name}">
                            ${src.name}
                        </h3>
                        <span class="px-2 py-0.5 text-xs font-mono rounded border uppercase ${statusColors[src.last_status] || statusColors.idle}">
                            ${src.last_status}
                        </span>
                    </div>
                    <p class="text-xs text-zinc-400 font-mono mt-1 truncate" title="${src.base_url}">${src.base_url}</p>
                    
                    <div class="mt-4 flex flex-wrap gap-2 text-xs">
                        <span class="px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 font-mono">
                            Mode: <span class="text-cyan-400 font-bold uppercase">${src.crawl_mode}</span>
                        </span>
                        <span class="px-2 py-1 rounded bg-zinc-900 border border-zinc-800 text-zinc-300 font-mono">
                            Articles: <span class="text-white font-bold">${src.article_count}</span>
                        </span>
                    </div>

                    ${src.feed_url ? `
                        <div class="mt-2 text-xs text-zinc-500 truncate font-mono">
                            Feed: <a href="${src.feed_url}" target="_blank" class="text-zinc-400 hover:text-cyan-400 underline">${src.feed_url}</a>
                        </div>
                    ` : ''}

                    <div class="mt-3 text-[11px] text-zinc-500">
                        Last Crawled: ${lastCrawled}
                    </div>
                </div>

                <div class="mt-5 pt-4 border-t border-zinc-800/80 flex items-center justify-between">
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

function renderKeywords() {
    const container = document.getElementById('keywords-list');
    if (!container) return;

    if (state.keywords.length === 0) {
        container.innerHTML = `
            <div class="p-8 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40">
                <p class="text-zinc-400 font-medium">No interest keywords assigned</p>
                <p class="text-zinc-600 text-xs mt-1">Add keywords below to guide the daily article curation engine.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="flex flex-wrap gap-2.5">
            ${state.keywords.map(kw => {
                let badgeClass = 'bg-cyan-950/60 border-cyan-800/80 text-cyan-300';
                let typePrefix = '';
                if (kw.is_required) {
                    badgeClass = 'bg-emerald-950/60 border-emerald-800 text-emerald-300';
                    typePrefix = '<span class="text-emerald-400 font-bold mr-1">[+] REQUIRED:</span>';
                } else if (kw.is_excluded) {
                    badgeClass = 'bg-rose-950/60 border-rose-800 text-rose-300';
                    typePrefix = '<span class="text-rose-400 font-bold mr-1">[-] EXCLUDED:</span>';
                }

                return `
                    <div class="glass-panel px-3 py-1.5 rounded-lg border flex items-center gap-2 text-sm ${badgeClass}">
                        <span>${typePrefix}<strong>${kw.term}</strong></span>
                        ${!kw.is_required && !kw.is_excluded ? `
                            <span class="px-1.5 py-0.2 rounded bg-black/40 text-[11px] font-mono font-bold text-cyan-400">
                                ${kw.weight > 0 ? '+' : ''}${kw.weight}x
                            </span>
                        ` : ''}
                        <button onclick="deleteKeyword('${kw.id}')" class="text-zinc-400 hover:text-white transition-colors ml-1">
                            &times;
                        </button>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

function renderEditions() {
    const container = document.getElementById('editions-list');
    if (!container) return;

    if (state.editions.length === 0) {
        container.innerHTML = `
            <div class="col-span-full py-16 text-center border border-dashed border-zinc-800 rounded-xl bg-zinc-950/40">
                <i data-lucide="book-open" class="w-10 h-10 text-zinc-600 mx-auto mb-3"></i>
                <p class="text-zinc-400 font-medium">No daily editions compiled yet</p>
                <p class="text-zinc-600 text-sm mt-1">Click "Compile Digest Now" to bundle available articles into your first EPUB!</p>
                <button onclick="triggerCompileNow()" class="mt-4 px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium text-sm transition-all shadow-lg shadow-violet-600/30">
                    📚 Compile Edition Now
                </button>
            </div>
        `;
        lucide.createIcons();
        return;
    }

    container.innerHTML = state.editions.map(ed => {
        const coverUrl = `${API_BASE}/editions/${ed.id}/cover`;
        const downloadUrl = `${API_BASE}/editions/${ed.id}/download`;
        const sizeMb = (ed.file_size_bytes / (1024 * 1024)).toFixed(2);

        return `
            <div class="glass-panel rounded-xl overflow-hidden flex flex-col justify-between group border border-white/10 hover:border-violet-500/40 transition-all">
                <div class="relative bg-zinc-950 h-52 flex items-center justify-center overflow-hidden border-b border-zinc-800">
                    <img src="${coverUrl}" alt="Cover" class="h-full w-full object-cover object-center group-hover:scale-105 transition-transform duration-500" onerror="this.src='/static/css/cover_fallback.jpg'; this.style.display='none';" />
                    <div class="absolute inset-0 bg-gradient-to-t from-zinc-950 via-transparent to-transparent"></div>
                    <div class="absolute bottom-3 left-3 right-3 flex justify-between items-end">
                        <span class="px-2 py-1 rounded bg-black/70 backdrop-blur-md text-[11px] font-mono text-cyan-400 border border-cyan-500/30">
                            ${ed.edition_date}
                        </span>
                        <span class="px-2 py-1 rounded bg-black/70 backdrop-blur-md text-[11px] font-mono text-violet-300 border border-violet-500/30">
                            ${ed.article_count} Articles
                        </span>
                    </div>
                </div>

                <div class="p-5 flex-1 flex flex-col justify-between">
                    <div>
                        <h3 class="font-bold text-white text-lg group-hover:text-violet-300 transition-colors">
                            ${ed.title}
                        </h3>
                        <div class="mt-2 flex items-center gap-3 text-xs text-zinc-400 font-mono">
                            <span>📦 ${sizeMb} MB</span>
                            <span>⏱ ~${Math.round(ed.total_word_count / 220)} min read</span>
                        </div>
                    </div>

                    <div class="mt-5 pt-4 border-t border-zinc-800 flex flex-col gap-2">
                        <div class="flex items-center gap-2">
                            <a href="${downloadUrl}" download class="flex-1 py-2 px-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white font-medium text-xs flex items-center justify-center gap-1.5 transition-all">
                                <i data-lucide="download" class="w-4 h-4 text-cyan-400"></i> Download EPUB
                            </a>
                            <button onclick="readEditionInBrowser('${ed.id}')" class="py-2 px-3 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white font-medium text-xs flex items-center justify-center gap-1.5 transition-all" title="Read in Browser">
                                <i data-lucide="eye" class="w-4 h-4 text-violet-400"></i>
                            </button>
                        </div>
                        <button onclick="sendEditionEmail('${ed.id}')" class="w-full py-2 px-3 rounded-lg bg-violet-600/30 hover:bg-violet-600/50 text-violet-200 border border-violet-500/40 font-medium text-xs flex items-center justify-center gap-1.5 transition-all">
                            <i data-lucide="send" class="w-3.5 h-3.5"></i> ${ed.sent_via_smtp ? 'Sent to Kindle (Resend)' : 'Send to E-Reader (SMTP)'}
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    lucide.createIcons();
}

function renderDashboardEditions() {
    const container = document.getElementById('dashboard-latest-edition');
    if (!container) return;

    if (state.editions.length === 0) {
        container.innerHTML = `
            <div class="p-6 text-center text-zinc-500 text-sm">
                No editions compiled yet today.
            </div>
        `;
        return;
    }

    const latest = state.editions[0];
    const downloadUrl = `${API_BASE}/editions/${latest.id}/download`;

    container.innerHTML = `
        <div class="flex items-center justify-between gap-4">
            <div>
                <span class="text-xs font-mono text-cyan-400 uppercase tracking-wider">Latest Digest</span>
                <h4 class="text-lg font-bold text-white mt-0.5">${latest.title}</h4>
                <p class="text-xs text-zinc-400 font-mono mt-1">
                    ${latest.article_count} Articles • ${(latest.file_size_bytes / 1024 / 1024).toFixed(2)} MB • ${new Date(latest.created_at).toLocaleDateString()}
                </p>
            </div>
            <div class="flex items-center gap-2">
                <a href="${downloadUrl}" download class="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-semibold text-xs flex items-center gap-2 transition-all shadow-lg shadow-cyan-500/20">
                    <i data-lucide="download" class="w-4 h-4"></i> Download
                </a>
                <button onclick="sendEditionEmail('${latest.id}')" class="px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs flex items-center gap-1.5 transition-all" title="Send to Device">
                    <i data-lucide="send" class="w-4 h-4 text-violet-400"></i>
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
        const res = await fetch(`${API_BASE}/editions/build-now`, { method: 'POST' });
        const data = await res.json();
    } catch (e) {
        showToast('Compilation request failed', 'error');
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
        showToast('Keyword removed', 'info');
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

        // Render preview
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
            submitAddSource(url, customName, targetFeed);
        };
    } catch (e) {
        showToast(e.message, 'error');
    } finally {
        probeBtn.disabled = false;
        probeBtn.textContent = 'Inspect Link';
    }
}

async function submitAddSource(url, name, feedUrl) {
    try {
        const payload = { url };
        if (name) payload.name = name;
        if (feedUrl) payload.feed_url = feedUrl;

        const res = await fetch(`${API_BASE}/sources`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to add source');

        showToast(`Added source: ${data.name}`, 'success');
        closeAddSourceModal();
        fetchSources();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// --- Keyword Management & Sandbox ---
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

async function evaluateSandbox() {
    const url = document.getElementById('sandbox-url-input').value.trim();
    const title = document.getElementById('sandbox-title-input').value.trim();
    const content = document.getElementById('sandbox-content-input').value.trim();

    const outputEl = document.getElementById('sandbox-results');
    outputEl.innerHTML = '<p class="text-zinc-500 font-mono text-xs">Evaluating matching rules...</p>';

    try {
        const res = await fetch(`${API_BASE}/keywords/evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, title, content })
        });
        const data = await res.json();

        let statusBanner = '';
        if (data.is_excluded_match) {
            statusBanner = '<div class="p-2.5 rounded bg-rose-950/80 border border-rose-800 text-rose-300 font-bold text-xs">⛔ Discarded: Excluded keyword matched! (Score: -1)</div>';
        } else if (data.is_required_missing) {
            statusBanner = '<div class="p-2.5 rounded bg-amber-950/80 border border-amber-800 text-amber-300 font-bold text-xs">⚠️ Skipped: A required keyword was not found. (Score: 0)</div>';
        } else {
            statusBanner = `<div class="p-2.5 rounded bg-cyan-950/80 border border-cyan-800 text-cyan-300 font-bold text-xs">✅ Approved! Total Relevance Score: ${data.score}</div>`;
        }

        const breakdownList = data.breakdown.map(b => `
            <li class="flex justify-between items-center text-xs font-mono py-1 border-b border-zinc-800/60">
                <span class="text-zinc-300"><strong>${b.term}</strong> (${b.type})</span>
                <span class="text-zinc-400">Title: ${b.title_hits} | Body: ${b.body_hits} &rarr; <strong class="text-cyan-400">+${b.contribution}</strong></span>
            </li>
        `).join('');

        outputEl.innerHTML = `
            ${statusBanner}
            <ul class="mt-3 space-y-1">
                ${breakdownList || '<li class="text-xs text-zinc-500 font-mono">No keyword hits for this sample.</li>'}
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
    const port = parseInt(document.getElementById('cfg-smtp-port').value.trim() || '587');
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

        // Render chapter index and articles
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
    // Quick action buttons
    document.getElementById('btn-crawl-all')?.addEventListener('click', triggerCrawlAll);
    document.getElementById('btn-compile-now')?.addEventListener('click', triggerCompileNow);

    // Modal listeners
    document.getElementById('btn-open-add-source')?.addEventListener('click', openAddSourceModal);
    document.getElementById('btn-close-source-modal')?.addEventListener('click', closeAddSourceModal);
    document.getElementById('probe-btn')?.addEventListener('click', probeSourceUrl);

    // Keyword forms
    document.getElementById('keyword-form')?.addEventListener('submit', handleAddKeyword);
    document.getElementById('sandbox-evaluate-btn')?.addEventListener('click', evaluateSandbox);

    // Settings form
    document.getElementById('settings-form')?.addEventListener('submit', saveSettingsForm);
    document.getElementById('btn-test-smtp')?.addEventListener('click', testSmtpSettings);

    // Close reader modal
    document.getElementById('btn-close-reader')?.addEventListener('click', closeReaderModal);
}
