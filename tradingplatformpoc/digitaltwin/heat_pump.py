import logging
from collections import OrderedDict
from typing import Dict, List, Tuple

import numpy as np


# These numbers come from "simple_heat_pump_model.ipynb" in data-exploration project
ELEC_INTERCEPT_COEF = -5.195751e-01
ELEC_RPM_SQUARED_COEF = 1.375397e-07
ELEC_FORWARD_TEMP_COEF = 3.693311e-02
ELEC_FORWARD_TEMP_TIMES_RPM_COEF = 2.581335e-05
HEAT_INTERCEPT_COEF = 0.520527
HEAT_RPM_COEF = 0.007857
HEAT_FORWARD_TEMP_TIMES_RPM_COEF = -0.000017
HEAT_BRINE_TEMP_TIMES_RPM_COEF = 0.000188


DEFAULT_COP = 4.6  # Specified in technical description of "Thermium Mega" heat pump
DEFAULT_BRINE_TEMP = 0
DEFAULT_FORWARD_TEMP = 55
RPM_MIN = 1500
RPM_MAX = 6000

MIN_WORKLOAD = 1
MAX_WORKLOAD = 10
POSSIBLE_WORKLOADS_WHEN_RUNNING: List[int] = np.arange(MIN_WORKLOAD, MAX_WORKLOAD + 1).tolist()


logger = logging.getLogger(__name__)


class HeatPump:
    """
    A class to allow building agents to convert electricity to heat.
    """

    @staticmethod
    def calculate_energy(workload: int, forward_temp_c: float = DEFAULT_FORWARD_TEMP,
                         brine_temp_c: float = DEFAULT_BRINE_TEMP, coeff_of_perf: float = DEFAULT_COP) -> \
            Tuple[float, float]:
        """
        Use simple linear models to calculate the electricity needed, and amount of heat produced, for a medium sized
        "Thermia" heat pump. See "simple_heat_pump_model.ipynb" in data-exploration project.
        Heat produced is then scaled using self.coeff_of_perf.

        @param workload: An integer describing the workload, or gear, of the heat pump. This being 0 corresponds to
            the heat pump not running at all, requiring no electricity and producing no heat.
        @param forward_temp_c: The setpoint in degrees Celsius. Models were fit using only 2 unique values; 35 and 55,
            so this preferably shouldn't deviate too far from those.
        @param brine_temp_c: The temperature of the brine fluid in degrees Celsius. Models were fit using only 3 unique
            values; -5, 0 and 5, so this preferably shouldn't deviate too far from those.
        @param coeff_of_perf: The coefficient of performance for the heat pump. Calculated as (heat output) divided by
            (elec input).

        @return A Tuple: First value being the amount of electricity needed to run the heat pump with the given
            settings, and the second value being the expected amount of heat produced by those settings. Units for both
            is kilowatt.
        """
        if workload == 0:
            return 0, 0

        # Convert workload to rpm
        rpm = map_workload_to_rpm(workload)

        # Calculate electricity needed, and heat output, for this setting
        predicted_elec = model_elec_needed(forward_temp_c, rpm)
        predicted_heat_normal_thermia = model_heat_output(forward_temp_c, rpm, brine_temp_c)

        predicted_heat = predicted_heat_normal_thermia * coeff_of_perf / DEFAULT_COP

        return predicted_elec, predicted_heat

    @staticmethod
    def calculate_for_all_workloads(forward_temp_c: float = DEFAULT_FORWARD_TEMP,
                                    brine_temp_c: float = DEFAULT_BRINE_TEMP, coeff_of_perf: float = DEFAULT_COP) -> \
            OrderedDict[int, Tuple[float, float]]:
        """
        Returns an ordered dictionary where workload are keys, in increasing order. The values are pairs of floats, the
        first one being electricity needed, and the second one heating produced.
        """
        # Want to evaluate all possible gears, and also to not run the heat pump at all
        workloads: List[int] = [0] + POSSIBLE_WORKLOADS_WHEN_RUNNING
        ordered_dict = OrderedDict()
        for workload in workloads:
            ordered_dict[workload] = HeatPump.calculate_energy(workload, forward_temp_c, brine_temp_c,
                                                               coeff_of_perf=coeff_of_perf)

        return ordered_dict
    
    @staticmethod
    def calculate_for_all_workloads_for_all_brine_temps(brine_temps: List[float],
                                                        forward_temp_c: float = DEFAULT_FORWARD_TEMP,
                                                        coeff_of_perf: float = DEFAULT_COP) -> \
            Dict[float, OrderedDict]:
        """
        Returns an ordered dictionary where workload are keys, in increasing order. The values are pairs of floats, the
        first one being electricity needed, and the second one heating produced.
        """
        dct = {}
        for brine_temp_c in brine_temps:
            dct[brine_temp_c] = HeatPump.calculate_for_all_workloads(forward_temp_c, brine_temp_c,
                                                                     coeff_of_perf=coeff_of_perf)

        return dct


