"""Reproducible California FHABS event analysis.

Usage: python scripts/analyze_fhabs.py.  Outputs are deliberately CSV/SVG so
they can be read without proprietary tools.  Raw data are never modified.
"""
from __future__ import annotations
import json, math, re
from pathlib import Path
import pandas as pd
import numpy as np

ROOT=Path(__file__).resolve().parents[1]; RAW=ROOT/'data/raw/fhabs'; OUT=ROOT/'data/derived'; FIG=ROOT/'figures'; DOC=ROOT/'reports'
for x in (OUT,FIG,DOC): x.mkdir(parents=True,exist_ok=True)
files={p.stem.split('_2026')[0]:p for p in RAW.glob('*.csv')}
tables={k:pd.read_csv(v,low_memory=False) for k,v in files.items()}

def date_col(d, choices):
    for c in choices:
        if c in d: return pd.to_datetime(d[c],errors='coerce',utc=True).dt.date.astype('string')
    return pd.Series(pd.NA,index=d.index,dtype='string')
def norm(s): return s.fillna('').astype(str).str.lower().str.replace(r'[^a-z0-9]','',regex=True)
def svg_bar(series,path,title,xlabel):
    w,h,m=1100,520,70; vals=series.astype(float); vmax=max(vals.max(),1); bw=(w-2*m)/len(vals)
    bars=''.join(f'<rect x="{m+i*bw+2:.1f}" y="{h-m-v/vmax*(h-2*m):.1f}" width="{max(bw-4,1):.1f}" height="{v/vmax*(h-2*m):.1f}" fill="#157f8c"/><text x="{m+(i+.5)*bw:.1f}" y="{h-m+18}" font-size="10" text-anchor="middle">{str(k)}</text>' for i,(k,v) in enumerate(vals.items()))
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><style>text{{font-family:Arial;fill:#162b3a}}.t{{font-size:20px;font-weight:bold}}</style><text class="t" x="{m}" y="32">{title}</text><line x1="{m}" y1="{h-m}" x2="{w-m}" y2="{h-m}" stroke="#333"/>{bars}<text x="{m}" y="{h-12}" font-size="12">{xlabel}</text></svg>',encoding='utf8')

# Event grain: one source Bloom_Report_ID at observation date (created date only
# when observation date is unavailable); never collapse different report IDs.
b=tables['bloom-report'].copy(); b['environmental_date']=date_col(b,['Observation_Date','Bloom_Date_Created']); b['date_imputed']=b['Observation_Date'].isna()
b['waterbody_clean']=b['Official_Water_Body_Name'].fillna(b['Water_Body_Name']).astype('string').str.strip()
b['valid_coordinates']=b['Bloom_Latitude'].between(32,43)&b['Bloom_Longitude'].between(-125,-114)
b['event_key']='FHABS:'+b['Bloom_Report_ID'].astype('Int64').astype(str)
b['duplicate_source_id']=b.duplicated('Bloom_Report_ID',keep=False)
event=b.sort_values(['Bloom_Report_ID','Bloom_Date_Created']).drop_duplicates('Bloom_Report_ID',keep='last').copy()
event['year']=pd.to_datetime(event['environmental_date']).dt.year; event['month']=pd.to_datetime(event['environmental_date']).dt.month
event['season']=pd.Categorical(event['month'].map({12:'Winter',1:'Winter',2:'Winter',3:'Spring',4:'Spring',5:'Spring',6:'Summer',7:'Summer',8:'Summer',9:'Fall',10:'Fall',11:'Fall'}),categories=['Winter','Spring','Summer','Fall'],ordered=True)
event['quality_flags']=np.select([event['environmental_date'].isna(),event['date_imputed'],~event['valid_coordinates']],['missing_environmental_date','date_imputed_from_created','invalid_or_missing_coordinate'],'')
keep=['event_key','Bloom_Report_ID','Case_ID','Advisory_ID','environmental_date','date_imputed','waterbody_clean','Water_Body_Name','Official_Water_Body_Name','County','Bloom_Latitude','Bloom_Longitude','valid_coordinates','quality_flags','year','month','season','Case_Status','Advisory_Recommended','Lab_Data_Linked_to_Bloom','Field_Visual_Records_Linked_to_Bloom','Field_Measurement_Data_Linked_to_Bloom']
event[keep].to_csv(OUT/'fhab_events_waterbody_date.csv',index=False)

# Relationship audit: test source IDs against Bloom_Report_ID and Case_ID.
relations=[]
for child_name,child in tables.items():
  for key in ['Bloom_Report_ID','Case_ID','Advisory_ID']:
    if key in child and key in b:
      x=set(child[key].dropna()); y=set(b[key].dropna()); counts=child.groupby(key).size() if key in child else pd.Series()
      relations.append({'child_table':child_name,'key':key,'child_nonnull':len(x),'parent_nonnull':len(y),'matched_child_ids':len(x&y),'unmatched_child_ids':len(x-y),'max_child_rows_per_key':int(counts.max()) if len(counts) else 0,'relationship':'one-to-many if max_child_rows_per_key > 1 else one-to-one candidate'})
pd.DataFrame(relations).to_csv(OUT/'relationship_audit.csv',index=False)
(DOC/'relational_diagram.mmd').write_text('''erDiagram\n  BLOOM_REPORT ||--o{ CASE : Case_ID\n  BLOOM_REPORT ||--o{ RESPONSE : Bloom_Report_ID\n  BLOOM_REPORT ||--o{ RESULT : Bloom_Report_ID\n  CASE ||--o{ RESPONSE : Case_ID\n  CASE ||--o{ RESULT : Case_ID\n''')

# Descriptive outputs and inferential uniformity test (Pearson chi-square; p-value
# omitted without SciPy to avoid pretending a numerical approximation is exact).
annual=event.groupby('year').event_key.nunique(); monthly=event.groupby('month').event_key.nunique().reindex(range(1,13),fill_value=0); seasonal=event.groupby('season',observed=False).event_key.nunique()
active=event.groupby('year').waterbody_clean.nunique(); annual_summary=pd.DataFrame({'distinct_events':annual,'active_waterbodies':active}); annual_summary['events_per_active_waterbody']=annual_summary.distinct_events/annual_summary.active_waterbodies
annual_summary.to_csv(OUT/'annual_summary.csv'); monthly.to_csv(OUT/'monthly_counts.csv'); seasonal.to_csv(OUT/'seasonal_counts.csv')
chi=float(((monthly-monthly.mean())**2/monthly.mean()).sum()); (DOC/'uniformity_test.txt').write_text(f'Pearson chi-square against equal monthly event counts: {chi:.3f}; df=11. Interpret with caution: reports are voluntary and observations are not independent.\n')
svg_bar(annual,FIG/'annual_events.svg','Distinct FHABS events by environmental year','Year'); svg_bar(monthly,FIG/'monthly_events.svg','Distinct FHABS events by month','Month'); svg_bar(seasonal,FIG/'seasonal_events.svg','Distinct FHABS events by season','Season')

# County and recurrence.
county=event[event.valid_coordinates].groupby('County').agg(distinct_events=('event_key','nunique'),affected_waterbodies=('waterbody_clean','nunique')).sort_values('distinct_events',ascending=False); county.to_csv(OUT/'county_summary.csv')
rec=event.dropna(subset=['waterbody_clean','year']).groupby('waterbody_clean').agg(distinct_events=('event_key','nunique'),active_years=('year','nunique'),counties=('County',lambda x:'; '.join(sorted(set(x.dropna().astype(str)))))).reset_index(); rec['ge5_events']=rec.distinct_events>=5; rec['ge3_years']=rec.active_years>=3; rec['overlap']=rec.ge5_events&rec.ge3_years; rec.sort_values(['overlap','distinct_events','active_years'],ascending=False).to_csv(OUT/'recurrence_hotspots.csv',index=False)
pd.crosstab(rec.ge5_events,rec.ge3_years).to_csv(OUT/'recurrence_definition_overlap.csv')
exclusions={'total_distinct_events':len(event),'valid_coordinate_events':int(event.valid_coordinates.sum()),'excluded_coordinate_events':int((~event.valid_coordinates).sum()),'missing_environmental_date':int(event.environmental_date.isna().sum()),'duplicate_source_ids_before_deduplication':int(b.duplicate_source_id.sum())}

# Inspection report: explicit observed columns, first 10 rows, and missingness.
lines=['# FHABS file inspection','']
for name,d in tables.items():
  lines += [f'## {name}',f'- Rows Ã— columns: {d.shape[0]} Ã— {d.shape[1]}',f'- Columns: {", ".join(d.columns)}','- Missing values: '+', '.join(f'{c}={int(d[c].isna().sum())}' for c in d.columns),'','First 10 rows:','```csv',d.head(10).to_csv(index=False).strip(),'```','']
lines += ['## Coordinate exclusions','```json',json.dumps(exclusions,indent=2),'```','', '## Limitations','FHABS reports are voluntary; event counts measure reporting, not biological incidence. Coordinates are screened only for plausible California longitude/latitude bounds. An event is a distinct Bloom_Report_ID, and the environmental date is Observation_Date, falling back to Bloom_Date_Created with a flag.']
(DOC/'inspection_and_methods.md').write_text('\n'.join(lines),encoding='utf8')
print(json.dumps(exclusions,indent=2))

