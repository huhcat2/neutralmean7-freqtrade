import json
import numpy as np
import pandas as pd

def daily_data(hourly):
    d=hourly.set_index('date').resample('1D').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'})
    available=hourly.date.max()+pd.Timedelta(hours=1)
    d=d.loc[d.index+pd.Timedelta(days=1)<=available].copy()
    r=np.log(d.close/d.close.shift(1))
    d['vol']=np.maximum(r.rolling(20).std(),r.rolling(60).std())*np.sqrt(365)
    d['z']=((np.log(d.close/d.close.rolling(20).mean()))/(r.rolling(20).std()*np.sqrt(20)).clip(lower=.01)).clip(-2,2)
    change=d.close.diff()
    up=change.clip(lower=0).rolling(14).mean()
    down=(-change.clip(upper=0)).rolling(14).mean()
    d['rsi']=100-100/(1+up/down.replace(0,np.nan))
    d.loc[down.eq(0)&up.gt(0),'rsi']=100.
    for n in [48,60,96,120,144,180]: d[f'ma{n}']=d.close.rolling(n).mean()
    return d


def model_features(hourly):
    daily=daily_data(hourly)
    c=daily.close; r=np.log(c/c.shift(1)); v=r.rolling(20).std().clip(lower=.003)
    x=pd.DataFrame(index=daily.index)
    for n in [1,7,21,63,126]: x[f'momentum{n}']=np.log(c/c.shift(n))/(v*np.sqrt(n))
    for n in [20,60,200]: x[f'trend{n}']=np.log(c/c.rolling(n).mean())/(v*np.sqrt(n))
    x['rsi14']=(daily.rsi-50)/25
    ema12=c.ewm(span=12,adjust=False).mean(); ema26=c.ewm(span=26,adjust=False).mean()
    macd=ema12-ema26; signal=macd.ewm(span=9,adjust=False).mean()
    x['macd']=(macd-signal)/c/v
    x['bollinger']=(c-c.rolling(20).mean())/c.rolling(20).std()
    x['volatility20']=v*np.sqrt(365)
    x['downside_ratio']=r.clip(upper=0).pow(2).rolling(20).mean()/r.pow(2).rolling(20).mean()
    volume=np.log1p(daily.volume)
    x['volume_surprise']=(volume-volume.rolling(20).mean())/volume.rolling(20).std()
    true_range=pd.concat([daily.high-daily.low,(daily.high-c.shift(1)).abs(),(daily.low-c.shift(1)).abs()],axis=1).max(axis=1)
    x['atr14']=true_range.rolling(14).mean()/c/v
    x['range_position']=(c-daily.low.rolling(20).min())/(daily.high.rolling(20).max()-daily.low.rolling(20).min())
    x=x.replace([np.inf,-np.inf],np.nan).clip(-10,10)
    return daily,x

def predict(x,model_path):
    m=json.loads(model_path.read_text(encoding='utf-8'))
    a=x[m['features']].to_numpy(dtype=float)
    return ((a-np.array(m['mean']))/np.array(m['scale']))@np.array(m['coef'])+m['intercept']

def targets(hourly,model_path):
    d,x=model_features(hourly)
    mean=d.close.rolling(48).mean();event=pd.Series(np.nan,index=d.index)
    event.loc[d.close>mean*1.02]=1.;event.loc[d.close<mean*.98]=0.
    trend=event.ffill().fillna(0.).gt(0)
    p=pd.Series(np.nan,index=x.index)
    eligible=(x.index>=pd.Timestamp('2022-12-31',tz='UTC'))&x.notna().all(axis=1)
    if eligible.any():p.loc[eligible]=predict(x.loc[eligible],model_path)
    positive=p.rolling(7,min_periods=1).mean().gt(0)
    return (.25+.75*(trend|positive)).clip(0,.995).where(x.notna().all(axis=1),np.nan)
