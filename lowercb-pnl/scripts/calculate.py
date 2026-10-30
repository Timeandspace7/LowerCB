"""Decimal reference calculator; no network or account access."""
import json
import sys
from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING

def calculate(x):
    def num(k, default=None, positive=False):
        v = x.get(k, default)
        if v is None:
            return None
        v = D(str(v))
        if not v.is_finite() or v < 0 or (positive and v == 0):
            raise ValueError(k + ' must be finite and nonnegative (positive where required)')
        return v
    m=num('face',100,True); pb=num('buy_price',positive=True)
    s=num('stock_price',positive=True); k0=num('current_conversion_price',positive=True)
    k=num('assumed_conversion_price',positive=True)
    if None in (pb,s,k0,k):
        raise ValueError('buy_price, stock_price, current_conversion_price, assumed_conversion_price required')
    pm=num('market_bond_price'); q=num('quantity')
    if q is not None and q != q.to_integral_value():
        raise ValueError('quantity must be whole bonds')
    ps=num('stock_exit_price',s); bs=num('bond_exit_price',95)
    tick=num('tick', '0.01', True)
    keys=['buy_fee','bond_sell_fee','conversion_sell_fee','funding_cost','bond_interest','conversion_interest']
    fee={z:num(z) or D(0) for z in keys}
    v0=m*s/k0; v=m*s/k
    out={'current_value':v0,'current_market_premium':pm/v0-1 if pm is not None else None,
         'assumed_value':v,'cost_premium':pb/v-1,'scenario_premium':bs/v-1,
         'theoretical_stock_breakeven':pb*k/m,'unknown_fees':[z for z in keys[:4] if x.get(z) is None]}
    def sale(price):
        pnl=None if q is None else (D(0) if q==0 else q*(price-pb)-fee['buy_fee']-fee['bond_sell_fee']-fee['funding_cost']+fee['bond_interest'])
        cap=None if q is None else (D(0) if q==0 else q*pb+fee['buy_fee'])
        return {'price':price,'value':v,'premium':price/v-1,'per_bond_gross_pnl':price-pb,'pnl':pnl,'return':pnl/cap if cap else None}
    out['sales']=[sale(D(str(p))) for p in x.get('bond_prices',[85,90,93,95,100,110,120,145])]
    if any(not r['price'].is_finite() or r['price']<0 for r in out['sales']):
        raise ValueError('invalid scenario price')
    if q is None:
        out.update(capital=None, shares=None,residual=None,conversion_pnl=None,conversion_return=None,actual_stock_breakeven=None,bond_breakeven=None,stock_cases=[])
    else:
        n=(q*m/k).to_integral_value(rounding=ROUND_FLOOR); r=q*m-n*k
        cap=q*pb+fee['buy_fee'] if q else D(0)
        pnl=n*ps+r+fee['conversion_interest']-q*pb-fee['buy_fee']-fee['conversion_sell_fee']-fee['funding_cost'] if q else D(0)
        be=(q*pb+fee['buy_fee']+fee['conversion_sell_fee']+fee['funding_cost']-r-fee['conversion_interest'])/n if n else None
        out.update(capital=cap,shares=n,residual=r,conversion_pnl=pnl,conversion_return=pnl/cap if cap else None,actual_stock_breakeven=be,bond_breakeven=pb+(fee['buy_fee']+fee['bond_sell_fee']+fee['funding_cost']-fee['bond_interest'])/q if q else None)
        points=[] if be is None else [be-D('.10'),(be/tick).to_integral_value(rounding=ROUND_FLOOR)*tick,be,(be/tick).to_integral_value(rounding=ROUND_CEILING)*tick,be+D('.10')]
        out['stock_cases']=[{'price':p,'pnl':n*p+r+fee['conversion_interest']-q*pb-fee['buy_fee']-fee['conversion_sell_fee']-fee['funding_cost']} for p in sorted(set(points)) if p>=0]
    days=x.get('daily',[])
    out['averages']=None
    if days:
        if len(days)!=20 or len({d['date'] for d in days})!=20 or sorted(d['date'] for d in days)!=[d['date'] for d in days]:
            raise ValueError('daily must contain 20 unique dates in ascending order')
        for day in days:
            if D(str(day['shares']))<=0 or D(str(day['amount']))<0:
                raise ValueError('invalid daily turnover/volume')
        a=sum(D(str(d['amount'])) for d in days); vol=sum(D(str(d['shares'])) for d in days)
        prev=D(str(days[-1]['amount']))/D(str(days[-1]['shares']))
        out['averages']={'twenty':a/vol,'previous':prev,'two_average_reference':max(a/vol,prev),'note':'Only valid if issuer terms use these two averages; other floors need separate checks.'}
    return out

def self_test():
    x={'quantity':10,'buy_price':93,'stock_price':'11.40','current_conversion_price':'18.36','assumed_conversion_price':'12.84','bond_exit_price':95}
    y=calculate(x)
    assert abs(y['scenario_premium']-D('.07'))<D('1e-24')
    assert y['shares']==77 and y['residual']==D('11.32') and y['conversion_pnl']==D('-40.88')
    assert y['sales'][3]['pnl']==20
    assert calculate(dict(x,quantity=0,buy_fee=3))['conversion_pnl']==0
    assert calculate(dict(x,quantity=None))['capital'] is None
    assert calculate(dict(x,quantity=20,buy_fee=5))['capital']==1865
    assert calculate(dict(x,conversion_sell_fee=5))['conversion_pnl']==D('-45.88')
    assert calculate(dict(x,quantity=1,assumed_conversion_price=200))['actual_stock_breakeven'] is None
    assert calculate(dict(x,quantity=1284))['residual']==0
    days=[{'date':f'2026-01-{i:02}','amount':100+i,'shares':10} for i in range(1,21)]
    assert calculate(dict(x,daily=days))['averages']['twenty']==D('11.05')
    for change in [{'quantity':-1},{'quantity':1.5},{'assumed_conversion_price':0},{'daily':days[:19]}]:
        try: calculate(dict(x,**change))
        except ValueError: pass
        else: raise AssertionError(change)
    print('All reference and boundary checks passed.')

if __name__=='__main__':
    if sys.argv[1:] == ['--self-test']:
        self_test()
    else:
        with open(sys.argv[1],encoding='utf-8') as f: result=calculate(json.load(f))
        text=json.dumps(result,ensure_ascii=False,indent=2,default=lambda z:str(z) if isinstance(z,D) else z)
        if len(sys.argv)>2:
            with open(sys.argv[2],'w',encoding='utf-8') as f:f.write(text+'\n')
        else:print(text)
