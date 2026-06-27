/**
 * ═══════════════════════════════════════════════════════════════════════════
 * aluglass.formula  –  FORMULA BUILDER v3
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * Kiến trúc v3 (single-file bundle, section markers rõ ràng):
 *
 *  §0   CSS Injection (light theme, design tokens)
 *  §1   Monaco Loader
 *  §2   Built-in Knowledge Base (FB_FUNCTIONS, FB_SNIPPETS, FB_TEMPLATES)
 *  §3   FunctionRegistry  – register/merge, không override
 *  §4   ContextCache      – TTL 30s, invalidate on-demand
 *  §5   CompletionRegistry – singleton WeakMap, no memory leak
 *  §6   ContextBuilder    – parent + current_row + siblings + global vars
 *  §7   CompletionProvider v3 – metadata đầy đủ, smart trigger
 *  §8   AluglassFormulaEditor class
 *  §9   Public API (openDialog, attachMonacoToField, ...)
 *
 * Class prefix chuẩn: afb-*  (thay aluglass-fb-*, aluglass-fp-*, aluglass-inline-*)
 * Backward-compat aliases được giữ ở cuối file.
 *
 * @version 3.1.0  (refactored: dedup ContextBuilder, CSS, _serializeDoc, scrollable tabs)
 */

frappe.provide("aluglass.formula");

// ═══════════════════════════════════════════════════════════════════════════
// §0  CSS INJECTION
// ═══════════════════════════════════════════════════════════════════════════
(function _injectCSS() {
  if (document.getElementById("afb-css-v3")) return;
  const s = document.createElement("style");
  s.id = "afb-css-v3";
  s.textContent = `
  /* ── Design tokens ──────────────────────────────────────────────── */
  :root {
    --afb-bg0:       #ffffff;
    --afb-bg1:       #f8fafc;
    --afb-bg2:       #f1f5f9;
    --afb-bg3:       #e2e8f0;
    --afb-bg4:       #cbd5e1;
    --afb-border:    #cbd5e1;
    --afb-border2:   #94a3b8;
    --afb-text:      #1e293b;
    --afb-text2:     #334155;
    --afb-text3:     #64748b;
    --afb-amber:     #f59e0b;
    --afb-amber2:    #fbbf24;
    --afb-green:     #10b981;
    --afb-red:       #ef4444;
    --afb-blue:      #3b82f6;
    --afb-purple:    #8b5cf6;
    --afb-cyan:      #06b6d4;
    --afb-pink:      #ec4899;
    --afb-orange:    #f97316;
    --afb-radius:    6px;
    --afb-mono:      'JetBrains Mono','Fira Code','Cascadia Code',monospace;
    --afb-ui:        'Inter','Segoe UI',sans-serif;
    --afb-shadow-md: 0 2px 4px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.1);
    --afb-shadow-lg: 0 10px 15px -3px rgba(0,0,0,.1),0 4px 6px -2px rgba(0,0,0,.06);
    --afb-tr:        150ms cubic-bezier(.4,0,.2,1);
  }

  /* ── Wrap ────────────────────────────────────────────────────────── */
  .afb-wrap {
    display:flex;flex-direction:column;
    background:var(--afb-bg0);color:var(--afb-text);
    border-radius:10px;border:1px solid var(--afb-border);
    box-shadow:var(--afb-shadow-lg);
    font-family:var(--afb-ui);font-size:13px;
    user-select:none;
  }

  /* ── Header ─────────────────────────────────────────────────────── */
  .afb-header {
    display:flex;align-items:center;gap:10px;
    padding:10px 16px;
    background:var(--afb-bg1);border-bottom:1px solid var(--afb-border);
    flex-shrink:0;
  }
  .afb-logo { display:flex;align-items:center;gap:7px; }
  .afb-logo-icon {
    width:22px;height:22px;border-radius:5px;
    background:linear-gradient(135deg,var(--afb-amber),var(--afb-pink));
    display:flex;align-items:center;justify-content:center;
    font-size:12px;font-weight:700;color:#000;
  }
  .afb-logo-text { font-weight:700;font-size:13px;letter-spacing:.3px; }
  .afb-header-meta { margin-left:auto;display:flex;align-items:center;gap:8px; }
  .afb-badge {
    font-size:11px;color:var(--afb-text2);
    background:var(--afb-bg3);border:1px solid var(--afb-border);
    padding:3px 9px;border-radius:20px;
  }

  /* ── Toolbar ─────────────────────────────────────────────────────── */
  .afb-toolbar {
    display:flex;align-items:center;gap:5px;flex-wrap:wrap;
    padding:7px 12px;
    background:var(--afb-bg1);border-bottom:1px solid var(--afb-border);
    flex-shrink:0;
  }
  .afb-btn {
    display:inline-flex;align-items:center;gap:5px;
    padding:5px 12px;border-radius:var(--afb-radius);
    font-size:12px;font-weight:600;cursor:pointer;
    border:1px solid var(--afb-border);
    background:var(--afb-bg3);color:var(--afb-text);
    transition:background var(--afb-tr),border-color var(--afb-tr),transform var(--afb-tr);
    outline:none;white-space:nowrap;
  }
  .afb-btn:hover { background:var(--afb-bg4);border-color:var(--afb-border2);transform:translateY(-1px); }
  .afb-btn:active { transform:translateY(0); }
  .afb-btn.primary { background:linear-gradient(135deg,var(--afb-amber),#e08800);border-color:transparent;color:#000;font-weight:700; }
  .afb-btn.primary:hover { background:linear-gradient(135deg,var(--afb-amber2),var(--afb-amber)); }
  .afb-btn.danger  { border-color:var(--afb-red);color:var(--afb-red); }
  .afb-btn.danger:hover  { background:rgba(239,68,68,.1); }
  .afb-btn.success { border-color:var(--afb-green);color:var(--afb-green); }
  .afb-btn.success:hover { background:rgba(16,185,129,.1); }
  .afb-btn.suggest { border-color:var(--afb-purple);color:var(--afb-purple); }
  .afb-btn.suggest:hover { background:rgba(139,92,246,.1); }
  .afb-btn.active  { background:var(--afb-bg4);border-color:var(--afb-amber);color:var(--afb-amber); }
  .afb-btn-sep { width:1px;height:20px;background:var(--afb-border);margin:0 2px; }
  .afb-tb-status { margin-left:auto;font-size:11px;color:var(--afb-text2);transition:color 200ms; }

  /* ── Body layout ─────────────────────────────────────────────────── */
  .afb-body { display:flex;flex:1;min-height:0;overflow:hidden; }

  /* ── Sidebar ─────────────────────────────────────────────────────── */
  .afb-sidebar {
    width:270px;min-width:220px;max-width:400px;
    border-right:1px solid var(--afb-border);
    background:var(--afb-bg1);
    display:flex;flex-direction:column;overflow:hidden;position:relative;
  }
  .afb-sb-resize {
    position:absolute;right:0;top:0;bottom:0;width:4px;
    cursor:col-resize;z-index:10;
  }
  .afb-sb-resize:hover { background:var(--afb-border2); }
  .afb-sb-tabs {
    display:flex;border-bottom:1px solid var(--afb-border);
    overflow-x:auto;scrollbar-width:thin;
    scrollbar-color:var(--afb-bg4) transparent;
    flex-shrink:0;
  }
  .afb-sb-tabs::-webkit-scrollbar { height:3px; }
  .afb-sb-tabs::-webkit-scrollbar-thumb { background:var(--afb-bg4);border-radius:2px; }
  .afb-sb-tabs::-webkit-scrollbar-track { background:transparent; }
  .afb-sb-tab {
    padding:8px 10px;cursor:pointer;font-size:11px;font-weight:500;
    color:var(--afb-text2);white-space:nowrap;
    border-bottom:2px solid transparent;
    transition:color var(--afb-tr),border-color var(--afb-tr);
    position:relative;
  }
  .afb-sb-tab:hover { color:var(--afb-text); }
  .afb-sb-tab.active { color:var(--afb-amber);border-bottom-color:var(--afb-amber); }
  .afb-sb-tab-badge {
    position:absolute;top:4px;right:2px;
    min-width:14px;height:14px;border-radius:7px;
    background:var(--afb-amber);color:#000;
    font-size:9px;font-weight:700;line-height:14px;
    text-align:center;padding:0 3px;
  }
  .afb-sb-search {
    padding:8px 10px;border-bottom:1px solid var(--afb-border);position:relative;flex-shrink:0;
  }
  .afb-sb-search input {
    width:100%;padding:6px 10px 6px 28px;
    background:var(--afb-bg3);border:1px solid var(--afb-border);
    border-radius:var(--afb-radius);color:var(--afb-text);
    font-size:12px;font-family:var(--afb-ui);outline:none;box-sizing:border-box;
  }
  .afb-sb-search input:focus { border-color:var(--afb-amber); }
  .afb-sb-search input::placeholder { color:var(--afb-text3); }
  .afb-sb-search-icon {
    position:absolute;left:18px;top:50%;transform:translateY(-50%);
    color:var(--afb-text3);font-size:12px;pointer-events:none;
  }
  .afb-sb-list {
    flex:1;overflow-y:auto;padding:6px;
    scrollbar-width:thin;scrollbar-color:var(--afb-bg4) transparent;
  }
  .afb-sb-list::-webkit-scrollbar { width:4px; }
  .afb-sb-list::-webkit-scrollbar-thumb { background:var(--afb-bg4);border-radius:2px; }
  .afb-sb-group { margin-bottom:6px; }
  .afb-sb-group-head {
    padding:4px 8px;font-size:10px;font-weight:700;letter-spacing:.8px;
    text-transform:uppercase;color:var(--afb-text3);
    display:flex;align-items:center;gap:6px;cursor:pointer;
  }
  .afb-sb-group-head:hover { color:var(--afb-text2); }
  .afb-sb-group-toggle { font-size:8px;transition:transform var(--afb-tr); }
  .afb-sb-group.collapsed .afb-sb-group-toggle { transform:rotate(-90deg); }
  .afb-sb-group.collapsed .afb-sb-group-items { display:none; }

  /* Sidebar items */
  .afb-sb-item {
    display:flex;align-items:flex-start;gap:8px;
    padding:6px 8px;border-radius:var(--afb-radius);
    cursor:grab;transition:background var(--afb-tr);
    margin-bottom:2px;border-left:3px solid transparent;
  }
  .afb-sb-item:hover  { background:var(--afb-bg3); }
  .afb-sb-item:active { cursor:grabbing; }
  .afb-sb-item.drag-source { opacity:.4; }
  .afb-sb-item.pinned { border-left-color:var(--afb-amber) !important; }
  .afb-sb-item-global { border-left-color:var(--afb-purple) !important; }
  .afb-sb-item-local  { border-left-color:var(--afb-green)  !important; }
  .afb-sb-item-ref    { border-left-color:var(--afb-orange) !important; }
  .afb-sb-item-func   { border-left-color:var(--afb-cyan)   !important; }
  .afb-sb-item-snip   { border-left-color:var(--afb-pink)   !important; }
  .afb-sb-item-sibling{ border-left-color:var(--afb-blue)   !important; }

  .afb-sb-item-icon {
    width:20px;height:20px;border-radius:4px;
    display:flex;align-items:center;justify-content:center;
    font-size:10px;flex-shrink:0;margin-top:1px;
  }
  .afb-sb-item-body { flex:1;min-width:0; }
  .afb-sb-item-name {
    font-size:12px;font-weight:700;font-family:var(--afb-mono);
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  }
  .afb-sb-item-desc { font-size:10px;color:var(--afb-text2);margin-top:1px; }
  .afb-sb-item-meta {
    font-size:9px;color:var(--afb-text3);font-family:var(--afb-mono);margin-top:2px;
    display:flex;gap:6px;flex-wrap:wrap;
  }
  .afb-sb-item-val  { font-size:10px;font-family:var(--afb-mono);color:var(--afb-green);margin-top:2px; }
  .afb-sb-item-source-badge {
    font-size:9px;padding:1px 5px;border-radius:3px;
    opacity:0;font-weight:600;letter-spacing:.4px;
    text-transform:uppercase;align-self:center;flex-shrink:0;
    transition:opacity var(--afb-tr);
  }
  .afb-sb-item:hover .afb-sb-item-source-badge { opacity:1; }
  .afb-sb-item-global .afb-sb-item-source-badge { background:rgba(139,92,246,.2);color:var(--afb-purple); }
  .afb-sb-item-local  .afb-sb-item-source-badge { background:rgba(16,185,129,.2);color:var(--afb-green); }
  .afb-sb-item-ref    .afb-sb-item-source-badge { background:rgba(249,115,22,.2);color:var(--afb-orange); }
  .afb-sb-item-func   .afb-sb-item-source-badge { background:rgba(6,182,212,.2);color:var(--afb-cyan); }
  .afb-sb-item-snip   .afb-sb-item-source-badge { background:rgba(236,72,153,.2);color:var(--afb-pink); }
  .afb-sb-item-sibling .afb-sb-item-source-badge { background:rgba(59,130,246,.2);color:var(--afb-blue); }

  .afb-sb-item-insert, .afb-sb-item-pin {
    opacity:0;font-size:11px;color:var(--afb-text3);padding:2px 4px;
    border-radius:3px;transition:opacity var(--afb-tr),color var(--afb-tr);
    cursor:pointer;flex-shrink:0;align-self:center;
  }
  .afb-sb-item:hover .afb-sb-item-insert,
  .afb-sb-item:hover .afb-sb-item-pin { opacity:1; }
  .afb-sb-item-insert:hover { background:var(--afb-bg4);color:var(--afb-amber); }
  .afb-sb-item-pin:hover    { background:var(--afb-bg4);color:var(--afb-amber); }
  .afb-sb-item-pin.pinned   { opacity:1;color:var(--afb-amber); }

  /* Type icons */
  .afb-type-var    { background:rgba(59,130,246,.15);color:#2563eb; }
  .afb-type-func   { background:rgba(139,92,246,.15);color:#7c3aed; }
  .afb-type-field  { background:rgba(6,182,212,.15);color:#0891b2; }
  .afb-type-const  { background:rgba(245,158,11,.15);color:#d97706; }
  .afb-type-ref    { background:rgba(16,185,129,.15);color:#059669; }
  .afb-type-snip   { background:rgba(236,72,153,.15);color:#db2777; }
  .afb-type-sibling{ background:rgba(59,130,246,.15);color:#2563eb; }

  /* ── Editor area ─────────────────────────────────────────────────── */
  .afb-editor-wrap { flex:1;display:flex;flex-direction:column;overflow:hidden; }
  .afb-monaco {
    flex:1;min-height:0;
    border-bottom:1px solid var(--afb-border);
    position:relative;
  }
  .afb-monaco.drag-over {
    outline:2px dashed var(--afb-amber);outline-offset:-2px;
    background:rgba(245,158,11,.03);
  }

  /* BUG FIX §2.7: padding-bottom ensures suggest widget doesn't cover last line */
  .afb-monaco .monaco-editor .view-lines,
  .afb-fp-monaco .monaco-editor .view-lines {
    padding-bottom:52px !important;
  }

  .afb-monaco .monaco-editor,
  .afb-monaco .monaco-editor .overflow-guard {
    overflow:visible !important;
  }
  .overflowingContentWidgets .suggest-widget {
    z-index:100000 !important;
  }
  /* Ẩn hoàn toàn status bar "Insert ↵ / show more" trong mọi context */
  .monaco-editor .suggest-widget .suggest-widget-status-bar,
  .overflowingContentWidgets .suggest-widget .suggest-widget-status-bar {
    display:none !important;
    height:0 !important;
    min-height:0 !important;
    padding:0 !important;
    border-top:none !important;
    overflow:hidden !important;
  }

  /* ── Validation bar ──────────────────────────────────────────────── */
  .afb-valbar {
    padding:6px 14px;background:var(--afb-bg1);
    height:38px;display:flex;align-items:center;
    gap:6px;flex-wrap:nowrap;overflow:hidden;
    border-bottom:1px solid var(--afb-border);flex-shrink:0;
  }
  .afb-chip {
    padding:3px 10px;border-radius:20px;
    font-size:11px;font-weight:700;letter-spacing:.2px;
    display:inline-flex;align-items:center;gap:4px;
  }
  .afb-chip.ok      { background:rgba(16,185,129,.15);color:var(--afb-green);border:1px solid rgba(16,185,129,.3); }
  .afb-chip.error   { background:rgba(239,68,68,.15);color:var(--afb-red);border:1px solid rgba(239,68,68,.3); }
  .afb-chip.warning { background:rgba(245,158,11,.15);color:var(--afb-amber);border:1px solid rgba(245,158,11,.3); }
  .afb-chip.info    { background:rgba(59,130,246,.15);color:#2563eb;border:1px solid rgba(59,130,246,.3); }
  .afb-valbar-hint  { margin-left:auto;font-size:11px;color:var(--afb-text3); }

  /* ── Status bar ──────────────────────────────────────────────────── */
  .afb-statusbar {
    display:flex;align-items:center;gap:12px;
    padding:3px 14px;background:var(--afb-bg2);
    border-top:1px solid var(--afb-border);
    font-size:10px;color:var(--afb-text3);
    font-family:var(--afb-mono);flex-shrink:0;
  }
  .afb-statusbar-item { display:flex;align-items:center;gap:4px; }
  .afb-statusbar-item.ok     { color:var(--afb-green); }
  .afb-statusbar-item.error  { color:var(--afb-red); }
  .afb-statusbar-item.warn   { color:var(--afb-amber); }
  .afb-statusbar-sep { width:1px;height:10px;background:var(--afb-border); }

  /* ── Panel resize ────────────────────────────────────────────────── */
  .afb-panel-resize {
    height:4px;cursor:row-resize;
    background:var(--afb-border);transition:background 150ms;flex-shrink:0;
  }
  .afb-panel-resize:hover { background:var(--afb-amber); }

  /* ── Bottom panel ────────────────────────────────────────────────── */
  .afb-panel { border-top:1px solid var(--afb-border);background:var(--afb-bg1);display:flex;flex-direction:column;flex-shrink:0; }
  .afb-panel-tabs { display:flex;border-bottom:1px solid var(--afb-border);overflow-x:auto;scrollbar-width:none; }
  .afb-panel-tabs::-webkit-scrollbar { display:none; }
  .afb-panel-tab {
    padding:8px 16px;cursor:pointer;font-size:12px;font-weight:500;
    color:var(--afb-text2);border-bottom:2px solid transparent;
    transition:color var(--afb-tr),border-color var(--afb-tr);white-space:nowrap;
  }
  .afb-panel-tab:hover { color:var(--afb-text); }
  .afb-panel-tab.active { color:var(--afb-amber);border-bottom-color:var(--afb-amber); }
  .afb-panel-body {
    display:none;padding:10px 14px;font-size:12px;
    height:130px;overflow-y:auto;
    font-family:var(--afb-mono);color:var(--afb-text2);line-height:1.6;
    scrollbar-width:thin;scrollbar-color:var(--afb-bg4) transparent;
  }
  .afb-panel-body.active { display:block; }
  .afb-result-ok    { color:var(--afb-green); }
  .afb-result-err   { color:var(--afb-red); }
  .afb-result-big   { font-size:20px;font-weight:700;color:var(--afb-amber); }
  .afb-result-label { font-size:11px;color:var(--afb-text3);margin-bottom:4px; }
  .afb-result-copy  {
    display:inline-flex;align-items:center;gap:4px;
    margin-top:8px;padding:3px 8px;border-radius:4px;
    background:var(--afb-bg4);border:1px solid var(--afb-border);
    color:var(--afb-text2);font-size:10px;cursor:pointer;
    transition:background var(--afb-tr);
  }
  .afb-result-copy:hover { background:var(--afb-bg3);color:var(--afb-amber); }

  /* Context table */
  .afb-ctx-table { width:100%;border-collapse:collapse;font-size:11px; }
  .afb-ctx-table th {
    text-align:left;padding:4px 8px;color:var(--afb-text3);
    font-weight:600;letter-spacing:.5px;border-bottom:1px solid var(--afb-border);
    font-size:10px;text-transform:uppercase;
  }
  .afb-ctx-table td { padding:4px 8px;border-bottom:1px solid rgba(0,0,0,.05); }
  .afb-ctx-table tr:hover td { background:var(--afb-bg3); }
  .afb-ctx-key  { color:#2563eb;font-family:var(--afb-mono); }
  .afb-ctx-val  { color:var(--afb-green);font-family:var(--afb-mono); }
  .afb-ctx-type { color:var(--afb-text3);font-size:10px; }
  .afb-ctx-src-global { color:var(--afb-purple);font-size:10px;font-weight:600; }
  .afb-ctx-src-local  { color:var(--afb-green);font-size:10px;font-weight:600; }
  .afb-ctx-src-row    { color:var(--afb-cyan);font-size:10px;font-weight:600; }
  .afb-ctx-src-sibling{ color:var(--afb-blue);font-size:10px;font-weight:600; }

  /* Explain panel */
  .afb-explain-step {
    display:flex;align-items:flex-start;gap:6px;
    padding:3px 0;border-bottom:1px solid rgba(0,0,0,.05);
  }
  .afb-explain-step:last-child { border-bottom:none; }
  .afb-explain-step-icon { font-size:12px;flex-shrink:0;margin-top:1px; }
  .afb-explain-step-body { flex:1;min-width:0; }
  .afb-explain-step-name { font-family:var(--afb-mono);font-size:12px;font-weight:700;color:var(--afb-amber); }
  .afb-explain-step-name.root  { color:var(--afb-amber);font-size:13px; }
  .afb-explain-step-name.input { color:#2563eb; }
  .afb-explain-step-formula { font-family:var(--afb-mono);font-size:10px;color:var(--afb-text2);margin-top:1px; }
  .afb-explain-step-value   { font-family:var(--afb-mono);font-size:11px;color:var(--afb-green);font-weight:700;margin-left:4px; }
  .afb-explain-step-deps    { font-size:10px;color:var(--afb-text3);margin-top:2px; }
  .afb-explain-inputs-section { margin-bottom:8px;padding-bottom:6px;border-bottom:1px dashed var(--afb-border); }
  .afb-explain-section-title  { font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--afb-text3);margin-bottom:4px; }

  /* Debug panel */
  .afb-debug-section { margin-bottom:10px; }
  .afb-debug-title { font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--afb-text3);margin-bottom:4px; }
  .afb-debug-token { display:inline-block;margin:2px 3px;padding:1px 6px;border-radius:3px;font-family:var(--afb-mono);font-size:10px; }
  .afb-debug-token-name    { background:rgba(245,158,11,.15);color:#d97706; }
  .afb-debug-token-number  { background:rgba(249,115,22,.15);color:#ea580c; }
  .afb-debug-token-string  { background:rgba(16,185,129,.15);color:#059669; }
  .afb-debug-token-op      { background:rgba(6,182,212,.15);color:#0891b2; }
  .afb-debug-token-paren   { background:rgba(0,0,0,.05);color:var(--afb-text2); }
  .afb-debug-token-keyword { background:rgba(236,72,153,.15);color:#db2777; }
  .afb-debug-token-var     { background:rgba(139,92,246,.15);color:#7c3aed; }
  .afb-debug-token-other   { background:rgba(0,0,0,.05);color:var(--afb-text3); }
  .afb-debug-ast {
    font-family:var(--afb-mono);font-size:10px;color:var(--afb-text2);
    white-space:pre-wrap;background:var(--afb-bg3);border-radius:var(--afb-radius);
    padding:8px;margin-top:6px;max-height:80px;overflow-y:auto;
  }

  /* History panel */
  .afb-history-item {
    padding:6px 8px;border-bottom:1px solid rgba(0,0,0,.05);
    cursor:pointer;transition:background var(--afb-tr);
    display:flex;align-items:center;gap:8px;
  }
  .afb-history-item:hover { background:var(--afb-bg3); }
  .afb-history-formula { flex:1;font-family:var(--afb-mono);font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }
  .afb-history-result { font-size:11px;font-family:var(--afb-mono); }
  .afb-history-result.ok  { color:var(--afb-green); }
  .afb-history-result.err { color:var(--afb-red); }
  .afb-history-time { font-size:10px;color:var(--afb-text3);flex-shrink:0; }

  /* Test-with-vars panel */
  .afb-tvars-table { width:100%;border-collapse:collapse;font-size:11px; }
  .afb-tvars-table th {
    text-align:left;padding:4px 8px;
    color:var(--afb-text3);font-size:10px;font-weight:700;
    text-transform:uppercase;letter-spacing:.5px;
    border-bottom:1px solid var(--afb-border);
  }
  .afb-tvars-table td { padding:3px 4px;border-bottom:1px solid rgba(0,0,0,.04); }
  .afb-tvar-input {
    padding:3px 6px;border:1px solid var(--afb-border);border-radius:4px;
    font-family:var(--afb-mono);font-size:11px;background:var(--afb-bg0);
    color:var(--afb-text);width:100px;outline:none;
  }
  .afb-tvar-input:focus { border-color:var(--afb-amber); }
  .afb-tvar-result { font-family:var(--afb-mono);font-size:16px;font-weight:700;color:var(--afb-amber); }

  /* Drag ghost */
  .afb-drag-ghost {
    position:fixed;pointer-events:none;z-index:9999;
    background:var(--afb-bg3);border:1px solid var(--afb-amber);
    border-radius:var(--afb-radius);padding:5px 12px;
    font-family:var(--afb-mono);font-size:12px;color:var(--afb-amber);
    box-shadow:var(--afb-shadow-md);opacity:0;transform:rotate(-3deg) scale(1.05);
    transition:opacity 80ms;left:-9999px;top:-9999px;
  }
  .afb-drag-ghost.visible { opacity:.95; }

  /* Tooltip */
  .afb-tooltip {
    position:fixed;z-index:200000;pointer-events:none;
    background:#ffffff;border:1px solid var(--afb-border2);
    border-radius:8px;padding:10px 14px;font-size:12px;max-width:320px;
    box-shadow:0 8px 24px rgba(0,0,0,.15);opacity:0;transition:opacity 120ms;
    color:var(--afb-text);
  }
  .afb-tooltip.visible { opacity:1; }
  .afb-tooltip-name { font-family:var(--afb-mono);color:var(--afb-amber);font-weight:700;margin-bottom:4px; }
  .afb-tooltip-sig  { font-family:var(--afb-mono);font-size:11px;color:var(--afb-cyan);margin-bottom:6px; }
  .afb-tooltip-desc { color:var(--afb-text2);line-height:1.5;margin-bottom:4px; }
  .afb-tooltip-example { margin-top:6px;font-size:10px;color:var(--afb-cyan);font-family:var(--afb-mono);padding:4px 8px;background:var(--afb-bg2);border-radius:4px; }
  .afb-tooltip-meta { margin-top:6px;font-size:10px;color:var(--afb-text3); }
  .afb-tooltip-source { margin-top:6px;font-size:10px;font-weight:600;padding:2px 6px;border-radius:3px;display:inline-block; }

  /* Snippets */
  .afb-snip-grid { display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:6px; }
  .afb-snip-card {
    background:var(--afb-bg3);border:1px solid var(--afb-border);border-left:3px solid var(--afb-pink);
    border-radius:var(--afb-radius);padding:8px 10px;cursor:pointer;
    transition:background var(--afb-tr),border-color var(--afb-tr);
  }
  .afb-snip-card:hover { background:var(--afb-bg4);border-color:var(--afb-amber);border-left-color:var(--afb-pink); }
  .afb-snip-card-title { font-size:11px;font-weight:600;margin-bottom:3px; }
  .afb-snip-card-code  { font-family:var(--afb-mono);font-size:10px;color:var(--afb-text3); }

  /* Template Gallery */
  .afb-tmpl-section { margin-bottom:10px; }
  .afb-tmpl-section-title { font-size:10px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--afb-text3);padding:4px 8px;margin-bottom:4px; }
  .afb-tmpl-card {
    background:var(--afb-bg3);border:1px solid var(--afb-border);
    border-radius:var(--afb-radius);padding:8px 10px;cursor:pointer;
    margin-bottom:4px;transition:background var(--afb-tr),border-color var(--afb-tr);
    display:flex;align-items:center;gap:8px;
  }
  .afb-tmpl-card:hover { background:var(--afb-bg4);border-color:var(--afb-purple); }
  .afb-tmpl-card-icon { font-size:14px;flex-shrink:0; }
  .afb-tmpl-card-body { flex:1;min-width:0; }
  .afb-tmpl-card-name { font-size:12px;font-weight:600;margin-bottom:2px; }
  .afb-tmpl-card-code { font-family:var(--afb-mono);font-size:10px;color:var(--afb-text3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }

  /* Smart Suggest overlay */
  .afb-suggest-overlay {
    position:fixed;inset:0;z-index:1000010;
    background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center;
  }
  .afb-suggest-dialog {
    background:#ffffff;border:1px solid #cbd5e1;border-radius:12px;
    padding:24px 28px;width:500px;max-width:95vw;max-height:80vh;overflow-y:auto;
    box-shadow:0 20px 25px -5px rgba(0,0,0,.2);
  }
  .afb-suggest-title { font-size:14px;font-weight:700;margin-bottom:12px;color:var(--afb-amber); }
  .afb-suggest-formula {
    font-family:var(--afb-mono);font-size:13px;background:var(--afb-bg3);
    border:1px solid var(--afb-border);border-radius:var(--afb-radius);
    padding:12px 14px;color:var(--afb-green);margin-bottom:8px;line-height:1.6;
  }
  .afb-suggest-desc { font-size:12px;color:var(--afb-text2);margin-bottom:10px; }
  .afb-suggest-actions { display:flex;gap:8px;justify-content:flex-end;margin-top:14px; }

  /* Shortcuts overlay */
  .afb-shortcuts-overlay {
    position:fixed;inset:0;z-index:1000010;
    background:rgba(0,0,0,.75);display:flex;align-items:center;justify-content:center;
  }
  .afb-shortcuts-dialog {
    background:#ffffff;border-radius:12px;padding:24px 28px;
    width:560px;max-width:90vw;max-height:85vh;overflow-y:auto;
    box-shadow:0 20px 25px -5px rgba(0,0,0,.2);
  }
  .afb-shortcuts-title { font-size:18px;font-weight:700;margin-bottom:16px;color:var(--afb-amber); }
  .afb-shortcuts-grid { display:grid;grid-template-columns:1fr 1fr;gap:10px; }
  .afb-shortcuts-section { font-size:11px;font-weight:700;text-transform:uppercase;color:#64748b;margin:12px 0 6px;grid-column:1/-1; }
  .afb-shortcuts-row { display:flex;align-items:center;justify-content:space-between;padding:6px 12px;background:#f1f5f9;border-radius:8px; }
  .afb-shortcuts-desc { font-size:12px;color:#1e293b; }
  .afb-shortcuts-keys { display:flex;gap:4px; }
  .afb-kbd { background:#e2e8f0;border:1px solid #cbd5e1;border-radius:4px;padding:2px 6px;font-family:monospace;font-size:10px;font-weight:600;color:#0f172a; }
  .afb-shortcuts-close-row { margin-top:20px;display:flex;justify-content:flex-end; }

  /* Find & Replace panel */
  .afb-fnr-panel {
    position:absolute;top:0;right:0;z-index:500;
    background:#fff;border:1px solid var(--afb-border2);
    border-radius:var(--afb-radius);box-shadow:var(--afb-shadow-lg);
    padding:32px 14px 10px 14px;min-width:320px;max-width:420px;
    font-family:var(--afb-ui);font-size:12px;
    animation:afb-fade-in 150ms ease;
  }
  .afb-fnr-row { display:flex;align-items:center;gap:6px;margin-bottom:6px; }
  .afb-fnr-label { width:56px;color:var(--afb-text3);font-size:11px;flex-shrink:0; }
  .afb-fnr-input {
    flex:1;padding:5px 8px;border:1px solid var(--afb-border);
    border-radius:var(--afb-radius);background:var(--afb-bg2);color:var(--afb-text);
    font-size:12px;font-family:var(--afb-mono);outline:none;
  }
  .afb-fnr-input:focus { border-color:var(--afb-amber); }
  .afb-fnr-actions { display:flex;gap:5px;margin-top:4px;flex-wrap:wrap; }
  .afb-fnr-close {
    position:absolute;top:6px;right:8px;cursor:pointer;
    color:var(--afb-text3);font-size:14px;padding:3px 7px;
    border-radius:4px;transition:background var(--afb-tr);
    background:var(--afb-bg3);font-weight:700;line-height:1;
  }
  .afb-fnr-close:hover { color:var(--afb-red); }
  .afb-fnr-count { font-size:11px;color:var(--afb-text3);align-self:center;margin-left:auto; }
  .afb-fnr-opt { display:flex;align-items:center;gap:4px;font-size:11px;color:var(--afb-text2);cursor:pointer; }
  .afb-fnr-highlight { background:rgba(245,158,11,.3) !important;border-bottom:2px solid var(--afb-amber) !important; }

  /* Diff overlay */
  .afb-diff-overlay {
    position:fixed;inset:0;z-index:1000010;
    background:rgba(0,0,0,.65);display:flex;align-items:center;justify-content:center;
  }
  .afb-diff-dialog {
    background:#fff;border-radius:12px;padding:24px 28px;
    width:700px;max-width:95vw;max-height:85vh;overflow-y:auto;
    box-shadow:0 20px 40px rgba(0,0,0,.2);border:1px solid var(--afb-border);
  }
  .afb-diff-title { font-size:15px;font-weight:700;color:var(--afb-amber);margin-bottom:16px; }
  .afb-diff-cols { display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px; }
  .afb-diff-col-label { font-size:11px;font-weight:700;text-transform:uppercase;color:var(--afb-text3);margin-bottom:4px; }
  .afb-diff-code {
    font-family:var(--afb-mono);font-size:12px;line-height:1.6;
    background:var(--afb-bg2);border:1px solid var(--afb-border);
    border-radius:var(--afb-radius);padding:10px 12px;
    white-space:pre-wrap;word-break:break-all;min-height:80px;
  }
  .afb-diff-add  { background:rgba(16,185,129,.2);color:var(--afb-green);border-radius:2px; }
  .afb-diff-del  { background:rgba(239,68,68,.15);color:var(--afb-red);text-decoration:line-through;border-radius:2px; }
  .afb-diff-same { color:var(--afb-text2); }
  .afb-diff-stats { font-size:11px;color:var(--afb-text3);margin-bottom:12px; }
  .afb-diff-close-row { display:flex;gap:8px;justify-content:flex-end; }

  /* Tour */
  .afb-tour-spotlight {
    position:fixed;z-index:99993;
    border:3px solid var(--afb-amber);border-radius:8px;
    box-shadow:0 0 0 9999px rgba(0,0,0,.65);
    pointer-events:none;transition:all 350ms cubic-bezier(.4,0,.2,1);
  }
  .afb-tour-card {
    position:fixed;z-index:99994;
    background:#fff;border:1.5px solid var(--afb-amber);
    border-radius:12px;padding:18px 22px;max-width:320px;
    box-shadow:0 16px 40px rgba(0,0,0,.2);
    animation:afb-fade-in 250ms ease;
  }
  .afb-tour-progress { display:flex;gap:4px;margin-bottom:10px; }
  .afb-tour-progress-dot { width:6px;height:6px;border-radius:3px;background:var(--afb-bg4);transition:background 200ms; }
  .afb-tour-progress-dot.active { background:var(--afb-amber);width:18px; }
  .afb-tour-progress-dot.done   { background:var(--afb-green); }
  .afb-tour-step  { font-size:10px;color:var(--afb-amber);font-weight:700;margin-bottom:6px; }
  .afb-tour-title { font-size:14px;font-weight:700;margin-bottom:6px; }
  .afb-tour-desc  { font-size:12px;color:var(--afb-text2);line-height:1.5;margin-bottom:14px; }
  .afb-tour-actions { display:flex;gap:6px;justify-content:flex-end; }

  /* Inline field */
  .afb-field-patch-wrap {
    border:1px solid var(--afb-border);border-radius:var(--afb-radius);
    overflow:hidden;background:var(--afb-bg0);
    transition:border-color 150ms,box-shadow 150ms;
  }
  .afb-field-patch-wrap:focus-within {
    border-color:var(--afb-amber);
    box-shadow:0 0 0 3px rgba(245,158,11,.12);
  }
  .afb-fp-toolbar {
    display:flex;align-items:center;gap:6px;
    padding:4px 8px;background:var(--afb-bg1);
    border-bottom:1px solid var(--afb-border);font-size:11px;
  }
  .afb-fp-lang-badge {
    font-family:var(--afb-mono);font-size:10px;
    background:var(--afb-bg3);color:var(--afb-text2);
    padding:2px 7px;border-radius:3px;font-weight:600;
  }
  .afb-fp-monaco {
    border-radius:0 0 var(--afb-radius) var(--afb-radius);overflow:hidden;
  }
  .afb-fp-monaco .monaco-editor,
  .afb-fp-monaco .monaco-editor .overflow-guard {
    overflow:visible !important;
  }
  /* BUG FIX §2.7: inline editor also needs padding bottom */
  .afb-fp-monaco .monaco-editor .view-lines {
    padding-bottom:4px !important;
  }

  /* Preview badge */
  .afb-preview-badge {
    display:none;align-items:center;gap:5px;padding:3px 9px;margin-top:3px;
    font-family:var(--afb-mono);font-size:11px;border-radius:var(--afb-radius);
    border:1px solid transparent;transition:all 150ms ease;min-height:22px;line-height:1.4;
  }
  .afb-preview-badge.visible { display:flex; }
  .afb-preview-badge.ok      { background:rgba(16,185,129,.08);border-color:rgba(16,185,129,.3);color:var(--afb-green); }
  .afb-preview-badge.error   { background:rgba(239,68,68,.08);border-color:rgba(239,68,68,.3);color:var(--afb-red); }
  .afb-preview-badge.loading { background:rgba(245,158,11,.07);border-color:rgba(245,158,11,.25);color:var(--afb-amber); }
  .afb-preview-val { font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:340px; }
  .afb-preview-spin {
    width:10px;height:10px;border-radius:50%;
    border:2px solid currentColor;border-top-color:transparent;
    animation:afb-spin 0.6s linear infinite;flex-shrink:0;
  }

  /* Animations */
  @keyframes afb-fade-in { from { opacity:0;transform:translateY(4px); } to { opacity:1;transform:none; } }
  @keyframes afb-spin     { to   { transform:rotate(360deg); } }
  @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
  .afb-loading {
    background:linear-gradient(90deg,var(--afb-bg3) 25%,var(--afb-bg4) 50%,var(--afb-bg3) 75%);
    background-size:200% 100%;animation:shimmer 1.4s infinite;
    border-radius:4px;height:12px;margin:4px 0;
  }
  .afb-anim { animation:afb-fade-in 200ms ease; }

  /* Layout fixes for dialog */
  .afb-wrap { height:100% !important;display:flex !important;flex-direction:column !important;border-radius:6px !important;overflow:hidden !important; }
  .afb-body { flex:1 !important;min-height:0 !important;overflow:hidden !important; }
  .afb-editor-wrap { flex:1 !important;display:flex !important;flex-direction:column !important;min-height:0 !important; }
  .afb-monaco { flex:1 !important;min-height:0 !important;position:relative !important;overflow:hidden !important;z-index:1 !important; }

  /* Monaco suggest widget global fixes */
  .monaco-editor .suggest-widget { background:#ffffff !important;border:1px solid #cbd5e1 !important;box-shadow:0 10px 15px -3px rgba(0,0,0,.1) !important;color:#1e293b !important;overflow:hidden !important; }
  .monaco-editor .suggest-widget .monaco-list { overflow:hidden !important; }
  .monaco-editor .suggest-widget .monaco-list-rows { overflow:hidden !important; }
  .monaco-editor .suggest-widget .monaco-list-row { background:#ffffff !important;color:#0f172a !important;font-size:13px !important;font-weight:500 !important;line-height:26px !important;box-sizing:border-box !important;max-width:100% !important; }
  .monaco-editor .suggest-widget .monaco-list-row.focused { background:#e2e8f0 !important;color:#0f172a !important; }
  .monaco-editor .suggest-widget .monaco-list-row .monaco-highlighted-label { color:#0f172a !important;font-weight:600 !important;overflow:hidden !important;text-overflow:ellipsis !important;white-space:nowrap !important;max-width:100% !important; }
  .monaco-editor .suggest-widget .monaco-list-row .monaco-highlighted-label .highlight { color:#d97706 !important;font-weight:700 !important; }
  .monaco-editor .suggest-widget .monaco-list-row .details-label { color:#475569 !important;font-size:11px !important;overflow:hidden !important;text-overflow:ellipsis !important;white-space:nowrap !important; }

  /* Monaco hover */
  .monaco-editor .monaco-hover, .monaco-editor .monaco-hover .monaco-hover-content {
    background:#ffffff !important;border:1px solid #cbd5e1 !important;color:#1e293b !important;
    opacity:1 !important;box-shadow:0 8px 20px rgba(0,0,0,.15) !important;
    border-radius:8px !important;z-index:100000 !important;font-size:12px !important;
  }
  .monaco-editor .monaco-hover .monaco-hover-content code {
    background:#f1f5f9 !important;color:#d97706 !important;padding:2px 4px !important;border-radius:4px !important;
    font-family:'JetBrains Mono',monospace !important;
  }

  /* Ẩn status bar "Insert ↵ / show more" */
  .monaco-editor .suggest-widget .suggest-status-bar,
  .monaco-editor .suggest-widget .suggest-widget-status-bar,
  .overflowingContentWidgets .suggest-widget .suggest-status-bar,
  .overflowingContentWidgets .suggest-widget .suggest-widget-status-bar {
    display:none !important;
    height:0 !important;
    min-height:0 !important;
    overflow:hidden !important;
    border-top:none !important;
  }

  .modal .modal-body {
    overflow: visible !important;
  }

  /* Tìm đoạn này trong CSS của bạn và cập nhật lại */
  .overflowingContentWidgets .suggest-widget {
      z-index: 100000 !important;
      /* Ép chiều cao tối thiểu và tối đa cho hộp gợi ý khi nó nhảy ra ngoài body */
      min-height: 200px !important; 
      max-height: 280px !important;
  }

  /* Đảm bảo danh sách các dòng gợi ý bên trong có thể cuộn và lấy đủ chiều cao */
  .overflowingContentWidgets .suggest-widget .tree {
      height: 100% !important;
      min-height: 200px !important;
  }

  /* Ép container chứa danh sách hiển thị đầy đủ */
  .overflowingContentWidgets .suggest-widget .monaco-list {
      height: 100% !important;
  }
  `;
  document.head.appendChild(s);
})();

