import logging
import threading

logger = logging.getLogger(__name__)


def get_running_threads():
    return [thread for thread in threading.enumerate() if (('run_' in thread.name) and (thread.is_alive()))]


# https://stackoverflow.com/questions/27102881/python-threading-self-stop-event-object-is-not-callable
class StoppableThread(threading.Thread):
    """Thread class with a stop() method. The thread itself has to check
    regularly for the stopped() condition."""

    def __init__(self, *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stopper = threading.Event()

    def stop_it(self):
        logger.info('Stopping thread.')
        self._stopper.set()

    def is_stopped(self):
        return self._stopper.is_set()
