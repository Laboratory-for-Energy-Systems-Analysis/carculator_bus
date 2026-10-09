import warnings
from itertools import product

import numexpr as ne
import numpy as np
import xarray as xr
import yaml
from carculator_utils.background_systems import BackgroundSystemModel
from carculator_utils.energy_consumption import (
    EnergyConsumptionModel,
    get_default_driving_cycle_name,
)
from carculator_utils.model import VehicleModel
from carculator_utils.numerical import capital_recovery_factor
from prettytable import PrettyTable

from . import DATA_DIR

warnings.simplefilter(action="ignore", category=FutureWarning)


class BusModel(VehicleModel):
    """Model buses using their supplied annual propulsion parameters.

    The inherited ``energy_target`` constructor argument is retained for call
    compatibility but has no effect. Automatic target-driven hybridization
    has been removed.
    """

    def set_battery_chemistry(self):
        # override default values for batteries
        # if provided by the user
        electric = self.energy_storage.setdefault("electric", {})
        for powertrain, size, year in product(
            ["BEV-depot", "FCEV", "BEV-opp", "BEV-motion"],
            self.array.coords["size"].values,
            self.array.year.values,
        ):
            chemistry = "LTO" if powertrain in ("BEV-opp", "BEV-motion") else "NMC-622"
            electric.setdefault((powertrain, size, year), chemistry)
        self.energy_storage.setdefault("origin", "CN")

    def set_all(self):
        """
        Size buses and calculate energy use, costs and emissions.

        Mass, power and energy storage are coupled. Bounded sizing iterations
        converge on driving mass per active vehicle/sample at a relative
        tolerance of 0.1%. Propulsion shares retain their annual input values;
        no energy-target adjustment is applied.

        :returns: Does not return anything. Modifies ``self.array`` in place.
        """

        # Actual driving-mass compliance is evaluated after sizing.
        self["is_compliant"] = True
        # whether the technology is available for the given year
        self["is_available"] = True

        if self.cycle is None:
            self.cycle = get_default_driving_cycle_name("bus")

        self.ecm = EnergyConsumptionModel(
            vehicle_type="bus",
            vehicle_size=list(self.array.coords["size"].values),
            cycle=self.cycle,
            gradient=self.gradient,
            country=self.country,
            powertrains=list(self.array.coords["powertrain"].values),
            ambient_temperature=self.ambient_temperature,
            indoor_temperature=self.indoor_temperature,
        )
        self.set_trips_properties()

        print("Finding solutions for buses...")

        for _ in self.iterate_sizing(
            "driving mass", rtol=0.001, mask=self.get_availability_mask()
        ):
            # driving mass from the previous iteration

            if self.target_mass:
                self.override_vehicle_mass()
            else:
                self.set_vehicle_masses()

            # size the engines and motors
            self.set_power_parameters()
            self.set_fuel_cell_power()
            self.set_fuel_cell_mass()
            # sizes different vehicle components
            self.set_component_masses()
            self.set_recuperation()

            self.calculate_ttw_energy()
            self.set_ttw_efficiency()

            self.set_share_recuperated_energy()
            self.set_battery_fuel_cell_replacements()

            self.set_energy_stored_properties()
            self.set_power_battery_properties()
            self.set_vehicle_masses()

        self["capacity utilization"] = np.clip(
            (self["average passengers"] / self["initial passengers capacity"]), 0, 1
        )

        self.adjust_cost()
        self.set_electricity_consumption()
        self.set_costs()
        # defines hot pollutant emissions
        # along the driving cycle
        self.set_hot_emissions()
        # defines abrasion emissions
        self.set_particulates_emission()
        # defines noise emissions
        self.set_noise_emissions()
        self.remove_energy_consumption_from_unavailable_vehicles()
        # self.check_compliance_of_buses()

        print("")
        print("Number of passengers on board")
        print(
            "'X' BEV with driving mass when fully "
            "occupied superior to the permissible gross weight."
        )
        print("'/' vehicles not available for the specified year or charging strategy.")
        print(
            "'O' electric vehicles that do not have "
            "enough time to charge batteries overnight."
        )

        # Display the reference, or the first available sample after selection.
        display_value = (
            "reference"
            if "reference" in self.array.coords["value"]
            else self.array.coords["value"].values[0]
        )
        # Display of table with passengers onboard
        t = PrettyTable([""] + self.array.coords["size"].values.tolist())

        for pt in self.array.coords["powertrain"].values:
            for y in self.array.coords["year"].values:
                row = [f"{pt}, {y}"]
                vals = []

                for s in self.array.coords["size"].values:
                    # fetch number of passengers onboard
                    val = np.round(
                        self.array.sel(
                            parameter=["average passengers"],
                            powertrain=pt,
                            year=y,
                            value=display_value,
                            size=s,
                        ).values,
                        1,
                    )

                    # indicate vehicles that have schedule issues
                    val = np.where(
                        self.array.sel(
                            parameter="has_schedule_issue",
                            powertrain=pt,
                            year=y,
                            value=display_value,
                            size=s,
                        ).values,
                        "O",
                        val,
                    )

                    # indicate vehicles that are too heavy
                    val = np.where(
                        self.array.sel(
                            parameter="is_too_heavy",
                            powertrain=pt,
                            year=y,
                            value=display_value,
                            size=s,
                        ).values,
                        "X",
                        val,
                    )

                    # indicate vehicles that are not commercially available
                    val = np.where(
                        self.array.sel(
                            parameter="is_available",
                            powertrain=pt,
                            year=y,
                            value=display_value,
                            size=s,
                        ).values,
                        val,
                        "/",
                    )
                    vals.append(val[0])

                t.add_row(row + vals)
        print(t)

    def check_compliance_of_buses(self):
        # Indicate vehicles not available before 2020
        # Essentially all BEVs and FCEVs
        l_pwt = [
            p
            for p in self.array.powertrain.values
            if p in ["BEV-opp", "BEV-depot", "FCEV", "HEV-d"]
        ]

        if len(l_pwt) > 0:
            self.array.loc[
                dict(
                    powertrain=l_pwt,
                    parameter="is_available",
                    year=[y for y in self.array.year.values if y < 2020],
                )
            ] = 0

        # Indicates in motion-type and opportunity-type vehicles
        # not available for inter-city purpose
        l_size = [
            s
            for s in self.array.coords["size"].values
            if s in ["13m-coach", "13m-coach-double"]
            and any(
                p
                for p in self.array.powertrain.values
                if p in ["BEV-opp", "BEV-motion", "BEV-depot"]
            )
        ]

        if len(l_size) > 0:
            self.array.loc[
                dict(
                    powertrain=[
                        p
                        for p in self.array.powertrain.values
                        if p in ["BEV-opp", "BEV-motion", "BEV-depot"]
                    ],
                    parameter="is_available",
                    size=l_size,
                )
            ] = 0

        # Indicate that in-motion bus are only available for 13m and 18m sizes
        l_size = [
            s
            for s in self.array.coords["size"].values
            if s in ["9m", "13m-city-double"]
            and "BEV-motion" in self.array.powertrain.values
        ]

        if len(l_size) > 0:
            self.array.loc[
                dict(
                    powertrain="BEV-motion",
                    parameter="is_available",
                    size=l_size,
                )
            ] = 0

    def adjust_cost(self):
        """
        This method adjusts costs of energy storage over time, to correct for the overly optimistic linear
        interpolation between years.
        """

        cost_factor, cost_factor_fcev = self._get_cost_factors()
        years = self.array.year

        # Correction of hydrogen tank cost, per kg
        if "FCEV" in self.array.powertrain.values:
            self.array.loc[:, ["FCEV"], "fuel tank cost per kg", :, :] = (
                1.078e58 * np.exp(-6.32e-2 * years) + 3.43e2
            ) * cost_factor_fcev

            # Correction of fuel cell stack cost, per kW
            self.array.loc[:, ["FCEV"], "fuel cell cost per kW", :, :] = (
                3.15e66 * np.exp(-7.35e-2 * years) + 2.39e1
            ) * cost_factor_fcev

        # Correction of energy battery system cost, per kWh
        l_pwt = [
            p
            for p in self.array.powertrain.values
            if p in ["BEV-opp", "BEV-depot", "BEV-motion"]
        ]

        if len(l_pwt) > 0:
            self.array.loc[
                :,
                l_pwt,
                "energy battery cost per kWh",
                :,
                :,
            ] = (2.75e86 * np.exp(-9.61e-2 * years) + 5.059e1) * cost_factor

        # Correction of power battery system cost, per kW
        l_pwt = [
            p
            for p in self.array.powertrain.values
            if p in ["ICEV-d", "ICEV-g", "FCEV", "HEV-d"]
        ]

        if len(l_pwt) > 0:
            self.array.loc[
                :,
                l_pwt,
                "power battery cost per kW",
                :,
                :,
            ] = (8.337e40 * np.exp(-4.49e-2 * years) + 11.17) * cost_factor

        # Correction of combustion powertrain cost for ICEV-g
        if "ICEV-g" in self.array.powertrain.values:
            self.array.loc[
                :,
                ["ICEV-g"],
                "combustion powertrain cost per kW",
                :,
                :,
            ] = (5.92e160 * np.exp(-0.1819 * years) + 26.76) * cost_factor

        self.apply_battery_cost_inputs(projected=True)

    def calculate_ttw_energy(self):
        """
        This method calculates the energy required to operate auxiliary services as well
        as to move the car. The sum is stored under the parameter label "TtW energy" in :attr:`self.array`.
        """
        self.energy = self.ecm.motive_energy_per_km(
            engine_efficiency=self.get_energy_efficiency_override("engine efficiency"),
            engine_efficiency_factor=xr.where(
                self.array.powertrain == "ICEV-g",
                1 - self["CNG engine efficiency correction factor"],
                1.0,
            ).transpose("size", "powertrain", "year", "value"),
            transmission_efficiency=self.get_energy_efficiency_override(
                "transmission efficiency"
            ),
            driving_mass=self["driving mass"],
            rr_coef=self["rolling resistance coefficient"],
            drag_coef=self["aerodynamic drag coefficient"],
            frontal_area=self["frontal area"],
            electric_motor_power=self["electric power"],
            engine_power=self["power"],
            combustion_engine_power=self["combustion power"],
            recuperation_efficiency=self["recuperation efficiency"],
            electric_motor_efficiency=self.get_electric_motor_efficiency(),
            aux_power=self["auxiliary power base demand"],
            battery_charge_eff=self["battery charge efficiency"],
            battery_discharge_eff=self["battery discharge efficiency"],
            fuel_cell_system_efficiency=self["fuel cell system efficiency"],
            hvac_power=self["HVAC power"],
            battery_cooling_unit=self["battery cooling unit"],
            battery_heating_unit=self["battery heating unit"],
            cooling_consumption=self["cooling energy consumption"],
            heating_consumption=self["heating energy consumption"],
            heat_pump_cop_cooling=self["heat pump CoP, cooling"],
            heat_pump_cop_heating=self["heat pump CoP, heating"],
        )

        self.energy = self.energy.assign_coords(
            {
                "powertrain": self.array.powertrain,
                "year": self.array.year,
                "size": self.array.coords["size"],
                "value": self.array.coords["value"],
            }
        )

        if self.energy_consumption:
            self.override_ttw_energy()

        distance = self.energy.sel(parameter="velocity").sum(dim="second") / 1000

        self["transmission efficiency"] = (
            np.ma.array(
                self.energy.loc[dict(parameter="transmission efficiency")],
                mask=self.energy.loc[dict(parameter="power load")] == 0.0,
            )
            .mean(axis=0)
            .T
        )

        self["engine efficiency"] = (
            np.ma.array(
                self.energy.loc[dict(parameter="engine efficiency")],
                mask=self.energy.loc[dict(parameter="power load")] == 0.0,
            )
            .mean(axis=0)
            .T
        )

        self["TtW energy"] = (
            self.energy.sel(
                parameter=[
                    "motive energy",
                    "auxiliary energy",
                    "cooling energy",
                    "heating energy",
                    "battery cooling energy",
                    "battery heating energy",
                ]
            ).sum(dim=["second", "parameter"])
            / distance
        ).T

        self["TtW energy"] += self.get_regeneration_credit()
        self.set_battery_energy_balance()

        self["TtW energy, combustion mode"] = self["TtW energy"] * (
            self["combustion power share"] > 0
        )
        self["TtW energy, electric mode"] = self["TtW energy"] * (
            self["combustion power share"] == 0
        )

        self["auxiliary energy"] = (
            self.energy.sel(
                parameter=[
                    "auxiliary energy",
                    "cooling energy",
                    "heating energy",
                    "battery cooling energy",
                    "battery heating energy",
                ]
            )
            .sum(dim=["parameter", "second"])
            .values
            / distance.values
        ).T

    def set_battery_fuel_cell_replacements(self):
        """Apply the bus battery and fuel-cell replacement assumptions.

        Charger-equipped buses carry at least one replacement energy battery
        over their service life, even when cycling demand alone implies none.
        This deliberate fleet-life assumption is retained independently of the
        two-wheeler policy; it is not a calibrated calendar-ageing model.
        The throughput-based battery factor is clipped to [1, 3] and may be
        fractional. Inventory supply and disposal include 1 + that factor,
        accounting for the initial pack as well. Costs include replacement packs.
        Fuel-cell replacements use their separate lifetime-hours calculation
        and are rounded up.
        """
        _ = lambda array: np.where(array == 0, 1, array)

        self["battery lifetime replacements"] = np.clip(
            (
                (self["lifetime kilometers"] * self["TtW energy"] / 3600)
                / _(self["electric energy stored"])
                / _(self["battery cycle life"])
                - 1
            ),
            1,
            3,
        ) * (self["charger mass"] > 0)

        # The number of fuel cell replacements is based on the
        # average distance driven with a set of fuel cells given
        # their lifetime expressed in hours of use.
        # The number of replacement is rounded *up* as we assume
        # no allocation of burden with a second life

        average_speed = (
            np.nanmean(
                np.where(
                    self.energy.sel(parameter="velocity") > 0,
                    self.energy.sel(parameter="velocity"),
                    np.nan,
                ),
                0,
            )
            * 3.6
        )

        self["fuel cell lifetime replacements"] = np.ceil(
            np.clip(
                self["lifetime kilometers"]
                / (average_speed.T * _(self["fuel cell lifetime hours"]))
                - 1,
                0,
                5,
            )
        ) * (self["fuel cell lifetime hours"] > 0)

    def set_vehicle_masses(self):
        """
        Define ``curb mass``, ``driving mass``, and ``total cargo mass``.

        * `curb mass <https://en.wikipedia.org/wiki/Curb_weight>`__ is the mass of the vehicle and fuel, without people or cargo.
        * ``total cargo mass`` is the mass of the cargo and passengers.
        * ``driving mass`` is the ``curb mass`` plus ``total cargo mass``.

        .. note:: driving mass = total cargo mass + driving mass

        """

        # Base components, common to all powertrains
        base_components = [
            "glider base mass",
            "suspension mass",
            "braking system mass",
            "wheels and tires mass",
            "electrical system mass",
            "transmission mass",
            "other components mass",
        ]

        self["curb mass"] = self[base_components].sum(axis=2) * (
            1 - self["lightweighting"]
        )

        curb_mass_includes = [
            "fuel mass",
            "charger mass",
            "converter mass",
            "inverter mass",
            "power distribution unit mass",
            # Updates with set_components_mass
            "combustion engine mass",
            # Updates with set_components_mass
            "electric engine mass",
            # Updates with set_components_mass
            "exhaust system mass",
            "fuel cell stack mass",
            "fuel cell ancillary BoP mass",
            "fuel cell essential BoP mass",
            "battery cell mass",
            "battery BoP mass",
            "fuel tank mass",
            "HVAC mass",
        ]
        self["curb mass"] += self[curb_mass_includes].sum(axis=2)

        # the curb mass is limited by
        # the fact that the mass
        # of the vehicle is full occupied
        # should be under
        # the maximum allowed gross mass

        self["cargo mass"] = self["average passengers"] * self["passenger luggage mass"]
        self["total cargo mass"] = (
            self["average passengers"] * self["average passenger mass"]
        ) + self["cargo mass"]

        self["driving mass"] = self["curb mass"] + self["total cargo mass"]

    def set_component_masses(self):
        self["combustion engine mass"] = (
            self["combustion power"] * self["engine mass per power"]
            + self["engine fixed mass"]
        )
        self["electric engine mass"] = np.clip(
            (24.56 * np.exp(0.0078 * self["electric power"])), 0, 600
        ) * (self["combustion power share"] < 1)

        self["transmission mass"] = (self["gross mass"] / 1000) * self[
            "transmission mass per ton of gross weight"
        ] + self["transmission fixed mass"]

        self["inverter mass"] = (
            self["electric power"] * self["inverter mass per power"]
            + self["inverter fix mass"]
        )

        self["HVAC mass"] = (self["HVAC power"] / 1000) * self[
            "HVAC system mass per kW"
        ] + self["HVAC system fixed mass"]

    def set_trips_properties(self):
        # average speed along the driving cycle
        self["distance per trip"] = (self.ecm.velocity.sum(axis=0) / 1000).T

        # distance driven per day is the product of the daily operation time
        # and the average speed across the driving cycle
        # (we omitted the stops in the average)
        speed = self.ecm.velocity / 1000 * 3600
        speed[speed == 0] = np.nan
        self["average speed"] = np.nanmean(
            speed,
            axis=0,
        ).T
        self["daily distance"] = self["operation time"] * self["average speed"]

        # the number of trips is simply the daily driven distance
        # divided by the distance of one trip
        self["number of trips"] = self["daily distance"] / self["distance per trip"]

    def set_energy_stored_properties(self):
        """
        First, fuel mass is defined. It is dependent on the range required.
        Then batteries are sized, depending on the range required and the energy consumption.
        :return:
        """
        _ = lambda x: np.where(x > 0, x, 1)

        self.set_average_lhv()
        self["fuel mass"] = (
            self["daily distance"]
            * self["TtW energy"]
            / 1000
            / _(self["LHV fuel MJ per kg"])
            * (self["LHV fuel MJ per kg"] > 0)
        )

        if "ICEV-g" in self.array.coords["powertrain"].values:
            # Based on manufacturer data
            # We use a four-cylinder configuration
            # Of 320L each
            # A cylinder of 320L @ 200 bar can hold 57.6 kg of CNG
            nb_cylinder = np.ceil(
                self.array.loc[dict(powertrain="ICEV-g", parameter="fuel mass")] / 57.6
            )

            self.array.loc[dict(powertrain="ICEV-g", parameter="fuel tank mass")] = (
                (0.018 * np.power(57.6, 2)) - (0.6011 * 57.6) + 52.235
            ) * nb_cylinder

        for pt in [
            pwt
            for pwt in ["ICEV-d", "HEV-d", "PHEV-c-d"]
            if pwt in self.array.coords["powertrain"].values
        ]:
            # From Wolff et al. 2020, Sustainability, DOI: 10.3390/su12135396.
            # We adjusted though the intercept from the original function (-54)
            # because we size here trucks based on the range autonomy
            # a low range autonomy would produce a negative fuel tank mass
            self.array.loc[dict(powertrain=pt, parameter="fuel tank mass")] = (
                17.159
                * np.log(
                    self.array.loc[dict(powertrain=pt, parameter="fuel mass")]
                    * (1 / 0.832)
                )
                - 30
            )

        if "FCEV" in self.array.coords["powertrain"].values:
            # Based on manufacturer data
            # We use a four-cylinder configuration
            # Of 650L each
            # A cylinder of 650L @ 700 bar can hold 14.4 kg of H2
            nb_cylinder = np.ceil(
                self.array.loc[dict(powertrain="FCEV", parameter="fuel mass")] / 14.4
            )

            self.array.loc[dict(powertrain="FCEV", parameter="fuel tank mass")] = (
                (
                    -0.1916
                    * np.power(
                        14.4,
                        2,
                    )
                )
                + (14.586 * 14.4)
                + 10.805
            ) * nb_cylinder

        # for older trolley BEV buses,
        # the share driven without the overhead
        # contact lines require a diesel generator

        if "BEV-motion" in self.array.coords["powertrain"].values:
            self.array.loc[
                dict(powertrain="BEV-motion", parameter="oxidation energy stored")
            ] = np.clip(
                (
                    (
                        self.array.loc[
                            dict(powertrain="BEV-motion", parameter="TtW energy")
                        ]
                        / 3600
                    )
                    * (
                        1
                        - self.array.loc[
                            dict(
                                powertrain="BEV-motion",
                                parameter="trip distance share with catenary",
                            )
                        ]
                    )
                )
                / self.array.loc[
                    dict(powertrain="BEV-motion", parameter="generator efficiency")
                ]
                * self.array.loc[
                    dict(powertrain="BEV-motion", parameter="daily distance")
                ]
                * (
                    1
                    - self.array.loc[
                        dict(
                            powertrain="BEV-motion",
                            parameter="use of auxiliary battery",
                        )
                    ]
                ),
                0,
                None,
            )

        self["oxidation energy stored"] = (
            self["fuel mass"] * self["LHV fuel MJ per kg"] / 3.6
        )

        self["electric energy stored"] = (
            self["daily distance"]
            * self["TtW energy"]
            / 1000
            / _(self["battery DoD"])
            / 3.6
            * (self["combustion power share"] == 0)
        )

        if "BEV-opp" in self.array.powertrain.values:
            # battery sizing factor
            # for fast-charge batteries
            # we operate only between a limited DoD window
            # to prevent cell degradation
            # meaning we use only a specific capacity window
            # hence, the size factor is 1 / (maximum SoC - maximum DoD)
            sizing_factor = 1 / (
                self.array.loc[dict(parameter="maximum SoC", powertrain="BEV-opp")]
                - self.array.loc[dict(parameter="battery DoD", powertrain="BEV-opp")]
            )

            # calculate the number of trips
            # which equals the total daily distance
            # divided by the length of one trip

            # calculate the number of charging opportunities

            self.array.loc[
                dict(parameter="electric energy stored", powertrain="BEV-opp")
            ] = (
                self.array.loc[
                    dict(parameter="distance per trip", powertrain="BEV-opp")
                ]
                * (
                    self.array.loc[dict(parameter="TtW energy", powertrain="BEV-opp")]
                    / 1000
                )
                * sizing_factor
                / 3.6
                / self.array.loc[
                    dict(
                        parameter="charging opportunity per trip", powertrain="BEV-opp"
                    )
                ]
            )

        if "BEV-depot" in self.array.powertrain.values:
            # we add a 20% capacity margin
            self.array.loc[
                dict(parameter="electric energy stored", powertrain="BEV-depot")
            ] = (
                self.array.loc[dict(parameter="daily distance", powertrain="BEV-depot")]
                * (
                    self.array.loc[dict(parameter="TtW energy", powertrain="BEV-depot")]
                    / 1000
                )
                * 1.2
                / self.array.loc[dict(parameter="battery DoD", powertrain="BEV-depot")]
                / 3.6
            )

        # for trolley BEV buses, it is more complex
        # as the size of the battery depends on the
        # extent of the presence of catenary lines
        # so we use the following rule of thumb:
        # the battery capacity is a third of that
        # of opportunity charging BEV buses

        if "BEV-motion" in self.array.powertrain.values:
            # battery sizing factor
            # for fast-charge batteries
            # we operate only between a limited DoD window
            # to prevent cell degradation
            # meaning we use only a specific capacity window
            # hence, the size factor is 1 / (maximum SoC - maximum DoD)
            sizing_factor = 1 / (
                self.array.loc[dict(parameter="maximum SoC", powertrain="BEV-motion")]
                - self.array.loc[dict(parameter="battery DoD", powertrain="BEV-motion")]
            )
            # calculate the number of trips
            # which equals the total daily distance
            # divided by the length of one trip

            # we assume that catenary systems can charge the
            # equivalent of 1kWh / min
            # according to the Zeus project https://www.vdv.de/zeeus-ebus-report-internet.pdfx

            # TtW energy [kj/km] - the charging capacity of the catenary system
            # * the share of the trip equipped with catenary
            # gives us the deficit (battery depletion) per km
            # in Givisiez, around 28% the trip distance is equipped with catenary

            # we add to this a sizing factor
            # to ensure tha the battery is always being charged
            # at a SoC between 40% and 80%
            # to limit degradation

            self.array.loc[
                dict(parameter="electric energy stored", powertrain="BEV-motion")
            ] = np.clip(
                (
                    (
                        self.array.loc[
                            dict(parameter="TtW energy", powertrain="BEV-motion")
                        ]
                        / 3600
                    )
                    - (
                        self.array.loc[
                            dict(
                                parameter="trip distance share with catenary",
                                powertrain="BEV-motion",
                            )
                        ]  # km/km
                        / self.array.loc[
                            dict(parameter="average speed", powertrain="BEV-motion")
                        ]  # km/h
                        * self.array.loc[
                            dict(
                                parameter="catenary system power",
                                powertrain="BEV-motion",
                            )
                        ]
                        / 1000  # kW)
                    )
                )
                * sizing_factor
                * self.array.loc[
                    dict(parameter="use of auxiliary battery", powertrain="BEV-motion")
                ]
                * self.array.loc[
                    dict(parameter="distance per trip", powertrain="BEV-motion")
                ],
                10,
                None,
            )

        if "FCEV" in self.array.powertrain.values:
            # Fuel cell buses do also have a battery, which capacity
            # corresponds roughly to 6% of the capacity contained in the
            # H2 tank

            self.array.loc[
                dict(powertrain="FCEV", parameter="electric energy stored")
            ] = 20 + (
                self.array.loc[dict(powertrain="FCEV", parameter="fuel mass")]
                * 120
                / 3.6
                * 0.06
            )

        # A measured/user-selected capacity overrides service-based sizing.
        if "capacity" in self.energy_storage:
            self.override_battery_capacity()

        self["battery cell mass"] = self["electric energy stored"] / _(
            self["battery cell energy density"]
        )

        self["energy battery mass"] = self["battery cell mass"] / _(
            self["battery cell mass share"]
        )

        self["battery BoP mass"] = (
            self["energy battery mass"] - self["battery cell mass"]
        )

    def set_costs(self):
        glider_components = [
            "glider base mass",
            "suspension mass",
            "braking system mass",
            "wheels and tires mass",
        ]

        self["glider cost"] = np.clip(
            ((38747 * np.log(self[glider_components].sum(dim="parameter"))) - 252194),
            33500,
            110000,
        )

        # Discount glider cost for 40t and 60t trucks because of the added trailer mass

        for size in [
            s for s in ["40t", "60t"] if s in self.array.coords["size"].values
        ]:
            self.array.loc[dict(parameter="glider cost", size=size)] *= 0.7

        self["lightweighting cost"] = (
            self["glider base mass"]
            * self["lightweighting"]
            * self["glider lightweighting cost per kg"]
        )
        self["electric powertrain cost"] = (
            self["electric powertrain cost per kW"] * self["electric power"]
        )
        self["combustion powertrain cost"] = (
            self["combustion power"] * self["combustion powertrain cost per kW"]
        )

        self["fuel cell cost"] = self["fuel cell power"] * self["fuel cell cost per kW"]

        self["power battery cost"] = (
            self["battery power"] * self["power battery cost per kW"]
        )
        self["energy battery cost"] = (
            self["energy battery cost per kWh"] * self["electric energy stored"]
        )
        self["fuel tank cost"] = self["fuel tank cost per kg"] * self["fuel mass"]
        # Per passenger-km
        self["energy cost"] = (
            self["energy cost per kWh"]
            * self["TtW energy"]
            / 3600
            / self["average passengers"]
        )

        # Retain the fuel-cost convention; electric modes use grid purchases.
        _ = lambda x: np.where(x == 0, 1, x)
        self["energy cost"] /= _(self["battery charge efficiency"])
        self.set_electricity_costs(
            self["energy cost per kWh"] / self["average passengers"]
        )

        self["component replacement cost"] = (
            self["energy battery cost"] * self["battery lifetime replacements"]
            + self["fuel cell cost"] * self["fuel cell lifetime replacements"]
        )

        to_markup = [
            "combustion powertrain cost",
            "component replacement cost",
            "electric powertrain cost",
            "energy battery cost",
            "fuel cell cost",
            "fuel tank cost",
            "glider cost",
            "lightweighting cost",
            "power battery cost",
        ]

        self[to_markup] *= self["markup factor"]

        # Interest is annual: convert lifetime distance to years before
        # annualizing capital. Unavailable zero-lifetime cells carry no annuity.
        annual_km = self["kilometers per year"]
        safe_annual_km = annual_km.where(annual_km > 0, 1)
        lifetime_years = self["lifetime kilometers"] / safe_annual_km
        valid_lifetime = (annual_km > 0) & (lifetime_years > 0)
        safe_lifetime_years = lifetime_years.where(valid_lifetime, 1)
        amortisation_factor = capital_recovery_factor(
            self["interest rate"], safe_lifetime_years
        ).where(valid_lifetime, 0)

        with open(DATA_DIR / "purchase_cost_params.yaml", "r") as stream:
            purchase_cost_list = yaml.safe_load(stream)["purchase"]

        self["purchase cost"] = self[purchase_cost_list].sum(axis=2)

        # per passenger-km
        self["amortised purchase cost"] = (
            self["purchase cost"]
            * amortisation_factor
            / self["average passengers"]
            / safe_annual_km
        )

        # per passenger-km
        self["adblue cost"] = (
            self["adblue cost per kg"] * 0.06 * self["fuel mass"]
        ) / self["daily distance"]
        self["maintenance cost"] = self["maintenance cost per km"]
        self["maintenance cost"] += self["adblue cost"]
        self["maintenance cost"] /= self["average passengers"]

        self["insurance cost"] = (
            self["insurance cost per year"]
            / self["average passengers"]
            / self["kilometers per year"]
        )

        self["toll cost"] = self["toll cost per km"] / self["average passengers"]

        # simple assumption that component replacement occurs at half of life.
        self["amortised component replacement cost"] = (
            (
                self["component replacement cost"]
                * (1 + self["interest rate"]) ** (-safe_lifetime_years / 2)
            )
            * amortisation_factor
            / safe_annual_km
            / self["average passengers"]
        )

        self["total cost per km"] = (
            self["energy cost"]
            + self["amortised purchase cost"]
            + self["maintenance cost"]
            + self["insurance cost"]
            + self["toll cost"]
            + self["amortised component replacement cost"]
        )

    # def set_noise_emissions(self):
    #     """
    #     Calculate noise emissions based on ``driving cycle``.
    #     The driving cycle is passed to the :class:`NoiseEmissionsModel` class and :meth:`get_sound_power_per_compartment`
    #     returns emissions per compartment type ("rural", "non-urban" and "urban") per second of driving cycle.
    #
    #     Noise emissions are not differentiated by size classes at the moment, but only by powertrain "type"
    #     (e.g., combustion, hybrid and electric)
    #
    #     :return: Does not return anything. Modifies ``self.array`` in place.
    #     """
    #     nem = NoiseEmissionsModel()
    #
    #     list_noise_emissions = [
    #         "noise, octave 1, day time, urban",
    #         "noise, octave 2, day time, urban",
    #         "noise, octave 3, day time, urban",
    #         "noise, octave 4, day time, urban",
    #         "noise, octave 5, day time, urban",
    #         "noise, octave 6, day time, urban",
    #         "noise, octave 7, day time, urban",
    #         "noise, octave 8, day time, urban",
    #         "noise, octave 1, day time, suburban",
    #         "noise, octave 2, day time, suburban",
    #         "noise, octave 3, day time, suburban",
    #         "noise, octave 4, day time, suburban",
    #         "noise, octave 5, day time, suburban",
    #         "noise, octave 6, day time, suburban",
    #         "noise, octave 7, day time, suburban",
    #         "noise, octave 8, day time, suburban",
    #         "noise, octave 1, day time, rural",
    #         "noise, octave 2, day time, rural",
    #         "noise, octave 3, day time, rural",
    #         "noise, octave 4, day time, rural",
    #         "noise, octave 5, day time, rural",
    #         "noise, octave 6, day time, rural",
    #         "noise, octave 7, day time, rural",
    #         "noise, octave 8, day time, rural",
    #     ]
    #
    #     l_pwt_combustion = [
    #         p
    #         for p in self.array.powertrain.values
    #         if p
    #         in [
    #             "ICEV-g",
    #             "ICEV-d",
    #         ]
    #     ]
    #
    #     l_pwt_electric = [
    #         p
    #         for p in self.array.powertrain.values
    #         if p
    #         in [
    #             "BEV-opp",
    #             "BEV-depot",
    #             "BEV-motion",
    #             "FCEV",
    #         ]
    #     ]
    #
    #     l_size_medium = [
    #         s
    #         for s in self.array.coords["size"].values
    #         if s in ["9m", "13m-city", "13m-coach"]
    #     ]
    #
    #     l_size_heavy = [
    #         s
    #         for s in self.array.coords["size"].values
    #         if s in ["13m-city-double", "13m-coach-double", "18m"]
    #     ]
    #
    #     if len(l_pwt_combustion) > 0 and len(l_size_medium) > 0:
    #         cycle = self.energy.sel(
    #             parameter="velocity", powertrain=l_pwt_combustion, size=l_size_medium
    #         )
    #
    #         self.array.loc[
    #             dict(
    #                 powertrain=l_pwt_combustion,
    #                 parameter=list_noise_emissions,
    #                 size=l_size_medium,
    #             )
    #         ] = nem.get_sound_power_per_compartment(
    #             powertrain_type="combustion",
    #             category="medium",
    #             cycle=cycle,
    #             size=l_size_medium,
    #         )
    #
    #     if len(l_pwt_combustion) > 0 and len(l_size_heavy) > 0:
    #         cycle = self.energy.sel(
    #             parameter="velocity", powertrain=l_pwt_combustion, size=l_size_heavy
    #         )
    #
    #         self.array.loc[
    #             dict(
    #                 powertrain=l_pwt_combustion,
    #                 parameter=list_noise_emissions,
    #                 size=l_size_heavy,
    #             )
    #         ] = nem.get_sound_power_per_compartment(
    #             powertrain_type="combustion",
    #             category="heavy",
    #             cycle=cycle,
    #             size=l_size_heavy,
    #         )
    #
    #     if len(l_pwt_electric) > 0 and len(l_size_medium) > 0:
    #         cycle = self.energy.sel(
    #             parameter="velocity", powertrain=l_pwt_electric, size=l_size_medium
    #         )
    #
    #         self.array.loc[
    #             dict(
    #                 powertrain=l_pwt_electric,
    #                 parameter=list_noise_emissions,
    #                 size=l_size_medium,
    #             )
    #         ] = nem.get_sound_power_per_compartment(
    #             powertrain_type="electric",
    #             category="medium",
    #             cycle=cycle,
    #             size=l_size_medium,
    #         )
    #
    #     if len(l_pwt_electric) > 0 and len(l_size_heavy) > 0:
    #         cycle = self.energy.sel(
    #             parameter="velocity", powertrain=l_pwt_electric, size=l_size_heavy
    #         )
    #
    #         self.array.loc[
    #             dict(
    #                 powertrain=l_pwt_electric,
    #                 parameter=list_noise_emissions,
    #                 size=l_size_heavy,
    #             )
    #         ] = nem.get_sound_power_per_compartment(
    #             powertrain_type="electric",
    #             category="heavy",
    #             cycle=cycle,
    #             size=l_size_heavy,
    #         )
    #
    #     if "HEV-d" in self.array.powertrain.values and len(l_size_medium) > 0:
    #         cycle = self.energy.sel(
    #             parameter="velocity", powertrain="HEV-d", size=l_size_medium
    #         )
    #
    #         self.array.loc[
    #             dict(
    #                 powertrain=["HEV-d"],
    #                 parameter=list_noise_emissions,
    #                 size=l_size_medium,
    #             )
    #         ] = nem.get_sound_power_per_compartment(
    #             powertrain_type="hybrid",
    #             category="medium",
    #             cycle=cycle,
    #             size=l_size_medium,
    #         )
    #
    #     if "HEV-d" in self.array.powertrain.values and len(l_size_heavy) > 0:
    #         cycle = self.energy.sel(
    #             parameter="velocity", powertrain="HEV-d", size=l_size_heavy
    #         )
    #
    #         self.array.loc[
    #             dict(
    #                 powertrain=["HEV-d"],
    #                 parameter=list_noise_emissions,
    #                 size=l_size_heavy,
    #             )
    #         ] = nem.get_sound_power_per_compartment(
    #             powertrain_type="hybrid",
    #             category="heavy",
    #             cycle=cycle,
    #             size=l_size_heavy,
    #         )

    def calculate_cost_impacts(self, sensitivity=False, scope=None):
        """
        This method returns an array with cost values per vehicle-km, sub-divided into the following groups:

        * Purchase
        * Maintenance
        * Component replacement
        * Energy
        * Total cost of ownership

        :return: a_matrix xarray array with cost information per vehicle-km
        :rtype: xarray.core.dataarray.DataArray
        """

        if scope is None:
            scope = {
                "size": self.array.coords["size"].values.tolist(),
                "powertrain": self.array.coords["powertrain"].values.tolist(),
                "year": self.array.coords["year"].values.tolist(),
            }
        else:
            scope["size"] = scope.get("size", self.array.coords["size"].values.tolist())
            scope["powertrain"] = scope.get(
                "powertrain", self.array.coords["powertrain"].values.tolist()
            )
            scope["year"] = scope.get("year", self.array.coords["year"].values.tolist())

        list_cost_cat = [
            "purchase",
            "maintenance",
            "insurance",
            "toll",
            "component replacement",
            "energy",
            "total",
        ]

        response = xr.DataArray(
            np.zeros(
                (
                    len(scope["size"]),
                    len(scope["powertrain"]),
                    len(list_cost_cat),
                    len(scope["year"]),
                    len(self.array.coords["value"].values),
                )
            ),
            coords=[
                scope["size"],
                scope["powertrain"],
                list_cost_cat,
                scope["year"],
                self.array.coords["value"].values.tolist(),
            ],
            dims=["size", "powertrain", "cost_type", "year", "value"],
        )

        response.loc[
            :,
            :,
            list_cost_cat,
            :,
            :,
        ] = self.array.sel(
            powertrain=scope["powertrain"],
            size=scope["size"],
            year=scope["year"],
            parameter=[
                "amortised purchase cost",
                "maintenance cost",
                "insurance cost",
                "toll cost",
                "amortised component replacement cost",
                "energy cost",
                "total cost per km",
            ],
        ).values

        if not sensitivity:
            return response * (self.array.sel(parameter="total cargo mass") > 100)
        else:
            return response / response.sel(value="reference")

    def get_availability_mask(self):
        """Return the existing technology/year availability policy per cell.

        Unsupported configurations do not constrain convergence of active buses.
        This mask does not relax mass limits or convergence for active vehicles.
        """
        available = xr.ones_like(self["driving mass"], dtype=bool)
        pwt = self.array.powertrain
        size = self.array.coords["size"]
        electric = pwt.isin(["BEV-depot", "BEV-opp", "BEV-motion"])
        available &= ~(electric & (self.array.year < 2020))
        available &= ~(size.str.contains("coach") & pwt.isin(["BEV-opp", "BEV-motion"]))
        available &= ~(
            (pwt == "BEV-motion")
            & size.isin(["13m-city-double", "13m-coach", "13m-coach-double"])
        )
        return available

    def remove_energy_consumption_from_unavailable_vehicles(self):
        """Apply technology availability and actual driving-mass compliance."""
        self["is_available"] = self.get_availability_mask()
        self["TtW energy"] *= self["is_available"]

        # A planning assumption about peak occupancy is not a physical limit
        # on the explicitly requested driving mass. Retain it as a diagnostic.
        self.peak_passenger_capacity_sufficient = (
            np.floor(
                (self["gross mass"] - self["curb mass"])
                / self["average passenger mass"].where(
                    self["average passenger mass"] > 0, 1
                )
            )
            >= self["average passengers"] * 1.5
        )
        self["is_compliant"] = self["driving mass"] <= self["gross mass"] + 1e-6
        self["TtW energy"] *= self["is_compliant"]
        self.mask_energy_outputs(
            self.get_availability_mask() & (self["is_compliant"] != 0)
        )
