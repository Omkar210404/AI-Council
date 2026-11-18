import React, { useState, useEffect, useRef } from "react";
import {
  ShieldAlert,
  Users,
  Compass,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  History,
  Send,
  RotateCcw,
  Sparkles,
  Info,
  ChevronRight,
  HelpCircle,
  TrendingUp,
  Sliders,
  Scale
} from "lucide-react";

export default function App() {
  const [question, setQuestion] = useState("");
  const [agents, setAgents] = useState([]);
  const [selectedAgentIds, setSelectedAgentIds] = useState(["optimist", "pessimist", "realist"]);
  const [providers, setProviders] = useState([]);
  
  // Model settings
  const [agentProvider, setAgentProvider] = useState("gemini");
  const [agentModel, setAgentModel] = useState("gemini-1.5-flash");
  const [judgeProvider, setJudgeProvider] = useState("gemini");
  const [judgeModel, setJudgeModel] = useState("gemini-1.5-pro");

  // State during execution
  const [isRunning, setIsRunning] = useState(false);
  const [neutralQuestion, setNeutralQuestion] = useState("");
  const [liveAgentResults, setLiveAgentResults] = useState({});
  const [judgeVerdict, setJudgeVerdict] = useState(null);
  const [judgeStatus, setJudgeStatus] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  // History & consistency modal
  const [history, setHistory] = useState([]);
  const [showConsistencyModal, setShowConsistencyModal] = useState(false);
  const [consistencyTopic, setConsistencyTopic] = useState("quit my job to start an AI consulting agency");
  const [consistencyResult, setConsistencyResult] = useState(null);
  const [consistencyLoading, setConsistencyLoading] = useState(false);

  const abortControllerRef = useRef(null);

  // Load initial data
  useEffect(() => {
    fetchAgents();
    fetchProviders();
    fetchHistory();
  }, []);

  const fetchAgents = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/agents");
      if (res.ok) {
        const data = await res.json();
        setAgents(data);
      }
    } catch (err) {
      console.warn("Failed to load agents", err);
    }
  };

  const fetchProviders = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/providers");
      if (res.ok) {
        const data = await res.json();
        setProviders(data);
        // Default to first configured provider if Gemini not configured
        const geminiProv = data.find(p => p.id === "gemini");
        if (!geminiProv || !geminiProv.configured) {
          const firstConfigured = data.find(p => p.configured) || data[0];
          if (firstConfigured) {
            setAgentProvider(firstConfigured.id);
            setAgentModel(firstConfigured.default_model);
            setJudgeProvider(firstConfigured.id);
            setJudgeModel(firstConfigured.judge_model);
          }
        }
      }
    } catch (err) {
      console.warn("Failed to load providers", err);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch("http://localhost:8000/api/sessions");
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (err) {
      console.warn("Failed to load history", err);
    }
  };

  const toggleAgent = (id) => {
    if (selectedAgentIds.includes(id)) {
      if (selectedAgentIds.length <= 2) {
        alert("Council requires at least 2 agents.");
        return;
      }
      setSelectedAgentIds(selectedAgentIds.filter(x => x !== id));
    } else {
      if (selectedAgentIds.length >= 5) {
        alert("Maximum 5 agents can be selected.");
        return;
      }
      setSelectedAgentIds([...selectedAgentIds, id]);
    }
  };

  const startDeliberation = async () => {
    if (!question.trim()) return;
    setIsRunning(true);
    setNeutralQuestion("");
    setLiveAgentResults({});
    setJudgeVerdict(null);
    setJudgeStatus("");
    setErrorMessage("");

    try {
      const response = await fetch("http://localhost:8000/api/evaluate/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          agent_ids: selectedAgentIds,
          agent_provider: agentProvider,
          agent_model: agentModel,
          judge_provider: judgeProvider,
          judge_model: judgeModel
        })
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || "Evaluation request failed");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop(); // keep last incomplete chunk

        for (const line of lines) {
          if (!line.trim()) continue;
          const eventMatch = line.match(/^event:\s*(.+)$/m);
          const dataMatch = line.match(/^data:\s*(.+)$/m);

          if (eventMatch && dataMatch) {
            const eventType = eventMatch[1].trim();
            const payload = JSON.parse(dataMatch[1].trim());

            if (eventType === "neutralised") {
              setNeutralQuestion(payload.neutral_question);
            } else if (eventType === "agent_result") {
              setLiveAgentResults(prev => ({
                ...prev,
                [payload.agent_id]: payload
              }));
            } else if (eventType === "judge_start") {
              setJudgeStatus(payload.message);
            } else if (eventType === "judge_verdict") {
              setJudgeVerdict(payload);
              setJudgeStatus("");
            } else if (eventType === "error") {
              setErrorMessage(payload.error);
            } else if (eventType === "done") {
              fetchHistory();
            }
          }
        }
      }
    } catch (err) {
      setErrorMessage(err.message);
    } finally {
      setIsRunning(false);
    }
  };

  const loadPastSession = async (sessionId) => {
    try {
      const res = await fetch(`http://localhost:8000/api/sessions/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setQuestion(data.original_question);
        setNeutralQuestion(data.neutral_question);
        setSelectedAgentIds(data.selected_agent_ids || []);
        setLiveAgentResults(data.agent_outputs || {});
        setJudgeVerdict(data.verdict || null);
        setErrorMessage("");
      }
    } catch (err) {
      alert("Could not load session details");
    }
  };

  const runConsistencyCheck = async () => {
    if (!consistencyTopic.trim()) return;
    setConsistencyLoading(true);
    setConsistencyResult(null);
    try {
      const res = await fetch(`http://localhost:8000/api/consistency-test?topic=${encodeURIComponent(consistencyTopic)}&provider=${agentProvider}`, {
        method: "POST"
      });
      if (res.ok) {
        const data = await res.json();
        setConsistencyResult(data);
      } else {
        alert("Failed to run consistency check");
      }
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      setConsistencyLoading(false);
    }
  };

  const getStanceClass = (stance) => {
    if (stance === "for") return "for";
    if (stance === "against") return "against";
    return "mixed";
  };

  return (
    <div className="app-container">
      {/* Sidebar: Past Decisions */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-title">
            <Scale size={20} color="#8b5cf6" />
            <span>Council Decisions</span>
          </div>
          <button
            className="new-btn"
            onClick={() => {
              setQuestion("");
              setNeutralQuestion("");
              setLiveAgentResults({});
              setJudgeVerdict(null);
              setErrorMessage("");
            }}
          >
            + New
          </button>
        </div>

        <div className="sidebar-list">
          {history.length === 0 ? (
            <div style={{ padding: "20px", color: "var(--text-subtle)", textAlign: "center", fontSize: "0.85rem" }}>
              No past sessions recorded yet.
            </div>
          ) : (
            history.map((item) => (
              <div
                key={item.id}
                className="history-item"
                onClick={() => loadPastSession(item.id)}
              >
                <div className="history-q">{item.original_question}</div>
                <div className="history-meta">
                  <span>{new Date(item.created_at).toLocaleDateString()}</span>
                  {item.verdict && (
                    <span style={{
                      fontWeight: 700,
                      color: item.verdict.verdict === "Recommended" ? "var(--for-green)" :
                             item.verdict.verdict === "Not recommended" ? "var(--against-red)" : "var(--mixed-amber)"
                    }}>
                      {item.verdict.verdict} ({item.verdict.score})
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Main Viewport */}
      <main className="main-viewport">
        {/* Top Navbar */}
        <header className="top-bar">
          <div className="top-left">
            <span className="logo-badge">COUNCIL</span>
            <span className="tagline">Anti-Sycophancy Multi-Agent Decision Engine</span>
          </div>

          <div className="top-actions">
            <button
              className="btn-secondary"
              onClick={() => setShowConsistencyModal(true)}
              title="Test system resistance against leading questions"
            >
              <ShieldAlert size={16} color="#38bdf8" />
              <span>Anti-Sycophancy Test</span>
            </button>
          </div>
        </header>

        <div className="content-body">
          {/* Main Question & Configuration */}
          <section className="prompt-card">
            <textarea
              className="input-box"
              placeholder="e.g. Is it a good idea to quit my stable corporate job and build an AI startup? Or should I invest in real estate?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={isRunning}
            />

            <div className="controls-row">
              {/* Agent Picker */}
              <div className="agent-picker-group">
                <span className="picker-label">Council Members ({selectedAgentIds.length}/5)</span>
                <div className="agent-chips">
                  {agents.map((ag) => {
                    const isSelected = selectedAgentIds.includes(ag.id);
                    return (
                      <div
                        key={ag.id}
                        className={`chip ${isSelected ? "selected" : ""}`}
                        onClick={() => !isRunning && toggleAgent(ag.id)}
                      >
                        {ag.name}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Model Pickers */}
              <div className="model-pickers">
                <div className="select-wrapper">
                  <span className="picker-label">Agents Model</span>
                  <select
                    value={agentProvider}
                    onChange={(e) => {
                      const prov = providers.find(p => p.id === e.target.value);
                      setAgentProvider(e.target.value);
                      if (prov) setAgentModel(prov.default_model);
                    }}
                    disabled={isRunning}
                  >
                    {providers.map(p => (
                      <option key={p.id} value={p.id}>
                        {p.name} {!p.configured ? "(Not Configured)" : ""}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="select-wrapper">
                  <span className="picker-label">Judge Model</span>
                  <select
                    value={judgeProvider}
                    onChange={(e) => {
                      const prov = providers.find(p => p.id === e.target.value);
                      setJudgeProvider(e.target.value);
                      if (prov) setJudgeModel(prov.judge_model);
                    }}
                    disabled={isRunning}
                  >
                    {providers.map(p => (
                      <option key={p.id} value={p.id}>
                        {p.name} (Judge)
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  className="btn-convene"
                  onClick={startDeliberation}
                  disabled={isRunning || !question.trim()}
                >
                  {isRunning ? <div className="spinner" /> : <Send size={16} />}
                  <span>{isRunning ? "Deliberating..." : "Convene Council"}</span>
                </button>
              </div>
            </div>
          </section>

          {/* Error Message */}
          {errorMessage && (
            <div style={{ background: "rgba(239, 68, 68, 0.15)", border: "1px solid #ef4444", borderRadius: "8px", padding: "14px", color: "#fca5a5", fontSize: "0.9rem" }}>
              <strong>Execution Error:</strong> {errorMessage}
            </div>
          )}

          {/* Step 1: Neutralised Question Display */}
          {neutralQuestion && (
            <div className="neutral-banner">
              <div className="neutral-title">
                <Sparkles size={14} />
                <span>Neutralised Formulation (Stripped of leading bias)</span>
              </div>
              <div className="neutral-text">"{neutralQuestion}"</div>
            </div>
          )}

          {/* Step 2: Live Agent Cards Grid */}
          {(isRunning || Object.keys(liveAgentResults).length > 0) && (
            <div className="agents-grid">
              {selectedAgentIds.map((agId) => {
                const agentMeta = agents.find(a => a.id === agId) || { name: agId, role: "Agent" };
                const res = liveAgentResults[agId];

                if (!res) {
                  return (
                    <div key={agId} className="loading-card">
                      <div className="spinner" />
                      <span>{agentMeta.name} is deliberating...</span>
                    </div>
                  );
                }

                if (res.error) {
                  return (
                    <div key={agId} className="agent-card" style={{ borderTop: "3px solid #ef4444" }}>
                      <div className="agent-header">
                        <div className="agent-name-role">
                          <span className="agent-name">{agentMeta.name}</span>
                          <span className="agent-role">Failed to respond</span>
                        </div>
                        <span className="stance-badge against">Failed</span>
                      </div>
                      <div style={{ color: "#fca5a5", fontSize: "0.85rem" }}>{res.error}</div>
                    </div>
                  );
                }

                const stanceClass = getStanceClass(res.stance);
                return (
                  <div key={agId} className={`agent-card ${stanceClass}`}>
                    <div className="agent-header">
                      <div className="agent-name-role">
                        <span className="agent-name">{res.agent_name}</span>
                        <span className="agent-role">{agentMeta.description || agentMeta.role}</span>
                      </div>
                      <span className={`stance-badge ${stanceClass}`}>
                        {res.stance}
                      </span>
                    </div>

                    {/* Confidence Meter */}
                    <div className="confidence-bar-container">
                      <span className="conf-label">Confidence:</span>
                      <div className="conf-track">
                        <div
                          className="conf-fill"
                          style={{
                            width: `${(res.confidence / 10) * 100}%`,
                            background: stanceClass === "for" ? "var(--for-green)" :
                                        stanceClass === "against" ? "var(--against-red)" : "var(--mixed-amber)"
                          }}
                        />
                      </div>
                      <span className="conf-val">{res.confidence}/10</span>
                    </div>

                    {/* Key points */}
                    <ul className="agent-points-list">
                      {res.key_points && res.key_points.map((pt, idx) => (
                        <li key={idx} className="agent-point-item">
                          <span className="point-bullet">•</span>
                          <span>{pt}</span>
                        </li>
                      ))}
                    </ul>

                    {/* Projection / Best-Worst case */}
                    {res.best_or_worst_case && (
                      <div className="agent-meta-box">
                        <strong>Projected Outcome:</strong>
                        <span>{res.best_or_worst_case}</span>
                      </div>
                    )}

                    {/* Missing info & Assumptions */}
                    {res.missing_information && res.missing_information.length > 0 && (
                      <div className="agent-meta-box" style={{ opacity: 0.85 }}>
                        <strong>Missing Information Identified:</strong>
                        <span>{res.missing_information.join("; ")}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Judge Status Tracker */}
          {judgeStatus && !judgeVerdict && (
            <div className="loading-card" style={{ borderStyle: "solid", borderColor: "var(--judge-purple-border)" }}>
              <div className="spinner" style={{ borderTopColor: "#a855f7" }} />
              <span style={{ color: "#c4b5fd", fontWeight: 600 }}>{judgeStatus}</span>
            </div>
          )}

          {/* Step 3: Judge Verdict Panel */}
          {judgeVerdict && (
            <section className="judge-panel">
              <div className="judge-top">
                <div className="judge-badge-area">
                  <div className={`verdict-tag ${judgeVerdict.verdict.toLowerCase().replace(" ", "-")}`}>
                    {judgeVerdict.verdict}
                  </div>
                  <div className="judge-score-badge">
                    <span className="score-number">{judgeVerdict.score}</span>
                    <span className="score-max">/100 viability</span>
                  </div>
                </div>

                <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                  <span style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
                    Judge Confidence: <strong style={{ color: "white" }}>{judgeVerdict.confidence}/10</strong>
                  </span>
                </div>
              </div>

              {/* Readable Synthesis */}
              <div className="judge-summary">
                {judgeVerdict.summary}
              </div>

              {/* Influential Agent Citation */}
              {judgeVerdict.influential_agent && (
                <div className="influential-banner">
                  ⚖️ <strong>Decisive Factor:</strong> Influenced primarily by {judgeVerdict.influential_agent}
                </div>
              )}

              {/* 2-column Analysis */}
              <div className="judge-grid-2col">
                {/* Agreements & Disagreements */}
                <div className="judge-section-card">
                  <div className="judge-section-title">
                    <CheckCircle2 size={16} color="#10b981" />
                    <span>Points of Agreement</span>
                  </div>
                  {judgeVerdict.agreements && judgeVerdict.agreements.length > 0 ? (
                    <ul className="verdict-list">
                      {judgeVerdict.agreements.map((item, idx) => (
                        <li key={idx}>
                          <strong>{item.topic}</strong>{" "}
                          <span style={{ color: "var(--text-subtle)", fontSize: "0.78rem" }}>
                            ({item.agents_involved.join(", ")})
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div style={{ fontSize: "0.85rem", color: "var(--text-subtle)" }}>No explicit consensus points.</div>
                  )}

                  <div className="judge-section-title" style={{ marginTop: "10px" }}>
                    <AlertTriangle size={16} color="#f59e0b" />
                    <span>Disagreements & Stronger Side</span>
                  </div>
                  {judgeVerdict.disagreements && judgeVerdict.disagreements.length > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                      {judgeVerdict.disagreements.map((d, idx) => (
                        <div key={idx} style={{ background: "rgba(255,255,255,0.03)", padding: "10px", borderRadius: "6px" }}>
                          <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#f8fafc", marginBottom: "4px" }}>
                            {d.topic}
                          </div>
                          <div style={{ fontSize: "0.8rem", color: "#94a3b8", marginBottom: "4px" }}>
                            • <em>Side A:</em> {d.side_a}<br/>
                            • <em>Side B:</em> {d.side_b}
                          </div>
                          <div style={{ fontSize: "0.8rem", color: "#67e8f9" }}>
                            <strong>Stronger:</strong> {d.stronger_side} — {d.reasoning}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: "0.85rem", color: "var(--text-subtle)" }}>Agents maintained parallel stances without direct clashes.</div>
                  )}
                </div>

                {/* Conditions to change & Things to find out */}
                <div className="judge-section-card">
                  <div className="judge-section-title">
                    <RotateCcw size={16} color="#38bdf8" />
                    <span>What Would Change This Verdict?</span>
                  </div>
                  <ul className="verdict-list">
                    {judgeVerdict.conditions_to_change_verdict && judgeVerdict.conditions_to_change_verdict.map((cond, idx) => (
                      <li key={idx}>{cond}</li>
                    ))}
                  </ul>

                  <div className="judge-section-title" style={{ marginTop: "12px" }}>
                    <HelpCircle size={16} color="#a78bfa" />
                    <span>2-3 Things to Find Out Before Deciding</span>
                  </div>
                  <ul className="verdict-list">
                    {judgeVerdict.things_to_find_out && judgeVerdict.things_to_find_out.map((item, idx) => (
                      <li key={idx}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </section>
          )}
        </div>
      </main>

      {/* Consistency Test Modal */}
      {showConsistencyModal && (
        <div className="modal-overlay" onClick={() => setShowConsistencyModal(false)}>
          <div className="modal-window" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <ShieldAlert size={20} color="#38bdf8" />
                <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Anti-Sycophancy Consistency Check</h3>
              </div>
              <button
                style={{ background: "none", border: "none", color: "#94a3b8", fontSize: "1.2rem", cursor: "pointer" }}
                onClick={() => setShowConsistencyModal(false)}
              >
                ✕
              </button>
            </div>

            <p style={{ fontSize: "0.88rem", color: "var(--text-muted)", lineHeight: 1.5 }}>
              Tests whether Council's neutraliser prevents phrasing bias. We evaluate the proposition phrased positively (<em>"Is X a good idea?"</em>), negatively (<em>"Is X a bad idea?"</em>), and neutrally (<em>"Should I do X?"</em>).
            </p>

            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <label style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 600 }}>Proposal to test:</label>
              <input
                type="text"
                value={consistencyTopic}
                onChange={(e) => setConsistencyTopic(e.target.value)}
                style={{
                  background: "#090c13",
                  border: "1px solid var(--border)",
                  borderRadius: "6px",
                  padding: "8px 12px",
                  color: "white"
                }}
              />
            </div>

            <button
              className="btn-convene"
              style={{ justifyContent: "center" }}
              onClick={runConsistencyCheck}
              disabled={consistencyLoading || !consistencyTopic.trim()}
            >
              {consistencyLoading ? <div className="spinner" /> : <ShieldAlert size={16} />}
              <span>{consistencyLoading ? "Running Triangulation..." : "Run Consistency Triangulation"}</span>
            </button>

            {consistencyResult && (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginTop: "10px" }}>
                <div style={{
                  padding: "12px",
                  borderRadius: "8px",
                  background: consistencyResult.is_swayed_by_wording ? "rgba(239, 68, 68, 0.15)" : "rgba(16, 185, 129, 0.15)",
                  border: `1px solid ${consistencyResult.is_swayed_by_wording ? "#ef4444" : "#10b981"}`,
                  color: consistencyResult.is_swayed_by_wording ? "#fca5a5" : "#6ee7b7",
                  fontSize: "0.9rem",
                  fontWeight: 600
                }}>
                  {consistencyResult.verdict_assessment}
                  <div style={{ fontSize: "0.8rem", fontWeight: 400, marginTop: "4px" }}>
                    Score Divergence: {consistencyResult.score_divergence} points | Verdicts Consistent: {consistencyResult.verdict_consistent ? "Yes" : "No"}
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {consistencyResult.runs.map((r, i) => (
                    <div key={i} style={{ background: "rgba(0,0,0,0.3)", padding: "10px", borderRadius: "6px", fontSize: "0.85rem" }}>
                      <div style={{ color: "#93c5fd", fontWeight: 600 }}>{r.phrasing_type}: "{r.raw_question}"</div>
                      <div style={{ color: "#94a3b8", fontSize: "0.8rem" }}>Neutralised: "{r.neutral_question}"</div>
                      <div style={{ marginTop: "4px", fontWeight: 700, color: "white" }}>
                        Verdict: {r.verdict} (Score: {r.score}/100, Confidence: {r.confidence}/10)
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
