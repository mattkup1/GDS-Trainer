def pad(s, n: int) -> str:
    """Right-pad (left-justify) s to width n, ported from script.js's pad()."""
    s = str(s)
    return s + " " * max(0, n - len(s))
