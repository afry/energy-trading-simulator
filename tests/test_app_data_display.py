from unittest import TestCase

from tradingplatformpoc.app.app_data_display import resource_dict_to_display_df


class Test(TestCase):
    def test_resource_dict_to_display_df(self):
        """Call resource_dict_to_display_df and make sure no error is encountered"""
        dict_to_test = {'Electricity': 12345678.0, 'Heating': 0.0}
        print(resource_dict_to_display_df(dict_to_test, 1 / 1000, 'MWh', 'Total'))
