import React, { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { ShieldAlert, Activity, Cpu, Sparkles, ShieldCheck, Play, Pause, Siren, ChevronDown, ChevronUp, Filter, Settings2, Clock3 } from 'lucide-react';
import './index.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? '' : 'http://localhost:5000');
const OFFLINE_CACHE_KEY = 'sentinel_offline_data';
const DEMO_TOKEN_KEY = 'sentinel_demo_admin_token';
const DEMO_TOKEN_FALLBACK = import.meta.env.VITE_DEMO_ADMIN_TOKEN || '';
const CHART_WINDOWS = ['1h', '5h', '24h'];
const WINDOW_META = {
  '1h': { label: 'Last 1 hour', bucket: '1-minute buckets' },
  '5h': { label: 'Last 5 hours', bucket: '5-minute buckets' },
  '24h': { label: 'Last 24 hours', bucket: '15-minute buckets' },
};

function App() {
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState({ requests: 0, anomalies: 0, activeIps: 0 });
  const [chartData, setChartData] = useState([]);
  const [insightData, setInsightData] = useState({});
  const [isConnected, setIsConnected] = useState(true);
  const [demoState, setDemoState] = useState({ running: false, attack_enabled: false });
  const [demoMode, setDemoMode] = useState(false);
  const [demoMessage, setDemoMessage] = useState('');
  const [adminTokenInput, setAdminTokenInput] = useState(localStorage.getItem(DEMO_TOKEN_KEY) || DEMO_TOKEN_FALLBACK || '');
  const [controlBusy, setControlBusy] = useState(false);
  const [demoPanelOpen, setDemoPanelOpen] = useState(false);
  const [selectedType, setSelectedType] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [selectedWindow, setSelectedWindow] = useState('1h');

  const fetchDashboardData = async () => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/dashboard?window=${selectedWindow}`);
      if (!resp.ok) throw new Error("Backend error");
      const data = await resp.json();
      setAlerts(data.alerts);
      setStats(data.stats);
      setChartData(data.chart);
      setIsConnected(true);
      
      // Cache latest DB payload for offline mode
      localStorage.setItem(OFFLINE_CACHE_KEY, JSON.stringify(data));
    } catch {
      console.error("Dashboard backend offline. Loading local cache.");
      setIsConnected(false);
      
      const cached = localStorage.getItem(OFFLINE_CACHE_KEY);
      if (cached) {
        const parsed = JSON.parse(cached);
        setAlerts(parsed.alerts);
        setStats(parsed.stats);
        setChartData(parsed.chart);
      } else {
        // Fallback UI data if no cache exists
        setStats({ requests: 842, anomalies: 2, activeIps: 5 });
        setChartData([
          { time: '12:00', reqs: 12 }, { time: '12:10', reqs: 18 },
          { time: '12:20', reqs: 140 }, { time: '12:30', reqs: 15 }
        ]);
        setAlerts([
          { id: "mock1", ip_address: '99.99.99.99', type: 'Rule-based', reason: 'Offline Mock: High request rate.' }
        ]);
      }
    }
  };

  const fetchDemoStatus = async () => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/demo/status`);
      if (!resp.ok) throw new Error('Demo status fetch failed');
      const data = await resp.json();
      setDemoMode(Boolean(data.demo_mode));
      setDemoState(data.state || { running: false, attack_enabled: false });
      if (!data.demo_mode) {
        setDemoMessage('Demo control mode is disabled on server.');
      }
    } catch {
      setDemoMessage('Demo control status unavailable.');
    }
  };

  const callDemoControl = async (path, payload = null) => {
    const token = localStorage.getItem(DEMO_TOKEN_KEY) || DEMO_TOKEN_FALLBACK || '';
    if (!token) {
      setDemoMessage('Enter admin access code to use demo controls.');
      return;
    }

    setControlBusy(true);
    try {
      const resp = await fetch(`${API_BASE_URL}${path}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Token': token,
        },
        body: payload ? JSON.stringify(payload) : undefined,
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || 'Control request failed');
      }

      setDemoMessage(data.message || 'Demo control updated.');
      await fetchDemoStatus();
    } catch (error) {
      setDemoMessage(error.message || 'Control request failed.');
    } finally {
      setControlBusy(false);
    }
  };

  const saveAdminToken = () => {
    const value = adminTokenInput.trim();
    if (!value) {
      localStorage.removeItem(DEMO_TOKEN_KEY);
      setDemoMessage('Admin token cleared.');
      return;
    }
    localStorage.setItem(DEMO_TOKEN_KEY, value);
    setDemoMessage('Admin token saved for this browser.');
  };

  const updateAlertStatus = async (alertId, status) => {
    try {
      const resp = await fetch(`${API_BASE_URL}/api/alerts/${alertId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status }),
      });

      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.error || 'Failed to update alert status.');
      }

      setAlerts(prev => prev.map(alert => {
        const currentId = alert.id || alert._id;
        if (currentId === alertId) {
          return { ...alert, status: data.alert?.status || status };
        }
        return alert;
      }));
    } catch (error) {
      setDemoMessage(error.message || 'Failed to update alert status.');
    }
  };

  const filteredAlerts = alerts.filter(alert => {
    const alertType = alert.type || 'unknown';
    const alertStatus = (alert.status || 'new').toLowerCase();
    const typeMatches = selectedType === 'all' || alertType === selectedType;
    const statusMatches = selectedStatus === 'all' || alertStatus === selectedStatus;
    return typeMatches && statusMatches;
  });

  const currentWindowMeta = WINDOW_META[selectedWindow] || WINDOW_META['1h'];

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 5000);
    return () => clearInterval(interval);
  }, [selectedWindow]);

  useEffect(() => {
    fetchDemoStatus();
    const demoInterval = setInterval(fetchDemoStatus, 5000);
    return () => clearInterval(demoInterval);
  }, []);

  const explainAnomaly = async (alertId, ip) => {
    setInsightData(prev => ({ ...prev, [alertId]: "Loading AI Analysis..." }));
    try {
      const resp = await fetch(`${API_BASE_URL}/api/explain/${alertId}`);
      const data = await resp.json();
      setInsightData(prev => ({ ...prev, [alertId]: data.insight || "Insight unavailable." }));
    } catch {
      setTimeout(() => {
        const insight = `User at IP ${ip} exhibits baseline suspicious behavior. Backend ML endpoint unreachable.`;
        setInsightData(prev => ({ ...prev, [alertId]: insight }));
      }, 500);
    }
  };

  return (
    <div className="dashboard-container">
      <header className="header">
        <h1>SentinelAI</h1>
        <div className={`header-status ${!isConnected ? 'header-status-disconnected' : ''}`}>
          <div className={`status-dot ${!isConnected ? 'status-dot-disconnected' : ''}`}></div>
          {isConnected ? "Monitoring Active" : "Backend Offline"}
        </div>
      </header>

      <div className="grid-metrics">
        <div className="glass-panel metric-card">
          <div className="metric-title metric-title-row">
            <Activity size={16} /> Total Traffic ({selectedWindow})
          </div>
          <div className="metric-value">{stats.requests}</div>
        </div>
        <div className="glass-panel metric-card">
          <div className="metric-title metric-title-row">
            <ShieldAlert size={16} color="var(--accent-red)" /> Anomalies Detected
          </div>
          <div className="metric-value metric-value-alert">{stats.anomalies}</div>
        </div>
        <div className="glass-panel metric-card">
          <div className="metric-title metric-title-row">
            <Cpu size={16} /> Tracked IPs
          </div>
          <div className="metric-value">{stats.activeIps}</div>
        </div>
      </div>

      <div className="demo-toggle-row">
        <button className="btn-toggle-demo" onClick={() => setDemoPanelOpen(prev => !prev)}>
          <Settings2 size={16} />
          {demoPanelOpen ? 'Hide Demo Controls' : 'Run Demo'}
          {demoPanelOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        <span className="demo-toggle-hint">Demo controls stay hidden until you open them.</span>
      </div>

      {demoPanelOpen && (
        <div className="glass-panel demo-controls">
          <div className="panel-header">
            <h2 className="panel-title panel-title-row"><ShieldCheck size={18} /> Demo Controls</h2>
            <span className="panel-chip">
              {demoState.running ? 'Simulator Running' : 'Simulator Stopped'}
            </span>
          </div>
          <p className="demo-note">
            Admin-only controls for live interview demo. Enter access code, then control simulator traffic.
          </p>
          <div className="token-row">
            <input
              className="token-input"
              type="password"
              placeholder="Enter admin access code"
              value={adminTokenInput}
              onChange={(e) => setAdminTokenInput(e.target.value)}
            />
            <button className="btn-dev" onClick={saveAdminToken}>Save Code</button>
          </div>
          <div className="control-row">
            <button
              className="btn-dev btn-dev-primary"
              disabled={!demoMode || controlBusy || demoState.running}
              onClick={() => callDemoControl('/api/demo/start')}
            >
              <Play size={14} /> Start Traffic
            </button>
            <button
              className="btn-dev btn-dev-danger"
              disabled={!demoMode || controlBusy || !demoState.running}
              onClick={() => callDemoControl('/api/demo/stop')}
            >
              <Pause size={14} /> Stop Traffic
            </button>
            <button
              className="btn-dev"
              disabled={!demoMode || controlBusy || !demoState.running || demoState.attack_enabled}
              onClick={() => callDemoControl('/api/demo/attack', { enabled: true })}
            >
              <Siren size={14} /> Attack ON
            </button>
            <button
              className="btn-dev"
              disabled={!demoMode || controlBusy || !demoState.running || !demoState.attack_enabled}
              onClick={() => callDemoControl('/api/demo/attack', { enabled: false })}
            >
              <Siren size={14} /> Attack OFF
            </button>
          </div>
          <p className="demo-note">
            {demoState.attack_enabled ? 'Attack traffic is ON.' : 'Attack traffic is OFF.'}
          </p>
          {demoMessage && <p className="demo-message">{demoMessage}</p>}
        </div>
      )}

      <div className="grid-main">
        <div className="glass-panel">
          <div className="panel-header">
            <h2 className="panel-title">Traffic Volume / Minute</h2>
            <span className="panel-chip">
              {currentWindowMeta.label}
            </span>
          </div>
          <div className="window-switcher" role="tablist" aria-label="Traffic chart time range">
            <div className="window-switcher-label"><Clock3 size={14} /> Time Window</div>
            <div className="window-switcher-buttons">
              {CHART_WINDOWS.map((windowKey) => (
                <button
                  key={windowKey}
                  className={`btn-window ${selectedWindow === windowKey ? 'btn-window-active' : ''}`}
                  onClick={() => setSelectedWindow(windowKey)}
                >
                  {windowKey}
                </button>
              ))}
            </div>
          </div>
          <p className="chart-meta">Aggregation: {currentWindowMeta.bucket}</p>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="time" stroke="#a0aab2" />
                <YAxis stroke="#a0aab2" />
                <Tooltip contentStyle={{ backgroundColor: '#1a1c23', border: 'none', borderRadius: '8px' }} />
                <Line type="monotone" dataKey="reqs" stroke="var(--accent-blue)" strokeWidth={3} dot={{ fill: 'var(--accent-blue)', r: 4 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="alerts-column">
          <div className="glass-panel filters-panel">
            <div className="panel-header">
              <h2 className="panel-title panel-title-row"><Filter size={18} /> Alert Filters</h2>
              <span className="panel-chip">{filteredAlerts.length} shown</span>
            </div>
            <div className="filter-row">
              <label className="filter-field">
                <span>Type</span>
                <select value={selectedType} onChange={(e) => setSelectedType(e.target.value)}>
                  <option value="all">All</option>
                  <option value="Rule-based">Rule-based</option>
                  <option value="ML-based">ML-based</option>
                </select>
              </label>
              <label className="filter-field">
                <span>Status</span>
                <select value={selectedStatus} onChange={(e) => setSelectedStatus(e.target.value)}>
                  <option value="all">All</option>
                  <option value="new">New</option>
                  <option value="investigating">Investigating</option>
                  <option value="resolved">Resolved</option>
                </select>
              </label>
            </div>
          </div>

          <div className="glass-panel">
            <div className="panel-header">
              <h2 className="panel-title">Recent Alerts</h2>
              <span className="panel-chip">
                Latest 20 Anomalies
              </span>
            </div>
            <div className="alert-list">
              {filteredAlerts.length === 0 ? (
                <p className="empty-state">No anomalies detected yet.</p>
              ) : (
                filteredAlerts.map((alert) => (
                  <div key={alert.id || alert._id} className="alert-item">
                    <div className="alert-header">
                      <span className="alert-ip">{alert.ip_address}</span>
                      <div className="alert-badges">
                        <span className="alert-badge">{alert.type}</span>
                        <span className={`alert-status-badge alert-status-${(alert.status || 'new').toLowerCase()}`}>{alert.status || 'new'}</span>
                      </div>
                    </div>
                    <div className="alert-reason">{alert.reason}</div>
                    <div className="alert-meta">
                      <span className="alert-meta-chip">Severity: {alert.severity || 'medium'}</span>
                      <span className="alert-meta-chip">Confidence: {alert.confidence ?? 70}%</span>
                    </div>
                    <div className="alert-actions">
                      <button className="btn-mini" onClick={() => updateAlertStatus(alert.id || alert._id, 'investigating')}>Investigating</button>
                      <button className="btn-mini" onClick={() => updateAlertStatus(alert.id || alert._id, 'resolved')}>Resolved</button>
                    </div>
                    <button className="btn-insight" onClick={() => explainAnomaly(alert.id || alert._id, alert.ip_address)}>
                      <Sparkles size={14} /> Explain Anomaly
                    </button>
                    {insightData[alert.id || alert._id] && (
                      <div className="ai-insight-box">
                        <strong>AI Insight:</strong> {insightData[alert.id || alert._id]}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