class ValueOutOfRangeError(Exception):
    """
    Raised when an input is out of valid range.
    """
    pass


def model_elec_needed(forward_temp_c: float, rpm: float) -> float:
    """
    This method calculates the electricity needed (in kW) for running the heat pump at the given RPM and forward
    temperature.
    Background: All data we had were a sparse table, provided by the heat pump manufacturer (Thermia), of electricity
    needed for some different RPMs, forward temperatures, and brine temperatures. From this table, we constructed a
    simple regression model, so that we can calculate it for more values than just the ones in the table.
    This work is done in "simple_heat_pump_model.ipynb" in data-exploration project.

    @param forward_temp_c: A float describing the forward temperature in degrees Celsius. In the data used to fit this
        model we only had two unique values of this parameter: 35 and 55. Therefore this method will log a warning if
        this parameter is < 30 or > 60.
    @param rpm: A float describing the revolutions per minute. In the data used to fit this model, this parameter ranged
        between 1500 and 6000. Therefore this method will log a warning if this parameter is < 1000 or > 7000.

    @return An estimate of the electricity needed, in kW, to run the heat pump with the given settings
    """
    if forward_temp_c < 30 or forward_temp_c > 60:
        logger.warning("Heat pump electricity consumption model was fit with forward temperature values of 35 and 55, "
                       "but got {} as input!".format(forward_temp_c))
    if rpm < 1000 or rpm > 7000:
        logger.warning("Heat pump electricity consumption model was fit with RPM values from 1500 to 6000, "
                       "but got {} as input!".format(rpm))
    return ELEC_INTERCEPT_COEF + \
        ELEC_RPM_SQUARED_COEF * rpm * rpm + \
        ELEC_FORWARD_TEMP_COEF * forward_temp_c + \
        ELEC_FORWARD_TEMP_TIMES_RPM_COEF * forward_temp_c * rpm


def model_heat_output(forward_temp_c: float, rpm: float, brine_temp_c: float) -> float:
    """
    This method calculates the heat produced (in kW) when running the heat pump at the given RPM and forward
    temperature.
    Background: All data we had were a sparse table, provided by the heat pump manufacturer (Thermia), of heat produced
    when running the heat pump for some different RPMs, forward temperatures, and brine temperatures. From this table,
    we constructed a simple regression model, so that we can calculate it for more values than just the ones in the
    table. This work is done in "simple_heat_pump_model.ipynb" in data-exploration project.

    @param forward_temp_c: A float describing the forward temperature in degrees Celsius. In the data used to fit this
        model we only had two unique values of this parameter: 35 and 55. Therefore this method will log a warning if
        this parameter is < 30 or > 60.
    @param rpm: A float describing the revolutions per minute. In the data used to fit this model, this parameter ranged
        between 1500 and 6000. Therefore this method will log a warning if this parameter is < 1000 or > 7000.
    @param brine_temp_c: A float describing the brine fluid temperature in degrees Celsius. In the data used to fit this
        model we only had 3 unique values of this parameter: -5, 0 and 5. Therefore this method will log a warning if
        this parameter is < -10 or > 10.

    @return An estimate of the heat produced, in kW, to run the heat pump with the given settings
    """
    if forward_temp_c < 30 or forward_temp_c > 60:
        logger.warning("Heat pump electricity consumption model was fit with forward temperature values of 35 and 55, "
                       "but got {} as input!".format(forward_temp_c))
    if rpm < 1000 or rpm > 7000:
        logger.warning("Heat pump electricity consumption model was fit with RPM values from 1500 to 6000, "
                       "but got {} as input!".format(rpm))
    if brine_temp_c < -10 or brine_temp_c > 10:
        logger.warning("Heat pump electricity consumption model was fit with brine temperature values of -5, 0 and 5, "
                       "but got {} as input!".format(brine_temp_c))
    return HEAT_INTERCEPT_COEF + \
        HEAT_RPM_COEF * rpm + \
        HEAT_FORWARD_TEMP_TIMES_RPM_COEF * forward_temp_c * rpm + \
        HEAT_BRINE_TEMP_TIMES_RPM_COEF * brine_temp_c * rpm


def map_workload_to_rpm(workload: float, rpm_min: float = RPM_MIN, rpm_max: float = RPM_MAX) -> float:
    """
    Function to perform a linear mapping of an input workload into an output rpm.
    The workload refers to the "intensity-step"/gear - setting on which the heat-pump shall work. As such, it is
    expected to be in the range 1 - 10.
    """
    if workload < MIN_WORKLOAD or workload > MAX_WORKLOAD:
        raise ValueOutOfRangeError("Input workload is out of range [0:100]")
    # --- Define ranges
    workload_range = MAX_WORKLOAD - MIN_WORKLOAD
    rpm_range = rpm_max - rpm_min

    # --- Convert the workload range into a 0-1 range
    normalized_workload = (workload - MIN_WORKLOAD) / workload_range

    # --- Convert the normalized range into an rpm
    rpm = rpm_min + (normalized_workload * rpm_range)

    return rpm
