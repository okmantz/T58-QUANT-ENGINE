//+------------------------------------------------------------------+
//| T58 Fisherman EA (twin: ES1! Fisherman Retracement 15m.py)       |
//| Trend filter (MA, optional RSI) defines direction; entry when    |
//| price has retraced a % of price against that trend within the    |
//| last N bars. %-based SL/TP, optional close time, BE + trailing.  |
//| UNCOMPILED: written from the input spec PDF - compile and test.  |
//+------------------------------------------------------------------+
#property copyright "T58 Trading"
#property version   "1.00"
#property strict
//============================================================================
// SHARED HELPERS (identical in every T58 EA file so each file is self-contained)
//============================================================================
#include <Trade\Trade.mqh>
CTrade trade;

enum ENUM_VOLUME_MODE { VOLUME_FIXED, VOLUME_MANAGED, VOLUME_PERCENT, VOLUME_MONEY };
enum ENUM_CALC_MODE   { CALC_MODE_OFF, CALC_MODE_PERCENT, CALC_MODE_POINTS, CALC_MODE_FACTOR };

// distance in PRICE units for a TP/SL/BE/TSL setting. price = reference price (open), rangeSize only used by FACTOR.
double CalcDistance(ENUM_CALC_MODE mode, double value, double price, double rangeSize = 0.0)
  {
   if(value <= 0.0)
      return 0.0;
   switch(mode)
     {
      case CALC_MODE_PERCENT: return price * value / 100.0;
      case CALC_MODE_POINTS:  return value * _Point;
      case CALC_MODE_FACTOR:  return rangeSize * value;
      default:                return 0.0;
     }
  }

// round DOWN to the broker's volume step; returns 0 if the result would be below the broker's minimum (trade is skipped, never oversized)
double NormalizeVolume(double lots)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double mn   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mx   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0.0)
      return 0.0;
   lots = MathFloor(lots / step + 1e-8) * step;
   if(lots > mx)
      lots = mx;
   if(lots < mn)
      return 0.0;
   int digits = 0;
   for(double s = step; s < 1.0 - 1e-9 && digits < 8; s *= 10.0)
      digits++;
   return NormalizeDouble(lots, digits);
  }

// account-currency loss for ONE lot if price moves `dist` against the position
double MoneyPerLot(double dist)
  {
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0.0 || ts <= 0.0)
      return 0.0;
   return dist / ts * tv;
  }

double VolumeForRiskMoney(double riskMoney, double slDist)
  {
   double perLot = MoneyPerLot(slDist);
   if(perLot <= 0.0 || riskMoney <= 0.0)
      return 0.0;
   return NormalizeVolume(riskMoney / perLot);
  }

double CalcVolume(ENUM_VOLUME_MODE mode, double fixedLots, double perMoney, double riskPct, double riskMoney, double slDist, double baseMoney = 0.0)
  {
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   switch(mode)
     {
      case VOLUME_FIXED:
         return NormalizeVolume(fixedLots);
      case VOLUME_MANAGED:
        {
         double units = (perMoney > 0.0) ? MathFloor(bal / perMoney) : 1.0;
         if(units < 1.0)
            units = 1.0;
         return NormalizeVolume(fixedLots * units);
        }
      case VOLUME_PERCENT:
        {
         double base = (baseMoney > 0.0) ? baseMoney : bal;
         return VolumeForRiskMoney(base * riskPct / 100.0, slDist);
        }
      case VOLUME_MONEY:
         return VolumeForRiskMoney(riskMoney, slDist);
     }
   return 0.0;
  }

bool IsNewBar(ENUM_TIMEFRAMES tf, datetime &lastBar)
  {
   datetime t = iTime(_Symbol, tf, 0);
   if(t == 0 || t == lastBar)
      return false;
   lastBar = t;
   return true;
  }

int CountMyPositions(long magic, long typeFilter = -1)
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != magic)
         continue;
      if(typeFilter >= 0 && PositionGetInteger(POSITION_TYPE) != typeFilter)
         continue;
      n++;
     }
   return n;
  }

void CloseMyPositions(long magic)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != magic)
         continue;
      if(!trade.PositionClose(tk))
         PrintFormat("T58: close failed ticket %I64u retcode=%d (%s)", tk, trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
  }

void DeleteMyOrders(long magic)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk == 0 || OrderGetString(ORDER_SYMBOL) != _Symbol || OrderGetInteger(ORDER_MAGIC) != magic)
         continue;
      trade.OrderDelete(tk);
     }
  }

