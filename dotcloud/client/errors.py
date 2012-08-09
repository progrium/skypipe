class RESTAPIError(Exception):
    def __init__(self, code=None, desc=None, trace_id=None):
        self.code = code
        self.desc = desc
        self.trace_id = trace_id

    def __str__(self):
        return self.desc

class AuthenticationNotConfigured(Exception):
    pass
