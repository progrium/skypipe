#
# All packages extending the dotcloud namespace must distribute their own
# dotcloud/__init__.py with this exact content.
#
# See http://www.python.org/dev/peps/pep-0382/
#

from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
