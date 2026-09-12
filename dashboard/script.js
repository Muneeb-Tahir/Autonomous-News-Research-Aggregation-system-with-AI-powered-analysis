/**
 * News Intelligence Agent — Dashboard JavaScript
 * Fetches news from the API, renders interactive cards,
 * handles chatbot, and on-demand collection.
 */

// ═══════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════
const API_BASE = window.location.origin;
const REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes
let currentCategory = '';
let refreshTimer = null;
let chatbotOpen = false;

// ═══════════════════════════════════════════════════
// Initialization
// ═══════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    setupCategoryButtons();
    fetchStatus();
    fetchNews();

    // Auto-refresh every 5 minutes
    refreshTimer = setInterval(() => {
        fetchNews();
        fetchStatus();
    }, REFRESH_INTERVAL);
});

// ═══════════════════════════════════════════════════
// Category Buttons
// ═══════════════════════════════════════════════════
function setupCategoryButtons() {
    const buttons = document.querySelectorAll('.cat-btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            buttons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            if (btn.dataset.mode === 'research') {
                // Switch to research view
                document.getElementById('loading').style.display = 'none';
                document.getElementById('news-cards').style.display = 'none';
                document.getElementById('error').style.display = 'none';
                document.getElementById('empty').style.display = 'none';
                document.getElementById('research-section').style.display = 'block';
                fetchResearch();
            } else {
                // Switch to news view
                document.getElementById('research-section').style.display = 'none';
                currentCategory = btn.dataset.category || '';
                fetchNews();
            }
        });
    });
}

// ═══════════════════════════════════════════════════
// Fetch News
// ═══════════════════════════════════════════════════
async function fetchNews() {
    showLoading();

    try {
        const params = new URLSearchParams({ hours: 168, limit: 20 });
        if (currentCategory) {
            params.set('category', currentCategory);
        }

        const response = await fetch(`${API_BASE}/api/top5?${params}`);

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}`);
        }

        const data = await response.json();

        if (data.articles && data.articles.length > 0) {
            renderNewsCards(data.articles);
            showContent();
        } else {
            showEmpty();
        }

        updateLastUpdated();

    } catch (err) {
        console.error('Failed to fetch news:', err);
        showError(err.message);
    }
}

// ═══════════════════════════════════════════════════
// Fetch Status
// ═══════════════════════════════════════════════════
async function fetchStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        const data = await response.json();

        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');

        const status = data.status || 'unknown';
        dot.className = 'status-dot ' + status;

        const totalArticles = data.total_articles || data.article_count || 0;

        if (data.last_collection) {
            const lastTime = new Date(data.last_collection);
            const minutesAgo = Math.round((Date.now() - lastTime.getTime()) / 60000);
            text.textContent = `${totalArticles} articles | Updated ${formatRelativeTime(minutesAgo)}`;
        } else {
            text.textContent = `${totalArticles} articles | ${status}`;
        }
    } catch (err) {
        const dot = document.getElementById('status-dot');
        const text = document.getElementById('status-text');
        dot.className = 'status-dot error';
        text.textContent = 'Server offline';
    }
}

// ═══════════════════════════════════════════════════
// Generate News (On-Demand Collection)
// ═══════════════════════════════════════════════════
async function triggerCollection() {
    const btn = document.getElementById('collect-btn');
    const icon = document.getElementById('collect-icon');
    const text = document.getElementById('collect-text');

    // Already collecting?
    if (btn.classList.contains('collecting')) return;

    btn.classList.add('collecting');
    icon.innerHTML = '&#x21BB;';
    text.textContent = 'Collecting...';

    try {
        const response = await fetch(`${API_BASE}/api/collect`, { method: 'POST' });
        const data = await response.json();

        if (data.status === 'already_running') {
            text.textContent = 'Already running...';
        } else {
            text.textContent = 'Collecting...';
            // Poll for completion
            pollCollectionStatus(btn, icon, text);
        }
    } catch (err) {
        console.error('Failed to trigger collection:', err);
        btn.classList.remove('collecting');
        icon.innerHTML = '&#x26A1;';
        text.textContent = 'Generate News';
    }
}

function pollCollectionStatus(btn, icon, text) {
    const poll = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/collect/status`);
            const data = await response.json();

            if (!data.is_collecting) {
                clearInterval(poll);
                btn.classList.remove('collecting');
                icon.innerHTML = '&#x2713;';
                text.textContent = 'Done!';

                // Refresh news and status
                fetchNews();
                fetchStatus();

                // Reset button after 2 seconds
                setTimeout(() => {
                    icon.innerHTML = '&#x26A1;';
                    text.textContent = 'Generate News';
                }, 2000);
            }
        } catch (err) {
            clearInterval(poll);
            btn.classList.remove('collecting');
            icon.innerHTML = '&#x26A1;';
            text.textContent = 'Generate News';
        }
    }, 3000); // Check every 3 seconds
}

