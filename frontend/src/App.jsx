import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Play, Settings, GitBranch, Key, Crosshair, FileCheck, List, Lock, X, Trash2, Loader, CheckCircle, XCircle, Clock, AlertCircle, RefreshCw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import './index.css';

// Parse issue link to extract repo URL and issue number
function parseIssueLink(link) {
  const trimmed = link.trim();
  // Full URL: https://github.com/owner/repo/issues/123
  const match = trimmed.match(/github\.com\/([^/]+\/[^/]+)\/issues\/(\d+)/);
  if (match) {
    return { repoUrl: `https://github.com/${match[1]}`, issueNum: parseInt(match[2]) };
  }
  return null;
}

// Status badge component
function StatusBadge({ status }) {
  const config = {
    running: { icon: <Loader size={12} className="spin-icon" />, color: 'var(--cs-color-semantic-warning)', label: 'Running' },
    completed: { icon: <CheckCircle size={12} />, color: 'var(--cs-color-semantic-success)', label: 'Completed' },
    failed: { icon: <XCircle size={12} />, color: 'var(--cs-color-semantic-danger)', label: 'Failed' },
    pending_approval: { icon: <AlertCircle size={12} />, color: 'var(--cs-color-semantic-info)', label: 'Needs Approval' },
  };
  const c = config[status] || { icon: <Clock size={12} />, color: 'var(--cs-color-text-muted)', label: status };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.7rem', color: c.color, fontWeight: 600 }}>
      {c.icon} {c.label}
    </span>
  );
}

