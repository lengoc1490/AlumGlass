/**
 * ═══════════════════════════════════════════════════════════════════════════
 * aluglass.formulaDialog  –  FORMULA DIALOG / TABLE / HTML BUILDER  v1.0
 * ═══════════════════════════════════════════════════════════════════════════
 *
 * Kiến trúc:
 *  §0   CSS Injection
 *  §1   Schema DSL helpers (defineDialog, defineTable, defineHTML)
 *  §2   MonacoCell  – Monaco nhúng trong 1 cell (reuse completionProvider từ formula_builder.js)
 *  §3   TableBuilder – render bảng phụ, bind row add/remove
 *  §4   HTMLBuilder  – render HTML template với Monaco cell
 *  §5   DialogBuilder – render toàn bộ dialog theo schema
 *  §6   Public API   – aluglass.formulaDialog.*
 *
 * Không import/modify formula_builder.js. Chỉ đọc:
 *   - aluglass.formula.loadMonaco()         (Monaco loader)
 *   - aluglass.formula.CompletionRegistry   (register completion model)
 *   - aluglass.formula.ContextCache         (context TTL cache)
 *   - aluglass.formula._esc()               (XSS escape)
 *   - aluglass.formula._serializeDoc()      (doc serializer)
 *   - window._afbPatchedEditors             (editor registry)
 *
 * Thêm vào hooks.py:
 *   app_include_js = [
 *     "/assets/aluglass/js/formula_builder.js?v=...",
 *     "/assets/aluglass/js/formula_builder_field.js?v=...",
 *     "/assets/aluglass/js/formula_builder_dialog.js?v=1.0.0",   ← THÊM
 *   ]
 *
 * @version 1.0.0
 */

frappe.provide("aluglass.formulaDialog");

