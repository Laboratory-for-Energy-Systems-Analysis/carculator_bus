"""

Submodules
==========

.. autosummary::
    :toctree: _autosummary


"""

__all__ = (
    "BusInputParameters",
    "fill_xarray_from_input_parameters",
    "BusModel",
    "InventoryBus",
    "get_driving_cycle",
    "get_road_gradient",
)

from pathlib import Path

# library version
from ._version import __version__

DATA_DIR = Path(__file__).resolve().parent / "data"

from carculator_utils.array import fill_xarray_from_input_parameters

from .bus_input_parameters import BusInputParameters
from .driving_cycles import get_driving_cycle, get_road_gradient
from .inventory import InventoryBus
from .model import BusModel
