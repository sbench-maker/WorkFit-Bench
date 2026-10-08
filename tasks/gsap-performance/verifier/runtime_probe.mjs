import { pathToFileURL } from "node:url";

const appPath = process.argv[2];
const scenario = process.argv[3];

const wait = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

class Monitor {
  constructor() {
    this.forcedLayouts = 0;
    this.writeSeen = false;
  }
  beginTurn() {
    this.writeSeen = false;
  }
  readLayout() {
    if (this.writeSeen) this.forcedLayouts += 1;
  }
  writeVisual() {
    this.writeSeen = true;
  }
  reset() {
    this.forcedLayouts = 0;
    this.writeSeen = false;
  }
}

class FakeTarget {
  constructor(label, monitor, rect = { left: 0, top: 0, right: 100, bottom: 100, width: 100, height: 100 }) {
    this.label = label;
    this.monitor = monitor;
    this.rect = { ...rect };
    this.dataset = {};
    this.attributes = {};
    this.visual = {};
    this.listeners = new Map();
  }
  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(handler);
  }
  removeEventListener(type, handler) {
    this.listeners.get(type)?.delete(handler);
  }
  emit(type, payload = {}) {
    this.monitor.beginTurn();
    for (const handler of [...(this.listeners.get(type) || [])]) handler({ type, target: this, ...payload });
  }
  getBoundingClientRect() {
    this.monitor.readLayout();
    return { ...this.rect };
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  getAttribute(name) {
    return this.attributes[name] ?? null;
  }
}

class FakeWindow extends FakeTarget {
  constructor(monitor, reduced) {
    super("window", monitor);
    this.innerHeight = 720;
    this.reduced = reduced;
    this.pendingTimers = new Map();
    this.nextTimer = 1;
  }
  matchMedia(query) {
    return { matches: this.reduced && query.includes("prefers-reduced-motion") };
  }
  setTimeout(callback, milliseconds) {
    const id = this.nextTimer++;
    const nativeId = setTimeout(() => {
      this.pendingTimers.delete(id);
      this.monitor.beginTurn();
      callback();
    }, milliseconds);
    this.pendingTimers.set(id, nativeId);
    return id;
  }
  clearTimeout(id) {
    const nativeId = this.pendingTimers.get(id);
    if (nativeId !== undefined) clearTimeout(nativeId);
    this.pendingTimers.delete(id);
  }
  requestAnimationFrame(callback) {
    return this.setTimeout(() => callback(Date.now()), 0);
  }
  cancelAnimationFrame(id) {
    this.clearTimeout(id);
  }
}

const META_KEYS = new Set([
  "duration", "delay", "ease", "stagger", "overwrite", "onStart", "onUpdate", "onComplete",
  "paused", "immediateRender", "defaults", "repeat", "yoyo", "callbackScope"
]);
const LAYOUT_KEYS = new Set([
  "top", "right", "bottom", "left", "width", "height", "minWidth", "maxWidth", "minHeight",
  "maxHeight", "margin", "marginTop", "marginRight", "marginBottom", "marginLeft", "padding",
  "paddingTop", "paddingRight", "paddingBottom", "paddingLeft"
]);

function targetsOf(value) {
  if (Array.isArray(value)) return value.flatMap(targetsOf);
  if (value && typeof value.length === "number" && typeof value !== "string" && !value.label) {
    return Array.from(value).flatMap(targetsOf);
  }
  return value ? [value] : [];
}

