// Render the brand reference images, the logo PNGs and each episode's header overlay.
// Needs Node and Playwright with Chromium:  npm i -D playwright && npx playwright install chromium
//   node tools/render_assets.js          everything
//   node tools/render_assets.js logo     only the logo PNGs, after python3 tools/make_logo.py
// Writes brand/assets/... and episodes/<episode>/assets/hud-overlay.png
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const ROOT = path.resolve(__dirname, "..");
const BRAND = JSON.parse(fs.readFileSync(path.join(ROOT, "brand", "brand.json"), "utf8"));
const C = BRAND.colors;
const FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Archivo:wght@500;700;800&family=Caveat:wght@700&family=Courier+Prime&family=IBM+Plex+Mono:wght@500;600&display=swap">';
// The registration crosshair tools/build_reel.py draws by the header and the captions
const MARK = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="${C.ink}" stroke-width="1.6" stroke-linecap="round"><circle cx="12" cy="12" r="6.3"/><path d="M12 0.5V23.5M0.5 12H23.5"/></g></svg>`;
const LOOP_PATH = "M4 30C60 27 112 33 152 28C177 25 188 7 172 6C156 6 160 31 192 31C242 31 292 23 336 18";
const LOOP = `<svg viewBox="0 0 340 40" xmlns="http://www.w3.org/2000/svg"><path d="${LOOP_PATH}" fill="none" stroke="${C.lemon}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

function out(...p) {
  const f = path.join(ROOT, ...p);
  fs.mkdirSync(path.dirname(f), { recursive: true });
  return f;
}

function tornPolygon(seed, depth = 7, step = 2.4) {
  let s = seed >>> 0;
  const rnd = () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  let i = 0; const j = () => (i++ % 2 ? rnd() * depth : rnd() * depth * 0.35);
  const P = [];
  for (let x = 0; x <= 100.001; x += step) P.push([x, j()]);
  for (let x = 100; x >= -0.001; x -= step) P.push([x, 100 - j()]);
  return "polygon(" + P.map(p => p[0].toFixed(2) + "% " + p[1].toFixed(2) + "%").join(",") + ")";
}

async function shot(page, html, file, { width, height, transparent = false }) {
  await page.setViewportSize({ width, height });
  await page.setContent(`<!doctype html><html><head><meta charset="utf-8">${FONTS}<style>html,body{margin:0;background:${transparent ? "transparent" : C.paper}}</style></head><body>${html}</body></html>`, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: file, omitBackground: transparent, clip: { x: 0, y: 0, width, height } });
  console.log("wrote", path.relative(ROOT, file));
}

// The logo PNGs: every SVG tools/make_logo.py wrote, this many pixels wide (transparent, except the avatar)
const LOGO_WIDTHS = { "logo": 1600, "logo-on-dark": 1600, "logo-horizontal": 2400, "mark": 1024, "avatar": 1080 };

