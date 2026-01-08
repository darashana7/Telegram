/**
 * Minervini Stock Screener - Frontend Application
 * Handles API interactions, UI updates, and user interactions
 */

// ===== Configuration =====
// Railway backend URL - set this to your Railway deployment URL
// Leave empty to use Vercel's API endpoints (same origin)
const RAILWAY_URL = 'https://perceptive-harmony-production-5a8a.up.railway.app';

// Use Railway backend if configured, otherwise use same origin (Vercel)
const API_BASE = RAILWAY_URL || window.location.origin;

const PRESETS = {
    nifty50: 'RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK,BHARTIARTL,ITC,SBIN,LT,AXISBANK',
    banknifty: 'HDFCBANK,ICICIBANK,AXISBANK,KOTAKBANK,SBIN,INDUSINDBK,BANDHANBNK,FEDERALBNK,IDFCFIRSTB,PNB',
    it: 'TCS,INFY,WIPRO,HCLTECH,TECHM,LTIM,MPHASIS,COFORGE,PERSISTENT,LTTS',
    pharma: 'SUNPHARMA,DRREDDY,CIPLA,DIVISLAB,APOLLOHOSP,BIOCON,LUPIN,ALKEM,TORNTPHARM,ZYDUSLIFE',
    auto: 'MARUTI,TATAMOTORS,M&M,BAJAJ-AUTO,HEROMOTOCO,EICHERMOT,ASHOKLEY,TVSMOTORS,BOSCHLTD,TVSMOTOR'
};

// ===== DOM Elements =====
const elements = {
    healthStatus: document.getElementById('health-status'),
    symbolsInput: document.getElementById('symbols-input'),
    scanBtn: document.getElementById('scan-btn'),
    loadingContainer: document.getElementById('loading-container'),
    resultsContainer: document.getElementById('results-container'),
    stockCards: document.getElementById('stock-cards'),
    scannedCount: document.getElementById('scanned-count'),
    passingCount: document.getElementById('passing-count'),
    qualifyingCount: document.getElementById('qualifying-count'),
    lastScan: document.getElementById('last-scan'),
    toast: document.getElementById('toast'),
    toastMessage: document.getElementById('toast-message'),
    apiModal: document.getElementById('api-modal'),
    apiResponse: document.getElementById('api-response'),

    // Progress Tracking
    scanProgressContainer: document.getElementById('scan-progress-container'),
    progressPercent: document.getElementById('progress-percent'),
    progressCurrent: document.getElementById('progress-current'),
    progressTotal: document.getElementById('progress-total'),
    progressBarFill: document.getElementById('progress-bar-fill'),
    progressStatusText: document.getElementById('progress-status-text')
};

// State
let pollInterval = null;

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', () => {
    checkHealth();
    startStatusPolling();
    setInterval(checkHealth, 30000); // Check every 30 seconds
});

// ===== Status Polling =====
function startStatusPolling() {
    if (pollInterval) clearInterval(pollInterval);
    checkStatus();
    pollInterval = setInterval(checkStatus, 5000); // Poll every 5 seconds
}

async function checkStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status`);
        const data = await response.json();

        if (data.is_scanning) {
            updateProgress(data);
        } else {
            elements.scanProgressContainer.style.display = 'none';
        }
    } catch (error) {
        console.error('Error polling status:', error);
    }
}

function updateProgress(data) {
    elements.scanProgressContainer.style.display = 'block';

    const percent = Math.round((data.progress / data.total) * 100) || 0;
    elements.progressPercent.textContent = `${percent}%`;
    elements.progressCurrent.textContent = data.progress;
    elements.progressTotal.textContent = data.total;
    elements.progressBarFill.style.width = `${percent}%`;

    if (percent === 100) {
        elements.progressStatusText.textContent = 'Scan complete! Processing results...';
        setTimeout(() => elements.scanProgressContainer.style.display = 'none', 10000);
    } else {
        elements.progressStatusText.textContent = `Analyzing ${data.total} stocks...`;
    }
}

// ===== Health Check =====
async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/api/health`);
        const data = await response.json();

        if (data.status === 'healthy') {
            elements.healthStatus.className = 'status-badge healthy';
            elements.healthStatus.querySelector('.status-text').textContent = 'Live';

            // Update stats if available
            if (data.stats) {
                elements.qualifyingCount.textContent = data.stats.qualifying || '--';
                elements.lastScan.textContent = data.stats.last_scan_time || 'Recent';
            }
        } else {
            throw new Error('Unhealthy');
        }
    } catch (error) {
        elements.healthStatus.className = 'status-badge unhealthy';
        elements.healthStatus.querySelector('.status-text').textContent = 'Backend Offline';
    }
}

// ===== Stock Scanning =====
async function scanStocks() {
    const symbolsRaw = elements.symbolsInput.value.trim();
    if (!symbolsRaw) {
        showToast('Please enter stock symbols', 'error');
        return;
    }

    // Parse and clean symbols
    const symbols = symbolsRaw.split(',').map(s => s.trim().toUpperCase()).filter(s => s).slice(0, 10);

    if (symbols.length === 0) {
        showToast('Please enter valid stock symbols', 'error');
        return;
    }

    // Show loading
    elements.scanBtn.disabled = true;
    elements.loadingContainer.style.display = 'flex';
    elements.resultsContainer.style.display = 'none';

    try {
        const response = await fetch(`${API_BASE}/api/scan?symbols=${symbols.join(',')}`);
        const data = await response.json();

        if (data.success) {
            displayResults(data);
            showToast(`Scanned ${data.scanned} stocks`, 'success');
        } else {
            throw new Error(data.error || 'Scan failed');
        }
    } catch (error) {
        console.error('Scan error:', error);
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        elements.scanBtn.disabled = false;
        elements.loadingContainer.style.display = 'none';
    }
}

