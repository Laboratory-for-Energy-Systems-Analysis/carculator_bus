.. _validity:

Bus calibration and validation
==============================

Bus evidence must distinguish vehicle specification checks, comparison with
another model, and measured energy. The historical manufacturer, VECTO and
HBEFA comparisons in :doc:`modeling` describe the original model development;
their agreement is not a new validation of all 2025 buses.

Measured auxiliary calibration
------------------------------

The adopted 13 m city BEV auxiliary prior is **8.3 kW**, transferred from the
Gillig Altoona test report 2020-05. OCBC and HD-UDDS informed the fit; Manhattan
was held out. The documented setup has cabin HVAC off, while base auxiliaries
and battery thermal management remain enabled. This is one vehicle, and the
held-out cycle is not an independent bus.

Repeating the conditional fit over the source motor-rating bounds
(262.5–562.5 kW) gives 8.280–8.393 kW. The rounded generic prior produces the
following transfer check with the generic motor rating:

.. list-table:: AC charging electricity, kWh/100 km
   :header-rows: 1

   * - Cycle
     - Model
     - Measured
     - Role
   * - OCBC
     - 146.22
     - 140.99
     - Used in conditional fitting
   * - HD-UDDS
     - 134.64
     - 130.05
     - Used in conditional fitting
   * - Manhattan
     - 194.74
     - 188.83
     - Held-out cycle

The generic-rating rerun differs from the conditional fit. Do not describe
its training-cycle agreement as independent validation. The prior applies to
``13m-city`` with ``BEV-depot``, ``BEV-opp`` and ``BEV-motion`` from 2020 onward;
other sizes and combustion buses retain their auxiliary assumptions. The
triangular 6.225–10.375 kW bounds are engineering uncertainty, not an empirical
confidence interval. A shared ``uncertainty_group`` gives the same draw across
modern years and charging strategies.

The family measurement snapshot has 16 paired observations for five buses.
BYD SORT tests specify auxiliaries off and have an unresolved electrical meter
boundary. They are screening comparisons and cannot validate the Gillig
auxiliary transfer. Historical diesel/hybrid tests likewise do not justify
fitting a generic 2025 vehicle. Manufacturer mass, power or battery-capacity
agreement alone does not establish correct consumption.

See the `measured bus comparisons <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/energy_measurements.rst>`_ and
`calibration assumptions and history <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/energy_model_repairs.rst>`_. The
`Gillig source report entry <https://www.altoonabustest.psu.edu/bus-details.aspx?BN=2020-05>`_
and exact settings are recorded in the shared measurement catalog.

Known limits
------------

HVAC depends on the supported ambient/indoor-temperature inputs. Base auxiliary
power is not a substitute for heating or cooling demand. Passenger load, stop
patterns, charging strategy and road load must be matched separately. The
six standard bus speed/grade traces and durations were restored from source
VECTO outputs; bundled grade is rise/run and numeric gradient overrides are
degrees. Matching those simulator traces does not independently validate fuel
or electricity use. Availability masks and charging constraints
must be checked before interpreting a zero energy output.

Energy boundaries and time trends
---------------------------------

``TtW energy`` is kJ/km. For a BEV it represents net stored-energy depletion;
``model.battery_terminal_energy`` reports net terminal DC energy separately.
``electricity consumption`` is charging electricity in kWh/km. Multiplying it
by 100 gives kWh/100 km. A meter boundary must be identified before comparing
these outputs. Regeneration and battery/charger losses must not be counted twice.

The 2025 motor/inverter (0.90), electric transmission (0.97), charger (0.90)
and symmetric battery one-way (sqrt(0.97)) values are component priors in their
documented scopes, not universally measured efficiencies. For relevant hybrid
scopes, the independent motor peak/system-power ratio is 0.65. The temporal
update preserves all 2025 scalar values and uncertainty distributions. Storage
and charger trends preserve relative legacy losses; newly explicit component
priors are extended across native years to avoid interpolating from missing
zero values. Historical estimates and future projections therefore change.

The family audit completes 546 annual cases (21 configurations, 2015–2040),
including availability-masked historical cells. The former inputs caused 20
sizing failures in this grid. All 40 existing 2025 measurement-comparison runs
retain their energy use and driving mass exactly. These are consistency and
regression checks, not 546 empirical validations. See
`temporal method, plots and limitations <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/temporal_energy.rst>`_.

Reproducibility
---------------

The installed package includes :download:`2025 record provenance
<../carculator_bus/data/defaults_2025_provenance.json>` and
:download:`temporal provenance and original affected records
<../carculator_bus/data/temporal_energy_provenance.json>`. Overrides should use measured
vehicle-specific inputs where available. Retain source, year, cycle, driving
mass, meter boundary and uncertainty assumptions with each comparison.

With matching Python 3.12 sibling checkouts, run from ``carculator_utils``::

   python scripts/validate_energy_measurements.py --output /tmp/measurements-new
   python scripts/audit_energy_time_trends.py --output /tmp/temporal-new

The shared `measurement catalog and outputs <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/energy_measurements.rst>`_
record excluded observations as well as paired values. Multiple cycles of one
vehicle and AC/DC measurements from one run are not independent vehicles.
The family artifact verification on 2026-10-08 passed 497 tests, with one
existing expected two-wheeler failure, plus offline wheel/source-distribution
model and LCIA checks. See :doc:`release` for the release verification record.
That software verification does not replace empirical validation.
