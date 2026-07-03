"""
AlumGlass Engine — Core calculation layer
Does NOT import from modules/ to avoid circular dependencies.

Key components:
- VariableResolver: Resolves all variables via Formula Variable Binding + DAG
- ProfileInterpreter: 2-pass scan+build for al_lines (Aluminum/Glass/Consumable/Accessory)
- AccessoryResolver: Builds formulas from AL Accessory Set with substitution
- CostAccumulator: Builds bucket + cost template formulas (FB Formula Set integrated)
- SnapshotBuilder: Persists ConfigSnapshot for audit trail
- BomOrchestrator: 6-step pipeline + after_calculate hooks
- RuleEngine: THRESHOLD + LOOKUP rules (CONSTANT/FORMULA/SEQUENCE → FB)
- module_registry: Event bus for v17 module hooks
"""
