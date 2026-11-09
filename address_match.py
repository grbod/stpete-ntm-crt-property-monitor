"""Address normalization and matching for the St Pete property monitor.

Zillow changed from abbreviated ("37th ave n") to spelled-out ("37th avenue n")
addresses in Aug 2026, which silently broke substring matching. Both the CSV
addresses and the Zillow addresses now go through the same normalizer and are
compared by exact house number + street, so spelling differences cannot matter.
"""
import logging
import re
from collections import defaultdict

DIRECTIONS = {"n", "s", "e", "w", "ne", "nw", "se", "sw"}

# Canonical form is the abbreviation. Never expand.
WORD_MAP = {
    "avenue": "ave", "av": "ave", "street": "st", "road": "rd", "drive": "dr",
    "boulevard": "blvd", "lane": "ln", "place": "pl", "court": "ct",
    "terrace": "ter", "circle": "cir", "highway": "hwy", "parkway": "pkwy",
    "trail": "trl", "way": "way", "north": "n", "south": "s", "east": "e",
    "west": "w", "northeast": "ne", "northwest": "nw", "southeast": "se",
    "southwest": "sw", "doctor": "dr", "junior": "jr",
    "first": "1st", "second": "2nd", "third": "3rd", "fourth": "4th",
    "fifth": "5th", "sixth": "6th", "seventh": "7th", "eighth": "8th",
    "ninth": "9th", "tenth": "10th",
}

_UNIT_RE = re.compile(r"\b(unit|apt|apartment|ste|suite|lot|bldg)\b.*$|#.*$")
_NUM_RE = re.compile(r"^(\d+)(?:-(\d+))?$")


def _tokens(street):
    """Lowercase street part (before first comma) as canonical tokens."""
    s = street.split(",")[0].lower()
    s = _UNIT_RE.sub(" ", s)
    s = re.sub(r"[^a-z0-9/\- ]", " ", s)
    s = re.sub(r"\bmartin luther\b", "ml", s)
    return [WORD_MAP.get(t, t) for t in s.split()]


def parse(address):
    """Return (numbers, base_street, direction) or None if unparseable.

    numbers: list of house-number strings (ranges expanded, same parity).
    direction: trailing N/S/E/W/NE/... or None if the row has none.
    """
    toks = _tokens(address)
    if len(toks) < 2:
        return None
    m = _NUM_RE.match(toks[0])
    if not m:
        return None
    start, end = int(m.group(1)), m.group(2)
    rest = toks[1:]
    frac = ""
    if rest and rest[0] == "1/2":
        frac, rest = " 1/2", rest[1:]
    if not rest:
        return None
    if end is not None:
        end = int(end)
        if end < start or end - start > 400:
            nums = [str(start) + frac]
        else:
            nums = [str(n) + frac for n in range(start, end + 1, 2)]
    else:
        nums = [str(start) + frac]
    direction = rest[-1] if rest[-1] in DIRECTIONS and len(rest) > 1 else None
    base = " ".join(rest[:-1] if direction else rest)
    return nums, base, direction


def street_key(address):
    """Base street name only, for the 'street coverage' canary."""
    p = parse(address)
    return p[1] if p else None


class AddressIndex:
    """CSV addresses indexed by (house number, base street).

    Each entry keeps (direction, zone, raw). Rows with no direction match a
    listing in either direction. Duplicates are collapsed and logged.
    """

    def __init__(self, rows):
        """rows: iterable of (raw_address, zone_or_None)."""
        self._idx = defaultdict(list)
        self.streets = set()
        self.dropped = []
        seen = set()
        for raw, zone in rows:
            raw = (raw or "").strip()
            p = parse(raw)
            if not p:
                self.dropped.append(raw)
                continue
            nums, base, direction = p
            self.streets.add(base)
            for n in nums:
                k = (n, base, direction, zone)
                if k in seen:
                    continue
                seen.add(k)
                self._idx[(n, base)].append((direction, zone, raw))
        if self.dropped:
            logging.info(f"AddressIndex: {len(self.dropped)} unparseable CSV rows dropped, e.g. {self.dropped[:3]}")

    def lookup(self, address):
        """Return list of (zone, raw_csv_address) matching the listing."""
        p = parse(address)
        if not p:
            return []
        nums, base, direction = p
        out = []
        for n in nums[:1]:
            for d, zone, raw in self._idx.get((n, base), []):
                if d is None or direction is None or d == direction:
                    out.append((zone, raw))
        return out

    def street_known(self, address):
        b = street_key(address)
        return b in self.streets if b else False