// ═══════════════════════════════════════════════════════════════════════════
// §1  MONACO LOADER
// ═══════════════════════════════════════════════════════════════════════════
window.__monacoLoaderPromise = window.__monacoLoaderPromise || null;

function loadMonaco() {
  if (window.__monacoLoaderPromise) return window.__monacoLoaderPromise;
  window.__monacoLoaderPromise = new Promise((resolve, reject) => {
    if (window.monaco) return resolve(window.monaco);
    const cdn = "https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs";
    const script = document.createElement("script");
    script.src = `${cdn}/loader.js`;
    script.onload = () => {
      if (typeof window.require !== "undefined") {
        window.require.config({ paths: { vs: cdn } });
        window.require(["vs/editor/editor.main"], () => resolve(window.monaco), reject);
      } else { reject("Monaco loader: require not defined"); }
    };
    script.onerror = () => reject("Monaco CDN load failed");
    document.head.appendChild(script);
  });
  return window.__monacoLoaderPromise;
}

// ═══════════════════════════════════════════════════════════════════════════
// §2  BUILT-IN KNOWLEDGE BASE
// ═══════════════════════════════════════════════════════════════════════════
const FB_FUNCTIONS = [
  // Math
  { name:"abs",        sig:"abs(number)",                cat:"Math",      desc:"Giá trị tuyệt đối",                    example:"abs(-5) → 5" },
  { name:"round",      sig:"round(number, decimals)",     cat:"Math",      desc:"Làm tròn số",                          example:"round(3.14159,2) → 3.14" },
  { name:"roundup",    sig:"roundup(x, d)",               cat:"Math",      desc:"Làm tròn lên theo d chữ số",           example:"roundup(3.01,1) → 3.1" },
  { name:"rounddown",  sig:"rounddown(x, d)",             cat:"Math",      desc:"Làm tròn xuống theo d chữ số",         example:"rounddown(3.99,1) → 3.9" },
  { name:"floor",      sig:"floor(number)",               cat:"Math",      desc:"Làm tròn xuống số nguyên",             example:"floor(3.9) → 3" },
  { name:"ceil",       sig:"ceil(number)",                cat:"Math",      desc:"Làm tròn lên số nguyên",               example:"ceil(3.1) → 4" },
  { name:"min",        sig:"min(a, b, ...)",              cat:"Math",      desc:"Giá trị nhỏ nhất",                     example:"min(10,20,5) → 5" },
  { name:"max",        sig:"max(a, b, ...)",              cat:"Math",      desc:"Giá trị lớn nhất",                     example:"max(10,20,5) → 20" },
  { name:"sum",        sig:"sum(list)",                   cat:"Math",      desc:"Tổng danh sách",                       example:"sum([1,2,3]) → 6" },
  { name:"average",    sig:"average(list)",               cat:"Math",      desc:"Trung bình cộng",                      example:"average([10,20]) → 15" },
  { name:"sqrt",       sig:"sqrt(number)",                cat:"Math",      desc:"Căn bậc hai",                          example:"sqrt(16) → 4" },
  { name:"power",      sig:"power(base, exp)",            cat:"Math",      desc:"Lũy thừa",                             example:"power(2,10) → 1024" },
  { name:"safe_div",   sig:"safe_div(a, b, def=0)",       cat:"Math",      desc:"Chia an toàn (tránh /0)",              example:"safe_div(10,0,0) → 0" },
  { name:"clamp",      sig:"clamp(x, lo, hi)",            cat:"Math",      desc:"Giới hạn giá trị [lo,hi]",             example:"clamp(150,0,100) → 100" },
  { name:"between",    sig:"between(x, lo, hi)",          cat:"Math",      desc:"Kiểm tra lo <= x <= hi",               example:"between(50,0,100) → True" },
  { name:"percent_of", sig:"percent_of(part, total)",     cat:"Math",      desc:"Tính phần trăm",                       example:"percent_of(25,100) → 25.0" },
  { name:"ln",         sig:"ln(x)",                       cat:"Math",      desc:"Logarit tự nhiên",                     example:"ln(2.718) ≈ 1.0" },
  { name:"log10",      sig:"log10(x)",                    cat:"Math",      desc:"Logarit cơ số 10",                     example:"log10(1000) → 3" },
  { name:"log",        sig:"log(x, base=e)",              cat:"Math",      desc:"Logarit tùy cơ số",                    example:"log(8,2) → 3" },
  { name:"exp",        sig:"exp(x)",                      cat:"Math",      desc:"e^x",                                  example:"exp(1) ≈ 2.718" },
  // Logic
  { name:"IF",         sig:"IF(cond, true_val, false_val)",    cat:"Logic",  desc:"Rẽ nhánh điều kiện",                example:"IF(qty>0,price*qty,0)" },
  { name:"IFS",        sig:"IFS(cond1, val1, cond2, val2, ...)",cat:"Logic", desc:"Nhiều điều kiện liên tiếp",          example:"IFS(x>70,'cao',x>40,'tb',True,'thấp')" },
  { name:"IIF",        sig:"IIF(cond, true_val, false_val)",   cat:"Logic",  desc:"Alias của IF()",                    example:"IIF(x>100,'High','Low')" },
  { name:"SWITCH",     sig:"SWITCH(val, case1, res1, ...)",    cat:"Logic",  desc:"Switch-case theo giá trị",           example:"SWITCH(status,'A','Active','I','Inactive')" },
  { name:"and_",       sig:"and_(a, b, ...)",                  cat:"Logic",  desc:"Tất cả điều kiện đều đúng",          example:"and_(x>0,y>0)" },
  { name:"or_",        sig:"or_(a, b, ...)",                   cat:"Logic",  desc:"Ít nhất một điều kiện đúng",         example:"or_(x>10,y>10)" },
  { name:"not_",       sig:"not_(value)",                      cat:"Logic",  desc:"Phủ định",                           example:"not_(is_closed)" },
  { name:"coalesce",   sig:"coalesce(a, b, ...)",              cat:"Logic",  desc:"Giá trị không null đầu tiên",        example:"coalesce(override,default_val)" },
  { name:"is_blank",   sig:"is_blank(x)",                      cat:"Logic",  desc:"Kiểm tra null/rỗng/0",               example:"is_blank(discount)" },
  { name:"not_blank",  sig:"not_blank(x)",                     cat:"Logic",  desc:"Kiểm tra có giá trị",                example:"not_blank(discount)" },
  { name:"isnumber",   sig:"isnumber(x)",                      cat:"Logic",  desc:"Kiểm tra là số",                    example:"isnumber('123') → True" },
  { name:"to_number",  sig:"to_number(x, def=0)",              cat:"Logic",  desc:"Chuyển thành số",                   example:"to_number('99.5',0) → 99.5" },
  // Aggregate
  { name:"sumif",      sig:"sumif(range, crit, sum_range)",    cat:"Aggregate", desc:"Tổng có điều kiện",               example:"sumif(items,'>100',amount)" },
  { name:"sumifs",     sig:"sumifs(sum_range, r1, c1, ...)",   cat:"Aggregate", desc:"Tổng nhiều điều kiện",            example:"sumifs(amount,qty,'>0')" },
  { name:"countif",    sig:"countif(range, crit)",             cat:"Aggregate", desc:"Đếm có điều kiện",                example:"countif(items,'>0')" },
  { name:"countifs",   sig:"countifs(r1, c1, ...)",            cat:"Aggregate", desc:"Đếm nhiều điều kiện",             example:"countifs(items,status='active')" },
  { name:"averageif",  sig:"averageif(range, crit)",           cat:"Aggregate", desc:"Trung bình có điều kiện",         example:"averageif(prices,'>0')" },
  { name:"count",      sig:"count(list)",                      cat:"Aggregate", desc:"Đếm phần tử",                     example:"count([1,2,3]) → 3" },
  { name:"unique",     sig:"unique(data, key=None)",           cat:"Aggregate", desc:"Lấy giá trị duy nhất",            example:"unique([1,1,2,3]) → [1,2,3]" },
  { name:"count_unique",sig:"count_unique(data, key=None)",    cat:"Aggregate", desc:"Đếm giá trị duy nhất",            example:"count_unique([1,1,2,3]) → 3" },
  { name:"flatten",    sig:"flatten(data)",                    cat:"Aggregate", desc:"Làm phẳng mảng lồng nhau",        example:"flatten([[1,2],[3]]) → [1,2,3]" },
  // Data/Array
  { name:"last",       sig:"last(data, sort_by=None, n=1, group_by=None)", cat:"Data", desc:"Phần tử cuối/lớn nhất sau sort", example:"last(rows,sort_by='date')" },
  { name:"first",      sig:"first(data, sort_by=None, n=1)",  cat:"Data",      desc:"Phần tử đầu/nhỏ nhất sau sort",    example:"first(rows,sort_by='date')" },
  { name:"nth",        sig:"nth(data, n, sort_by=None)",       cat:"Data",      desc:"Phần tử thứ n sau sort",           example:"nth(rows,2,sort_by='amount')" },
  { name:"sort",       sig:"sort(data, key=None, reverse=False)",cat:"Data",    desc:"Sắp xếp mảng",                    example:"sort(rows,key='date',reverse=True)" },
  { name:"filter_array",sig:"filter_array(data, op, thresh, key=None)",cat:"Data",desc:"Lọc mảng theo điều kiện",       example:"filter_array(rows,'>',100,key='amount')" },
  { name:"map_key",    sig:"map_key(data, key)",               cat:"Data",      desc:"Lấy 1 field từ list of dicts",     example:"map_key(rows,'amount')" },
  { name:"group_sum",  sig:"group_sum(data, group_key, sum_key)",cat:"Data",    desc:"Gộp nhóm + tổng",                 example:"group_sum(rows,'loai','amount')" },
  { name:"group_count",sig:"group_count(data, group_key)",     cat:"Data",      desc:"Gộp nhóm + đếm",                  example:"group_count(rows,'loai')" },
  { name:"group_avg",  sig:"group_avg(data, group_key, avg_key)",cat:"Data",    desc:"Gộp nhóm + trung bình",           example:"group_avg(rows,'loai','rate')" },
  // Lookup
  { name:"vlookup",    sig:"vlookup(val, tbl, col)",           cat:"Lookup",    desc:"Tra bảng dọc",                    example:"vlookup(code,price_table,2)" },
  { name:"xlookup",    sig:"xlookup(val, look_range, ret_range)",cat:"Lookup",  desc:"Tra bảng linh hoạt",              example:"xlookup(item_code,items,prices)" },
  { name:"fetch",      sig:"fetch(doctype, name, field)",       cat:"Lookup",    desc:"Lấy giá trị từ doctype khác",     example:"fetch('Item',item_code,'weight')" },
  { name:"get_var",    sig:"get_var(var_name)",                 cat:"Lookup",    desc:"Lấy biến toàn cục",               example:"get_var('VAT_RATE')" },
  { name:"get_price",  sig:"get_price(item, price_list)",       cat:"Lookup",    desc:"Lấy giá item",                    example:"get_price(item_code,'Standard')" },
  { name:"choose",     sig:"choose(n, v1, v2, ...)",            cat:"Lookup",    desc:"Chọn giá trị theo số",            example:"choose(2,'A','B','C') → B" },
  // String
  { name:"len",        sig:"len(string)",                       cat:"String",    desc:"Độ dài chuỗi",                    example:"len('hello') → 5" },
  { name:"upper",      sig:"upper(string)",                     cat:"String",    desc:"Chữ hoa",                         example:"upper('abc') → 'ABC'" },
  { name:"lower",      sig:"lower(string)",                     cat:"String",    desc:"Chữ thường",                      example:"lower('ABC') → 'abc'" },
  { name:"trim",       sig:"trim(string)",                      cat:"String",    desc:"Xóa khoảng trắng đầu/cuối",       example:"trim('  hi  ') → 'hi'" },
  { name:"concat",     sig:"concat(a, b, ...)",                 cat:"String",    desc:"Nối chuỗi",                       example:"concat(first,' ',last)" },
  { name:"left",       sig:"left(text, n)",                     cat:"String",    desc:"n ký tự bên trái",                example:"left('ABCDE',3) → 'ABC'" },
  { name:"right",      sig:"right(text, n)",                    cat:"String",    desc:"n ký tự bên phải",                example:"right('ABCDE',3) → 'CDE'" },
  { name:"mid",        sig:"mid(text, start, len)",             cat:"String",    desc:"Chuỗi con",                       example:"mid('ABCDE',2,3) → 'BCD'" },
  { name:"contains",   sig:"contains(string, substr)",          cat:"String",    desc:"Chuỗi có chứa không",             example:"contains(name,'AL')" },
  { name:"replace",    sig:"replace(s, find, repl)",            cat:"String",    desc:"Thay thế chuỗi",                  example:"replace(code,'-','')" },
  { name:"safe_str",   sig:"safe_str(x)",                       cat:"String",    desc:"Chuyển thành chuỗi an toàn",      example:"safe_str(None) → ''" },
  // Date
  { name:"today",      sig:"today()",                           cat:"Date",      desc:"Ngày hôm nay",                    example:"today() → 2025-05-13" },
  { name:"now",        sig:"now()",                             cat:"Date",      desc:"Thời gian hiện tại",              example:"now()" },
  { name:"year",       sig:"year(date)",                        cat:"Date",      desc:"Lấy năm",                         example:"year(posting_date) → 2025" },
  { name:"month",      sig:"month(date)",                       cat:"Date",      desc:"Lấy tháng",                       example:"month(posting_date) → 5" },
  { name:"day",        sig:"day(date)",                         cat:"Date",      desc:"Lấy ngày",                        example:"day(posting_date) → 13" },
  { name:"quarter",    sig:"quarter(date)",                     cat:"Date",      desc:"Lấy quý (1–4)",                  example:"quarter('2025-07-15') → 3" },
  { name:"date_diff",  sig:"date_diff(d1, d2, unit)",           cat:"Date",      desc:"Khoảng cách giữa 2 ngày",         example:"date_diff(end,start,'days')" },
  { name:"date_add",   sig:"date_add(date, days, months=0, years=0)",cat:"Date", desc:"Cộng ngày/tháng/năm",            example:"date_add(posting_date,30)" },
  { name:"date_format",sig:"date_format(dt, fmt='%d/%m/%Y')",  cat:"Date",      desc:"Định dạng ngày thành chuỗi",      example:"date_format(posting_date,'%d/%m/%Y')" },
  { name:"workdays",   sig:"workdays(date1, date2)",            cat:"Date",      desc:"Số ngày làm việc giữa 2 ngày",    example:"workdays(start,end)" },
  // Allocation / Graph
  { name:"allocate",   sig:"allocate(sources, targets, method='equal')",cat:"Alloc", desc:"Phân bổ chi phí",             example:"allocate(srcs,tgts,'qty')" },
  { name:"topo_sort_data",sig:"topo_sort_data(items, id_key, deps_list_key, dep_id_key)",cat:"Graph",desc:"Sắp xếp topo theo danh sách deps",example:"topo_sort_data(bom,'code','deps','code')" },
];