// ═══════════════════════════════════════════════════════════════════════════
// §0  CSS INJECTION
// ═══════════════════════════════════════════════════════════════════════════
(function _injectDialogCSS() {
  if (document.getElementById("afbd-css-v1")) return;
  const s = document.createElement("style");
  s.id = "afbd-css-v1";
  s.textContent = `
  /* ── Dialog overlay ──────────────────────────────────────────────── */
  .afbd-overlay {
    position:fixed;inset:0;
    background:rgba(0,0,0,.55);
    z-index:1200;
    display:flex;align-items:center;justify-content:center;
    backdrop-filter:blur(3px);
  }
  .afbd-dialog {
    background:#fff;
    border-radius:12px;
    box-shadow:0 20px 60px rgba(0,0,0,.25);
    display:flex;flex-direction:column;
    overflow:hidden;
    max-height:92vh;
    font-family:'Inter','Segoe UI',sans-serif;
    font-size:13px;
    color:#1e293b;
    animation:afbd-pop .18s cubic-bezier(.34,1.56,.64,1);
    position:relative;
  }
  @keyframes afbd-pop {
    from { opacity:0;transform:scale(.93) translateY(8px); }
    to   { opacity:1;transform:scale(1)   translateY(0); }
  }

  /* ── Dialog header ───────────────────────────────────────────────── */
  .afbd-header {
    display:flex;align-items:center;gap:10px;
    padding:12px 18px;
    background:#f8fafc;
    border-bottom:1px solid #e2e8f0;
    flex-shrink:0;
  }
  .afbd-header-icon {
    width:28px;height:28px;border-radius:7px;
    background:linear-gradient(135deg,#f59e0b,#ec4899);
    display:flex;align-items:center;justify-content:center;
    font-size:14px;font-weight:700;color:#000;flex-shrink:0;
  }
  .afbd-header-title { font-weight:700;font-size:14px;flex:1; }
  .afbd-header-sub   { font-size:11px;color:#64748b;margin-top:1px; }
  .afbd-header-close {
    width:28px;height:28px;border-radius:6px;
    display:flex;align-items:center;justify-content:center;
    cursor:pointer;font-size:16px;color:#64748b;
    transition:background .12s,color .12s;
    border:none;background:transparent;
  }
  .afbd-header-close:hover { background:#e2e8f0;color:#1e293b; }

  /* ── Body / Sections ─────────────────────────────────────────────── */
  .afbd-body {
    flex:1;overflow-y:auto;
    padding:20px 22px;
    display:flex;flex-direction:column;gap:20px;
    scrollbar-width:thin;scrollbar-color:#cbd5e1 transparent;
  }
  .afbd-body::-webkit-scrollbar { width:5px; }
  .afbd-body::-webkit-scrollbar-thumb { background:#cbd5e1;border-radius:3px; }

  .afbd-section { display:flex;flex-direction:column;gap:8px; }
  .afbd-section-title {
    font-size:11px;font-weight:700;letter-spacing:.8px;
    text-transform:uppercase;color:#64748b;
    display:flex;align-items:center;gap:6px;
  }
  .afbd-section-title::after {
    content:'';flex:1;height:1px;background:#e2e8f0;
  }

  /* ── Filter row (Company / From date / To date …) ────────────────── */
  .afbd-filter-row {
    display:flex;flex-wrap:wrap;gap:14px;
  }
  .afbd-filter-field {
    display:flex;flex-direction:column;gap:4px;
    min-width:140px;
    flex:1;
  }
  .afbd-filter-field label {
    font-size:11px;font-weight:600;color:#475569;
  }
  .afbd-filter-field input,
  .afbd-filter-field select {
    padding:7px 10px;
    border:1px solid #cbd5e1;
    border-radius:6px;
    font-size:12px;
    color:#1e293b;
    outline:none;
    background:#fff;
    transition:border-color .12s, box-shadow .12s;
    font-family:inherit;
    width:100%;
    box-sizing:border-box;
  }
  .afbd-filter-field input:focus,
  .afbd-filter-field select:focus {
    border-color:#f59e0b;
    box-shadow:0 0 0 3px rgba(245,158,11,.12);
  }
  /* Monaco formula cell (filter row) */
  .afbd-filter-field .afbd-mono-cell-wrap {
    border:1px solid #cbd5e1;border-radius:6px;
    overflow:visible;
    transition:border-color .12s,box-shadow .12s;
    background:#fff;position:relative;
  }
  .afbd-filter-field .afbd-mono-cell-wrap:focus-within {
    border-color:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,.12);
  }

  /* ── Table ───────────────────────────────────────────────────────── */
  .afbd-table-wrap {
    border:1px solid #e2e8f0;
    border-radius:8px;
    overflow:hidden;
  }
  .afbd-table {
    width:100%;border-collapse:collapse;font-size:12px;
  }
  .afbd-table thead {
    background:#f8fafc;
    border-bottom:1px solid #e2e8f0;
  }
  .afbd-table th {
    padding:7px 10px;
    font-size:10px;font-weight:700;letter-spacing:.6px;
    text-transform:uppercase;color:#64748b;
    text-align:left;white-space:nowrap;
  }
  .afbd-table th.afbd-th-idx { width:40px;text-align:center; }
  .afbd-table th.afbd-th-del { width:34px; }
  .afbd-table tbody tr { border-bottom:1px solid #f1f5f9;transition:background .1s; }
  .afbd-table tbody tr:last-child { border-bottom:none; }
  .afbd-table tbody tr:hover { background:#fafbfd; }
  .afbd-table td { padding:5px 8px;vertical-align:middle; }
  .afbd-table td.afbd-td-idx {
    text-align:center;font-size:11px;color:#94a3b8;
    font-family:monospace;width:40px;
  }
  .afbd-table td input,
  .afbd-table td select {
    width:100%;padding:5px 8px;
    border:1px solid transparent;border-radius:5px;
    background:transparent;font-size:12px;color:#1e293b;
    outline:none;font-family:inherit;box-sizing:border-box;
    transition:border-color .12s,background .12s;
  }
  .afbd-table td input:hover,
  .afbd-table td select:hover { background:#f1f5f9; }
  .afbd-table td input:focus,
  .afbd-table td select:focus {
    border-color:#f59e0b;background:#fff;
    box-shadow:0 0 0 2px rgba(245,158,11,.1);
  }
  /* Monaco cell in table */
  .afbd-table td .afbd-mono-cell-wrap {
    border:1px solid transparent;border-radius:5px;
    overflow:visible;
    transition:border-color .12s;
    position:relative;min-width:100px;
  }
  .afbd-table td .afbd-mono-cell-wrap:focus-within {
    border-color:#f59e0b;
    box-shadow:0 0 0 2px rgba(245,158,11,.08);
  }
  .afbd-table tbody tr:hover td .afbd-mono-cell-wrap { border-color:#e2e8f0; }

  /* ── Delete button ───────────────────────────────────────────────── */
  .afbd-del-btn {
    width:26px;height:26px;border-radius:5px;
    border:none;background:transparent;
    cursor:pointer;color:#94a3b8;font-size:13px;
    display:flex;align-items:center;justify-content:center;
    transition:background .1s,color .1s;
  }
  .afbd-del-btn:hover { background:#fee2e2;color:#ef4444; }

  /* ── Add row button ──────────────────────────────────────────────── */
  .afbd-add-row-btn {
    display:inline-flex;align-items:center;gap:5px;
    padding:5px 12px;border-radius:6px;
    border:1.5px dashed #cbd5e1;background:transparent;
    color:#64748b;font-size:12px;font-weight:600;cursor:pointer;
    transition:border-color .12s,color .12s,background .12s;
    margin-top:6px;
    font-family:inherit;
  }
  .afbd-add-row-btn:hover {
    border-color:#f59e0b;color:#b45309;background:rgba(245,158,11,.05);
  }

  /* ── HTML template block ─────────────────────────────────────────── */
  .afbd-html-block {
    border:1px solid #e2e8f0;border-radius:8px;
    overflow:hidden;
    display:flex;flex-direction:column;
  }
  .afbd-html-toolbar {
    display:flex;align-items:center;gap:6px;
    padding:5px 10px;background:#f8fafc;
    border-bottom:1px solid #e2e8f0;font-size:11px;
  }
  .afbd-html-lang-badge {
    font-family:monospace;font-size:10px;font-weight:700;
    background:#e2e8f0;color:#475569;padding:2px 7px;border-radius:3px;
  }
  .afbd-html-preview-btn {
    margin-left:auto;
    display:inline-flex;align-items:center;gap:4px;
    padding:3px 9px;border-radius:4px;
    border:1px solid #cbd5e1;background:#fff;
    color:#475569;font-size:11px;cursor:pointer;font-weight:600;
    transition:border-color .12s,color .12s;font-family:inherit;
  }
  .afbd-html-preview-btn:hover { border-color:#f59e0b;color:#b45309; }
  .afbd-html-preview-area {
    display:none;border-top:1px solid #e2e8f0;
    padding:12px;background:#fff;
    font-size:12px;min-height:60px;
  }
  .afbd-html-preview-area.visible { display:block; }

  /* ── Footer / action bar ─────────────────────────────────────────── */
  .afbd-footer {
    display:flex;align-items:center;gap:8px;
    padding:12px 20px;
    background:#f8fafc;border-top:1px solid #e2e8f0;
    flex-shrink:0;
  }
  .afbd-footer-hint { font-size:11px;color:#94a3b8;flex:1; }
  .afbd-action-btn {
    display:inline-flex;align-items:center;gap:5px;
    padding:7px 18px;border-radius:7px;
    font-size:12px;font-weight:700;cursor:pointer;
    border:1px solid #cbd5e1;background:#e2e8f0;
    color:#1e293b;
    transition:background .12s,border-color .12s,transform .1s;
    font-family:inherit;outline:none;
  }
  .afbd-action-btn:hover { background:#cbd5e1; }
  .afbd-action-btn.primary {
    background:linear-gradient(135deg,#f59e0b,#e08800);
    border-color:transparent;color:#000;
  }
  .afbd-action-btn.primary:hover { background:linear-gradient(135deg,#fbbf24,#f59e0b); }
  .afbd-action-btn:active { transform:translateY(1px); }

  /* ── Monaco cell loading placeholder ─────────────────────────────── */
  .afbd-mono-loading {
    padding:5px 8px;font-size:11px;color:#94a3b8;font-family:monospace;min-height:24px;
    display:flex;align-items:center;gap:5px;
  }
  .afbd-mono-loading::before {
    content:'⏳';font-size:10px;animation:afbd-spin 1s linear infinite;display:inline-block;
  }
  @keyframes afbd-spin { to { transform:rotate(360deg); } }

  /* ── Suggest widget z-index fix ───────────────────────────────────── */
  .overflowingContentWidgets .suggest-widget { z-index:110000 !important; }
  .afbd-dialog .monaco-editor .view-lines { padding-bottom:40px !important; }
  .afbd-dialog .monaco-editor,
  .afbd-dialog .monaco-editor .overflow-guard { overflow:visible !important; }

  /* ── Resize handle ───────────────────────────────────────────────── */
  .afbd-resize-handle {
    position:absolute;bottom:0;right:0;
    width:16px;height:16px;cursor:se-resize;
    color:#cbd5e1;font-size:11px;
    display:flex;align-items:flex-end;justify-content:flex-end;
    padding:2px;box-sizing:border-box;
    user-select:none;
  }
  `;
  document.head.appendChild(s);
})();


