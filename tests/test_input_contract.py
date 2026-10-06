import json
from copy import deepcopy

import pytest
from carculator_bus import BusInputParameters, fill_xarray_from_input_parameters


@pytest.mark.parametrize("from_file", [False, True])
def test_custom_inputs_are_used_without_modifying_the_caller(tmp_path, from_file):
    parameters = {
        "custom": {
            "name": "custom mass",
            "amount": 42.0,
            "kind": "distribution",
            "uncertainty_type": 1,
            "sizes": ["test size"],
            "powertrain": ["test powertrain"],
            "year": 2020,
        }
    }
    extra = ["custom derived"]
    before = deepcopy(parameters)
    source = parameters
    if from_file:
        source = tmp_path / "parameters.json"
        source.write_text(json.dumps(parameters))
    ip = BusInputParameters(parameters=source, extra=extra)
    ip.static()
    _, array = fill_xarray_from_input_parameters(ip)
    assert array.sel(parameter="custom mass").item() == 42.0
    assert array.sel(parameter="custom derived").item() == 0.0
    assert parameters == before
    assert extra == ["custom derived"]


def test_bus_keeps_battery_overrides_and_input_array():
    import xarray as xr
    from carculator_bus import BusModel

    ip = BusInputParameters()
    ip.static()
    _, array = fill_xarray_from_input_parameters(
        ip, scope={"size": ["13m-city"], "powertrain": ["BEV-depot"], "year": [2020]}
    )
    before = array.copy(deep=True)
    key = ("BEV-depot", "13m-city", 2020)
    storage = {"origin": "CH", "electric": {key: "LTO"}, "capacity": {key: 100}}
    original = deepcopy(storage)
    model = BusModel(array, energy_storage=storage)
    assert model.energy_storage["origin"] == "CH"
    assert model.energy_storage["electric"][key] == "LTO"
    assert model.energy_storage["capacity"] == original["capacity"]
    assert storage == original
    xr.testing.assert_identical(array, before)
    assert model["battery cell energy density"].item() > 0
