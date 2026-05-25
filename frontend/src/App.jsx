import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Play, Settings, GitBranch, Key, Crosshair, FileCheck, History, List, Lock } from 'lucide-react';
import './index.css';

function App() {
  const [authToken, setAuthToken] = useState(localStorage.getItem('auth_token') || null);
  const [passwordInput, setPasswordInput] = useState('');
  
  const [activeTab, setActiveTab] = useState('hunt'); // 'hunt' or 'history' or 'benchmark'
  // Configuration State
  const [provider, setProvider] = useState('gemini');
  const [model, setModel] = useState('gemini-3.5-pro');
  const [apiKey, setApiKey] = useState(localStorage.getItem('llm_api_key') || '');
  const [githubToken, setGithubToken] = useState(localStorage.getItem('github_token') || '');

  // Target State
  const [repoUrl, setRepoUrl] = useState('');
  const [issueLinks, setIssueLinks] = useState('');
  
  // Benchmark State
  const [benchmarkInput, setBenchmarkInput] = useState('[\n  {\n    "repo_url": "https://github.com/chalk/chalk",\n    "issues": [669]\n  }\n]');

  // Execution State
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [approvalBranch, setApprovalBranch] = useState(null);
  const [approvalDiff, setApprovalDiff] = useState(null);
  const wsRef = useRef(null);
  const logsEndRef = useRef(null);

  // History State
  const [hunts, setHunts] = useState([]);
  const [selectedHunt, setSelectedHunt] = useState(null);
  const [selectedHuntLogs, setSelectedHuntLogs] = useState([]);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Fetch hunts for history tab
  useEffect(() => {
    if (activeTab === 'history' && authToken) {
      fetch('http://localhost:8000/api/hunts', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      })
        .then(res => res.json())
        .then(data => setHunts(data))
        .catch(err => console.error("Error fetching hunts:", err));
    }
  }, [activeTab, authToken]);

  const handleSelectHunt = async (hunt) => {
    setSelectedHunt(hunt);
    try {
      const res = await fetch(`http://localhost:8000/api/hunts/${hunt.id}/logs`, {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      const logsData = await res.json();
      setSelectedHuntLogs(logsData);
    } catch (e) {
      console.error(e);
    }
  };

  // Save config to local storage
  useEffect(() => {
    localStorage.setItem('llm_api_key', apiKey);
    localStorage.setItem('github_token', githubToken);
  }, [apiKey, githubToken]);

  const handleApprove = async (action) => {
    const repoName = repoUrl.split('/').pop();
    try {
      await fetch('http://localhost:8000/api/approve', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ repo_name: repoName, action })
      });
      setApprovalBranch(null);
    } catch (e) {
      alert("Error sending approval: " + e.message);
    }
  };

  const fetchPendingApprovals = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/approvals', {
        headers: { 'Authorization': `Bearer ${authToken}` }
      });
      const data = await res.json();
      if (data.pending && data.pending.length > 0) {
        setApprovalBranch(data.pending[0].branch);
        setApprovalDiff(data.pending[0].diff);
      } else {
        setApprovalBranch(null);
        setApprovalDiff(null);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    if (authToken) fetchPendingApprovals();
  }, [authToken]);

  useEffect(() => {
    if (!authToken) return;
    const ws = new WebSocket('ws://localhost:8000/ws/stream');
    
    ws.onmessage = (event) => {
      const msg = event.data;
      setLogs((prev) => [...prev, msg]);
      
      if (msg.startsWith('__APPROVAL_REQUIRED__:')) {
        fetchPendingApprovals();
      }
    };

    wsRef.current = ws;
    return () => ws.close();
  }, [authToken]);

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('http://localhost:8000/api/login', {
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
    } catch (e) {
      console.error("Login error", e);
    }
  };

  const handleLogout = () => {
    setAuthToken(null);
    localStorage.removeItem('auth_token');
  };

  const handleStartHunt = async () => {
    if (!apiKey || !githubToken || !repoUrl || !issueLinks) {
      alert("Please fill in all required fields!");
      return;
    }

    setIsRunning(true);
    setApprovalBranch(null);
    setLogs(["[SYSTEM] Connecting to Issue Hunter Backend..."]);

    const issueNum = parseInt(issueLinks.split('/').pop());

    try {
      await fetch('http://localhost:8000/api/hunt', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          repo_url: repoUrl,
          issues: [issueNum],
          provider: provider,
          model: model,
          api_key: apiKey,
          github_token: githubToken
        })
      });
    } catch (error) {
      console.error("Failed to start hunt", error);
      setIsRunning(false);
    }
  };

  const handleApproval = async (action) => {
    try {
      await fetch('http://localhost:8000/api/approve', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          repo_name: repoUrl.split('/').pop(),
          action: action
        })
      });
      setApprovalBranch(null);
      setApprovalDiff(null);
    } catch (e) {
      console.error("Approval error", e);
    }
  };

  const renderDiff = (diffStr) => {
    if (!diffStr) return <div style={{ color: 'var(--text-secondary)' }}>No diff available.</div>;
    return diffStr.split('\n').map((line, i) => {
      let color = '#a9b1d6';
      let background = 'transparent';
      if (line.startsWith('+') && !line.startsWith('+++')) { color = '#9ece6a'; background = 'rgba(158, 206, 106, 0.1)'; }
      else if (line.startsWith('-') && !line.startsWith('---')) { color = '#f7768e'; background = 'rgba(247, 118, 142, 0.1)'; }
      else if (line.startsWith('@@')) color = '#7aa2f7';
      return (
        <div key={i} style={{ color, background, fontFamily: 'Fira Code, monospace', whiteSpace: 'pre-wrap', padding: '0 4px' }}>
          {line || ' '}
        </div>
      );
    });
  };

  const handleStartBenchmark = async () => {
    if (!apiKey || !githubToken || !benchmarkInput) {
      alert("Please fill in API Key, GitHub Token, and the Benchmark JSON.");
      return;
    }

    try {
      const targets = JSON.parse(benchmarkInput);
      if (!Array.isArray(targets)) throw new Error("Input must be a JSON array.");
      
      const res = await fetch('http://localhost:8000/api/benchmark', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          targets: targets,
          provider: provider,
          model: model,
          api_key: apiKey,
          github_token: githubToken
        })
      });
      if (res.ok) {
        alert("Benchmark batch queued successfully! Check the History tab for progress.");
        setActiveTab('history');
      } else {
        alert("Failed to start benchmark.");
      }
    } catch (e) {
      alert("Invalid JSON format or error: " + e.message);
    }
  };

  if (!authToken) {
    return (
      <div className="app-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div className="glass-panel" style={{ width: '400px', textAlign: 'center' }}>
          <Lock size={48} style={{ color: 'var(--accent-color)', marginBottom: '1rem' }} />
          <h2>Authentication Required</h2>
          <form onSubmit={handleLogin} style={{ marginTop: '2rem' }}>
            <div className="form-group">
              <label>Admin Password</label>
              <input 
                type="password" 
                value={passwordInput} 
                onChange={e => setPasswordInput(e.target.value)} 
                placeholder="Enter password..." 
              />
            </div>
            <button className="btn" type="submit" style={{ width: '100%', marginTop: '1rem' }}>Login</button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="app-container">
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Issue Hunter</h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
            Autonomous AI agent for fixing open-source bugs.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', background: 'var(--panel-bg)', padding: '0.5rem', borderRadius: '12px' }}>
          <button 
            className={`btn ${activeTab === 'hunt' ? 'active' : ''}`} 
            style={{ background: activeTab === 'hunt' ? 'var(--accent-color)' : 'transparent' }}
            onClick={() => setActiveTab('hunt')}
          >
            <Crosshair size={16} /> Hunt
          </button>
          <button 
            className={`btn ${activeTab === 'history' ? 'active' : ''}`} 
            style={{ background: activeTab === 'history' ? 'var(--accent-color)' : 'transparent' }}
            onClick={() => setActiveTab('history')}
          >
            <History size={16} /> History
          </button>
          <button 
            className={`btn ${activeTab === 'benchmark' ? 'active' : ''}`} 
            style={{ background: activeTab === 'benchmark' ? 'var(--accent-color)' : 'transparent' }}
            onClick={() => setActiveTab('benchmark')}
          >
            <List size={16} /> Benchmark
          </button>
          <button 
            className="btn" 
            style={{ background: 'var(--danger-color)' }}
            onClick={handleLogout}
          >
            Logout
          </button>
        </div>
      </header>

      {activeTab === 'hunt' ? (
        <>
          <div className="grid-2">
        {/* Configuration Panel */}
        <div className="glass-panel">
          <h2><Settings size={20} /> Configuration</h2>
          
          <div className="grid-2">
            <div className="form-group">
              <label>LLM Provider</label>
              <select value={provider} onChange={e => setProvider(e.target.value)}>
                <option value="gemini">Google Gemini</option>
                <option value="openai">OpenAI (Coming Soon)</option>
                <option value="anthropic">Anthropic (Coming Soon)</option>
              </select>
            </div>
            
            <div className="form-group">
              <label>Model</label>
              <input 
                type="text" 
                value={model} 
                onChange={e => setModel(e.target.value)}
                placeholder="e.g. gemini-3.5-pro"
              />
            </div>
          </div>

          <div className="form-group">
            <label><Key size={14} style={{display:'inline', marginRight:4}} /> API Key</label>
            <input 
              type="password" 
              value={apiKey} 
              onChange={e => setApiKey(e.target.value)}
              placeholder="Your LLM API Key"
            />
          </div>

          <div className="form-group">
            <label><GitBranch size={14} style={{display:'inline', marginRight:4}} /> GitHub Token</label>
            <input 
              type="password" 
              value={githubToken} 
              onChange={e => setGithubToken(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxx"
            />
          </div>
        </div>

        {/* Target Panel */}
        <div className="glass-panel">
          <h2><Crosshair size={20} /> Target Mission</h2>
          
          <div className="form-group">
            <label>Repository URL</label>
            <input 
              type="text" 
              value={repoUrl} 
              onChange={e => setRepoUrl(e.target.value)}
              placeholder="https://github.com/chalk/chalk"
            />
          </div>

          <div className="form-group">
            <label>Issue Numbers or Links</label>
            <input 
              type="text" 
              value={issueLinks} 
              onChange={e => setIssueLinks(e.target.value)}
              placeholder="669, 702 or https://github.com/chalk/chalk/issues/669"
            />
          </div>

          <button 
            className="btn" 
            onClick={handleStartHunt} 
            disabled={isRunning}
            style={{ marginTop: '1rem' }}
          >
            {isRunning ? (
              <>Hunting... <span className="terminal-dot dot-yellow"></span></>
            ) : (
              <><Play size={18} /> Start Hunt</>
            )}
          </button>
        </div>
      </div>

      {/* Live Terminal */}
      <div className="terminal-wrapper">
        <div className="terminal-header">
          <div className="terminal-dots">
            <div className="terminal-dot dot-red"></div>
            <div className="terminal-dot dot-yellow"></div>
            <div className="terminal-dot dot-green"></div>
          </div>
          <Terminal size={14} /> Agent Live Terminal
        </div>
        <div className="terminal-content">
          {logs.length === 0 ? (
            <div style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
              Waiting for mission control...
            </div>
          ) : (
            logs.map((log, i) => (
              <div 
                key={i} 
                className={`log-entry ${log.includes('ERROR') || log.includes('Failed') ? 'error' : log.includes('Successfully') || log.includes('Complete') ? 'success' : 'info'}`}
              >
                <span style={{opacity: 0.5}}>[{new Date().toLocaleTimeString()}]</span> {log}
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* Approval Dashboard */}
      {approvalBranch && (
        <div className="glass-panel" style={{ border: '1px solid var(--accent-glow)', boxShadow: '0 0 20px rgba(99,102,241,0.2)', marginTop: '2rem' }}>
          <h2><FileCheck size={20} /> Action Required: Approve PR Creation</h2>
          <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)' }}>
            The agent has finished implementing the fix on branch <strong style={{color: '#fff'}}>{approvalBranch}</strong> and is ready to open a Pull Request.
          </p>
          
          <div style={{
            background: '#1a1b26',
            borderRadius: '8px',
            padding: '1rem',
            maxHeight: '400px',
            overflowY: 'auto',
            marginBottom: '1rem',
            border: '1px solid var(--panel-border)'
          }}>
            {renderDiff(approvalDiff)}
          </div>

          <div style={{ display: 'flex', gap: '1rem' }}>
            <button className="btn" style={{ background: 'var(--success-color)' }} onClick={() => handleApprove('approve')}>
              Approve & Create PR
            </button>
            <button className="btn" style={{ background: 'var(--danger-color)' }} onClick={() => handleApprove('reject')}>
              Reject
            </button>
          </div>
        </div>
      )}
        </>
      ) : activeTab === 'benchmark' ? (
        <div className="grid-2">
          {/* Configuration Panel - Shared */}
          <div className="glass-panel">
            <h2><Settings size={20} /> Configuration</h2>
            
            <div className="grid-2">
              <div className="form-group">
                <label>LLM Provider</label>
                <select value={provider} onChange={e => setProvider(e.target.value)}>
                  <option value="gemini">Google Gemini</option>
                  <option value="openai">OpenAI (LiteLLM Proxy)</option>
                  <option value="anthropic">Anthropic (LiteLLM Proxy)</option>
                </select>
              </div>
              
              <div className="form-group">
                <label>Model</label>
                <input 
                  type="text" 
                  value={model} 
                  onChange={e => setModel(e.target.value)}
                  placeholder="e.g. gemini-3.5-pro"
                />
              </div>
            </div>

            <div className="form-group">
              <label><Key size={14} style={{display:'inline', marginRight:4}} /> API Key</label>
              <input 
                type="password" 
                value={apiKey} 
                onChange={e => setApiKey(e.target.value)}
                placeholder="Your LLM API Key"
              />
            </div>

            <div className="form-group">
              <label><GitBranch size={14} style={{display:'inline', marginRight:4}} /> GitHub Token</label>
              <input 
                type="password" 
                value={githubToken} 
                onChange={e => setGithubToken(e.target.value)}
                placeholder="ghp_xxxxxxxxxxxx"
              />
            </div>
          </div>

          {/* Benchmark Panel */}
          <div className="glass-panel">
            <h2><List size={20} /> Benchmark Suite</h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.875rem' }}>
              Provide a JSON array of repositories and issues to test against. The system will enqueue all of them as separate hunts.
            </p>
            
            <div className="form-group">
              <label>JSON Dataset</label>
              <textarea 
                value={benchmarkInput} 
                onChange={e => setBenchmarkInput(e.target.value)}
                style={{ height: '200px', fontFamily: 'Fira Code, monospace', padding: '1rem' }}
                placeholder='[{"repo_url": "...", "issues": [1, 2]}]'
              />
            </div>

            <button 
              className="btn" 
              onClick={handleStartBenchmark} 
              style={{ marginTop: '1rem' }}
            >
              <Play size={18} /> Queue Benchmark Batch
            </button>
          </div>
        </div>
      ) : (
        <div className="grid-2">
          {/* History Sidebar */}
          <div className="glass-panel" style={{ maxHeight: '80vh', overflowY: 'auto' }}>
            <h2><List size={20} /> Past Hunts</h2>
            {hunts.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)' }}>No hunts recorded yet.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {hunts.map(hunt => (
                  <div 
                    key={hunt.id} 
                    onClick={() => handleSelectHunt(hunt)}
                    style={{ 
                      padding: '1rem', 
                      background: selectedHunt?.id === hunt.id ? 'var(--accent-glow)' : 'rgba(0,0,0,0.2)', 
                      borderRadius: '8px', 
                      cursor: 'pointer',
                      border: `1px solid ${hunt.status === 'completed' ? 'var(--success-color)' : hunt.status === 'failed' ? 'var(--danger-color)' : 'var(--panel-border)'}`
                    }}
                  >
                    <div style={{ fontWeight: 'bold' }}>{hunt.repo_url.split('/').pop()}</div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Issues: {hunt.issues}</div>
                    <div style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}>{new Date(hunt.created_at).toLocaleString()}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* History Details */}
          <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
            <h2>Details</h2>
            {selectedHunt ? (
              <div style={{ flex: 1, overflowY: 'auto' }}>
                <h3>Report</h3>
                <pre style={{ 
                  background: 'rgba(0,0,0,0.3)', 
                  padding: '1rem', 
                  borderRadius: '8px', 
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap',
                  marginBottom: '1rem'
                }}>
                  {selectedHunt.report_md || 'No report generated.'}
                </pre>
                
                <h3>Logs</h3>
                <div style={{ 
                  background: 'var(--terminal-bg)', 
                  padding: '1rem', 
                  borderRadius: '8px', 
                  fontFamily: 'Fira Code, monospace',
                  fontSize: '0.875rem',
                  color: '#a9b1d6'
                }}>
                  {selectedHuntLogs.map((log, i) => (
                    <div key={i} className="log-entry">{log}</div>
                  ))}
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--text-secondary)' }}>Select a hunt to view details.</p>
            )}
          </div>
        </div>
      )}

    </div>
  );
}

export default App;
