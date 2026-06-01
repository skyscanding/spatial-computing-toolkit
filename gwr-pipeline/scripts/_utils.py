"""
Shared utilities for GWR pipeline scripts.
"""
import arcpy


def resolve_field(feature_class, preferred=None, fallback_keywords=None):
    """
    Resolve a field name in a feature class.

    Priority:
      1. If `preferred` is given and exists, use it.
      2. If `fallback_keywords` given, search existing fields for a case-insensitive match.
      3. Raise ValueError with a list of available fields.

    Parameters
    ----------
    feature_class : str     Path to an existing feature class or layer.
    preferred : str | None  Explicit field name to try first.
    fallback_keywords : list[str] | None
        Substrings to match against actual field names (case-insensitive).

    Returns
    -------
    str  The resolved field name.

    Raises
    ------
    ValueError  If the field cannot be resolved.
    """
    existing = {f.name for f in arcpy.ListFields(feature_class)}

    if preferred and preferred in existing:
        return preferred

    if fallback_keywords:
        for fld in existing:
            low = fld.lower()
            for kw in fallback_keywords:
                if kw.lower() in low:
                    return fld

    avail = ", ".join(sorted(existing)[:30])
    wanted = preferred or (fallback_keywords or ["<none>"])
    raise ValueError(
        f"Cannot find field in '{feature_class}'.\n"
        f"  Wanted: {wanted}\n"
        f"  Available: {avail}"
    )


def with_default(value, fallback):
    """Return value if not None/empty, else fallback."""
    return value if value else fallback
