"""Selecting model years must not change a bus's propulsion assumptions."""

from copy import deepcopy

import numpy as np
import pytest
import xarray as xr
from carculator_utils.array import fill_xarray_from_input_parameters

from carculator_bus import BusInputParameters, BusModel, InventoryBus

POWERTRAINS = ["ICEV-d", "ICEV-g", "HEV-d", "BEV-depot"]
PHYSICAL_PARAMETERS = [
    "combustion power share",
    "combustion power",
    "electric power",
    "TtW energy",
    "fuel consumption",
    "electricity consumption",
    "curb mass",
    "driving mass",
    "energy battery mass",
]
# Match the existing per-cell driving-mass convergence tolerance.
SIZING_RTOL = 0.001


def run_model(array, **kwargs):
    original = array.copy(deep=True)
    model = BusModel(array, country="CH", **kwargs)
    model.set_all()
    xr.testing.assert_identical(array, original)
    np.testing.assert_array_equal(
        model["combustion power share"],
        array.sel(parameter="combustion power share"),
    )
    np.testing.assert_array_equal(
        model["is_compliant"], model["driving mass"] <= model["gross mass"] + 1e-6
    )
    return model


@pytest.fixture(scope="module", params=["13m-city", "13m-coach"])
def reference(request):
    inputs = BusInputParameters()
    inputs.static()
    _, array = fill_xarray_from_input_parameters(
        inputs,
        scope={
            "size": [request.param],
            "powertrain": POWERTRAINS,
            "year": [2020, 2025, 2030],
        },
    )
    array = array.isel(value=[0, 0]).assign_coords(value=[9, 2])
    array.loc[dict(parameter="average passengers", value=2)] *= 1.1
    model = run_model(array.sel(year=[2025]))
    inventory = InventoryBus(model, scenario="static", functional_unit="vkm")
    impacts = inventory.calculate_impacts()
    assert np.isfinite(impacts).all()
    return array, model, inventory, impacts


def assert_same_2025_physics(model, reference):
    np.testing.assert_allclose(
        model.array.sel(year=[2025], parameter=PHYSICAL_PARAMETERS),
        reference.array.sel(year=[2025], parameter=PHYSICAL_PARAMETERS),
        rtol=SIZING_RTOL,
        atol=1e-9,
    )
    np.testing.assert_array_equal(
        model["electric power"].sel(powertrain=["ICEV-d", "ICEV-g"]), 0
    )


@pytest.mark.parametrize("years", [[2020, 2025], [2025, 2030], [2030, 2020, 2025]])
def test_completed_runs_preserve_physics_fuel_and_emissions_across_year_scopes(
    reference, years
):
    array, single_model, single_inventory, single_impacts = reference
    model = run_model(array.sel(year=years))
    assert_same_2025_physics(model, single_model)
    inventory = InventoryBus(model, scenario="static", functional_unit="vkm")
    impacts = inventory.calculate_impacts()
    assert np.isfinite(impacts).all()
    np.testing.assert_allclose(
        impacts.sel(year=[2025]), single_impacts, rtol=SIZING_RTOL, atol=1e-12
    )

    yi = list(inventory.scope["year"]).index(2025)
    for powertrain in POWERTRAINS:
        search = (f"transport, bus, {powertrain},",)
        (column,) = inventory.find_input_indices(search)
        (single_column,) = single_inventory.find_input_indices(search)
        fuel = "methane" if powertrain == "ICEV-g" else "diesel"
        supply = (
            "electricity supply for electric vehicles"
            if powertrain == "BEV-depot"
            else f"fuel supply for {fuel} vehicles"
        )
        (row,) = inventory.get_vehicle_supply_indices(supply, [column])
        (single_row,) = single_inventory.get_vehicle_supply_indices(
            supply, [single_column]
        )
        np.testing.assert_allclose(
            inventory.A[:, row, column, yi],
            single_inventory.A[:, single_row, single_column, 0],
            rtol=SIZING_RTOL,
            atol=1e-12,
        )
        for name in (
            "Carbon dioxide, fossil",
            "Carbon dioxide, non-fossil",
            "Sulfur dioxide",
            "Methane, fossil",
            "Methane, non-fossil",
        ):
            flow = (name, ("air",), "kilogram")
            np.testing.assert_allclose(
                inventory.A[:, inventory.inputs[flow], column, yi],
                single_inventory.A[:, single_inventory.inputs[flow], single_column, 0],
                rtol=SIZING_RTOL,
                atol=1e-12,
            )


def test_legacy_energy_targets_cannot_reenable_adjustment(reference):
    array, single_model, _, _ = reference
    targets = {2025: 0.7, 2030: 0.5}
    original = deepcopy(targets)
    model = run_model(array.sel(year=[2025, 2030]), energy_target=targets)
    assert targets == original
    assert_same_2025_physics(model, single_model)


def test_explicit_input_power_split_is_preserved(reference):
    array, _, _, _ = reference
    array = array.copy(deep=True)
    array.loc[dict(parameter="combustion power share", powertrain="ICEV-d")] = (
        xr.DataArray(
            [[0.95, 0.85, 0.9], [0.8, 1, 0.9]],
            dims=("value", "year"),
            coords={"value": [9, 2], "year": [2020, 2025, 2030]},
        )
    )
    model = run_model(array.sel(year=[2030, 2020, 2025]))
    selected = model.array.sel(powertrain="ICEV-d")
    np.testing.assert_allclose(
        selected.sel(parameter="combustion power"),
        selected.sel(parameter="power")
        * selected.sel(parameter="combustion power share"),
        rtol=2e-6,
    )
