(() => {
  const cv = document.getElementById('crowd');
  const ctx = cv.getContext('2d');
  const W = 1000, H = 560, TAU = Math.PI * 2;
  const FONT = '"Secular One", Rubik, Arial, sans-serif';
  const MAX = 400;

  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = a => a[Math.floor(Math.random() * a.length)];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  /* ---------- canvas sizing ---------- */
  let K = 1;
  function resize() {
    const r = cv.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.max(1, Math.round(r.width * dpr));
    cv.height = Math.max(1, Math.round(r.height * dpr));
    K = cv.width / W;
  }
  new ResizeObserver(resize).observe(cv);
  resize();

  /* ---------- content ---------- */
  const SIGNS = [
    'דמוקרטיה!', 'לא נוותר', 'ביחד\nננצח', 'הפרדת\nרשויות', 'שוויון\nלכולם',
    'עם חזק\nדמוקרטיה חזקה', 'אני פה בשביל\nהילדים', 'אמא שלי\nגם פה', 'הבאתי\nכיסא מתקפל',
    'קפה בתרמוס\nודמוקרטיה', 'כל שבוע\nעד שננצח',
  ];
  const CHANTS = ['דֶּ-מוֹ-קְרַטְ-יָה!', 'לא נוותר!', 'ביחד!', 'דמוקרטיה!', 'עוד שבוע, עוד שבוע!', 'מי שתה לי את הקפה?'];

  const SKINS = ['#f2c9a0', '#e0ac7e', '#c68a5c', '#8d5a3b', '#f6d7b8', '#b77a52'];
  const HAIR = ['#2a1d16', '#5a3a22', '#8a8a8a', '#c49a5a', '#1b1b1f', '#d9d4cc'];
  const SHIRTS = ['#f4f6fb', '#2457c5', '#1f2b5e', '#7aa6ff', '#e9e4d4', '#3a3f4f', 'flag'];
  const PANTS = ['#26304f', '#3b3b45', '#5a4b38', '#1f1f24', '#6b7a8f'];
  const HATS = ['hair', 'hair', 'curly', 'cap', 'tembel', 'tembel', 'bald'];
  const ITEMS = ['sign', 'sign', 'sign', 'sign', 'flag', 'flag', 'flag', 'drum', 'megaphone'];

  const PATH = {
    beard: new Path2D('M-9,-93 Q-7,-80 5,-81 Q13,-83 13,-91 Q8,-87 3,-88 Q-3,-88 -9,-93Z'),
    hair: new Path2D('M-13.6,-99 A13.6,13.6 0 0 1 13.4,-101 Q4,-106 -13.6,-99Z'),
    cap: new Path2D('M-13.5,-101 A13.5,13.5 0 0 1 13.5,-101 Z'),
    tembel: new Path2D('M-11,-104 Q-11,-117 0,-117 Q11,-117 11,-104 Z'),
    mega: new Path2D('M16,-95 L16,-87 L44,-78 L44,-104Z'),
    zig: new Path2D('M-14,-6 L-7,10 L0,-6 L7,10 L14,-6'),
    star1: new Path2D('M25,10 L31,20.5 L19,20.5Z'),
    star2: new Path2D('M25,24 L31,13.5 L19,13.5Z'),
  };
  const CURLS = [[-11, -103], [-5, -110], [3, -111], [10, -106], [-13, -96]];

  /* ---------- state ---------- */
  const people = [];
  const banners = [];
  let bubbles = [];
  let boost = 1, bigT = 0, T = 0, flash = false, dimA = 0, waveX = null, drummers = 0;
  let running = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- drawing helpers ---------- */
  function line(x1, y1, x2, y2, color, w) {
    ctx.strokeStyle = color; ctx.lineWidth = w;
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  }
  function circle(x, y, r, color) {
    ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.fill();
  }
  function ellipse(x, y, rx, ry, color) {
    ctx.fillStyle = color; ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, TAU); ctx.fill();
  }
  const phoneGlow = document.createElement('canvas');
  phoneGlow.width = phoneGlow.height = 72;
  {
    const g = phoneGlow.getContext('2d');
    const gr = g.createRadialGradient(36, 36, 0, 36, 36, 36);
    gr.addColorStop(0, 'rgba(255,246,207,.95)');
    gr.addColorStop(0.45, 'rgba(255,246,207,.55)');
    gr.addColorStop(1, 'rgba(255,246,207,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 72, 72);
  }

  /* ---------- cached sign images & text widths ---------- */
  const signCache = new Map();
  const widthCache = new Map();
  const SK = 3;
  function signSprite(p) {
    const key = p.sign + '|' + p.board + '|' + p.ink;
    let c = signCache.get(key);
    if (c) return c;
    const lines = p.sign.split('\n');
    ctx.save(); ctx.font = `16px ${FONT}`;
    let mw = 1;
    lines.forEach(t => { mw = Math.max(mw, ctx.measureText(t).width); });
    ctx.restore();
    const fs = Math.min(19, 16 * 84 / mw), lh = fs * 1.1, bh = lines.length * lh + 12, pad = 2;
    const cvs = document.createElement('canvas');
    cvs.width = Math.ceil((96 + pad * 2) * SK); cvs.height = Math.ceil((bh + pad * 2) * SK);
    const g = cvs.getContext('2d');
    g.scale(SK, SK); g.translate(pad, pad);
    g.fillStyle = p.board; g.strokeStyle = 'rgba(0,0,0,.25)'; g.lineWidth = 1.5;
    g.beginPath(); g.roundRect(0, 0, 96, bh, 3); g.fill(); g.stroke();
    g.fillStyle = p.ink; g.font = `${fs.toFixed(1)}px ${FONT}`;
    g.textAlign = 'center'; g.textBaseline = 'middle'; g.direction = 'rtl';
    lines.forEach((t, i) => g.fillText(t, 48, 6 + lh * (i + 0.5)));
    c = { cvs, x: -48 - pad, y: -bh - pad, w: 96 + pad * 2, h: bh + pad * 2 };
    signCache.set(key, c);
    return c;
  }
  function textWidth(text, size) {
    const key = size + '|' + text;
    let w = widthCache.get(key);
    if (w === undefined) {
      ctx.save(); ctx.font = `${size}px ${FONT}`; w = ctx.measureText(text).width; ctx.restore();
      widthCache.set(key, w);
    }
    return w;
  }

  /* ---------- person construction ---------- */
  function makePerson(x, opts = {}) {
    const depth = opts.depth ?? Math.random();
    const shirt = pick(SHIRTS);
    const hat = pick(HATS);
    return {
      x, depth, y: 440 + depth * 95, s: 0.8 + depth * 0.5,
      speed: opts.speed ?? rand(18, 30), phase: rand(0, 6.28),
      item: opts.item ?? pick(ITEMS),
      skin: pick(SKINS), hair: pick(HAIR), pants: pick(PANTS), hat,
      shirtCol: shirt === 'flag' ? '#f4f6fb' : shirt,
      sleeve: shirt === 'flag' ? '#2457c5' : shirt,
      flagShirt: shirt === 'flag',
      hatCol: hat === 'cap' ? pick(['#2457c5', '#1b1b1f', '#f4f6fb']) : pick(['#e9e2c8', '#d8c9a0', '#9bb4e8']),
      beard: Math.random() < 0.3, glasses: Math.random() < 0.3,
      sign: pick(SIGNS), board: pick(['#ffffff', '#f4efe2', '#dfe8ff']), ink: pick(['#1d3fa6', '#16182a', '#1d3fa6']),
      jumpT: 0, jumpDelay: -1, cheer: false, waved: false,
      nextBubble: rand(0.5, 8), bubble: null,
      hand: { x: 0, y: 0 }, bodyY: 0, jy: 0, a: 0, hx: 0, hy: 0, bx: 0, by: 0,
    };
  }

  function insertPerson(p) {
    let i = people.findIndex(q => q.y > p.y);
    if (i < 0) i = people.length;
    people.splice(i, 0, p);
    if (p.item === 'drum') drummers++;
    return p;
  }

  /* ---------- banner pair ---------- */
  function addBannerPair(x) {
    const depth = 0.5, speed = 23;
    const a = insertPerson(makePerson(x, { depth, speed, item: 'banner' }));
    const b = insertPerson(makePerson(x + 190 * a.s, { depth, speed, item: 'banner' }));
    a.bannerWith = b; b.follower = true;
    banners.push({ a, b });
  }

  /* ---------- per-frame pose ---------- */
  function pose(p) {
    const s = p.s, a = p.a = Math.sin(p.phase) * 0.5;
    const bob = Math.abs(Math.cos(p.phase)) * 2.5;
    const jy = p.jy = p.jumpT > 0 ? Math.sin(Math.PI * (1 - p.jumpT / 0.6)) * 30 : 0;
    p.bodyY = p.y - (bob + jy) * s;
    const cheer = p.cheer && p.jumpT > 0;

    const wave = Math.sin(T * 4 + p.phase) * 4;
    let hx = 14, hy = -114 + wave;
    if (p.item === 'megaphone') { hx = 18; hy = -90; }
    if (p.item === 'banner') { hx = 12; hy = -112; }
    const beat = p.beat = Math.abs(Math.sin(T * (bigT > 0 ? 16 : 9) + p.phase));
    if (p.item === 'drum') { hx = 22; hy = -80 + beat * 10; }
    if (cheer && (p.item === 'sign' || p.item === 'flag')) hy -= 10;

    let bx, by;
    if (cheer) { bx = -10; by = -126; }
    else if (flash) { bx = -6; by = -124 + Math.sin(T * 2 + p.phase) * 3; }
    else if (p.item === 'banner' || p.item === 'flag') { bx = hx - 7; by = hy + 10; }
    else if (p.item === 'drum') { bx = 8; by = -78 + (1 - beat) * 10; }
    else { const ba = -a * 0.9; bx = -4 + Math.sin(ba) * 30; by = -78 + Math.cos(ba) * 30; }

    p.hx = hx; p.hy = hy; p.bx = bx; p.by = by;
    p.hand.x = p.x + hx * s; p.hand.y = p.bodyY + hy * s;
  }

  const visible = p => p.x > -140 && p.x < W + 140;

  function drawShadow(p) {
    const s = p.s, k = 1 - p.jy / 90;
    ellipse(p.x + 2 * s, p.y + 1, 19 * s * k, 5 * s * k, 'rgba(0,0,0,.35)');
  }

  function drawPerson(p) {
    const { a, hx, hy, bx, by } = p;
    ctx.save();
    ctx.translate(p.x, p.bodyY); ctx.scale(p.s, p.s);

    const leg = sgn => {
      const ex = Math.sin(a * sgn) * 40, ey = -42 + Math.cos(a * sgn) * 40;
      line(0, -44, ex, ey, p.pants, 10);
      ellipse(ex + 4, ey + 1, 8, 4, '#141418');
    };

    leg(-1);
    line(-4, -78, bx, by, p.sleeve, 8);
    circle(bx, by, 4.5, p.skin);
    if (flash) {
      ctx.save(); ctx.translate(bx, by - 4);
      ctx.drawImage(phoneGlow, -18, -26, 36, 36);
      ctx.fillStyle = '#222'; ctx.beginPath(); ctx.roundRect(-4, -8, 8, 13, 1.5); ctx.fill();
      circle(0, -5, 2.2, '#fff');
      ctx.restore();
    }
    leg(1);

    // torso
    ctx.fillStyle = p.shirtCol; ctx.beginPath(); ctx.roundRect(-14, -84, 28, 44, 7); ctx.fill();
    if (p.flagShirt) {
      ctx.fillStyle = '#2457c5'; ctx.fillRect(-14, -78, 28, 4); ctx.fillRect(-14, -52, 28, 4);
    }

    // head
    circle(0, -98, 13, p.skin);
    if (p.beard) { ctx.fillStyle = p.hair; ctx.fill(PATH.beard); }
    if (p.hat === 'hair') { ctx.fillStyle = p.hair; ctx.fill(PATH.hair); }
    else if (p.hat === 'curly') CURLS.forEach(([cx, cy]) => circle(cx, cy, 5.5, p.hair));
    else if (p.hat === 'cap') { ctx.fillStyle = p.hatCol; ctx.fill(PATH.cap); ellipse(15, -101, 9, 2.6, p.hatCol); }
    else if (p.hat === 'tembel') { ctx.fillStyle = p.hatCol; ctx.fill(PATH.tembel); ellipse(0, -104, 17, 4, p.hatCol); }
    circle(6, -100.5, 1.8, '#16161a');
    line(2, -106, 9.5, -105, '#16161a', 1.6);
    circle(13, -97.5, 3.5, p.skin);
    if (p.glasses) {
      ctx.strokeStyle = '#16161a'; ctx.lineWidth = 1.3;
      ctx.beginPath(); ctx.arc(6, -100.5, 4.5, 0, TAU); ctx.stroke();
      line(1.5, -100.5, -9, -101.5, '#16161a', 1.3);
    }
    if (p.bubble || (p.cheer && p.jumpT > 0)) ellipse(8.5, -89, 3.4, 4.2, '#5a1a1a');
    else line(5, -89, 10, -89.5, '#5a1a1a', 1.4);

    // items
    if (p.item === 'drum') {
      ctx.save(); ctx.translate(16, -56);
      ctx.fillStyle = '#c8323c'; ctx.fillRect(-14, -8, 28, 20);
      ctx.strokeStyle = '#f2d58a'; ctx.lineWidth = 1.5; ctx.stroke(PATH.zig);
      ellipse(0, 12, 14, 4, '#a52630');
      ellipse(0, -8, 14, 4, '#f3efe4');
      ctx.strokeStyle = '#c9c2ad'; ctx.lineWidth = 1; ctx.stroke();
      ctx.restore();
      line(hx, hy, hx - 4, hy + 13, '#d9b77a', 2.5);
      line(bx, by, bx + 6, by + 13, '#d9b77a', 2.5);
    } else if (p.item !== 'megaphone') {
      ctx.save(); ctx.translate(hx, hy);
      if (p.item === 'sign') {
        line(0, 16, 0, -44, '#8a6a43', 4);
        ctx.translate(0, -44); ctx.rotate(Math.sin(T * 2.6 + p.phase) * 4 * Math.PI / 180);
        const c = signSprite(p);
        ctx.drawImage(c.cvs, c.x, c.y, c.w, c.h);
      } else {
        line(0, 16, 0, p.item === 'flag' ? -62 : -42, '#8a6a43', 3);
        if (p.item === 'flag') drawFlag(p);
      }
      ctx.restore();
    }

    line(6, -78, hx, hy, p.sleeve, 8);
    circle(hx, hy, 4.5, p.skin);
    if (p.item === 'megaphone') {
      ctx.fillStyle = '#efefef'; ctx.fill(PATH.mega);
      ctx.strokeStyle = '#555'; ctx.lineWidth = 1.5; ctx.stroke(PATH.mega);
      ctx.fillStyle = '#2457c5'; ctx.fillRect(38, -102, 4, 22);
    }
    ctx.restore();
  }

  function drawFlag(p) {
    const skew = Math.sin(T * 5 + p.phase) * 9 * Math.PI / 180;
    ctx.translate(1, -60);
    ctx.transform(1, Math.tan(skew), 0, 1, 0, 0);
    ctx.scale(0.92 + Math.sin(T * 5 + p.phase + 1) * 0.08, 1);
    ctx.fillStyle = '#f7f7fb'; ctx.fillRect(0, 0, 50, 34);
    ctx.strokeStyle = '#c9cde0'; ctx.lineWidth = 0.8; ctx.strokeRect(0, 0, 50, 34);
    ctx.fillStyle = '#2457c5'; ctx.fillRect(0, 3.5, 50, 5); ctx.fillRect(0, 25.5, 50, 5);
    ctx.strokeStyle = '#2457c5'; ctx.lineWidth = 1.6;
    ctx.stroke(PATH.star1); ctx.stroke(PATH.star2);
  }

  function drawBanner(bn) {
    const A = bn.a.hand, B = bn.b.hand, s = bn.a.s;
    const t1 = A.y - 40 * s, t2 = B.y - 40 * s, h = 32 * s, sag = 6 * s, mx = (A.x + B.x) / 2, my = (t1 + t2) / 2;
    ctx.beginPath();
    ctx.moveTo(A.x, t1); ctx.quadraticCurveTo(mx, my + sag, B.x, t2);
    ctx.lineTo(B.x, t2 + h); ctx.quadraticCurveTo(mx, my + h + sag, A.x, t1 + h);
    ctx.closePath();
    ctx.fillStyle = '#f7f7fb'; ctx.fill();
    ctx.strokeStyle = '#2457c5'; ctx.lineWidth = 4 * s; ctx.stroke();
    ctx.fillStyle = '#2457c5'; ctx.font = `${(22 * s).toFixed(1)}px ${FONT}`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.direction = 'rtl';
    ctx.fillText('דמוקרטיה', mx, my + h / 2 + sag * 0.5);
  }

  /* ---------- speech bubbles ---------- */
  function say(p, text, big = false, life = 2.2) {
    if (p.bubble) bubbles = bubbles.filter(b => b !== p.bubble);
    const size = big ? 18 : 15;
    const b = { p, text, big, size, w: textWidth(text, size) + 20, h: big ? 30 : 26, life, max: life };
    p.bubble = b; bubbles.push(b);
  }
  function drawBubble(b) {
    const p = b.p, s = p.s;
    const mx = p.x + 12 * s, my = p.bodyY - 92 * s;
    let bx = mx + 16;
    const by = my - 34 - b.h;
    if (bx + b.w > W - 4) bx = W - 4 - b.w;
    const tx = Math.min(Math.max(bx + 8, mx), bx + b.w - 22);
    ctx.globalAlpha = clamp(Math.min(b.life / 0.3, (b.max - b.life) / 0.12), 0, 1);
    ctx.fillStyle = '#fff'; ctx.strokeStyle = '#16182a'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.roundRect(bx, by, b.w, b.h, 10); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(tx, by + b.h); ctx.lineTo(mx + 4, my - 6); ctx.lineTo(tx + 13, by + b.h);
    ctx.fill(); ctx.stroke();
    ctx.fillRect(tx + 1.5, by + b.h - 3, 10, 4);
    ctx.fillStyle = b.big ? '#1d3fa6' : '#16182a';
    ctx.font = `${b.size}px ${FONT}`;
    ctx.fillText(b.text, bx + b.w / 2, by + b.h / 2 + 1);
    ctx.globalAlpha = 1;
  }

  /* ---------- update ---------- */
  function update(dt) {
    boost = Math.max(1, boost - dt * 0.35);
    if (bigT > 0) bigT -= dt;
    let talking = 0;
    for (const b of bubbles) if (!b.big) talking++;

    if (waveX !== null) {
      waveX -= 650 * dt;
      for (const p of people) {
        if (!p.waved && p.x >= waveX) { p.waved = true; p.cheer = true; p.jumpT = 0.6; p.jumpDelay = -1; }
      }
      if (waveX < -200) waveX = null;
    }

    for (const p of people) {
      p.x += p.speed * p.s * boost * dt;
      p.phase += dt * (p.speed / 6) * boost;
      if (!p.follower && p.x > W + 100) {
        const shift = W + 300 + rand(0, 120);
        p.x -= shift; if (p.bannerWith) p.bannerWith.x -= shift;
      }
      if (p.jumpDelay > 0) { p.jumpDelay -= dt; if (p.jumpDelay <= 0) { p.jumpT = 0.6; p.jumpDelay = -1; } }
      if (p.jumpT > 0) { p.jumpT = Math.max(0, p.jumpT - dt); if (p.jumpT === 0) p.cheer = false; }
      p.nextBubble -= dt;
      if (!p.bubble && p.nextBubble <= 0 && p.x > 20 && p.x < W - 80) {
        if (talking < 5) { say(p, pick(CHANTS)); talking++; }
        p.nextBubble = p.item === 'megaphone' ? rand(1.5, 4) : rand(4, 10);
      }
    }

    bubbles = bubbles.filter(b => {
      b.life -= dt;
      if (b.life <= 0) { b.p.bubble = null; return false; }
      return true;
    });
  }

  function render() {
    ctx.setTransform(K, 0, 0, K, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    if (dimA > 0.005) { ctx.fillStyle = `rgba(0,0,0,${dimA.toFixed(3)})`; ctx.fillRect(0, 0, W, H); }

    for (const p of people) pose(p);
    for (const p of people) if (visible(p)) drawShadow(p);
    for (const p of people) if (visible(p)) drawPerson(p);
    for (const bn of banners) drawBanner(bn);

    ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.direction = 'rtl';
    for (const b of bubbles) drawBubble(b);

    if (bigT > 0) {
      const k = 1 - bigT / 2;
      const sc = k < 0.12 ? 0.5 + (k / 0.12) * 0.65 : 1.15 - Math.min(0.15, (k - 0.12) * 0.6);
      ctx.save();
      ctx.globalAlpha = bigT < 0.5 ? bigT / 0.5 : 1;
      ctx.translate(500, 110); ctx.rotate(-3 * Math.PI / 180); ctx.scale(sc, sc);
      ctx.font = `96px ${FONT}`;
      ctx.lineWidth = 8; ctx.strokeStyle = '#fff'; ctx.strokeText('דמוקרטיה!', 0, 0);
      ctx.fillStyle = '#3b74ff'; ctx.fillText('דמוקרטיה!', 0, 0);
      ctx.restore();
    }
  }

  /* ---------- sound: synthesized drums ---------- */
  let audio = null, master = null, noiseBuf = null, soundOn = false;
  let nextBeat = 0, step = 0, rollUntil = 0;
  function initAudio() {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return false;
    audio = new AC();
    master = audio.createGain(); master.gain.value = 0.45; master.connect(audio.destination);
    noiseBuf = audio.createBuffer(1, audio.sampleRate * 0.3, audio.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return true;
  }
  function kick(t, v) {
    const o = audio.createOscillator(), g = audio.createGain();
    o.frequency.setValueAtTime(140, t); o.frequency.exponentialRampToValueAtTime(45, t + 0.25);
    g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
    o.connect(g).connect(master); o.start(t); o.stop(t + 0.4);
  }
  function snare(t, v) {
    const n = audio.createBufferSource(), f = audio.createBiquadFilter(), g = audio.createGain();
    n.buffer = noiseBuf; f.type = 'highpass'; f.frequency.value = 1400;
    g.gain.setValueAtTime(v, t); g.gain.exponentialRampToValueAtTime(0.001, t + 0.12);
    n.connect(f).connect(g).connect(master); n.start(t); n.stop(t + 0.15);
  }
  // "דֶּ-מוֹ-קְרַטְ-יָה" rhythm: dum, dum, dum-dum-dum, rest
  const PATTERN = ['K', 'S', 'K', 'S', 'K', 'K', 'K', '-'];
  function scheduleAudio() {
    if (!audio || !soundOn || !running) return;
    const now = audio.currentTime;
    if (nextBeat < now) nextBeat = now + 0.05;
    const v = Math.min(1, 0.4 + drummers * 0.06);
    while (nextBeat < now + 0.15) {
      const t = nextBeat;
      if (t < rollUntil) {
        snare(t, 0.45);
        if (step % 4 === 0) kick(t, 0.9);
        nextBeat += 0.0625;
      } else {
        const hit = PATTERN[step % PATTERN.length];
        if (hit === 'K') kick(t, v);
        else if (hit === 'S') snare(t, v * 0.5);
        nextBeat += 0.25;
      }
      step++;
    }
  }

  /* ---------- loop ---------- */
  let last = performance.now();
  function frame(now) {
    const real = Math.min(0.05, (now - last) / 1000); last = now;
    const target = flash ? 0.35 : 0;
    dimA += (target - dimA) * Math.min(1, real * 5);
    if (running && real > 0) { T += real; update(real); }
    scheduleAudio();
    render();
    requestAnimationFrame(frame);
  }

  /* ---------- controls ---------- */
  const fmt = new Intl.NumberFormat('he-IL');
  const addBtn = document.getElementById('add');
  const add10Btn = document.getElementById('add10');
  function updateCount() {
    document.getElementById('police').textContent = fmt.format(people.length);
    document.getElementById('org').textContent = fmt.format(people.length * 9871 + 1948);
    const full = people.length >= MAX;
    addBtn.disabled = full; add10Btn.disabled = full;
  }
  function addOne() {
    if (people.length >= MAX) return;
    const p = insertPerson(makePerson(-50 - rand(0, 60)));
    say(p, pick(['הגעתי!', 'חכו לי!', 'איפה החניה?']), false, 1.8);
    updateCount();
  }
  function addMany(n) {
    const count = Math.min(n, MAX - people.length);
    let first = null;
    for (let i = 0; i < count; i++) {
      const p = insertPerson(makePerson(-50 - rand(0, 380)));
      if (!first || p.x > first.x) first = p;
    }
    if (first) say(first, 'הבאנו את כל השכונה!', false, 2);
    updateCount();
  }
  function drums() {
    const onScreen = people.filter(p => p.x > 20 && p.x < W - 80);
    for (let i = onScreen.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1)); [onScreen[i], onScreen[j]] = [onScreen[j], onScreen[i]];
    }
    const talkers = new Set(onScreen.slice(0, 14));
    for (const p of people) {
      p.jumpDelay = rand(0.01, 0.35);
      if (talkers.has(p)) say(p, pick(['דמוקרטיה!', 'דמוקרטיה!', 'לא נוותר!']), true);
      p.nextBubble = rand(3, 7);
    }
    bigT = 2; boost = 2.2;
    if (audio && soundOn) rollUntil = audio.currentTime + 1.6;
    if (!running) togglePause();
  }
  function startWave() {
    for (const p of people) p.waved = false;
    waveX = W + 150;
    if (!running) togglePause();
  }
  const pauseBtn = document.getElementById('pause');
  function togglePause() { running = !running; pauseBtn.textContent = running ? 'השהה' : 'הפעל'; }
  pauseBtn.textContent = running ? 'השהה' : 'הפעל';

  const soundBtn = document.getElementById('sound');
  soundBtn.addEventListener('click', () => {
    if (!audio && !initAudio()) { soundBtn.disabled = true; return; }
    soundOn = !soundOn;
    if (soundOn) audio.resume();
    soundBtn.setAttribute('aria-pressed', String(soundOn));
  });

  addBtn.addEventListener('click', addOne);
  add10Btn.addEventListener('click', () => addMany(10));
  document.getElementById('stage').addEventListener('click', addOne);
  document.getElementById('drums').addEventListener('click', drums);
  document.getElementById('wave').addEventListener('click', startWave);
  pauseBtn.addEventListener('click', togglePause);
  const flashBtn = document.getElementById('flash');
  flashBtn.addEventListener('click', () => {
    flash = !flash;
    flashBtn.setAttribute('aria-pressed', String(flash));
  });

  /* ---------- start ---------- */
  const starters = ['flag', 'sign', 'drum', 'sign', 'flag', 'megaphone', 'sign', 'flag', 'sign', 'drum'];
  starters.forEach((it, i) => insertPerson(makePerson(-80 + i * 110 + rand(-20, 20), { item: it })));
  addBannerPair(360);
  updateCount();
  if (document.fonts) document.fonts.ready.then(() => {
    signCache.clear(); widthCache.clear();
    for (const b of bubbles) b.w = textWidth(b.text, b.size) + 20;
  });
  requestAnimationFrame(frame);
})();
