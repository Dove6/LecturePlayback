import re

_SLIDE_PATTERN = re.compile(r'slide:(null|\d+)@(?:(?:(\d+)\:)?(\d{1,2})\:)?(\d{1,2})(?:\.(\d{1,3}))?')

def _parse_slide(line):
    if (match := _SLIDE_PATTERN.fullmatch(line)) is not None:
        page_num = match.group(1)
        page_num = int(page_num) if page_num != 'null' else None
        time_elems = dict(zip(
            ('hours', 'minutes', 'seconds', 'milliseconds'),
            map(
                lambda x: int(x) if x is not None else 0,
                match.group(2, 3, 4, 5)
            )
        ))
        time_elems['milliseconds'] = int(f'{time_elems["milliseconds"]}00'[:3])  # special case: trailing zeroes may be ommited
        time_ms = time_elems['milliseconds'] \
            + time_elems['seconds'] * 1000 \
            + time_elems['minutes'] * 60 * 1000 \
            + time_elems['hours'] * 60 * 60 * 1000
        return {
            'timestamp': time_ms,
            'pagenumber': page_num
        }
    else:
        raise Exception('Invalid description line format!')

def _parse_pointer(line):
    pass

def parse(filename):
    description = {
        'slide': [],
        'pointer': [],
    }
    with open(filename) as desc:
        for line in desc:
            line = ''.join(line.split())  # remove all whitespaces
            if line.find('slide') == 0:
                description['slide'].append(_parse_slide(line))
            elif line.find('pointer') == 0:
                description['pointer'].append(_parse_pointer(line))
            elif len(line) == 0:
                pass
            else:
                raise Exception('Invalid description format!')
    description['slide'] = sorted(description['slide'], key=lambda x: x['timestamp'])
    description['pointer'] = sorted(description['pointer'], key=lambda x: x['timestamp'])
    return description