// ═══════════════════════════════════════════════════════════════════════════
// §1  SCHEMA DSL HELPERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Định nghĩa một dialog schema.
 * @param {object} schema
 * @param {string} schema.title
 * @param {string} [schema.subtitle]
 * @param {string} [schema.icon]          emoji icon
 * @param {string} [schema.width]         default "760px"
 * @param {string} [schema.height]        default auto
 * @param {object} [schema.scope]         { current_doctype, current_docname, ... }
 * @param {Array}  schema.sections        mảng section
 * @param {string} [schema.footer_hint]
 * @returns schema object (pass vào DialogBuilder.open)
 */
aluglass.formulaDialog.define = function(schema) {
  return Object.assign({
    title: "Dialog",
    icon: "📐",
    width: "760px",
    sections: [],
    footer_hint: "",
  }, schema);
};

/**
 * Tạo một filter row section (Company, From date, To date…).
 * @param {object} opts
 * @param {string} opts.label         Section label
 * @param {Array}  opts.fields        mảng field descriptor
 * @returns section descriptor
 *
 * Field descriptor:
 *   { fieldname, label, fieldtype, value, width, placeholder, formula }
 *   fieldtype: "Data" | "Date" | "Select" | "Formula" | "Int" | "Float"
 *   formula: true  → dùng Monaco cell thay vì input thường
 */
aluglass.formulaDialog.filterSection = function(opts) {
  return Object.assign({ _type: "filter", label: "", fields: [] }, opts);
};

/**
 * Tạo một table section (Items, Accounts…).
 * @param {object} opts
 * @param {string} opts.label           Section label
 * @param {string} opts.key             key trong data object (vd: "items")
 * @param {Array}  opts.columns         mảng column descriptor
 * @param {Array}  [opts.rows]          initial rows
 * @param {boolean}[opts.show_idx]      hiển thị cột Idx (default true)
 * @param {boolean}[opts.allow_add]     cho phép thêm row (default true)
 * @param {boolean}[opts.allow_delete]  cho phép xóa row (default true)
 * @param {number} [opts.min_rows]      số row tối thiểu (default 3)
 * @returns section descriptor
 *
 * Column descriptor:
 *   { fieldname, label, fieldtype, width, placeholder, options, formula }
 *   fieldtype: "Data" | "Int" | "Float" | "Date" | "Select" | "Formula"
 *   formula: true  → Monaco cell
 *   width: CSS width string, ví dụ "120px", "1fr"
 */
aluglass.formulaDialog.tableSection = function(opts) {
  return Object.assign({
    _type: "table", label: "", key: "rows",
    columns: [], rows: [], show_idx: true,
    allow_add: true, allow_delete: true, min_rows: 3,
  }, opts);
};

/**
 * Tạo một HTML / Monaco section dùng để soạn template hoặc công thức dài.
 * @param {object} opts
 * @param {string} opts.label
 * @param {string} opts.key             key trong data object
 * @param {string} [opts.language]      "aluglass-formula" | "html" | "python" | ...
 * @param {string} [opts.height]        default "120px"
 * @param {boolean}[opts.show_preview]  preview HTML output (chỉ khi language=html)
 * @param {string} [opts.value]         initial value
 * @returns section descriptor
 */
aluglass.formulaDialog.htmlSection = function(opts) {
  return Object.assign({
    _type: "html", label: "", key: "html_content",
    language: "aluglass-formula", height: "120px",
    show_preview: false, value: "",
  }, opts);
};


