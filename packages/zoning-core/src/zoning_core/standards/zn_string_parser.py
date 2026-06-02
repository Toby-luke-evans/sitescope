"""Parse Toronto zoning label strings (zn_string) into structured components.

Toronto zone labels encode parameters directly in the label string:
  "CR 3.0 (c2.0; r2.5) SS2"   → CR zone, d=3.0, c=2.0, r=2.5, SS2
  "R (d0.6)(x12) (f6.0)(a185)" → R zone, d=0.6, f=6.0, a=185
  "RA (d2.5)"                   → RA zone, d=2.5
  "RM (d1.0)(x16)(f12.0)(a185)(au100)" → RM zone, d=1.0, f=12.0, a=185, au=100

Parameter key reference:
  d  = maximum FSI (density)
  f  = minimum lot frontage (m)
  a  = minimum lot area (sqm)
  au = minimum lot area per dwelling unit (sqm)
  u  = maximum number of dwelling units
  c  = maximum commercial/non-residential FSI (CR zones)
  r  = maximum residential FSI (CR zones)
  SS = Development Standard Set (1, 2, or 3 for CR zones)
"""

import re
from dataclasses import dataclass


@dataclass
class ZnStringParsed:
    """Parsed components from a Toronto zoning label string."""

    zone_code: str
    d: float | None = None      # max FSI (density)
    f: float | None = None      # min lot frontage (m)
    a: float | None = None      # min lot area (sqm)
    au: float | None = None     # min lot area per dwelling unit (sqm)
    u: int | None = None        # max dwelling units
    c: float | None = None      # max commercial FSI (CR zones)
    r: float | None = None      # max residential FSI (CR zones)
    ss: int = 0                 # development standard set (0 = N/A)


# ── Regex patterns ──────────────────────────────────────────────

# Development Standard Set: "SS1", "SS2", "SS3" at end of string
_RE_SS = re.compile(r"SS(\d)\s*$")

# CR-style split FSI in parentheses: "(c2.0; r2.5)"
_RE_CR_SPLIT = re.compile(r"\(c([\d.]+)\s*;\s*r([\d.]+)\)")

# CR-style bare FSI after zone code: "CR 3.0 ..." or "CR-T 5.0 ..."
_RE_CR_BARE_FSI = re.compile(r"^(?:CR(?:-T|E)?)\s+([\d.]+)")

# Individual label parameters: "(d0.6)", "(f6.0)", "(a185)", "(au100)", "(u5)"
# NOTE: "au" must be matched before "a" to avoid "au100" matching as "a" = "u100"
_RE_AU = re.compile(r"\(au([\d.]+)\)")
_RE_D = re.compile(r"\(d([\d.]+)\)")
_RE_F = re.compile(r"\(f([\d.]+)\)")
_RE_A = re.compile(r"\(a([\d.]+)\)")      # Only matches after au is extracted
_RE_U = re.compile(r"\(u(\d+)\)")

# Zone code: leading word(s) before first parenthesis or digit pattern
# Handles: R, RD, RS, RT, RM, RA, RAC, CR, CRE, CR-T, E, EL, EO, I, IH, IE, OS, ON, OR, OG, UT, CL
_RE_ZONE_CODE = re.compile(r"^([A-Z]{1,3}(?:-[A-Z])?)")


def parse_zn_string(zn_string: str | None) -> ZnStringParsed | None:
    """Parse a Toronto zoning label string into structured components.

    Args:
        zn_string: Raw zoning label from CKAN, e.g. "CR 3.0 (c2.0; r2.5) SS2"

    Returns:
        ZnStringParsed with extracted values, or None if input is empty/None.
    """
    if not zn_string or not zn_string.strip():
        return None

    s = zn_string.strip()

    # Extract zone code
    m = _RE_ZONE_CODE.match(s)
    zone_code = m.group(1) if m else s.split()[0] if s else "R"

    result = ZnStringParsed(zone_code=zone_code)

    # Extract Development Standard Set
    m = _RE_SS.search(s)
    if m:
        result.ss = int(m.group(1))

    # Extract CR-style split FSI: (c2.0; r2.5)
    m = _RE_CR_SPLIT.search(s)
    if m:
        result.c = float(m.group(1))
        result.r = float(m.group(2))

    # Extract CR-style bare FSI: "CR 3.0" (total FSI before parentheses)
    m = _RE_CR_BARE_FSI.match(s)
    if m:
        result.d = float(m.group(1))

    # Extract parenthesized label values — order matters: au before a
    m = _RE_AU.search(s)
    if m:
        result.au = float(m.group(1))

    m = _RE_D.search(s)
    if m:
        result.d = float(m.group(1))  # Overrides bare FSI if both present

    m = _RE_F.search(s)
    if m:
        result.f = float(m.group(1))

    # For "a" we need to avoid matching "au" — search on string with "au" removed
    s_no_au = _RE_AU.sub("", s)
    m = _RE_A.search(s_no_au)
    if m:
        result.a = float(m.group(1))

    m = _RE_U.search(s)
    if m:
        result.u = int(m.group(1))

    return result