// ===== Display Results =====
function displayResults(data) {
    elements.resultsContainer.style.display = 'block';
    elements.scannedCount.textContent = data.scanned;
    elements.passingCount.textContent = data.passing;
    elements.qualifyingCount.textContent = data.passing;
    elements.lastScan.textContent = 'Just now';

    // Clear previous cards
    elements.stockCards.innerHTML = '';

    // Create cards for each result
    data.results.forEach(stock => {
        const card = createStockCard(stock);
        elements.stockCards.appendChild(card);
    });

    // Animate cards in
    const cards = elements.stockCards.querySelectorAll('.stock-card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        setTimeout(() => {
            card.style.transition = 'all 0.3s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
}

// ===== Create Stock Card =====
function createStockCard(stock) {
    const card = document.createElement('div');
    card.className = `stock-card ${stock.passes ? 'passing' : 'failing'}`;

    const scoreClass = stock.score >= 5 ? 'high' : stock.score >= 3 ? 'medium' : 'low';
    const pctFromHighClass = stock.pct_from_high <= 25 ? 'positive' : 'negative';
    const pctAboveLowClass = stock.pct_above_low >= 30 ? 'positive' : 'negative';

    card.innerHTML = `
        <div class="stock-header">
            <span class="stock-symbol">${stock.symbol}</span>
            <span class="stock-score ${scoreClass}">${stock.passes ? '✓' : '✗'} ${stock.score}/6</span>
        </div>
        <div class="stock-price">₹${formatNumber(stock.price)}</div>
        <div class="stock-metrics">
            <div class="metric">
                <span class="metric-label">50 SMA</span>
                <span class="metric-value">${stock.sma_50 ? '₹' + formatNumber(stock.sma_50) : 'N/A'}</span>
            </div>
            <div class="metric">
                <span class="metric-label">150 SMA</span>
                <span class="metric-value">${stock.sma_150 ? '₹' + formatNumber(stock.sma_150) : 'N/A'}</span>
            </div>
            <div class="metric">
                <span class="metric-label">From 52W High</span>
                <span class="metric-value ${pctFromHighClass}">${stock.pct_from_high ? stock.pct_from_high + '%' : 'N/A'}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Above 52W Low</span>
                <span class="metric-value ${pctAboveLowClass}">${stock.pct_above_low ? '+' + stock.pct_above_low + '%' : 'N/A'}</span>
            </div>
        </div>
    `;

    return card;
}

// ===== Preset Functions =====
function setPreset(presetName) {
    if (PRESETS[presetName]) {
        elements.symbolsInput.value = PRESETS[presetName];
        showToast(`Loaded ${presetName.toUpperCase()} preset`, 'success');
    }
}

// ===== API Testing =====
async function testEndpoint(endpoint) {
    try {
        showToast('Testing endpoint...', 'success');
        const response = await fetch(`${API_BASE}${endpoint}`);
        const data = await response.json();

        elements.apiResponse.textContent = JSON.stringify(data, null, 2);
        elements.apiModal.classList.add('show');
    } catch (error) {
        elements.apiResponse.textContent = `Error: ${error.message}`;
        elements.apiModal.classList.add('show');
    }
}

function closeModal() {
    elements.apiModal.classList.remove('show');
}

// Close modal on backdrop click
elements.apiModal?.addEventListener('click', (e) => {
    if (e.target === elements.apiModal) {
        closeModal();
    }
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
    }
});

// ===== Toast Notifications =====
function showToast(message, type = 'success') {
    elements.toast.className = `toast ${type} show`;
    elements.toastMessage.textContent = message;
    elements.toast.querySelector('.toast-icon').textContent = type === 'success' ? '✓' : '✗';

    setTimeout(() => {
        elements.toast.classList.remove('show');
    }, 3000);
}

// ===== Utility Functions =====
function formatNumber(num) {
    if (num === null || num === undefined) return 'N/A';
    return new Intl.NumberFormat('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(num);
}

// ===== About Modal =====
function showAbout() {
    alert('Minervini Stock Screener v2.0\n\nBuilt for NSE Stock Market\nUsing Mark Minervini\'s Trend Template\n\n© 2026');
}

// ===== Trigger Full Scan =====
async function triggerFullScan() {
    if (!confirm('Start scanning all 2000+ NSE stocks? This will run in the background on Railway.')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/scanall`, { method: 'POST' });
        const data = await response.json();

        if (data.status === 'started' || data.status === 'already_running') {
            showToast(data.message || 'Full scan running...', 'success');
            startStatusPolling(); // Ensure polling is active
        } else {
            showToast('Failed to start scan', 'error');
        }
    } catch (error) {
        showToast('Error: ' + error.message, 'error');
    }
}

// ===== Pulse Animation Handler =====
elements.symbolsInput?.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        scanStocks();
    }
});
