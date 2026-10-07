from copy import deepcopy

import numpy as np
import pytest
from carculator_bus import BusInputParameters, BusModel

from carculator_utils.array import fill_xarray_from_input_parameters


@pytest.fixture(scope="module")
def array():
    ip = BusInputParameters()
    ip.static()
    return fill_xarray_from_input_parameters(ip, scope={})[1]


@pytest.fixture(scope="module")
def _model(array):
    model = BusModel(array, country="CH")
    model.set_all()
    return model


@pytest.fixture
def bm(_model):
    # Tests may modify model state; preserve independence without import-time work.
    return deepcopy(_model)


def test_fuel_blends(bm):
    # Shares of a fuel blend must equal 1
    for fuel in bm.fuel_blend:
        np.testing.assert_array_equal(
            np.array(bm.fuel_blend[fuel]["primary"]["share"])
            + np.array(bm.fuel_blend[fuel]["secondary"]["share"]),
            np.ones(bm.array.sizes["year"]),
        )

    # A fuel cannot be specified both as primary and secondary fuel
    for fuel in bm.fuel_blend:
        assert (
            bm.fuel_blend[fuel]["primary"]["type"]
            != bm.fuel_blend[fuel]["secondary"]["type"]
        )


def test_battery_mass(bm):
    # Battery mass must equal cell mass and BoP mass
    assert np.allclose(
        bm.array.sel(
            parameter="energy battery mass",
            powertrain="BEV-depot",
            year=2020,
            size="13m-city",
        ),
        bm.array.sel(
            parameter="battery cell mass",
            powertrain="BEV-depot",
            year=2020,
            size="13m-city",
        )
        + bm.array.sel(
            parameter="battery BoP mass",
            powertrain="BEV-depot",
            year=2020,
            size="13m-city",
        ),
    )

    # Cell mass must equal capacity divided by energy density of cells
    assert np.allclose(
        bm.array.sel(
            parameter="battery cell mass",
            powertrain="BEV-depot",
            year=2020,
            size="13m-city",
        ),
        bm.array.sel(
            parameter="electric energy stored",
            powertrain="BEV-depot",
            year=2020,
            size="13m-city",
        )
        / bm.array.sel(
            parameter="battery cell energy density",
            powertrain="BEV-depot",
            year=2020,
            size="13m-city",
        ),
    )


def test_model_results(bm):
    # Assert useful physical invariants rather than writing an unchecked workbook.
    selected = bm.array.sel(year=2020)
    for parameter in ("curb mass", "driving mass", "TtW energy"):
        values = selected.sel(parameter=parameter)
        assert np.all(np.isfinite(values)), parameter
        assert np.all(values >= 0), parameter
    assert np.all(
        selected.sel(parameter="driving mass") >= selected.sel(parameter="curb mass")
    )