const FB_SNIPPETS = [
  { title:"Giá sau thuế",  code:"price * (1 + vat_rate / 100)",                               desc:"Tính giá gộp thuế" },
  { title:"Chiết khấu",    code:"price * (1 - discount_pct / 100)",                            desc:"Áp dụng % chiết khấu" },
  { title:"Rẽ nhánh",      code:"IF(condition, value_if_true, value_if_false)",                 desc:"Công thức có điều kiện" },
  { title:"Giới hạn",      code:"clamp(value, min_val, max_val)",                              desc:"Kẹp giá trị trong khoảng" },
  { title:"Lợi nhuận %",   code:"round((revenue - cost) / cost * 100, 2)",                     desc:"Tỷ lệ lợi nhuận" },
  { title:"Ngày đến hạn",  code:"date_add(posting_date, payment_days)",                        desc:"Tính ngày thanh toán" },
  { title:"Coalesce",      code:"coalesce(override_price, default_price, 0)",                   desc:"Fallback an toàn" },
  { title:"Giá trị mới",   code:"last(rows, sort_by='date', value_key='weight')",              desc:"Giá trị mới nhất" },
];

const FB_TEMPLATES = [
  {
    category:"🏗️ Nhôm Kính",
    templates:[
      { icon:"📐", name:"Diện tích cửa",        code:"(custom_width_mm / 1000) * (custom_height_mm / 1000)",                    desc:"Tính m² từ mm" },
      { icon:"🪟", name:"Số thanh nhôm",         code:"round((custom_width_mm / 1000) / $BUOC_KHUNG, 0) + 1",                   desc:"Theo bước khung" },
      { icon:"💰", name:"Thành tiền có VAT",      code:"qty * rate * (1 + $VAT_RATE / 100)",                                      desc:"Giá × SL × (1+thuế)" },
      { icon:"🔢", name:"DT × đơn giá",           code:"(custom_width_mm/1000) * (custom_height_mm/1000) * rate",                desc:"DT × đơn giá" },
      { icon:"📏", name:"Chu vi cửa (mm)",        code:"2 * (custom_width_mm + custom_height_mm)",                                desc:"Perimeter" },
      { icon:"🪤", name:"Độ dày → loại",          code:"IFS(do_day > 70, 'dày', do_day > 50, 'vừa', True, 'mỏng')",            desc:"Phân loại theo độ dày" },
    ],
  },
  {
    category:"💼 Kế Toán / Bán Hàng",
    templates:[
      { icon:"💵", name:"Giá sau CK + VAT",       code:"price * (1 - discount/100) * (1 + $VAT_RATE/100)",                       desc:"Full pricing pipeline" },
      { icon:"📊", name:"Lợi nhuận gộp (%)",      code:"safe_div(revenue - cost, revenue, 0) * 100",                             desc:"Gross margin %" },
      { icon:"📅", name:"Ngày thanh toán",         code:"date_add(posting_date, payment_days)",                                   desc:"Due date" },
      { icon:"🔄", name:"Cross-line ref",           code:"items.canh_trai.qty * items.canh_trai.rate",                            desc:"Tham chiếu dòng khác" },
      { icon:"∑",  name:"Tổng nhiều dòng",          code:"items.canh_trai.amount + items.canh_phai.amount",                       desc:"Sum cross-lines" },
      { icon:"🎯", name:"Giá fallback",             code:"coalesce(custom_override_rate, rate, 0)",                               desc:"Giá ưu tiên override" },
    ],
  },
  {
    category:"🧮 Toán Học Thông Dụng",
    templates:[
      { icon:"📦", name:"Làm tròn VNĐ",           code:"round(amount, -3)",                                                      desc:"Tròn nghìn đồng" },
      { icon:"🔒", name:"Chia an toàn",            code:"safe_div(numerator, denominator, 0)",                                   desc:"Không lỗi /0" },
      { icon:"📈", name:"Tăng trưởng (%)",          code:"safe_div(current - previous, previous, 0) * 100",                      desc:"YoY / MoM growth" },
      { icon:"⚖️", name:"Trọng số",                 code:"round(percent_of(part, total), 2)",                                    desc:"% của tổng" },
    ],
  },
  {
    category:"📋 Dữ Liệu / Mảng",
    templates:[
      { icon:"🔍", name:"Lọc dòng > 100",          code:"filter_array(rows, '>', 100, key='amount')",                            desc:"Filter mảng" },
      { icon:"⬆️", name:"Giá trị mới nhất",         code:"last(rows, sort_by='posting_date', value_key='rate')",                 desc:"Latest record" },
      { icon:"📊", name:"Tổng theo nhóm",           code:"group_sum(rows, 'loai_vt', 'so_luong')",                               desc:"Group + sum" },
      { icon:"🔤", name:"Danh sách duy nhất",       code:"unique(map_key(rows, 'item_code'))",                                   desc:"Distinct values" },
    ],
  },
];

const FB_SHORTCUTS = [
  { section:"Chạy & Lưu" },
  { desc:"Chạy thử công thức",         keys:["Ctrl","Enter"] },
  { desc:"Lưu công thức",              keys:["Ctrl","S"] },
  { section:"Editor" },
  { desc:"Format công thức",           keys:["Alt","F"] },
  { desc:"Toggle multi-line",          keys:["Alt","M"] },
  { desc:"Copy công thức",             keys:["Alt","C"] },
  { desc:"Undo",                       keys:["Ctrl","Z"] },
  { desc:"Redo",                       keys:["Ctrl","Y"] },
  { section:"Sidebar & Tìm kiếm" },
  { desc:"Tìm biến/hàm",              keys:["Ctrl","P"] },
  { desc:"Reload context",             keys:["Alt","R"] },
  { section:"Giao diện" },
  { desc:"Xem shortcuts",              keys:["Ctrl","?"] },
  { desc:"Gợi ý công thức",           keys:["Alt","G"] },
  { desc:"Giải thích từng bước",       keys:["Alt","E"] },
  { section:"Editor nâng cao" },
  { desc:"Tìm & Thay thế",            keys:["Ctrl","H"] },
  { desc:"So sánh công thức (Diff)",   keys:["Diff","Button"] },
  { desc:"Test với biến",              keys:["Alt","T"] },
];

const TYPE_ICON = {
  var:     { cls:"afb-type-var",     icon:"V" },
  func:    { cls:"afb-type-func",    icon:"ƒ" },
  field:   { cls:"afb-type-field",   icon:"⊞" },
  const:   { cls:"afb-type-const",   icon:"#" },
  ref:     { cls:"afb-type-ref",     icon:"→" },
  snip:    { cls:"afb-type-snip",    icon:"✦" },
  sibling: { cls:"afb-type-sibling", icon:"↔" },
};

// ═══════════════════════════════════════════════════════════════════════════
// §3  FunctionRegistry  (register/merge, không override toàn bộ)
// ═══════════════════════════════════════════════════════════════════════════
class _FunctionRegistry {
  constructor() {
    this._base = [...FB_FUNCTIONS];
    this._ext  = new Map();
    this._snippets  = [...FB_SNIPPETS];
    this._templates = [...FB_TEMPLATES];
  }
  /** Đăng ký 1 hàm (override nếu trùng tên, thêm mới nếu chưa có) */
  register(fn) { this._ext.set(fn.name, fn); }
  registerAll(fns) { fns.forEach(f => this.register(f)); }
  unregister(name) { this._ext.delete(name); }
  /** Merge: ext ghi đè base theo tên */
  getAll() {
    if (!this._ext.size) return this._base;
    const map = new Map(this._base.map(f => [f.name, f]));
    this._ext.forEach((f, k) => map.set(k, f));
    return [...map.values()];
  }
  find(name) { return this._ext.get(name) || this._base.find(f => f.name === name) || null; }
  addSnippet(s)     { this._snippets.push(s); }
  getSnippets()     { return this._snippets; }
  addTemplate(section, t) {
    const sec = this._templates.find(s => s.category === section);
    if (sec) sec.templates.push(t);
    else this._templates.push({ category: section, templates: [t] });
  }
  getTemplates()    { return this._templates; }
}

aluglass.formula.FunctionRegistry = new _FunctionRegistry();

// ═══════════════════════════════════════════════════════════════════════════
// §4  ContextCache  (TTL 30s)
// ═══════════════════════════════════════════════════════════════════════════
aluglass.formula.ContextCache = (() => {
  const _store  = new Map();
  const TTL_MS  = 30_000;
  const key = (dt, dn) => `${dt||""}::${dn||""}`;
  return {
    get(doctype, docname) {
      const e = _store.get(key(doctype, docname));
      if (!e) return null;
      if (Date.now() - e.ts > TTL_MS) { _store.delete(key(doctype, docname)); return null; }
      return e.data;
    },
    set(doctype, docname, data) { _store.set(key(doctype, docname), { data, ts:Date.now() }); },
    invalidate(doctype, docname) {
      if (docname) { _store.delete(key(doctype, docname)); }
      else { for (const k of _store.keys()) { if (k.startsWith(`${doctype}::`)) _store.delete(k); } }
    },
    clear() { _store.clear(); },
    get size() { return _store.size; },
    /** Merge child fields into existing cache entry */
    mergeChildFields(doctype, fields) {
      for (const [k, e] of _store.entries()) {
        if (k.startsWith(`${doctype}::`)) {
          e.data.child_fields = [...new Set([...(e.data.child_fields||[]), ...fields])];
        }
      }
    },
  };
})();

// ═══════════════════════════════════════════════════════════════════════════
// §5  CompletionRegistry  (singleton WeakMap, no memory leak)
// ═══════════════════════════════════════════════════════════════════════════
aluglass.formula.CompletionRegistry = (() => {
  const _langDisposables = new Map();
  const _handlers = new WeakMap();
  const _activeModels = new Set();

  function _ensureRegistration(languageId) {
    if (_langDisposables.has(languageId)) return;
    if (typeof monaco === "undefined") return;
    const disposable = monaco.languages.registerCompletionItemProvider(languageId, {
      triggerCharacters: [".", "[", "$", "(", ",", " "],
      provideCompletionItems(model, pos) {
        const handler = _handlers.get(model);
        if (!handler) return { suggestions: [] };
        try { return handler(model, pos) || { suggestions: [] }; }
        catch (e) { console.warn("[CompletionRegistry] handler error:", e); return { suggestions: [] }; }
      },
    });
    _langDisposables.set(languageId, disposable);
  }

  return {
    register(model, handlerFn, languageId = "aluglass-formula") {
      if (!model || typeof handlerFn !== "function") return;
      if (window.monaco) _ensureRegistration(languageId);
      _handlers.set(model, handlerFn);
      _activeModels.add(model);
      const sub = model.onWillDispose(() => {
        _handlers.delete(model); _activeModels.delete(model); sub.dispose();
      });
    },
    unregister(model) { if (!model) return; _handlers.delete(model); _activeModels.delete(model); },
    ensureLanguage(languageId = "aluglass-formula") { if (window.monaco) _ensureRegistration(languageId); },
    get activeCount() { return _activeModels.size; },
  };
})();

// ═══════════════════════════════════════════════════════════════════════════
// §6  ContextBuilder  (parent + current_row + siblings + global + refs)
// ═══════════════════════════════════════════════════════════════════════════
const _ContextBuilder = {
  _SKIP: new Set(["Section Break","Column Break","Tab Break","Heading","Button",
                  "Image","Attach","Attach Image","Barcode","Signature",
                  "Table","Table MultiSelect"]),

  /**
   * @param {{ frm, childTableField?, cdn?, liveCtx? }} params
   */
  build({ frm, childTableField, cdn, liveCtx } = {}) {
    const SKIP = this._SKIP;
    const parentMeta = frappe.get_meta?.(frm?.doctype);

    // 1. Fields doctype mẹ – kèm notation "tableName[0].field" cho child tables
    const parentFields = (parentMeta?.fields || [])
      .filter(mf => !SKIP.has(mf.fieldtype))
      .map(mf => ({
        name:      mf.fieldname,
        label:     mf.label || mf.fieldname,
        fieldtype: mf.fieldtype,
        doctype:   frm?.doctype,
        source:    "parent",
        value:     frm?.doc?.[mf.fieldname],
        insert:    mf.fieldname,
      }));

    // 2. Fields row hiện tại (nếu trong child table)
    let currentRowFields = [];
    let childDoctype = null;
    if (childTableField && cdn && frm) {
      childDoctype = parentMeta?.fields
        ?.find(f => f.fieldname === childTableField)?.options;
      if (childDoctype) {
        const childMeta = frappe.get_meta?.(childDoctype);
        const row = (frm.doc?.[childTableField] || []).find(r => r.name === cdn) || {};
        currentRowFields = (childMeta?.fields || [])
          .filter(mf => !SKIP.has(mf.fieldtype))
          .map(mf => ({
            name:      mf.fieldname,
            label:     mf.label || mf.fieldname,
            fieldtype: mf.fieldtype,
            doctype:   childDoctype,
            source:    "current_row",
            value:     row[mf.fieldname],
            insert:    mf.fieldname,
            rowName:   cdn,
          }));
      }
    }

    // 3. Sibling child tables → tableName[idx].field  +  tableName[0].field (chuẩn)
    const siblingItems = [];
    if (frm) {
      (parentMeta?.fields || [])
        .filter(mf => (mf.fieldtype === "Table" || mf.fieldtype === "Table MultiSelect"))
        .forEach(tableMf => {
          const tblField   = tableMf.fieldname;
          const tblDoctype = tableMf.options;
          const tblMeta    = frappe.get_meta?.(tblDoctype);
          const rows       = frm.doc?.[tblField] || [];
          const cfNames    = (tblMeta?.fields || []).filter(f => !SKIP.has(f.fieldtype));

          const rowCount = rows.length || 1;
          for (let idx = 0; idx < Math.min(rowCount, 30); idx++) {
            const row = rows[idx] || {};
            cfNames.forEach(cf => {
              siblingItems.push({
                name:      `${tblField}[${idx}].${cf.fieldname}`,
                label:     `${cf.label || cf.fieldname} — hàng ${idx + 1}`,
                fieldtype: cf.fieldtype,
                doctype:   tblDoctype,
                source:    tblField === childTableField ? "current_table" : "sibling_table",
                value:     row[cf.fieldname],
                insert:    `${tblField}[${idx}].${cf.fieldname}`,
                tableName: tblField,
                rowIdx:    idx,
                rowName:   row.name,
              });
            });
          }
        });
    }

    // 4. Global vars từ live context
    const globalVars = (liveCtx?.variables || [])
      .filter(v => v?.source === "global")
      .map(v => ({
        name:      "$" + v.name,
        label:     v.label || v.name,
        fieldtype: "Currency / Data",
        doctype:   "Global Variable",
        source:    "global",
        value:     v.value,
        insert:    "$" + v.name,
      }));

    // 5. References (line refs)
    const refs = (liveCtx?.references || []).map(r => ({
      name:    r.name,
      label:   r.label || r.name,
      doctype: r.doctype || "Reference",
      source:  "ref",
      value:   null,
      insert:  r.name,
    }));

    // 6. Local vars (non-global từ live context)
    const localVars = (liveCtx?.variables || [])
      .filter(v => v?.source !== "global")
      .map(v => ({
        name:      v.name,
        label:     v.label || v.name,
        fieldtype: v.field_type || v.type || "Data",
        doctype:   v.doctype || frm?.doctype,
        source:    "local",
        value:     v.value,
        insert:    v.name,
      }));

    return {
      parentFields, currentRowFields, siblingItems,
      globalVars, refs, localVars,
      allItems: [...currentRowFields, ...localVars, ...parentFields, ...siblingItems, ...globalVars, ...refs],
    };
  },
};