// ═══════════════════════════════════════════════════════════════════════════
// §2  MONACO CELL (nhúng Monaco nhỏ vào 1 cell)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * MonacoCell – Monaco editor nhỏ trong một cell/field.
 * Tái dùng toàn bộ completion provider từ formula_builder.js.
 */
class MonacoCell {
  /**
   * @param {HTMLElement} container
   * @param {object} opts
   * @param {string}  opts.value
   * @param {string}  opts.language         default "aluglass-formula"
   * @param {string}  opts.height           default "28px"
   * @param {boolean} opts.word_wrap        default false
   * @param {object}  opts.scope            { current_doctype, current_docname, ... }
   * @param {function}opts.onChange
   * @param {string}  [opts.cellKey]        unique key để register editor
   */
  constructor(container, opts = {}) {
    this._container = container;
    this._opts      = Object.assign({
      value: "", language: "aluglass-formula", height: "28px",
      word_wrap: false, scope: {}, onChange: null, cellKey: null,
    }, opts);
    this._editor    = null;
    this._disposed  = false;
    this._init();
  }

  _init() {
    // Placeholder loading
    const loading = document.createElement("div");
    loading.className = "afbd-mono-loading";
    loading.textContent = "Monaco…";
    this._container.appendChild(loading);

    // Đảm bảo loadMonaco được gọi
    const monacoLoader = aluglass?.formula?.loadMonaco;
    if (typeof monacoLoader !== "function") {
      loading.textContent = "⚠ formula_builder.js chưa tải";
      console.error("[FormulaDialog] aluglass.formula.loadMonaco not found. Load formula_builder.js trước.");
      return;
    }

    monacoLoader().then(() => {
      if (this._disposed || typeof monaco === "undefined") return;
      loading.remove();

      const language = this._opts.language || "aluglass-formula";

      // Tạo model Monaco
      this._model = monaco.editor.createModel(this._opts.value || "", language);

      // Container div
      const edDiv = document.createElement("div");
      edDiv.style.cssText = `height:${this._opts.height};min-height:22px;`;
      this._container.appendChild(edDiv);

      // Tạo editor
      this._editor = monaco.editor.create(edDiv, {
        model              : this._model,
        language           : language,
        theme              : "vs",
        fontSize           : 12,
        fontFamily         : "'JetBrains Mono','Fira Code',monospace",
        lineNumbers        : "off",
        glyphMargin        : false,
        folding            : false,
        lineDecorationsWidth: 0,
        lineNumbersMinChars: 0,
        minimap            : { enabled: false },
        scrollbar          : { vertical:"hidden", horizontal:"hidden", useShadows:false },
        overviewRulerLanes : 0,
        hideCursorInOverviewRuler: true,
        scrollBeyondLastLine: false,
        wordWrap           : this._opts.word_wrap ? "on" : "off",
        quickSuggestions   : true,
        suggestOnTriggerCharacters: true,
        tabSize            : 2,
        renderLineHighlight: "none",
        contextmenu        : false,
        fixedOverflowWidgets: true,
        padding            : { top: 4, bottom: 4 },
      });

      // Đăng ký completion model vào CompletionRegistry của formula_builder.js
      if (aluglass?.formula?.CompletionRegistry?.register) {
        aluglass.formula.CompletionRegistry.register(this._model, this._opts.scope || {});
        this._registeredModel = this._model;
      }

      // onChange callback
      this._changeDisposable = this._model.onDidChangeContent(() => {
        if (typeof this._opts.onChange === "function") {
          this._opts.onChange(this._model.getValue());
        }
      });

      // Đăng ký vào global registry nếu có cellKey
      if (this._opts.cellKey) {
        window._afbPatchedEditors = window._afbPatchedEditors || {};
        window._afbPatchedEditors[this._opts.cellKey] = {
          getValue: () => this._model?.getValue() || "",
          setValue: (v) => this._model?.setValue(v || ""),
          dispose : () => this.dispose(),
          getEditor: () => this._editor,
        };
      }

      this._editorReady = true;
    });
  }

  getValue() {
    return this._model?.getValue() || "";
  }

  setValue(val) {
    if (this._model) this._model.setValue(val || "");
  }

  layout() {
    if (this._editor) this._editor.layout();
  }

