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

    Given the forecasted efficiency, the BuildingAgent should optimise the mix of heat pump/district heat with respect to total cost,
    where the cost may or may not be adjusted for carbon intensity.

    The function for calculating pump efficiency based on gear and desired temperature can be based on the work in the Decision maker project
    """