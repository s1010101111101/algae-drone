# California FHABS analysis

This repository contains a reproducible, event-level analysis of California's
Freshwater Harmful Algal Bloom System (FHABS) exports.  Run:

```powershell
python scripts/analyze_fhabs.py
```

Raw source data live under `data/raw/` and are excluded from Git because the
official files are mutable, sizable, and must retain their provenance.  Run
`python scripts/download_data.py` to refresh them; the command records URLs,
UTC retrieval times, byte counts, and SHA-256 checksums in `data/raw/sources.csv`.

## Analytical choices

* A distinct event is one `Bloom_Report_ID`; repeated export rows retain the
  latest source row and receive a duplicate-source-ID audit flag.
* The event date is `Observation_Date`; a missing observation date falls back
  to `Bloom_Date_Created` and is flagged.
* Map eligibility requires a plausible California latitude (32â€“43) and
  longitude (âˆ’125 to âˆ’114); exclusions are counted in the methods report.
* `waterbody_clean` uses the official waterbody name when supplied, otherwise
  the reported name.  It is not a geographic entity reconciliation.
* Satellite matching is intentionally a separate step: only a documented
  waterbody-name/geometry crosswalk and an observation window may be used.
  Satellite products are screening-level, provisional estimates, not advisory
  or toxin measurements.

## Sources and limitations

FHABS is voluntary reporting. Counts show reporting activity, not biological
incidence.  The source registry documents every download URL and timestamp.
The California/SFEI satellite API describes cyano-index and chlorophyll-a
zonal statistics for roughly 255 waterbodies; its 2002â€“2012 MERIS period has
known possible false positives. See `reports/inspection_and_methods.md`.

