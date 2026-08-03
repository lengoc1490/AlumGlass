# AlumGlass ERP v28.7

ERP for aluminum & glass manufacturing — Quotation, Dynamic BOM, Costing, MRP, Construction.

> **v28.7 (2026-08-03):** Zero hardcode engine, data-driven architecture, 50% fewer DB queries.
> See [CHANGELOG-v28.7.md](CHANGELOG-v28.7.md) for full details.

## Architecture

- **60+ Doctypes** across 12 business modules
- **Formula Builder v31** integration — DAG-based formula evaluation, no `eval()` on user input
- **Dynamic BOM engine** — config-driven, not flat/static BOM
- **Single source of truth**: AL Variable Library → Variable Set → Bom Set → Dialog
- **0 lines of code** to add new products, materials, cost buckets, pricing dimensions, calculation patterns, or system variables

## Key Features

- **Configurable BOM**: Add products, materials, cost buckets, pricing dimensions without code
- **Dynamic formula fields**: Bom Set configures which fields are formulas
- **Composite key pricing**: Auto-discovered from Pricing Dimensions + Variable Mappings
- **Data-driven calc patterns**: Quantity calculation via DB-stored lambda functions
- **System variables**: Resolved from DB (Profile System, Product Type, Formula Global Variables)
- **Immutable BOM versions**: Snapshots capture all formula fields automatically
- **Performance**: Batch queries, Redis caching (`get_cached_doc`), single commit

## Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app alumglass
```

After install, custom fields are auto-created on Quotation, Quotation Item, Sales Order, Item, Item Price, Batch, Work Order, etc.

Seed demo data:
```bash
bench console
>>> from alumglass.setup.seed_demo_data import seed_all
>>> seed_all()
```

## Documentation

| Document | Description |
|---|---|
| [ALUMGLASS_PRODUCTION_REFERENCE.md](ALUMGLASS_PRODUCTION_REFERENCE.md) | Production architecture & API reference |
| [CHANGELOG-v28.7.md](CHANGELOG-v28.7.md) | v28.7 detailed changelog |
| [v28.2-UPGRADE-ANALYSIS.md](v28.2-UPGRADE-ANALYSIS.md) | Hardcode elimination analysis & plan |
| [ARCHITECTURE-REVIEW-v28.2.md](ARCHITECTURE-REVIEW-v28.2.md) | Architecture review |
| [CAU_TRUC_MODULE_VA_DOCTYPE.md](CAU_TRUC_MODULE_VA_DOCTYPE.md) | Module & doctype structure |
| [KE_HOACH_TRIEN_KHAI_CHI_TIET.md](KE_HOACH_TRIEN_KHAI_CHI_TIET.md) | Detailed implementation plan |
| [NAMING-CONVENTION.md](NAMING-CONVENTION.md) | Naming conventions |

## Modules

| Module | Role |
|---|---|
| **AL Master Data** | Variable Library, Material Category, Profile System, Product Type, Pricing Dimension |
| **AL BOM Engine** | Dynamic BOM, Cost Buckets, Cost Templates, BOM Versions |
| **AL Formula Rules** | Calculation Rules, Dynamic Item Rules, Quantity Calc Methods |
| **AL Selling** | Quotation/Sales Order overrides |
| **AL Buying** | Supplier Price List, Material Plan, Cost Variance |
| **AL Stock** | Project Warehouse Map |
| **AL Manufacturing** | Cutting Standard, Cutting Plan (Alu+Glass), Production Order Bridge |
| **AL Construction** | Installation Team, Site Survey, Installation Order/Progress, Handover |
| **AL Account** | Project Profitability Snapshot, Financial Config |
| **AL Quality** | Warranty Policy |
| **AL AI** | Suggestion Log, Alert Config |

## Development

```bash
cd apps/alumglass
pre-commit install
```

### Test

```bash
bench console
>>> from alumglass.run_test import main
>>> main()
# Expected: GIA_VAT ≈ 22,717,289 VND
```

## License

MIT
