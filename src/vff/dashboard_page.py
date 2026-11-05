"""The dashboard's HTML. `PAGE` takes the JSON data at __DATA__; `REDIRECT` is left at the page's old address."""

REDIRECT = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Dashboard moved</title>
<meta http-equiv="refresh" content="0; url=__URL__"></head>
<body style="font-family:-apple-system,Helvetica,Arial,sans-serif;padding:40px">The dashboard moved to
<a href="__URL__">data_tracker/dashboard.html</a>.</body></html>
"""

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Voice Form Filler</title>
<style>
:root {
  color-scheme: light;
  --surface: #f4f3ef; --card: #ffffff; --side: #ffffff; --line: #e4e2dc; --grid: #ecebe6; --soft: #f1f0ec;
  --text: #16161a; --text-2: #55544f; --muted: #8b8984;
  --s1: #2a78d6; --s2: #eb6834; --s3: #1baf7a; --s4: #eda100; --s5: #e87ba4; --s6: #008300; --s7: #6250d6; --s8: #e34948;
  --good: #0ca30c; --warn: #fab219; --warn-ink: #8a5a00; --critical: #d03b3b;
  --fs: 15px; --radius: 14px; --shadow: 0 1px 2px rgba(0,0,0,.04), 0 6px 20px rgba(0,0,0,.05);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface: #151515; --card: #202020; --side: #1b1b1b; --line: #33322f; --grid: #2c2b29; --soft: #2a2a28;
    --text: #f0efec; --text-2: #c3c2b7; --muted: #8f8d86; --warn-ink: #fab219;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #d55181; --s6: #008300; --s7: #9085e9; --s8: #e66767;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 6px 20px rgba(0,0,0,.25);
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: #151515; --card: #202020; --side: #1b1b1b; --line: #33322f; --grid: #2c2b29; --soft: #2a2a28;
  --text: #f0efec; --text-2: #c3c2b7; --muted: #8f8d86; --warn-ink: #fab219;
  --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --s5: #d55181; --s6: #008300; --s7: #9085e9; --s8: #e66767;
  --shadow: 0 1px 2px rgba(0,0,0,.3), 0 6px 20px rgba(0,0,0,.25);
}
:root[data-size="big"] { --fs: 18px; }
* { box-sizing: border-box; }
html { font-size: var(--fs); }
body { margin: 0; background: var(--surface); color: var(--text); font: 1rem/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
a { color: var(--s1); }
.app { display: grid; grid-template-columns: 232px 1fr; min-height: 100vh; }
aside { background: var(--side); border-right: 1px solid var(--line); padding: 22px 14px; position: sticky; top: 0; height: 100vh; display: flex; flex-direction: column; }
.brand { font-weight: 700; font-size: 1.15rem; letter-spacing: -.01em; padding: 0 10px 6px; display: flex; align-items: center; gap: 10px; }
.brand .logo { width: 30px; height: 30px; border-radius: 9px; background: var(--s1); display: grid; place-items: center; color: #fff; font-size: 15px; }
.brand small { display: block; font-size: .72rem; font-weight: 500; color: var(--muted); letter-spacing: .04em; text-transform: uppercase; }
nav { display: flex; flex-direction: column; gap: 2px; margin-top: 16px; }
nav button { font: inherit; font-size: .95rem; text-align: left; display: flex; align-items: center; gap: 10px; padding: 9px 12px; border: 0; border-radius: 10px; background: none; color: var(--text-2); cursor: pointer; }
nav button:hover { background: var(--soft); color: var(--text); }
nav button[aria-selected="true"] { background: color-mix(in srgb, var(--s1) 12%, transparent); color: var(--text); font-weight: 600; }
nav button .ic { width: 20px; text-align: center; opacity: .85; }
nav button .count { margin-left: auto; min-width: 20px; padding: 0 6px; border-radius: 10px; font-size: .75rem; text-align: center;
                    background: color-mix(in srgb, var(--critical) 16%, transparent); color: var(--critical); }
nav button .count:empty { display: none; }
nav .group { font-size: .7rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); padding: 14px 12px 4px; }
aside .foot { margin-top: auto; padding: 10px 12px 0; font-size: .78rem; color: var(--muted); border-top: 1px solid var(--line); }
.live { display: inline-flex; align-items: center; gap: 6px; }
.live i { width: 8px; height: 8px; border-radius: 50%; background: var(--good); box-shadow: 0 0 0 3px color-mix(in srgb, var(--good) 25%, transparent); }
.content { padding: 22px 32px 64px; min-width: 0; }
.bar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; margin-bottom: 18px; }
.bar h1 { font-size: 1.5rem; margin: 0; letter-spacing: -.01em; }
.bar .sub { color: var(--muted); font-size: .85rem; width: 100%; margin-top: -6px; }
.tools { margin-left: auto; display: flex; flex-wrap: wrap; gap: 8px; }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; overflow: hidden; background: var(--card); }
.seg button { font: inherit; font-size: .78rem; padding: 5px 12px; border: 0; background: none; color: var(--text-2); cursor: pointer; }
.seg button[aria-pressed="true"] { background: var(--text); color: var(--card); }
h2 { font-size: 1.1rem; margin: 26px 0 12px; }
h2:first-child { margin-top: 0; }
p { margin: 0 0 10px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 20px 22px; box-shadow: var(--shadow); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 14px; }
.tile { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 16px 18px; box-shadow: var(--shadow); }
.tile .k { color: var(--text-2); font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; }
.tile .v { font-size: 2.1rem; font-weight: 700; line-height: 1.15; margin: 4px 0 2px; font-variant-numeric: tabular-nums; }
.tile .d { color: var(--muted); font-size: .85rem; }
.tile.good .v { color: var(--good); } .tile.bad .v { color: var(--critical); }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
.fcard { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px 20px; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 8px; }
.fcard .title { font-weight: 600; line-height: 1.3; }
.fcard .score { font-size: 2rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.1; }
.fcard .score small { font-size: .88rem; font-weight: 500; color: var(--text-2); }
.say { display: flex; flex-wrap: wrap; gap: 5px; }
.say span { font-size: .78rem; background: var(--soft); border: 1px solid var(--line); border-radius: 999px; padding: 2px 9px; color: var(--text-2); }
.foot { font-size: .8rem; color: var(--muted); }
.bar-h { height: 10px; display: flex; gap: 2px; background: var(--grid); border-radius: 5px; overflow: hidden; }
.bar-h i { display: block; height: 100%; }
.bar-h .r { background: var(--good); } .bar-h .w { background: var(--critical); } .bar-h .l { background: var(--warn); }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; font-weight: 600; font-size: .85rem; white-space: nowrap; }
.pill.good { background: color-mix(in srgb, var(--good) 15%, transparent); color: var(--good); }
.pill.warn { background: color-mix(in srgb, var(--warn) 24%, transparent); color: var(--warn-ink); }
.pill.critical { background: color-mix(in srgb, var(--critical) 14%, transparent); color: var(--critical); }
.pill.neutral { background: var(--soft); color: var(--text-2); }
.report { display: grid; grid-template-columns: 150px 1fr; gap: 6px 18px; padding: 14px 0; border-top: 1px solid var(--line); }
.report:first-of-type { border-top: 0; padding-top: 0; }
.report .when { font-weight: 600; }
.report .src { font-size: .8rem; color: var(--muted); }
.report .story { color: var(--text-2); font-size: .92rem; }
.report .forms { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; }
.chip { display: inline-flex; align-items: center; gap: 8px; border: 1px solid var(--line); background: var(--soft); border-radius: 10px; padding: 6px 10px; font-size: .85rem; }
.chip .n { color: var(--muted); }
.chip a { font-weight: 600; text-decoration: none; }
.btn { display: inline-flex; align-items: center; gap: 8px; font: inherit; font-size: .9rem; font-weight: 600; padding: 8px 14px; border-radius: 10px; border: 1px solid var(--line); background: var(--card); color: var(--text); text-decoration: none; cursor: pointer; box-shadow: var(--shadow); }
.btn:hover { background: var(--soft); }
.btn.primary { background: var(--s1); border-color: var(--s1); color: #fff; }
.btn.primary:hover { filter: brightness(1.08); background: var(--s1); }
.btn .ic { font-size: 1.1rem; }
.btn.stop { background: var(--critical); border-color: var(--critical); color: #fff; }
.btn.stop:hover { filter: brightness(1.08); background: var(--critical); }
.btn:disabled { opacity: .6; cursor: wait; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
#runCard { margin-bottom: 18px; }
.actions .hint { font-size: .85rem; color: var(--muted); }
.progress { margin-bottom: 18px; display: none; }
.progress.on { display: block; }
.progress .ptop { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.progress .pmsg { font-weight: 600; }
.progress .ptime { color: var(--muted); font-size: .85rem; white-space: nowrap; }
.pbar { height: 10px; border-radius: 999px; background: var(--soft); overflow: hidden; margin: 12px 0 10px; }
.pbar i { display: block; height: 100%; width: 0; border-radius: 999px; background: var(--s1); transition: width .6s ease; }
.progress.done .pbar i { background: var(--good); } .progress.stopped .pbar i { background: var(--critical); }
.progress.stalled .pbar i { background: var(--warn); }
.steps { display: flex; gap: 6px; flex-wrap: wrap; list-style: none; margin: 0; padding: 0; font-size: .82rem; color: var(--muted); }
.steps li { display: flex; align-items: center; gap: 6px; }
.steps li::before { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--line); }
.steps li.past { color: var(--text-2); } .steps li.past::before { background: var(--good); }
.steps li.now { color: var(--text); font-weight: 600; } .steps li.now::before { background: var(--s1); box-shadow: 0 0 0 3px color-mix(in srgb, var(--s1) 25%, transparent); }
.steps li + li { margin-left: 6px; }
.picker { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line); }
.picker .q { font-weight: 600; margin-bottom: 8px; }
.picker .chips { display: flex; flex-wrap: wrap; gap: 8px; }
.picker .file { margin: 0 0 10px; display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.picker .file input { font: inherit; font-size: .9rem; }
.console { margin-bottom: 18px; display: none; padding: 14px 16px; }
.console.on { display: block; }
.console .chead { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
.console pre { margin: 0; max-height: 42vh; overflow: auto; font-size: .82rem; line-height: 1.45; white-space: pre-wrap; word-break: break-word; background: var(--soft); border-radius: 8px; padding: 10px 12px; }
.console .heard { margin-top: 10px; padding: 10px 12px; border-left: 3px solid var(--s1); background: color-mix(in srgb, var(--s1) 8%, transparent); border-radius: 0 8px 8px 0; }
.viewer { margin-bottom: 14px; display: none; padding: 14px 16px; }
.viewer.on { display: block; }
.viewer .vhead { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
.viewer iframe { width: 100%; height: 78vh; border: 1px solid var(--line); border-radius: 8px; background: #fff; }
.btn.small { padding: 5px 10px; font-size: .82rem; }
.chip a.view { cursor: pointer; }
.toast { position: fixed; left: 50%; bottom: 28px; transform: translateX(-50%); background: var(--text); color: var(--card); padding: 10px 18px; border-radius: 999px; font-size: .9rem; box-shadow: var(--shadow); opacity: 0; transition: opacity .2s; pointer-events: none; z-index: 3; max-width: 90vw; }
.toast.on { opacity: 1; }
.hero { display: grid; grid-template-columns: auto 1fr; gap: 10px 28px; align-items: center; }
.gauge { width: 136px; height: 136px; }
.gauge text { fill: var(--text); font-weight: 700; font-size: 30px; }
.gauge .sub { fill: var(--text-2); font-weight: 400; font-size: 11px; }
.lead { font-size: 1.2rem; line-height: 1.35; }
.lead b { font-variant-numeric: tabular-nums; }
.fix { border-left: 4px solid var(--critical); background: var(--soft); border-radius: 8px; padding: 12px 16px; margin-bottom: 10px; }
.fix b { display: block; margin-bottom: 3px; }
.fix .got { font-family: ui-monospace, Menlo, monospace; font-size: .88rem; }
.ok { border-left: 4px solid var(--good); background: var(--soft); border-radius: 8px; padding: 14px 16px; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: .88rem; color: var(--text-2); }
.legend span::before { content: ""; display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; background: var(--sw); }
.row { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; }
select { font: inherit; font-size: .88rem; padding: 5px 9px; background: var(--card); color: var(--text); border: 1px solid var(--line); border-radius: 8px; }
svg.chart { width: 100%; height: auto; display: block; overflow: visible; }
.axis text { fill: var(--muted); font-size: 11px; }
.axis line { stroke: var(--grid); }
.tip { position: fixed; pointer-events: none; background: var(--card); color: var(--text); border: 1px solid var(--line); border-radius: 8px; padding: 7px 10px; font-size: .88rem; box-shadow: var(--shadow); display: none; max-width: 320px; z-index: 2; }
table { width: 100%; border-collapse: collapse; font-size: .95rem; }
th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--text-2); font-weight: 600; font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.bars { display: grid; grid-template-columns: minmax(160px, 260px) 1fr auto; gap: 10px 14px; align-items: center; }
.bars .bar-h { height: 16px; }
.nums { font-size: .88rem; color: var(--text-2); white-space: nowrap; font-variant-numeric: tabular-nums; }
.test { margin-bottom: 18px; }
.test .name { font-weight: 600; font-size: 1.05rem; }
.test .when { color: var(--muted); font-size: .85rem; }
code { background: var(--soft); border: 1px solid var(--line); border-radius: 5px; padding: 1px 7px; font-size: .88rem; }
.steps li { margin-bottom: 8px; }
.howto { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
.howto .card h3 { margin: 0 0 8px; font-size: 1rem; }
.howto .card .cmd { display: block; font-family: ui-monospace, Menlo, monospace; font-size: .9rem; background: var(--soft); border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; margin: 8px 0; }
details summary { cursor: pointer; color: var(--text-2); font-size: .95rem; margin: 10px 0; }
.small { font-size: .85rem; color: var(--muted); }
.empty { color: var(--muted); padding: 28px 18px; text-align: center; }
.empty b { color: var(--text); display: block; margin-bottom: 4px; }
.panel { display: none; } .panel.on { display: block; }
@media (max-width: 820px) {
  .app { grid-template-columns: 1fr; }
  aside { position: static; height: auto; border-right: 0; border-bottom: 1px solid var(--line); padding: 14px; }
  nav { flex-direction: row; flex-wrap: wrap; } nav .group { display: none; } aside .foot { display: none; }
  .content { padding: 18px 16px 48px; }
  .hero { grid-template-columns: 1fr; } .bars { grid-template-columns: 1fr; } .report { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="app">
<aside>
  <div class="brand"><span class="logo">🎙</span><span>Voice Form Filler<small>Dashboard</small></span></div>
  <nav id="nav" role="tablist">
    <button data-tab="overview"><span class="ic">◧</span>Overview</button>
    <button data-tab="reports"><span class="ic">▤</span>Reports<span class="count neutral" id="reportCount"></span></button>
    <button data-tab="forms"><span class="ic">▣</span>Forms</button>
    <div class="group">Accuracy</div>
    <button data-tab="accuracy"><span class="ic">◉</span>Score &amp; fixes<span class="count" id="fixCount"></span></button>
    <button data-tab="tests"><span class="ic">☑</span>Tests</button>
    <button data-tab="trend"><span class="ic">↗</span>Over time</button>
    <div class="group">Help</div>
    <button data-tab="howto"><span class="ic">?</span>How to use</button>
  </nav>
  <div class="foot"><span class="live"><i></i>updates by itself</span><br><span id="stamp"></span></div>
</aside>

<div class="content">
  <div class="bar">
    <h1 id="title">Overview</h1>
    <div class="tools">
      <button class="btn primary" id="recordTop" hidden><span class="ic">🎙</span>Record a report</button>
      <div class="seg" id="theme"><button data-v="auto">Auto</button><button data-v="light">Light</button><button data-v="dark">Dark</button></div>
      <div class="seg" id="size"><button data-v="normal">Normal text</button><button data-v="big">Big text</button></div>
    </div>
    <div class="sub" id="subtitle"></div>
  </div>

  <div class="card progress" id="progress" aria-live="polite">
    <div class="ptop"><span class="pmsg" id="pmsg"></span><span class="ptime" id="ptime"></span></div>
    <button class="btn stop" id="pstop" hidden title="Ends the run now and throws away anything it saved">■ Stop — save nothing</button>
    <div class="pbar"><i id="pfill"></i></div>
    <ol class="steps" id="psteps"></ol>
  </div>
  <div class="card console" id="console">
    <div class="chead"><b id="ctitle"></b><span><button class="btn small stop" id="cstop">■ Stop</button> <button class="btn small" id="cclose">Close</button></span></div>
    <pre id="clines"></pre>
    <div class="heard" id="cheard" hidden></div>
  </div>

  <section class="panel" data-panel="overview">
    <div class="card" id="runCard"><div class="actions" id="actions"></div><div class="picker" id="picker" hidden></div></div>
    <div class="tiles" id="tiles"></div>
    <h2>Latest reports</h2>
    <div class="card" id="latestReports"></div>
    <h2>The forms it fills</h2>
    <div class="grid" id="formCards"></div>
  </section>

  <section class="panel" data-panel="reports">
    <div class="card viewer" id="viewer">
      <div class="vhead"><b id="viewerTitle"></b><span><a class="btn small" id="viewerOpen" target="_blank">Open in a new tab</a> <button class="btn small" id="viewerClose">Close</button></span></div>
      <iframe id="viewerFrame" title="The filled form"></iframe>
    </div>
    <div class="card" id="reportList"></div>
  </section>

  <section class="panel" data-panel="forms">
    <div class="card" style="margin-bottom:14px">
      <b>Pick a form by saying its name.</b> Start the recording with <code>OSHA form 301</code> or <code>Mishap</code> and only that form is filled, with only its questions asked. Say none of them and every form that fits the story is filled.
    </div>
    <div class="grid" id="formCards2"></div>
  </section>

  <section class="panel" data-panel="accuracy">
    <div class="card hero" id="hero"></div>
    <h2>What to fix next</h2>
    <div class="card" id="fix"></div>
  </section>

  <section class="panel" data-panel="tests">
    <div class="card" id="testList"></div>
  </section>

  <section class="panel" data-panel="trend">
    <div class="card">
      <div class="row" style="margin-bottom:10px">
        <div class="legend" id="legend"></div>
        <label class="small" style="margin-left:auto">Show <select id="modeSel"><option value="all">all tests</option><option value="voice">spoken tests only</option><option value="typed">typed tests only</option></select></label>
      </div>
      <div id="trendChart"></div>
      <details><summary>Show as a table</summary><div id="trendTable"></div></details>
    </div>
    <h2>All test runs</h2>
    <div class="card" id="runList"></div>
  </section>

  <section class="panel" data-panel="howto">
    <div class="howto">
      <div class="card"><h3>1 · File a report by talking</h3><span class="cmd">uv run record</span>
        Press Enter or say <b>"start recording"</b>, say which form (or nothing), tell what happened in order, say <b>"stop recording"</b>. The forms are filled, saved, added to the Excel file and opened.</div>
      <div class="card"><h3>2 · File a report from a voice memo or notes</h3><span class="cmd">uv run make-report --input memo.m4a</span>
        Works with audio, video (sound only) or a text file. Add <code>--forms osha_301</code> to force a form.</div>
      <div class="card"><h3>3 · Check the accuracy</h3><span class="cmd">uv run live-test</span>
        Read one of the test scripts out loud; every box is checked against the right answers. <code>--typed</code> skips the microphone.</div>
      <div class="card"><h3>4 · Bring in old filled PDFs</h3><span class="cmd">uv run add-old-pdfs ~/old_forms</span>
        Copies them in and rebuilds the Excel file so every report, old and new, is in one place.</div>
      <div class="card"><h3>This page</h3><span class="cmd">uv run dashboard</span>
        Starts the page with its buttons. Each button runs its step right here — you talk, the page shows what was heard and the filled form; no other window opens. It rebuilds on every load, reloads every 30 seconds (not during a run) and stays where you were. Nothing leaves this computer — it runs on this Mac only.</div>
    </div>
  </section>
</div>
</div>
<div class="tip" id="tip"></div>
<div class="toast" id="toast"></div>
<script>
const DATA = __DATA__;
const TOKEN = "__TOKEN__";
const CAN_RUN = TOKEN !== "" && location.protocol.startsWith("http");
const SERIES = ["--s1","--s2","--s3","--s4","--s5","--s6","--s7","--s8"];
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const pct = (r, s) => s ? Math.round(100 * r / s) : null;
const modeWord = m => m === "voice" ? "spoken" : "typed";
const niceName = s => s.title.split(" — ")[0];
const fileUrl = p => "file://" + p.split("/").map(encodeURIComponent).join("/");
const pdfUrl = (r, name) => CAN_RUN ? `/records/${encodeURIComponent(r.id)}/${encodeURIComponent(name)}` : fileUrl(`${DATA.records_dir}/${r.id}/${name}`);
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const tip = document.getElementById("tip");
const showTip = (e, h) => { tip.innerHTML = h; tip.style.display = "block"; moveTip(e); };
const moveTip = e => { tip.style.left = Math.min(e.clientX + 14, innerWidth - 330) + "px"; tip.style.top = (e.clientY + 14) + "px"; };
const hideTip = () => { tip.style.display = "none"; };
const remember = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
const recall = k => { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } };
const forget = k => { try { localStorage.removeItem(k); } catch (e) {} };

function segment(id, attr, fallback) {
  const el = document.getElementById(id);
  const apply = v => { if (v === "auto" || v === "normal") document.documentElement.removeAttribute(attr); else document.documentElement.setAttribute(attr, v);
                       el.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.v === v)); };
  el.querySelectorAll("button").forEach(b => b.addEventListener("click", () => { apply(b.dataset.v); remember("vff-" + id, b.dataset.v); }));
  apply(recall("vff-" + id) || fallback);
}
segment("theme", "data-theme", "auto");
segment("size", "data-size", "normal");

// ---- test data
const points = [];
DATA.runs.forEach(run => run.scripts.forEach(s => points.push({run: run.started, folder: run.folder, ...s})));
const scripts = [...new Set(points.map(p => p.script))].sort();
const nameOf = {}; points.forEach(p => { nameOf[p.script] = niceName(p); });
const colorOf = Object.fromEntries(scripts.map((s, i) => [s, `var(${SERIES[i % SERIES.length]})`]));
const latest = {}; points.forEach(p => { latest[p.script] = p; });
const latestPts = scripts.map(s => latest[s]);
const totR = latestPts.reduce((a, p) => a + p.right, 0), totS = latestPts.reduce((a, p) => a + p.scored, 0);
const wrongNow = totS - totR, P = pct(totR, totS);
const lastRun = DATA.runs[DATA.runs.length - 1];
const fixes = [];
latestPts.forEach(p => p.forms.forEach(f => {
  if (!f.filled) fixes.push({p, f, missing: true});
  f.boxes.filter(b => b.verdict === "✗").forEach(b => fixes.push({p, f, b}));
}));
const lastByForm = {};
points.forEach(p => p.forms.forEach(f => { lastByForm[f.title] = {p, f}; }));
const reports = DATA.reports;
const formsFilled = reports.reduce((a, r) => a + r.forms.length, 0);

document.getElementById("stamp").textContent = CAN_RUN ? `live · rebuilt ${DATA.generated}` : `page made ${DATA.generated}`;

// ---- the buttons: each one asks the dashboard server (this Mac only) to run a command
let toastTimer;
function toast(msg) { const t = document.getElementById("toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove("on"), 6000); }
const gone = () => toast("The dashboard isn't running any more. Start it again with: uv run dashboard");
function post(path, body) {
  return fetch(path, {method: "POST", headers: {"X-VFF-Token": TOKEN, "Content-Type": "application/json"}, body: JSON.stringify(body || {})})
    .then(r => r.json());
}
function run(name, choice, file) {
  post(`/run/${name}`, {choice: choice || "", file: file || ""}).then(j => { toast(j.message); if (j.ok && BUTTONS_WITH_OUTPUT.has(name)) openConsole(); })
    .catch(gone);
}
// a recording made elsewhere (a phone's voice memo): send the file to the server, then run on it
function runMemo(choice) {
  const file = document.getElementById("memoFile")?.files[0];
  if (!file) { toast("Pick the recording first (the file from your phone)."); return; }
  toast(`Sending ${file.name}…`);
  fetch("/upload", {method: "POST", headers: {"X-VFF-Token": TOKEN, "X-VFF-Name": file.name, "Content-Type": "application/octet-stream"}, body: file})
    .then(r => r.json()).then(j => { if (!j.ok) { toast(j.message); return; } run("memo", choice, j.file); })
    .catch(gone);
}
const BUTTONS = [["record", "🎙", "Record a report", "primary"], ["memo", "📱", "Use a recording from your phone"], ["live-test", "🗣", "Spoken test"],
                 ["typed-test", "⌨", "Typed test (no microphone)"], ["excel", "📊", "Open the Excel tracker"], ["records", "📁", "Open the records folder"]];
const BUTTONS_WITH_OUTPUT = new Set(["record", "memo", "live-test", "typed-test"]);
const FORM_CHIPS = [...[...DATA.forms].sort((a, b) => (a.status !== "approved") - (b.status !== "approved")).map(f => [f.id, f.title]), ["any", "Any — every form that fits the story"]];
// what each button asks before it starts: the form to fill, or the script to read
const PICKS = {
  record: {q: "Which form?", chips: [...FORM_CHIPS, ["voice", `🎤 Say it — ${DATA.forms.map(f => `"${f.say[0]}"`).join(" or ")} starts the recording`]]},
  memo: {q: "Pick the recording (get it onto this computer first — AirDrop, email it to yourself, or a cable), then click the form.", file: true, chips: FORM_CHIPS},
  "live-test": {q: "Which script will you read?", chips: DATA.scripts.map(s => [String(s.n), `${s.n} · ${s.title}`])},
  "typed-test": {q: "Which script?", chips: [...DATA.scripts.map(s => [String(s.n), `${s.n} · ${s.title}`]), ["all", "All of them"]]},
};
document.getElementById("actions").innerHTML = CAN_RUN
  ? BUTTONS.map(([n, ic, label, cls]) => `<button class="btn ${cls || ""}" data-pick="${n}"><span class="ic">${ic}</span>${esc(label)}</button>`).join("")
  : `<span class="hint">To get click-to-run buttons here, start the page with <code>uv run dashboard</code>.</span>`;
const picker = document.getElementById("picker");
function showPicker(name) {
  const pick = PICKS[name];
  if (!pick) { run(name); return; }
  picker.hidden = false;
  const fileBox = pick.file ? `<p class="file"><input type="file" id="memoFile" accept="${DATA.file_types.join(",")}"> <span class="hint">voice memo, video or text file — it stays on this computer</span></p>` : "";
  picker.innerHTML = `<div class="q">${esc(pick.q)}</div>${fileBox}<div class="chips">${pick.chips.map(([v, label]) => `<button class="btn small" data-choice="${esc(v)}">${esc(label)}</button>`).join("")}</div>`;
  picker.querySelectorAll("[data-choice]").forEach(b => b.addEventListener("click", () => {
    if (pick.file) { runMemo(b.dataset.choice); return; }
    run(name, b.dataset.choice);
    if (name !== "record") showPicker("record");
  }));
  picker.querySelector("[data-choice='voice']")?.classList.add("primary");
}
document.querySelectorAll("[data-pick]").forEach(b => b.addEventListener("click", () => showPicker(b.dataset.pick)));
if (CAN_RUN) showPicker("record");  // the form choice is right there when the page opens
const recordTop = document.getElementById("recordTop");
recordTop.addEventListener("click", () => { openTab("overview"); showPicker("record"); document.getElementById("runCard").scrollIntoView({behavior: "smooth"}); });

// ---- the output of the running command, shown on the page instead of a Terminal window
const consoleCard = document.getElementById("console"), clines = document.getElementById("clines");
let shownLines = 0, consoleRun = "";
function openConsole() { consoleCard.classList.add("on"); }
document.getElementById("cclose").addEventListener("click", () => consoleCard.classList.remove("on"));
// the kill switch: ends the run and throws away what it saved; the form choice comes back so it can be redone
const stopButtons = [document.getElementById("pstop"), document.getElementById("cstop")];
function stopRun() {
  stopButtons.forEach(b => b.disabled = true);
  post("/stop").then(j => { toast(j.message); showPicker("record"); }).catch(gone)
    .finally(() => stopButtons.forEach(b => b.disabled = false));
}
stopButtons.forEach(b => b.addEventListener("click", stopRun));
function drawOutput(o) {
  if (!o.title) return;
  const key = `${o.title}@${o.started}`;
  if (key !== consoleRun) { consoleRun = key; shownLines = 0; clines.textContent = ""; document.getElementById("cheard").hidden = true; openConsole(); }
  if (o.total < shownLines) { shownLines = 0; clines.textContent = ""; }
  if (o.lines.length) {
    clines.textContent += (clines.textContent ? "\n" : "") + o.lines.join("\n");
    shownLines = o.total;
    clines.scrollTop = clines.scrollHeight;
    const heard = clines.textContent.match(/What I heard:\n\s*(.+)/);
    if (heard) { const h = document.getElementById("cheard"); h.hidden = false; h.innerHTML = `<b>What it heard:</b> ${esc(heard[1])}`; }
  }
  document.getElementById("ctitle").textContent = o.running ? `${o.title} — running since ${o.started}` : `${o.title} — ${o.exit ? "stopped" : "finished"}`;
  document.getElementById("cstop").hidden = !o.running;
}
document.getElementById("reportCount").textContent = reports.length || "";
document.getElementById("fixCount").textContent = fixes.length || "";

// ---- overview tiles
document.getElementById("tiles").innerHTML = [
  {k: "Reports filed", v: reports.length, d: reports.length ? `latest ${reports[0].created}` : "none yet — say uv run record"},
  {k: "Forms filled", v: formsFilled, d: reports.length ? `across ${plural(reports.length, "report")}` : "—"},
  {k: "Accuracy (latest tests)", v: P === null ? "—" : `${P}%`, d: totS ? `${totR} of ${totS} checked boxes right` : "no test yet", cls: P === null ? "" : wrongNow === 0 ? "good" : ""},
  {k: "Boxes to fix", v: totS ? wrongNow : "—", d: totS ? (wrongNow ? "see Score & fixes" : "nothing to fix") : "—", cls: totS ? (wrongNow ? "bad" : "good") : ""},
].map(t => `<div class="tile ${t.cls || ""}"><div class="k">${esc(t.k)}</div><div class="v">${esc(t.v)}</div><div class="d">${esc(t.d)}</div></div>`).join("");

// ---- reports
const reportRow = r => `<div class="report">
  <div><div class="when">${esc(r.created)}</div><div class="src">${esc(r.source)}</div></div>
  <div><div class="story">${r.story ? esc(r.story) + (r.story.length >= 180 ? "…" : "") : "<span class='small'>(no transcript)</span>"}</div>
    <div class="forms">${r.forms.length ? r.forms.map(f => `<span class="chip"><span>${esc(f.title)}</span><span class="n">${plural(f.filled, "box")}${f.to_check ? ` · ${f.to_check} to check` : ""}</span>${f.print_pdf ? `<a class="view" data-view="${esc(r.id)}/${esc(f.print_pdf)}" data-title="${esc(f.title)} — ${esc(r.created)}">View</a> <a href="${pdfUrl(r, f.print_pdf)}" target="_blank">Open PDF</a>` : ""}</span>`).join("")
      : `<span class="small">No form fit this story.</span>`}</div></div></div>`;
const noReports = `<div class="empty"><b>No report yet.</b>Say <code>uv run record</code> in the app folder and tell what happened. It shows up here.</div>`;
document.getElementById("latestReports").innerHTML = reports.length ? reports.slice(0, 3).map(reportRow).join("") + (reports.length > 3 ? `<p class="small" style="margin:12px 0 0">…and ${reports.length - 3} more under <b>Reports</b>.</p>` : "") : noReports;
document.getElementById("reportList").innerHTML = reports.length ? reports.map(reportRow).join("") : noReports;

// ---- form cards (overview + forms)
const formCards = DATA.forms.map(f => {
  const l = lastByForm[f.title];
  const say = f.say.map(w => `<span>“${esc(w)}”</span>`).join("");
  let score = `<div class="score">—<small> not tested yet</small></div>`, bar = "", foot = "";
  if (l) {
    const n = l.f.right + l.f.wrong, total = n + l.f.look || 1;
    const seg = (k, c) => k ? `<i class="${c}" style="width:${100 * k / total}%"></i>` : "";
    score = `<div class="score">${n ? `${pct(l.f.right, n)}%` : "—"}<small> · ${l.f.right} of ${n} right${l.f.look ? `, ${l.f.look} to read` : ""}</small></div>`;
    bar = `<div class="bar-h">${seg(l.f.right, "r")}${seg(l.f.wrong, "w")}${seg(l.f.look, "l")}</div>`;
    foot = `Last tested with “${esc(nameOf[l.p.script])}” · ${esc(l.p.run)}`;
  }
  const status = f.status === "approved" ? `<span class="pill good">✓ map approved</span>` : `<span class="pill warn">map in review</span>`;
  return `<div class="fcard"><div class="title">${esc(f.title)}</div>${score}${bar}<div class="say">${say}</div><div class="row" style="justify-content:space-between"><span class="foot">${foot}</span>${status}</div></div>`;
}).join("");
document.getElementById("formCards").innerHTML = formCards;
document.getElementById("formCards2").innerHTML = formCards;

// ---- accuracy: gauge + fixes
const hero = document.getElementById("hero");
if (!DATA.runs.length) hero.innerHTML = `<div></div><div class="lead">No test has been run yet. See <b>How to use</b>, step 3.</div>`;
else {
  const r = 56, c = 2 * Math.PI * r, color = wrongNow === 0 ? "var(--good)" : P >= 90 ? "var(--s1)" : "var(--warn)";
  hero.innerHTML = `<svg class="gauge" viewBox="0 0 136 136" role="img" aria-label="${P} percent of boxes right">
    <circle cx="68" cy="68" r="${r}" fill="none" stroke="var(--grid)" stroke-width="12"/>
    <circle cx="68" cy="68" r="${r}" fill="none" stroke="${color}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${c * P / 100} ${c}" transform="rotate(-90 68 68)"/>
    <text x="68" y="66" text-anchor="middle" dominant-baseline="middle">${P}%</text><text x="68" y="90" text-anchor="middle" class="sub">boxes right</text></svg>
    <div><div class="lead"><b>${totR}</b> of <b>${totS}</b> checked boxes are right in the latest run of each test.</div>
    <div class="small" style="margin-top:6px">${plural(latestPts.length, "test")} · ${plural(DATA.runs.length, "run")} · last ${esc(lastRun.started)}</div>
    <div style="margin-top:10px">${wrongNow === 0 ? `<span class="pill good">✓ Every checked box is right</span>` : `<span class="pill critical">✗ ${plural(wrongNow, "box")} to fix</span>`}</div></div>`;
}
document.getElementById("fix").innerHTML = !DATA.runs.length ? `<div class="empty"><b>Run a test first.</b><code>uv run live-test</code></div>`
  : fixes.length === 0 ? `<div class="ok">✓ Nothing to fix. Every checked box in the latest tests is right.</div>`
  : fixes.map(x => x.missing
      ? `<div class="fix"><b>${esc(nameOf[x.p.script])} test · ${esc(x.f.title)}</b>The form was not filled at all, but it should have been.</div>`
      : `<div class="fix"><b>${esc(nameOf[x.p.script])} test · ${esc(x.f.title)} · box "${esc(x.b.label)}"</b>
         <div>Should be: <span class="got">${x.b.expected ? esc(x.b.expected) : "(empty)"}</span></div>
         <div>The app wrote: <span class="got">${x.b.got ? esc(x.b.got) : "(empty)"}</span></div></div>`).join("");

// ---- tests
document.getElementById("testList").innerHTML = !latestPts.length ? `<div class="empty"><b>Run a test first.</b><code>uv run live-test</code></div>` : latestPts.map(p => {
  const rows = p.forms.map(f => {
    const total = f.right + f.wrong + f.look || 1;
    const seg = (n, c, w) => n ? `<i class="${c}" style="width:${100 * n / total}%" title="${n} ${w}"></i>` : "";
    const status = !f.filled ? `<span class="pill critical">✗ not filled</span>` : f.wrong === 0 ? `<span class="pill good">✓ all right</span>` : `<span class="pill critical">✗ ${f.wrong} wrong</span>`;
    return `<div>${esc(f.title)}</div><div class="bar-h">${seg(f.right, "r", "right")}${seg(f.wrong, "w", "wrong")}${seg(f.look, "l", "to read yourself")}</div><div class="nums">${f.right} right · ${f.wrong} wrong · ${f.look} to read &nbsp;${status}</div>`;
  }).join("");
  return `<div class="test"><div class="row"><span class="name">${esc(nameOf[p.script])}</span><span class="when">${esc(p.title)} · ${esc(p.run)} · ${modeWord(p.mode)} test</span></div><div class="bars">${rows}</div></div>`;
}).join("") + `<p class="small"><span class="pill good">✓</span> right &nbsp; <span class="pill critical">✗</span> wrong &nbsp; <span class="pill warn">👁</span> a written answer — read it yourself, it can't be matched word for word</p>`;

// ---- trend
document.getElementById("legend").innerHTML = scripts.map(s => `<span style="--sw:${colorOf[s]}">${esc(nameOf[s])}</span>`).join("");
function drawTrend(mode) {
  const pts = points.filter(p => (mode === "all" || p.mode === mode) && p.scored);
  const runs = [...new Set(pts.map(p => p.run))];
  const host = document.getElementById("trendChart");
  if (!runs.length) { host.innerHTML = `<div class="empty">No ${mode === "all" ? "" : modeWord(mode) + " "}tests yet.</div>`; document.getElementById("trendTable").innerHTML = ""; return; }
  const W = 1000, H = 300, L = 44, R = 130, T = 16, B = 46;
  const x = i => runs.length === 1 ? L + (W - L - R) / 2 : L + (W - L - R) * i / (runs.length - 1);
  const y = v => T + (H - T - B) * (1 - v / 100);
  let svg = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Percent of boxes right per test, by run"><g class="axis">`;
  [0, 25, 50, 75, 100].forEach(v => { svg += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${v}%</text>`; });
  const step = Math.ceil(runs.length / 9);
  runs.forEach((r, i) => { if (i % step === 0 || i === runs.length - 1) svg += `<text x="${x(i)}" y="${H - B + 18}" text-anchor="middle">${esc(r.slice(5))}</text>`; });
  svg += `</g>`;
  const labels = [];
  scripts.forEach(s => {
    const mine = pts.filter(p => p.script === s);
    if (!mine.length) return;
    const path = mine.map(p => `${x(runs.indexOf(p.run))},${y(pct(p.right, p.scored))}`);
    if (path.length > 1) svg += `<polyline fill="none" stroke="${colorOf[s]}" stroke-width="2.5" stroke-linejoin="round" points="${path.join(" ")}"/>`;
    mine.forEach(p => { svg += `<circle cx="${x(runs.indexOf(p.run))}" cy="${y(pct(p.right, p.scored))}" r="${p.mode === "voice" ? 7 : 5}" fill="${colorOf[s]}" stroke="var(--card)" stroke-width="2" data-tip="${esc(`<b>${nameOf[s]}</b> · ${p.run} · ${modeWord(p.mode)} test<br>${p.right} of ${p.scored} right (${pct(p.right, p.scored)}%)`)}"/>`; });
    const last = mine[mine.length - 1];
    const ended = runs.indexOf(last.run) === runs.length - 1, lx = x(runs.indexOf(last.run)), ly = y(pct(last.right, last.scored));
    labels.push({x: ended ? lx + 11 : lx, y: ended ? ly + 4 : ly - 12, anchor: ended ? "start" : "middle", text: `${nameOf[s]} ${pct(last.right, last.scored)}%`});
  });
  labels.sort((a, b) => a.y - b.y || a.x - b.x);
  for (let i = 1; i < labels.length; i++) { const prev = labels[i - 1]; if (Math.abs(labels[i].x - prev.x) < 140 && labels[i].y - prev.y < 14) labels[i].y = prev.y + 14; }
  labels.forEach(l => { svg += `<text x="${l.x}" y="${l.y}" text-anchor="${l.anchor}" font-size="12" fill="var(--text-2)" paint-order="stroke" stroke="var(--card)" stroke-width="3">${esc(l.text)}</text>`; });
  svg += `</svg><p class="small">Big dots = spoken tests, small dots = typed tests. Point at a dot to see the count.</p>`;
  host.innerHTML = svg;
  host.querySelectorAll("[data-tip]").forEach(el => { el.addEventListener("mouseenter", e => showTip(e, el.dataset.tip)); el.addEventListener("mousemove", moveTip); el.addEventListener("mouseleave", hideTip); });
  document.getElementById("trendTable").innerHTML = `<table><thead><tr><th>Run</th>${scripts.map(s => `<th>${esc(nameOf[s])}</th>`).join("")}</tr></thead><tbody>` +
    runs.map(r => `<tr><td>${esc(r)}</td>${scripts.map(s => { const p = pts.find(q => q.run === r && q.script === s); return `<td class="num">${p ? `${p.right} / ${p.scored} (${modeWord(p.mode)})` : "—"}</td>`; }).join("")}</tr>`).join("") + `</tbody></table>`;
}
document.getElementById("modeSel").addEventListener("change", e => drawTrend(e.target.value));
drawTrend("all");
document.getElementById("runList").innerHTML = DATA.runs.length
  ? `<table><thead><tr><th>When</th><th>Tests</th><th class="num">Right</th><th class="num">Checked</th><th class="num">%</th><th>Folder</th></tr></thead><tbody>` +
    [...DATA.runs].reverse().map(r => { const R = r.scripts.reduce((a, s) => a + s.right, 0), S = r.scripts.reduce((a, s) => a + s.scored, 0);
      return `<tr><td>${esc(r.started)}</td><td>${esc(r.scripts.map(s => `${nameOf[s.script]} (${modeWord(s.mode)})`).join(", "))}</td><td class="num">${R}</td><td class="num">${S}</td><td class="num">${S ? pct(R, S) + "%" : "—"}</td><td class="small">${esc(r.folder)}</td></tr>`; }).join("") + `</tbody></table>`
  : `<div class="empty">No tests yet.</div>`;

// ---- the form viewer: a filled PDF shown on the Reports page (remembered through the auto-reload)
const viewer = document.getElementById("viewer");
function showForm(id, pdf, title, keep = true) {
  const r = reports.find(x => x.id === id), form = r && r.forms.find(f => f.print_pdf === pdf);
  if (!form) { forget("vff-view"); return false; }
  document.getElementById("viewerTitle").textContent = title || `${form.title} — ${r.created}`;
  document.getElementById("viewerOpen").href = pdfUrl(r, pdf);
  const frame = document.getElementById("viewerFrame");
  if (frame.dataset.src !== pdfUrl(r, pdf)) { frame.src = pdfUrl(r, pdf); frame.dataset.src = pdfUrl(r, pdf); }
  viewer.classList.add("on");
  if (keep) remember("vff-view", JSON.stringify({id, pdf, title}));
  return true;
}
document.getElementById("viewerClose").addEventListener("click", () => { viewer.classList.remove("on"); forget("vff-view"); });
document.addEventListener("click", e => {
  const a = e.target.closest("[data-view]");
  if (!a) return;
  e.preventDefault();
  const [id, pdf] = a.dataset.view.split("/");
  showForm(id, pdf, a.dataset.title);
  openTab("reports");
  viewer.scrollIntoView({behavior: "smooth", block: "start"});
});
try { const v = JSON.parse(recall("vff-view") || "null"); if (v) showForm(v.id, v.pdf, v.title, false); } catch (e) { forget("vff-view"); }

// ---- the progress bar: asks the dashboard server every second where the current run is
const progressCard = document.getElementById("progress");
const PAGE_OPENED = Date.now() / 1000;
const SHOW_DONE_FOR = 180, STALLED_AFTER = 120, FORGET_AFTER = 20 * 60;  // seconds
const mmss = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
function drawProgress(p) {
  const running = p.step && p.step !== "done" && p.step !== "stopped";
  const show = p.step && (running ? p.age < FORGET_AFTER : p.age < SHOW_DONE_FOR);
  progressCard.classList.toggle("on", !!show);
  if (!show) return;
  const stalled = running && p.age > STALLED_AFTER;
  progressCard.className = `card progress on ${p.step === "done" ? "done" : p.step === "stopped" ? "stopped" : stalled ? "stalled" : ""}`;
  document.getElementById("pmsg").textContent = stalled ? `${p.message} — no news for ${Math.round(p.age / 60)} min; see the output below` : p.message;
  document.getElementById("ptime").textContent = running ? `${p.percent}% · ${mmss(p.updated - p.started + p.age)}` : p.step === "done" ? `took ${mmss(p.updated - p.started)}` : "";
  document.getElementById("pfill").style.width = `${p.step === "stopped" ? 100 : p.percent}%`;
  document.getElementById("pstop").hidden = !running;
  const names = (p.steps || []).map(st => st[0]), at = names.indexOf(p.step);
  document.getElementById("psteps").innerHTML = (p.steps || []).map(([name, label], i) =>
    `<li class="${i < at || p.step === "done" ? "past" : i === at ? "now" : ""}">${esc(label)}</li>`).join("");
}
function showWhatFinished(p) {
  // A run just finished: bring its report (or test) onto the page, once.
  const key = p.report ? `report:${p.report}` : p.run ? `test:${p.run}` : "";
  if (!key || recall("vff-shown") === key) return;
  remember("vff-shown", key);
  let tab = "overview";
  if (p.report && p.pdfs && p.pdfs.length) {
    remember("vff-view", JSON.stringify({id: p.report, pdf: p.pdfs[0], title: ""}));
    tab = "reports";
  } else if (p.run) {
    tab = "tests";
  }
  remember("vff-tab", tab);
  location.replace(`${location.pathname}?t=${Date.now()}#${tab}`);  // a fresh load that lands on that tab
}
let running = false;
if (CAN_RUN) {
  let outputRunning = false;
  const poll = () => Promise.all([
    fetch("/progress").then(r => r.json()),
    fetch(`/output?since=${shownLines}`).then(r => r.json()),
  ]).then(([p, o]) => {
    outputRunning = !!o.running;
    running = outputRunning || (!!p.step && p.step !== "done" && p.step !== "stopped" && p.age < FORGET_AFTER);
    drawOutput(o);
    drawProgress(p);
    if (p.step === "done" && !outputRunning && p.updated >= PAGE_OPENED - 10) showWhatFinished(p);  // only a run that ended while this page was open
  }).catch(() => {});
  poll();
  setInterval(poll, 1000);
}
// the page rebuilds itself every 30 s (new reports and tests), except in the middle of a run
setInterval(() => { if (!running) location.reload(); }, 30000);

// ---- navigation: the page remembers where you were through the auto-reload
const TITLES = {overview: ["Overview", ""],
  reports: ["Reports", "Every report filed with the app, newest first. Open PDF shows the printed copy."],
  forms: ["Forms", "The forms the app can fill today, and the words that pick each one."],
  accuracy: ["Score & fixes", "How many checked boxes the latest test of each script got right, and what is still wrong."],
  tests: ["Tests", "The latest run of each test script, form by form."],
  trend: ["Over time", "Is it getting better? Percent of boxes right per test, run by run."],
  howto: ["How to use", "The commands, in the order you'll use them."]};
const NAV = [...document.querySelectorAll("#nav [data-tab]")];
function openTab(name, keep = true) {
  if (!TITLES[name]) name = "overview";
  NAV.forEach(b => b.setAttribute("aria-selected", b.dataset.tab === name));
  document.querySelectorAll(".panel").forEach(pn => pn.classList.toggle("on", pn.dataset.panel === name));
  document.getElementById("title").textContent = TITLES[name][0];
  document.getElementById("subtitle").textContent = TITLES[name][1];
  recordTop.hidden = !CAN_RUN || name === "overview";
  if (keep) { remember("vff-tab", name); history.replaceState(null, "", "#" + name); }
}
NAV.forEach(b => b.addEventListener("click", () => openTab(b.dataset.tab)));
openTab(location.hash.slice(1) || recall("vff-tab") || "overview", false);
</script>
</body>
</html>
"""
