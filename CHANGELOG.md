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

- Add native 2025 inputs and explicit component-efficiency priors, extended consistently across model years.
- Adopt an 8.3 kW auxiliary prior for 13 m city BEVs from 2020 onward, with triangular 6.225–10.375 kW engineering uncertainty and documented single-bus calibration limits.
- Preserve explicit battery chemistry, origin, capacity and custom input choices during initialization and sizing.
- Correct CNG efficiency accounting and exclude unavailable vehicles from bounded sizing checks; mask unavailable energy and supply outputs consistently.
- Correct annualized costs and discounted replacements; bus cost outputs remain per passenger-kilometre.
- Inherit corrected shared battery/regen physics, fuel blend accounting, hot pollutant translation and export behavior.

### Documentation and verification

- Add current installation and executable 2025 quick-start examples, migration notes and a release checklist.
- Record calibration scope, measurement boundaries and numerical consistency separately from empirical validation.
- Verify built wheels and sdist-built wheels, packaged resource hashes, installed tests with export extras and offline core-only model/LCIA smoke runs.

### Known limitations

- The auxiliary calibration is transferred from one Gillig bus; a held-out cycle is not an independent vehicle validation.
- Charging strategy, passenger load, HVAC and schedule constraints must match the intended service. Availability masks do not certify every schedule.
- Bus cost outputs already include passenger normalization; do not divide them by occupancy again.

See [validation](docs/validity.rst) and [release preparation](RELEASING.md) for scope and verification instructions.
