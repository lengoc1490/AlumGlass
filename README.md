# AlumGlass ERP v28.8

ERP for aluminum & glass manufacturing — Quotation, Dynamic BOM, Costing, MRP, Construction.

> **v28.8 (2026-08-04):** Production hardening — composite pricing fix, immutability guard, role-based access, test suite, audit trail.
> See [TONG_QUAN_KIEN_TRUC.md](TONG_QUAN_KIEN_TRUC.md) for comprehensive architecture documentation.

## Architecture

- **60 Doctypes** across 10 business modules
- **Formula Builder v31** integration — DAG-based formula evaluation, no `eval()` on user input
- **Dynamic BOM engine** — config-driven, 7-phase calculation
- **Single source of truth**: AL Variable Library → Variable Set → Bom Set → Dialog
- **Zero hardcode**: Mọi logic từ DB. Thêm sản phẩm/ngành/config mới = 0 dòng code.

## Key Features

- **Configurable BOM**: Add products, materials, cost buckets, pricing dimensions without code
- **Dynamic formula fields**: Bom Set configures which fields are formulas
- **Composite key pricing**: Auto-discovered from Pricing Dimensions + Variable Mappings (fixed in v28.8)
- **Data-driven calc patterns**: Quantity calculation via DB-stored lambda functions
- **System variables**: Resolved from DB (Profile System, Product Type, Formula Global Variables)
- **Immutable BOM versions**: Snapshots capture all formula fields automatically (guarded in v28.8)
- **Role-based access**: 4 business roles (AL Sales, BOM Manager, Site Engineer, Accountant) — no System Manager needed for daily ops
- **Performance**: Batch queries, Redis caching (`get_cached_doc`), single commit (~10-12 queries/calc)
- **Audit trail**: `track_changes` on critical doctypes + ConfigSnapshot for every calculation

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app alumglass
```

After install, custom fields are auto-created on Quotation, Quotation Item, Sales Order, Item, Item Price, Batch, Work Order, etc.
Roles & permissions are auto-installed via `after_install` hook.

Seed demo data:
```bash
bench console
>>> from alumglass.setup.seed_demo_data import seed_all
>>> seed_all()
```

## Quick Start

```bash
# Run all tests
bench --site <site> run-tests --app alumglass

# Verify golden case (GIA_VAT ≈ 22,717,289 VND)
bench console
>>> from alumglass.run_test import main
>>> main()

# Test composite pricing (khác màu → khác giá)
bench --site <site> run-tests --app alumglass \
    --module alumglass.tests.test_composite_pricing
```

## Documentation

| Document | Description |
|---|---|
| [TONG_QUAN_KIEN_TRUC.md](TONG_QUAN_KIEN_TRUC.md) | ★ Toàn bộ kiến trúc, flow tính toán 7-phase, cơ chế, nguyên tắc |
| [HUONG_DAN_TRIEN_KHAI.md](HUONG_DAN_TRIEN_KHAI.md) | ★ Hướng dẫn triển khai từng bước: cài đặt → cấu hình → go-live |
| [ALUMGLASS_PRODUCTION_REFERENCE.md](ALUMGLASS_PRODUCTION_REFERENCE.md) | Production architecture & API reference (cập nhật v28.8) |
| [CHANGELOG-v28.7.md](CHANGELOG-v28.7.md) | Detailed changelog v28.7 + v28.8 |
| [CAU_TRUC_MODULE_VA_DOCTYPE.md](CAU_TRUC_MODULE_VA_DOCTYPE.md) | Module & doctype structure (60 doctypes) |
| [ARCHITECTURE-REVIEW-v28.2.md](ARCHITECTURE-REVIEW-v28.2.md) | Architecture review & recommendations |
| [NAMING-CONVENTION.md](NAMING-CONVENTION.md) | English naming conventions |

## Modules

| Module | Role | Doctypes |
|---|---|---|
| **AL Master Data** | Variable Library, Material Category, Profile System, Product Type, Pricing Dimension | 12 |
| **AL BOM Engine** | Dynamic BOM, Cost Buckets, Cost Templates, BOM Versions | 12 |
| **AL Formula Rules** | Calculation Rules, Dynamic Item Rules, Quantity Calc Methods | 8 |
| **AL Buying** | Supplier Price List, Material Plan, Cost Variance | 5 |
| **AL Stock** | Project Warehouse Map | 1 |
| **AL Manufacturing** | Cutting Standard, Cutting Plan (Alu+Glass), Production Order Bridge | 6 |
| **AL Construction** | Installation Team, Site Survey, Installation Order/Progress, Handover | 11 |
| **AL Account** | Project Profitability Snapshot, Financial Config | 2 |
| **AL Quality** | Warranty Policy | 1 |
| **AL AI Intelligence** | Suggestion Log, Interaction Log, Alert Config | 3 |

## Business Roles (v28.8)

| Role | Mô tả |
|---|---|
| **AL Sales User** | CRUD Quotation, Sales Order; Read Master Data, BOM Engine |
| **AL BOM Manager** | Full Master Data, BOM Engine, Formula Rules |
| **AL Site Engineer** | Full Construction; Read/Write Stock |
| **AL Project Accountant** | Full Account; Read/Write Buying |

## Development

```bash
cd apps/alumglass
pre-commit install
```

### Test

```bash
# All tests
bench --site <site> run-tests --app alumglass

# Specific modules
bench --site <site> run-tests --app alumglass --module alumglass.tests.test_bom_orchestrator
bench --site <site> run-tests --app alumglass --module alumglass.tests.test_composite_pricing

# Manual verification
bench console
>>> from alumglass.run_test import main
>>> main()
```

## License

MIT
