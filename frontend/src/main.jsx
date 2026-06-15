import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_BASE = `http://${window.location.hostname}:8000`;

function formatSeconds(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60).toString().padStart(2, "0");
  const seconds = Math.floor(totalSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function App() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const overlayRef = useRef(null);
  const streamRef = useRef(null);
  const intervalRef = useRef(null);
  const audioRef = useRef(null);
  const closedSinceRef = useRef(null);
  const predictionInFlightRef = useRef(false);

  const [subject, setSubject] = useState("알고리즘");
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState("idle");
  const [prediction, setPrediction] = useState(null);
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");
  const [elapsed, setElapsed] = useState(0);

  const isStudying = Boolean(session?.is_active);

  useEffect(() => {
    return () => {
      stopCamera();
      clearInterval(intervalRef.current);
    };
  }, []);

  useEffect(() => {
    if (!isStudying) return;
    const timer = window.setInterval(() => {
      const started = new Date(session.started_at).getTime();
      setElapsed(Math.max(0, Math.floor((Date.now() - started) / 1000)));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [isStudying, session]);

  async function requestJson(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || "요청을 처리하지 못했습니다.");
    }
    return response.json();
  }

  async function startCamera() {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 960, height: 540, facingMode: "user" },
      audio: false,
    });
    streamRef.current = stream;
    videoRef.current.srcObject = stream;
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    clearOverlay();
  }

  async function startSession() {
    setError("");
    try {
      await requestJson("/users/default");
      const newSession = await requestJson("/study-sessions/start", {
        method: "POST",
        body: JSON.stringify({ user_id: 1, subject }),
      });
      setSession(newSession);
      setStatus("awake");
      setElapsed(0);
      setLogs([]);
      setStats(null);
      await startCamera();
      intervalRef.current = window.setInterval(() => captureAndPredict(newSession.id), 900);
    } catch (err) {
      setError(
        err.message === "No face detected"
          ? "얼굴이 화면 중앙에 보이도록 카메라 위치를 맞춰주세요."
          : err.message,
      );
    }
  }

  async function endSession() {
    if (!session) return;
    setError("");
    clearInterval(intervalRef.current);
    intervalRef.current = null;
    stopCamera();
    try {
      const ended = await requestJson(`/study-sessions/${session.id}/end`, { method: "POST" });
      setSession(ended);
      setStatus("idle");
      await refreshStats(ended.id);
    } catch (err) {
      setError(err.message);
    }
  }

  function captureFrame() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return null;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.72);
  }

  async function captureAndPredict(sessionId) {
    if (predictionInFlightRef.current) return;
    const imageBase64 = captureFrame();
    if (!imageBase64) return;
    predictionInFlightRef.current = true;
    try {
      const now = Date.now();
      const closedDuration = closedSinceRef.current ? now - closedSinceRef.current : 0;
      const result = await requestJson("/drowsiness/predict-frame", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          image_base64: imageBase64,
          eye_closed_duration_ms: Math.floor(closedDuration),
        }),
      });
      if (result.ear !== null && result.ear < 0.24) {
        closedSinceRef.current = closedSinceRef.current ?? now;
      } else {
        closedSinceRef.current = null;
      }
      drawOverlay(result);
      setPrediction(result);
      setStatus(result.is_drowsy ? "drowsy" : "awake");
      if (result.is_drowsy) playAlarm();
      await refreshLogs(sessionId);
      await refreshStats(sessionId);
    } catch (err) {
      clearOverlay();
      setError(
        err.message === "No face detected"
          ? "얼굴이 화면 중앙에 보이도록 카메라 위치를 맞춰주세요."
          : err.message,
      );
    } finally {
      predictionInFlightRef.current = false;
    }
  }

  function clearOverlay() {
    const overlay = overlayRef.current;
    if (!overlay) return;
    const context = overlay.getContext("2d");
    context.clearRect(0, 0, overlay.width, overlay.height);
  }

  function drawOverlay(result) {
    const video = videoRef.current;
    const overlay = overlayRef.current;
    if (!video || !overlay || video.videoWidth === 0 || video.videoHeight === 0) return;

    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
    const context = overlay.getContext("2d");
    context.clearRect(0, 0, overlay.width, overlay.height);

    const color = result.is_drowsy ? "#ff5a5a" : "#26d07c";
    context.lineWidth = 4;
    context.strokeStyle = color;
    context.fillStyle = color;
    context.font = "700 22px system-ui, sans-serif";

    if (result.face_box) {
      drawBox(context, result.face_box, result.is_drowsy ? "DROWSY" : "AWAKE");
    }

    context.lineWidth = 3;
    context.strokeStyle = "#ffd166";
    context.fillStyle = "#ffd166";
    for (const [index, box] of (result.eye_boxes || []).entries()) {
      drawBox(context, box, `EYE ${index + 1}`);
    }
  }

  function drawBox(context, box, label) {
    context.strokeRect(box.x, box.y, box.width, box.height);
    const labelWidth = context.measureText(label).width + 14;
    const labelY = Math.max(0, box.y - 28);
    context.fillRect(box.x, labelY, labelWidth, 28);
    context.fillStyle = "#101818";
    context.fillText(label, box.x + 7, labelY + 20);
    context.fillStyle = context.strokeStyle;
  }

  function playAlarm() {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const context = audioRef.current || new AudioContext();
    audioRef.current = context;
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.18, context.currentTime + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, context.currentTime + 0.5);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.55);
  }

  async function refreshLogs(sessionId) {
    const data = await requestJson(`/drowsiness/logs?session_id=${sessionId}`);
    setLogs(data.slice(0, 8));
  }

  async function refreshStats(sessionId) {
    const data = await requestJson(`/stats/session/${sessionId}`);
    setStats(data);
  }

  const statusText = {
    idle: "대기",
    awake: "정상",
    drowsy: "졸음",
  }[status];

  return (
    <main className="app">
      <section className="workspace">
        <div className="videoPanel">
          <div className={`statusRibbon ${status}`}>
            <span>{statusText}</span>
            <strong>{isStudying ? formatSeconds(elapsed) : "00:00"}</strong>
          </div>
          <video ref={videoRef} autoPlay playsInline muted />
          <canvas ref={overlayRef} className="overlayCanvas" />
          <canvas ref={canvasRef} hidden />
          {!isStudying && <div className="emptyCamera">Sleep Study Guard</div>}
        </div>

        <aside className="controlPanel">
          <div className="brandBlock">
            <p>졸음 감지 공부 세션</p>
            <h1>Sleep Study Guard</h1>
          </div>

          <label className="field">
            <span>과목</span>
            <input
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              disabled={isStudying}
              maxLength={120}
            />
          </label>

          <div className="actions">
            <button className="primary" onClick={startSession} disabled={isStudying || !subject.trim()}>
              시작
            </button>
            <button className="secondary" onClick={endSession} disabled={!isStudying}>
              종료
            </button>
          </div>

          {error && <p className="error">{error}</p>}

          <div className="metrics">
            <div>
              <span>졸음 횟수</span>
              <strong>{stats?.drowsy_count ?? 0}</strong>
            </div>
            <div>
              <span>감지 로그</span>
              <strong>{stats?.total_logs ?? 0}</strong>
            </div>
            <div>
              <span>졸음 비율</span>
              <strong>{Math.round((stats?.drowsy_ratio ?? 0) * 100)}%</strong>
            </div>
          </div>

          <div className="prediction">
            <span>EAR</span>
            <strong>{prediction?.ear?.toFixed(3) ?? "-"}</strong>
            <span>감김 시간</span>
            <strong>{prediction ? `${prediction.eye_closed_duration_ms}ms` : "-"}</strong>
            <span>예측 확률</span>
            <strong>{prediction ? `${Math.round(prediction.probability * 100)}%` : "-"}</strong>
          </div>
        </aside>
      </section>

      <section className="logBand">
        <h2>최근 감지 기록</h2>
        <div className="logList">
          {logs.length === 0 && <p className="emptyLog">아직 기록이 없습니다.</p>}
          {logs.map((log) => (
            <article key={log.id} className={log.is_drowsy ? "logItem danger" : "logItem"}>
              <strong>{log.is_drowsy ? "졸음" : "정상"}</strong>
              <span>{new Date(log.detected_at).toLocaleTimeString()}</span>
              <span>{Math.round(log.probability * 100)}%</span>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