// break-even then trailing stop for this EA's positions. Distances come from CalcDistance (percent of OPEN price or points).
void ManageStops(long magic,
                 ENUM_CALC_MODE beMode, double beTrigger, double beBuffer,
                 ENUM_CALC_MODE tslMode, double tslTrigger, double tslValue, double tslStep)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != magic)
         continue;
      long   type = PositionGetInteger(POSITION_TYPE);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double profit = (type == POSITION_TYPE_BUY) ? (bid - open) : (open - ask);
      double newSL = sl;
      bool   modify = false;

      if(beMode != CALC_MODE_OFF && beTrigger > 0.0)
        {
         double trig = CalcDistance(beMode, beTrigger, open);
         double buf  = CalcDistance(beMode, beBuffer, open);
         if(profit > trig)
           {
            double cand = (type == POSITION_TYPE_BUY) ? open + buf : open - buf;
            if(type == POSITION_TYPE_BUY && (sl == 0.0 || cand > newSL)) { newSL = cand; modify = true; }
            if(type == POSITION_TYPE_SELL && (sl == 0.0 || cand < newSL)) { newSL = cand; modify = true; }
           }
        }
      if(tslMode != CALC_MODE_OFF && tslValue > 0.0)
        {
         double trig = CalcDistance(tslMode, tslTrigger, open);
         double dist = CalcDistance(tslMode, tslValue, open);
         double step = CalcDistance(tslMode, tslStep, open);
         if(profit > trig)
           {
            if(type == POSITION_TYPE_BUY)
              {
               double cand = bid - dist;
               if(sl == 0.0 || (cand - newSL) >= MathMax(step, _Point)) { newSL = cand; modify = true; }
              }
            else
              {
               double cand = ask + dist;
               if(sl == 0.0 || (newSL - cand) >= MathMax(step, _Point)) { newSL = cand; modify = true; }
              }
           }
        }
      if(modify)
        {
         newSL = NormalizeDouble(newSL, _Digits);
         if(MathAbs(newSL - sl) > _Point * 0.5)
            if(!trade.PositionModify(tk, newSL, tp))
               PrintFormat("T58: SL modify failed ticket %I64u retcode=%d (%s)", tk, trade.ResultRetcode(), trade.ResultRetcodeDescription());
        }
     }
  }

// minutes since midnight (server time)
int MinutesNow()
  {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   return t.hour * 60 + t.min;
  }

int DayOfWeekNow()
  {
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   return t.day_of_week;     // 0 = Sunday ... 6 = Saturday
  }

datetime DayStart(datetime t)
  {
   MqlDateTime s;
   TimeToStruct(t, s);
   s.hour = 0; s.min = 0; s.sec = 0;
   return StructToTime(s);
  }