function parseTransform(target, value) {
  if (typeof value !== "string") return;
  const tx = value.match(/translateX\(\s*(-?[\d.]+)px\s*\)/i);
  const ty = value.match(/translateY\(\s*(-?[\d.]+)px\s*\)/i);
  const pair = value.match(/translate(?:3d)?\(\s*(-?[\d.]+)px\s*,\s*(-?[\d.]+)px/i);
  if (tx) target.visual.x = Number(tx[1]);
  if (ty) target.visual.y = Number(ty[1]);
  if (pair) {
    target.visual.x = Number(pair[1]);
    target.visual.y = Number(pair[2]);
  }
}

class FakeGsap {
  constructor(monitor) {
    this.monitor = monitor;
    this.records = [];
    this.allocations = 0;
    this.kills = 0;
  }
  _apply(targetValue, vars, kind, allocate = true) {
    const targets = targetsOf(targetValue);
    if (allocate) this.allocations += 1;
    const flattened = { ...vars };
    if (vars?.css && typeof vars.css === "object") Object.assign(flattened, vars.css);
    this.records.push({
      kind,
      targets: targets.map((target) => target.label || "anonymous"),
      vars: Object.fromEntries(Object.entries(flattened).filter(([key]) => key !== "css"))
    });
    for (const target of targets) {
      for (const [key, value] of Object.entries(flattened)) {
        if (key === "css" || META_KEYS.has(key)) continue;
        this.monitor.writeVisual();
        if (key === "autoAlpha") {
          target.visual.opacity = value;
          target.visual.visibility = Number(value) === 0 ? "hidden" : "visible";
        } else if (key === "transform") {
          target.visual.transform = value;
          parseTransform(target, value);
        } else {
          target.visual[key] = value;
        }
      }
    }
    return { killed: false, kill() { this.killed = true; } };
  }
  to(targets, vars) {
    return this._apply(targets, vars || {}, "to", true);
  }
  fromTo(targets, fromVars, toVars) {
    this._apply(targets, fromVars || {}, "from", false);
    return this._apply(targets, toVars || {}, "fromTo", true);
  }
  set(targets, vars) {
    return this._apply(targets, vars || {}, "set", false);
  }
  quickTo(target, property, options = {}) {
    this.allocations += 1;
    const tween = { killed: false, kill() { this.killed = true; } };
    const setter = (value) => {
      if (tween.killed) return;
      this._apply(target, { [property]: value, ...options }, "quickTo-update", false);
    };
    setter.tween = tween;
    this.records.push({ kind: "quickTo-create", targets: [target.label], vars: { property, ...options } });
    return setter;
  }
  quickSetter(target, property) {
    return (value) => this._apply(target, { [property]: value }, "quickSetter-update", false);
  }
  timeline() {
    this.allocations += 1;
    const api = {
      to: (targets, vars) => { this._apply(targets, vars || {}, "timeline-to", false); return api; },
      fromTo: (targets, fromVars, toVars) => {
        this._apply(targets, fromVars || {}, "timeline-from", false);
        this._apply(targets, toVars || {}, "timeline-fromTo", false);
        return api;
      },
      set: (targets, vars) => { this._apply(targets, vars || {}, "timeline-set", false); return api; },
      kill: () => { this.kills += 1; return api; },
      play: () => api,
      reverse: () => api,
      restart: () => api,
      pause: () => api
    };
    return api;
  }
  context(callback) {
    callback();
    return { revert: () => { this.kills += 1; } };
  }
  killTweensOf() {
    this.kills += 1;
  }
}

function buildFixture(reduced = false) {
  const monitor = new Monitor();
  const win = new FakeWindow(monitor, reduced);
  const board = new FakeTarget("incident-board", monitor, {
    left: 12, top: 8, right: 1212, bottom: 728, width: 1200, height: 720
  });
  const halo = new FakeTarget("cursor-halo", monitor);
  const drawer = new FakeTarget("detail-drawer", monitor);
  drawer.dataset.state = "closed";
  drawer.setAttribute("aria-hidden", "true");
  const openButton = new FakeTarget("open-drawer", monitor);
  const closeButton = new FakeTarget("close-drawer", monitor);
  const cards = Array.from({ length: 240 }, (_, index) => {
    const top = index < 16 ? 32 + index * 38 : 900 + (index - 16) * 9;
    return new FakeTarget(`card-${String(index + 1).padStart(3, "0")}`, monitor, {
      left: 30, top, right: 250, bottom: top + 110, width: 220, height: 110
    });
  });
  const selectors = new Map([
    [".incident-board", board],
    [".cursor-halo", halo],
    [".detail-drawer", drawer],
    ['[data-action="open-drawer"]', openButton],
    ['[data-action="close-drawer"]', closeButton]
  ]);
  const root = {
    querySelector(selector) { return selectors.get(selector) || null; },
    querySelectorAll(selector) { return selector === ".incident-card" ? cards : []; }
  };
  const gsap = new FakeGsap(monitor);
  const ScrollTrigger = { refreshes: 0, refresh() { this.refreshes += 1; } };
  return { monitor, win, board, halo, drawer, openButton, closeButton, cards, root, gsap, ScrollTrigger };
}

async function mount(reduced = false) {
  const fixture = buildFixture(reduced);
  const url = `${pathToFileURL(appPath).href}?probe=${scenario}-${reduced}-${Date.now()}-${Math.random()}`;
  const module = await import(url);
  if (typeof module.mountIncidentWall !== "function") throw new Error("app.js does not export mountIncidentWall");
  const cleanup = module.mountIncidentWall({
    root: fixture.root,
    win: fixture.win,
    gsap: fixture.gsap,
    ScrollTrigger: fixture.ScrollTrigger
  });
  if (typeof cleanup !== "function") throw new Error("mountIncidentWall does not return a cleanup function");
  return { ...fixture, cleanup };
}

function badLayoutRecords(records) {
  const bad = [];
  for (const record of records) {
    const properties = Object.keys(record.vars || {}).filter((key) => LAYOUT_KEYS.has(key));
    if (properties.length) bad.push({ kind: record.kind, targets: record.targets, properties });
  }
  return bad;
}

function endpoint(drawer) {
  return {
    x: drawer.visual.x ?? null,
    xPercent: drawer.visual.xPercent ?? null,
    right: drawer.visual.right ?? null,
    transform: drawer.visual.transform ?? null,
    state: drawer.dataset.state,
    ariaHidden: drawer.getAttribute("aria-hidden")
  };
}

async function pointerScenario() {
  const fixture = await mount(false);
  const startAllocations = fixture.gsap.allocations;
  const startRecord = fixture.gsap.records.length;
  for (let index = 0; index < 180; index++) {
    fixture.board.emit("pointermove", { clientX: 200 + index, clientY: 128 + index });
  }
  fixture.board.emit("pointermove", { clientX: 511, clientY: 307 });
  await wait(35);
  const records = fixture.gsap.records.slice(startRecord).filter((record) => record.targets.includes("cursor-halo"));
  return {
    allocationDelta: fixture.gsap.allocations - startAllocations,
    finalX: fixture.halo.visual.x ?? null,
    finalY: fixture.halo.visual.y ?? null,
    records,
    badLayoutRecords: badLayoutRecords(records)
  };
}

async function revealScenario() {
  const fixture = await mount(false);
  for (let index = 0; index < fixture.cards.length; index++) {
    if (index < 16) {
      fixture.cards[index].rect.top = -300;
      fixture.cards[index].rect.bottom = -190;
    } else if (index < 38) {
      fixture.cards[index].rect.top = 24 + (index - 16) * 25;
      fixture.cards[index].rect.bottom = fixture.cards[index].rect.top + 110;
    } else {
      fixture.cards[index].rect.top = 940 + index;
      fixture.cards[index].rect.bottom = 1050 + index;
    }
  }
  fixture.monitor.reset();
  const startAllocations = fixture.gsap.allocations;
  const startRecord = fixture.gsap.records.length;
  fixture.win.emit("scroll");
  await wait(20);
  const firstDelta = fixture.gsap.allocations - startAllocations;
  const afterFirst = fixture.gsap.allocations;
  fixture.win.emit("scroll");
  await wait(20);
  const revealed = fixture.cards.filter((card) => card.dataset.revealed === "true").map((card) => card.label);
  const newRecords = fixture.gsap.records.slice(startRecord);
  return {
    firstAllocationDelta: firstDelta,
    repeatAllocationDelta: fixture.gsap.allocations - afterFirst,
    forcedLayouts: fixture.monitor.forcedLayouts,
    revealed,
    card018: fixture.cards[17].visual,
    card039Revealed: fixture.cards[38].dataset.revealed === "true",
    badLayoutRecords: badLayoutRecords(newRecords)
  };
}

async function behaviorScenario() {
  const fixture = await mount(false);
  fixture.openButton.emit("click");
  const open = endpoint(fixture.drawer);
  fixture.closeButton.emit("click");
  const closed = endpoint(fixture.drawer);

  const reduced = await mount(true);
  reduced.openButton.emit("click");
  reduced.closeButton.emit("click");
  const animatedRecords = reduced.gsap.records.filter((record) =>
    ["to", "fromTo", "quickTo-create", "quickTo-update", "timeline-to", "timeline-fromTo"].includes(record.kind)
  );
  const nonZeroDurations = animatedRecords
    .filter((record) => Number(record.vars?.duration || 0) > 0)
    .map((record) => ({ kind: record.kind, targets: record.targets, duration: record.vars.duration }));
  return {
    initialRevealedCount: fixture.cards.filter((card) => card.dataset.revealed === "true").length,
    initialCard: fixture.cards[0].visual,
    open,
    closed,
    normalBadLayoutRecords: badLayoutRecords(fixture.gsap.records),
    reducedNonZeroDurations: nonZeroDurations,
    reducedOpenState: reduced.drawer.dataset.state,
    reducedAriaHidden: reduced.drawer.getAttribute("aria-hidden")
  };
}

async function lifecycleScenario() {
  const fixture = await mount(false);
  for (let index = 0; index < 14; index++) fixture.win.emit("resize");
  await wait(180);
  const refreshesAfterBurst = fixture.ScrollTrigger.refreshes;

  fixture.win.emit("resize");
  fixture.cleanup();
  const allocationsAfterCleanup = fixture.gsap.allocations;
  const recordsAfterCleanup = fixture.gsap.records.length;
  const haloAfterCleanup = { ...fixture.halo.visual };
  const drawerAfterCleanup = endpoint(fixture.drawer);
  const refreshesAtCleanup = fixture.ScrollTrigger.refreshes;
  fixture.board.emit("pointermove", { clientX: 900, clientY: 600 });
  fixture.win.emit("scroll");
  fixture.win.emit("resize");
  fixture.openButton.emit("click");
  fixture.closeButton.emit("click");
  await wait(180);
  return {
    refreshesAfterBurst,
    refreshesAfterCleanup: fixture.ScrollTrigger.refreshes - refreshesAtCleanup,
    allocationDeltaAfterCleanup: fixture.gsap.allocations - allocationsAfterCleanup,
    recordDeltaAfterCleanup: fixture.gsap.records.length - recordsAfterCleanup,
    haloUnchanged: JSON.stringify(haloAfterCleanup) === JSON.stringify(fixture.halo.visual),
    drawerUnchanged: JSON.stringify(drawerAfterCleanup) === JSON.stringify(endpoint(fixture.drawer)),
    killSignals: fixture.gsap.kills
  };
}

async function run() {
  if (scenario === "pointer") return pointerScenario();
  if (scenario === "reveal") return revealScenario();
  if (scenario === "behavior") return behaviorScenario();
  if (scenario === "lifecycle") return lifecycleScenario();
  if (scenario === "smoke") {
    const fixture = await mount(false);
    fixture.cleanup();
    return { exported: true };
  }
  throw new Error(`unknown probe scenario: ${scenario}`);
}

try {
  const data = await run();
  process.stdout.write(JSON.stringify({ ok: true, data }));
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: String(error?.message || error), stack: String(error?.stack || "") }));
  process.exitCode = 1;
}
