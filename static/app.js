(() => {
  "use strict";

  // ---------- elements ----------
  const $ = (sel) => document.querySelector(sel);
  const els = {
    lang: $("#lang"), langNative: $("#langNative"), langName: $("#langName"),
    status: $("#status"), transcript: $("#transcript"), empty: $("#empty"),
    mic: $("#mic"), handsfree: $("#handsfree"), clear: $("#clear"),
    textForm: $("#textForm"), textInput: $("#textInput"), wave: $("#wave"),
    modes: document.querySelectorAll('input[name="mode"]'),
  };

  // ---------- tuning ----------
  const VAD = {
    start: 0.04,        // voice level that counts as speech
    silenceMs: 900,     // pause that ends an utterance (hands-free)
    minSpeechMs: 350,   // shorter than this is a cough, not speech
    onsetMs: 150,       // speech must last this long to count
    idleResetMs: 12000, // restart an empty recording so it never grows
    bargeFactor: 2.5,   // be pickier while the AI is talking (speaker echo)
  };

  const STATUS = {
    offline: "Reconnecting…",
    idle: "Tap the microphone and start talking.",
    listening: "Listening. Tap again when you are done.",
    listeningHandsFree: "Listening. Just talk, I'll wait for you to finish.",
    thinking: "Thinking…",
    speaking: "Speaking. Talk or tap the microphone to cut in.",
  };

  // ---------- state ----------
  let ws = null;
  let state = "offline";
  let languages = [];
  let stream = null, audioCtx = null, analyser = null, levelBuf = null;
  let recorder = null, recording = false, recStart = 0;
  let heardSpeech = false, voiceSince = 0, speechStart = 0, lastVoice = 0;
  let handsFree = false;
  const player = new Audio();
  let playQueue = [], playing = false, serverDone = true, pendingSentence = null, currentAi = null;
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---------- small helpers ----------
  const save = (k, v) => { try { localStorage.setItem(k, v); } catch (_) { /* private mode */ } };
  const load = (k) => { try { return localStorage.getItem(k); } catch (_) { return null; } };
  const currentMode = () => [...els.modes].find((m) => m.checked).value;

  function setState(next) {
    state = next;
    document.body.dataset.state = next;
    els.status.textContent = next === "listening" && handsFree ? STATUS.listeningHandsFree : STATUS[next];
    els.mic.setAttribute("aria-label", next === "listening" ? "Stop and send" : "Start talking");
  }

  function addLine(kind, text) {
    els.empty.hidden = true;
    const p = document.createElement("p");
    p.className = `line ${kind}`;
    p.dir = "auto";
    p.textContent = text;
    els.transcript.appendChild(p);
    els.transcript.scrollTop = els.transcript.scrollHeight;
    return p;
  }

  function appendAi(text) {
    if (!currentAi) currentAi = addLine("ai", "");
    currentAi.textContent += (currentAi.textContent ? " " : "") + text;
    els.transcript.scrollTop = els.transcript.scrollHeight;
  }

  // ---------- websocket ----------
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.binaryType = "arraybuffer";
    ws.onopen = () => { sendConfig(); setState(recording ? "listening" : "idle"); };
    ws.onclose = () => { stopPlayback(); setState("offline"); setTimeout(connect, 1500); };
    ws.onmessage = onMessage;
  }

  const send = (obj) => ws && ws.readyState === WebSocket.OPEN && ws.send(JSON.stringify(obj));
  const sendConfig = () => send({ type: "config", language: els.lang.value, mode: currentMode() });

  function onMessage(ev) {
    if (typeof ev.data !== "string") {            // binary frame: audio of the pending sentence
      if (!pendingSentence) return;
      const url = URL.createObjectURL(new Blob([ev.data], { type: "audio/mpeg" }));
      enqueue({ text: pendingSentence, url });
      pendingSentence = null;
      return;
    }
    const msg = JSON.parse(ev.data);
    switch (msg.type) {
      case "thinking":
        serverDone = false; currentAi = null;
        if (!playing) setState("thinking");
        break;
      case "transcript": addLine("you", msg.text); break;
      case "sentence":
        if (msg.audio) pendingSentence = msg.text;
        else enqueue({ text: msg.text, url: null });
        break;
      case "done": serverDone = true; maybeFinish(); break;
      case "error": addLine("note", msg.message); serverDone = true; maybeFinish(); break;
    }
  }

  // ---------- playback ----------
  function enqueue(item) {
    playQueue.push(item);
    if (!playing) playNext();
  }

  function playNext() {
    const item = playQueue.shift();
    if (!item) { playing = false; maybeFinish(); return; }
    playing = true;
    setState("speaking");
    appendAi(item.text);
    if (!item.url) { playNext(); return; }                    // text-only fallback
    const next = () => { URL.revokeObjectURL(item.url); playNext(); };
    player.onended = next;
    player.onerror = next;
    player.src = item.url;
    player.play().catch(next);
  }

  function maybeFinish() {
    if (playing || playQueue.length || !serverDone) return;
    setState(recording ? "listening" : "idle");
  }

  function stopPlayback() {
    player.onended = player.onerror = null;
    player.pause();
    playQueue.forEach((i) => i.url && URL.revokeObjectURL(i.url));
    playQueue = []; playing = false; pendingSentence = null; currentAi = null;
  }

  function interrupt() {
    stopPlayback();
    serverDone = true;
    send({ type: "interrupt" });
  }

  // ---------- microphone ----------
  async function ensureMic() {
    if (stream) return true;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
    } catch (err) {
      addLine("note", "The microphone is blocked. Allow access in your browser and try again.");
      return false;
    }
    audioCtx = new AudioContext();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 1024;
    levelBuf = new Uint8Array(analyser.fftSize);
    audioCtx.createMediaStreamSource(stream).connect(analyser);
    return true;
  }

  function startRecording() {
    if (recording || !stream) return;
    const mime = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"]
      .find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m));
    const parts = [];
    recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
    recorder._parts = parts;
    recorder.ondataavailable = (e) => e.data.size && parts.push(e.data);
    recorder.start();
    recording = true; heardSpeech = false; voiceSince = 0;
    recStart = lastVoice = performance.now();
  }

  function stopRecording(sendIt) {
    if (!recording) return;
    recording = false;
    const r = recorder;
    r.onstop = () => {
      if (!sendIt || !r._parts.length) return;
      const blob = new Blob(r._parts, { type: r.mimeType });
      if (blob.size < 1500) return;
      stopPlayback();                       // the server cancels the old reply on new audio
      serverDone = false;
      setState("thinking");
      blob.arrayBuffer().then((buf) => ws && ws.readyState === WebSocket.OPEN && ws.send(buf));
    };
    r.stop();
  }

  async function onMicClick() {
    if (state === "offline") return;
    if (handsFree) { els.handsfree.checked = false; setHandsFree(false); return; }
    if (recording) { stopRecording(true); return; }
    if (!(await ensureMic())) return;
    if (playing || !serverDone) interrupt();
    startRecording();
    setState("listening");
  }

  async function setHandsFree(on) {
    handsFree = on;
    if (on) {
      if (!(await ensureMic())) { els.handsfree.checked = false; handsFree = false; return; }
      startRecording();
      setState(playing ? "speaking" : "listening");
    } else {
      stopRecording(false);
      if (state === "listening") setState("idle");
    }
  }

  // ---------- level meter, waveform and hands-free voice detection ----------
  const ctx2d = els.wave.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const colors = {};

  function sizeCanvas() {
    els.wave.width = els.wave.clientWidth * dpr;
    els.wave.height = els.wave.clientHeight * dpr;
    const css = getComputedStyle(document.documentElement);
    for (const k of ["--accent", "--warm", "--rule", "--ink"]) colors[k] = css.getPropertyValue(k).trim();
  }

  function readLevel() {
    if (!analyser) return 0;
    analyser.getByteTimeDomainData(levelBuf);
    let sum = 0;
    for (const v of levelBuf) { const x = (v - 128) / 128; sum += x * x; }
    return Math.sqrt(sum / levelBuf.length);
  }

  function drawWave(now) {
    const w = els.wave.width, h = els.wave.height, mid = h / 2;
    ctx2d.clearRect(0, 0, w, h);
    ctx2d.lineWidth = 2 * dpr;
    ctx2d.lineJoin = "round";
    ctx2d.beginPath();
    const listening = recording && analyser;
    const speaking = state === "speaking" && !reduceMotion;
    ctx2d.strokeStyle = speaking ? colors["--warm"] : listening ? colors["--accent"] : colors["--rule"];
    for (let x = 0; x <= w; x += 3 * dpr) {
      let y = mid;
      if (listening) {
        y = mid + ((levelBuf[Math.floor((x / w) * (levelBuf.length - 1))] - 128) / 128) * h * 0.9;
      } else if (speaking) {
        y = mid + Math.sin(x * 0.012 / dpr + now * 0.005) * h * 0.22 * (0.65 + 0.35 * Math.sin(now * 0.002));
      }
      x === 0 ? ctx2d.moveTo(x, y) : ctx2d.lineTo(x, y);
    }
    ctx2d.stroke();
  }

  function detectVoice(now, level) {
    const gate = playing ? VAD.start * VAD.bargeFactor : VAD.start;
    if (level > gate) {
      if (!voiceSince) voiceSince = now;
      lastVoice = now;
      if (!heardSpeech && now - voiceSince > VAD.onsetMs) {
        heardSpeech = true; speechStart = voiceSince;
        if (playing) interrupt();                                   // barge-in
      }
    } else if (!heardSpeech) {
      voiceSince = 0;
    }

    if (heardSpeech && now - lastVoice > VAD.silenceMs) {
      const long = lastVoice - speechStart >= VAD.minSpeechMs;
      stopRecording(long);
      startRecording();                                             // ready for the next sentence
    } else if (!heardSpeech && now - recStart > VAD.idleResetMs) {
      stopRecording(false);
      startRecording();
    }
  }

  function tick(now) {
    const level = readLevel();
    if (handsFree && recording) detectVoice(now, level);
    drawWave(now);
    requestAnimationFrame(tick);
  }

  // ---------- language + UI wiring ----------
  function applyLanguageLabel() {
    const lang = languages.find((l) => l.code === els.lang.value);
    if (!lang) return;
    els.langNative.textContent = lang.native;
    els.langNative.dir = lang.rtl ? "rtl" : "ltr";
    els.langName.textContent = `${lang.name}, tap to change`;
    document.documentElement.lang = lang.code;
  }

  async function loadLanguages() {
    const data = await (await fetch("/api/languages")).json();
    languages = data.languages;
    for (const l of languages) {
      const opt = document.createElement("option");
      opt.value = l.code;
      opt.textContent = `${l.native} (${l.name})`;
      els.lang.appendChild(opt);
    }
    const saved = load("lang");
    els.lang.value = languages.some((l) => l.code === saved) ? saved : data.default;
    const savedMode = load("mode");
    els.modes.forEach((m) => { m.checked = m.value === (savedMode || "chat"); });
    applyLanguageLabel();
  }

  els.lang.addEventListener("change", () => {
    save("lang", els.lang.value);
    applyLanguageLabel();
    sendConfig();
  });
  els.modes.forEach((m) => m.addEventListener("change", () => { save("mode", currentMode()); sendConfig(); }));
  els.handsfree.addEventListener("change", () => setHandsFree(els.handsfree.checked));
  els.mic.addEventListener("click", onMicClick);

  els.clear.addEventListener("click", () => {
    interrupt();
    send({ type: "reset" });
    els.transcript.querySelectorAll(".line").forEach((n) => n.remove());
    els.empty.hidden = false;
  });

  els.textForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = els.textInput.value.trim();
    if (!text || state === "offline") return;
    els.textInput.value = "";
    stopPlayback();
    serverDone = false;
    send({ type: "text", text });
  });

  window.addEventListener("resize", sizeCanvas);

  // ---------- start ----------
  sizeCanvas();
  setState("offline");
  loadLanguages().then(connect);
  requestAnimationFrame(tick);
})();
