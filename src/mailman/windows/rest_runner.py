
import logging

from mailman.config import config
from wsgiref.simple_server import make_server


log = logging.getLogger('mailman.process2')



class RestRunner:
    """Stoppable REST API server runner using wsgiref.

    Follows the same ``run()`` / ``stop()`` interface as the Mailman
    runner classes so it can be started in a daemon thread alongside
    LMTPRunner, TaskRunner, etc.
    """

    def __init__(self, name):
        self.name = name
        self._httpd = None

    def run(self):
        """Serve the REST WSGI app until stop() is called."""
        # Deferred to avoid circular import: wsgiapp -> ... -> helpers -> services
        from mailman.rest.wsgiapp import make_application
        host = config.webservice.hostname
        port = int(config.webservice.port)
        self._httpd = make_server(host, port, make_application())
        log.debug('REST server starting on %s:%s (wsgiref)', host, port)
        self._httpd.serve_forever()

    def stop(self):
        """Shut down the REST server."""
        if self._httpd is not None:
            self._httpd.shutdown()

