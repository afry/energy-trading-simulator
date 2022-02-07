import datetime
from unittest import TestCase

import numpy as np

import pandas as pd

from tradingplatformpoc.district_heating_calculations import calculate_jan_feb_avg_heating_sold, \
    calculate_peak_day_avg_cons_kw, estimate_district_heating_price, exact_district_heating_price_for_month


from matplotlib import pyplot as plt

class Test(TestCase):
    # Rough prices:
    # Jan - Feb: 0.55 + 0.66 + 0.10 = 1.31 SEK / kWh
    # Mar - Apr: 0.55 + 0.10 = 0.65 SEK / kWh
    # May - Sep: 0.33 + 0.10 = 0.45 SEK / kWh
    # Oct - Dec: 0.55 + 0.10 = 0.65 SEK / kWh

    def test_estimate_district_heating_price_jan(self):
        self.assertAlmostEqual(1.311891744, estimate_district_heating_price(datetime.datetime(2019, 1, 1)))

    def test_estimate_district_heating_price_feb(self):
        self.assertAlmostEqual(1.322548426, estimate_district_heating_price(datetime.datetime(2019, 2, 1)))

    def test_estimate_district_heating_price_mar(self):
        self.assertAlmostEqual(0.649462366, estimate_district_heating_price(datetime.datetime(2019, 3, 1)))

    def test_estimate_district_heating_price_apr(self):
        self.assertAlmostEqual(0.652777777, estimate_district_heating_price(datetime.datetime(2019, 4, 1)))

    def test_estimate_district_heating_price_may(self):
        self.assertAlmostEqual(0.429462366, estimate_district_heating_price(datetime.datetime(2019, 5, 1)))

    def test_estimate_district_heating_price_jun(self):
        self.assertAlmostEqual(0.432777777, estimate_district_heating_price(datetime.datetime(2019, 6, 1)))
        #print(estimate_district_heating_price(datetime.datetime(2019, 6, 1)))

    def test_estimate_district_heating_price_july(self):
        self.assertAlmostEqual(0.429462365, estimate_district_heating_price(datetime.datetime(2019, 7, 1)))

    def test_estimate_district_heating_price_aug(self):
        self.assertAlmostEqual(0.429462365, estimate_district_heating_price(datetime.datetime(2019, 8, 1)))

    # def test_estimate_district_heating_price_oct(self):
    #    self.assertAlmostEqual(0.432777777, estimate_district_heating_price(datetime.datetime(2019, 9, 1)))

    def test_estimate_district_heating_price_oct(self):
        self.assertAlmostEqual(0.649462365, estimate_district_heating_price(datetime.datetime(2019, 10, 1)))

    def test_estimate_district_heating_price_nov(self):
        self.assertAlmostEqual(0.652777777, estimate_district_heating_price(datetime.datetime(2019, 11, 1)))

    def test_estimate_district_heating_price_dec(self):
            self.assertAlmostEqual(0.649462365, estimate_district_heating_price(datetime.datetime(2019, 12, 1)))






    # tests for exact price calculations
    def some_test(self):

        output_temp = []
        output_test = []
        output = []

        year = [2019]
        #month = [1,2,3,4,5,6,7,8,9,10,11,12]
        month = [10,11]
        consumption_this_month_kwh = [1200]
        jan_feb_avg_consumption_kw = [50,100,150,200]
        prev_month_peak_day_avg_consumption_kw = [8,16,32,40]

        for i in year:
            print("-------------------YEAR = ", i)
            for j in month:
                print("-------------------MONTH = ", j)
                for k in consumption_this_month_kwh:
                    print("-------------------Consumption = ", k)
                    for l in jan_feb_avg_consumption_kw:
                        print("-------------------Jan_fab_avg = ", l)
                        for m in prev_month_peak_day_avg_consumption_kw:
                            print("-------------------Prev_month_peak_day_avg = ", m)
                            effect_fee, grid_fee, base_marginal_price, exact_fee = exact_district_heating_price_for_month(j, i, k, l, m)
                            print("effect_fee = ", effect_fee)
                            print("grid_fee = ", grid_fee)
                            print("base_marginal_price = ", base_marginal_price)
                            print("exact_fee = ", exact_fee)
                            output_temp.append(i)
                            output_temp.append(j)
                            output_temp.append(k)
                            output_temp.append(l)
                            output_temp.append(m)
                            output_temp.append(effect_fee)
                            output_temp.append(grid_fee)
                            output_temp.append(base_marginal_price)
                            output_temp.append(exact_fee)

                            output_test.append(output_temp)
                            output_temp = []

        print("***********************")
        output.append(output_test)
        print('output', output)
        print('type(output)', type(output))
        print('len(output)', len(output))
        print("-----------------------------")
        print("output[0] = ", output[0])
        print("len(output[0]) = ", len(output[0]))
        print("output[0][0] = ", output[0][0])
        print("len(output[0][1]) = ", len(output[0][1]))
        print("output[0][0][0] = ", output[0][0][0], output[0][0][1], output[0][1][3], output[0][1][4])
        # output = [year, month, Consumption, Jan_feb_avg, Prev_month_peak_day_avg, effect_fee, grid_fee, base_marginal_price, exact_fee]


        year_test = []
        month_test = []
        Consumption_test = []
        Jan_feb_avg_test = []
        Prev_month_peak_day_avg_test = []
        effect_fee_test = []
        grid_fee_test = []
        base_marginal_price_test = []
        exact_fee_test = []


        for i in range(len(output[0])):
            #for j in range(len(output[0][0])):
            #print(i)
            #print(output[0][i][j])
            year_test.append(output[0][i][0])
            month_test.append(output[0][i][1])
            Consumption_test.append(output[0][i][2])
            Jan_feb_avg_test.append(output[0][i][3])
            Prev_month_peak_day_avg_test.append(output[0][i][4])
            effect_fee_test.append(output[0][i][5])
            grid_fee_test.append(output[0][i][6])
            base_marginal_price_test.append(output[0][i][7])
            exact_fee_test.append(output[0][i][8])


        print("year_test = ", year_test)
        print("month_test = ", month_test)
        print("Consumption_test = ", Consumption_test)
        print("Jan_feb_avg_test = ", Jan_feb_avg_test)
        print("Prev_month_peak_day_avg_test = ", Prev_month_peak_day_avg_test)
        print("effect_fee_test = ", effect_fee_test)
        print("grid_fee_test = ", grid_fee_test)
        print("base_marginal_price_test = ", base_marginal_price_test)
        print("exact_fee_test = ", exact_fee_test)

        # year = [2019]
        # # month = [1,2,3,4,5,6,7,8,9,10,11,12]
        # month = [10, 11]
        # consumption_this_month_kwh = [1200]
        # jan_feb_avg_consumption_kw = [50, 100, 150]
        # prev_month_peak_day_avg_consumption_kw = [8, 16, 32]

        test_case_year = 2019
        test_case_month = 10
        test_case_consumption = 1200

        test_case_exact_fee = []
        test_case_effect_fee_test = []
        test_case_grid_fee_test = []
        test_case_Jan_feb_avg = []
        test_case_Prev_month_peak_day_avg = []

        for i in range(len(year_test)):
            if year_test[i] == test_case_year and month_test[i] == test_case_month and  Consumption_test[i] == test_case_consumption:
                test_case_Jan_feb_avg.append(Jan_feb_avg_test[i])
                test_case_Prev_month_peak_day_avg.append(Prev_month_peak_day_avg_test[i])
                test_case_exact_fee.append(exact_fee_test[i])
                test_case_effect_fee_test.append(effect_fee_test[i])
                test_case_grid_fee_test.append(grid_fee_test[i])
        print()
        len_uniq = test_case_Jan_feb_avg.count(test_case_Jan_feb_avg[0])#len(list(set(test_case_Jan_feb_avg)))
        #test_case_Prev_month_peak_day_avg = list(set(test_case_Prev_month_peak_day_avg))
        print("test_case_Jan_feb_avg = ", test_case_Jan_feb_avg)
        print("test_case_Prev_month_peak_day_avg = ", test_case_Prev_month_peak_day_avg)
        print("test_case_exact_fee = ", test_case_exact_fee)
        print("test_case_effect_fee_test = ", test_case_effect_fee_test)
        print("test_case_grid_fee_test = ", test_case_grid_fee_test)


        # plot for the exact fee
        fig, ax = plt.subplots(3, sharex=True)
        for i in range(0,len(test_case_Jan_feb_avg),len_uniq):
            ax[0].plot(test_case_Prev_month_peak_day_avg[i:i+len_uniq], test_case_exact_fee[i:i+len_uniq], marker = 'o', label = 'Jan_feb_avg = ' + str(test_case_Jan_feb_avg[i]))
            #plt.xticks(test_case_Prev_month_peak_day_avg, test_case_Prev_month_peak_day_avg)
            ax[1].plot(test_case_Prev_month_peak_day_avg[i:i+len_uniq], test_case_effect_fee_test[i:i+len_uniq], marker = 'o', label = 'Jan_feb_avg = ' + str(test_case_Jan_feb_avg[i]))
            #plt.xticks(test_case_Prev_month_peak_day_avg, test_case_Prev_month_peak_day_avg)
            ax[2].plot(test_case_Prev_month_peak_day_avg[i:i + len_uniq], test_case_grid_fee_test[i:i + len_uniq], marker='o', label='Jan_feb_avg = ' + str(test_case_Jan_feb_avg[i]))

        ax[0].set_xticks(test_case_Prev_month_peak_day_avg, test_case_Prev_month_peak_day_avg)
        plt.xlabel("Prev_month_peak_day_avg")
        ax[0].set_ylabel("Exact_Cost")
        ax[1].set_ylabel("Effect_Fee")
        ax[2].set_ylabel("Grid_Fee")

        ax[0].set_title(label='year = ' + str(test_case_year) + ', month = ' + str(test_case_month) + ', Consumption = ' + str(test_case_consumption) )
        plt.legend(loc='center left', bbox_to_anchor=(1, 1.75))
        #plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), fancybox=True, shadow=True, ncol=5)
        plt.show()



        # plt.plot([0.1, 0.2, 0.3, 0.4], [1, 2, 3, 4], label='first plot')
        # plt.plot([0.1, 0.2, 0.3, 0.4], [1, 4, 9, 16], label='second plot')
        # plt.xlabel("Time (s)")
        # plt.ylabel("Scale (Bananas)")
        # plt.legend()
        # plt.show()


        # exact_district_heating_price_for_month(10, 2019, 1200, 50, 16)
        # exact_district_heating_price_for_month(10, 2019, 1200, 100, 16)
        # exact_district_heating_price_for_month(10, 2019, 1200, 150, 16)
        # exact_district_heating_price_for_month(10, 2019, 1200, 200, 16)
        # exact_district_heating_price_for_month(10, 2019, 1200, 250, 16)
        # (month, year, consumption_this_month_kwh, jan_feb_avg_consumption_kw, prev_month_peak_day_avg_consumption_kw)


    def test_calculate_jan_feb_avg_heating_sold(self):
        """Test basic functionality of calculate_jan_feb_avg_heating_sold"""
        all_external_heating_sells = pd.Series()
        all_external_heating_sells[datetime.datetime(2019, 2, 1, 1)] = 50
        all_external_heating_sells[datetime.datetime(2019, 3, 1, 1)] = 100
        self.assertAlmostEqual(50, calculate_jan_feb_avg_heating_sold(all_external_heating_sells,
                                                                      datetime.datetime(2019, 3, 1, 1)))
        self.assertTrue(np.isnan(calculate_jan_feb_avg_heating_sold(all_external_heating_sells,
                                                                    datetime.datetime(2019, 2, 1, 1))))

    def test_calculate_peak_day_avg_cons_kw(self):
        """Test basic functionality of calculate_peak_day_avg_cons_kw"""
        all_external_heating_sells = pd.Series()
        all_external_heating_sells[datetime.datetime(2019, 3, 1, 1)] = 100
        all_external_heating_sells[datetime.datetime(2019, 3, 1, 2)] = 140
        all_external_heating_sells[datetime.datetime(2019, 3, 2, 1)] = 50
        all_external_heating_sells[datetime.datetime(2019, 3, 2, 2)] = 50
        all_external_heating_sells[datetime.datetime(2019, 3, 2, 3)] = 50
        self.assertAlmostEqual(10, calculate_peak_day_avg_cons_kw(all_external_heating_sells, 2019, 3))