// ═══════════════════════════════════════════════════
// Chatbot
// ═══════════════════════════════════════════════════
function toggleChatbot() {
    const panel = document.getElementById('chatbot-panel');
    chatbotOpen = !chatbotOpen;

    if (chatbotOpen) {
        panel.classList.add('open');
        document.getElementById('chatbot-input').focus();
    } else {
        panel.classList.remove('open');
    }
}

async function sendMessage() {
    const input = document.getElementById('chatbot-input');
    const message = input.value.trim();
    if (!message) return;

    // Add user message
    addChatMessage(message, 'user');
    input.value = '';

    // Show typing indicator
    const typingId = showTyping();

    try {
        const response = await fetch(`${API_BASE}/api/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message }),
        });

        const data = await response.json();
        removeTyping(typingId);

        const botResponse = data.response || data.error || 'No response.';
        addChatMessage(botResponse, 'bot');

    } catch (err) {
        removeTyping(typingId);
        addChatMessage('Failed to reach server. Is it running?', 'bot');
    }
}

function addChatMessage(text, sender) {
    const container = document.getElementById('chatbot-messages');
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${sender}`;

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    bubble.textContent = text;

    msgDiv.appendChild(bubble);
    container.appendChild(msgDiv);

    // Scroll to bottom
    container.scrollTop = container.scrollHeight;
}

function showTyping() {
    const container = document.getElementById('chatbot-messages');
    const typingDiv = document.createElement('div');
    const id = 'typing-' + Date.now();
    typingDiv.id = id;
    typingDiv.className = 'chat-message bot';
    typingDiv.innerHTML = `
        <div class="chat-bubble">
            <div class="chat-typing">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    container.appendChild(typingDiv);
    container.scrollTop = container.scrollHeight;
    return id;
}

function removeTyping(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

// ═══════════════════════════════════════════════════
// Render News Cards
// ═══════════════════════════════════════════════════
function renderNewsCards(articles) {
    const container = document.getElementById('news-cards');
    container.innerHTML = '';

    articles.forEach((article, index) => {
        const card = createNewsCard(article, index);
        container.appendChild(card);
    });
}

function createNewsCard(article, index) {
    const card = document.createElement('article');
    card.className = 'news-card' + (article.is_breaking ? ' breaking' : '');

    const importanceScore = Math.round(article.importance_score || 0);
    const urgencyScore = Math.round(article.urgency_score || 0);

    const sources = [article.source_name || 'Unknown'];
    if (article.additional_sources && Array.isArray(article.additional_sources)) {
        article.additional_sources.forEach(src => {
            if (src && src.name && !sources.includes(src.name)) {
                sources.push(src.name);
            }
        });
    }

    const catEmoji = {
        'WORLD': '\u{1F30D}', 'POLITICS': '\u{1F3DB}', 'BUSINESS': '\u{1F4B0}',
        'FINANCE': '\u{1F4C8}', 'TECHNOLOGY': '\u{1F4BB}', 'AI': '\u{1F916}',
        'SCIENCE': '\u{1F52C}', 'HEALTH': '\u{1F3E5}', 'CLIMATE': '\u{1F321}',
        'SPORTS': '\u26BD', 'SPACE': '\u{1F680}', 'CRYPTO': '\u20BF',
        'ENTERTAINMENT': '\u{1F3AC}', 'CYBERSECURITY': '\u{1F512}',
        'GAMING': '\u{1F3AE}', 'GENERAL': '\u{1F4F0}',
    };

    const emoji = catEmoji[article.category] || '\u{1F4F0}';
    const description = article.description || 'No description available.';
    const truncatedDesc = description.length > 250
        ? description.substring(0, 247) + '...'
        : description;

    const credScore = Math.round(article.credibility_score || 50);
    const authLabel = credScore >= 80 ? 'Verified' : credScore >= 60 ? 'Credible' : credScore >= 40 ? 'Unverified' : 'Suspicious';
    const authClass = credScore >= 80 ? 'verified' : credScore >= 60 ? 'credible' : credScore >= 40 ? 'unverified' : 'suspicious';
    const ageText = formatArticleAge(article.published_at);

    card.innerHTML = `
        <div class="card-header">
            <div class="card-rank">${index + 1}</div>
            <h2 class="card-title">${escapeHtml(article.title || 'Untitled')}</h2>
        </div>

        <div class="card-meta">
            <span class="meta-tag category">${emoji} ${article.category || 'GENERAL'}</span>
            <span class="meta-tag ${authClass}">${authClass === 'verified' ? '\u2705' : authClass === 'credible' ? '\u{1F7E2}' : authClass === 'unverified' ? '\u{1F7E1}' : '\u{1F534}'} ${authLabel}</span>
            <span class="meta-tag age">${ageText}</span>
            <span class="meta-tag sources">\u{1F4F0} ${sources.length} source${sources.length > 1 ? 's' : ''}</span>
        </div>

        <div class="score-bar-container">
            <span class="score-label">Importance</span>
            <div class="score-bar">
                <div class="score-bar-fill" style="width: ${importanceScore}%"></div>
            </div>
            <span class="score-value">${importanceScore}</span>
        </div>

        <div class="score-bar-container">
            <span class="score-label">Credibility</span>
            <div class="score-bar">
                <div class="score-bar-fill ${authClass}" style="width: ${credScore}%"></div>
            </div>
            <span class="score-value">${credScore}</span>
        </div>

        <p class="card-description">${escapeHtml(truncatedDesc)}</p>

        <div class="card-footer">
            <span class="card-source"><strong>${escapeHtml(sources.join(', '))}</strong> \u2022 ${formatArticleTime(article.published_at)}</span>
            <a href="${escapeHtml(article.url || '#')}" target="_blank" rel="noopener noreferrer" class="card-link">
                Read more \u2192
            </a>
        </div>
    `;

    return card;
}

// ═══════════════════════════════════════════════════
// UI State Management
// ═══════════════════════════════════════════════════
function showLoading() {
    document.getElementById('loading').style.display = 'flex';
    document.getElementById('news-cards').style.display = 'none';
    document.getElementById('error').style.display = 'none';
    document.getElementById('empty').style.display = 'none';
}

function showContent() {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('news-cards').style.display = 'flex';
    document.getElementById('error').style.display = 'none';
    document.getElementById('empty').style.display = 'none';
}

function showError(message) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('news-cards').style.display = 'none';
    document.getElementById('error').style.display = 'block';
    document.getElementById('empty').style.display = 'none';
    document.getElementById('error-message').textContent = message || 'Something went wrong.';
}

function showEmpty() {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('news-cards').style.display = 'none';
    document.getElementById('error').style.display = 'none';
    document.getElementById('empty').style.display = 'block';
}

// ═══════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatRelativeTime(minutes) {
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
}

function formatArticleTime(isoString) {
    if (!isoString) return '';
    try {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.round(diffMs / 60000);
        return formatRelativeTime(diffMins);
    } catch {
        return '';
    }
}

function updateLastUpdated() {
    const el = document.getElementById('last-updated');
    const now = new Date();
    el.textContent = `Last updated: ${now.toLocaleString('en-PK', { timeZone: 'Asia/Karachi' })}`;
}

function formatArticleAge(isoString) {
    if (!isoString) return 'Unknown age';
    try {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.round(diffMs / 60000);
        const diffHours = Math.round(diffMs / 3600000);
        const diffDays = Math.round(diffMs / 86400000);

        if (diffMins < 60) return `\u{1F7E2} ${diffMins}m ago`;
        if (diffHours < 24) return `\u{1F7E2} ${diffHours}h ago`;
        if (diffDays === 1) return `\u{1F7E1} Yesterday`;
        if (diffDays <= 3) return `\u{1F7E1} ${diffDays} days ago`;
        if (diffDays <= 7) return `\u{1F7E0} ${diffDays} days old`;
        return `\u{1F534} ${diffDays} days old`;
    } catch {
        return 'Unknown age';
    }
}

// ═══════════════════════════════════════════════════
// Research Papers
// ═══════════════════════════════════════════════════
let currentResearchPriority = '';

async function fetchResearch(priority) {
    const loading = document.getElementById('research-loading');
    const cards = document.getElementById('research-cards');
    const empty = document.getElementById('research-empty');

    loading.style.display = 'flex';
    cards.style.display = 'none';
    empty.style.display = 'none';

    try {
        const params = new URLSearchParams({ limit: 50 });
        if (priority) params.set('priority', priority);

        const response = await fetch(`${API_BASE}/api/research?${params}`);
        const data = await response.json();

        loading.style.display = 'none';

        if (data.papers && data.papers.length > 0) {
            renderResearchCards(data.papers);
            cards.style.display = 'block';
        } else {
            empty.style.display = 'block';
        }
    } catch (err) {
        loading.style.display = 'none';
        empty.style.display = 'block';
        console.error('Failed to fetch research:', err);
    }
}

function renderResearchCards(papers) {
    const container = document.getElementById('research-cards');
    container.innerHTML = '';

    // Group by category
    const groups = {};
    papers.forEach(paper => {
        const cat = paper.category_name || 'Other';
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(paper);
    });

    // Sort groups: priority 1 first
    const sortedGroups = Object.entries(groups).sort((a, b) => {
        const pa = a[1][0]?.priority || 3;
        const pb = b[1][0]?.priority || 3;
        return pa - pb;
    });

    const priorityEmoji = { 1: '\u{1F916}', 2: '\u{1F4BB}', 3: '\u{1F525}' };

    sortedGroups.forEach(([catName, catPapers]) => {
        const priority = catPapers[0]?.priority || 3;
        const emoji = priorityEmoji[priority] || '\u{1F4DA}';

        const header = document.createElement('div');
        header.className = 'research-category-header';
        header.innerHTML = `<h3>${emoji} ${escapeHtml(catName)} <span class="paper-count">${catPapers.length} paper${catPapers.length > 1 ? 's' : ''}</span></h3>`;
        container.appendChild(header);

        const grid = document.createElement('div');
        grid.className = 'research-category-grid';
        catPapers.forEach((paper, i) => grid.appendChild(createPaperCard(paper, i)));
        container.appendChild(grid);
    });
}

function createPaperCard(paper, index) {
    const card = document.createElement('div');
    card.className = 'paper-card';

    const analysis = paper.analysis || {};
    const difficulty = analysis.difficulty || 'intermediate';
    const diffEmoji = difficulty === 'beginner' ? '\u{1F7E2}' : difficulty === 'advanced' ? '\u{1F534}' : '\u{1F7E1}';
    const authors = (paper.authors || []).slice(0, 3).join(', ');
    const authorsMore = (paper.authors || []).length > 3 ? ` +${paper.authors.length - 3} more` : '';

    const problems = (analysis.open_problems || []).map(p => `<li>${escapeHtml(p)}</li>`).join('');
    const opportunities = (analysis.opportunities || []).map(o => `<li>${escapeHtml(o)}</li>`).join('');
    const skills = (analysis.skills_needed || []).map(s => `<span class="skill-tag">${escapeHtml(s)}</span>`).join('');
    const tags = (analysis.field_tags || []).map(t => `<span class="field-tag">${escapeHtml(t)}</span>`).join('');

    const summary = analysis.summary || (paper.abstract ? paper.abstract.substring(0, 250) + '...' : 'Analysis pending...');

    const pubDate = paper.published_at ? new Date(paper.published_at).toLocaleDateString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric'
    }) : 'Unknown date';

    const cat = paper.primary_category || '';
    const sourceBadges = {
        'crossref': '\u{1F4DA} Crossref (Verified)',
        'semantic': '\u{1F9E0} Semantic Scholar',
        'openalex': '\u{1F30D} OpenAlex',
        'scholar': '\u{1F4DA} Crossref (Verified)',
    };
    const isArxiv = !['crossref', 'semantic', 'openalex', 'scholar'].includes(cat);
    const sourceBadge = isArxiv ? '\u2705 arXiv (Verified)' : (sourceBadges[cat] || '\u{1F4D6} Research');

    card.innerHTML = `
        <div class="paper-header">
            <span class="paper-cat">${escapeHtml(paper.primary_category || '')}</span>
            <span class="paper-date">\u{1F4C5} ${pubDate}</span>
        </div>
        <h3 class="paper-title">${escapeHtml(paper.title)}</h3>
        <p class="paper-authors">${escapeHtml(authors)}${authorsMore}</p>
        <div class="paper-meta-row">
            <span class="paper-source-badge ${isArxiv ? 'arxiv' : 'scholar'}">${sourceBadge}</span>
            <span class="paper-difficulty ${difficulty}">${diffEmoji} ${difficulty}</span>
        </div>
        <p class="paper-summary">${escapeHtml(summary)}</p>

        ${analysis.problem_addressed ? `<div class="paper-section">
            <h4>\u{1F3AF} Problem Addressed</h4>
            <p>${escapeHtml(analysis.problem_addressed)}</p>
        </div>` : ''}

        ${problems ? `<div class="paper-section">
            <h4>\u{26A0}\u{FE0F} Open Problems</h4>
            <ul>${problems}</ul>
        </div>` : ''}

        ${opportunities ? `<div class="paper-section opportunities">
            <h4>\u{1F4A1} How You Can Contribute</h4>
            <ul>${opportunities}</ul>
        </div>` : ''}

        ${skills ? `<div class="paper-skills">${skills}</div>` : ''}
        ${tags ? `<div class="paper-tags">${tags}</div>` : ''}

        <div class="paper-footer">
            ${paper.pdf_url ? `<a href="${escapeHtml(paper.pdf_url)}" target="_blank" class="paper-link pdf-link">\u{1F4C4} Download PDF</a>` : ''}
            ${paper.abs_url ? `<a href="${escapeHtml(paper.abs_url)}" target="_blank" class="paper-link">\u{1F517} Read on arXiv</a>` : ''}
        </div>
    `;
    return card;
}

async function refreshResearch() {
    const btn = document.getElementById('research-refresh-btn');
    const icon = document.getElementById('research-refresh-icon');
    const text = document.getElementById('research-refresh-text');

    if (btn.classList.contains('collecting')) return;

    btn.classList.add('collecting');
    icon.innerHTML = '&#x21BB;';
    text.textContent = 'Fetching...';

    try {
        await fetch(`${API_BASE}/api/research/refresh`, { method: 'POST' });

        // Poll for completion
        const poll = setInterval(async () => {
            try {
                const r = await fetch(`${API_BASE}/api/collect/status`);
                const d = await r.json();
                if (!d.is_fetching_papers) {
                    clearInterval(poll);
                    btn.classList.remove('collecting');
                    icon.innerHTML = '&#x2713;';
                    text.textContent = 'Done!';
                    fetchResearch(currentResearchPriority);
                    setTimeout(() => { icon.innerHTML = '&#x26A1;'; text.textContent = 'Fetch Papers'; }, 2000);
                }
            } catch { clearInterval(poll); btn.classList.remove('collecting'); icon.innerHTML = '&#x26A1;'; text.textContent = 'Fetch Papers'; }
        }, 3000);
    } catch {
        btn.classList.remove('collecting');
        icon.innerHTML = '&#x26A1;';
        text.textContent = 'Fetch Papers';
    }
}

function filterResearch(btn) {
    document.querySelectorAll('.research-filter').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentResearchPriority = btn.dataset.priority || '';
    fetchResearch(currentResearchPriority);
}