  dispose() {
    this._disposed = true;
    this._changeDisposable?.dispose?.();
    if (this._registeredModel && aluglass?.formula?.CompletionRegistry?.unregister) {
      aluglass.formula.CompletionRegistry.unregister(this._registeredModel);
    }
    this._editor?.dispose?.();
    this._model?.dispose?.();
    if (this._opts.cellKey && window._afbPatchedEditors?.[this._opts.cellKey]) {
      delete window._afbPatchedEditors[this._opts.cellKey];
    }
    this._editor = null;
    this._model  = null;
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// §3  TABLE BUILDER
// ═══════════════════════════════════════════════════════════════════════════

class TableBuilder {
  /**
   * @param {HTMLElement} container
   * @param {object}      sectionDef   tableSection descriptor
   * @param {object}      scope        { current_doctype, current_docname, ... }
   */
  constructor(container, sectionDef, scope) {
    this._container = container;
    this._def       = sectionDef;
    this._scope     = scope || {};
    this._rows      = [];           // array of { _id, [fieldname]: value }
    this._cells     = new Map();    // _id+fieldname → MonacoCell
    this._uid       = 0;

    // Seed initial rows + min_rows blank
    const initRows  = sectionDef.rows || [];
    const minRows   = sectionDef.min_rows ?? 3;
    const seed      = initRows.length > 0 ? initRows : [];
    seed.forEach(r => this._pushRow(r));
    while (this._rows.length < minRows) this._pushRow({});

    this._render();
  }

  // ── Internal helpers ────────────────────────────────────────────────────

  _nextId() { return `r${++this._uid}`; }

  _pushRow(data = {}) {
    const row = Object.assign({ _id: this._nextId() }, data);
    this._rows.push(row);
    return row;
  }

  _cellKey(rowId, fieldname) {
    return `afbd::${this._def.key}::${rowId}::${fieldname}`;
  }

  _makeCell(td, row, col) {
    const ck  = this._cellKey(row._id, col.fieldname);
    const val = row[col.fieldname] ?? "";

    if (col.formula || col.fieldtype === "Formula") {
      // Monaco cell
      const wrap = document.createElement("div");
      wrap.className = "afbd-mono-cell-wrap";
      wrap.style.cssText = `width:${col.width || "100%"};min-width:80px;`;
      td.appendChild(wrap);

      const cell = new MonacoCell(wrap, {
        value    : String(val),
        language : col.language || "aluglass-formula",
        height   : col.cell_height || "28px",
        word_wrap: col.word_wrap || false,
        scope    : this._scope,
        cellKey  : ck,
        onChange : (v) => { row[col.fieldname] = v; },
      });
      this._cells.set(ck, cell);
    } else if (col.fieldtype === "Select") {
      const sel = document.createElement("select");
      const options = (col.options || "").split("\n").filter(Boolean);
      options.forEach(o => {
        const opt = document.createElement("option");
        opt.value = opt.textContent = o;
        if (o === val) opt.selected = true;
        sel.appendChild(opt);
      });
      sel.addEventListener("change", () => { row[col.fieldname] = sel.value; });
      td.appendChild(sel);
    } else {
      // Regular input
      const inp = document.createElement("input");
      inp.type  = col.fieldtype === "Date" ? "date"
                : (col.fieldtype === "Int" || col.fieldtype === "Float") ? "number"
                : "text";
      inp.value = val !== "" && val != null ? val : "";
      inp.placeholder = col.placeholder || "";
      if (col.width) inp.style.width = col.width;
      inp.addEventListener("input", () => { row[col.fieldname] = inp.value; });
      td.appendChild(inp);
    }
  }

  _renderRow(row, tbody) {
    const def = this._def;
    const tr  = document.createElement("tr");
    tr.dataset.rowId = row._id;

    // Idx
    if (def.show_idx !== false) {
      const tdIdx = document.createElement("td");
      tdIdx.className = "afbd-td-idx";
      tdIdx.textContent = this._rows.indexOf(row) + 1;
      tr.appendChild(tdIdx);
    }

    // Data columns
    def.columns.forEach(col => {
      const td = document.createElement("td");
      if (col.col_width) td.style.width = col.col_width;
      this._makeCell(td, row, col);
      tr.appendChild(td);
    });

    // Delete button
    if (def.allow_delete !== false) {
      const tdDel = document.createElement("td");
      const btn   = document.createElement("button");
      btn.className   = "afbd-del-btn";
      btn.title       = "Xóa dòng";
      btn.textContent = "✕";
      btn.addEventListener("click", () => this._deleteRow(row._id));
      tdDel.appendChild(btn);
      tr.appendChild(tdDel);
    }

    tbody.appendChild(tr);
  }

  _rebuildIdxColumn() {
    const trs = this._container.querySelectorAll("tbody tr");
    trs.forEach((tr, i) => {
      const tdIdx = tr.querySelector(".afbd-td-idx");
      if (tdIdx) tdIdx.textContent = i + 1;
    });
  }

  _deleteRow(rowId) {
    // Dispose Monaco cells for this row
    this._def.columns.forEach(col => {
      const ck   = this._cellKey(rowId, col.fieldname);
      const cell = this._cells.get(ck);
      if (cell) { cell.dispose(); this._cells.delete(ck); }
    });
    // Remove DOM
    const tr = this._container.querySelector(`tr[data-row-id="${rowId}"]`);
    if (tr) tr.remove();
    // Remove from _rows
    const idx = this._rows.findIndex(r => r._id === rowId);
    if (idx !== -1) this._rows.splice(idx, 1);
    this._rebuildIdxColumn();
  }

  _addRow() {
    const row  = this._pushRow({});
    const tbody = this._container.querySelector("tbody");
    this._renderRow(row, tbody);
    this._rebuildIdxColumn();
    // Scroll into view
    const newTr = tbody.querySelector(`tr[data-row-id="${row._id}"]`);
    newTr?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ── Render ──────────────────────────────────────────────────────────────

  _render() {
    const def = this._def;
    const wrap = document.createElement("div");
    wrap.className = "afbd-table-wrap";

    const table = document.createElement("table");
    table.className = "afbd-table";

    // THEAD
    const thead = document.createElement("thead");
    const trHead = document.createElement("tr");
    if (def.show_idx !== false) {
      const th = document.createElement("th");
      th.className = "afbd-th-idx";
      th.textContent = "Idx";
      trHead.appendChild(th);
    }
    def.columns.forEach(col => {
      const th = document.createElement("th");
      th.textContent = col.label || col.fieldname;
      if (col.col_width) th.style.width = col.col_width;
      trHead.appendChild(th);
    });
    if (def.allow_delete !== false) {
      const th = document.createElement("th");
      th.className = "afbd-th-del";
      trHead.appendChild(th);
    }
    thead.appendChild(trHead);
    table.appendChild(thead);

    // TBODY
    const tbody = document.createElement("tbody");
    this._rows.forEach(row => this._renderRow(row, tbody));
    table.appendChild(tbody);

    wrap.appendChild(table);
    this._container.appendChild(wrap);

    // Add row button
    if (def.allow_add !== false) {
      const addBtn = document.createElement("button");
      addBtn.className   = "afbd-add-row-btn";
      addBtn.innerHTML   = "＋ Thêm dòng";
      addBtn.addEventListener("click", () => this._addRow());
      this._container.appendChild(addBtn);
    }
  }

  // ── Public API ──────────────────────────────────────────────────────────

  /** Lấy data hiện tại dưới dạng array */
  getData() {
    return this._rows.map(row => {
      const out = {};
      this._def.columns.forEach(col => {
        const ck   = this._cellKey(row._id, col.fieldname);
        const cell = this._cells.get(ck);
        out[col.fieldname] = cell ? cell.getValue() : (row[col.fieldname] ?? "");
      });
      return out;
    });
  }

  /** Set data (rebuild rows) */
  setData(rows) {
    // Dispose all cells
    this._cells.forEach(c => c.dispose());
    this._cells.clear();
    // Clear DOM
    const tbody = this._container.querySelector("tbody");
    if (tbody) tbody.innerHTML = "";
    this._rows = [];
    this._uid  = 0;
    // Re-seed
    (rows || []).forEach(r => this._pushRow(r));
    while (this._rows.length < (this._def.min_rows ?? 3)) this._pushRow({});
    this._rows.forEach(row => {
      const tbody2 = this._container.querySelector("tbody");
      this._renderRow(row, tbody2);
    });
    this._rebuildIdxColumn();
  }

  dispose() {
    this._cells.forEach(c => c.dispose());
    this._cells.clear();
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// §4  HTML BUILDER (Monaco cho HTML / template / formula dài)
// ═══════════════════════════════════════════════════════════════════════════

class HTMLBuilder {
  constructor(container, sectionDef, scope) {
    this._container = container;
    this._def       = sectionDef;
    this._scope     = scope || {};
    this._cell      = null;
    this._render();
  }

  _render() {
    const def  = this._def;
    const wrap = document.createElement("div");
    wrap.className = "afbd-html-block";

    // Toolbar
    const toolbar = document.createElement("div");
    toolbar.className = "afbd-html-toolbar";
    const badge = document.createElement("span");
    badge.className   = "afbd-html-lang-badge";
    badge.textContent = def.language || "formula";
    toolbar.appendChild(badge);

    // Preview button (HTML only)
    let previewArea = null;
    if (def.show_preview && (def.language === "html" || def.language === "HTML")) {
      const prevBtn = document.createElement("button");
      prevBtn.className   = "afbd-html-preview-btn";
      prevBtn.textContent = "👁 Preview";
      prevBtn.addEventListener("click", () => {
        if (!previewArea) return;
        const visible = previewArea.classList.toggle("visible");
        if (visible) previewArea.innerHTML = this._cell?.getValue() || "";
      });
      toolbar.appendChild(prevBtn);

      previewArea = document.createElement("div");
      previewArea.className = "afbd-html-preview-area";
    }

    wrap.appendChild(toolbar);

    // Monaco container
    const monoWrap = document.createElement("div");
    monoWrap.className = "afbd-mono-cell-wrap";
    monoWrap.style.borderRadius = "0";
    monoWrap.style.borderLeft = monoWrap.style.borderRight = monoWrap.style.borderBottom = "none";
    monoWrap.style.borderTop = "none";
    wrap.appendChild(monoWrap);

    if (previewArea) wrap.appendChild(previewArea);

    this._container.appendChild(wrap);

    // Init Monaco cell
    this._cell = new MonacoCell(monoWrap, {
      value    : def.value || "",
      language : def.language || "aluglass-formula",
      height   : def.height || "120px",
      word_wrap: true,
      scope    : this._scope,
      cellKey  : `afbd::html::${def.key}`,
      onChange : (v) => {
        if (previewArea && previewArea.classList.contains("visible")) {
          previewArea.innerHTML = v;
        }
      },
    });
  }

  getValue() { return this._cell?.getValue() || ""; }
  setValue(v){ this._cell?.setValue(v); }
  dispose()  { this._cell?.dispose(); }
}


// ═══════════════════════════════════════════════════════════════════════════
// §5  DIALOG BUILDER
// ═══════════════════════════════════════════════════════════════════════════

class DialogBuilder {
  /**
   * @param {object} schema   aluglass.formulaDialog.define(...)
   */
  constructor(schema) {
    this._schema    = schema;
    this._overlay   = null;
    this._dialog    = null;
    this._scope     = schema.scope || {};
    this._filterData= {};       // flat key→value cho filter section
    this._tables    = new Map();// key → TableBuilder
    this._htmlBlocks= new Map();// key → HTMLBuilder
    this._filterCells = new Map(); // key → MonacoCell (filter formula fields)
    this._onSave    = schema.onSave || null;
    this._onCancel  = schema.onCancel || null;
  }

  // ── Open ────────────────────────────────────────────────────────────────

  open() {
    if (this._overlay) return;
    this._buildDOM();
    document.body.appendChild(this._overlay);

    // Esc to close
    this._escHandler = (e) => { if (e.key === "Escape") this.close(); };
    document.addEventListener("keydown", this._escHandler);

    // Layout Monaco editors after mount
    setTimeout(() => this._layoutAll(), 120);
    return this;
  }

  close() {
    document.removeEventListener("keydown", this._escHandler);
    this._tables.forEach(t => t.dispose());
    this._htmlBlocks.forEach(h => h.dispose());
    this._filterCells.forEach(c => c.dispose());
    this._tables.clear();
    this._htmlBlocks.clear();
    this._filterCells.clear();
    if (this._overlay) { this._overlay.remove(); this._overlay = null; }
    if (typeof this._onCancel === "function") this._onCancel();
  }

  /** Lấy toàn bộ data từ dialog */
  getData() {
    const result = Object.assign({}, this._filterData);

    // Filter monaco cells
    this._filterCells.forEach((cell, key) => {
      result[key] = cell.getValue();
    });

    // Tables
    this._tables.forEach((tb, key) => {
      result[key] = tb.getData();
    });

    // HTML blocks
    this._htmlBlocks.forEach((hb, key) => {
      result[key] = hb.getValue();
    });

    return result;
  }

  /** Set data vào dialog */
  setData(data = {}) {
    // Filter fields
    this._schema.sections
      .filter(s => s._type === "filter")
      .forEach(sec => {
        sec.fields.forEach(f => {
          if (data[f.fieldname] === undefined) return;
          if (f.formula || f.fieldtype === "Formula") {
            this._filterCells.get(f.fieldname)?.setValue(String(data[f.fieldname]));
          } else {
            const inp = this._dialog?.querySelector(
              `[data-filter-field="${f.fieldname}"]`
            );
            if (inp) inp.value = data[f.fieldname];
            this._filterData[f.fieldname] = data[f.fieldname];
          }
        });
      });

    // Tables
    this._schema.sections
      .filter(s => s._type === "table")
      .forEach(sec => {
        if (data[sec.key] !== undefined) {
          this._tables.get(sec.key)?.setData(data[sec.key]);
        }
      });

    // HTML blocks
    this._schema.sections
      .filter(s => s._type === "html")
      .forEach(sec => {
        if (data[sec.key] !== undefined) {
          this._htmlBlocks.get(sec.key)?.setValue(data[sec.key]);
        }
      });
  }

  // ── DOM builders ────────────────────────────────────────────────────────

  _buildDOM() {
    const schema = this._schema;

    // Overlay
    this._overlay = document.createElement("div");
    this._overlay.className = "afbd-overlay";
    this._overlay.addEventListener("mousedown", (e) => {
      if (e.target === this._overlay) this.close();
    });

    // Dialog
    const dlg = document.createElement("div");
    dlg.className = "afbd-dialog";
    dlg.style.width = schema.width || "760px";
    if (schema.height) dlg.style.height = schema.height;
    dlg.style.maxWidth = "98vw";
    this._dialog = dlg;

    // Header
    dlg.appendChild(this._buildHeader());

    // Body
    const body = document.createElement("div");
    body.className = "afbd-body";

    schema.sections.forEach(sec => {
      body.appendChild(this._buildSection(sec));
    });

    dlg.appendChild(body);

    // Footer
    dlg.appendChild(this._buildFooter());

    // Resize handle
    const resizeHandle = document.createElement("div");
    resizeHandle.className = "afbd-resize-handle";
    resizeHandle.textContent = "⤡";
    resizeHandle.title = "Kéo để thay đổi kích thước";
    this._initResize(dlg, resizeHandle);
    dlg.appendChild(resizeHandle);

    this._overlay.appendChild(dlg);
  }

  _buildHeader() {
    const schema = this._schema;
    const header = document.createElement("div");
    header.className = "afbd-header";

    const iconEl = document.createElement("div");
    iconEl.className   = "afbd-header-icon";
    iconEl.textContent = schema.icon || "📐";
    header.appendChild(iconEl);

    const titleWrap = document.createElement("div");
    titleWrap.style.flex = "1";
    const titleEl = document.createElement("div");
    titleEl.className   = "afbd-header-title";
    titleEl.textContent = schema.title || "Dialog";
    titleWrap.appendChild(titleEl);
    if (schema.subtitle) {
      const sub = document.createElement("div");
      sub.className   = "afbd-header-sub";
      sub.textContent = schema.subtitle;
      titleWrap.appendChild(sub);
    }
    header.appendChild(titleWrap);

    const closeBtn = document.createElement("button");
    closeBtn.className   = "afbd-header-close";
    closeBtn.textContent = "✕";
    closeBtn.title       = "Đóng (Esc)";
    closeBtn.addEventListener("click", () => this.close());
    header.appendChild(closeBtn);

    return header;
  }

  _buildFooter() {
    const schema = this._schema;
    const footer = document.createElement("div");
    footer.className = "afbd-footer";

    const hint = document.createElement("span");
    hint.className   = "afbd-footer-hint";
    hint.textContent = schema.footer_hint || "Ctrl+Space: gợi ý • Esc: đóng";
    footer.appendChild(hint);

    // Custom buttons
    const extraBtns = schema.extra_buttons || [];
    extraBtns.forEach(eb => {
      const btn = document.createElement("button");
      btn.className   = "afbd-action-btn " + (eb.type || "");
      btn.textContent = eb.label || "Action";
      btn.addEventListener("click", () => {
        if (typeof eb.onClick === "function") eb.onClick(this.getData(), this);
      });
      footer.appendChild(btn);
    });

    // Cancel
    const cancelBtn = document.createElement("button");
    cancelBtn.className   = "afbd-action-btn";
    cancelBtn.textContent = "✕ Hủy";
    cancelBtn.addEventListener("click", () => this.close());
    footer.appendChild(cancelBtn);

    // Save
    const saveBtn = document.createElement("button");
    saveBtn.className   = "afbd-action-btn primary";
    saveBtn.textContent = schema.save_label || "💾 Lưu";
    saveBtn.addEventListener("click", () => this._onSaveClick());
    footer.appendChild(saveBtn);

    return footer;
  }

  _buildSection(sec) {
    const wrap = document.createElement("div");
    wrap.className = "afbd-section";

    if (sec.label) {
      const title = document.createElement("div");
      title.className   = "afbd-section-title";
      title.textContent = sec.label;
      wrap.appendChild(title);
    }

    switch (sec._type) {
      case "filter": this._buildFilterSection(wrap, sec); break;
      case "table":  this._buildTableSection(wrap, sec);  break;
      case "html":   this._buildHTMLSection(wrap, sec);   break;
      default:
        wrap.innerHTML += `<div style="color:#ef4444;font-size:11px;">Unknown section type: ${sec._type}</div>`;
    }

    return wrap;
  }

  _buildFilterSection(wrap, sec) {
    const row = document.createElement("div");
    row.className = "afbd-filter-row";

    sec.fields.forEach(f => {
      const fieldWrap = document.createElement("div");
      fieldWrap.className = "afbd-filter-field";
      if (f.width) fieldWrap.style.flexBasis = f.width;
      if (f.max_width) fieldWrap.style.maxWidth = f.max_width;

      const label = document.createElement("label");
      label.textContent = f.label || f.fieldname;
      fieldWrap.appendChild(label);

      if (f.formula || f.fieldtype === "Formula") {
        // Monaco cell
        const cellWrap = document.createElement("div");
        cellWrap.className = "afbd-mono-cell-wrap";
        fieldWrap.appendChild(cellWrap);

        const cell = new MonacoCell(cellWrap, {
          value    : String(f.value || ""),
          language : f.language || "aluglass-formula",
          height   : f.height || "28px",
          word_wrap: f.word_wrap || false,
          scope    : this._scope,
          cellKey  : `afbd::filter::${f.fieldname}`,
          onChange : (v) => { this._filterData[f.fieldname] = v; },
        });
        this._filterCells.set(f.fieldname, cell);
      } else if (f.fieldtype === "Select") {
        const sel = document.createElement("select");
        sel.dataset.filterField = f.fieldname;
        const opts = (f.options || "").split("\n").filter(Boolean);
        opts.forEach(o => {
          const opt = document.createElement("option");
          opt.value = opt.textContent = o;
          if (o === f.value) opt.selected = true;
          sel.appendChild(opt);
        });
        sel.addEventListener("change", () => { this._filterData[f.fieldname] = sel.value; });
        this._filterData[f.fieldname] = f.value || (opts[0] || "");
        fieldWrap.appendChild(sel);
      } else {
        const inp = document.createElement("input");
        inp.type  = f.fieldtype === "Date" ? "date"
                  : (f.fieldtype === "Int" || f.fieldtype === "Float") ? "number"
                  : "text";
        inp.value = f.value !== undefined ? f.value : "";
        inp.placeholder   = f.placeholder || "";
        inp.dataset.filterField = f.fieldname;
        inp.addEventListener("input", () => { this._filterData[f.fieldname] = inp.value; });
        this._filterData[f.fieldname] = f.value ?? "";
        fieldWrap.appendChild(inp);
      }

      row.appendChild(fieldWrap);
    });

    wrap.appendChild(row);
  }

  _buildTableSection(wrap, sec) {
    const tb = new TableBuilder(wrap, sec, this._scope);
    this._tables.set(sec.key, tb);
  }

  _buildHTMLSection(wrap, sec) {
    const hb = new HTMLBuilder(wrap, sec, this._scope);
    this._htmlBlocks.set(sec.key, hb);
  }

  // ── Save ────────────────────────────────────────────────────────────────

  _onSaveClick() {
    const data = this.getData();
    if (typeof this._onSave === "function") {
      const result = this._onSave(data, this);
      // Nếu onSave trả về false → không đóng
      if (result === false) return;
    }
    this.close();
  }

  // ── Layout ──────────────────────────────────────────────────────────────

  _layoutAll() {
    this._filterCells.forEach(c => c.layout());
    this._tables.forEach(tb => {
      tb._cells.forEach(c => c.layout());
    });
    this._htmlBlocks.forEach(hb => hb._cell?.layout());
  }

  // ── Resize ──────────────────────────────────────────────────────────────

  _initResize(dlg, handle) {
    let startX, startY, startW, startH;
    handle.addEventListener("mousedown", (e) => {
      e.preventDefault();
      startX = e.clientX;
      startY = e.clientY;
      const rect = dlg.getBoundingClientRect();
      startW = rect.width;
      startH = rect.height;

      const onMove = (ev) => {
        const dx = ev.clientX - startX;
        const dy = ev.clientY - startY;
        dlg.style.width  = Math.max(400, startW + dx) + "px";
        dlg.style.height = Math.max(300, startH + dy) + "px";
        this._layoutAll();
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup",   onUp);
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup",   onUp);
    });
  }
}


// ═══════════════════════════════════════════════════════════════════════════
// §6  PUBLIC API
// ═══════════════════════════════════════════════════════════════════════════

/** Mở một dialog từ schema, trả về DialogBuilder instance */
aluglass.formulaDialog.open = function(schema, opts = {}) {
  const merged = Object.assign({}, schema, {
    onSave  : opts.onSave   || schema.onSave,
    onCancel: opts.onCancel || schema.onCancel,
    scope   : opts.scope    || schema.scope || {},
  });
  const builder = new aluglass.formulaDialog.Builder(merged);
  builder.open();
  return builder;
};

/** Expose class để advanced use */
aluglass.formulaDialog.Builder   = DialogBuilder;
aluglass.formulaDialog.MonacoCell = MonacoCell;
aluglass.formulaDialog.TableBuilder = TableBuilder;
aluglass.formulaDialog.HTMLBuilder  = HTMLBuilder;

console.info("[Formula Dialog Builder v1.0] Loaded — DialogBuilder, TableBuilder, HTMLBuilder, MonacoCell");