(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const svg = document.getElementById('crowd');
  const W = 1000;

  const rand = (a, b) => a + Math.random() * (b - a);
  const pick = a => a[Math.floor(Math.random() * a.length)];
  function el(tag, attrs = {}, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  const setLine = (l, x1, y1, x2, y2) => {
    l.setAttribute('x1', x1); l.setAttribute('y1', y1);
    l.setAttribute('x2', x2); l.setAttribute('y2', y2);
  };
  const setPos = (c, x, y) => { c.setAttribute('cx', x); c.setAttribute('cy', y); };

  /* ---------- layers ---------- */
  const defs = el('defs', {}, svg);
  const glow = el('filter', { id: 'phoneGlow', x: '-100%', y: '-100%', width: '300%', height: '300%' }, defs);
  el('feGaussianBlur', { stdDeviation: 5 }, glow);
  const dim = el('rect', { id: 'dim', width: 1000, height: 560, fill: '#000', opacity: 0 }, svg);
  const L = {
    shadows: el('g', {}, svg),
    people: el('g', {}, svg),
    banners: el('g', {}, svg),
    bubbles: el('g', {}, svg),
    fx: el('g', {}, svg),
  };

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

  /* ---------- state ---------- */
  let people = [];
  let bubbles = [];
  let boost = 1, bigT = 0, T = 0, flash = false;
  let running = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- person construction ---------- */
  function flagShape(parent) {
    const g = el('g', {}, parent);
    el('rect', { width: 50, height: 34, fill: '#f7f7fb', stroke: '#c9cde0', 'stroke-width': 0.8 }, g);
    el('rect', { y: 3.5, width: 50, height: 5, fill: '#2457c5' }, g);
    el('rect', { y: 25.5, width: 50, height: 5, fill: '#2457c5' }, g);
    const star = { fill: 'none', stroke: '#2457c5', 'stroke-width': 1.6, 'stroke-linejoin': 'round' };
    el('polygon', Object.assign({ points: '25,10 31,20.5 19,20.5' }, star), g);
    el('polygon', Object.assign({ points: '25,24 31,13.5 19,13.5' }, star), g);
    return g;
  }

  function makePerson(x, opts = {}) {
    const depth = opts.depth ?? Math.random();
    const p = {
      x, depth, y: 440 + depth * 95, s: 0.8 + depth * 0.5,
      speed: opts.speed ?? rand(18, 30), phase: rand(0, 6.28),
      item: opts.item ?? pick(ITEMS),
      skin: pick(SKINS), hair: pick(HAIR), shirt: pick(SHIRTS), pants: pick(PANTS), hat: pick(HATS),
      beard: Math.random() < 0.3, glasses: Math.random() < 0.3,
      sign: pick(SIGNS), board: pick(['#ffffff', '#f4efe2', '#dfe8ff']), ink: pick(['#1d3fa6', '#16182a', '#1d3fa6']),
      jumpT: 0, jumpDelay: -1, nextBubble: rand(0.5, 8), bubble: null,
      hand: { x: 0, y: 0 }, bodyY: 0, P: {},
    };
    build(p);
    return p;
  }

  function build(p) {
    const P = p.P;
    p.shadow = el('ellipse', { fill: 'rgba(0,0,0,.35)' }, L.shadows);
    const g = p.g = el('g', {});
    const next = people.find(q => q.y > p.y);
    if (next) L.people.insertBefore(g, next.g); else L.people.appendChild(g);

    const shirtCol = p.shirt === 'flag' ? '#f4f6fb' : p.shirt;
    const sleeve = p.shirt === 'flag' ? '#2457c5' : shirtCol;
    const limb = (color, w) => el('line', { stroke: color, 'stroke-width': w, 'stroke-linecap': 'round' }, g);

    P.legB = limb(p.pants, 10); P.shoeB = el('ellipse', { rx: 8, ry: 4, fill: '#141418' }, g);
    P.armB = limb(sleeve, 8); P.handB = el('circle', { r: 4.5, fill: p.skin }, g);
    P.phone = el('g', { visibility: 'hidden' }, g);
    el('circle', { cy: -8, r: 12, fill: '#fff6cf', opacity: 0.9, filter: 'url(#phoneGlow)' }, P.phone);
    el('rect', { x: -4, y: -8, width: 8, height: 13, rx: 1.5, fill: '#222' }, P.phone);
    el('circle', { cy: -5, r: 2.2, fill: '#fff' }, P.phone);
    P.legF = limb(p.pants, 10); P.shoeF = el('ellipse', { rx: 8, ry: 4, fill: '#141418' }, g);

    el('rect', { x: -14, y: -84, width: 28, height: 44, rx: 7, fill: shirtCol }, g);
    if (p.shirt === 'flag') {
      el('rect', { x: -14, y: -78, width: 28, height: 4, fill: '#2457c5' }, g);
      el('rect', { x: -14, y: -52, width: 28, height: 4, fill: '#2457c5' }, g);
    }

    // head
    el('circle', { cx: 0, cy: -98, r: 13, fill: p.skin }, g);
    if (p.beard) el('path', { d: 'M-9,-93 Q-7,-80 5,-81 Q13,-83 13,-91 Q8,-87 3,-88 Q-3,-88 -9,-93Z', fill: p.hair }, g);
    if (p.hat === 'hair') el('path', { d: 'M-13.6,-99 A13.6,13.6 0 0 1 13.4,-101 Q4,-106 -13.6,-99Z', fill: p.hair }, g);
    else if (p.hat === 'curly') {
      [[-11, -103], [-5, -110], [3, -111], [10, -106], [-13, -96]].forEach(([cx, cy]) => el('circle', { cx, cy, r: 5.5, fill: p.hair }, g));
    } else if (p.hat === 'cap') {
      const c = pick(['#2457c5', '#1b1b1f', '#f4f6fb']);
      el('path', { d: 'M-13.5,-101 A13.5,13.5 0 0 1 13.5,-101 Z', fill: c }, g);
      el('ellipse', { cx: 15, cy: -101, rx: 9, ry: 2.6, fill: c }, g);
    } else if (p.hat === 'tembel') {
      const c = pick(['#e9e2c8', '#d8c9a0', '#9bb4e8']);
      el('path', { d: 'M-11,-104 Q-11,-117 0,-117 Q11,-117 11,-104 Z', fill: c }, g);
      el('ellipse', { cx: 0, cy: -104, rx: 17, ry: 4, fill: c }, g);
    }
    el('circle', { cx: 6, cy: -100.5, r: 1.8, fill: '#16161a' }, g);
    el('line', { x1: 2, y1: -106, x2: 9.5, y2: -105, stroke: '#16161a', 'stroke-width': 1.6, 'stroke-linecap': 'round' }, g);
    el('circle', { cx: 13, cy: -97.5, r: 3.5, fill: p.skin }, g);
    if (p.glasses) {
      el('circle', { cx: 6, cy: -100.5, r: 4.5, fill: 'none', stroke: '#16161a', 'stroke-width': 1.3 }, g);
      el('line', { x1: 1.5, y1: -100.5, x2: -9, y2: -101.5, stroke: '#16161a', 'stroke-width': 1.3 }, g);
    }
    P.mouthC = el('line', { x1: 5, y1: -89, x2: 10, y2: -89.5, stroke: '#5a1a1a', 'stroke-width': 1.4, 'stroke-linecap': 'round' }, g);
    P.mouthO = el('ellipse', { cx: 8.5, cy: -89, rx: 3.4, ry: 4.2, fill: '#5a1a1a', visibility: 'hidden' }, g);

    // items
    P.item = el('g', {}, g);
    if (p.item === 'sign') {
      el('line', { x1: 0, y1: 16, x2: 0, y2: -44, stroke: '#8a6a43', 'stroke-width': 4, 'stroke-linecap': 'round' }, P.item);
      P.board = el('g', {}, P.item);
      P.boardRect = el('rect', { x: -48, width: 96, rx: 3, fill: p.board, stroke: 'rgba(0,0,0,.25)', 'stroke-width': 1.5 }, P.board);
      P.lines = p.sign.split('\n').map(t => {
        const tx = el('text', { x: 0, 'text-anchor': 'middle', 'dominant-baseline': 'central', fill: p.ink }, P.board);
        tx.textContent = t;
        return tx;
      });
      fitSign(p);
    } else if (p.item === 'flag' || p.item === 'banner') {
      const len = p.item === 'flag' ? -62 : -42;
      el('line', { x1: 0, y1: 16, x2: 0, y2: len, stroke: '#8a6a43', 'stroke-width': 3, 'stroke-linecap': 'round' }, P.item);
      if (p.item === 'flag') P.flag = flagShape(P.item);
    } else if (p.item === 'drum') {
      P.drum = el('g', { transform: 'translate(16 -56)' }, g);
      el('rect', { x: -14, y: -8, width: 28, height: 20, fill: '#c8323c' }, P.drum);
      el('path', { d: 'M-14,-6 L-7,10 L0,-6 L7,10 L14,-6', fill: 'none', stroke: '#f2d58a', 'stroke-width': 1.5 }, P.drum);
      el('ellipse', { cx: 0, cy: 12, rx: 14, ry: 4, fill: '#a52630' }, P.drum);
      el('ellipse', { cx: 0, cy: -8, rx: 14, ry: 4, fill: '#f3efe4', stroke: '#c9c2ad' }, P.drum);
      P.stickB = el('line', { stroke: '#d9b77a', 'stroke-width': 2.5, 'stroke-linecap': 'round' }, g);
      P.stickF = el('line', { stroke: '#d9b77a', 'stroke-width': 2.5, 'stroke-linecap': 'round' }, g);
      g.insertBefore(P.drum, P.item);
    } else if (p.item === 'megaphone') {
      P.mega = el('g', {}, g);
      el('polygon', { points: '16,-95 16,-87 44,-78 44,-104', fill: '#efefef', stroke: '#555', 'stroke-width': 1.5 }, P.mega);
      el('rect', { x: 38, y: -102, width: 4, height: 22, fill: '#2457c5' }, P.mega);
    }
    P.armF = limb(sleeve, 8); P.handF = el('circle', { r: 4.5, fill: p.skin }, g);
    if (P.mega) g.appendChild(P.mega);
  }

  function fitSign(p) {
    const P = p.P, bw = 96;
    P.lines.forEach(t => t.setAttribute('font-size', 16));
    let mw = 1;
    P.lines.forEach(t => { try { mw = Math.max(mw, t.getComputedTextLength()); } catch (e) {} });
    const fs = Math.min(19, 16 * (bw - 12) / mw), lh = fs * 1.1, bh = P.lines.length * lh + 12;
    P.boardRect.setAttribute('y', -bh); P.boardRect.setAttribute('height', bh);
    P.lines.forEach((t, i) => { t.setAttribute('font-size', fs.toFixed(1)); t.setAttribute('y', (-bh + 6 + lh * (i + 0.5)).toFixed(1)); });
  }

  /* ---------- banner pair ---------- */
  const banners = [];
  function addBannerPair(x) {
    const depth = 0.5, speed = 23;
    const a = makePerson(x, { depth, speed, item: 'banner' }); people.push(a);
    const b = makePerson(x + 190 * a.s, { depth, speed, item: 'banner' }); people.push(b);
    a.bannerWith = b; b.follower = true;
    const g = el('g', {}, L.banners);
    const path = el('path', { fill: '#f7f7fb', stroke: '#2457c5', 'stroke-width': 5 }, g);
    const text = el('text', { 'text-anchor': 'middle', 'dominant-baseline': 'central', fill: '#2457c5' }, g);
    text.textContent = 'דמוקרטיה';
    banners.push({ a, b, path, text });
  }

  /* ---------- per-frame ---------- */
  function renderPerson(p) {
    const P = p.P, s = p.s, a = Math.sin(p.phase) * 0.5;
    const bob = Math.abs(Math.cos(p.phase)) * 2.5;
    const jy = p.jumpT > 0 ? Math.sin(Math.PI * (1 - p.jumpT / 0.6)) * 30 : 0;
    p.bodyY = p.y - (bob + jy) * s;
    p.g.setAttribute('transform', `translate(${p.x.toFixed(1)} ${p.bodyY.toFixed(1)}) scale(${s.toFixed(3)})`);
    const k = 1 - jy / 90;
    setPos(p.shadow, (p.x + 2 * s).toFixed(1), p.y + 1);
    p.shadow.setAttribute('rx', (19 * s * k).toFixed(1)); p.shadow.setAttribute('ry', (5 * s * k).toFixed(1));

    const leg = (ln, shoe, sgn) => {
      const ex = Math.sin(a * sgn) * 40, ey = -42 + Math.cos(a * sgn) * 40;
      setLine(ln, 0, -44, ex.toFixed(1), ey.toFixed(1)); setPos(shoe, (ex + 4).toFixed(1), (ey + 1).toFixed(1));
    };
    leg(P.legB, P.shoeB, -1); leg(P.legF, P.shoeF, 1);

    const wave = Math.sin(T * 4 + p.phase) * 4;
    let hx = 14, hy = -114 + wave;
    if (p.item === 'megaphone') { hx = 18; hy = -90; }
    if (p.item === 'banner') { hx = 12; hy = -112; }
    const beat = Math.abs(Math.sin(T * (bigT > 0 ? 16 : 9) + p.phase));
    if (p.item === 'drum') { hx = 22; hy = -80 + beat * 10; }

    // back arm
    let bx, by;
    if (flash) { bx = -6; by = -124 + Math.sin(T * 2 + p.phase) * 3; }
    else if (p.item === 'banner' || p.item === 'flag') { bx = hx - 7; by = hy + 10; }
    else if (p.item === 'drum') { bx = 8; by = -78 + (1 - beat) * 10; }
    else { const ba = -a * 0.9; bx = -4 + Math.sin(ba) * 30; by = -78 + Math.cos(ba) * 30; }
    setLine(P.armB, -4, -78, bx.toFixed(1), by.toFixed(1)); setPos(P.handB, bx.toFixed(1), by.toFixed(1));
    P.phone.setAttribute('visibility', flash ? 'visible' : 'hidden');
    if (flash) P.phone.setAttribute('transform', `translate(${bx.toFixed(1)} ${(by - 4).toFixed(1)})`);

    setLine(P.armF, 6, -78, hx.toFixed(1), hy.toFixed(1)); setPos(P.handF, hx.toFixed(1), hy.toFixed(1));
    if (p.item === 'drum') {
      setLine(P.stickF, hx, hy, hx - 4, hy + 13);
      setLine(P.stickB, bx, by, bx + 6, by + 13);
    } else {
      P.item.setAttribute('transform', `translate(${hx.toFixed(1)} ${hy.toFixed(1)})`);
    }
    if (P.board) P.board.setAttribute('transform', `translate(0 -44) rotate(${(Math.sin(T * 2.6 + p.phase) * 4).toFixed(2)})`);
    if (P.flag) P.flag.setAttribute('transform', `translate(1 -60) skewY(${(Math.sin(T * 5 + p.phase) * 9).toFixed(2)}) scale(${(0.92 + Math.sin(T * 5 + p.phase + 1) * 0.08).toFixed(3)} 1)`);

    const shouting = !!p.bubble;
    P.mouthO.setAttribute('visibility', shouting ? 'visible' : 'hidden');
    P.mouthC.setAttribute('visibility', shouting ? 'hidden' : 'visible');
    p.hand.x = p.x + hx * s; p.hand.y = p.bodyY + hy * s;
  }

  function renderBanner(bn) {
    const A = bn.a.hand, B = bn.b.hand, s = bn.a.s;
    const t1 = A.y - 40 * s, t2 = B.y - 40 * s, h = 32 * s, sag = 6 * s, mx = (A.x + B.x) / 2, my = (t1 + t2) / 2;
    const f = v => v.toFixed(1);
    bn.path.setAttribute('d', `M${f(A.x)},${f(t1)} Q${f(mx)},${f(my + sag)} ${f(B.x)},${f(t2)} L${f(B.x)},${f(t2 + h)} Q${f(mx)},${f(my + h + sag)} ${f(A.x)},${f(t1 + h)} Z`);
    bn.path.setAttribute('stroke-width', f(4 * s));
    bn.text.setAttribute('x', f(mx)); bn.text.setAttribute('y', f(my + h / 2 + sag * 0.5));
    bn.text.setAttribute('font-size', f(22 * s));
  }

  /* ---------- speech bubbles ---------- */
  function say(p, text, big = false, life = 2.2) {
    if (p.bubble) { p.bubble.g.remove(); bubbles = bubbles.filter(b => b !== p.bubble); }
    const g = el('g', {}, L.bubbles);
    const rect = el('rect', { rx: 10, fill: '#fff', stroke: '#16182a', 'stroke-width': 2 }, g);
    const tail = el('path', { fill: '#fff', stroke: '#16182a', 'stroke-width': 2, 'stroke-linejoin': 'round' }, g);
    const cover = el('rect', { height: 4, fill: '#fff' }, g);
    const tx = el('text', { 'text-anchor': 'middle', 'dominant-baseline': 'central', 'font-size': big ? 18 : 15, fill: big ? '#1d3fa6' : '#16182a' }, g);
    tx.textContent = text;
    let tw = 60; try { tw = tx.getComputedTextLength(); } catch (e) {}
    const b = { p, g, rect, tail, cover, tx, w: tw + 20, h: big ? 30 : 26, life, max: life };
    p.bubble = b; bubbles.push(b);
  }
  function renderBubble(b) {
    const p = b.p, s = p.s;
    const mx = p.x + 12 * s, my = p.bodyY - 92 * s;
    let bx = mx + 16, by = my - 34 - b.h;
    if (bx + b.w > W - 4) bx = W - 4 - b.w;
    const tx = Math.min(Math.max(bx + 8, mx), bx + b.w - 22);
    b.rect.setAttribute('x', bx); b.rect.setAttribute('y', by); b.rect.setAttribute('width', b.w); b.rect.setAttribute('height', b.h);
    b.tail.setAttribute('d', `M${tx},${by + b.h} L${mx + 4},${my - 6} L${tx + 13},${by + b.h}`);
    b.cover.setAttribute('x', tx + 1.5); b.cover.setAttribute('y', by + b.h - 3); b.cover.setAttribute('width', 10);
    b.tx.setAttribute('x', bx + b.w / 2); b.tx.setAttribute('y', by + b.h / 2 + 1);
    b.g.setAttribute('opacity', Math.max(0, Math.min(1, b.life / 0.3, (b.max - b.life) / 0.12)).toFixed(2));
  }

  /* ---------- big chant overlay ---------- */
  const big = el('text', { x: 500, y: 110, 'text-anchor': 'middle', 'dominant-baseline': 'central', 'font-size': 96, fill: '#3b74ff', stroke: '#fff', 'stroke-width': 8, 'paint-order': 'stroke', 'stroke-linejoin': 'round', opacity: 0 }, L.fx);
  big.textContent = 'דמוקרטיה!';

  /* ---------- update ---------- */
  function update(dt) {
    boost = Math.max(1, boost - dt * 0.35);
    if (bigT > 0) bigT -= dt;
    let talking = bubbles.filter(b => b.h < 30).length;

    people.forEach(p => {
      p.x += p.speed * p.s * boost * dt;
      p.phase += dt * (p.speed / 6) * boost;
      if (!p.follower && p.x > W + 100) {
        const shift = W + 300 + rand(0, 120);
        p.x -= shift; if (p.bannerWith) p.bannerWith.x -= shift;
      }
      if (p.jumpDelay > 0) { p.jumpDelay -= dt; if (p.jumpDelay <= 0) { p.jumpT = 0.6; p.jumpDelay = -1; } }
      if (p.jumpT > 0) p.jumpT = Math.max(0, p.jumpT - dt);
      p.nextBubble -= dt;
      if (!p.bubble && p.nextBubble <= 0 && p.x > 20 && p.x < W - 80) {
        if (talking < 4) { say(p, pick(CHANTS)); talking++; }
        p.nextBubble = p.item === 'megaphone' ? rand(1.5, 4) : rand(4, 10);
      }
    });

    bubbles = bubbles.filter(b => {
      b.life -= dt;
      if (b.life <= 0) { b.g.remove(); b.p.bubble = null; return false; }
      return true;
    });
  }

  function render() {
    people.forEach(renderPerson);
    banners.forEach(renderBanner);
    bubbles.forEach(renderBubble);
    if (bigT > 0) {
      const k = 1 - bigT / 2;
      const sc = k < 0.12 ? 0.5 + (k / 0.12) * 0.65 : 1.15 - Math.min(0.15, (k - 0.12) * 0.6);
      big.setAttribute('opacity', (bigT < 0.5 ? bigT / 0.5 : 1).toFixed(2));
      big.setAttribute('transform', `translate(500 110) rotate(-3) scale(${sc.toFixed(3)}) translate(-500 -110)`);
    } else big.setAttribute('opacity', 0);
  }

  let last = performance.now();
  function frame(now) {
    let dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (!running) dt = 0;
    if (dt > 0) { T += dt; update(dt); }
    render();
    requestAnimationFrame(frame);
  }

  /* ---------- controls ---------- */
  const fmt = new Intl.NumberFormat('he-IL');
  function updateCount() {
    document.getElementById('police').textContent = fmt.format(people.length);
    document.getElementById('org').textContent = fmt.format(people.length * 9871 + 1948);
  }
  function addOne() {
    if (people.length >= 48) return;
    const p = makePerson(-50 - rand(0, 60));
    people.push(p);
    say(p, pick(['הגעתי!', 'חכו לי!', 'איפה החניה?']), false, 1.8);
    updateCount();
  }
  function drums() {
    people.forEach(p => {
      p.jumpDelay = rand(0.01, 0.35);
      say(p, pick(['דמוקרטיה!', 'דמוקרטיה!', 'לא נוותר!']), true);
      p.nextBubble = rand(3, 7);
    });
    bigT = 2; boost = 2.2;
    if (!running) togglePause();
  }
  const pauseBtn = document.getElementById('pause');
  function togglePause() { running = !running; pauseBtn.textContent = running ? 'השהה' : 'הפעל'; }
  pauseBtn.textContent = running ? 'השהה' : 'הפעל';

  document.getElementById('add').addEventListener('click', addOne);
  document.getElementById('stage').addEventListener('click', addOne);
  document.getElementById('drums').addEventListener('click', drums);
  pauseBtn.addEventListener('click', togglePause);
  const flashBtn = document.getElementById('flash');
  flashBtn.addEventListener('click', () => {
    flash = !flash;
    flashBtn.setAttribute('aria-pressed', String(flash));
    dim.setAttribute('opacity', flash ? 0.35 : 0);
  });

  /* ---------- start ---------- */
  const starters = ['flag', 'sign', 'drum', 'sign', 'flag', 'megaphone', 'sign', 'flag', 'sign', 'drum'];
  starters.forEach((it, i) => people.push(makePerson(-80 + i * 110 + rand(-20, 20), { item: it })));
  addBannerPair(360);
  updateCount();
  if (document.fonts) document.fonts.ready.then(() => people.forEach(p => { if (p.P.board) fitSign(p); }));
  requestAnimationFrame(frame);
})();
