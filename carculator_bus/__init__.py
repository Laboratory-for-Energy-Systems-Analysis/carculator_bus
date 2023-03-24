"""

Submodules
==========

.. autosummary::
    :toctree: _autosummary


"""

_all_ = (
    "BusInputParameters",
    "fill_xarray_from_input_parameters",
    "BusModel",
    "InventoryBus",
)

# library version
__version__ = (0, 0, 8)

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

from carculator_utils.array import fill_xarray_from_input_parameters

from .bus_input_parameters import BusInputParameters
from .inventory import InventoryBus
from .model import BusModel
