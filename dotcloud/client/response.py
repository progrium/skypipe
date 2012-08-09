import json
import httplib  # only for exception

def bytes_to_lines(stream):
    """Reads single bytes from stream, emits lines.
    
       This hack makes me sick, but requests makes this impossible
       to do reliably, otherwise."""
    line = ""
    for byte in stream:
        line += byte
        if line.endswith("\r\n"):
            yield line
            line = ""

class BaseResponse(object):
    def __init__(self, obj=None):
        self.obj = obj

    @classmethod
    def create(cls, res=None, trace_id=None, streaming=False):
        resp = None

        if streaming:
            stream = bytes_to_lines(res.iter_content(chunk_size=1))
            first_line = next(stream)
            data = json.loads(first_line)
        else:
            if res.text:
                data = json.loads(res.text)
            else:
                data = None
        if streaming:
            resp = StreamingJsonObjectResponse(obj=data['object'], stream=stream)
        elif data and 'object' in data:
            resp = ItemResponse(obj=data['object'])
        elif data and 'objects' in data:
            resp = ListResponse(obj=data['objects'])
        else:
            resp = NoItemResponse(obj=None)
        resp.trace_id = trace_id
        resp.res = res
        resp.data = data
        return resp

    def find_link(self, rel):
        for link in self.data.get('links', []):
            if link.get('rel') == rel:
                return link
        return None

class ListResponse(BaseResponse):
    @property
    def items(self):
        return self.obj

    @property
    def item(self):
        return self.obj[0]

class ItemResponse(BaseResponse):
    @property
    def items(self):
        return [self.obj]

    @property
    def item(self):
        return self.obj

class NoItemResponse(BaseResponse):
    @property
    def items(self):
        return None

    @property
    def item(self):
        return None

class StreamingJsonObjectResponse(BaseResponse):
    def __init__(self, obj, stream):
        BaseResponse.__init__(self, obj)
        self._stream = stream

    @property
    def items(self):
        def stream():
            try:
                for line in self._stream:
                    line = line.rstrip()
                    if line:  # ignore empty lines (keep-alive)
                        yield json.loads(line)['object']
            except httplib.HTTPException:
                pass  # simply ignore when the connection is dropped
        return stream()

    @property
    def item(self):
        return self.obj
