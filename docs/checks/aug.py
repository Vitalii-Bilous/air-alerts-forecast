import pandas as pd, numpy as np, sys
o=pd.read_csv(sys.argv[1],parse_dates=['started_at','finished_at']); v=pd.read_csv(sys.argv[2],parse_dates=['started_at','finished_at'])
a,b=pd.Timestamp('2026-08-01',tz='UTC'),pd.Timestamp('2026-09-01',tz='UTC')
o=o[(o.started_at>=a)&(o.started_at<b)]; v=v[(v.started_at>=a)&(v.started_at<b)].rename(columns={'region':'oblast'})
print("Aug official by level:",o.level.value_counts().to_dict(),"volunteer:",len(v),"naive:",v.naive.sum())
TOL=pd.Timedelta(minutes=3)
rows=[]
def minutes_mask(df):
    m=np.zeros(31*24*60,bool)
    for s,f in zip(df.started_at,df.finished_at):
        i=int((s-a).total_seconds()//60); j=int(min((f-a).total_seconds()//60,len(m)))
        m[i:max(j,i+1)]=True
    return m
vm_all=[];om_all=[]
for ob,vg in v.groupby('oblast'):
    og=o[o.oblast==ob]
    os_=og.started_at.values
    # volunteer start matched to any official start within tol
    d=np.array([np.min(np.abs(os_-s)) if len(os_) else np.timedelta64(10**9,'s') for s in vg.started_at.values])
    vmatch=(d<=TOL.to_timedelta64()).mean()
    # which level is the nearest official start
    lv=[og.level.values[np.argmin(np.abs(os_-s))] if len(os_) else None for s in vg.started_at.values]
    vs=vg.started_at.values
    od=np.array([np.min(np.abs(vs-s)) for s in os_]) if len(os_) else np.array([])
    ocov=(od<=TOL.to_timedelta64()).mean() if len(od) else np.nan
    # overlap: official alert overlaps any volunteer interval
    vm=minutes_mask(vg); om=minutes_mask(og)
    jac=(vm&om).sum()/max((vm|om).sum(),1)
    # volunteer self-overlap
    vv=vg.sort_values('started_at'); selfov=(vv.started_at.values[1:]<vv.finished_at.values[:-1]).sum()
    rows.append(dict(oblast=ob,vol=len(vg),off=len(og),off_oblastlvl=(og.level=='oblast').sum(),
        vol_start_matched=round(vmatch,2),off_start_covered=round(ocov,2),
        vol_min=int(vm.sum()),off_union_min=int(om.sum()),min_jaccard=round(jac,2),
        vol_minutes_inside_off=round((vm&om).sum()/max(vm.sum(),1),2),vol_self_overlaps=selfov,
        nearest_lvl=pd.Series(lv).value_counts().to_dict()))
r=pd.DataFrame(rows).sort_values('vol',ascending=False)
pd.set_option('display.width',250); pd.set_option('display.max_columns',20)
print(r.to_string(index=False))
t=r[['vol','off']].sum(); print("totals",t.to_dict())
print("weighted vol_start_matched",(r.vol*r.vol_start_matched).sum()/r.vol.sum())
print("weighted min_jaccard",(r.vol_min*r.min_jaccard).sum()/r.vol_min.sum())