async function logoPngs(page) {
  const dir = path.join(ROOT, "brand", "assets", "logo");
  const files = fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => f.endsWith(".svg")).sort() : [];
  if (!files.length) console.log("no logo SVGs in brand/assets/logo: run python3 tools/make_logo.py first");
  for (const f of files) {
    const svg = fs.readFileSync(path.join(dir, f), "utf8");
    const [, vw, vh] = svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/).map(Number);
    const width = LOGO_WIDTHS[f.replace(/\.svg$/, "").replace(/^[^-]+-/, "")] || 1600;
    const height = Math.round(width * vh / vw);
    await page.setViewportSize({ width, height });
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:transparent}svg{display:block}</style></head><body>${svg.replace(/width="[^"]*" height="[^"]*"/, `width="${width}" height="${height}"`)}</body></html>`);
    const file = path.join(dir, f.replace(/\.svg$/, ".png"));
    await page.screenshot({ path: file, omitBackground: true, clip: { x: 0, y: 0, width, height } });
    console.log("wrote", path.relative(ROOT, file));
  }
}

function hud(tag) {
  return `<div style="position:relative;width:1080px;height:1920px">
    <div style="position:absolute;left:64px;top:232px;height:64px;padding:0 18px;display:flex;align-items:center;background:${C.ink};color:${C.card};font:400 34px/1 Anton;letter-spacing:.03em">${BRAND.brand.toUpperCase()}</div>
    ${tag ? `<div style="position:absolute;right:150px;top:240px;height:48px;padding:0 16px;display:flex;align-items:center;border:3px solid ${C.ink};color:${C.ink};font:600 20px/1 'IBM Plex Mono';letter-spacing:.12em;white-space:nowrap">● ${tag}</div>` : ""}
    <div style="position:absolute;left:987px;top:317px;width:26px;height:26px;opacity:.6">${MARK}</div>
    <div style="position:absolute;left:37px;top:1517px;width:26px;height:26px;opacity:.6">${MARK}</div>
  </div>`;
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  if (process.argv[2] === "logo") {
    await logoPngs(page);
    await browser.close();
    return;
  }

  // 1. Style frames (brand/assets/style-frames/) are stills of the pilot from tools/build_reel.py --stills.

  // 2. Header overlay (transparent) for every episode, plus a base without a tag
  await shot(page, hud(""), out("brand", "assets", "overlays", "hud-base.png"), { width: 1080, height: 1920, transparent: true });
  const episodes = path.join(ROOT, "episodes");
  for (const dir of fs.existsSync(episodes) ? fs.readdirSync(episodes) : []) {
    const f = path.join(episodes, dir, "episode.json");
    if (!fs.existsSync(f)) continue;
    const ep = JSON.parse(fs.readFileSync(f, "utf8"));
    await shot(page, hud(ep.tag), out("episodes", dir, "assets", "hud-overlay.png"), { width: 1080, height: 1920, transparent: true });
  }

  // 3. Blank caption strip (transparent), 900 px wide with torn edges and a shadow
  await shot(page, `<div style="padding:30px;width:960px;height:260px;box-sizing:border-box"><div style="filter:drop-shadow(0 6px 10px rgba(30,24,16,.28))"><div style="width:900px;height:200px;background:${C.caption_strip};clip-path:${tornPolygon(9)}"></div></div></div>`,
    out("brand", "assets", "overlays", "caption-strip.png"), { width: 960, height: 260, transparent: true });

  // 4. Safe-zone guide (transparent bands, use at 30–50% opacity in Canva)
  const z = BRAND.safe_zones_px;
  const band = (y0, y1, bg, label, fg) => `<div style="position:absolute;left:0;right:0;top:${y0}px;height:${y1 - y0}px;background:${bg};display:flex;align-items:center;justify-content:center;font:600 30px 'IBM Plex Mono';color:${fg};letter-spacing:.06em">${label}</div>`;
  await shot(page, `<div style="position:relative;width:1080px;height:1920px">
      ${band(z.instagram_top_bar[0], z.instagram_top_bar[1], "rgba(200,68,58,.35)", "KEEP CLEAR · INSTAGRAM TOP BAR", "#7a1f17")}
      ${band(z.header[0], z.header[1], "rgba(26,26,26,.35)", "HEADER BAND", "#111")}
      ${band(z.content[0], z.content[1], "rgba(245,238,48,.35)", "CARDS AND PHOTOS · y 380–1240", "#3d3a00")}
      ${band(z.caption_strip[0], z.caption_strip[1], "rgba(26,26,26,.18)", "CAPTION STRIP · y 1265–1520", "#111")}
      ${band(z.keep_clear_from_y, 1920, "rgba(200,68,58,.35)", "KEEP CLEAR · CAPTION, AUDIO, BUTTONS", "#7a1f17")}
      <div style="position:absolute;left:${z.right_button_rail.x_from}px;top:${z.right_button_rail.y_from}px;width:${1080 - z.right_button_rail.x_from}px;height:${1920 - z.right_button_rail.y_from}px;background:repeating-linear-gradient(135deg,rgba(200,68,58,.45) 0 10px,transparent 10px 20px)"></div>
    </div>`, out("brand", "assets", "guides", "safe-zones.png"), { width: 1080, height: 1920, transparent: true });

  // 5. Palette card
  const sw = Object.entries(C).map(([k, v]) => `<div style="display:flex;flex-direction:column;gap:10px"><div style="height:150px;background:${v};border:2px solid rgba(0,0,0,.15)"></div><div style="font:600 22px 'IBM Plex Mono';color:${C.ink}">${k.replace(/_/g, " ").toUpperCase()}</div><div style="font:500 22px 'IBM Plex Mono';color:#555">${v}</div></div>`).join("");
  await shot(page, `<div style="width:1080px;height:720px;box-sizing:border-box;padding:56px;background:${C.paper}"><div style="font:400 64px Anton;color:${C.ink};margin-bottom:34px">${BRAND.brand.toUpperCase()} PAPER STYLE · COLOURS</div><div style="display:grid;grid-template-columns:repeat(4,1fr);gap:28px">${sw}</div></div>`,
    out("brand", "assets", "palette.png"), { width: 1080, height: 720 });

  // 6. Type specimen
  await shot(page, `<div style="width:1080px;height:1080px;box-sizing:border-box;padding:64px;background:${C.paper};display:flex;flex-direction:column;gap:46px;color:${C.ink}">
      <div><div style="font:600 22px 'IBM Plex Mono';letter-spacing:.14em;color:#555">NUMBERS AND HEADLINES · ANTON</div><div style="font:400 150px/1 Anton">₹2,40,000</div></div>
      <div><div style="font:600 22px 'IBM Plex Mono';letter-spacing:.14em;color:#555">LABELS · IBM PLEX MONO SEMIBOLD</div><div style="display:inline-block;margin-top:12px;background:${C.ink};color:${C.card};font:600 30px 'IBM Plex Mono';letter-spacing:.14em;padding:10px 14px">CLAIM SE PEHLE</div></div>
      <div><div style="font:600 22px 'IBM Plex Mono';letter-spacing:.14em;color:#555">CAPTIONS · ARCHIVO EXTRABOLD</div><div style="font:800 54px/1.2 Archivo;margin-top:10px"><span style="background:${C.lemon};padding:0 8px">Claim reject?</span> Pehle KYC. <span style="color:${C.pencil}">Phir form.</span></div></div>
      <div style="display:flex;gap:70px;align-items:flex-end"><div><div style="font:600 22px 'IBM Plex Mono';letter-spacing:.14em;color:#555">NOTES · CAVEAT</div><div style="font:700 72px Caveat;color:${C.stamp_red}">employer se poochho</div></div>
      <div><div style="font:600 22px 'IBM Plex Mono';letter-spacing:.14em;color:#555">PLAN CARD · COURIER PRIME</div><div style="font:400 40px 'Courier Prime'">Bank KYC verified.</div></div></div>
    </div>`, out("brand", "assets", "type-specimen.png"), { width: 1080, height: 1080 });

  // 7. Marks
  fs.writeFileSync(out("brand", "assets", "marks", "crosshair.svg"), MARK + "\n");
  fs.writeFileSync(out("brand", "assets", "marks", "loop-scribble.svg"), LOOP + "\n");
  console.log("wrote brand/assets/marks/crosshair.svg, loop-scribble.svg");
  await shot(page, `<div style="width:256px;height:256px">${MARK}</div>`, out("brand", "assets", "marks", "crosshair.png"), { width: 256, height: 256, transparent: true });
  await shot(page, `<div style="width:1190px;height:140px">${LOOP}</div>`, out("brand", "assets", "marks", "loop-scribble.png"), { width: 1190, height: 140, transparent: true });

  // 8. Logo PNGs
  await logoPngs(page);

  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
