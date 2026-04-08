import re

def natural_sort_key(s):
    """
    Key function for natural sorting of strings containing numbers.
    e.g., sort ["Part1", "Part2", "Part10"] correctly instead of ["Part1", "Part10", "Part2"]
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]
