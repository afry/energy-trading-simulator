from unittest import TestCase

from tradingplatformpoc.digitaltwin.battery_digital_twin import BatteryDigitalTwin


class TestBatteryDigitalTwin(TestCase):

    def setUp(self):
        self.storage_digital_twin = BatteryDigitalTwin(max_capacity_kwh=100.0, max_charge_rate_fraction=0.25,
                                                       max_discharge_rate_fraction=0.2, start_capacity_kwh=6,
                                                       discharging_efficiency=0.93)

    def test_charge_battery(self):
        """Test charging the battery with the input amount. It will charge the battery with
            maximum amount of (max_capacity_kwh * max_charge_rate_fraction), if the capacity (after charging)
            is equal or less than "max_capacity_kwh", at one time step."""
        self.assertAlmostEqual(5, self.storage_digital_twin.charge(5))

    def test_discharge_battery(self):
        """Test discharging the battery with the input amount. Total discharging amount should be equal or less than
            (max_capacity_kwh * max_discharge_rate_fraction), if it does not exceed (capacity * discharging_efficiency),
             at one time step. When discharging the storage X kWh, the current capacity decreased by
             (X / discharging_efficiency)."""
        # Start capacity is 6
        self.assertAlmostEqual(6.0, self.storage_digital_twin.capacity_kwh)
        self.assertAlmostEqual(4.65, self.storage_digital_twin.discharge(4.65))
        # 4.65 / 0.93 = 5, so we expect 1 here
        self.assertAlmostEqual(1.0, self.storage_digital_twin.capacity_kwh)

    def test_possible_charge_amount(self):
        self.assertAlmostEqual(25, self.storage_digital_twin.get_possible_charge_amount())

    def test_possible_discharge_amount(self):
        self.assertAlmostEqual(5.58, self.storage_digital_twin.get_possible_discharge_amount())
