from unittest import TestCase

from tradingplatformpoc import heat_pump
from tradingplatformpoc.heat_pump import HeatPump, ValueOutOfRangeError


class Test(TestCase):

    def test_throughput_calculation(self):
        """Test that calculate_energy works in a reasonable way, and that specifying a COP works as intended"""
        elec_input, heat_output = HeatPump.calculate_energy(workload=6, forward_temp_c=60, brine_temp_c=0)
        cop_output = heat_output / elec_input
        self.assertAlmostEqual(2.7613787873898135, cop_output)

        # If we want a "better" heat pump, assert that output COP increases by the correct amount
        elec_input, heat_output = HeatPump.calculate_energy(workload=6, forward_temp_c=60, brine_temp_c=0,
                                                            coeff_of_perf=5)
        better_cop_output = heat_output / elec_input
        cop_output_percent_increase = better_cop_output / cop_output
        cop_input_percent_increase = 5 / heat_pump.DEFAULT_COP
        self.assertAlmostEqual(cop_input_percent_increase, cop_output_percent_increase)

    def test_calculate_for_all_workloads(self):
        """Test that calculate_for_all_workloads produces some results, and that the results are strictly increasing."""
        test_pump = heat_pump.HeatPump()

        results = test_pump.calculate_for_all_workloads()

        self.assertEqual(11, len(results))

        def strictly_increasing(some_list):
            return all(x < y for x, y in zip(some_list, some_list[1:]))

        self.assertTrue(strictly_increasing(list(results.keys())))
        # When sorted by workload, both input and output should be steadily increasing
        self.assertTrue(strictly_increasing([x[0] for x in results.values()]))  # Tests input electricity
        self.assertTrue(strictly_increasing([x[1] for x in results.values()]))  # Tests output heating

    def test_logging(self):
        """Test that heat pump methods log warnings when inputs are outside of expected range"""
        with self.assertLogs() as captured:
            elec_needed = heat_pump.model_elec_needed(70, 8000)
            self.assertAlmostEqual(25.3237594, elec_needed)
        self.assertEqual(len(captured.records), 2)

        with self.assertLogs() as captured:
            heat_output = heat_pump.model_heat_output(70, 8000, -11)
            self.assertAlmostEqual(37.312527, heat_output)
        self.assertEqual(len(captured.records), 3)

    def test_map_workload_to_rpm(self):
        """Test that map_workload_to_rpm throws an error when input is outside expected range"""
        with self.assertRaises(ValueOutOfRangeError):
            heat_pump.map_workload_to_rpm(12)
