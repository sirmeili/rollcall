"""How different two colors look: CIEDE2000 in CIELAB, from sRGB under D65.

Pure functions with no dependency, following Sharma, Wu and Dalal (2005), "The CIEDE2000
color-difference formula: implementation notes, supplementary test data, and mathematical
observations". As a rough guide, a ΔE below 2 is barely visible, 2 to 10 is close and above
25 is clearly different.
"""

import math

Lab = tuple[float, float, float]

# The D65 white point (2° observer), as XYZ with Y = 1.
_WHITE = (0.95047, 1.0, 1.08883)
_EPSILON = 216 / 24389
_KAPPA = 24389 / 27
_POW25_7 = 25.0**7


def _linear(channel: int) -> float:
    """An sRGB channel (0-255) without its gamma."""
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _f(t: float) -> float:
    return t ** (1 / 3) if t > _EPSILON else (_KAPPA * t + 16) / 116


def hex_to_lab(hex_color: str) -> Lab:
    """CIELAB for an sRGB color written RRGGBB (a leading # and a trailing alpha are
    ignored)."""
    text = hex_color.removeprefix("#")
    r, g, b = (_linear(int(text[i : i + 2], 16)) for i in (0, 2, 4))
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    fx, fy, fz = (_f(v / w) for v, w in zip((x, y, z), _WHITE, strict=True))
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def _hue(b: float, a: float) -> float:
    """The hue angle in degrees, 0 to 360; 0 for a neutral color."""
    if a == 0 and b == 0:
        return 0.0
    return math.degrees(math.atan2(b, a)) % 360


def ciede2000(lab1: Lab, lab2: Lab) -> float:
    """ΔE00 between two CIELAB colors, with kL = kC = kH = 1."""
    l1, a1, b1 = lab1
    l2, a2, b2 = lab2

    c_bar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_bar**7 / (c_bar**7 + _POW25_7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p, h2p = _hue(b1, a1p), _hue(b2, a2p)

    dlp = l2 - l1
    dcp = c2p - c1p
    if c1p * c2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    d_hp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp / 2))

    lp_bar = (l1 + l2) / 2
    cp_bar = (c1p + c2p) / 2
    if c1p * c2p == 0:
        hp_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hp_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hp_bar = (h1p + h2p + 360) / 2
    else:
        hp_bar = (h1p + h2p - 360) / 2

    t = (
        1
        - 0.17 * math.cos(math.radians(hp_bar - 30))
        + 0.24 * math.cos(math.radians(2 * hp_bar))
        + 0.32 * math.cos(math.radians(3 * hp_bar + 6))
        - 0.20 * math.cos(math.radians(4 * hp_bar - 63))
    )
    d_theta = 30 * math.exp(-(((hp_bar - 275) / 25) ** 2))
    r_c = 2 * math.sqrt(cp_bar**7 / (cp_bar**7 + _POW25_7))
    s_l = 1 + 0.015 * (lp_bar - 50) ** 2 / math.sqrt(20 + (lp_bar - 50) ** 2)
    s_c = 1 + 0.045 * cp_bar
    s_h = 1 + 0.015 * cp_bar * t
    r_t = -math.sin(math.radians(2 * d_theta)) * r_c

    dl, dc, dh = dlp / s_l, dcp / s_c, d_hp / s_h
    return math.sqrt(dl**2 + dc**2 + dh**2 + r_t * dc * dh)
