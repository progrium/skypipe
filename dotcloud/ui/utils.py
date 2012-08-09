from __future__ import unicode_literals
import sys

def get_columns_width(rows):
    width = {}
    for row in rows:
        for (idx, word) in enumerate(map(unicode, row)):
            width.setdefault(idx, 0)
            width[idx] = max(width[idx], len(word))
    return width

def pprint_table(rows):
    rows = list(rows)
    width = get_columns_width(rows)

    def print_separator():
        if not rows:
            return
        sys.stdout.write('+')
        for (idx, word) in enumerate(map(unicode, rows[0])):
            sys.stdout.write('-{sep}-+'.format(sep=('-' * width[idx])))
        print ''

    print_separator()
    for row_idx, row in enumerate(rows):
        sys.stdout.write('|')
        for (idx, word) in enumerate(map(unicode, row)):
            sys.stdout.write(' {word:{width}} |'.format(word=word, width=(width[idx]))),
        print ''
        if row_idx == 0:
            # We just printed the table header
            print_separator()
    print_separator()


def pprint_kv(items, separator=':', padding=2, offset=0, skip_empty=True):
    if not items:
        return
    width = max([len(item[0]) for item in items if item[1] or not skip_empty]) + padding
    for item in items:
        (key, value) = item
        if not value:
            continue
        if isinstance(value, list) or isinstance(value, tuple):
            print '{align}{0}:'.format(key, align=' ' * offset)
            pprint_kv(value, offset=offset + 2)
        else:
            print'{align}{key:{width}}{value}'.format(
                align=' ' * offset,
                key='{0}{1}'.format(key, separator),
                value=value,
                width=width)
