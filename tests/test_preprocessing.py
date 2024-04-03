from unittest import TestCase

from tradingplatformpoc.data.preprocessing import clean, read_office_data


class Test(TestCase):
    def test_read_office_data(self):
        data = read_office_data()
        self.assertEqual(8756, len(data.index))
        cleaned_data = clean(data)
        self.assertEqual(8760, len(cleaned_data.index))
