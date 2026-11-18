//+------------------------------------------------------------------+
//| T58 Range Breakout EA (twin: ES1! Range Breakout 5m.py)          |
//| Builds a range between two server times, then places a buy-stop  |
//| above and a sell-stop below it. Daily trade limits, range-size   |
//| filters, SL/TP as factor-of-range / percent / points.            |
//| UNCOMPILED: written from the input spec PDF - compile and test.  |
//| Defaults assume IC-style server time: 09:30 ET = 16:30 server.   |
//+------------------------------------------------------------------+
#property copyright "T58 Trading"
#property version   "1.00"
#property strict
// T58_TWIN=range_breakout
// T58_TIMEFRAME=5m
// (engine hooks: the Python backtester runs this EA through its vectorised twin in app/strategy/ea_twins, reading the
//  input lines below. MetaTrader ignores these comment lines.)
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
input ENUM_TIMEFRAMES  InpRangeTimeframe = PERIOD_M1;       // use M1 for live trading
input ENUM_VOLUME_MODE InpVolumeMode = VOLUME_MONEY;
input double InpFixedLots = 0.10;
input double InpLotsPerMoney = 10000.0;
input double InpRiskPercent = 1.0;
input double InpRiskMoney = 250.0;
input int    InpOrderBufferPoints = 0;
input ENUM_CALC_MODE InpTargetMode = CALC_MODE_FACTOR;
input double InpTargetValue = 1.5;
input ENUM_CALC_MODE InpStopMode = CALC_MODE_FACTOR;
input double InpStopValue = 1.0;
input group "=== Time (server time) ==="
input int InpRangeStartHour = 16;
input int InpRangeStartMinute = 30;
input int InpRangeEndHour = 17;
input int InpRangeEndMinute = 0;
input int InpDeleteOrdersHour = 19;
input int InpDeleteOrdersMinute = 0;      // 12:00 ET
input bool InpClosePositions = true;
input int InpCloseHour = 22;
input int InpCloseMinute = 55;
input group "=== Break-even / trailing ==="
input ENUM_CALC_MODE InpBEMode = CALC_MODE_OFF;      // PERCENT or POINTS (FACTOR is not meaningful after entry)
input double InpBETrigger = 0.0;
input double InpBEBuffer = 0.0;
input ENUM_CALC_MODE InpTSLMode = CALC_MODE_OFF;
input double InpTSLTrigger = 0.0;
input double InpTSLValue = 0.0;
input double InpTSLStep = 0.0;
input group "=== Trading frequency ==="
input int InpMaxLong = 1;
input int InpMaxShort = 1;
input int InpMaxTotal = 2;
input group "=== Range filter ==="
input double InpMinRangePoints = 0.0;
input double InpMinRangePercent = 0.0;
input double InpMaxRangePoints = 0.0;     // 0 = no maximum
input double InpMaxRangePercent = 0.0;    // 0 = no maximum
input group "=== More ==="
input string InpComment = "T58 RangeBreakout";
input long   InpMagic = 58004;
input bool   InpDebug = false;

datetime g_day = 0;
bool     g_ordersPlaced = false;
int      g_longs = 0, g_shorts = 0;
ulong    g_seenDeals = 0;

double ModeDistance(ENUM_CALC_MODE mode, double v, double refPrice, double rangeSize)
  {
   if(v <= 0.0 || mode == CALC_MODE_OFF) return 0.0;
   if(mode == CALC_MODE_FACTOR)  return rangeSize * v;
   if(mode == CALC_MODE_PERCENT) return refPrice * v / 100.0;
   return v * _Point;
  }

void CountTodaysFills()
  {
   g_longs = 0; g_shorts = 0;
   if(!HistorySelect(g_day, TimeCurrent() + 60)) return;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong tk = HistoryDealGetTicket(i);
      if(HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagic || HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
      if(HistoryDealGetInteger(tk, DEAL_TYPE) == DEAL_TYPE_BUY) g_longs++; else g_shorts++;
     }
  }