function App() {
  const [authToken, setAuthToken] = useState(localStorage.getItem('auth_token') || null);
  const [passwordInput, setPasswordInput] = useState('');
  
  // Configuration State
  const [provider, setProvider] = useState(localStorage.getItem('provider') || 'gemini');
  const [model, setModel] = useState(localStorage.getItem('model') || 'gemini-3.5-pro');
  const [apiKey, setApiKey] = useState(localStorage.getItem('llm_api_key') || '');
  const [githubToken, setGithubToken] = useState(localStorage.getItem('github_token') || '');
  const [baseUrl, setBaseUrl] = useState(localStorage.getItem('base_url') || '');

  // Target State - single issue link only
  const [issueLink, setIssueLink] = useState(localStorage.getItem('issue_link') || '');

  // Execution State
  const [isRunning, setIsRunning] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [activeHuntId, setActiveHuntId] = useState(null);
  const [logs, setLogs] = useState([]);
  const [approvalBranch, setApprovalBranch] = useState(null);
  const [approvalDiff, setApprovalDiff] = useState(null);
  const [approvalHuntId, setApprovalHuntId] = useState(null);
  const logsEndRef = useRef(null);
  const pollRef = useRef(null);

  // Hunt List State
  const [hunts, setHunts] = useState([]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Save config to local storage
  useEffect(() => {
    localStorage.setItem('provider', provider);
    localStorage.setItem('model', model);
    localStorage.setItem('llm_api_key', apiKey);
    localStorage.setItem('github_token', githubToken);
    localStorage.setItem('base_url', baseUrl);
    localStorage.setItem('issue_link', issueLink);
  }, [provider, model, apiKey, githubToken, baseUrl, issueLink]);

  // Fetch hunts on load, auto-reconnect to running hunts
  const fetchHunts = () => {
    if (!authToken) return;
    fetch('/api/hunts', { headers: { 'Authorization': `Bearer ${authToken}` } })
      .then(res => res.json())
      .then(data => setHunts(data))
      .catch(err => console.error("Error fetching hunts:", err));
  };

  useEffect(() => {
    if (!authToken) return;
    fetch('/api/hunts', { headers: { 'Authorization': `Bearer ${authToken}` } })
      .then(res => res.json())
      .then(data => {
        setHunts(data);
        // Auto-reconnect to the most recent running hunt
        const runningHunt = data.find(h => h.status === 'running');
        if (runningHunt && !pollRef.current) {
          startPolling(runningHunt.id);
        }
      })
      .catch(err => console.error("Error fetching hunts:", err));

    const interval = setInterval(fetchHunts, 3000);
    return () => clearInterval(interval);
  }, [authToken]);

  // --- Polling logic ---
  const startPolling = async (huntId) => {
    // Stop any existing polling first
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    
    setActiveHuntId(huntId);
    setIsRunning(true);
    setLogs(['[SYSTEM] Loading hunt logs...']);
    
    // Load existing logs
    try {
      const res = await fetch(`/api/hunts/${huntId}/logs`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      const existingLogs = await res.json();
      if (existingLogs.length > 0) setLogs(existingLogs);
    } catch (e) {
      console.error('Failed to load logs:', e);
    }
    
    let lastLogCount = 0;
    pollRef.current = setInterval(async () => {
      try {
        const huntRes = await fetch('/api/hunts', {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const allHunts = await huntRes.json();
        setHunts(allHunts);
        const hunt = allHunts.find(h => h.id === huntId);
        
        if (!hunt || (hunt.status !== 'running')) {
          // Hunt finished — load final logs
          const logsRes = await fetch(`/api/hunts/${huntId}/logs`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
          });
          const finalLogs = await logsRes.json();
          setLogs(finalLogs);
          setIsRunning(false);
          setActiveHuntId(null);
          clearInterval(pollRef.current);
          pollRef.current = null;
          if (hunt && hunt.status === 'pending_approval') fetchPendingApprovals();
          return;
        }
        
        // Fetch latest logs
        const logsRes = await fetch(`/api/hunts/${huntId}/logs`, {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        const allLogs = await logsRes.json();
        if (allLogs.length > lastLogCount) {
          lastLogCount = allLogs.length;
          setLogs(allLogs);
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }, 3000);
  };

  // Cleanup polling on unmount
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  // --- Click hunt in sidebar to view/poll ---
  const handleSelectHunt = (hunt) => {
    if (hunt.status === 'running') {
      startPolling(hunt.id);
    } else {
      // Just load its logs into the terminal (no polling)
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      setActiveHuntId(hunt.id);
      setIsRunning(false);
      fetch(`/api/hunts/${hunt.id}/logs`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      })
        .then(res => res.json())
        .then(data => setLogs(data.length > 0 ? data : ['[SYSTEM] No logs for this hunt.']))
        .catch(() => setLogs(['[ERROR] Failed to load logs.']));
    }
  };

  // --- Delete hunt ---
  const handleDeleteHunt = async (e, huntId) => {
    e.stopPropagation(); // Don't trigger select
    if (!confirm('Delete this hunt and all its logs?')) return;
    try {
      await fetch(`/api/hunts/${huntId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      // If we were polling this hunt, stop
      if (activeHuntId === huntId) {
        if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        setActiveHuntId(null);
        setIsRunning(false);
        setLogs([]);
      }
      fetchHunts();
    } catch (err) {
      alert('Failed to delete hunt: ' + err.message);
    }
  };

  const handleRecreatePR = async (huntId) => {
    try {
      const res = await fetch(`/api/hunts/${huntId}/recreate-pr`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
        body: JSON.stringify({ github_token: githubToken })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to recreate PR');
      if (data.status === 'queued') {
        alert(data.message);
      } else {
        alert(`PR created successfully! Link: ${data.pr_url}`);
      }
      fetchHunts();
    } catch (err) {
      alert(err.message);
    }
  };

  // --- Approvals ---
  const handleApprove = async (action) => {
    if (!approvalHuntId) return;
    try {
      await fetch('/api/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
        body: JSON.stringify({ hunt_id: approvalHuntId, action })
      });
      setApprovalBranch(null);
      setApprovalDiff(null);
      setApprovalHuntId(null);
    } catch (e) {
      alert("Error: " + e.message);
    }
  };

  const fetchPendingApprovals = async () => {
    try {
      const res = await fetch('/api/approvals', { headers: { 'Authorization': `Bearer ${authToken}` } });
      const data = await res.json();
      if (data.pending && data.pending.length > 0) {
        setApprovalBranch(data.pending[0].branch);
        setApprovalDiff(data.pending[0].diff);
        setApprovalHuntId(data.pending[0].hunt_id);
      } else {
        setApprovalBranch(null);
        setApprovalDiff(null);
        setApprovalHuntId(null);
      }
    } catch (e) { console.error(e); }
  };

  useEffect(() => { if (authToken) fetchPendingApprovals(); }, [authToken]);

  // --- Auth ---
  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: passwordInput })
      });
      if (res.ok) {
        const data = await res.json();
        setAuthToken(data.token);
        localStorage.setItem('auth_token', data.token);
      } else {
        alert("Invalid password");
      }
    } catch (e) { console.error("Login error", e); }
  };

  const handleLogout = () => {
    setAuthToken(null);
    localStorage.removeItem('auth_token');
  };

  // --- Start Hunt (from issue link) ---
  const handleStartHunt = async () => {
    const parsed = parseIssueLink(issueLink);
    if (!parsed) {
      alert("Please enter a valid GitHub issue link (e.g. https://github.com/owner/repo/issues/123)");
      return;
    }
    if (!apiKey || !githubToken) {
      alert("Please fill in API Key and GitHub Token!");
      return;
    }

    setIsStarting(true);

    try {
      const res = await fetch('/api/hunt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
        body: JSON.stringify({
          repo_url: parsed.repoUrl,
          issues: [parsed.issueNum],
          provider, model,
          api_key: apiKey,
          github_token: githubToken,
          base_url: baseUrl || undefined
        })
      });

      if (!res.ok) throw new Error("Server responded with " + res.status);

      // Process SSE stream asynchronously to keep Vercel alive
      (async () => {
        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let hid = null;
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            let boundary = buffer.indexOf('\n\n');
            while (boundary !== -1) {
              const chunk = buffer.slice(0, boundary);
              buffer = buffer.slice(boundary + 2);
              if (chunk.startsWith('data: ')) {
                let msg = chunk.slice(6).replace(/__NEWLINE__/g, '\n');
                if (msg.startsWith('Workflow queued. Hunt ID: ')) {
                  hid = msg.split('Hunt ID: ')[1].trim();
                  setIsStarting(false);
                  setIssueLink('');
                  fetchHunts();
                  startPolling(hid); // Switch to the new hunt
                }
              }
              boundary = buffer.indexOf('\n\n');
            }
          }
        } catch (err) {
          console.error("Stream error:", err);
        }
        if (hid) fetchHunts(); // Refresh when hunt completes
      })();

    } catch (error) {
      console.error("Failed to start hunt", error);
      setIsStarting(false);
      alert(`[ERROR] ${error.message}`);
    }
  };

  // --- Diff renderer ---
  const renderDiff = (diffStr) => {
    if (!diffStr) return <div style={{ color: 'var(--cs-color-text-muted)' }}>No diff available.</div>;
    return diffStr.split('\n').map((line, i) => {
      let color = 'var(--cs-color-text-primary)', background = 'transparent';
      if (line.startsWith('+') && !line.startsWith('+++')) { color = 'var(--cs-color-semantic-success)'; background = 'rgba(45, 122, 56, 0.1)'; }
      else if (line.startsWith('-') && !line.startsWith('---')) { color = 'var(--cs-color-semantic-danger)'; background = 'rgba(169, 35, 35, 0.1)'; }
      else if (line.startsWith('@@')) color = 'var(--cs-color-semantic-info)';
      return <div key={i} style={{ color, background, fontFamily: 'JetBrains Mono, monospace', whiteSpace: 'pre-wrap', padding: '0 4px' }}>{line || ' '}</div>;
    });
  };

  // --- Login screen ---
  if (!authToken) {
    return (
      <div className="app-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div className="cs-panel" style={{ width: '400px', textAlign: 'center' }}>
          <Lock size={48} style={{ color: 'var(--cs-color-brand-umber)', marginBottom: '1rem' }} />
          <h2>Authentication Required</h2>
          <form onSubmit={handleLogin} style={{ marginTop: '2rem' }}>
            <div className="cs-field">
              <label className="cs-field__label">Admin Password</label>
              <input className="cs-field__control" type="password" value={passwordInput} onChange={e => setPasswordInput(e.target.value)} placeholder="Enter password..." />
            </div>
            <button className="cs-button" type="submit" style={{ width: '100%', marginTop: '1rem' }}>Login</button>
          </form>
        </div>
      </div>
    );
  }

  // --- Group hunts by repo ---
  const grouped = {};
  hunts.forEach(hunt => {
    const repo = hunt.repo_url.split('/').slice(-2).join('/');
    if (!grouped[repo]) grouped[repo] = [];
    grouped[repo].push(hunt);
  });

  return (
    <div className="app-container" style={{ maxWidth: '100%', padding: '2rem' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1>Issue Hunter</h1>
          <p style={{ color: 'var(--cs-color-text-muted)', marginTop: '0.5rem' }}>
            Autonomous AI agent for fixing open-source bugs.
          </p>
        </div>
        <button className="cs-button cs-button--danger cs-button--sm" onClick={handleLogout}>Logout</button>
      </header>

      <div style={{ display: 'flex', gap: '2rem', alignItems: 'flex-start' }}>
        {/* Left Sidebar: Hunting List */}
        <div className="cs-panel" style={{ width: '320px', flexShrink: 0, maxHeight: '85vh', overflowY: 'auto' }}>
          <h2><List size={20} /> Hunting List</h2>
          {hunts.length === 0 ? (
            <p style={{ color: 'var(--cs-color-text-muted)' }}>No hunts yet. Start one!</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {Object.entries(grouped).map(([repo, rHunts]) => (
                <div key={repo}>
                  <div style={{
                    fontWeight: 'bold', fontSize: '0.8rem', color: 'var(--cs-color-text-muted)',
                    textTransform: 'uppercase', letterSpacing: '0.05em',
                    borderBottom: '1px solid rgba(69, 33, 14, 0.1)', paddingBottom: '0.4rem', marginBottom: '0.5rem'
                  }}>
                    <a href={`https://github.com/${repo}`} target="_blank" rel="noreferrer" style={{ color: 'inherit', textDecoration: 'none' }} className="hover:underline">
                      {repo}
                    </a>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    {rHunts.map(hunt => (
                      <div
                        key={hunt.id}
                        onClick={() => handleSelectHunt(hunt)}
                        style={{
                          padding: '0.6rem 0.75rem',
                          background: activeHuntId === hunt.id ? 'var(--cs-color-surface-page)' : 'transparent',
                          borderRadius: '8px',
                          cursor: 'pointer',
                          border: `1px solid ${activeHuntId === hunt.id ? 'var(--cs-color-brand-umber)' : 'transparent'}`,
                          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: '0.875rem', fontWeight: 500 }}>
                            Issue {hunt.issues.map((iss, i) => (
                              <React.Fragment key={iss}>
                                <a 
                                  href={`https://github.com/${repo}/issues/${iss}`} 
                                  target="_blank" 
                                  rel="noreferrer" 
                                  onClick={e => e.stopPropagation()} 
                                  style={{ color: 'inherit', textDecoration: 'none' }} 
                                  className="hover:underline"
                                >
                                  #{iss}
                                </a>
                                {i < hunt.issues.length - 1 ? ', ' : ''}
                              </React.Fragment>
                            ))}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem' }}>
                            <StatusBadge status={hunt.status} />
                            <span style={{ fontSize: '0.7rem', color: 'var(--cs-color-text-muted)' }}>
                              {new Date(hunt.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                        <button
                          onClick={(e) => handleDeleteHunt(e, hunt.id)}
                          title="Delete hunt"
                          style={{
                            background: 'transparent', border: 'none', color: 'var(--cs-color-text-muted)',
                            cursor: 'pointer', padding: '4px', borderRadius: '4px',
                            opacity: 0.5, transition: 'opacity 0.15s'
                          }}
                          onMouseEnter={e => e.currentTarget.style.opacity = 1}
                          onMouseLeave={e => e.currentTarget.style.opacity = 0.5}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Main Content */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          <div className="grid-2">
            {/* Configuration Panel */}
            <div className="cs-panel">
              <h2><Settings size={20} /> Configuration</h2>
              <div className="grid-2">
                <div className="cs-field">
                  <label className="cs-field__label">LLM Provider</label>
                  <select className="cs-field__control" value={provider} onChange={e => setProvider(e.target.value)}>
                    <option value="gemini">Google Gemini</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                  </select>
                </div>
                <div className="cs-field">
                  <label className="cs-field__label">Model</label>
                  <input className="cs-field__control" type="text" value={model} onChange={e => setModel(e.target.value)} placeholder="e.g. gemini-3.5-pro" />
                </div>
              </div>
              <div className="cs-field">
                <label className="cs-field__label"><Key size={14} style={{display:'inline', marginRight:4}} /> API Key</label>
                <input className="cs-field__control" type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="Your LLM API Key" />
              </div>
              <div className="cs-field">
                <label className="cs-field__label"><GitBranch size={14} style={{display:'inline', marginRight:4}} /> GitHub Token</label>
                <input className="cs-field__control" type="password" value={githubToken} onChange={e => setGithubToken(e.target.value)} placeholder="ghp_xxxxxxxxxxxx" />
              </div>
              <div className="cs-field">
                <label className="cs-field__label">Custom Base URL (Optional)</label>
                <input className="cs-field__control" type="text" value={baseUrl} onChange={e => setBaseUrl(e.target.value)} placeholder="e.g. http://localhost:11434/v1" />
              </div>
            </div>

            {/* Target Panel */}
            <div className="cs-panel">
              <h2><Crosshair size={20} /> Target Mission</h2>
              <div className="cs-field">
                <label className="cs-field__label">GitHub Issue Link</label>
                <input className="cs-field__control"
                  type="text" 
                  value={issueLink} 
                  onChange={e => setIssueLink(e.target.value)}
                  placeholder="https://github.com/owner/repo/issues/123"
                />
                {issueLink && parseIssueLink(issueLink) && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--cs-color-semantic-success)', marginTop: '0.25rem' }}>
                    ✓ Repo: {parseIssueLink(issueLink).repoUrl.split('/').slice(-2).join('/')} · Issue #{parseIssueLink(issueLink).issueNum}
                  </div>
                )}
                {issueLink && !parseIssueLink(issueLink) && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--cs-color-semantic-danger)', marginTop: '0.25rem' }}>
                    ✗ Invalid format. Use: https://github.com/owner/repo/issues/123
                  </div>
                )}
              </div>

              <button className="cs-button" onClick={handleStartHunt} disabled={isStarting} style={{ marginTop: '1rem' }}>
                {isStarting ? (
                  <><Loader size={18} className="spin-icon" /> Starting...</>
                ) : (
                  <><Play size={18} /> Start Hunt</>
                )}
              </button>
            </div>
          </div>

          {/* Terminal or Report */}
          {activeHuntId && hunts.find(h => h.id === activeHuntId)?.status === 'completed' && hunts.find(h => h.id === activeHuntId)?.report_md ? (
            <div className="cs-panel" style={{ height: '500px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <CheckCircle size={20} color="var(--cs-color-semantic-success)" />
                  <h2 style={{ margin: 0, color: 'var(--cs-color-semantic-success)' }}>Mission Accomplished</h2>
                </div>
                <button className="cs-button" onClick={() => handleRecreatePR(activeHuntId)}>
                  <RefreshCw size={16} style={{ marginRight: '6px' }} />
                  Re-create PR
                </button>
              </div>
              <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', background: '#ffffff', borderRadius: '8px', border: '1px solid rgba(69, 33, 14, 0.1)', lineHeight: '1.6' }}>
                <ReactMarkdown>{hunts.find(h => h.id === activeHuntId).report_md}</ReactMarkdown>
              </div>
            </div>
          ) : (
            <div className="terminal-wrapper">
              <div className="terminal-header">
                <div className="terminal-dots">
                  <div className="terminal-dot dot-red"></div>
                  <div className="terminal-dot dot-yellow"></div>
                  <div className="terminal-dot dot-green"></div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Terminal size={14} /> Agent Live Terminal
                  {isRunning && <Loader size={12} className="spin-icon" style={{ color: 'var(--cs-color-semantic-warning)' }} />}
                  {activeHuntId && <span style={{ fontSize: '0.7rem', color: 'var(--cs-color-text-muted)' }}>({activeHuntId.slice(0,8)}...)</span>}
                </div>
                <button 
                  onClick={() => setLogs([])}
                  style={{
                    background: 'transparent', border: '1px solid rgba(69, 33, 14, 0.1)', 
                    color: 'var(--cs-color-text-muted)', borderRadius: '4px',
                    padding: '2px 8px', fontSize: '0.75rem', cursor: 'pointer', marginLeft: 'auto'
                  }}
                >
                  Clear
                </button>
              </div>
              <div className="terminal-content">
                {logs.length === 0 ? (
                  <div style={{ color: 'var(--cs-color-text-muted)', fontStyle: 'italic' }}>
                    Waiting for mission control... Click a hunt or start a new one.
                  </div>
                ) : (
                  logs.map((log, i) => (
                    <div 
                      key={i} 
                      className={`log-entry ${log.includes('ERROR') || log.includes('Failed') || log.includes('Exception') ? 'error' : log.includes('Successfully') || log.includes('Complete') || log.includes('APPROVED') ? 'success' : log.includes('Phase') || log.includes('ATTEMPT') ? 'phase' : 'info'}`}
                    >
                      {log}
                    </div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          )}

          {/* Approval Dashboard */}
          {approvalBranch && (
            <div className="cs-panel" style={{ border: '1px solid var(--cs-color-semantic-warning)', boxShadow: '0 0 20px rgba(140, 91, 0, 0.1)' }}>
              <h2><FileCheck size={20} /> Action Required: Approve PR Creation</h2>
              <p style={{ marginBottom: '1rem', color: 'var(--cs-color-text-muted)' }}>
                 <strong style={{color: 'var(--cs-color-brand-umber)'}}>{approvalBranch}</strong> is ready for PR.
              </p>
              <div style={{
                background: '#ffffff', borderRadius: '8px', padding: '1rem',
                maxHeight: '400px', overflowY: 'auto', marginBottom: '1rem',
                border: '1px solid rgba(69, 33, 14, 0.1)'
              }}>
                {renderDiff(approvalDiff)}
              </div>
              <div style={{ display: 'flex', gap: '1rem' }}>
                <button className="cs-button" style={{ background: 'var(--cs-color-semantic-success)' }} onClick={() => handleApprove('approve')}>
                  Approve & Create PR
                </button>
                <button className="cs-button cs-button--danger cs-button--sm" onClick={() => handleApprove('reject')}>
                  Reject
                </button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}

export default App;
