from unittest import TestCase

from tradingplatformpoc.generate_data.generation_functions.non_residential.common import \
    probability_of_0_space_heating, space_heating_given_more_than_0


class Test(TestCase):

    def test_probability_of_0_heating(self):
        self.assertEqual(0.0, probability_of_0_space_heating(0))
        self.assertEqual(0.0, probability_of_0_space_heating(4.9))
        self.assertAlmostEqual(0.2001756355822556, probability_of_0_space_heating(10))
        self.assertAlmostEqual(0.4963395653959213, probability_of_0_space_heating(12.5))
        self.assertAlmostEqual(0.8990463418486527, probability_of_0_space_heating(15))
        self.assertEqual(1.0, probability_of_0_space_heating(20))

    def test_heating_given_more_than_0(self):
        self.assertAlmostEqual(26.030581, space_heating_given_more_than_0(0))
        self.assertAlmostEqual(16.5071027, space_heating_given_more_than_0(4.9))
        self.assertAlmostEqual(6.594911, space_heating_given_more_than_0(10))
        self.assertAlmostEqual(1.7359935, space_heating_given_more_than_0(12.5))
        self.assertEqual(0.0, space_heating_given_more_than_0(15))