void PlaceBreakoutOrders()
  {
   datetime t0 = g_day + (InpRangeStartHour * 60 + InpRangeStartMinute) * 60;
   datetime t1 = g_day + (InpRangeEndHour * 60 + InpRangeEndMinute) * 60;
   MqlRates r[];
   int n = CopyRates(_Symbol, InpRangeTimeframe, t0, t1 - 1, r);
   if(n <= 0) { g_ordersPlaced = true; return; }
   double hi = r[0].high, lo = r[0].low;
   for(int i = 1; i < n; i++) { hi = MathMax(hi, r[i].high); lo = MathMin(lo, r[i].low); }
   double size = hi - lo, mid = (hi + lo) / 2.0;
   g_ordersPlaced = true;
   if(size <= 0.0) return;
   double pts = size / _Point, pct = size / mid * 100.0;
   if(InpMinRangePoints > 0 && pts < InpMinRangePoints) return;
   if(InpMinRangePercent > 0 && pct < InpMinRangePercent) return;
   if(InpMaxRangePoints > 0 && pts > InpMaxRangePoints) return;
   if(InpMaxRangePercent > 0 && pct > InpMaxRangePercent) return;

   double buf = InpOrderBufferPoints * _Point;
   double buyPx = NormalizeDouble(hi + buf, _Digits), sellPx = NormalizeDouble(lo - buf, _Digits);
   datetime expiry = g_day + (InpDeleteOrdersHour * 60 + InpDeleteOrdersMinute) * 60;
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);

   double slB = ModeDistance(InpStopMode, InpStopValue, hi, size), tpB = ModeDistance(InpTargetMode, InpTargetValue, hi, size);
   double slS = ModeDistance(InpStopMode, InpStopValue, lo, size), tpS = ModeDistance(InpTargetMode, InpTargetValue, lo, size);
   if(InpMaxLong > 0 && InpMaxTotal > 0)
     {
      double lots = CalcVolume(InpVolumeMode, InpFixedLots, InpLotsPerMoney, InpRiskPercent, InpRiskMoney, slB);
      if(lots > 0.0 && !trade.BuyStop(lots, buyPx, _Symbol, slB > 0 ? NormalizeDouble(buyPx - slB, _Digits) : 0.0,
                                      tpB > 0 ? NormalizeDouble(buyPx + tpB, _Digits) : 0.0, ORDER_TIME_SPECIFIED, expiry, InpComment))
         PrintFormat("T58: BuyStop failed %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
   if(InpMaxShort > 0 && InpMaxTotal > 0)
     {
      double lots = CalcVolume(InpVolumeMode, InpFixedLots, InpLotsPerMoney, InpRiskPercent, InpRiskMoney, slS);
      if(lots > 0.0 && !trade.SellStop(lots, sellPx, _Symbol, slS > 0 ? NormalizeDouble(sellPx + slS, _Digits) : 0.0,
                                       tpS > 0 ? NormalizeDouble(sellPx - tpS, _Digits) : 0.0, ORDER_TIME_SPECIFIED, expiry, InpComment))
         PrintFormat("T58: SellStop failed %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
   if(InpDebug) PrintFormat("T58 range: hi=%.2f lo=%.2f size=%.2f", hi, lo, size);
  }

void OnTick()
  {
   datetime today = DayStart(TimeCurrent());
   if(today != g_day) { g_day = today; g_ordersPlaced = false; g_longs = 0; g_shorts = 0; DeleteMyOrders(InpMagic); }
   ManageStops(InpMagic, InpBEMode, InpBETrigger, InpBEBuffer, InpTSLMode, InpTSLTrigger, InpTSLValue, InpTSLStep);
   int now = MinutesNow(), dow = DayOfWeekNow();
   if(InpClosePositions && now >= InpCloseHour * 60 + InpCloseMinute) { CloseMyPositions(InpMagic); DeleteMyOrders(InpMagic); return; }
   if(now >= InpDeleteOrdersHour * 60 + InpDeleteOrdersMinute) DeleteMyOrders(InpMagic);
   if(dow == 0 || dow == 6) return;
   // once the day's trade limit is reached, remove the opposite pending order
   CountTodaysFills();
   if(g_longs + g_shorts >= InpMaxTotal || g_longs >= InpMaxLong || g_shorts >= InpMaxShort) DeleteMyOrders(InpMagic);
   if(!g_ordersPlaced && now >= InpRangeEndHour * 60 + InpRangeEndMinute && now < InpDeleteOrdersHour * 60 + InpDeleteOrdersMinute)
      PlaceBreakoutOrders();
  }
