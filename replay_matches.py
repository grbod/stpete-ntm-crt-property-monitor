"""Replay saved Zillow snapshots through the old and new matchers.

Read-only: sends nothing, calls no APIs. Usage:
    python replay_matches.py [glob]            # default all_property_data_20*.json
    python replay_matches.py --spelled         # also re-run with abbreviations spelled out
"""
import glob
import json
import re
import sys

import pandas as pd

from address_match import AddressIndex

EXCLUDED = {"NTM-1", "RC-1", "RC-2", "RC-3"}
SPELL = {"ave": "avenue", "st": "street", "rd": "road", "dr": "drive", "blvd": "boulevard",
         "ln": "lane", "pl": "place", "ct": "court", "n": "north", "s": "south", "e": "east", "w": "west"}


def spell_out(address):
    street, _, rest = address.partition(",")
    toks = [SPELL.get(t, t) if i > 0 else t for i, t in enumerate(street.split())]
    return " ".join(toks) + (("," + rest) if rest else "")


def load_listings(pattern):
    seen = {}
    for f in sorted(glob.glob(pattern)):
        try:
            data = json.load(open(f))
        except Exception:
            continue
        for e in data:
            a = (e.get("address") or "")
            if a:
                seen.setdefault(a.lower(), f[-15:-5])
    return seen


def main():
    spelled = "--spelled" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    listings = load_listings(args[0] if args else "all_property_data_20*.json")

    ntm_df = pd.read_csv("NTMaddresses.csv")
    ntm_old = ntm_df["Address"].str.lower().tolist()
    ntm_idx = AddressIndex((a, None) for a in ntm_df["Address"])

    hl_df = pd.read_csv("HealthOfficeAddresses.csv")
    hl_idx = AddressIndex(zip(hl_df["Address"], hl_df["Zone_Class"]))
    hl_old = {}
    for a, z in zip(hl_df["Address"].str.lower(), hl_df["Zone_Class"]):
        hl_old.setdefault(" ".join(a.split()[:3]), []).append(z)

    print(f"unique listings: {len(listings)}   (NTM rows indexed, unparseable dropped: {len(ntm_idx.dropped)};"
          f" Health dropped: {len(hl_idx.dropped)})")
    both = old_only = new_only = 0
    h_both = h_old = h_new = 0
    known = 0
    for addr in listings:
        test = spell_out(addr) if spelled else addr
        o = any(c in addr for c in ntm_old)
        n = bool(ntm_idx.lookup(test))
        if o and n: both += 1
        elif o: old_only += 1; print("  NTM OLD-ONLY:", addr, "<-", [c for c in ntm_old if c in addr][:2])
        elif n: new_only += 1; print("  NTM NEW-ONLY:", addr, "<-", ntm_idx.lookup(test)[:2])
        core = " ".join(addr.split(",")[0].split()[:3])
        ho = any(z not in EXCLUDED for z in hl_old.get(core, []))
        hn = any(z not in EXCLUDED for z, _ in hl_idx.lookup(test))
        if ho and hn: h_both += 1
        elif ho: h_old += 1; print("  HEALTH OLD-ONLY:", addr)
        elif hn: h_new += 1; print("  HEALTH NEW-ONLY:", addr, "<-", hl_idx.lookup(test)[:2])
        known += ntm_idx.street_known(test) or hl_idx.street_known(test)
    print(f"NTM    both={both} old_only={old_only} new_only={new_only}")
    print(f"HEALTH both={h_both} old_only={h_old} new_only={h_new}")
    print(f"street coverage (canary): {known}/{len(listings)} = {known / max(1, len(listings)):.0%}")


if __name__ == "__main__":
    main()
