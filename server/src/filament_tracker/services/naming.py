"""Product names: the default name and the catalog name (see GLOSSARY.md).

Scans, the AMS and making a product from a catalog color all name products here, so the
two forms are defined once.
"""

# Product.display_name is a String(100).
NAME_LENGTH = 100


def default_name(kind: str, color_rgba: str) -> str:
    """A product's name when first seen on a tag or in the AMS: its material, then ` #` and
    the first six hex digits of its color, such as PLA Basic #FF0000."""
    return f"{kind} #{color_rgba[:6]}"


def is_default_name(name: str, color_rgba: str) -> bool:
    """Whether `name` is the default name for a product of this color: it ends with ` #` and
    the color's first six hex digits, compared without regard to case. A typed name that
    happens to end that way counts."""
    return name.casefold().endswith(f" #{color_rgba[:6]}".casefold())


def catalog_name(color_name: str, line_name: str) -> str:
    """A catalog color's name, a space, then its filament line's name, such as Hot Pink PLA
    Basic, cut to fit a product's name."""
    return f"{color_name} {line_name}"[:NAME_LENGTH]
