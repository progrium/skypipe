"""
dotcloud.ui.colors - Pythonic wrapper around colorama

Usage:
    colors = Colors()

    # Format string inlining
    print '{c.green}->{c.reset} Hello world!'.format(c=colors)

    # Call
    print colors.blue('Hello world!')

    # Wrapper
    with colors.red:
        print 'Hello world'

"""

import sys
import colorama

colorama.init()


class Colors(object):
    def __init__(self, disable_colors=None):
        """ Initialize Colors

        disable_colors can be either:
            * True: Disable colors. Useful to disable colors dynamically
            * None: Automatic colors. Colors will be enabled unless stdin is
                    not a tty (for instance if piped to another program).
            * False: Force enable colors, even if not running on a pty.
        """
        self.disable_colors = disable_colors
        if self.disable_colors is None:
            self.disable_colors = False if sys.stdout.isatty() else True

    def __getattr__(self, color):
        if self.disable_colors:
            return Color(None)
        color = color.upper()
        if color in ['DIM', 'BRIGHT']:
            return getattr(colorama.Style, color.upper())
        if color == 'RESET':
            return colorama.Style.RESET_ALL
        return Color(color)


class Color(object):
    def __init__(self, color):
        self.color = self._lookup_color(color)

    def _lookup_color(self, color):
        """ Lookup color by name """
        if color is None:
            return None
        if not hasattr(colorama.Fore, color.upper()):
            raise KeyError('Unknown color "{0}"'.format(color))
        return getattr(colorama.Fore, color.upper())

    def __enter__(self):
        if self.color is not None:
            sys.stdout.write(self.color)

    def __exit__(self, type, value, traceback):
        if self.color is not None:
            sys.stdout.write(colorama.Style.RESET_ALL)

    def __str__(self):
        if self.color is None:
            return ''
        return self.color

    def __call__(self, text):
        if self.color is None:
            return text
        return '{color}{text}{reset}'.format(
            color=self.color,
            text=text,
            reset=colorama.Style.RESET_ALL
            )
