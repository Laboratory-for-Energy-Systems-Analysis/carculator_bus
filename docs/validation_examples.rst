Validation examples: what the comparisons show
==============================================

A completed calculation is necessary but is not enough to establish that the
vehicle represents reality. This page separates comparisons with reported energy
use, checks of the calculation, and changes caused by the background database.
See :doc:`interpretation` for units and :doc:`validity` for detailed checks.

The figures reproduce **saved audits from October 2026**. This documentation
review replotted their recorded numbers; it did not rerun every model or fit
new parameters. Sources and software revisions belong to each audit, so these
figures should not be described as measurements of the latest software release.

How to make a fair energy comparison
------------------------------------

Match the vehicle and year, the second-by-second speed and road gradient, test
mass, resistance coefficients, temperature, auxiliary loads, and fuel or battery
properties. State where energy was measured. Charging electricity includes
losses that a battery-terminal measurement excludes. If a test mass is
reconstructed from curb mass and a documented payload, label it as reconstructed
rather than weighed.

The 9 October family evidence review retained 41 paired observations from 40
runs and excluded 77 other observations with recorded reasons. **All 41 pairs
remain screening comparisons under that review's strict matching rules.** This
is not a count of independently validated vehicles, and the earlier use of two
bus cycles to fit an auxiliary load does not change that classification.
Multiple cycles or meter locations on one vehicle share evidence.

An auxiliary-load adjustment based on one electric bus
------------------------------------------------------

.. figure:: _static/validation/bus_electricity.png
   :alt: Reported and modelled charging electricity for Gillig on Manhattan, OCBC and HD-UDDS cycles

   AC energy entering the charger after the Gillig bus tests, compared with
   saved 2025 model runs. The model uses the generic motor rating and the
   transferred 8.3 kW base auxiliary assumption. Cabin HVAC was off in these
   comparisons; battery thermal loads remained enabled.
   :download:`Values <_static/validation/bus_electricity.csv>`.

The model gives 194.74, 146.22 and 134.64 kWh/100 km for Manhattan, OCBC and
HD-UDDS respectively, compared with 188.83, 140.99 and 130.05 reported. The
differences are +3.1%, +3.7% and +3.5%.

OCBC and HD-UDDS informed the auxiliary adjustment; Manhattan was held out.
It is a useful check on another cycle for the same bus, not independent evidence
from another bus model. The fit used reported motor-rating bounds, while the
plotted transfer check uses the generic rating.

The resulting **8.3 kW** is the generic base auxiliary input for 13 m battery
electric city buses from 2020 onward, across depot, opportunity and in-motion
charging. The triangular range 6.225–10.375 kW expresses engineering uncertainty;
it is not a statistical confidence interval. Applying the result from one Gillig
bus to other vehicles remains an assumption. It does not replace the separate,
outside-temperature-dependent HVAC calculation.

BYD SORT measurements have an unresolved meter location. Historical diesel and
hybrid bus measurements use older vehicles and different operating conditions.
They remain useful screening evidence but do not validate this auxiliary
assumption across the bus fleet. See :doc:`validity` for the source report,
calibration conditions and remaining gaps.

Change in life cycle climate scores
-----------------------------------

The next chart compares **two calculations**, not model outputs with measured
emissions. Both use the same 2025 vehicle inputs and national electricity-supply
settings in Switzerland. Only the bundled background inventory/index and impact
coefficients were changed. The updated bundle was rebuilt with premise and
ecoinvent 3.12 cutoff. The previous bundle is identified by Git revision
``aeace0e53937870fa05ec8aeba392e41d75aaa0b``; it should not be described as a clean
older-ecoinvent baseline because it already contained some newer coefficients.

The displayed scenario is ``SSP2-NPi``. Results are grams CO2-equivalent per
vehicle-km, using IPCC 2021 GWP100 excluding biogenic CO2 within the ``recipe``
midpoint collection. Vehicle masses and consumption were unchanged: all 138
recorded physical outputs matched exactly. The full audit covers 96 combinations
of eight vehicles, three years and four background scenarios.

.. figure:: _static/validation/climate_bus.png
   :alt: Previous and updated background climate scores for 2025 bus vehicles

   Model-to-model background comparison, not measured validation.
   :download:`Values <_static/validation/climate_bus.csv>`.

Traceable results
-----------------

Download the :download:`plotted values and source checksums
<_static/validation/plot_inputs.json>` and :download:`source manifest
<_static/validation/source_manifest.json>`. The JSON stores observation IDs and,
where recorded in the comparison table, original source URLs. Sources for the
reused diagnostic figures are listed in their linked method pages.

The shared `background-rebuild guide <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/background_rebuild.rst>`_ contains the
complete climate CSV, software revisions, rebuild report and comparison command.
The `energy evidence guide <https://github.com/Laboratory-for-Energy-Systems-Analysis/carculator_utils/blob/master/docs/energy_measurements.rst>`_ provides the original
measurement catalog, exclusions and run records. These are reproducibility
records, not new evidence of external accuracy.

To redraw the new bar charts from saved results, run from ``carculator_utils``
with Matplotlib installed::

   python scripts/plot_documentation_validation.py --output /tmp/validation-plots

The plotting script does not recalculate vehicles. Reproducing a model audit
requires the matching source revisions and inputs recorded in that audit.