// ═══════════════════════════════════════════════════════════════════════════
// §7  CompletionProvider v3 — metadata đầy đủ, smart trigger
// ═══════════════════════════════════════════════════════════════════════════

/** Documentation string đầy đủ cho 1 variable item */
function _buildVarDoc(item) {
  const lines = [
    `**${item.name}**`,
    (item.label && item.label !== item.name) ? `_${item.label}_` : "",
    "",
    "| Thuộc tính | Giá trị |",
    "|---|---|",
    `| Doctype | \`${item.doctype || "—"}\` |`,
    `| Kiểu dữ liệu | \`${item.fieldtype || "—"}\` |`,
    `| Nguồn | \`${item.source || "—"}\` |`,
    item.value != null ? `| Giá trị hiện tại | \`${String(item.value).substring(0, 80)}\` |` : "",
    item.rowName ? `| Row | \`${item.rowName}\` |` : "",
  ].filter(Boolean);
  return lines.join("\n");
}

function _buildCompletionHandler(editorRef, contextFn) {
  const mk = () => (window.monaco ? window.monaco.languages.CompletionItemKind : {});

  return function(model, pos) {
    if (model !== editorRef.getModel?.()) return { suggestions: [] };
    const MK = mk();
    const word       = model.getWordUntilPosition(pos);
    const lineBefore = model.getLineContent(pos.lineNumber).substring(0, pos.column);
    const range = {
      startLineNumber: pos.lineNumber, endLineNumber: pos.lineNumber,
      startColumn: word.startColumn,   endColumn: pos.column,
    };

    const ctx    = contextFn ? contextFn() : { allItems:[], currentRowFields:[], siblingItems:[], globalVars:[], parentFields:[], refs:[], localVars:[] };
    const fnReg  = aluglass.formula.FunctionRegistry;
    const seen   = new Set();
    const items  = [];
    const add = item => { if (!seen.has(item.label)) { seen.add(item.label); items.push({ range, ...item }); } };

    // TRIGGER: `tableName[N].` → fields của bảng đó
    const tblDotMatch = lineBefore.match(/(\w+)\[\d+\]\.$/);
    if (tblDotMatch) {
      const tblName = tblDotMatch[1];
      ctx.siblingItems
        .filter(s => s.tableName === tblName)
        .forEach(s => add({
          label: s.name.split(".").pop(),
          kind: MK.Field,
          insertText: s.name.split(".").pop(),
          detail: `${s.fieldtype} · ${s.doctype} · hàng ${(s.rowIdx||0)+1}`,
          documentation: _buildVarDoc(s),
          sortText: "0_" + s.name,
        }));
      return { suggestions: items };
    }

    // TRIGGER: `word.` → child fields
    const plainDotMatch = lineBefore.match(/(\w+)\.$/);
    if (plainDotMatch) {
      ctx.allItems.forEach(s => add({
        label: s.name,
        kind: MK.Field,
        insertText: s.insert,
        detail: `${s.fieldtype||""} · ${s.doctype||""}`,
        documentation: _buildVarDoc(s),
        sortText: "0_" + s.name,
      }));
      return { suggestions: items };
    }

    // TRIGGER: `tableName[` → suggest row indices
    const tblIdxMatch = lineBefore.match(/(\w+)\[$/);
    if (tblIdxMatch) {
      const tblName = tblIdxMatch[1];
      const indices = [...new Set(ctx.siblingItems.filter(s => s.tableName === tblName).map(s => s.rowIdx))];
      if (!indices.length) indices.push(0);
      indices.forEach(idx => add({
        label: String(idx),
        kind: MK.Value,
        insertText: String(idx),
        detail: `Hàng ${idx+1}`,
        sortText: "0i_" + idx,
      }));
      return { suggestions: items };
    }

    // 1. Fields row hiện tại (priority cao nhất)
    ctx.currentRowFields.forEach(f => add({
      label: f.name, kind: MK.Field, insertText: f.insert,
      detail: `${f.fieldtype} · ${f.doctype} (hàng hiện tại)`,
      documentation: _buildVarDoc(f), sortText: "1_" + f.name,
    }));

    // 2. Keywords
    ["IF","IFS","IIF","SWITCH","and_","or_","not_","True","False","None","in"]
      .forEach(kw => add({ label:kw, kind:MK.Keyword, insertText:kw, sortText:"2k_"+kw }));

    // 3. Hàm (từ FunctionRegistry)
    fnReg.getAll().forEach(f => {
      if (seen.has(f.name)) return;
      add({
        label: f.name, kind: MK.Function,
        insertText: f.name + "($1)",
        insertTextRules: window.monaco?.languages.CompletionItemInsertTextRule?.InsertAsSnippet,
        documentation: `**${f.sig}**\n\n${f.desc}\n\n_Ví dụ: ${f.example}_`,
        detail: `ƒ ${f.cat}`,
        sortText: "3_" + f.name,
      });
    });

    // 4. Global vars $VAR
    const isGlobalCtx = lineBefore.endsWith("$") || word.word.startsWith("$");
    ctx.globalVars.forEach(v => add({
      label: v.name, kind: MK.Variable, insertText: v.insert,
      detail: `🌍 Global · ${v.value != null ? v.value : "—"}`,
      documentation: _buildVarDoc(v),
      sortText: (isGlobalCtx ? "1g_" : "4g_") + v.name,
    }));

    // 5. Local vars
    ctx.localVars.forEach(v => add({
      label: v.name, kind: MK.Field, insertText: v.insert,
      detail: `${v.fieldtype} · ${v.doctype} · ${v.value != null ? v.value : "—"}`,
      documentation: _buildVarDoc(v), sortText: "4l_" + v.name,
    }));

    // 6. Fields doctype mẹ
    ctx.parentFields.forEach(f => add({
      label: f.name, kind: MK.Field, insertText: f.insert,
      detail: `${f.fieldtype} · ${f.doctype}`,
      documentation: _buildVarDoc(f), sortText: "5_" + f.name,
    }));

    // 7. Sibling tables tableName[idx].field
    ctx.siblingItems.slice(0, 30).forEach(s => add({
      label: s.name, kind: MK.Field, insertText: s.insert,
      detail: `${s.fieldtype} · ${s.doctype} · hàng ${(s.rowIdx||0)+1}`,
      documentation: _buildVarDoc(s), sortText: "6_" + s.name,
    }));

    // 8. References
    ctx.refs.forEach(r => add({
      label: r.name, kind: MK.Reference, insertText: r.insert,
      detail: `🔗 ${r.doctype}`, documentation: _buildVarDoc(r), sortText: "7_" + r.name,
    }));

    // 9. Snippets
    fnReg.getSnippets().forEach(s => add({
      label: s.title, kind: MK.Snippet,
      insertText: s.code,
      insertTextRules: window.monaco?.languages.CompletionItemInsertTextRule?.InsertAsSnippet,
      detail: s.desc || "Snippet", sortText: "8_" + s.title,
    }));

    return { suggestions: items };
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// §8  AluglassFormulaEditor CLASS
// ═══════════════════════════════════════════════════════════════════════════
class AluglassFormulaEditor {
  constructor(opts) {
    this.opts = Object.assign({
      value:              "",
      height:             "480px",
      show_toolbar:       true,
      show_sidebar:       true,
      show_panel:         true,
      read_only:          false,
      current_doctype:    null,
      current_docname:    null,
      current_field:      null,
      child_table_field:  null,
      row_index:          null,
      line_ref:           null,
      formula_set_code:   null,
      field_label:        null,
      onChange:           null,
      onSave:             null,
      onValidate:         null,
    }, opts);

    this.editor          = null;
    this._liveCtx        = null;
    this._builtCtx       = null;
    this._destroyed      = false;
    this._disposables    = [];
    this._uid            = "fb_" + Math.random().toString(36).substr(2, 8);
    this._activeTab      = "global";
    this._activePanel    = "result";
    this._sbCollapsed    = {};
    this._dragGhost      = null;
    this._dragging       = false;
    this._tooltip        = null;
    this._statusTimer    = null;
    this._validTimer     = null;
    this._testRunning    = false;
    this._multiLine      = false;
    this._pinnedItems    = [];
    this._items          = {
      global: [], local: [], refs: [], funcs: [], snips: [], sibling: [],
    };
    this._history        = [];
    this._testVarRows    = [];
    this._onboardKey     = "afb_v3_onboarded";
    this._tourEscHandler = null;
    this._editorReady    = false;
    this._suppressResize = false;
    this._registeredModel= null;
  }

  _scope() {
    return {
      current_doctype:    this.opts.current_doctype,
      current_docname:    this.opts.current_docname,
      child_table_field:  this.opts.child_table_field,
      row_index:          this.opts.row_index,
      line_ref:           this.opts.line_ref,
      formula_set_code:   this.opts.formula_set_code,
    };
  }

  // _buildCtx() {
  //   return _ContextBuilder.build({
  //     frm:             { doctype: this.opts.current_doctype, doc: {}, docname: this.opts.current_docname },
  //     childTableField: this.opts.child_table_field,
  //     cdn:             this.opts.row_index,
  //     liveCtx:         this._liveCtx,
  //   });
  // }

  _buildCtx() {
    // Lấy frm thực tế từ frappe nếu có (để có giá trị live từ frm.doc)
    let liveDoc = {};
    try {
      const activeFrm = frappe.ui?.form?.get_open_form?.() ||
        (cur_frm && cur_frm.doctype === this.opts.current_doctype ? cur_frm : null);
      if (activeFrm && activeFrm.doctype === this.opts.current_doctype) {
        liveDoc = activeFrm.doc || {};
      }
    } catch {}

    return _ContextBuilder.build({
      frm: {
        doctype : this.opts.current_doctype,
        docname : this.opts.current_docname,
        doc     : liveDoc,
      },
      childTableField : this.opts.child_table_field,
      cdn             : this._resolveCdn(),
      liveCtx         : this._liveCtx,
    });
  }

  /** Resolve cdn (row name) từ row_index hoặc child_table_field */
  _resolveCdn() {
    if (!this.opts.child_table_field || this.opts.row_index == null) return null;
    try {
      const activeFrm = frappe.ui?.form?.get_open_form?.() ||
        (cur_frm && cur_frm.doctype === this.opts.current_doctype ? cur_frm : null);
      if (!activeFrm) return null;
      const rows = activeFrm.doc?.[this.opts.child_table_field] || [];
      // row_index là idx-1 (0-based), nhưng cũng thử theo .name nếu đã truyền string
      if (typeof this.opts.row_index === "string") return this.opts.row_index;
      return rows[this.opts.row_index]?.name || null;
    } catch {
      return null;
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────
  render($wrapper) {
    this.$wrapper = $wrapper;
    $wrapper.empty().html(this._buildHTML());
    this._cache();
    this._initTooltip();
    this._initDragGhost();
    if (this.opts.show_sidebar) this._initSidebar();
    if (this.opts.show_panel)   this._initPanel();
    this._initMonaco();
    this._loadLiveContext();
    this._injectSavedTemplates();
    this._bindToolbar();
    this._maybeShowWelcomeTour();
  }

  _cache() {
    this._q    = sel => this.$wrapper[0].querySelector(sel);
    this._qAll = sel => [...this.$wrapper[0].querySelectorAll(sel)];
    this.$valbar  = this.$wrapper.find(".afb-valbar");
    this.$status  = this.$wrapper.find(".afb-tb-status");
    this.$monacoContainer = this._q(`#mono-${this._uid}`);
  }

  _buildHTML() {
    const uid = this._uid;
    const h   = this.opts.height || "560px";
    let out = `<div class="afb-wrap" style="height:${h};">`;

    // Header
    out += `<div class="afb-header">
      <div class="afb-logo">
        <div class="afb-logo-icon">ƒ</div>
        <span class="afb-logo-text">Formula Builder</span>
        <span style="font-size:10px;color:var(--afb-text3);background:var(--afb-bg3);padding:2px 6px;border-radius:3px;margin-left:4px">v3</span>
      </div>
      <div class="afb-header-meta">
        ${this.opts.formula_set_code ? `<span class="afb-badge">📋 ${_esc(this.opts.formula_set_code)}</span>` : ""}
        ${this.opts.current_doctype  ? `<span class="afb-badge">${_esc(this.opts.current_doctype)}${this.opts.current_docname ? " · " + _esc(this.opts.current_docname) : ""}</span>` : ""}
        ${this.opts.field_label      ? `<span class="afb-badge" style="color:var(--afb-purple)">${_esc(this.opts.field_label)}</span>` : ""}
      </div>
    </div>`;

    // Toolbar
    if (this.opts.show_toolbar) {
      out += `<div class="afb-toolbar">
        <button class="afb-btn primary afb-act-test"         title="Chạy thử (Ctrl+Enter)">▶</button>
        <div class="afb-btn-sep"></div>
        <button class="afb-btn afb-act-format"               title="Format (Alt+F)">⇄</button>
        <button class="afb-btn afb-act-multiline"            title="Toggle multi-line (Alt+M)">↕</button>
        <button class="afb-btn afb-act-explain"              title="Giải thích (Alt+E)">📊</button>
        <button class="afb-btn afb-act-testvars"             title="Test với biến (Alt+T)">🧪</button>
        <button class="afb-btn afb-act-ctx"                  title="Xem context">🌐</button>
        <button class="afb-btn afb-act-reload-ctx"           title="Reload context (Alt+R)">🔄</button>
        <div class="afb-btn-sep"></div>
        <button class="afb-btn afb-act-copy-formula"         title="Copy (Alt+C)">📋</button>
        <button class="afb-btn suggest afb-act-suggest"      title="Gợi ý AI (Alt+G)">💡</button>
        <div class="afb-btn-sep"></div>
        <button class="afb-btn afb-act-undo"                 title="Undo">↩</button>
        <button class="afb-btn afb-act-redo"                 title="Redo">↪</button>
        <div class="afb-btn-sep"></div>
        <button class="afb-btn danger afb-act-clear"         title="Xóa">✕</button>
        <button class="afb-btn afb-act-shortcuts"            title="Phím tắt (Ctrl+?)">⌨</button>
        <button class="afb-btn afb-act-findreplace"          title="Tìm & Thay thế (Ctrl+H)">🔎</button>
        <button class="afb-btn afb-act-diff"                 title="So sánh">⊟</button>
        <button class="afb-btn afb-act-save-template"        title="Lưu mẫu">💾</button>
        <span class="afb-tb-status"></span>
      </div>`;
    }

    // Body
    out += `<div class="afb-body">`;

    // Sidebar
    if (this.opts.show_sidebar) {
      out += `<div class="afb-sidebar" id="sb-${uid}">
        <div class="afb-sb-resize" id="sbr-${uid}"></div>
        <div class="afb-sb-tabs">
          <div class="afb-sb-tab active" data-tab="global">🌍 Global</div>
          <div class="afb-sb-tab" data-tab="local">📄 Local</div>
          <div class="afb-sb-tab" data-tab="sibling">↔ Sibling</div>
          <div class="afb-sb-tab" data-tab="refs">🔗 Ref</div>
          <div class="afb-sb-tab" data-tab="funcs">ƒ Hàm</div>
          <div class="afb-sb-tab" data-tab="snips">✦ Snip</div>
          <div class="afb-sb-tab" data-tab="tmpl">🎨 Mẫu</div>
          <div class="afb-sb-tab" data-tab="pins" id="pintab-${uid}">📌 Ghim<span class="afb-sb-tab-badge" id="pinbadge-${uid}" style="display:none">0</span></div>
        </div>
        <div class="afb-sb-search">
          <span class="afb-sb-search-icon">🔍</span>
          <input type="text" placeholder="Tìm nhanh... (Ctrl+P)" class="afb-sb-q" id="sbq-${uid}" autocomplete="off">
        </div>
        <div class="afb-sb-list" id="sbl-${uid}"></div>
      </div>`;
    }

    // Editor
    out += `<div class="afb-editor-wrap">
      <div class="afb-monaco" id="mono-${uid}" style="position:relative"></div>
      <div class="afb-fnr-panel" id="fnr-${uid}" style="display:none;position:absolute;top:8px;right:8px"></div>
      <div class="afb-valbar">
        <span style="color:var(--afb-text3)">Nhập công thức để bắt đầu...</span>
      </div>
      <div class="afb-statusbar" id="sbar-${uid}">
        <span class="afb-statusbar-item" id="sbpos-${uid}">Ln 1, Col 1</span>
        <span class="afb-statusbar-sep"></span>
        <span class="afb-statusbar-item" id="sblen-${uid}">0 ký tự</span>
        <span class="afb-statusbar-sep"></span>
        <span class="afb-statusbar-item" id="sbval-${uid}">—</span>
      </div>
    </div>`;

    out += `</div>`; // end .afb-body

    // Bottom panel
    if (this.opts.show_panel) {
      out += `
      <div class="afb-panel-resize" id="prsz-${uid}"></div>
      <div class="afb-panel" id="pnl-${uid}">
        <div class="afb-panel-tabs">
          <div class="afb-panel-tab active" data-panel="result">📈 Kết quả</div>
          <div class="afb-panel-tab" data-panel="testvars">🧪 Tính thử</div>
          <div class="afb-panel-tab" data-panel="ctx">🌐 Context</div>
          <div class="afb-panel-tab" data-panel="explain">💡 Giải thích</div>
          <div class="afb-panel-tab" data-panel="debug">🐛 Debug</div>
          <div class="afb-panel-tab" data-panel="history">🕐 Lịch sử</div>
        </div>
        <div class="afb-panel-body active" data-pb="result"><span style="color:var(--afb-text3)">Nhấn ▶ hoặc Ctrl+Enter để xem kết quả.</span></div>
        <div class="afb-panel-body" data-pb="testvars"><span style="color:var(--afb-text3)">Nhấn 🧪 để test công thức với biến tuỳ chỉnh.</span></div>
        <div class="afb-panel-body" data-pb="ctx"><span style="color:var(--afb-text3)">Đang tải context...</span></div>
        <div class="afb-panel-body" data-pb="explain"><span style="color:var(--afb-text3)">Nhấn 📊 để phân tích công thức.</span></div>
        <div class="afb-panel-body" data-pb="debug"><span style="color:var(--afb-text3)">Nhấn 📊 để xem debug info.</span></div>
        <div class="afb-panel-body" data-pb="history"><span style="color:var(--afb-text3)">Chưa có lịch sử chạy.</span></div>
      </div>`;
    }

    out += `</div>`; // end .afb-wrap
    return out;
  }

  // ── Monaco ────────────────────────────────────────────────────────────────
  async _initMonaco() {
    await loadMonaco();
    if (typeof monaco === "undefined") { console.error("Monaco failed to load"); return; }

    this._registerLanguage();
    this._registerLightTheme();
    this._patchOverflowGuard();

    this.editor = monaco.editor.create(this.$monacoContainer, {
      value:                      this.opts.value || "",
      language:                   "aluglass-formula",
      theme:                      "aluglass-light",
      automaticLayout:            false,
      fontSize:                   13,
      fontFamily:                 "'JetBrains Mono','Fira Code',monospace",
      fontLigatures:              true,
      minimap:                    { enabled: false },
      scrollBeyondLastLine:       false,
      readOnly:                   this.opts.read_only,
      lineNumbers:                "on",
      glyphMargin:                true,
      folding:                    true,
      wordWrap:                   "on",
      suggestOnTriggerCharacters: true,
      quickSuggestions:           { other:true, strings:true },
      parameterHints:             { enabled:true },
      suggest:                    { preview:true, showStatusBar:false, insertMode:"replace", showIcons:true },
      suggestFontSize:            13,
      suggestLineHeight:          26,
      bracketPairColorization:    { enabled:true },
      tabCompletion:              "on",
      acceptSuggestionOnEnter:    "on",
      hover:                      { enabled:true, delay:300 },
      scrollbar:                  { alwaysConsumeMouseWheel:true, useShadows:false },
      fixedOverflowWidgets:       true,
      suggestWidgetPosition: 'below',
      // BUG FIX §2.7: padding bottom prevents suggest widget from covering last line
      padding:                    { top:8, bottom:120 },
    });

    // Hover + Signature providers
    this._disposables.push(
      monaco.languages.registerHoverProvider("aluglass-formula", {
        provideHover: (model, pos) => this._provideHover(model, pos),
      }),
      monaco.languages.registerSignatureHelpProvider("aluglass-formula", {
        signatureHelpTriggerCharacters: ["(", ","],
        provideSignatureHelp: (model, pos) => this._provideSignatureHelp(model, pos),
      }),
    );

    // CompletionRegistry (§5) — no per-instance provider, no memory leak
    const model = this.editor.getModel();
    this._registeredModel = model;
    aluglass.formula.CompletionRegistry.ensureLanguage("aluglass-formula");
    aluglass.formula.CompletionRegistry.register(
      model,
      _buildCompletionHandler(this.editor, () => this._buildCtx()),
      "aluglass-formula",
    );

    // Content change
    this._disposables.push(
      this.editor.onDidChangeModelContent(e => {
        if (this._destroyed) return;
        const val = this.getValue();
        if (this.opts.onChange) this.opts.onChange(val);
        this._updateStatusLen(val);
        clearTimeout(this._validTimer);
        this._validTimer = setTimeout(() => {
          if (!this._destroyed) {
            if (val.trim()) this._runValidation(val);
            else this.$valbar.html(`<span style="color:var(--afb-text3)">Nhập công thức để bắt đầu...</span>`);
          }
        }, 400);
        // Auto-trigger on $
        if (e.changes.some(c => c.text === "$")) {
          setTimeout(() => { if (!this._destroyed && this.editor) this.editor.trigger("kbd","editor.action.triggerSuggest",{}); }, 80);
        }
      }),
      this.editor.onDidChangeCursorPosition(e => {
        const sbpos = this._q(`#sbpos-${this._uid}`);
        if (sbpos) sbpos.textContent = `Ln ${e.position.lineNumber}, Col ${e.position.column}`;
      }),
    );

    // Keyboard commands
    const KC = monaco.KeyCode, KM = monaco.KeyMod;
    this.editor.addCommand(KM.CtrlCmd | KC.KeyS, () => { if (this.opts.onSave) this.opts.onSave(this.getValue()); });
    this.editor.addCommand(KM.CtrlCmd | KC.KeyP, () => { this._q("#sbq-" + this._uid)?.focus(); });
    this.editor.addCommand(KM.Alt    | KC.KeyF,  () => { this._actFormat(); });
    this.editor.addCommand(KM.CtrlCmd| KC.Enter, () => { this._actTest(); });
    this.editor.addCommand(KM.Alt    | KC.KeyM,  () => { this._actToggleMultiLine(); });
    this.editor.addCommand(KM.Alt    | KC.KeyC,  () => { this._actCopyFormula(); });
    this.editor.addCommand(KM.Alt    | KC.KeyR,  () => { this._actReloadContext(); });
    this.editor.addCommand(KM.Alt    | KC.KeyG,  () => { this._actSmartSuggest(); });
    this.editor.addCommand(KM.Alt    | KC.KeyE,  () => { this._actExplain(); });
    this.editor.addCommand(KM.Alt    | KC.KeyT,  () => { this._actTestWithVars(); });
    this.editor.addCommand(KM.CtrlCmd| KM.Shift | KC.Slash, () => { this._actShowShortcuts(); });
    this.editor.addCommand(KM.CtrlCmd| KC.KeyH,  () => { this._actToggleFindReplace(); });

    this._initDragAndDrop();
    this._initPanelResize();

    // ResizeObserver for layout
    if (typeof ResizeObserver !== "undefined" && this.$monacoContainer) {
      this._resizeObserver = new ResizeObserver(() => {
        if (this.editor && !this._destroyed && !this._suppressResize) {
          this.editor.layout();
        }
      });
      this._resizeObserver.observe(this.$monacoContainer);
      this._disposables.push({ dispose: () => this._resizeObserver?.disconnect() });
    }

    this._updateStatusLen(this.opts.value || "");
    this._editorReady = true;
  }

  _patchOverflowGuard() {
    requestAnimationFrame(() => {
      const guard = this.$monacoContainer?.querySelector(".overflow-guard");
      if (!guard) return;
      guard.style.overflow = "visible";
      const obs = new MutationObserver(() => { if (guard.style.overflow !== "visible") guard.style.overflow = "visible"; });
      obs.observe(guard, { attributes:true, attributeFilter:["style"] });
      this._disposables.push({ dispose: () => obs.disconnect() });
    });
  }

  _registerLightTheme() {
    if (window._afbLightTheme) return;
    window._afbLightTheme = true;
    monaco.editor.defineTheme("aluglass-light", {
      base: "vs", inherit: true,
      rules: [
        { token:"keyword",   foreground:"c026d3", fontStyle:"bold" },
        { token:"type",      foreground:"2563eb", fontStyle:"bold" },
        { token:"identifier",foreground:"1e293b" },
        { token:"variable",  foreground:"8b5cf6", fontStyle:"bold" },
        { token:"string",    foreground:"059669" },
        { token:"number",    foreground:"ea580c" },
        { token:"comment",   foreground:"64748b", fontStyle:"italic" },
        { token:"operator",  foreground:"0f172a" },
        { token:"delimiter", foreground:"475569" },
      ],
      colors: {
        "editor.background":                "#ffffff",
        "editor.foreground":                "#1e293b",
        "editorLineNumber.foreground":      "#94a3b8",
        "editorLineNumber.activeForeground":"#f59e0b",
        "editor.selectionBackground":       "#cbd5e180",
        "editor.lineHighlightBackground":   "#f1f5f9",
        "editorCursor.foreground":          "#f59e0b",
      },
    });
    monaco.editor.setTheme("aluglass-light");
  }

  _registerLanguage() {
    if (monaco.languages.getLanguages().some(l => l.id === "aluglass-formula")) return;
    monaco.languages.register({ id: "aluglass-formula" });
    const builtins = aluglass.formula.FunctionRegistry.getAll().map(f => f.name);
    monaco.languages.setMonarchTokensProvider("aluglass-formula", {
      keywords: ["if","iff","and","or","not","true","false","null","in","IF","IFS","IIF","SWITCH","True","False","None"],
      builtins,
      operators: ["+","-","*","/","%","**","==","!=","<",">","<=",">="],
      tokenizer: {
        root: [
          [/\$[a-zA-Z_]\w*/, "variable"],
          [/[a-zA-Z_]\w*/, { cases: { "@keywords":"keyword", "@builtins":"type", "@default":"identifier" } }],
          [/"([^"\\]|\\.)*"/, "string"],
          [/'([^'\\]|\\.)*'/, "string"],
          [/#[^\n]*/, "comment"],
          [/\/\/[^\n]*/, "comment"],
          [/\d+\.?\d*([eE][+-]?\d+)?/, "number"],
          [/[+\-*/%<>=!&|^~?:]/, "operator"],
          [/[()[\],.]/, "delimiter"],
        ],
      },
    });
  }

  _provideHover(model, pos) {
    const word = model.getWordAtPosition(pos);
    if (!word) return null;
    // Check functions
    const fn = aluglass.formula.FunctionRegistry.find(word.word);
    if (fn) {
      return {
        range: new monaco.Range(pos.lineNumber, word.startColumn, pos.lineNumber, word.endColumn),
        contents: [{ value:`**${fn.sig}**` }, { value:`${fn.desc}\n\n_${fn.example}_` }],
      };
    }
    // Check variables
    const ctx = this._buildCtx();
    let varName = word.word;
    if (varName.startsWith("$")) varName = varName.slice(1);
    const item = ctx.allItems.find(i => i.name === word.word || i.name === "$"+varName || i.insert === word.word);
    if (item) {
      return {
        range: new monaco.Range(pos.lineNumber, word.startColumn, pos.lineNumber, word.endColumn),
        contents: [
          { value: `**${item.name}** · _${item.source || "—"}_` },
          { value: `| Thuộc tính | Giá trị |\n|---|---|\n| Doctype | \`${item.doctype||"—"}\` |\n| Kiểu | \`${item.fieldtype||"—"}\` |\n| Giá trị | \`${item.value != null ? item.value : "null"}\` |` },
        ],
      };
    }
    return null;
  }

  _provideSignatureHelp(model, pos) {
    const text = model.getValueInRange({ startLineNumber:pos.lineNumber, startColumn:1, endLineNumber:pos.lineNumber, endColumn:pos.column });
    const match = text.match(/(\w+)\s*\([^)]*$/);
    if (!match) return null;
    const fn = aluglass.formula.FunctionRegistry.find(match[1]);
    if (!fn) return null;
    const params = fn.sig.match(/\(([^)]+)\)/)?.[1]?.split(",").map(p => ({ label:p.trim() })) || [];
    const commas = (text.split(match[0])[1] || "").split(",").length - 1;
    const active = Math.min(commas, params.length - 1);
    return {
      value: { signatures:[{ label:fn.sig, documentation:fn.desc, parameters:params, activeParameter:active }], activeSignature:0, activeParameter:active },
      dispose: () => {},
    };
  }

  _updateStatusLen(val) {
    const el = this._q(`#sblen-${this._uid}`);
    if (el) el.textContent = `${val.length} ký tự · ${val.split("\n").length} dòng`;
  }

  // ── Drag & Drop ──────────────────────────────────────────────────────────
  _initDragAndDrop() {
    const self = this;
    this.$wrapper.on("dragstart.afb", ".afb-sb-item", function(e) {
      const text = this.dataset.token || this.querySelector(".afb-sb-item-name").textContent.trim();
      e.originalEvent.dataTransfer.setData("text/plain", text);
      e.originalEvent.dataTransfer.setData("afb/token", text);
      e.originalEvent.dataTransfer.effectAllowed = "copy";
      self._showDragGhost(text);
      this.classList.add("drag-source");
    });
    this.$wrapper.on("dragend.afb", ".afb-sb-item", function() {
      this.classList.remove("drag-source");
      self._hideDragGhost();
    });
    const container = this.$monacoContainer;
    if (!container) return;
    container.addEventListener("dragover", e => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; container.classList.add("drag-over"); });
    container.addEventListener("dragleave", () => container.classList.remove("drag-over"));
    container.addEventListener("drop", e => {
      e.preventDefault(); container.classList.remove("drag-over"); self._hideDragGhost();
      const text = e.dataTransfer.getData("afb/token") || e.dataTransfer.getData("text/plain");
      if (!text || !self.editor) return;
      const p = self.editor.getPosition();
      self.editor.executeEdits("drag-drop", [{ range: new monaco.Range(p.lineNumber, p.column, p.lineNumber, p.column), text: text + " ", forceMoveMarkers:true }]);
      self.editor.focus();
    });
  }

  // ── Panel Resize ──────────────────────────────────────────────────────────
  _initPanelResize() {
    const uid = this._uid;
    const rsz = this._q(`#prsz-${uid}`);
    const pnl = this._q(`#pnl-${uid}`);
    if (!rsz || !pnl) return;
    let startY, startH;
    const onDown = e => { startY = e.clientY; startH = pnl.offsetHeight; document.addEventListener("mousemove", onMove); document.addEventListener("mouseup", onUp); document.body.style.cursor = "row-resize"; document.body.style.userSelect = "none"; };
    const onMove = e => { const newH = Math.min(400, Math.max(80, startH + (startY - e.clientY))); pnl.style.flexBasis = newH + "px"; pnl.querySelectorAll(".afb-panel-body").forEach(el => { el.style.height = Math.max(40, newH - 40) + "px"; }); };
    const onUp   = () => { document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); document.body.style.cursor = ""; document.body.style.userSelect = ""; };
    rsz.addEventListener("mousedown", onDown);
  }

  // ── Sidebar ──────────────────────────────────────────────────────────────
  _initSidebar() {
    const uid = this._uid;
    this.$wrapper.on("click.afb", ".afb-sb-tab", e => this._switchSbTab($(e.currentTarget).data("tab")));
    this.$wrapper.on("input.afb", `#sbq-${uid}`, () => this._renderSbItems(this._q(`#sbq-${uid}`)?.value?.toLowerCase() || ""));
    this.$wrapper.on("click.afb", ".afb-sb-group-head", e => {
      const grp = $(e.currentTarget).closest(".afb-sb-group");
      const key = grp.data("grp");
      this._sbCollapsed[key] = !this._sbCollapsed[key];
      grp.toggleClass("collapsed", !!this._sbCollapsed[key]);
    });
    this._initSbResize();
    this.$wrapper.on("keydown.afb", e => { if ((e.ctrlKey || e.metaKey) && e.key === "p") { e.preventDefault(); this._q(`#sbq-${uid}`)?.focus(); } });
    this._renderSbItems();
  }

  _initSbResize() {
    const uid = this._uid, sb = this._q(`#sb-${uid}`), rsz = this._q(`#sbr-${uid}`);
    if (!rsz || !sb) return;
    let startX, startW;
    const onDown = e => { startX = e.clientX; startW = sb.offsetWidth; document.addEventListener("mousemove", onMove); document.addEventListener("mouseup", onUp); document.body.style.cursor = "col-resize"; document.body.style.userSelect = "none"; };
    const onMove = e => { sb.style.width = Math.min(400, Math.max(180, startW + (e.clientX - startX))) + "px"; };
    const onUp   = () => { document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); document.body.style.cursor = ""; document.body.style.userSelect = ""; };
    rsz.addEventListener("mousedown", onDown);
  }

  _switchSbTab(tab) {
    this._activeTab = tab;
    this._qAll(".afb-sb-tab").forEach(el => el.classList.toggle("active", el.dataset.tab === tab));
    this._renderSbItems();
  }

  _renderSbItems(query = "") {
    const list = this._q(`#sbl-${this._uid}`);
    if (!list) return;
    const prevScroll = list.scrollTop;

    if (this._activeTab === "snips") { list.innerHTML = this._buildSnipGrid(query); this._bindSnipClicks(list); list.scrollTop = prevScroll; return; }
    if (this._activeTab === "tmpl")  { list.innerHTML = this._buildTmplGallery(query); this._bindTmplClicks(list); list.scrollTop = prevScroll; return; }
    if (this._activeTab === "pins")  { this._renderPinTab(list, query); list.scrollTop = prevScroll; return; }

    const allItems = this._getTabItems(this._activeTab);
    const filtered = query ? allItems.filter(i => i.name?.toLowerCase().includes(query) || i.desc?.toLowerCase().includes(query) || i.cat?.toLowerCase().includes(query)) : allItems;

    if (!filtered.length) { list.innerHTML = `<div style="padding:20px;text-align:center;color:var(--afb-text3);font-size:12px">Không tìm thấy</div>`; list.scrollTop = prevScroll; return; }

    if (query) {
      list.innerHTML = filtered.map(i => this._buildItemHTML(i)).join("");
    } else {
      const groups = {};
      filtered.forEach(i => { const g = i.cat || "Khác"; if (!groups[g]) groups[g] = []; groups[g].push(i); });
      list.innerHTML = Object.entries(groups).map(([gname, items]) => {
        const key = this._activeTab + "_" + gname;
        const collapsed = !!this._sbCollapsed[key];
        return `<div class="afb-sb-group${collapsed ? " collapsed" : ""}" data-grp="${key}">
          <div class="afb-sb-group-head"><span class="afb-sb-group-toggle">▾</span>${_esc(gname)}<span style="margin-left:auto;color:var(--afb-text3)">${items.length}</span></div>
          <div class="afb-sb-group-items">${items.map(i => this._buildItemHTML(i)).join("")}</div>
        </div>`;
      }).join("");
    }
    this._bindSbItemEvents(list);
    list.scrollTop = prevScroll;
  }

  _getTabItems(tab) {
    if (tab === "funcs") {
      const seen = new Set();
      return aluglass.formula.FunctionRegistry.getAll().filter(f => { if (seen.has(f.name)) return false; seen.add(f.name); return true; })
        .map(f => ({ name:f.name, type:"func", cat:f.cat, desc:f.desc, insert:f.name+"()" }));
    }
    if (tab === "snips") return this._items.snips || [];
    return this._items[tab] || [];
  }

  _buildItemHTML(item) {
    const ti = TYPE_ICON[item.type] || TYPE_ICON.field;
    const isPinned = this._pinnedItems.some(p => p.name === item.name);
    const colorMap = { var:"afb-sb-item-global", global:"afb-sb-item-global", local:"afb-sb-item-local", ref:"afb-sb-item-ref", func:"afb-sb-item-func", snip:"afb-sb-item-snip", sibling:"afb-sb-item-sibling" };
    const colorCls = colorMap[item.type] || (this._activeTab === "global" ? "afb-sb-item-global" : this._activeTab === "sibling" ? "afb-sb-item-sibling" : "afb-sb-item-local");
    const sourceLabels = { "afb-sb-item-global":"global","afb-sb-item-ref":"ref","afb-sb-item-func":"fn","afb-sb-item-snip":"snip","afb-sb-item-local":"local","afb-sb-item-sibling":"sibling" };
    const sourceLabel = sourceLabels[colorCls] || "local";
    const metaHtml = (item.doctype || item.fieldtype) ? `<div class="afb-sb-item-meta"><span>${_esc(item.fieldtype||"")}</span>${item.doctype ? `<span>·</span><span>${_esc(item.doctype)}</span>` : ""}</div>` : "";
    const valHtml  = item.val != null ? `<div class="afb-sb-item-val">${_esc(String(item.val))}</div>` : "";
    const insertToken = item.insert || item.name;
    return `<div class="afb-sb-item afb-anim ${colorCls}${isPinned?" pinned":""}" draggable="true"
      data-token="${_esc(insertToken)}" data-name="${_esc(item.name)}" title="${_esc(item.desc||item.name)}"
      data-item-type="${_esc(item.type||"field")}" data-item-cat="${_esc(item.cat||"")}">
      <div class="afb-sb-item-icon ${ti.cls}">${ti.icon}</div>
      <div class="afb-sb-item-body">
        <div class="afb-sb-item-name">${_esc(item.name)}</div>
        <div class="afb-sb-item-desc">${_esc(item.desc||"")}</div>
        ${metaHtml}${valHtml}
      </div>
      <span class="afb-sb-item-source-badge">${sourceLabel}</span>
      <div class="afb-sb-item-pin ${isPinned?"pinned":""}" title="${isPinned?"Bỏ ghim":"Ghim"}">📌</div>
      <div class="afb-sb-item-insert" title="Chèn vào editor">+</div>
    </div>`;
  }

  _bindSbItemEvents(container) {
    container.querySelectorAll(".afb-sb-item").forEach(el => {
      el.addEventListener("dblclick", () => this._insertFocused(el.dataset.token));
      el.querySelector(".afb-sb-item-insert")?.addEventListener("click", e => { e.stopPropagation(); this._insertFocused(el.dataset.token); });
      el.querySelector(".afb-sb-item-pin")?.addEventListener("click", e => { e.stopPropagation(); this._togglePin(el); });
      el.addEventListener("mouseenter", ev => this._showItemTooltip(ev, el.dataset));
      el.addEventListener("mouseleave", () => this._hideTooltip());
    });
  }

  _togglePin(el) {
    const name = el.dataset.name;
    const idx = this._pinnedItems.findIndex(p => p.name === name);
    if (idx >= 0) { this._pinnedItems.splice(idx, 1); this._setStatus(`📌 Bỏ ghim: ${name}`, "warning"); }
    else { this._pinnedItems.push({ name, type:el.dataset.itemType||"field", cat:el.dataset.itemCat||"", desc:el.title||name, insert:el.dataset.token||name }); this._setStatus(`📌 Ghim: ${name}`, "ok"); }
    this._updatePinBadge(); this._renderSbItems();
  }

  _updatePinBadge() {
    const badge = this._q(`#pinbadge-${this._uid}`);
    if (!badge) return;
    const count = this._pinnedItems.length;
    badge.textContent = String(count);
    badge.style.display = count > 0 ? "inline-block" : "none";
  }

  _renderPinTab(list, query = "") {
    const items = query ? this._pinnedItems.filter(p => p.name.toLowerCase().includes(query)) : this._pinnedItems;
    if (!items.length) { list.innerHTML = `<div style="padding:24px 16px;text-align:center;color:var(--afb-text3);font-size:12px"><div style="font-size:20px;margin-bottom:8px">📌</div>Chưa có mục nào được ghim.</div>`; return; }
    list.innerHTML = items.map(i => this._buildItemHTML(i)).join("");
    this._bindSbItemEvents(list);
  }

  _buildSnipGrid(query = "") {
    const snips = aluglass.formula.FunctionRegistry.getSnippets();
    const filtered = query ? snips.filter(s => s.title.toLowerCase().includes(query) || s.code.toLowerCase().includes(query)) : snips;
    if (!filtered.length) return `<div style="padding:20px;text-align:center;color:var(--afb-text3);font-size:12px">Không tìm thấy</div>`;
    return `<div class="afb-snip-grid" style="padding:8px">${filtered.map(s => `<div class="afb-snip-card" data-code="${_esc(s.code)}" title="${_esc(s.desc)}"><div class="afb-snip-card-title">${_esc(s.title)}</div><div class="afb-snip-card-code">${_esc(s.code.substring(0,40))}${s.code.length>40?"…":""}</div></div>`).join("")}</div>`;
  }

  _bindSnipClicks(container) {
    container.querySelectorAll(".afb-snip-card").forEach(el => el.addEventListener("click", () => { this._insertFocused(el.dataset.code); this._setStatus("✦ Snippet đã chèn","ok"); }));
  }

  _buildTmplGallery(query = "") {
    let html = '<div style="padding:6px">';
    let hasAny = false;
    aluglass.formula.FunctionRegistry.getTemplates().forEach(section => {
      const tfs = query ? section.templates.filter(t => t.name.toLowerCase().includes(query) || t.code.toLowerCase().includes(query)) : section.templates;
      if (!tfs.length) return;
      hasAny = true;
      html += `<div class="afb-tmpl-section"><div class="afb-tmpl-section-title">${_esc(section.category)}</div>`;
      tfs.forEach(t => { html += `<div class="afb-tmpl-card" data-code="${_esc(t.code)}" title="${_esc(t.desc)}"><div class="afb-tmpl-card-icon">${t.icon}</div><div class="afb-tmpl-card-body"><div class="afb-tmpl-card-name">${_esc(t.name)}</div><div class="afb-tmpl-card-code">${_esc(t.code.substring(0,50))}${t.code.length>50?"…":""}</div></div></div>`; });
      html += `</div>`;
    });
    html += "</div>";
    return hasAny ? html : `<div style="padding:20px;text-align:center;color:var(--afb-text3);font-size:12px">Không tìm thấy</div>`;
  }

  _bindTmplClicks(container) {
    container.querySelectorAll(".afb-tmpl-card").forEach(el => el.addEventListener("click", () => { this._insertFocused(el.dataset.code); this._setStatus("🎨 Template đã áp dụng","ok"); }));
  }

  // ── Toolbar ────────────────────────────────────────────────────────────────
  _bindToolbar() {
    this.$wrapper.on("click.afb",".afb-act-test",         () => this._actTest());
    this.$wrapper.on("click.afb",".afb-act-format",       () => this._actFormat());
    this.$wrapper.on("click.afb",".afb-act-multiline",    () => this._actToggleMultiLine());
    this.$wrapper.on("click.afb",".afb-act-explain",      () => this._actExplain());
    this.$wrapper.on("click.afb",".afb-act-testvars",     () => this._actTestWithVars());
    this.$wrapper.on("click.afb",".afb-act-ctx",          () => this._actShowCtx());
    this.$wrapper.on("click.afb",".afb-act-reload-ctx",   () => this._actReloadContext());
    this.$wrapper.on("click.afb",".afb-act-clear",        () => this._actClear());
    this.$wrapper.on("click.afb",".afb-act-suggest",      () => this._actSmartSuggest());
    this.$wrapper.on("click.afb",".afb-act-copy-formula", () => this._actCopyFormula());
    this.$wrapper.on("click.afb",".afb-act-shortcuts",    () => this._actShowShortcuts());
    this.$wrapper.on("click.afb",".afb-act-save-template",() => this._actSaveTemplate());
    this.$wrapper.on("click.afb",".afb-act-findreplace",  () => this._actToggleFindReplace());
    this.$wrapper.on("click.afb",".afb-act-diff",         () => this._actShowDiff());
    this.$wrapper.on("click.afb",".afb-act-undo",         () => this.editor?.trigger("kbd","undo"));
    this.$wrapper.on("click.afb",".afb-act-redo",         () => this.editor?.trigger("kbd","redo"));
  }

  // ── Panel ──────────────────────────────────────────────────────────────────
  _initPanel() {
    this.$wrapper.on("click.afb",".afb-panel-tab", e => this._switchPanel($(e.currentTarget).data("panel")));
  }

  _switchPanel(panel) {
    this._activePanel = panel;
    this._qAll(".afb-panel-tab").forEach(el => el.classList.toggle("active", el.dataset.panel === panel));
    this._qAll(".afb-panel-body").forEach(el => el.classList.toggle("active", el.dataset.pb === panel));
    if (panel === "history") this._renderHistory();
  }

  _setPanelContent(panel, html) {
    const el = this._q(`[data-pb="${panel}"]`);
    if (el) { el.innerHTML = html; el.classList.add("afb-anim"); }
  }

  // ── Actions ────────────────────────────────────────────────────────────────
  async _actTest() {
    if (this._testRunning) { this._setStatus("⚠️ Đang chạy...","warning"); return; }
    const formula = this.getValue();
    if (!formula) return;
    this._testRunning = true;
    this._setStatus("⏳ Đang chạy...","");
    this._switchPanel("result");
    this._setPanelContent("result", `<div class="afb-loading" style="width:60%"></div><div class="afb-loading" style="width:40%"></div>`);
    try {
      const res = await frappe.call({ 
        method:"aluglass.api.formula_builder.evaluate_formula", 
        args:{ 
          formula, 
          scope_context_json:JSON.stringify(this._scope()),
          frm_doc_json: this._getFrmDocJson(),
        } 
      });
      if (this._destroyed) return;
      const r = res.message;
      if (r.success) {
        const val = r.result;
        const fmtVal = typeof val === "number" ? val.toLocaleString("vi-VN") : String(val ?? "null");
        const typeColor = typeof val === "number" ? "var(--afb-amber)" : "var(--afb-cyan)";
        this._setPanelContent("result", `<div class="afb-result-label">KẾT QUẢ</div><div class="afb-result-big afb-result-ok" style="color:${typeColor}">${_esc(fmtVal)}</div>${r.elapsed_ms!=null?`<div style="margin-top:4px;color:var(--afb-text3);font-size:11px">⏱ ${r.elapsed_ms}ms</div>`:""}<div class="afb-result-copy" data-copy="${_esc(fmtVal)}">📋 Copy kết quả</div>`);
        this._q("[data-copy]")?.addEventListener("click", e => { navigator.clipboard?.writeText(e.currentTarget.dataset.copy); this._setStatus("📋 Đã copy!","ok"); });
        this._setStatus("✓ Thành công","ok");
        this._addHistory(formula, fmtVal, true);
        const sbval = this._q(`#sbval-${this._uid}`);
        if (sbval) { sbval.textContent = `= ${fmtVal}`; sbval.className = "afb-statusbar-item ok"; }
      } else {
        this._setPanelContent("result", `<div class="afb-result-err">✗ Lỗi: ${_esc(r.error||"Unknown")}</div><div class="afb-result-copy" data-copy="${_esc(r.error||"")}">📋 Copy lỗi</div>`);
        this._q("[data-copy]")?.addEventListener("click", e => { navigator.clipboard?.writeText(e.currentTarget.dataset.copy); });
        this._setStatus("✗ Lỗi","err");
        this._addHistory(formula, r.error||"Error", false);
        const sbval = this._q(`#sbval-${this._uid}`);
        if (sbval) { sbval.textContent = "✗ Lỗi"; sbval.className = "afb-statusbar-item error"; }
      }
    } catch(e) {
      if (this._destroyed) return;
      this._setPanelContent("result", `<div class="afb-result-err">✗ ${_esc(String(e))}</div>`);
      this._setStatus("✗ Lỗi kết nối","err");
    } finally { this._testRunning = false; }
  }

  // NEW v3: Test With Variables (§2.6)
  _actTestWithVars() {
    this._switchPanel("testvars");
    const formula = this.getValue();
    if (!formula) { this._setPanelContent("testvars", `<span style="color:var(--afb-text3)">Nhập công thức trước.</span>`); return; }

    const knownFns  = new Set(aluglass.formula.FunctionRegistry.getAll().map(f => f.name));
    const knownKeys = new Set(["IF","IFS","IIF","SWITCH","and_","or_","not_","True","False","None","in"]);
    const varNames  = [...new Set((formula.match(/\$?[a-zA-Z_]\w*/g) || []).filter(t => !knownFns.has(t) && !knownKeys.has(t) && !knownFns.has(t.replace(/^\$/,""))).map(t => t))];

    const ctx = this._buildCtx();
    this._testVarRows = varNames.map(name => {
      const cleanName = name.startsWith("$") ? name.slice(1) : name;
      const item = ctx.allItems.find(i => i.insert === name || i.name === name || i.name === "$"+cleanName);
      return { name, value: item?.value ?? "", fieldtype: item?.fieldtype || "Data", doctype: item?.doctype || "—", source: item?.source || "—" };
    });

    const rows = this._testVarRows.map((r, i) => `<tr>
      <td style="padding:4px 8px;font-family:var(--afb-mono);font-size:11px;white-space:nowrap">${_esc(r.name)}</td>
      <td style="padding:3px 4px"><input type="text" class="afb-tvar-input" data-idx="${i}" value="${_esc(String(r.value??""))}" /></td>
      <td style="padding:4px 8px;font-size:10px;color:var(--afb-text3)">${_esc(r.fieldtype)} · ${_esc(r.doctype)}</td>
    </tr>`).join("");

    this._setPanelContent("testvars", `
      <div class="afb-result-label" style="margin-bottom:4px">Công thức: <span style="font-family:var(--afb-mono);color:var(--afb-amber)">${_esc(formula.substring(0,80))}</span></div>
      <table class="afb-tvars-table"><thead><tr><th>BIẾN</th><th>GIÁ TRỊ</th><th>NGUỒN</th></tr></thead><tbody>${rows}</tbody></table>
      <div style="margin-top:8px;display:flex;align-items:center;gap:10px">
        <button class="afb-btn primary afb-tvar-run" style="padding:5px 14px">▶ Tính thử</button>
        <span class="afb-tvar-result"></span>
      </div>`);

    const pane = this._q(`[data-pb="testvars"]`);
    if (!pane) return;

    pane.querySelector(".afb-tvar-run")?.addEventListener("click", async () => {
      // Collect override values
      const overrides = {};
      pane.querySelectorAll(".afb-tvar-input").forEach(inp => {
        const row = this._testVarRows[parseInt(inp.dataset.idx)];
        if (row && inp.value !== "") overrides[row.name] = inp.value;
      });
      const resultEl = pane.querySelector(".afb-tvar-result");
      if (resultEl) resultEl.textContent = "⏳...";
      try {
        const res = await frappe.call({ method:"aluglass.api.formula_builder.evaluate_formula", args:{ formula, scope_context_json:JSON.stringify(this._scope()), override_vars:JSON.stringify(overrides) } });
        const r = res.message;
        if (r.success) {
          const fmtVal = typeof r.result === "number" ? r.result.toLocaleString("vi-VN") : String(r.result ?? "null");
          if (resultEl) { resultEl.textContent = `= ${fmtVal}`; resultEl.className = "afb-tvar-result"; }
        } else {
          if (resultEl) { resultEl.textContent = `✗ ${r.error||"Lỗi"}`; resultEl.style.color = "var(--afb-red)"; }
        }
      } catch(e) { if (resultEl) { resultEl.textContent = `✗ Lỗi kết nối`; resultEl.style.color = "var(--afb-red)"; } }
    });
  }

  _actFormat() {
    let val = this.getValue().trim();
    if (!val) return;
    val = val
      .replace(/\s*([+*/%><=!&|]+)\s*/g," $1 ")
      .replace(/\s*-\s*(?!\d)/g," - ")
      .replace(/([^+\-*/%><=!&|(,\s])\s*-\s*(\d)/g,"$1 - $2")
      .replace(/\s*,\s*/g,", ")
      .replace(/\(\s+/g,"(").replace(/\s+\)/g,")")
      .replace(/\s{2,}/g," ")
      .replace(/(\w+)\s*\(\s*/g,"$1(").trim();
    this.setValue(val); this._setStatus("⇄ Đã format","ok");
  }

  _actToggleMultiLine() {
    this._multiLine = !this._multiLine;
    const btn = this._q(".afb-act-multiline");
    if (btn) btn.classList.toggle("active", this._multiLine);
    let val = this.getValue().trim();
    if (!val) return;
    if (this._multiLine) {
      val = val.replace(/\s+([+\-*\/])\s+/g,"\n  $1 ").replace(/\s*(,)\s*/g,",\n  ");
    } else {
      val = val.replace(/\n\s*/g," ").replace(/\s{2,}/g," ").trim();
    }
    this.setValue(val); this._setStatus(this._multiLine ? "↕ Multi-line ON" : "↕ Single-line ON","ok");
  }

  _actCopyFormula() {
    const val = this.getValue();
    if (!val) { this._setStatus("Không có gì để copy","warning"); return; }
    if (navigator.clipboard?.writeText) { navigator.clipboard.writeText(val).then(() => this._setStatus("📋 Đã copy","ok")).catch(() => this._fallbackCopy(val)); }
    else this._fallbackCopy(val);
  }

  _fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); this._setStatus("📋 Đã copy","ok"); } catch {}
    ta.remove();
  }

  async _actReloadContext() {
    this._setStatus("🔄 Đang reload...","");
    aluglass.formula.ContextCache.invalidate(this.opts.current_doctype, this.opts.current_docname);
    await this._loadLiveContext();
    this._setStatus("🔄 Context đã cập nhật","ok");
  }

  _actShowCtx(silent = false) {
      if (!silent) this._switchPanel("ctx");
      if (!Array.isArray(this._liveCtx?.variables)) {
          if (!silent) this._setPanelContent("ctx", `<span style="color:var(--afb-text3)">Chưa có context.</span>`);
          return;
      }
      const ctx = this._buildCtx();
      const allCtxItems = ctx.allItems;
      const rows = allCtxItems.filter(v => v && v.name).map(v => {
          const srcCls = { global: "afb-ctx-src-global", parent: "afb-ctx-src-local", current_row: "afb-ctx-src-row", sibling_table: "afb-ctx-src-sibling", local: "afb-ctx-src-local" }[v.source] || "afb-ctx-src-local";
          const srcLbl = { global: "🌍 global", parent: "📄 parent", current_row: "📍 row", sibling_table: "↔ sibling", local: "📄 local" }[v.source] || "📄 local";
          return `<tr><td class="afb-ctx-key">${_esc(v.name)}</td>
                  <td class="afb-ctx-val">${_esc(String(v.value ?? ""))}</td>
                  <td class="afb-ctx-type">${_esc(v.fieldtype || "")}</td>
                  <td class="${srcCls}">${srcLbl}</td>
                  <td class="afb-ctx-type">${_esc(v.doctype || "")}</td>
                  </tr>`;
      }).join("");
      this._setPanelContent("ctx", `<table class="afb-ctx-table">
          <thead>
              <tr><th>Biến</th><th>Giá trị</th><th>Kiểu</th><th>Nguồn</th><th>Doctype</th></tr>
          </thead>
          <tbody>${rows}</tbody>
      </table>`);
  }

  _actClear() {
    if (!this.getValue()) return;
    frappe.confirm("Xóa toàn bộ công thức?", () => {
      this.setValue(""); this.$valbar.html(`<span style="color:var(--afb-text3)">Nhập công thức để bắt đầu...</span>`);
      this._setPanelContent("result",`<span style="color:var(--afb-text3)">Nhấn ▶ Chạy thử để xem kết quả.</span>`);
      const sbval = this._q(`#sbval-${this._uid}`); if (sbval) { sbval.textContent = "—"; sbval.className = "afb-statusbar-item"; }
    });
  }

  _addHistory(formula, result, success) {
    const time = new Date().toLocaleTimeString("vi-VN", { hour:"2-digit", minute:"2-digit", second:"2-digit" });
    this._history.unshift({ formula, result, success, time });
    this._history = this._history.slice(0, 20);
    if (this._activePanel === "history") this._renderHistory();
  }

  _renderHistory() {
    if (!this._history.length) { this._setPanelContent("history",`<span style="color:var(--afb-text3)">Chưa có lịch sử chạy.</span>`); return; }
    const rows = this._history.map((h,i) => `<div class="afb-history-item" data-formula="${_esc(h.formula)}"><span style="color:var(--afb-text3);font-size:10px;flex-shrink:0">#${i+1}</span><span class="afb-history-formula">${_esc(h.formula)}</span><span class="afb-history-result ${h.success?"ok":"err"}">${_esc(h.result)}</span><span class="afb-history-time">${h.time}</span></div>`).join("");
    this._setPanelContent("history",rows);
    this._q(`[data-pb="history"]`)?.querySelectorAll(".afb-history-item").forEach(el => el.addEventListener("click", () => { this.setValue(el.dataset.formula); this._setStatus("🕐 Khôi phục","ok"); }));
  }

  async _actExplain() {
    const formula = this.getValue();
    if (!formula) return;
    this._switchPanel("explain");
    this._setPanelContent("explain",`<div class="afb-loading" style="width:70%"></div><div class="afb-loading" style="width:50%"></div>`);
    try {
      const res = await frappe.call({ method:"aluglass.api.formula_builder.explain_formula", args:{ formula, scope_context_json:JSON.stringify(this._scope()) } });
      if (this._destroyed) return;
      const r = res.message;
      if (r.error && !r.steps?.length) { this._setPanelContent("explain",`<div class="afb-result-err">✗ ${_esc(r.error)}</div>`); return; }

      let html = "";
      const inputs   = (r.steps||[]).filter(s => s.is_input);
      const formulas = (r.steps||[]).filter(s => !s.is_input);

      if (inputs.length) {
        html += `<div class="afb-explain-inputs-section"><div class="afb-explain-section-title">📥 Inputs (${inputs.length})</div>`;
        inputs.forEach(step => { html += `<div class="afb-explain-step"><span class="afb-explain-step-icon">📥</span><div class="afb-explain-step-body"><span class="afb-explain-step-name input">${_esc(step.name)}</span><span class="afb-explain-step-value">${_esc(String(step.value??"null"))}</span></div></div>`; });
        html += `</div>`;
      }
      if (formulas.length) {
        html += `<div class="afb-explain-section-title">🔢 Chuỗi tính toán (${formulas.length} bước)</div>`;
        formulas.forEach((step, i) => {
          const indent = Math.max(0, step.depth || 0);
          const valStr = step.value != null ? (typeof step.value === "number" ? step.value.toLocaleString("vi-VN") : String(step.value)) : "null";
          const depEntries = step.deps ? Object.entries(step.deps) : [];
          html += `<div class="afb-explain-step" style="margin-left:${indent*12}px">
            <span class="afb-explain-step-icon">${step.is_root ? "🎯" : "🔢"}</span>
            <div class="afb-explain-step-body">
              <div><span class="afb-explain-step-name${step.is_root?" root":""}">${_esc(step.name)}</span><span class="afb-explain-step-value">= ${_esc(valStr)}</span></div>
              ${step.formula ? `<div class="afb-explain-step-formula">${_esc(step.formula.replace(/\n/g," ").substring(0,80))}${step.formula.length>80?"…":""}</div>` : ""}
              ${depEntries.length ? `<div class="afb-explain-step-deps">↑ ${depEntries.map(([k,v]) => `<span style="color:#93c5fd">${_esc(k)}</span>=<span style="color:var(--afb-green)">${_esc(String(v))}</span>`).join(" · ")}</div>` : ""}
            </div>
          </div>`;
        });
      }
      if (r.vars_used?.length) html += `<div style="margin-top:10px;padding-top:6px;border-top:1px solid var(--afb-border);color:var(--afb-text3);font-size:10px">Biến sử dụng: ${r.vars_used.map(v => `<span style="color:#93c5fd">${_esc(v)}</span>`).join(", ")}</div>`;
      if (r.circular_risk) html += `<div style="margin-top:6px;color:var(--afb-red);font-size:11px">⚠ Cảnh báo: Vòng lặp tròn!</div>`;

      this._setPanelContent("explain", html || `<span style="color:var(--afb-text3)">Không có thông tin phân tích.</span>`);
      this._renderDebugPanel(r, formula);
    } catch(e) {
      if (this._destroyed) return;
      this._setPanelContent("explain",`<div class="afb-result-err">Lỗi kết nối: ${_esc(String(e))}</div>`);
    }
  }

  _renderDebugPanel(r, formula) {
    let dbg = "";
    const tokens = Array.isArray(r.debug_info?.tokens) && r.debug_info.tokens.length ? r.debug_info.tokens : this._naiveLex(formula);
    if (tokens.length) {
      dbg += `<div class="afb-debug-section"><div class="afb-debug-title">🔤 Tokens (${tokens.length})</div><div>${tokens.map(t => `<span class="afb-debug-token afb-debug-token-${_esc(t.type||"name")}">${_esc(String(t.value))}</span>`).join("")}</div></div>`;
    }
    if (r.debug_info?.ast_summary) { dbg += `<div class="afb-debug-section"><div class="afb-debug-title">🌳 AST Summary</div><div class="afb-debug-ast">${_esc(r.debug_info.ast_summary)}</div></div>`; }
    if (r.vars_used?.length) {
      const ctx = this._buildCtx();
      dbg += `<div class="afb-debug-section"><div class="afb-debug-title">📍 Variable Resolution</div>${r.vars_used.map(v => {
        const item = ctx.allItems.find(x => x.name === v || x.insert === v);
        const resolved = item ? `<span style="color:var(--afb-green)">${_esc(String(item.value??"null"))}</span> <span style="color:var(--afb-text3);font-size:9px">[${_esc(item.source||"")}]</span>` : `<span style="color:var(--afb-text3)">? (chưa resolve)</span>`;
        return `<div style="display:flex;gap:8px;font-size:11px;padding:2px 0"><span style="color:#93c5fd;font-family:var(--afb-mono)">${_esc(v)}</span><span style="color:var(--afb-text3)">→</span>${resolved}</div>`;
      }).join("")}</div>`;
    }
    if (!dbg) dbg = `<span style="color:var(--afb-text3)">Không có debug info.</span>`;
    this._setPanelContent("debug", dbg);
  }

  _naiveLex(formula) {
    const tokens = [];
    const patterns = [
      { re:/^\$[a-zA-Z_]\w*/, type:"var" },
      { re:/^[a-zA-Z_]\w*/, type:"name" },
      { re:/^"([^"\\]|\\.)*"/, type:"string" },
      { re:/^'([^'\\]|\\.)*'/, type:"string" },
      { re:/^\d+\.?\d*/, type:"number" },
      { re:/^[+\-*/%<>=!&|^~]+/, type:"op" },
      { re:/^[()[\],]/, type:"paren" },
      { re:/^\s+/, type:"ws" },
      { re:/^./, type:"other" },
    ];
    const KEYWORDS = new Set(["IF","IFS","IIF","SWITCH","True","False","None","and_","or_","not_","in"]);
    const FUNCS    = new Set(aluglass.formula.FunctionRegistry.getAll().map(f => f.name));
    let src = formula;
    while (src.length) {
      let matched = false;
      for (const { re, type } of patterns) {
        const m = src.match(re);
        if (m) {
          if (type !== "ws") {
            let ft = type;
            if (type === "name") { if (KEYWORDS.has(m[0])) ft = "keyword"; }
            tokens.push({ value:m[0], type:ft });
          }
          src = src.slice(m[0].length); matched = true; break;
        }
      }
      if (!matched) { tokens.push({ value:src[0], type:"other" }); src = src.slice(1); }
    }
    return tokens.slice(0, 80);
  }

  async _actSmartSuggest() {
    this._setStatus("💡 Đang tìm gợi ý...","");
    try {
      const res = await frappe.call({ method:"aluglass.api.formula_builder.smart_suggest_formula", args:{ doctype:this.opts.current_doctype||"", fieldname:this.opts.current_field||"", field_label:this.opts.field_label||"", scope_context_json:JSON.stringify(this._scope()) } });
      if (this._destroyed) return;
      if (res.message?.suggestions?.length) { this._showSuggestDialog(res.message.suggestions); return; }
    } catch {}
    if (!this._destroyed) await this._actAISuggest();
  }

  async _actAISuggest() {
    const formula  = this.getValue();
    const ctx      = this._buildCtx();
    const varNames = ctx.allItems.slice(0,20).map(v => v.name).join(", ");
    const prompt = `Bạn là chuyên gia ERP Frappe. Field: "${this.opts.field_label||this.opts.current_field||"công thức"}" trong doctype "${this.opts.current_doctype||""}". Biến có sẵn: ${varNames||"(không có)"}. ${formula ? "Công thức hiện tại: "+formula : "Chưa có công thức."}\n\nĐề xuất 2-3 công thức phù hợp. Trả về JSON: {"suggestions":[{"label":"Tên","formula":"công thức","desc":"mô tả"}]}. Chỉ JSON, không gì khác.`;
    this._setStatus("🤖 Đang hỏi AI...","");
    try {
      const res = await frappe.call({
        method: "aluglass.api.formula_builder.ai_suggest_formula",
        args: { prompt }
      });
      if (this._destroyed) return;
      const text = res.message?.text || "";
      const clean = text.replace(/```json|```/g, "").trim();
      const parsed = JSON.parse(clean);
      if (parsed?.suggestions?.length) {
        this._showSuggestDialog(parsed.suggestions);
        this._setStatus("🤖 AI đã gợi ý", "ok");
      } else {
        this._switchSbTab("tmpl");
        this._setStatus("💡 Chọn công thức từ tab Mẫu", "warning");
      }
    } catch {
      if (!this._destroyed) {
        this._switchSbTab("tmpl");
        this._setStatus("💡 Chọn công thức từ tab Mẫu", "warning");
      }
    }
  }

  _showSuggestDialog(suggestions) {
    document.querySelector(".afb-suggest-overlay")?.remove();
    const overlay = document.createElement("div");
    overlay.className = "afb-suggest-overlay";
    overlay.innerHTML = `<div class="afb-suggest-dialog">
      <div class="afb-suggest-title">💡 Gợi ý công thức</div>
      ${suggestions.slice(0,3).map((s,i) => `<div style="margin-bottom:12px"><div style="font-size:11px;color:var(--afb-text3);margin-bottom:4px">${_esc(s.label||"Gợi ý "+(i+1))}</div><div class="afb-suggest-formula">${_esc(s.formula)}</div><div class="afb-suggest-desc">${_esc(s.desc||"")}</div><button class="afb-btn success" data-formula="${_esc(s.formula)}" style="font-size:11px;padding:4px 10px">✓ Dùng</button></div>`).join("")}
      <div class="afb-suggest-actions"><button class="afb-btn afb-suggest-close">✕ Đóng</button></div>
    </div>`;
    document.body.appendChild(overlay);
    const closeDialog = () => { overlay.remove(); document.removeEventListener("keydown", onKey); };
    overlay.querySelectorAll("[data-formula]").forEach(btn => btn.addEventListener("click", () => { this.setValue(btn.dataset.formula); closeDialog(); this._setStatus("✓ Đã áp dụng","ok"); }));
    overlay.querySelector(".afb-suggest-close")?.addEventListener("click", closeDialog);
    overlay.addEventListener("click", e => { if (e.target === overlay) closeDialog(); });
    const onKey = e => { if (e.key === "Escape") closeDialog(); };
    document.addEventListener("keydown", onKey);
  }

  async _runValidation(formula) {
    if (this._destroyed) return;
    try {
      const res = await frappe.call({ method:"aluglass.api.formula_builder.validate_formula", args:{ formula, scope_context_json:JSON.stringify(this._scope()) } });
      if (this._destroyed) return;
      this._applyValidation(res.message);
      if (this.opts.onValidate) this.opts.onValidate(res.message);
    } catch {}
  }

  _applyValidation(res) {
    if (!res) return;
    const chips = [];
    const formula = this.getValue();
    if (res.valid || res.ok) {
      chips.push(`<span class="afb-chip ok">✓ Hợp lệ</span>`);
      if (res.normalized && res.normalized !== formula) chips.push(`<span class="afb-chip info">⇄ Đã chuẩn hóa</span>`);
    } else {
      [...new Set(res.errors||[])].forEach(e => chips.push(`<span class="afb-chip error">✗ ${_esc(e)}</span>`));
    }
    [...new Set(res.warnings||[])].forEach(w => chips.push(`<span class="afb-chip warning">⚠ ${_esc(w)}</span>`));
    if (res.circular_detected) chips.push(`<span class="afb-chip error">↺ Vòng lặp tròn!</span>`);
    if (formula.length > 500) chips.push(`<span class="afb-chip warning">⚠ Công thức dài (${formula.length} ký tự)</span>`);
    const hint = `<span class="afb-valbar-hint">Ctrl+Enter · Ctrl+S · Alt+F · Ctrl+?</span>`;
    this.$valbar.html((chips.length ? chips.join(" ") : `<span style="color:var(--afb-text3)">Công thức sẵn sàng</span>`) + hint);
    const sbval = this._q(`#sbval-${this._uid}`);
    if (sbval && formula.length <= 500) {
      if (res.valid || res.ok) { sbval.textContent = "✓ Hợp lệ"; sbval.className = "afb-statusbar-item ok"; }
      else { sbval.textContent = "✗ Lỗi cú pháp"; sbval.className = "afb-statusbar-item error"; }
    }
    if (this.editor && res.markers?.length) {
      const markers = res.markers.map(m => ({ severity:m.severity==="warning"?monaco.MarkerSeverity.Warning:monaco.MarkerSeverity.Error, startLineNumber:m.startLine||1, startColumn:m.startCol||1, endLineNumber:m.endLine||m.startLine||1, endColumn:m.endCol||(m.startCol||1)+5, message:m.message||"Lỗi" }));
      monaco.editor.setModelMarkers(this.editor.getModel(), "afb", markers);
    } else if (this.editor) { monaco.editor.setModelMarkers(this.editor.getModel(), "afb", []); }
  }

  async _loadLiveContext() {
    if (this._destroyed) return;
    const scope = this._scope();
    const dt    = scope.current_doctype;
    const dn    = scope.current_docname;

    // Check cache first (§4)
    const cached = aluglass.formula.ContextCache.get(dt, dn);
    if (cached) {
      this._liveCtx = cached;
      this._populateSidebarFromCtx(cached);
      if (this.opts.show_panel) this._actShowCtx(true);
      return;
    }

    try {
      const res = await frappe.call({ method:"aluglass.api.formula_builder.get_live_context", args:{ scope_context_json:JSON.stringify(scope) } });
      if (this._destroyed) return;
      if (res.message?.success) {
        aluglass.formula.ContextCache.set(dt, dn, res.message);
        this._liveCtx = res.message;
        this._populateSidebarFromCtx(res.message);
        if (this.opts.show_panel) this._actShowCtx(true);
      }
    } catch { this._setStatus?.("⚠ Không tải được context","warn"); }
  }

  _populateSidebarFromCtx(ctx) {
    if (!ctx?.variables || !Array.isArray(ctx.variables)) return;
    const ctx3 = this._buildCtx();
    this._items.global  = ctx3.globalVars.map(v  => ({ name:v.name, type:"var",     cat:"Toàn cục",  desc:v.label||v.name, val:v.value, doctype:v.doctype, fieldtype:v.fieldtype }));
    this._items.local   = ctx3.localVars.map(v   => ({ name:v.name, type:"field",   cat:v.doctype||"Cục bộ", desc:v.label||v.name, val:v.value, doctype:v.doctype, fieldtype:v.fieldtype }));
    this._items.refs    = ctx3.refs.map(r         => ({ name:r.name, type:"ref",     cat:r.doctype||"Tham chiếu", desc:r.label||r.name, insert:r.insert }));
    this._items.sibling = ctx3.siblingItems.slice(0,100).map(s => ({ name:s.name, type:"sibling", cat:s.tableName||"Sibling", desc:s.label||s.name, val:s.value, doctype:s.doctype, fieldtype:s.fieldtype, insert:s.insert }));
    this._items.snips   = aluglass.formula.FunctionRegistry.getSnippets().map(s => ({ name:s.title, type:"snip", cat:"Snippet", desc:s.desc, insert:s.code }));
    this._renderSbItems();
  }

  _actShowShortcuts() {
    document.querySelector(".afb-shortcuts-overlay")?.remove();
    const overlay = document.createElement("div");
    overlay.className = "afb-shortcuts-overlay";
    let rows = "";
    FB_SHORTCUTS.forEach(s => {
      if (s.section) { rows += `<div class="afb-shortcuts-section">${_esc(s.section)}</div>`; }
      else { rows += `<div class="afb-shortcuts-row"><span class="afb-shortcuts-desc">${_esc(s.desc)}</span><span class="afb-shortcuts-keys">${s.keys.map(k => `<span class="afb-kbd">${_esc(k)}</span>`).join("")}</span></div>`; }
    });
    overlay.innerHTML = `<div class="afb-shortcuts-dialog"><div class="afb-shortcuts-title">⌨ Phím tắt Formula Builder v3</div><div class="afb-shortcuts-grid">${rows}</div><div class="afb-shortcuts-close-row"><button class="afb-btn" id="sc-close">✕ Đóng (Esc)</button></div></div>`;
    document.body.appendChild(overlay);
    const close = () => { overlay.remove(); document.removeEventListener("keydown", onKey); };
    overlay.querySelector("#sc-close")?.addEventListener("click", close);
    overlay.addEventListener("click", e => { if (e.target === overlay) close(); });
    const onKey = e => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
  }

  // ── Find & Replace ──────────────────────────────────────────────────────
  _actToggleFindReplace() {
    const uid = this._uid;
    const panel = this._q(`#fnr-${uid}`);
    if (!panel) return;
    if (panel.style.display === "none" || !panel.style.display) { this._openFindReplace(panel); }
    else { panel.style.display = "none"; this.editor?.focus(); }
  }

  _openFindReplace(panel) {
    panel.style.display = "block";
    panel.innerHTML = `<span class="afb-fnr-close" id="fnr-close-${this._uid}">✕</span>
      <div class="afb-fnr-row"><span class="afb-fnr-label">Tìm</span><input class="afb-fnr-input" id="fnr-find-${this._uid}" placeholder="Nhập từ cần tìm..." autocomplete="off"/><span class="afb-fnr-count" id="fnr-count-${this._uid}"></span></div>
      <div class="afb-fnr-row"><span class="afb-fnr-label">Thay bằng</span><input class="afb-fnr-input" id="fnr-repl-${this._uid}" placeholder="Chuỗi thay thế..." autocomplete="off"/></div>
      <div class="afb-fnr-row" style="gap:12px"><label class="afb-fnr-opt"><input type="checkbox" id="fnr-case-${this._uid}"> Hoa/Thường</label><label class="afb-fnr-opt"><input type="checkbox" id="fnr-regex-${this._uid}"> Regex</label></div>
      <div class="afb-fnr-actions"><button class="afb-btn" id="fnr-prev-${this._uid}">◀</button><button class="afb-btn" id="fnr-next-${this._uid}">▶</button><button class="afb-btn success" id="fnr-r1-${this._uid}">Thay 1</button><button class="afb-btn primary" id="fnr-ra-${this._uid}">Thay Tất Cả</button></div>`;

    const uid = this._uid;
    const findInput  = this._q(`#fnr-find-${uid}`);
    const replInput  = this._q(`#fnr-repl-${uid}`);
    const caseChk    = this._q(`#fnr-case-${uid}`);
    const regexChk   = this._q(`#fnr-regex-${uid}`);
    const countEl    = this._q(`#fnr-count-${uid}`);
    let _deco = [];

    const highlight = () => {
      if (!this.editor || !findInput.value) { if (countEl) countEl.textContent = ""; return; }
      const text = this.editor.getValue(), find = findInput.value;
      const flags = (caseChk?.checked?"":"i")+"g";
      const pattern = regexChk?.checked ? find : find.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
      let matches = [];
      try { const re = new RegExp(pattern, flags); let m; while ((m=re.exec(text))!==null) { matches.push({start:m.index,end:m.index+m[0].length}); if(matches.length>200)break; } } catch {}
      if (countEl) countEl.textContent = matches.length ? `${matches.length} kết quả` : "Không tìm thấy";
      const model = this.editor.getModel();
      if (!model) return;
      _deco = this.editor.deltaDecorations(_deco, matches.map(mm => { const s=model.getPositionAt(mm.start),e=model.getPositionAt(mm.end); return { range:new monaco.Range(s.lineNumber,s.column,e.lineNumber,e.column), options:{ inlineClassName:"afb-fnr-highlight" } }; }));
    };

    const replaceAll = () => {
      if (!this.editor || !findInput.value) return;
      const text = this.editor.getValue(), find = findInput.value, repl = replInput.value||"";
      const flags = (caseChk?.checked?"":"i")+"g";
      const pattern = regexChk?.checked ? find : find.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
      try { const re = new RegExp(pattern,flags); const count=(text.match(re)||[]).length; const newText=text.replace(re,repl); this.setValue(newText); this._setStatus(`✓ Đã thay ${count} kết quả`,"ok"); highlight(); } catch(e) { this._setStatus("Regex lỗi: "+e.message,"err"); }
    };

    const close = () => { panel.style.display="none"; if(_deco.length) _deco=this.editor?.deltaDecorations?.(_deco,[])||[]; this.editor?.focus(); };

    findInput?.addEventListener("input", highlight);
    caseChk?.addEventListener("change", highlight);
    regexChk?.addEventListener("change", highlight);
    this._q(`#fnr-next-${uid}`)?.addEventListener("click", () => { if(!this.editor||!findInput.value) return; this.editor.trigger("fnr","editor.action.nextMatchFindAction",{}); });
    this._q(`#fnr-prev-${uid}`)?.addEventListener("click", () => { if(!this.editor||!findInput.value) return; this.editor.trigger("fnr","editor.action.previousMatchFindAction",{}); });
    this._q(`#fnr-r1-${uid}`)?.addEventListener("click", () => {
      if (!this.editor || !findInput.value) return;
      const text=this.editor.getValue(),find=findInput.value,repl=replInput.value||"";
      const flags=caseChk?.checked?"":"i";
      const pattern=regexChk?.checked?find:find.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
      try { const re=new RegExp(pattern,flags); const newText=text.replace(re,repl); this.setValue(newText); this._setStatus("✓ Đã thay 1 kết quả","ok"); highlight(); } catch(e) { this._setStatus("Regex lỗi","err"); }
    });
    this._q(`#fnr-ra-${uid}`)?.addEventListener("click", replaceAll);
    this._q(`#fnr-close-${uid}`)?.addEventListener("click", close);
    panel.addEventListener("keydown", e => { if(e.key==="Escape") close(); if(e.key==="Enter"&&e.target===findInput){e.preventDefault();this._q(`#fnr-next-${uid}`)?.click();} });
    requestAnimationFrame(() => findInput?.focus());
  }

  // ── Formula Diff ──────────────────────────────────────────────────────────
  _actShowDiff() {
    const currentFormula = this.getValue();
    document.querySelector(".afb-diff-overlay")?.remove();
    const overlay = document.createElement("div");
    overlay.className = "afb-diff-overlay";
    overlay.innerHTML = `<div class="afb-diff-dialog">
      <div class="afb-diff-title">⊟ So Sánh Công Thức</div>
      <div style="margin-bottom:12px"><div class="afb-diff-col-label">Công thức cũ</div><textarea class="afb-fnr-input" id="diff-old" rows="4" style="width:100%;resize:vertical;min-height:80px;font-family:var(--afb-mono);font-size:12px;border:2px solid #cbd5e1;border-radius:6px;padding:10px 12px;background:#f8fafc;box-sizing:border-box" placeholder="Dán công thức cũ..."></textarea></div>
      <div class="afb-diff-col-label">Công thức hiện tại</div>
      <div class="afb-diff-code" id="diff-new" style="border:2px solid #cbd5e1;border-radius:6px;background:#f8fafc;min-height:60px;padding:10px 12px">${_esc(currentFormula||"(trống)")}</div>
      <div id="diff-result" style="margin-top:14px"></div>
      <div class="afb-diff-close-row" style="margin-top:14px"><button class="afb-btn primary" id="diff-run">🔍 So Sánh</button><button class="afb-btn" id="diff-close">✕ Đóng</button></div>
    </div>`;
    document.body.appendChild(overlay);
    const run = () => {
      const oldText=(overlay.querySelector("#diff-old").value||"").trim();
      const result=overlay.querySelector("#diff-result");
      if (!oldText) { result.innerHTML=`<div style="color:var(--afb-text3);font-size:12px">Nhập công thức cũ để so sánh.</div>`; return; }
      const diff=this._computeCharDiff(oldText,currentFormula||"");
      const addCount=diff.filter(d=>d.type==="add").length, delCount=diff.filter(d=>d.type==="del").length;
      const oldHtml=diff.filter(d=>d.type!=="add").map(d=>d.type==="del"?`<span class="afb-diff-del">${_esc(d.text)}</span>`:`<span class="afb-diff-same">${_esc(d.text)}</span>`).join("");
      const newHtml=diff.filter(d=>d.type!=="del").map(d=>d.type==="add"?`<span class="afb-diff-add">${_esc(d.text)}</span>`:`<span class="afb-diff-same">${_esc(d.text)}</span>`).join("");
      result.innerHTML=`<div class="afb-diff-stats">+${addCount} thêm · -${delCount} xóa</div><div class="afb-diff-cols"><div><div class="afb-diff-col-label" style="color:var(--afb-red)">🗑 Cũ</div><div class="afb-diff-code">${oldHtml}</div></div><div><div class="afb-diff-col-label" style="color:var(--afb-green)">✓ Mới</div><div class="afb-diff-code">${newHtml}</div></div></div>`;
    };
    const close = () => overlay.remove();
    overlay.querySelector("#diff-run")?.addEventListener("click",run);
    overlay.querySelector("#diff-close")?.addEventListener("click",close);
    overlay.addEventListener("click",e=>{ if(e.target===overlay) close(); });
    document.addEventListener("keydown",e=>{ if(e.key==="Escape") close(); },{once:true});
  }

  _actSaveTemplate() {
    const formula = this.getValue();
    if (!formula) { this._setStatus("Nhập công thức trước","warning"); return; }
    const storageKey = "afb_saved_templates";
    let saved = [];
    try { saved = JSON.parse(localStorage.getItem(storageKey)||"[]"); } catch {}

    document.querySelector(".afb-save-tmpl-overlay")?.remove();
    const overlay = document.createElement("div");
    overlay.className = "afb-save-tmpl-overlay";
    overlay.style.cssText = "position:fixed;inset:0;z-index:1000010;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center";
    overlay.innerHTML = `<div style="background:#fff;border-radius:12px;padding:24px 28px;width:480px;max-width:95vw;box-shadow:0 20px 40px rgba(0,0,0,.2);border:1px solid #cbd5e1">
      <div style="font-size:15px;font-weight:700;color:#f59e0b;margin-bottom:16px">💾 Lưu mẫu công thức</div>
      <div style="margin-bottom:10px"><label style="font-size:12px;font-weight:600;color:#475569;display:block;margin-bottom:4px">Tên mẫu *</label><input id="st-name" type="text" placeholder="VD: Tính thành tiền VAT" style="width:100%;padding:8px 10px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;box-sizing:border-box;outline:none"/></div>
      <div style="margin-bottom:10px"><label style="font-size:12px;font-weight:600;color:#475569;display:block;margin-bottom:4px">Mô tả</label><input id="st-desc" type="text" placeholder="Mô tả ngắn..." style="width:100%;padding:8px 10px;border:1px solid #cbd5e1;border-radius:6px;font-size:13px;box-sizing:border-box;outline:none"/></div>
      <div style="margin-bottom:14px"><div style="font-family:var(--afb-mono);font-size:12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;padding:10px 12px;word-break:break-all;max-height:80px;overflow-y:auto">${_esc(formula)}</div></div>
      <div style="display:flex;gap:8px;justify-content:flex-end"><button id="st-cancel" style="padding:7px 14px;border-radius:6px;border:1px solid #cbd5e1;background:#e2e8f0;font-size:12px;font-weight:600;cursor:pointer">✕ Hủy</button><button id="st-save" style="padding:7px 16px;border-radius:6px;border:none;background:linear-gradient(135deg,#f59e0b,#e08800);color:#000;font-size:12px;font-weight:700;cursor:pointer">💾 Lưu</button></div>
    </div>`;
    document.body.appendChild(overlay);
    const nameInput = overlay.querySelector("#st-name");
    nameInput?.focus();
    const close = () => overlay.remove();
    overlay.querySelector("#st-cancel")?.addEventListener("click",close);
    overlay.addEventListener("click",e=>{ if(e.target===overlay) close(); });
    document.addEventListener("keydown",e=>{ if(e.key==="Escape") close(); },{once:true});
    overlay.querySelector("#st-save")?.addEventListener("click",() => {
      const name=(nameInput?.value||"").trim();
      if (!name) { nameInput.style.borderColor="#ef4444"; nameInput.focus(); return; }
      const newTmpl={ icon:"⭐", name, code:formula, desc:(overlay.querySelector("#st-desc")?.value||"").trim()||name, cat:"📌 Mẫu đã lưu", savedAt:new Date().toISOString() };
      saved.unshift(newTmpl);
      try { localStorage.setItem(storageKey, JSON.stringify(saved.slice(0,100))); } catch {}
      close();
      aluglass.formula.FunctionRegistry.addTemplate("📌 Mẫu đã lưu", newTmpl);
      this._switchSbTab("tmpl");
      this._setStatus("💾 Đã lưu mẫu: "+name,"ok");
    });
  }

  _injectSavedTemplates() {
    const storageKey = "afb_saved_templates";
    let saved = [];
    try { saved = JSON.parse(localStorage.getItem(storageKey)||"[]"); } catch {}
    if (!saved.length) return;
    // Inject vào FunctionRegistry một lần
    const existing = aluglass.formula.FunctionRegistry.getTemplates().find(s => s.category === "📌 Mẫu đã lưu");
    if (!existing) {
      const section = { category:"📌 Mẫu đã lưu", _savedSection:true, templates:saved.map(t => ({ icon:t.icon||"⭐", name:t.name, code:t.code, desc:t.desc||t.name })) };
      aluglass.formula.FunctionRegistry._templates.unshift(section);
    }
  }

  _computeCharDiff(a, b) {
    const MAX_LEN = 2000;
    if (a.length > MAX_LEN) a = a.substring(0, MAX_LEN);
    if (b.length > MAX_LEN) b = b.substring(0, MAX_LEN);
    const aW = a.split(/(\s+|\b)/), bW = b.split(/(\s+|\b)/);
    const m = aW.length, n = bW.length;
    const dp = Array.from({ length:m+1 }, () => new Array(n+1).fill(0));
    for (let i=1;i<=m;i++) for(let j=1;j<=n;j++) { if(aW[i-1]===bW[j-1]) dp[i][j]=dp[i-1][j-1]+1; else dp[i][j]=Math.max(dp[i-1][j],dp[i][j-1]); }
    const result = [];
    let i=m, j=n;
    while(i>0||j>0) {
      if(i>0&&j>0&&aW[i-1]===bW[j-1]) { result.unshift({type:"same",text:aW[i-1]}); i--;j--; }
      else if(j>0&&(i===0||dp[i][j-1]>=dp[i-1][j])) { result.unshift({type:"add",text:bW[j-1]}); j--; }
      else { result.unshift({type:"del",text:aW[i-1]}); i--; }
    }
    return result;
  }

  // ── Tour ──────────────────────────────────────────────────────────────────
  _maybeShowWelcomeTour() {
    if (localStorage.getItem(this._onboardKey)) return;
    setTimeout(() => {
      if (this._destroyed) return;
      this._runTour([
        { selector:".afb-header",  title:"🎉 Formula Builder v3!", desc:"Công cụ viết công thức mạnh mẽ với Monaco Editor, sidebar đầy đủ metadata, test với biến và nhiều tính năng mới." },
        { selector:".afb-act-test",title:"▶ Chạy thử công thức", desc:"Nhấn ▶ hoặc Ctrl+Enter để chạy công thức và xem kết quả ngay." },
        { selector:".afb-act-testvars",title:"🧪 Test với biến", desc:"Tính thử với giá trị tuỳ chỉnh cho mỗi biến — giống Excel." },
        { selector:".afb-sidebar", title:"📚 Sidebar đầy đủ metadata", desc:"Biến toàn cục, local, sibling table, hàm, snippet. Hover để xem doctype + fieldtype + giá trị." },
        { selector:".afb-act-suggest", title:"💡 Gợi ý AI", desc:"AI đề xuất công thức phù hợp với field của bạn." },
      ], 0, () => { localStorage.setItem(this._onboardKey, "1"); });
    }, 900);
  }

  _runTour(steps, index, onComplete) {
    if (this._destroyed || index >= steps.length) {
      document.querySelectorAll(".afb-tour-spotlight,.afb-tour-card").forEach(el => el.remove());
      if (this._tourEscHandler) { document.removeEventListener("keydown", this._tourEscHandler); this._tourEscHandler = null; }
      if (onComplete) onComplete(); return;
    }
    const step  = steps[index];
    const total = steps.length;
    document.querySelectorAll(".afb-tour-spotlight,.afb-tour-card").forEach(el => el.remove());
    const target = this.$wrapper[0].querySelector(step.selector) || document.querySelector(step.selector);
    if (!target) { this._runTour(steps, index+1, onComplete); return; }
    const rect = target.getBoundingClientRect(), pad = 6;
    const spotlight = document.createElement("div");
    spotlight.className = "afb-tour-spotlight";
    spotlight.style.cssText = `left:${rect.left-pad}px;top:${rect.top-pad}px;width:${rect.width+pad*2}px;height:${rect.height+pad*2}px;`;
    document.body.appendChild(spotlight);
    const dots = steps.map((_,i) => `<div class="afb-tour-progress-dot${i<index?" done":i===index?" active":""}"></div>`).join("");
    const card  = document.createElement("div");
    card.className = "afb-tour-card";
    card.innerHTML = `<div class="afb-tour-progress">${dots}</div><div class="afb-tour-step">${index+1} / ${total}</div><div class="afb-tour-title">${_esc(step.title)}</div><div class="afb-tour-desc">${_esc(step.desc)}</div><div class="afb-tour-actions"><button class="afb-btn" id="tour-skip">Bỏ qua</button>${index>0?'<button class="afb-btn" id="tour-prev">← Trước</button>':""}<button class="afb-btn primary" id="tour-next">${index<total-1?"Tiếp →":"Xong ✓"}</button></div>`;
    let cardLeft = rect.left, cardTop = rect.bottom + 12 + pad;
    if (cardTop + 180 > window.innerHeight - 20) cardTop = rect.top - 180 - 12 - pad;
    if (cardLeft + 300 > window.innerWidth - 16) cardLeft = window.innerWidth - 300 - 16;
    card.style.left = Math.max(8, cardLeft) + "px";
    card.style.top  = Math.max(8, cardTop) + "px";
    document.body.appendChild(card);
    const advance = () => this._runTour(steps, index+1, onComplete);
    const abort   = () => { document.querySelectorAll(".afb-tour-spotlight,.afb-tour-card").forEach(el => el.remove()); if(this._tourEscHandler) document.removeEventListener("keydown",this._tourEscHandler); localStorage.setItem(this._onboardKey,"1"); };
    card.querySelector("#tour-next")?.addEventListener("click", advance);
    card.querySelector("#tour-skip")?.addEventListener("click", abort);
    card.querySelector("#tour-prev")?.addEventListener("click", () => this._runTour(steps, index-1, onComplete));
    if (this._tourEscHandler) document.removeEventListener("keydown", this._tourEscHandler);
    this._tourEscHandler = e => { if(e.key==="Escape") abort(); };
    document.addEventListener("keydown", this._tourEscHandler);
  }

  // ── Tooltip ────────────────────────────────────────────────────────────────
  _initTooltip() {
    const tt = document.createElement("div");
    tt.className = "afb-tooltip";
    document.body.appendChild(tt);
    this._tooltip = tt;
  }

  // SỬA toàn bộ hàm thành:
  _showItemTooltip(ev, dataset) {
    if (!this._tooltip) return;
    const name    = dataset.name;
    const type    = dataset.itemType || "";
    const token   = dataset.token   || name;

    // 1. Hàm built-in / registered
    const fn = aluglass.formula.FunctionRegistry.find(name);
    if (fn) {
      this._tooltip.innerHTML = `
        <div class="afb-tooltip-name">${_esc(fn.name)}</div>
        <div class="afb-tooltip-sig">${_esc(fn.sig)}</div>
        <div class="afb-tooltip-desc">${_esc(fn.desc)}</div>
        <div class="afb-tooltip-example">${_esc(fn.example)}</div>
        <span class="afb-tooltip-source" style="background:rgba(6,182,212,.15);color:var(--afb-cyan)">${_esc(fn.cat)}</span>`;
      return this._positionTooltip(ev);
    }

    // 2. Snippet
    if (type === "snip") {
      const snips = aluglass.formula.FunctionRegistry.getSnippets();
      const snip  = snips.find(s => s.title === name || s.code === token);
      if (snip) {
        this._tooltip.innerHTML = `
          <div class="afb-tooltip-name">${_esc(snip.title)}</div>
          <div class="afb-tooltip-desc">${_esc(snip.desc || "Snippet")}</div>
          <div class="afb-tooltip-example">${_esc(snip.code.substring(0, 120))}${snip.code.length > 120 ? "…" : ""}</div>
          <span class="afb-tooltip-source" style="background:rgba(236,72,153,.15);color:var(--afb-pink)">snippet</span>`;
        return this._positionTooltip(ev);
      }
    }

    // 3. Template
    if (type === "tmpl" || dataset.itemCat?.startsWith("🎨") || dataset.itemCat?.startsWith("📌")) {
      const allTmpls = aluglass.formula.FunctionRegistry.getTemplates().flatMap(s => s.templates);
      const tmpl     = allTmpls.find(t => t.name === name || t.code === token);
      if (tmpl) {
        this._tooltip.innerHTML = `
          <div class="afb-tooltip-name">${tmpl.icon || "🎨"} ${_esc(tmpl.name)}</div>
          <div class="afb-tooltip-desc">${_esc(tmpl.desc || "")}</div>
          <div class="afb-tooltip-example">${_esc(tmpl.code.substring(0, 120))}${tmpl.code.length > 120 ? "…" : ""}</div>
          <span class="afb-tooltip-source" style="background:rgba(139,92,246,.15);color:var(--afb-purple)">template</span>`;
        return this._positionTooltip(ev);
      }
    }

    // 4. Context variable / field / ref
    const ctx3 = this._buildCtx();
    const item  = ctx3.allItems.find(i => i.name === name || i.insert === name)
                  || this._pinnedItems.find(i => i.name === name);
    if (!item) return;
    const srcColors = {
      global        : "rgba(139,92,246,.15);color:var(--afb-purple)",
      local         : "rgba(16,185,129,.15);color:var(--afb-green)",
      parent        : "rgba(16,185,129,.15);color:var(--afb-green)",
      current_row   : "rgba(59,130,246,.15);color:var(--afb-blue)",
      sibling_table : "rgba(59,130,246,.15);color:var(--afb-blue)",
      ref           : "rgba(249,115,22,.15);color:var(--afb-orange)",
    };
    const srcStyle = srcColors[item.source] || "rgba(100,116,139,.15);color:var(--afb-text3)";
    this._tooltip.innerHTML = `
      <div class="afb-tooltip-name">${_esc(item.name)}</div>
      ${item.label && item.label !== item.name ? `<div class="afb-tooltip-sig">${_esc(item.label)}</div>` : ""}
      <div class="afb-tooltip-meta">
        <strong>Doctype:</strong> ${_esc(item.doctype || "—")}<br>
        <strong>Kiểu:</strong> ${_esc(item.fieldtype || "—")}<br>
        <strong>Nguồn:</strong> ${_esc(item.source || "—")}
        ${item.rowName ? `<br><strong>Row:</strong> ${_esc(item.rowName)}` : ""}
      </div>
      ${item.value != null ? `<div class="afb-tooltip-example">Giá trị hiện tại: ${_esc(String(item.value))}</div>` : ""}
      <span class="afb-tooltip-source" style="background:${srcStyle}">${_esc(item.source || "—")}</span>`;
    this._positionTooltip(ev);
  }

  _positionTooltip(ev) {
    const rect = ev.currentTarget.getBoundingClientRect();
    this._tooltip.style.left = rect.right + 8 + "px";
    this._tooltip.style.top  = rect.top + "px";
    this._tooltip.classList.add("visible");
    requestAnimationFrame(() => {
      if (!this._tooltip) return;
      const tr = this._tooltip.getBoundingClientRect();
      if (tr.right  > window.innerWidth  - 10) this._tooltip.style.left = rect.left - tr.width - 8 + "px";
      if (tr.bottom > window.innerHeight - 10) this._tooltip.style.top  = window.innerHeight - tr.height - 10 + "px";
    });
  }
  
  _hideTooltip() { if (this._tooltip) this._tooltip.classList.remove("visible"); }

  // ── Drag Ghost ────────────────────────────────────────────────────────────
  _initDragGhost() {
    const ghost = document.createElement("div");
    ghost.className = "afb-drag-ghost";
    document.body.appendChild(ghost);
    this._dragGhost = ghost;
    this._onMouseMoveDrag = e => { if (!this._dragging || !this._dragGhost) return; this._dragGhost.style.left = e.clientX+18+"px"; this._dragGhost.style.top = e.clientY-8+"px"; };
    document.addEventListener("mousemove", this._onMouseMoveDrag);
  }

  _showDragGhost(text) { if (!this._dragGhost) return; this._dragging=true; this._dragGhost.textContent=text.length>42?text.substring(0,39)+"…":text; this._dragGhost.classList.add("visible"); }
  _hideDragGhost()     { this._dragging=false; if(this._dragGhost){this._dragGhost.classList.remove("visible"); this._dragGhost.style.left="-9999px";this._dragGhost.style.top="-9999px";} }

  // ── Insert Token ──────────────────────────────────────────────────────────
  _insertFocused(token) {
    if (!this.editor || !token) return;
    const snapshots = [];
    let el = this.$wrapper[0]?.parentElement;
    while (el && el !== document.body) {
      const style = window.getComputedStyle(el);
      if (style.overflowY === "auto" || style.overflowY === "scroll") { snapshots.push({ el, top:el.scrollTop, left:el.scrollLeft, behavior:style.scrollBehavior }); el.style.scrollBehavior = "auto"; }
      el = el.parentElement;
    }
    this.editor.focus();
    snapshots.forEach(({ el, top, left, behavior }) => { el.style.scrollBehavior=behavior; if(el.scrollTop!==top)el.scrollTop=top; if(el.scrollLeft!==left)el.scrollLeft=left; });
    const selection = this.editor.getSelection();
    const pos = this.editor.getPosition();
    if (!pos) return;
    const range = selection && !selection.isEmpty() ? selection : new monaco.Range(pos.lineNumber, pos.column, pos.lineNumber, pos.column);
    this._suppressResize = true;
    this.editor.executeEdits("sidebar-insert", [{ range, text:token+" ", forceMoveMarkers:true }]);
    setTimeout(() => { this._suppressResize = false; }, 150);
  }

  _setStatus(msg, type = "") {
    if (!this.$status?.length) return;
    const colorMap = { ok:"var(--afb-green)", err:"var(--afb-red)", warning:"var(--afb-amber)" };
    this.$status.css("color", colorMap[type] || "var(--afb-text2)").text(msg);
    clearTimeout(this._statusTimer);
    this._statusTimer = setTimeout(() => { if (this.$status) this.$status.text(""); }, 4000);
  }

  // ── Public API ────────────────────────────────────────────────────────────
  getValue()   { return this.editor ? this.editor.getValue().trim() : ""; }
  setValue(val) {
    if (!this.editor) return;
    const scroll = this.editor.saveViewState();
    this.editor.setValue(val || "");
    if (scroll) this.editor.restoreViewState(scroll);
    this._updateStatusLen(val || "");
  }
  focus()      { if (this.editor) this.editor.focus(); }
  updateScope(ns) { Object.assign(this.opts, ns); aluglass.formula.ContextCache.invalidate(this.opts.current_doctype, this.opts.current_docname); this._loadLiveContext(); }
  getPinnedItems()  { return [...this._pinnedItems]; }
  clearPinnedItems() { this._pinnedItems = []; this._updatePinBadge(); this._renderSbItems(); }

  /**
   * Serialize frm.doc hiện tại (bao gồm child table rows) để truyền lên server.
   * Hỗ trợ cả bản ghi chưa lưu (new-xxx).
   */
  _getFrmDocJson() {
    return aluglass.formula._serializeDoc(this.opts.current_doctype, this.opts.current_docname);
  }

  dispose() {
    clearTimeout(this._statusTimer); clearTimeout(this._validTimer);
    this._destroyed = true;
    this._disposables.forEach(d => d.dispose?.());
    if (this._registeredModel) { aluglass.formula.CompletionRegistry.unregister(this._registeredModel); this._registeredModel = null; }
    if (this._onMouseMoveDrag) { document.removeEventListener("mousemove", this._onMouseMoveDrag); this._onMouseMoveDrag = null; }
    if (this._tourEscHandler) { document.removeEventListener("keydown", this._tourEscHandler); this._tourEscHandler = null; }
    if (this.editor) this.editor.dispose();
    this.$wrapper?.off?.(".afb");
    if (this._tooltip)   this._tooltip.remove();
    if (this._dragGhost) this._dragGhost.remove();
    document.querySelectorAll(".afb-tour-spotlight,.afb-tour-card,.afb-suggest-overlay,.afb-shortcuts-overlay").forEach(el => el.remove());
  }
}

