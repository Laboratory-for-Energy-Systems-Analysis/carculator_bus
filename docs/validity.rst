.. _validity:

Bus calibration and validation
==============================

Bus evidence must distinguish vehicle specification checks, comparison with
another model, and measured energy. The historical manufacturer, VECTO and
HBEFA comparisons in :doc:`modeling` describe the original model development;
their agreement is not a new validation of all 2025 buses.

.. _bus-year-selection:

.. _charging-cost-accounting:

Charging cost accounting
------------------------

Electricity running costs use grid purchases: ``electricity consumption`` in
kWh/km times the electricity tariff. Grid consumption already includes both
battery-charge and charger losses; neither efficiency is applied again when
billing that electricity. Previously the cost formula omitted charger losses.
At 90% charger efficiency it understated the electricity component by 10%; at
80% efficiency it understated it by 20%. This correction changes costs, while
preserving vehicle energy demand, inventory electricity exchanges and LCIA.

BEVs use this grid-based calculation. Other powertrains retain their existing
fuel-cost convention. Tariffs and charging-efficiency assumptions have not
been refitted.

Bus costs remain per passenger-km, using each vehicle/year/sample's passenger
count. For comparison on a vehicle-km basis, the default Swiss 2025
``13m-city`` depot BEV costs approximately EUR 27.59/100 vehicle-km for
electricity, corrected from EUR 24.83. Depot, opportunity and in-motion electric
strategies share the same billing boundary.

Completed model/inventory checks and the shared billing contract are described
in the `shared charging-cost validation <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/validity.rst#charging-cost-accounting>`_.


Propulsion inputs and year selection
------------------------------------

Bus propulsion follows the supplied annual vehicle parameters. The legacy
``adjust_combustion_power_share`` routine has been removed completely. It
previously ran only for multi-year selections and reduced the combustion share
of nominal diesel and gas buses to meet energy-reduction targets, adding
electric propulsion. Its 2020 reference could also be extrapolated from the
selected future years. Consequently, selecting other years changed the same
2025 vehicle's powertrain, fuel demand, emissions and inventory results.

There is no opt-in version of this adjustment. The shared constructor's legacy
``energy_target`` argument remains accepted for call compatibility but has no
effect on bus calculations; remove it from bus scripts. Set propulsion
assumptions through the annual vehicle inputs. The ``is_compliant`` output
continues to indicate actual driving-mass compliance with gross mass, not
compliance with energy-reduction or CO2 targets. The obsolete energy-target
asterisk in the passenger table has also been removed.

For the default Swiss 2025 ``13m-city`` diesel bus on the bundled bus cycle,
the previous model reported approximately 38.49 L/100 km when run alone,
33.16 L/100 km with 2020, and 28.74 L/100 km with 2030. The corrected runs
retain the input combustion share of 100% and approximately 38.49 L/100 km
across those selections. This is a consistency repair, not a new calibration.
Recalculate multi-year studies that relied on the former automatic adjustment.

``tests/test_energy_year_scope.py`` completes model and LCIA runs for
``13m-city`` and ``13m-coach`` buses, using diesel, gas, non-plug-in diesel
hybrid and depot BEV powertrains and two passenger-load samples. It compares
2025 alone with selections including 2020, 2030 and reordered years, checking
propulsion shares, engine/motor ratings, energy, mass, fuel/electricity inputs,
direct emissions and characterized results. Physical and inventory comparisons
use the existing 0.1% driving-mass sizing tolerance; propulsion shares must
retain their input values exactly. Explicit input power splits are preserved,
and passing legacy energy targets cannot reactivate the removed routine.

Run the focused checks with the matching shared runtime::

   python -m pytest tests/test_energy_year_scope.py

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

.. _bus-temperature-inputs:

Temperature inputs and country fallback
---------------------------------------

``ambient_temperature`` accepts a Celsius scalar for all months or twelve
values in January--December order. The cabin assumption is fixed at 20 degrees
Celsius: ``indoor_temperature`` accepts the scalar ``20`` or twelve monthly
values all equal to ``20``. Other cabin settings now raise ``ValueError`` before
sizing because the empirical HVAC curve does not model thermostat sensitivity.
HVAC demand still varies with outside temperature. For example, the following
imposes an illustrative constant outside temperature of 25 degrees Celsius:

.. code-block:: python

    model = BusModel(array, country="BR", ambient_temperature=25.0)
    model.set_all()

Supply a twelve-element sequence instead of ``25.0`` for a local monthly
profile. Ambient-temperature overrides take precedence over the country lookup and
leave the supplied array or sequence unchanged.

Without an override, the shared runtime uses the first matching country row
in its bundled ``monthly_avg_temp.csv``. If no row exists, it prints a notice
and uses Switzerland's monthly series. The current table lacks Brazil, the US,
Canada, India and Australia, among other countries. This fallback is a modelling
assumption whose suitability depends on the study location.

The shared fallback now retains decimal temperatures, fixing a crash on the
Swiss value ``1.9``. Completed checks in all five countries cover 13m-city
diesel, fuel-cell and depot BEV buses in 2025/2030 with two load samples.
They compare default-fallback runs against explicitly supplied Swiss
temperatures through sizing, fuel/charging exchanges and LCIA. These are
software consistency checks; neither the temperature dataset nor the HVAC
calibration is changed. See the
`shared regression <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/tests/test_temperature_fallback.py>`_.

Cabin-temperature limitation
----------------------------

Earlier versions accepted different cabin settings but only used them to choose
between heating and cooling; the ambient-dependent load magnitude stayed the
same. A completed 2025 13m-city depot-BEV at 0 degrees Celsius outside consumed
121.25 kWh/100 km charging electricity at cabin settings of 15, 20 and 25 degrees.
Those results cannot establish the energy effect of a thermostat change.

The new validation makes that limitation explicit while preserving default
20-degree results. Ambient profiles, HVAC power, heat-pump coefficients and
battery thermal-management assumptions retain their existing roles. This is
an input-contract correction, with no new heat-balance model or calibration.
Completed multi-year diesel, fuel-cell and depot-BEV checks preserve sizing,
inventories and LCIA for the supported setting; see the
`shared cabin-temperature regression <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/tests/test_cabin_temperature.py>`_.

Battery replacement assumption
------------------------------

Charger-equipped buses retain a deliberate minimum of **one replacement
battery over service life**, even when the cycling estimate implies none.
The initial pack is additional, so battery supply and disposal include at
least two packs. This fleet-life assumption is not established by the energy
calibration above or by a fitted calendar-ageing model. The throughput-based
factor remains fractional and capped at three replacements. See
:ref:`the calculation, scope and cost treatment <bus-battery-replacement-policy>`.
The removal of forced replacements in ``carculator_two_wheeler`` does not
change this bus policy or any bus results.

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

Additional methane leakage
---------------------------

Gas buses now emit the methane represented by their additional fuel-purchase allowance; previously the lost gas was absent from direct emissions.
The shared calculation preserves the existing convention: loss in kg per km
is engine fuel times the ``CNG pump-to-tank leakage`` ratio, and purchased fuel
is engine fuel plus that loss. Fossil/non-fossil methane follows the blend.
Both generic-air methane flows now enter non-exhaust impacts and exports;
combustion CO2 and HBEFA exhaust emissions are unchanged.

The historical 0.4% default is retained as an additional-loss assumption.
Its source combines several station/delivery/vehicle stages and includes LNG
boil-off; it does not establish a residual CNG loss after every supplier.
Existing supplier losses are retained, so possible overlap is not eliminated
by this accounting repair. Specify only loss additional to the selected
supplier; set the parameter to zero if that supplier covers all relevant losses.
See the shared `methane leakage boundary and verification notes
<https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/methane_leakage.rst>`_.

Completed regressions include 13m-city buses, diesel/BEV controls,
2020/2025/2030, two samples, fossil gas, sewage biomethane, biological synthetic
methane and mixed fuels. They check mass balance, unchanged upstream inventories,
ReCiPe/EF climate contributions, and repeated multi-year Brightway exports.
These establish accounting consistency, not measured leakage-rate validation.
