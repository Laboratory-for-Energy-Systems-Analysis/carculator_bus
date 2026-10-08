Release notes
=============

0.1.1
-----

When upgrading from an earlier version:

* Create a Python 3.12 environment and install the updated package as described
  in :doc:`installation`. This version requires ``carculator_utils>=1.3.6``.
* Recalculate saved scenarios: changes to energy accounting, battery sizing,
  costs and emissions can affect results.
* Select a supported background scenario: ``SSP2-NPi``,
  ``SSP2-PkBudg1000``, ``SSP2-PkBudg650`` or ``static``. Older ``1150`` and
  ``500`` pathway labels are no longer accepted.

The :download:`changelog <../CHANGELOG.md>` lists the changes in each version.
See :doc:`validity` for calibration evidence and the scope of model validation.

Bus battery replacement behavior is unchanged: charger-equipped buses retain
at least one replacement over service life, in addition to their initial pack.
See :ref:`bus-battery-replacement-policy` for this explicit fleet-life assumption.
