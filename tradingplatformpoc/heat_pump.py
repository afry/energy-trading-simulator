from io import StringIO

import numpy as np

import pandas as pd

from sklearn import linear_model
from sklearn.preprocessing import PolynomialFeatures


class HeatPump():
    """
    A component to allow building agents to convert electricity to heat.
    """
    coeff_of_perf: float
    max_capacity: float

    """
    This class needs the following:
    
    1. A function for calculating forcasted efficiency att different gears given the brine and target temperature
    2. A method for actually converting power to heat at the specified efficiency

    Given the forecasted efficiency, the BuildingAgent should optimise the mix of heat pump/district heat with respect
    to total cost, where the cost may or may not be adjusted for carbon intensity.

    The function for calculating pump efficiency based on gear and desired temperature can be based on the work in the
    Decision maker project
    """

    # --- Fetch calibration data to be run at instantiation
    calibration_data_stringio = StringIO("""forward_temp_C,rpm,brine_temp_C,desired_heat_kW,cop
    35., 0., -5., 0., 0.
    35., 0., 0., 0., 0.
    35., 0., 5., 0., 0.
    35., 1500., -5., 9.54, 3.89
    35., 1500., 0., 11.10, 4.58
    35., 1500., 5., 12.83, 5.34
    35., 3000., -5., 19.30, 4.09
    35., 3000., 0., 22.33, 4.73
    35., 3000., 5., 25.91, 5.47
    35., 3600., -5., 23.11, 4.01
    35., 3600., 0., 26.70, 4.61
    35., 3600., 5., 30.98, 5.31
    35., 4500., -5., 28.71, 3.83
    35., 4500., 0., 33.13, 4.38
    35., 4500., 5., 38.56, 5.04
    35., 6000., -5., 38.08, 3.44
    35., 6000., 0., 43.82, 3.91
    35., 6000., 5., 48.58, 4.27
    55., 0., -5., 0., 0.
    55., 0., 0., 0., 0.
    55., 0., 5., 0., 0.
    55., 1500., -5., 9.41, 2.40
    55., 1500., 0., 10.64, 2.73
    55., 1500., 5., 12.08, 3.12
    55., 3000., -5., 18.46, 2.61
    55., 3000., 0., 21.04, 2.98
    55., 3000., 5., 23.99, 3.41
    55., 3600., -5., 22.10, 2.62
    55., 3600., 0., 25.17, 2.97
    55., 3600., 5., 28.70, 3.39
    55., 4500., -5., 27.59, 2.58
    55., 4500., 0., 31.36, 2.92
    55., 4500., 5., 35.72, 3.32
    55., 6000., -5., 37.10, 2.51
    55., 6000., 0., 41.69, 2.79
    55., 6000., 5., 47.23, 3.16""")

    calibration_data = pd.read_csv(calibration_data_stringio)

    # --- Split calibration data into dependent and independent variables
    calibration_heat_kw, calibration_cop, calibration_features = calibration_data['desired_heat_kW'], calibration_data[
        'cop'], calibration_data.drop(['desired_heat_kW', 'cop'], axis='columns')

    # --- Generate polynomial features
    ndeg_heat, ndeg_cop = 2, 4
    polynomial_features_heat = PolynomialFeatures(degree=ndeg_heat)
    polynomial_features_cop = PolynomialFeatures(degree=ndeg_cop)

    # --- Transform calibration features for proper fitting (for single variable, this would return [1, x, x**2])
    calibration_features_heat = polynomial_features_heat.fit_transform(calibration_features)
    calibration_features_cop = polynomial_features_cop.fit_transform(calibration_features)

    # --- Make regression objects
    model_heat = linear_model.LinearRegression()
    model_cop = linear_model.LinearRegression()

    # --- Calibrate models to tabulated data
    model_heat.fit(calibration_features_heat, calibration_heat_kw)
    model_cop.fit(calibration_features_cop, calibration_cop)

    # Should this be a static method or specific to instance?
    # Is there any dependency on the state of an instance?
    def get_heatpump_throughputs(self, forward_temp_c: np.array, workload: np.array,
                                 brine_temp_c: np.array,
                                 polynomial_features_heat=polynomial_features_heat,
                                 polynomial_features_cop=polynomial_features_cop,
                                 model_heat=model_heat, model_cop=model_cop):
        """
        Calculates predicted heat output in kWh as well as "Coefficient of Production" (COP), which specifies the
        efficiency of electricity->heat conversion at the given settings

        We use tabluated data to fit a linear model with polynomial features as parameters
        """
        # logger.info("Calculating heatpump throughputs (heat and COP).")

        # --- Convert workload to rpm
        rpm = self.map_workload_to_rpm(workload=workload)

        # --- Transform new readings to correct shape for model
        sensor_readings = np.transpose(np.array([forward_temp_c, rpm, brine_temp_c]))
        features_for_heat_prediction = polynomial_features_heat.fit_transform(sensor_readings)
        features_for_cop_prediction = polynomial_features_cop.fit_transform(sensor_readings)

        # --- Assign predictions to variables
        predicted_heat_kw = model_heat.predict(features_for_heat_prediction)
        predicted_cop = model_cop.predict(features_for_cop_prediction)

        return predicted_heat_kw, predicted_cop

    def map_workload_to_rpm(self, workload: np.array, workload_min: float = 10, workload_max: float = 100,
                            rpm_min: float = 1500, rpm_max: float = 6000) -> np.array:
        """
        Function to perform a linear mapping of an input workload into an output rpm.
        The workload refers to the "intensity-step"/gear - setting on which the heat-pump shall work. As such, it is
        expected to be in the range 0 - 100%.

        TODO: change workload from current 0-100% to actual heat-pump step-setting (i.e. workload_min=0, workload_max=9)
        TODO: Before committing the above TODO, write a unit test to ensure correct behaviour after limit-change!
        """

        if workload.min() < workload_min or workload.max() > workload_max:
            raise ValueOutOfRangeError("Input workload is out of range [0:100]. Currently spans ", workload.min(),
                                       "to ", workload.max())
        # --- Define ranges
        workload_range = workload_max - workload_min
        rpm_range = rpm_max - rpm_min

        # --- Convert the workload range into a 0-1 range
        normalized_workload = (workload - workload_min) / workload_range

        # --- Convert the normalized range into an rpm
        rpm = rpm_min + (normalized_workload * rpm_range)

        return rpm

    def produce_heat(self, input_elec_power: float, cop: float):
        """
        A function for the heat pump component to actually return heat given an amount of power.
        This is calculated by simply inputting the provided electric power and multiplying it by the selected COP
        """
        heat: float = input_elec_power * cop
        return heat


class ValueOutOfRangeError(Exception):
    """
    Raised when an input is out of valid range.
    """
    pass
