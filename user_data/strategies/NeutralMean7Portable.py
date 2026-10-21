"""Standalone causal NeutralMean7 implementation for the bundled Freqtrade adapter."""
from pathlib import Path
import numpy as np
import pandas as pd
from neutralmean7_bundle.execution import BTCAdaptiveBase
from neutralmean7_bundle.kernel import targets


class NeutralMean7Portable(BTCAdaptiveBase):
    params={'family':'core'}

    def bot_start(self,**kwargs):
        self._observed_times=None
        self._asset_dir=Path(__file__).resolve().parent/'neutralmean7_bundle'/'assets'
        self._seed=pd.read_feather(self._asset_dir/'history_1h.feather')
        self._seed_end=self._seed.date.max()
        self._state_path=Path(self.config['user_data_dir'])/'neutralmean7_state'/'history_1h.feather'
        mode=str(getattr(self.config.get('runmode'),'value',self.config.get('runmode','')))
        self._write_state=mode in ['live','dry_run']
        if self._write_state and self._state_path.exists():
            self._seed=pd.concat([self._seed,pd.read_feather(self._state_path)]).drop_duplicates('date',keep='last').sort_values('date')
            self._seed_end=self._seed.date.max()

    def populate_indicators(self,dataframe,metadata):
        columns=['date','open','high','low','close','volume']
        asof=dataframe.date.max()+pd.Timedelta(hours=1)
        incoming=dataframe[columns].copy()
        if incoming.date.min()>self._seed_end+pd.Timedelta(hours=1):
            raise ValueError('NeutralMean7 history gap: backfill hourly candles or restore the persistent history before trading.')
        history=pd.concat([self._seed.loc[self._seed.date<asof,columns],incoming])
        history=history.drop_duplicates('date',keep='last').sort_values('date').reset_index(drop=True)
        schedule=targets(history,self._asset_dir/'model.json')
        schedule=schedule.rename_axis('available_at').reset_index(name='core_target')
        schedule['available_at']+=pd.Timedelta(days=1)
        d=dataframe.copy();d['closed_at']=d.date+pd.Timedelta(hours=1)
        schedule['available_at']=schedule.available_at.astype(d.closed_at.dtype)
        d=pd.merge_asof(d.sort_values('closed_at'),schedule.sort_values('available_at'),left_on='closed_at',right_on='available_at',direction='backward')
        d['core_available']=d.available_at;d['target']=d.core_target
        shock=d.close/d.close.shift(24)-1<=-.10
        d['cooldown']=shock.astype(int).rolling(72,min_periods=1).max().astype(bool)
        d['healthy']=d.volume.gt(0)
        if self._write_state:
            self._state_path.parent.mkdir(parents=True,exist_ok=True)
            temporary=self._state_path.with_suffix('.tmp.feather')
            history.reset_index(drop=True).to_feather(temporary);temporary.replace(self._state_path)
            self._seed=history;self._seed_end=history.date.max()
        return d

    def _row(self,pair,now):
        row=super()._row(pair,now)
        if row is None:return None
        row=row.copy();row['blocked_adds']=bool(row.cooldown);row['cooldown']=False
        return row

    def confirm_trade_entry(self,pair,order_type,amount,rate,time_in_force,current_time,entry_tag,side,**kwargs):
        row=self._row(pair,current_time)
        if row is None or row.blocked_adds:return False
        return super().confirm_trade_entry(pair,order_type,amount,rate,time_in_force,current_time,entry_tag,side,**kwargs)

    def custom_stake_amount(self,pair,current_time,current_rate,proposed_stake,min_stake,max_stake,leverage,entry_tag,side,**kwargs):
        row=self._row(pair,current_time)
        if row is None or row.blocked_adds:return 0.
        return super().custom_stake_amount(pair,current_time,current_rate,proposed_stake,min_stake,max_stake,leverage,entry_tag,side,**kwargs)

    def adjust_trade_position(self,trade,current_time,current_rate,current_profit,min_stake,max_stake,**kwargs):
        if not self._allowed(current_time) or current_time.hour!=self.decision_hour:return None
        row=self._row(trade.pair,current_time)
        if row is None:return None
        if row.blocked_adds:
            fee=float(self.config.get('fee',.0015))
            cash=max(0.,self.wallets.get_free('USDT')-trade.stake_amount*fee)
            value=trade.amount*current_rate;weight=value/(cash+value)
            if row.target>weight:return None
        return super().adjust_trade_position(trade,current_time,current_rate,current_profit,min_stake,max_stake,**kwargs)


class NeutralMean7PortableLag2(NeutralMean7Portable):
    information_lag_hours=2
    decision_hour=2