// open a market position with SL/TP given as PRICE DISTANCES from the fill reference; returns true on success
bool OpenMarket(bool buy, double lots, double slDist, double tpDist, long magic, string comment)
  {
   if(lots <= 0.0)
     {
      Print("T58: volume resolved to 0 (below broker minimum or risk too small) - trade skipped.");
      return false;
     }
   trade.SetExpertMagicNumber(magic);
   trade.SetTypeFillingBySymbol(_Symbol);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double px  = buy ? ask : bid;
   double sl  = (slDist > 0.0) ? (buy ? px - slDist : px + slDist) : 0.0;
   double tp  = (tpDist > 0.0) ? (buy ? px + tpDist : px - tpDist) : 0.0;
   sl = (sl > 0.0) ? NormalizeDouble(sl, _Digits) : 0.0;
   tp = (tp > 0.0) ? NormalizeDouble(tp, _Digits) : 0.0;
   bool ok = buy ? trade.Buy(lots, _Symbol, 0.0, sl, tp, comment) : trade.Sell(lots, _Symbol, 0.0, sl, tp, comment);
   if(!ok)
      PrintFormat("T58: %s FAILED retcode=%d (%s)", buy ? "BUY" : "SELL", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   return ok;
  }

double IndicatorValue(int handle, int shift)
  {
   double b[1];
   if(handle == INVALID_HANDLE || CopyBuffer(handle, 0, shift, 1, b) != 1)
      return EMPTY_VALUE;
   return b[0];
  }


input group "=== Volume ==="
input ENUM_VOLUME_MODE InpVolumeMode = VOLUME_MONEY;
input double InpFixedLots = 0.10;
input double InpLotsPerMoney = 10000.0;
input double InpRiskPercent = 1.0;
input double InpBaseMoney = 50000.0;
input double InpRiskMoney = 250.0;
input group "=== Order ==="
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M15;
input double InpRetracementPercent = 0.35;
input int    InpRetLookback = 8;
input double InpTPPercent = 0.60;
input double InpSLPercent = 0.60;
input group "=== Time (server time) ==="
input bool InpClosePositions = true;
input int  InpCloseHour = 22;
input int  InpCloseMinute = 45;
input int  InpMaxTradesPerDay = 4;
input group "=== Break-even / trailing (% of price, 0 = off) ==="
input double InpBETriggerPercent = 0.0;
input double InpBEBufferPercent = 0.0;
input double InpTSLTriggerPercent = 0.0;
input double InpTSLPercent = 0.0;
input double InpTSLStepPercent = 0.0;
input group "=== Filters ==="
input bool InpBuyTrades = true;
input bool InpSellTrades = true;
input bool InpMAFilter = true;
input ENUM_TIMEFRAMES InpMATimeframe = PERIOD_M15;
input int  InpMAPeriods = 200;
input ENUM_MA_METHOD InpMAMethod = MODE_SMA;
input ENUM_APPLIED_PRICE InpMAPrice = PRICE_CLOSE;
input bool InpRSIFilter = false;
input ENUM_TIMEFRAMES InpRSITimeframe = PERIOD_M15;
input int  InpRSIPeriods = 14;
input ENUM_APPLIED_PRICE InpRSIPrice = PRICE_CLOSE;
input double InpRSILevel = 40.0;     // buys need RSI < level, sells need RSI > 100 - level
input group "=== More ==="
input string InpComment = "T58 Fisherman";
input long   InpMagic = 58005;

int g_ma = INVALID_HANDLE, g_rsi = INVALID_HANDLE;
datetime g_lastBar = 0, g_day = 0;
int g_tradesToday = 0;

int OnInit()
  {
   if(InpMAFilter)  { g_ma  = iMA(_Symbol, InpMATimeframe, InpMAPeriods, 0, InpMAMethod, InpMAPrice); if(g_ma == INVALID_HANDLE) return INIT_FAILED; }
   if(InpRSIFilter) { g_rsi = iRSI(_Symbol, InpRSITimeframe, InpRSIPeriods, InpRSIPrice);            if(g_rsi == INVALID_HANDLE) return INIT_FAILED; }
   if(InpSLPercent <= 0.0 && (InpVolumeMode == VOLUME_PERCENT || InpVolumeMode == VOLUME_MONEY))
     { Print("T58: risk-based volume needs SL Percent > 0."); return INIT_PARAMETERS_INCORRECT; }
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason)
  { if(g_ma != INVALID_HANDLE) IndicatorRelease(g_ma); if(g_rsi != INVALID_HANDLE) IndicatorRelease(g_rsi); }

void OnTick()
  {
   datetime today = DayStart(TimeCurrent());
   if(today != g_day) { g_day = today; g_tradesToday = 0; }
   ManageStops(InpMagic,
               InpBETriggerPercent > 0.0 ? CALC_MODE_PERCENT : CALC_MODE_OFF, InpBETriggerPercent, InpBEBufferPercent,
               InpTSLPercent > 0.0 ? CALC_MODE_PERCENT : CALC_MODE_OFF, InpTSLTriggerPercent, InpTSLPercent, InpTSLStepPercent);
   int now = MinutesNow();
   if(InpClosePositions && now >= InpCloseHour * 60 + InpCloseMinute) { CloseMyPositions(InpMagic); return; }
   if(!IsNewBar(InpTimeframe, g_lastBar)) return;             // signals are evaluated once per closed signal bar
   int dow = DayOfWeekNow();
   if(dow == 0 || dow == 6 || g_tradesToday >= InpMaxTradesPerDay || CountMyPositions(InpMagic) > 0) return;

   double c1 = iClose(_Symbol, InpTimeframe, 1);
   int hi = iHighest(_Symbol, InpTimeframe, MODE_HIGH, InpRetLookback, 1);
   int lo = iLowest(_Symbol, InpTimeframe, MODE_LOW, InpRetLookback, 1);
   if(hi < 0 || lo < 0 || c1 <= 0.0) return;
   double extHigh = iHigh(_Symbol, InpTimeframe, hi), extLow = iLow(_Symbol, InpTimeframe, lo);
   bool pulledBack = (extHigh - c1) / c1 * 100.0 >= InpRetracementPercent;      // dipped from recent high  -> buy in an uptrend
   bool bounced    = (c1 - extLow)  / c1 * 100.0 >= InpRetracementPercent;      // rallied from recent low -> sell in a downtrend

   bool upTrend = true, downTrend = true;
   if(InpMAFilter)
     {
      double ma = IndicatorValue(g_ma, 1);
      if(ma == EMPTY_VALUE) return;
      double cm = iClose(_Symbol, InpMATimeframe, 1);
      upTrend = cm > ma; downTrend = cm < ma;
     }
   bool rsiBuy = true, rsiSell = true;
   if(InpRSIFilter)
     {
      double r = IndicatorValue(g_rsi, 1);
      if(r == EMPTY_VALUE) return;
      rsiBuy = r < InpRSILevel; rsiSell = r > 100.0 - InpRSILevel;
     }
   bool buy  = InpBuyTrades  && upTrend   && pulledBack && rsiBuy;
   bool sell = InpSellTrades && downTrend && bounced    && rsiSell;
   if(buy == sell) return;                                     // neither, or (unfiltered) both -> no trade
   double px = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double slD = px * InpSLPercent / 100.0, tpD = (InpTPPercent > 0.0) ? px * InpTPPercent / 100.0 : 0.0;
   double lots = CalcVolume(InpVolumeMode, InpFixedLots, InpLotsPerMoney, InpRiskPercent, InpRiskMoney, slD, InpBaseMoney);
   if(OpenMarket(buy, lots, slD, tpD, InpMagic, InpComment)) g_tradesToday++;
  }
