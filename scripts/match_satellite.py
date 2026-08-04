"""Satellite-FHABS matching contract.

Input `data/raw/satellite/weekly_waterbody_observations.csv` must contain
waterbody_id, waterbody_name, week_start, cyano_mean, chlorophyll_mean.
Each row is a weekly aggregation of SFEI API daily zonal values, retaining
missing values rather than treating cloud/no-pixel observations as zero.
"""
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
events=pd.read_csv(ROOT/'data/derived/fhab_events_waterbody_date.csv',parse_dates=['environmental_date'])
sat=pd.read_csv(ROOT/'data/raw/satellite/weekly_waterbody_observations.csv',parse_dates=['week_start'])
events['waterbody_key']=events.waterbody_clean.str.lower().str.replace(r'[^a-z0-9]','',regex=True)
sat['waterbody_key']=sat.waterbody_name.str.lower().str.replace(r'[^a-z0-9]','',regex=True)
def match(days):
    x=events.merge(sat,on='waterbody_key',how='left',suffixes=('_event','_sat'))
    x['day_offset']=(x.week_start-x.environmental_date).abs().dt.days
    x=x[x.day_offset.le(days)].sort_values(['event_key','day_offset']).drop_duplicates('event_key')
    return pd.DataFrame({'window_days':[days],'matched_events':[x.event_key.nunique()],'event_total':[events.event_key.nunique()],
      'match_rate':[x.event_key.nunique()/events.event_key.nunique()], 'missing_cyano':[x.cyano_mean.isna().sum()], 'missing_chlorophyll':[x.chlorophyll_mean.isna().sum()]})
pd.concat([match(d) for d in (7,14,30)]).to_csv(ROOT/'data/derived/satellite_match_sensitivity.csv',index=False)

