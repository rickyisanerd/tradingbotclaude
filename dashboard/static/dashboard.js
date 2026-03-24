let currentSection = 'overview';
let refreshTimer = null;

async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    return res.json();
}

function loadSection(section) {
    currentSection = section;
    document.querySelectorAll('.nav-links button').forEach(b => b.classList.remove('active'));
    document.getElementById('btn-' + section)?.classList.add('active');
    document.getElementById('content').innerHTML = '<div class="loading">Loading...</div>';
    render();
}

async function render() {
    const el = document.getElementById('content');
    try {
        switch (currentSection) {
            case 'overview': await renderOverview(el); break;
            case 'positions': await renderPositions(el); break;
            case 'trades': await renderTrades(el); break;
            case 'weights': await renderWeights(el); break;
            case 'health': await renderHealth(el); break;
            case 'audit': await renderAudit(el); break;
        }
    } catch (e) {
        el.innerHTML = `<div class="loading">Error: ${e.message}</div>`;
    }
}

async function renderOverview(el) {
    const data = await api('/api/overview');
    const s = data.stats;
    const pnlClass = s.total_pnl >= 0 ? 'positive' : 'negative';

    el.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total P&L</div>
                <div class="value ${pnlClass}">$${s.total_pnl.toFixed(2)}</div>
            </div>
            <div class="stat-card">
                <div class="label">Win Rate</div>
                <div class="value">${s.win_rate}%</div>
            </div>
            <div class="stat-card">
                <div class="label">Wins / Losses</div>
                <div class="value">${s.win_count} / ${s.loss_count}</div>
            </div>
            <div class="stat-card">
                <div class="label">Open Positions</div>
                <div class="value">${s.open_count}</div>
            </div>
        </div>

        <h3 class="section-title">Open Positions</h3>
        ${positionsTable(data.open_positions)}

        <h3 class="section-title">Recent Trades</h3>
        ${tradesTable(data.recent_trades)}

        <h3 class="section-title">Analyzer Weights</h3>
        ${weightsDisplay(data.weights)}

        <h3 class="section-title">Signal Source Health</h3>
        ${healthTable(data.health)}
    `;
}

async function renderPositions(el) {
    const data = await api('/api/overview');
    el.innerHTML = `<h3 class="section-title">Open Positions</h3>${positionsTable(data.open_positions)}`;
}

async function renderTrades(el) {
    const data = await api('/api/overview');
    el.innerHTML = `<h3 class="section-title">Trade History</h3>${tradesTable(data.recent_trades)}`;
}

async function renderWeights(el) {
    const data = await api('/api/overview');
    const history = await api('/api/weights/history');
    el.innerHTML = `
        <h3 class="section-title">Current Weights</h3>
        ${weightsDisplay(data.weights)}
        <h3 class="section-title">Weight History</h3>
        ${weightHistoryTable(history)}
    `;
}

async function renderHealth(el) {
    const data = await api('/api/health');
    el.innerHTML = `<h3 class="section-title">Signal Source Health</h3>${healthTable(data.sources)}`;
}

async function renderAudit(el) {
    const logs = await api('/api/audit');
    el.innerHTML = `<h3 class="section-title">Audit Log</h3>` +
        logs.map(l => `
            <div class="audit-entry">
                <span class="type">${l.event_type}</span>
                <span class="time">${l.created_at}</span>
                <div class="details">${l.details || ''}</div>
            </div>
        `).join('');
}

function positionsTable(positions) {
    if (!positions.length) return '<p style="color:var(--text-muted);padding:16px;">No open positions</p>';
    return `<table>
        <thead><tr><th>Symbol</th><th>Qty</th><th>Entry</th><th>Stop</th><th>Target</th><th>Score</th><th>Since</th></tr></thead>
        <tbody>${positions.map(p => `<tr>
            <td><strong>${p.symbol}</strong></td>
            <td>${p.qty}</td>
            <td>$${p.entry_price?.toFixed(2) || '-'}</td>
            <td>$${p.stop?.toFixed(2) || '-'}</td>
            <td>$${p.target?.toFixed(2) || '-'}</td>
            <td>${p.score?.toFixed(3) || '-'}</td>
            <td>${p.entry_time?.slice(0,10) || '-'}</td>
        </tr>`).join('')}</tbody>
    </table>`;
}

function tradesTable(trades) {
    if (!trades.length) return '<p style="color:var(--text-muted);padding:16px;">No trades yet</p>';
    return `<table>
        <thead><tr><th>Symbol</th><th>Status</th><th>P&L $</th><th>P&L %</th><th>Exit Reason</th><th>Score</th><th>Date</th></tr></thead>
        <tbody>${trades.map(t => {
            const cls = (t.pnl_dollars || 0) >= 0 ? 'pnl-positive' : 'pnl-negative';
            const badge = t.status === 'open' ? 'badge-open' : 'badge-closed';
            return `<tr>
                <td><strong>${t.symbol}</strong></td>
                <td><span class="badge ${badge}">${t.status}</span></td>
                <td class="${cls}">${t.pnl_dollars != null ? '$' + t.pnl_dollars.toFixed(2) : '-'}</td>
                <td class="${cls}">${t.pnl_pct != null ? (t.pnl_pct * 100).toFixed(2) + '%' : '-'}</td>
                <td>${t.exit_reason || '-'}</td>
                <td>${t.score?.toFixed(3) || '-'}</td>
                <td>${(t.exit_time || t.entry_time)?.slice(0,10) || '-'}</td>
            </tr>`;
        }).join('')}</tbody>
    </table>`;
}

function weightsDisplay(weights) {
    return `<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:24px;">
        ${Object.entries(weights).map(([name, w]) => `
            <div class="weight-bar-container" style="margin-bottom:10px;">
                <span style="width:140px;display:inline-block;font-size:13px;">${name}</span>
                <div style="flex:1;background:var(--border);border-radius:4px;height:8px;">
                    <div class="weight-bar" style="width:${(w * 100).toFixed(0)}%;"></div>
                </div>
                <span style="width:50px;text-align:right;font-size:13px;">${(w * 100).toFixed(1)}%</span>
            </div>
        `).join('')}
    </div>`;
}

function weightHistoryTable(history) {
    if (!history.length) return '<p style="color:var(--text-muted);padding:16px;">No weight updates yet</p>';
    return `<table>
        <thead><tr><th>Analyzer</th><th>Weight</th><th>Reason</th><th>Updated</th></tr></thead>
        <tbody>${history.map(w => `<tr>
            <td>${w.analyzer}</td>
            <td>${(w.weight * 100).toFixed(1)}%</td>
            <td>${w.reason}</td>
            <td>${w.updated_at}</td>
        </tr>`).join('')}</tbody>
    </table>`;
}

function healthTable(sources) {
    if (!sources || !sources.length) return '<p style="color:var(--text-muted);padding:16px;">No sources tracked yet</p>';
    return `<table>
        <thead><tr><th>Source</th><th>Status</th><th>Failures</th><th>Last Success</th><th>Last Failure</th></tr></thead>
        <tbody>${sources.map(s => {
            const badge = s.status === 'healthy' ? 'badge-healthy' : s.status === 'degraded' ? 'badge-degraded' : 'badge-down';
            return `<tr>
                <td>${s.source_name}</td>
                <td><span class="badge ${badge}">${s.status}</span></td>
                <td>${s.consecutive_failures}</td>
                <td>${s.last_success_at || '-'}</td>
                <td>${s.last_failure_at || '-'}</td>
            </tr>`;
        }).join('')}</tbody>
    </table>`;
}

async function triggerScan() {
    showToast('Running scan...');
    const result = await api('/api/trigger/scan', { method: 'POST' });
    const buys = result.buys?.length || 0;
    const watches = result.watches?.length || 0;
    showToast(`Scan complete: ${buys} buys, ${watches} watches`);
    render();
}

async function triggerRefresh() {
    showToast('Refreshing signals...');
    const result = await api('/api/trigger/refresh', { method: 'POST' });
    showToast('Signal refresh complete');
    render();
}

function showToast(msg) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4000);
}

// Initial load
loadSection('overview');

// Auto-refresh every 60 seconds
refreshTimer = setInterval(render, 60000);
