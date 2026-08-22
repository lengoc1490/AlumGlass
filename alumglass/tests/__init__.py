"""AlumGlass ERP — Test Suite.

Cấu trúc test (bench run-tests --app alumglass):
- test_bom_orchestrator.py: Integration tests cho BomOrchestrator (CDMQ-2C, CDMQ-4C)
- test_composite_pricing.py: Composite Key Pricing validation
- test_calc_pattern_hybrid.py: lookup_calc_pattern HYBRID (DB-first + fallback)
- test_safe_eval_a3.py / test_cost_template_validate.py / test_pricing_dimension_snapshot.py
- test_async_bom_calculation.py: async threshold/enqueue/worker

Standalone tests (KHÔNG dùng FrappeTestCase, cần site) nằm ở repo root
`standalone_tests/` — NGOÀI package alumglass/ để `bench run-tests` không collect
(ví dụ `test_phase_b_fbmax.py` — FakeFrappe stub). Chạy:
    python3 -m pytest standalone_tests/test_phase_b_fbmax.py
"""
