import logging

logger = logging.getLogger(__name__)


class Progress:
    def __init__(self):
        self.frac_complete = 0.0

    def get_process(self):
        return self.frac_complete

    def increase(self, increase_by: float):
        """
        Increases the progress bar, and returns its current value.
        """
        # Capping at 0.0 and 1.0 to avoid StreamlitAPIException
        self.frac_complete = min(1.0, max(0.0, self.frac_complete + increase_by))

    def final(self):
        self.frac_complete = 1.0

    def display(self):
        frac_complete = self.get_process()
        logger.info('Approx. frac complete {}'.format(frac_complete))
