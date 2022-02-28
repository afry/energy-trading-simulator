from unittest import TestCase

import numpy as np

from tradingplatformpoc import heat_pump


class Test(TestCase):

    def test_throughput_calculation(self):
        test_pump = heat_pump.HeatPump()
        # What are good test parameters?

        forward_temp_c = np.array([45])
        workload = np.array([60])
        brine_temp_c = np.array([0])

        heat_output, cop_output = test_pump.get_heatpump_throughputs(forward_temp_c=forward_temp_c, workload=workload, brine_temp_c=brine_temp_c)
        #self.assertEqual()
        print(heat_output, cop_output)
        self.assertAlmostEqual(heat_output[0], 28.8, places=1)
        self.assertAlmostEqual(cop_output[0], 5.9, places=1)

    def test_power_conversion(self):
        test_pump = heat_pump.HeatPump()

        input_power = 100
        cop = 3.5

        heat_output = test_pump.produce_heat(input_elec_power=input_power, cop=cop)

        self.assertEqual(heat_output, input_power*cop)