// ─── §9  UTILITY + PUBLIC API ────────────────────────────────────────────────
function _esc(str) {
  return String(str || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

aluglass.formula._esc = _esc; // export for formula_builder_field.js

// Shared doc serializer – used by both the dialog editor and patchField previews
const _SKIP_DOC_TYPES = new Set([
  "Section Break","Column Break","Tab Break","Heading","Button",
  "HTML","Image","Attach","Attach Image","Barcode","Signature",
  "Table","Table MultiSelect",
]);
aluglass.formula._serializeDoc = function(doctype, docname) {
  try {
    let frm = null;
    try { frm = (cur_frm && cur_frm.doctype === doctype) ? cur_frm : null; } catch {}
    if (!frm?.doc) return null;
    const doc  = frm.doc;
    const meta = frappe.get_meta?.(doctype);
    if (!meta) return null;
    const result = {};
    meta.fields.forEach(f => {
      if (_SKIP_DOC_TYPES.has(f.fieldtype)) return;
      const v = doc[f.fieldname];
      if (v !== undefined && v !== null) result[f.fieldname] = v;
    });
    meta.fields
      .filter(f => f.fieldtype === "Table" || f.fieldtype === "Table MultiSelect")
      .forEach(tableMf => {
        const rows      = doc[tableMf.fieldname] || [];
        const childMeta = frappe.get_meta?.(tableMf.options);
        result[tableMf.fieldname] = rows.map(row => {
          const rowData = {};
          if (childMeta) {
            childMeta.fields.forEach(cf => {
              if (_SKIP_DOC_TYPES.has(cf.fieldtype)) return;
              const v = row[cf.fieldname];
              if (v !== undefined && v !== null) rowData[cf.fieldname] = v;
            });
          } else {
            Object.keys(row).forEach(k => {
              if (!k.startsWith("__") && row[k] !== undefined && row[k] !== null) rowData[k] = row[k];
            });
          }
          if (row.idx  !== undefined) rowData.idx  = row.idx;
          if (row.name)               rowData.name = row.name;
          return rowData;
        });
      });
    return JSON.stringify(result);
  } catch (e) {
    console.warn("[FormulaBuilder] _serializeDoc error:", e);
    return null;
  }
};

aluglass.formula.Editor = AluglassFormulaEditor;

let _currentDialog = null;

aluglass.formula.openDialog = function(opts = {}) {
  // Đóng dialog cũ nếu có
  if (_currentDialog && _currentDialog.close) {
    _currentDialog.close();
    _currentDialog = null;
  }

  let editorInst = null;
  let overlay = null;
  let dialog = null;

  // Overlay
  overlay = document.createElement("div");
  overlay.className = "afb-custom-dialog-overlay";
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
    z-index: 1100;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(2px);
  `;

  // Dialog container
  dialog = document.createElement("div");
  dialog.className = "afb-custom-dialog";
  dialog.style.cssText = `
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    width: 90vw;
    max-width: 1200px;
    height: 80vh;
    max-height: 800px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    border: 1px solid #cbd5e1;
    transform: none;
  `;

  // Header
  const header = document.createElement("div");
  header.style.cssText = `
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 15px;
    flex-shrink: 0;
  `;
  header.innerHTML = `
    <span>📐 Formula Builder v3</span>
    <button class="afb-custom-dialog-close" style="background:none;border:none;font-size:20px;cursor:pointer;padding:0 8px;color:#64748b;">✕</button>
  `;

  // Body (chứa editor) – overflow visible để suggest widget thoát ra
  const body = document.createElement("div");
  body.style.cssText = `
    flex: 1;
    overflow: visible !important;
    position: relative;
    min-height: 0;
    padding: 0;
  `;
  const mountId = `afb-dlg-${++aluglass.formula._dlgCounter}`;
  const mountDiv = document.createElement("div");
  mountDiv.id = mountId;
  mountDiv.style.height = "100%";
  mountDiv.style.width = "100%";
  mountDiv.style.overflow = "visible";
  body.appendChild(mountDiv);

  // Footer
  const footer = document.createElement("div");
  footer.style.cssText = `
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 14px 20px;
    border-top: 1px solid #e2e8f0;
    background: #f8fafc;
    flex-shrink: 0;
  `;
  const runBtn = document.createElement("button");
  runBtn.textContent = "▶ Chạy thử";
  runBtn.className = "afb-btn";
  runBtn.style.cssText = "padding:6px 16px; font-size:13px;";
  const saveBtn = document.createElement("button");
  saveBtn.textContent = "💾 Lưu công thức";
  saveBtn.className = "afb-btn primary";
  saveBtn.style.cssText = "padding:6px 16px; font-size:13px;";
  footer.appendChild(runBtn);
  footer.appendChild(saveBtn);

  dialog.appendChild(header);
  dialog.appendChild(body);
  dialog.appendChild(footer);
  overlay.appendChild(dialog);
  document.body.appendChild(overlay);

  // Đóng dialog
  const closeDialog = () => {
    if (editorInst && editorInst.dispose) editorInst.dispose();
    if (overlay && overlay.remove) overlay.remove();
    if (_currentDialog === closeDialog) _currentDialog = null;
  };
  header.querySelector(".afb-custom-dialog-close").addEventListener("click", closeDialog);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) closeDialog(); });
  // Esc
  const escHandler = (e) => { if (e.key === "Escape") closeDialog(); };
  document.addEventListener("keydown", escHandler);
  const finalClose = () => {
    document.removeEventListener("keydown", escHandler);
    closeDialog();
  };

  // Nút lưu
  saveBtn.addEventListener("click", () => {
    if (opts.onSave) opts.onSave(editorInst?.getValue() || "");
    finalClose();
  });
  runBtn.addEventListener("click", () => {
    if (editorInst && editorInst._editorReady && editorInst.editor) editorInst._actTest();
    else frappe.show_alert({ message: "Editor chưa sẵn sàng", indicator: "orange" });
  });

  // Khởi tạo editor
  const editorOpts = Object.assign({ height: "100%", show_toolbar: true, show_sidebar: true, show_panel: true }, opts);
  editorInst = new AluglassFormulaEditor(editorOpts);
  editorInst.render($(mountDiv));

  // Layout và fix overflow guard
  setTimeout(() => {
    if (editorInst && editorInst.editor) {
      editorInst.editor.layout();
      const monacoContainer = mountDiv.querySelector(".monaco-editor");
      if (monacoContainer) {
        const overflowGuard = monacoContainer.querySelector(".overflow-guard");
        if (overflowGuard) overflowGuard.style.overflow = "visible";
        // Tăng padding-bottom cho view-lines qua JS để chắc chắn
        const viewLines = monacoContainer.querySelector(".view-lines");
        if (viewLines) viewLines.style.paddingBottom = "120px";
      }
      setTimeout(() => editorInst.editor.layout(), 50);
    }
  }, 100);

  _currentDialog = { close: finalClose };
  return _currentDialog;
};

// ── attachToField (pill UI) ────────────────────────────────────────────────
aluglass.formula.attachToField = function(frm, fieldname, editorOpts = {}) {
  const field = frm.fields_dict[fieldname];
  if (!field) { console.warn(`[FormulaBuilder] Field '${fieldname}' not found.`); return null; }
  const meta     = frappe.get_meta(frm.doctype);
  const fieldMeta= meta?.fields?.find(f => f.fieldname === fieldname);
  const label    = fieldMeta?.label || fieldname;
  const $wrap    = $(field.wrapper);
  $wrap.find(".afb-pill-wrap").remove();
  const getValue = () => frm.doc[fieldname] || "";
  const $pill = $(`<div class="afb-pill-wrap" style="display:flex;align-items:center;gap:6px;padding:4px 8px;margin-top:4px;background:#f8fafc;border:1px solid #cbd5e1;border-radius:6px;font-size:12px;font-family:monospace;cursor:pointer;min-height:30px;"><span style="color:#8b5cf6;font-size:11px;flex-shrink:0;">ƒ</span><span class="afb-pill-val" style="flex:1;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:300px;">${_esc(getValue())||'<span style="color:#94a3b8">Nhập công thức...</span>'}</span><span style="font-size:10px;color:#64748b;background:#e2e8f0;padding:2px 6px;border-radius:4px;flex-shrink:0;">✏ Sửa</span></div>`);
  $pill.on("click", () => {
    aluglass.formula.openDialog(Object.assign({ value:getValue(), current_doctype:frm.doctype, current_docname:frm.docname, current_field:fieldname, field_label:label, height:"560px" }, editorOpts, {
      onSave: val => { frm.set_value(fieldname, val); $pill.find(".afb-pill-val").html(val ? _esc(val) : '<span style="color:#94a3b8">Nhập công thức...</span>'); },
    }));
  });
  $wrap.append($pill);
  return $pill;
};

// ── attachToChildField (pill UI in child table) ───────────────────────────
aluglass.formula.attachToChildField = function(frm, childTableField, rowName, fieldname, editorOpts = {}) {
  const childData = frm.doc[childTableField] || [];
  const row = childData.find(r => r.name === rowName);
  if (!row) { console.warn(`[FormulaBuilder] Row '${rowName}' not found.`); return null; }
  const cdt = row.doctype, cdn = row.name;
  const grid = frm.fields_dict[childTableField]?.grid;
  if (!grid) return null;
  const gridRow = grid.get_row(cdn);
  if (!gridRow) return null;
  const field   = gridRow.get_field?.(fieldname);
  const wrapper = field?.wrapper || field?.$wrapper;
  if (!wrapper) return null;
  const $wrap = $(wrapper);
  $wrap.find(".afb-pill-wrap").remove();
  const getValue = () => row[fieldname] || "";
  const $pill = $(`<div class="afb-pill-wrap" style="display:inline-flex;align-items:center;gap:4px;padding:2px 6px;margin-top:2px;background:#f8fafc;border:1px solid #cbd5e1;border-radius:4px;font-size:11px;font-family:monospace;cursor:pointer;max-width:100%;box-sizing:border-box;"><span style="color:#8b5cf6;flex-shrink:0;">ƒ</span><span class="afb-pill-val" style="color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:180px;">${_esc(getValue())||'<span style="color:#94a3b8">—</span>'}</span><span style="color:#94a3b8;flex-shrink:0;">✏</span></div>`);
  $pill.on("click", () => {
    aluglass.formula.openDialog(Object.assign({ value:getValue(), current_doctype:frm.doctype, current_docname:frm.docname, child_table_field:childTableField, row_index:row.idx-1, current_field:fieldname, field_label:fieldname }, editorOpts, {
      onSave: val => { frappe.model.set_value(cdt, cdn, fieldname, val); $pill.find(".afb-pill-val").html(val ? _esc(val) : '<span style="color:#94a3b8">—</span>'); },
    }));
  });
  $wrap.append($pill);
  return $pill;
};

// ── quickEdit ────────────────────────────────────────────────────────────────
aluglass.formula.quickEdit = function(currentValue, opts = {}) {
  return new Promise(resolve => {
    aluglass.formula.openDialog({ ...opts, value:currentValue||"", onSave:val => resolve(val) });
  });
};

// ── syncFieldValue / syncAllFields ─────────────────────────────────────────
aluglass.formula.syncFieldValue = function(frm, fieldname) {
  // Sync editor ← frm.doc after server-side hooks
  // Used by formula_builder_field.js patchField editors
  const key = `${frm.doctype}::${frm.docname||"__new__"}::${fieldname}`;
  const api  = window._afbPatchedEditors?.[key];
  if (api) api.setValue(frm.doc[fieldname] || "");
};

aluglass.formula.syncAllFields = function(frm) {
  const prefix = `${frm.doctype}::`;
  const map = window._afbPatchedEditors || {};
  Object.entries(map).forEach(([key, api]) => {
    if (!key.startsWith(prefix)) return;
    const fieldname = key.split("::")[2];
    if (fieldname) api.setValue(frm.doc[fieldname] || "");
  });
};

// ── invalidateContext ────────────────────────────────────────────────────────
aluglass.formula.invalidateContext = function(frm, docname) {
  if (!frm?.doctype) return;
  aluglass.formula.ContextCache.invalidate(frm.doctype, docname || frm.docname);
  const inst = aluglass.formula._activeEditorInstance;
  if (inst && !inst._destroyed) inst._loadLiveContext?.();
};

// ── Backward-compat aliases ──────────────────────────────────────────────────
// CSS class aliases so existing code/markup still works
(function _compatAliases() {
  if (document.getElementById("afb-compat-css")) return;
  const s = document.createElement("style");
  s.id = "afb-compat-css";
  s.textContent = `
    /* Map old class names → new afb-* names for backward compat */
    .aluglass-fb-wrap     { /* use afb-wrap */ }
    .aluglass-field-patch-wrap { border:1px solid var(--afb-border,#cbd5e1);border-radius:var(--afb-radius,6px);overflow:hidden;background:#fff;transition:border-color 150ms,box-shadow 150ms; }
    .aluglass-field-patch-wrap:focus-within { border-color:var(--afb-amber,#f59e0b);box-shadow:0 0 0 3px rgba(245,158,11,.12); }
    .aluglass-fp-toolbar  { display:flex;align-items:center;gap:6px;padding:4px 8px;background:var(--afb-bg1,#f8fafc);border-bottom:1px solid var(--afb-border,#cbd5e1);font-size:11px; }
    .aluglass-fp-lang-badge { font-family:monospace;font-size:10px;background:var(--afb-bg3,#e2e8f0);color:var(--afb-text2,#334155);padding:2px 7px;border-radius:3px;font-weight:600; }
    .aluglass-fp-monaco   { border-radius:0 0 6px 6px;overflow:visible; }
    .aluglass-fp-monaco .monaco-editor, .aluglass-fp-monaco .monaco-editor .overflow-guard { overflow:visible !important; }
    .aluglass-fp-monaco .monaco-editor .view-lines { padding-bottom:4px !important; }
    .aluglass-btn         { display:inline-flex;align-items:center;gap:5px;padding:5px 12px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid var(--afb-border,#cbd5e1);background:var(--afb-bg3,#e2e8f0);color:var(--afb-text,#1e293b);outline:none;white-space:nowrap;transition:background 150ms,border-color 150ms; }
    .aluglass-btn:hover   { background:var(--afb-bg4,#cbd5e1); }
    .aluglass-btn.primary { background:linear-gradient(135deg,#f59e0b,#e08800);border-color:transparent;color:#000;font-weight:700; }
  `;
  document.head.appendChild(s);
})();

// ── Missing public API exports (fix: loadMonaco / _ContextBuilder / counters) ──
aluglass.formula.loadMonaco           = loadMonaco;        // required by formula_builder_dialog.js
aluglass.formula._ContextBuilder      = _ContextBuilder;   // required by formula_builder_field.js
aluglass.formula._dlgCounter          = aluglass.formula._dlgCounter          ?? 0;    // guard against NaN on ++
aluglass.formula._activeEditorInstance = aluglass.formula._activeEditorInstance ?? null; // guard against undefined read

console.info("[Formula Builder v3.1] Loaded — FunctionRegistry, ContextBuilder(§6), CompletionProvider v3, TestWithVars, ContextCache, CompletionRegistry, _serializeDoc shared, loadMonaco, _ContextBuilder exported");