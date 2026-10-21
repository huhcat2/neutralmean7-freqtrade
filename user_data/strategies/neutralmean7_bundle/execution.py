import numpy as np
import pandas as pd
from freqtrade.strategy import IStrategy

class BTCAdaptiveBase(IStrategy):
    INTERFACE_VERSION=3
    timeframe='1h'
    startup_candle_count=4801
    can_short=False
    process_only_new_candles=True
    minimal_roi={}
    stoploss=-.99
    trailing_stop=False
    use_exit_signal=False
    position_adjustment_enable=True
    max_entry_position_adjustment=-1
    order_types={'entry':'market','exit':'market','stoploss':'market','stoploss_on_exchange':False}
    params={'family':'carry'}
    information_lag_hours=1
    decision_hour=1
    schedule_name=None

    def populate_entry_trend(self,dataframe,metadata):
        # Schedule only. All market-state checks use lagged callback data.
        dataframe['enter_long']=dataframe.date.dt.hour.eq(self.decision_hour-1).astype(int)
        dataframe['enter_tag']='adaptive'
        return dataframe

    def populate_exit_trend(self,dataframe,metadata):
        dataframe['exit_long']=0
        return dataframe

    def _allowed(self,now):
        observed=getattr(self,'_observed_times',None)
        return now.minute==0 and now.second==0 and (observed is None or int(now.timestamp()) in observed)

    def _row(self,pair,now):
        frame,_=self.dp.get_analyzed_dataframe(pair,self.timeframe)
        cutoff=pd.Timestamp(now)-pd.Timedelta(hours=self.information_lag_hours)
        i=frame.closed_at.searchsorted(cutoff,side='right')-1
        if i<0: return None
        row=frame.iloc[i]
        return row if row.closed_at>=cutoff-pd.Timedelta(hours=1) else None

    def confirm_trade_entry(self,pair,order_type,amount,rate,time_in_force,current_time,entry_tag,side,**kwargs):
        if not self._allowed(current_time) or current_time.hour!=self.decision_hour: return False
        row=self._row(pair,current_time)
        return bool(row is not None and row.healthy and not row.cooldown and row.target>0)

    def custom_stake_amount(self,pair,current_time,current_rate,proposed_stake,min_stake,max_stake,leverage,entry_tag,side,**kwargs):
        if not self._allowed(current_time) or current_time.hour!=self.decision_hour: return 0.
        row=self._row(pair,current_time)
        if row is None or not row.healthy or row.cooldown or not np.isfinite(row.target): return 0.
        cash=self.wallets.get_free('USDT'); fee=float(self.config.get('fee',.0015))
        target=float(np.clip(row.target,0,.995))
        stake=min(target*cash/(1+target*fee),cash/(1+fee),max_stake)
        return stake if stake>=max(10.,min_stake or 0.) else 0.

    def adjust_trade_position(self,trade,current_time,current_rate,current_profit,min_stake,max_stake,**kwargs):
        if not self._allowed(current_time): return None
        if self.params['family']=='carry' and not self.schedule_name: return None
        row=self._row(trade.pair,current_time)
        if row is None or not row.healthy: return None
        if not row.cooldown and current_time.hour!=self.decision_hour: return None
        # This property scans all filled orders. Evaluate only at actionable
        # times, especially important for a persistent core position.
        if trade.date_last_filled_utc>=current_time: return None
        fee=float(self.config.get('fee',.0015))
        # Backtest wallet defers the remaining entry fee until realization. In
        # live this extra deduction is conservative, never implicit borrowing.
        cash=max(0.,self.wallets.get_free('USDT')-trade.stake_amount*fee)
        value=trade.amount*current_rate; capital=cash+value
        weight=value/capital
        goal=float(np.clip(row.target,0,.995))
        if not np.isfinite(goal): return None
        if row.cooldown: goal=min(goal,.25,weight)
        if abs(goal-weight)<.03 and goal>0: return None
        delta=goal*capital-value
        minimum=max(10.,min_stake or 0.)
        if delta>0:
            amount=min(delta/(1+goal*fee),cash/(1+fee),max_stake)
            return (amount,'inventory_add') if amount>=minimum else None
        if goal==0: return (-trade.stake_amount,'allocation_flat')
        amount=min(value,-delta/(1-goal*fee))
        qty=np.floor(amount/current_rate*1e5)/1e5
        if qty*current_rate<minimum or (trade.amount-qty)*current_rate<minimum: return None
        return (-trade.stake_amount*qty/trade.amount,'risk_reduce' if row.cooldown else 'inventory_reduce')
