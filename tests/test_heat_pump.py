from unittest import TestCase

from tradingplatformpoc import heat_pump


class Test(TestCase):

    def test_throughput_calculation(self):
        test_pump = heat_pump.HeatPump()

        elec_input, heat_output = test_pump.calculate_energy(workload=6, forward_temp_c=60, brine_temp_c=0)
        cop_output = heat_output / elec_input
        self.assertAlmostEqual(2.7613787873898135, cop_output)

        # If we want a "better" heat pump, assert that output COP increases by the correct amount
        better_pump = heat_pump.HeatPump(5)

        elec_input, heat_output = better_pump.calculate_energy(workload=6, forward_temp_c=60, brine_temp_c=0)
        better_cop_output = heat_output / elec_input
        cop_output_percent_increase = better_cop_output / cop_output
        cop_input_percent_increase = 5 / heat_pump.DEFAULT_COP
        self.assertAlmostEqual(cop_input_percent_increase, cop_output_percent_increase)

    def test_calculate_for_all_workloads(self):
        test_pump = heat_pump.HeatPump()

        results = test_pump.calculate_for_all_workloads()

        self.assertEqual(11, len(results.index))

        results = results.sort_values(by=['workload'], axis=0, ascending=True)
        # When sorted by workload, both input and output should be steadily increasing
        self.assertTrue(results['input'].is_monotonic_increasing)
        self.assertTrue(results['output'].is_monotonic_increasing)
