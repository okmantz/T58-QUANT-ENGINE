//+------------------------------------------------------------------+
//| T58 Turnaround Tuesday EA  (twin: ES1! Turnaround Tuesday 5m.py) |
//| Buys on a chosen weekday (default Monday), closes on another     |
//| (default Tuesday). Optional daily MA filter.                      |
//| UNCOMPILED: written from the input spec PDF - compile and test.   |
//| Defaults assume an IC-style server (GMT+2/+3): 09:30 ET = 16:30.  |
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


input group "=== General ==="
input bool               InpWaitNewDayHigh = false;
input ENUM_VOLUME_MODE   InpVolumeMode     = VOLUME_MONEY;
input double             InpFixedLots      = 0.10;
input double             InpLotsPerMoney   = 10000.0;
input double             InpRiskPercent    = 1.0;
input double             InpRiskMoney      = 600.0;
input ENUM_CALC_MODE     InpTargetMode     = CALC_MODE_OFF;
input double             InpTargetValue    = 0.0;
input ENUM_CALC_MODE     InpStopMode       = CALC_MODE_PERCENT;
input double             InpStopValue      = 1.5;
input group "=== Time (server time) ==="
input int  InpStartHour = 16;
input int  InpStartMinute = 30;
input int  InpCloseHour = 22;
input int  InpCloseMinute = 55;
input int  InpOpenDow  = 1;    // 0=Sun,1=Mon ... 6=Sat (MqlDateTime day_of_week)
input int  InpCloseDow = 2;    // default Tuesday
input group "=== Break-even / trailing ==="
input ENUM_CALC_MODE InpBEMode = CALC_MODE_OFF;
input double InpBETrigger = 0.0;
input double InpBEBuffer  = 0.0;
input ENUM_CALC_MODE InpTSLMode = CALC_MODE_OFF;
input double InpTSLTrigger = 0.0;
input double InpTSLValue = 0.0;
input double InpTSLStep = 0.0;
input group "=== MA filter ==="
input bool                InpUseMA = true;
input ENUM_TIMEFRAMES     InpMATimeframe = PERIOD_D1;
input int                 InpMAPeriods = 200;
input ENUM_MA_METHOD      InpMAMethod = MODE_SMA;
input ENUM_APPLIED_PRICE  InpMAPrice = PRICE_CLOSE;
input group "=== More ==="
input string InpComment = "T58 TurnaroundTue";
input long   InpMagic = 58002;

int      g_maHandle = INVALID_HANDLE;
datetime g_day = 0;
bool     g_tradedToday = false;

int OnInit()
  {
   if(InpUseMA)
     {
      g_maHandle = iMA(_Symbol, InpMATimeframe, InpMAPeriods, 0, InpMAMethod, InpMAPrice);
      if(g_maHandle == INVALID_HANDLE) return INIT_FAILED;
     }
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { if(g_maHandle != INVALID_HANDLE) IndicatorRelease(g_maHandle); }

void OnTick()
  {
   datetime today = DayStart(TimeCurrent());
   if(today != g_day) { g_day = today; g_tradedToday = false; }
   ManageStops(InpMagic, InpBEMode, InpBETrigger, InpBEBuffer, InpTSLMode, InpTSLTrigger, InpTSLValue, InpTSLStep);

   int now = MinutesNow();
   int dow = DayOfWeekNow();
   // exit: on the close weekday at/after the close time
   if(dow == InpCloseDow && now >= InpCloseHour * 60 + InpCloseMinute)
      CloseMyPositions(InpMagic);

   if(g_tradedToday || dow != InpOpenDow) return;
   if(now < InpStartHour * 60 + InpStartMinute || now >= InpCloseHour * 60 + InpCloseMinute) return;
   if(CountMyPositions(InpMagic) > 0) { g_tradedToday = true; return; }
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(InpUseMA)
     {
      double ma = IndicatorValue(g_maHandle, 1);               // last COMPLETED MA bar
      double cl = iClose(_Symbol, InpMATimeframe, 1);
      if(ma == EMPTY_VALUE || cl <= ma) { g_tradedToday = true; return; }   // filter fails for today
     }
   if(InpWaitNewDayHigh && ask < iHigh(_Symbol, PERIOD_D1, 0)) return;
   double slD = CalcDistance(InpStopMode, InpStopValue, ask);
   double tpD = CalcDistance(InpTargetMode, InpTargetValue, ask);
   double lots = CalcVolume(InpVolumeMode, InpFixedLots, InpLotsPerMoney, InpRiskPercent, InpRiskMoney, slD);
   OpenMarket(true, lots, slD, tpD, InpMagic, InpComment);
   g_tradedToday = true;
  }
