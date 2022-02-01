from tradingplatformpoc.digitaltwin.idigital_twin import IDigitalTwin


class StorageDigitalTwin(IDigitalTwin):

    def __init__(self, max_capacity_kwh: float,
                 max_charge_rate_fraction: float,
                 max_discharge_rate_fraction: float,
                 discharging_efficiency: float,
                 start_capacity_kwh: float = 0,
                 start_is_charging: bool = True):
        """

        @param max_capacity_kwh: The amount of energy that can be stored at a maximum, in kWh
        @param max_charge_rate_fraction: How much of the total capacity that can be charged in one time step. If this is
            1.0, then the storage unit can go from totally empty, to totally full, in one time step.
        @param max_discharge_rate_fraction: How much of the total capacity that can be discharged in one time step. If
            this is 1.0, then the storage unit can go from totally full, to totally empty, in one time step.
        @param discharging_efficiency: How efficient is the battery (RoundTripEfficiency efficiency). If this is 0.93,
            then the storage unit can only output (discharge) 93% of its full capacity.
        @param start_capacity_kwh: The amount of energy contained in the storage unit on startup.
        @param start_is_charging: If the storage unit is in charging or discharging mode on startup (some storage units,
            such as a hydrogen storage, may take some time to transition from charging to discharging mode).
        """
        super().__init__()
        self.max_capacity_kwh = max_capacity_kwh
        self.max_charge_rate_fraction = max_charge_rate_fraction
        self.max_discharge_rate_fraction = max_discharge_rate_fraction
        self.discharging_efficiency = discharging_efficiency
        self.capacity_kwh = start_capacity_kwh
        self.is_charging = start_is_charging
        self.charge_limit_kwh = self.max_capacity_kwh * self.max_charge_rate_fraction
        self.discharge_limit_kwh = self.max_capacity_kwh * self.max_discharge_rate_fraction

    def charge(self, quantity):
        """Charges the battery, changing the fields "charging" and "capacity".
        Will return how much the battery was charged. This will most often be equal to the "quantity" argument, but will
        be adjusted for "max_capacity_kwh" and "max_charge_rate_fraction".
        """
        self.is_charging = True
        # So that we don't exceed max capacity:
        amount_to_charge = min(float(self.max_capacity_kwh - self.capacity_kwh), float(quantity), self.charge_limit_kwh)
        self.capacity_kwh = self.capacity_kwh + amount_to_charge
        return amount_to_charge

    def discharge(self, quantity):
        """Discharges the battery, changing the fields "charging" and "capacity".
        Will return how much the battery was discharged. This will most often be equal to the "quantity" argument, but
        will be adjusted for current "capacity_kwh", "discharging_efficiency" and "max_discharge_rate_fraction".
        When discharging "quantity" (X kWh) from the storage, the current capacity is decreased by
        "X / discharging_efficiency"."""
        self.is_charging = False
        # So that we don't discharge more than self.capacity:
        amount_to_discharge = min(min(float(self.capacity_kwh * self.discharging_efficiency), float(quantity)),
                                  self.discharge_limit_kwh)
        self.capacity_kwh = self.capacity_kwh - (amount_to_discharge / self.discharging_efficiency)
        return amount_to_discharge

    def get_possible_charge_amount(self):
        return min([self.max_capacity_kwh - self.capacity_kwh, self.charge_limit_kwh])

    def get_possible_discharge_amount(self):
        return min([self.capacity_kwh * self.discharging_efficiency, self.discharge_limit_kwh])
