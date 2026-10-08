# Changelog

Notable user-facing changes to `carculator_bus`. The entry below is prepared for release;
it has not yet been published. Older entries, where present, retain their original record.

## [0.1.1] - Unreleased

### Compatibility and installation

- Require Python 3.12 (`>=3.12,<3.13`); older Python environments must be recreated.
- Use NumPy `>=1.26.4,<2` through the shared runtime.
- Require the stable `carculator_utils>=1.3.6` release, including its export extras.
- Build wheels and source distributions from centralized `pyproject.toml` metadata.
- Keep core model/LCIA use independent of Brightway; install `excel` or `brightway` extras for export. The Brightway extra targets the legacy stack (`bw2io<0.9`, `bw2data<4`, `bw2calc<2`).
- Align documentation versions with the package version and provide complete documentation-build dependencies.

### Model and inventory changes

- Gas buses now emit the methane represented by their additional fuel-purchase allowance; previously the lost gas was absent from direct emissions. Use the shared mass balance, include both origins in impacts/exports, and document the historical loss-rate boundary; see [validation](docs/validity.rst#additional-methane-leakage).
- Make projected costs reproducible with `stochastic(n, seed=...)`, retaining factors across sample/year selections and serialization without using NumPy's global RNG. Keep deterministic static/sensitivity factors and explicit battery prices. `stochastic(1)` now also samples cost factors; regenerate old stochastic cost results.
- Display the available sample in the bus summary when sample `0` is absent, allowing selected stochastic samples to complete.
- Correct year/sample alignment in automatic component-cost projections. Multi-year sensitivity references now match static prices and costs; sampled factors remain attached to their samples across years. Preserve existing price curves, explicit battery prices and physical/inventory outputs.
- Preserve explicit generic and selected-chemistry battery prices through cost adjustment, including scoped zero and per-sample constructor inputs. Verify completed purchase and replacement costs and unchanged default pricing; see [usage](docs/usage.rst#battery-unit-costs).
- Add native 2025 inputs and explicit component-efficiency priors, extended consistently across model years.
- Adopt an 8.3 kW auxiliary prior for 13 m city BEVs from 2020 onward, with triangular 6.225–10.375 kW engineering uncertainty and documented single-bus calibration limits.
- Preserve explicit battery chemistry, origin, capacity and custom input choices during initialization and sizing.
- Correct CNG efficiency accounting and exclude unavailable vehicles from bounded sizing checks; mask unavailable energy and supply outputs consistently.
- Correct annualized costs and discounted replacements; bus cost outputs remain per passenger-kilometre.
- Inherit corrected shared battery/regen physics, fuel blend accounting, hot pollutant translation and export behavior.

### Documentation and verification

- Clarify the retained minimum of one replacement energy battery for charger-equipped buses, separate from cycling demand. Document initial-plus-replacement inventory accounting, fractional allocation, the three-replacement cap and cost treatment; bus calculations are unchanged.

- Add current installation and executable 2025 quick-start examples, migration notes and a release checklist.
- Record calibration scope, measurement boundaries and numerical consistency separately from empirical validation.
- Verify built wheels and sdist-built wheels, packaged resource hashes, installed tests with export extras and offline core-only model/LCIA smoke runs.

### Known limitations

- The auxiliary calibration is transferred from one Gillig bus; a held-out cycle is not an independent vehicle validation.
- Charging strategy, passenger load, HVAC and schedule constraints must match the intended service. Availability masks do not certify every schedule.
- Bus cost outputs already include passenger normalization; do not divide them by occupancy again.

See [validation](docs/validity.rst) and [release preparation](RELEASING.md) for scope and verification instructions.
