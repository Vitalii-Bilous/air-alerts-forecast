import pandas as pd, numpy as np, sys
v=pd.read_csv(sys.argv[1],parse_dates=['started_at','finished_at']); o=pd.read_csv(sys.argv[2],parse_dates=['started_at','finished_at'])
v['m']=v.started_at.dt.tz_convert(None).dt.to_period('M'); o['m']=o.started_at.dt.tz_convert(None).dt.to_period('M')
pd.set_option('display.width',300); pd.set_option('display.max_columns',40)
months=pd.period_range('2025-05','2026-09',freq='M')
t=v.pivot_table(index='region',columns='m',values='started_at',aggfunc='count').reindex(columns=months).fillna(0).astype(int)
t.columns=[str(c)[2:] for c in t.columns]
print("VOLUNTEER alerts per oblast per month"); print(t.to_string())
v['dur']=(v.finished_at-v.started_at).dt.total_seconds()/60
print("median duration (min) by month, all regions"); print(v[v.m.isin(months)].groupby('m').dur.median().round(1).to_string())
# start match rate with own-oblast official (any level), tol 3 min, per month
TOL=np.timedelta64(180,'s')
res={}
for (reg,m),g in v[v.m.isin(months[:-1])].groupby(['region','m']):
    os_=np.sort(o[(o.oblast==reg)&(o.m==m)].started_at.values)
    if len(os_)==0: res[(reg,str(m)[2:])]=np.nan; continue
    s=g.started_at.values; idx=np.clip(np.searchsorted(os_,s),1,len(os_)-1) if len(os_)>1 else np.zeros(len(s),int)
    d=np.minimum(np.abs(os_[idx]-s),np.abs(os_[np.maximum(idx-1,0)]-s))
    res[(reg,str(m)[2:])]=round((d<=TOL).mean(),2)
r=pd.Series(res).unstack()
print("Share of volunteer starts matching an official start in SAME oblast (±3 min)"); print(r.to_string())
