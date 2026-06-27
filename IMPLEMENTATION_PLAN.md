# AlumGlass ERP v17.0 — Kế Hoạch Triển Khai

## Cấu trúc app đã tạo

```
apps/alumglass/
├── IMPLEMENTATION_PLAN.md            ← File này
├── requirements.txt
├── alumglass/                        ← Frappe Python module
│   ├── hooks.py                      ← ĐÃ CẬP NHẬT: doc_events, scheduler, JS/CSS, fixtures
│   ├── __init__.py
│   ├── engine/                       ← Core calculation engine (8 files)
│   │   ├── module_registry.py        ← Event bus (register_hook/fire_hooks)
│   │   ├── variable_resolver.py      ← Resolve biến + inject glass_thick
│   │   ├── rule_engine.py            ← CONSTANT/FORMULA/THRESHOLD/LOOKUP/SEQUENCE
│   │   ├── profile_interpreter.py    ← 2-pass: Scan → Build (NHOM/KINH/VTP/PK)
│   │   ├── pk_resolver.py            ← PK Set + substitution + validation
│   │   ├── cost_accumulator.py       ← Cost buckets + template formulas
│   │   ├── snapshot_builder.py       ← ConfigSnapshot + drift detection
│   │   └── orchestrator.py           ← BomOrchestrator 6 bước + hooks + APIs
│   ├── modules/                      ← Module Layer v17 (10 files)
│   │   ├── __init__.py               ← Đăng ký hooks A→D
│   │   ├── discount/                 ← DiscountStack + API (2 files)
│   │   ├── version/                  ← BOM Version Manager + API (2 files)
│   │   ├── approval/                 ← Approval Engine (1 file)
│   │   ├── mrp/                      ← MRP Lite Aggregator + API (2 files)
│   │   ├── cost_variance/            ← Variance Analyzer + API (2 files)
│   │   ├── notification/             ← Notification Engine + Alert Rules (2 files)
│   │   └── analytics/                ← KPI Calculator + API (2 files)
│   ├── custom_fields/                ← Custom field JSON (2 files)
│   │   ├── item_custom_fields.json
│   │   └── quotation_item_custom_fields.json
│   ├── patches/                      ← Migration scripts (3 files)
│   │   └── v17_0/
│   │       ├── create_initial_bom_versions.py
│   │       ├── setup_roles.py
│   │       └── import_fixtures.py
│   ├── public/js/                    ← Client-side JS (2 files)
│   │   ├── quotation_item.js         ← BOM Dialog, Glass Selector, Calculate
│   │   └── bom_dialog.js             ← BOM Form: Publish, Diff, Rollback, Formula Builder
│   └── scheduled_tasks.py            ← Daily/Weekly cron jobs
```

## Tổng cộng: 28 file Python + 2 file JS + 2 file JSON + 3 file patch = 35 files đã tạo

## Hướng dẫn cài đặt nhanh

```bash
cd ~/frappe-bench

# 1. Setup app
bench setup-app apps/alumglass

# 2. Cài vào site
bench --site your-site.com install-app alumglass

# 3. Migrate (tạo DocTypes + custom fields + chạy patches)
bench --site your-site.com migrate

# 4. Import fixtures
bench --site your-site.com execute alumglass.patches.v17_0.import_fixtures.execute

# 5. Setup roles
bench --site your-site.com execute alumglass.patches.v17_0.setup_roles.execute

# 6. Build JS assets
bench build

# 7. Restart
bench restart
```

## Công việc còn lại cần làm

### BẮT BUỘC (để app chạy được):
1. **Tạo 34 DocType** qua Desk UI (Setup → DocType → New) hoặc JSON files
   - Tham khảo field definitions trong `AlumGlass_ERP_v17_FINAL.md` Section IV
2. **Tạo custom fields** trên Sales Order Item và Sales Invoice Item (tương tự Quotation Item)
3. **Import master data fixtures** (AL Glass Master, AL Calculation Rule, AL Cost Bucket, AL Cost Template) — xem Section VI trong design doc

### NÊN LÀM:
4. **Tạo thư mục fixtures/** với JSON files cho master data
5. **Tạo các Script Reports** (al_quotation_summary, al_bom_price_analysis, v.v.) trong `alumglass/reports/`
6. **Viết unit tests** cho engine

## Tích hợp formula_builder — Các API đã sử dụng

### Python:
- `from formula_builder.formula_utils import FormulaEngine` — Orchestrator bước 6
- `from formula_builder.api.settings_cache import get_allowed_funcs` — Security validation

### JavaScript:
- `formula_builder.formula.initGridField(frm, gridField, fieldname, opts)` — Monaco trong grid cells
- `formula_builder.formula.patchField(frm, fieldname, opts)` — Monaco trong form fields
- `formula_builder.formula.openDialog(opts)` — Full Formula Builder dialog

Các field đã tích hợp Formula Builder trong `bom_dialog.js`:
- `al_lines.qty_formula`
- `al_lines.show_condition`
- `al_lines.width_formula`
- `al_lines.height_formula`
- `al_lines.panel_count_formula`
- `al_lines.qty_per_panel_formula`

## Luồng tính giá (BomOrchestrator)

1. VariableResolver.resolve() → inputs_dict + glass_thick injection
2. ProfileInterpreter.pass1_scan() → variable_registry
3. ProfileInterpreter.pass2_build() → all_formulas
4. PkResolver.build_formulas() → formulas_pk
5. CostAccumulator.build() → formulas_cost
6. FormulaEngine.calculate() + SnapshotBuilder.persist()
7. Hook A: DiscountStack.apply()
8. Hook B: BOMVersionManager.link_version()
9. Hook C: CostVarianceAnalyzer.register()
10. Hook D: NotificationEngine.check_alerts()
