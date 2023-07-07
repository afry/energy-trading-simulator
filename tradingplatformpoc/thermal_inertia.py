# TODO: Here we should implement thermal inertia as a virtual ackumulator tank

class ThermalInertia:
    """
    A class for allowing BuildingAgents to use heat stored in the structure of the house.
    """
    amount: float
    max_offset_above: float
    max_offset_below: float
    current_balance: float
    number_of_periods_with_offset: int
    max_allowed_number_of_periods_before_return: int

    def __init__(self, amount: float, max_offset_above: float, max_offset_below: float,
                 balance_to_start_with: float = 0.0, number_of_periods_with_offset: int = 0):
        self.amount = amount
        self.max_offset_above = max_offset_above
        self.max_offset_below = max_offset_below
        self.current_balance = balance_to_start_with
        self.number_of_periods_with_offset = number_of_periods_with_offset

    def take_out_heat(self):
        # TODO: Check amount allowed
        if self.number_of_periods_with_offset <= self.max_allowed_number_of_periods_before_return:
            self.current_balance -= self.amount

    def put_in_heat(self):
        # TODO: Check amount allowed
        self.current_balance += self.amount

    def trading_period_counter(self):
        if self.current_balance != 0.0:
            self.number_of_periods_with_offset += 1
        else:
            self.number_of_periods_with_offset = 0

    # TODO: Must return to zero sooner than X number of trading periods
    # Make sure not called more than once or twice a day
