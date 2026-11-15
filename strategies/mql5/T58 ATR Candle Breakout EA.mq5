//+------------------------------------------------------------------+
//| T58 ATR Candle Breakout EA (twin: ES1! ATR Candle Breakout 15m)  |
//| A closed signal candle larger than ATR x mult that closes near   |
//| its extreme (and has a decent body) triggers an entry in its     |
//| direction. Optional trend (HTF MA), MTF ATR, time-of-day and S/R |
//| filters. Fixed-money risk sizing from the SL distance.           |
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


input group "=== Strategy ==="
input ENUM_TIMEFRAMES InpSignalTF = PERIOD_M15;
input int    InpATRPeriod = 14;
input double InpATRMult = 1.5;
input double InpCloseProxPct = 25.0;      // close must be within this % of the range from the candle extreme
input double InpMinBodyPct = 50.0;        // 0 = off
input group "=== Trend filter ==="
input bool InpUseTrend = true;
input ENUM_TIMEFRAMES InpTrendTF = PERIOD_H4;
input int  InpTrendPeriod = 50;
input ENUM_MA_METHOD InpTrendMethod = MODE_EMA;
input group "=== MTF ATR confirmation ==="
input bool InpUseMTF = false;
input ENUM_TIMEFRAMES InpMTFTF = PERIOD_H1;
input int  InpMTFATRPeriod = 14;
input double InpMTFMult = 1.0;
input group "=== Time filter (server time) ==="
input bool InpUseTime = true;
input int  InpStartHour = 16;
input int  InpEndHour = 22;
input bool InpSkipFriLate = true;
input bool InpSkipMonEarly = true;
input group "=== S/R filter ==="
input bool InpUseSR = false;
input ENUM_TIMEFRAMES InpSRTF = PERIOD_H1;
input int  InpSRLookback = 200;
input double InpSRZoneATR = 0.5;
input int  InpSRMinTouches = 2;
input group "=== Risk ==="
input double InpSLPercent = 0.50;
input double InpTPPercent = 1.00;
input double InpRiskMoney = 250.0;
input group "=== Trailing stop ==="
input bool InpUseTSL = false;
input double InpTSLActivatePercent = 0.30;
input double InpTSLStepPercent = 0.20;
input group "=== General ==="
input long InpMagic = 58006;
input int  InpSlippage = 50;
input int  InpMaxTradesPerDay = 3;

int g_atr = INVALID_HANDLE, g_trend = INVALID_HANDLE, g_mtfAtr = INVALID_HANDLE;
datetime g_lastBar = 0, g_day = 0;
int g_tradesToday = 0;

int OnInit()
  {
   g_atr = iATR(_Symbol, InpSignalTF, InpATRPeriod);
   if(InpUseTrend) g_trend = iMA(_Symbol, InpTrendTF, InpTrendPeriod, 0, InpTrendMethod, PRICE_CLOSE);
   if(InpUseMTF)   g_mtfAtr = iATR(_Symbol, InpMTFTF, InpMTFATRPeriod);
   if(g_atr == INVALID_HANDLE || (InpUseTrend && g_trend == INVALID_HANDLE) || (InpUseMTF && g_mtfAtr == INVALID_HANDLE)) return INIT_FAILED;
   if(InpSLPercent <= 0.0) { Print("T58: SL percent must be > 0 (risk-based sizing)."); return INIT_PARAMETERS_INCORRECT; }
   trade.SetDeviationInPoints(InpSlippage);
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason)
  {
   if(g_atr != INVALID_HANDLE) IndicatorRelease(g_atr);
   if(g_trend != INVALID_HANDLE) IndicatorRelease(g_trend);
   if(g_mtfAtr != INVALID_HANDLE) IndicatorRelease(g_mtfAtr);
  }

// 1 = price sits inside an S/R zone that blocks a buy (resistance), -1 = blocks a sell (support), 0 = clear
int SRBlock(double price, double atr)
  {
   double zone = InpSRZoneATR * atr;
   int resTouch = 0, supTouch = 0;
   int bars = InpSRLookback;
   for(int i = 2; i < bars - 2; i++)
     {
      double h = iHigh(_Symbol, InpSRTF, i), l = iLow(_Symbol, InpSRTF, i);
      bool swingH = h > iHigh(_Symbol, InpSRTF, i - 1) && h > iHigh(_Symbol, InpSRTF, i + 1) && h > iHigh(_Symbol, InpSRTF, i - 2) && h > iHigh(_Symbol, InpSRTF, i + 2);
      bool swingL = l < iLow(_Symbol, InpSRTF, i - 1) && l < iLow(_Symbol, InpSRTF, i + 1) && l < iLow(_Symbol, InpSRTF, i - 2) && l < iLow(_Symbol, InpSRTF, i + 2);
      if(swingH && MathAbs(price - h) <= zone && h >= price) resTouch++;
      if(swingL && MathAbs(price - l) <= zone && l <= price) supTouch++;
     }
   if(resTouch >= InpSRMinTouches) return 1;
   if(supTouch >= InpSRMinTouches) return -1;
   return 0;
  }

void OnTick()
  {
   datetime today = DayStart(TimeCurrent());
   if(today != g_day) { g_day = today; g_tradesToday = 0; }
   if(InpUseTSL) ManageStops(InpMagic, CALC_MODE_OFF, 0, 0, CALC_MODE_PERCENT, InpTSLActivatePercent, InpTSLStepPercent, 0.0);
   if(!IsNewBar(InpSignalTF, g_lastBar)) return;
   if(g_tradesToday >= InpMaxTradesPerDay || CountMyPositions(InpMagic) > 0) return;

   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   if(t.day_of_week == 0 || t.day_of_week == 6) return;
   if(InpUseTime)
     {
      if(t.hour < InpStartHour || t.hour >= InpEndHour) return;
      if(InpSkipFriLate && t.day_of_week == 5 && t.hour >= InpEndHour - 2) return;
      if(InpSkipMonEarly && t.day_of_week == 1 && t.hour < InpStartHour + 2) return;
     }
   double atr = IndicatorValue(g_atr, 1);
   if(atr == EMPTY_VALUE || atr <= 0.0) return;
   double o = iOpen(_Symbol, InpSignalTF, 1), h = iHigh(_Symbol, InpSignalTF, 1), l = iLow(_Symbol, InpSignalTF, 1), c = iClose(_Symbol, InpSignalTF, 1);
   double range = h - l;
   if(range <= 0.0 || range < InpATRMult * atr) return;
   if(InpMinBodyPct > 0.0 && MathAbs(c - o) / range * 100.0 < InpMinBodyPct) return;
   bool bullish = (h - c) / range * 100.0 <= InpCloseProxPct && c > o;
   bool bearish = (c - l) / range * 100.0 <= InpCloseProxPct && c < o;
   if(bullish == bearish) return;
   bool buy = bullish;

   if(InpUseTrend)
     {
      double ma = IndicatorValue(g_trend, 1), cT = iClose(_Symbol, InpTrendTF, 1);
      if(ma == EMPTY_VALUE) return;
      if(buy && cT <= ma) return;
      if(!buy && cT >= ma) return;
     }
   if(InpUseMTF)
     {
      double ha = IndicatorValue(g_mtfAtr, 1);
      double ho = iOpen(_Symbol, InpMTFTF, 0), hc = iClose(_Symbol, InpMTFTF, 0), hh = iHigh(_Symbol, InpMTFTF, 0), hl = iLow(_Symbol, InpMTFTF, 0);
      if(ha == EMPTY_VALUE || (hh - hl) < InpMTFMult * ha) return;
      if(buy && hc <= ho) return;
      if(!buy && hc >= ho) return;
     }
   if(InpUseSR)
     {
      int b = SRBlock(c, atr);
      if(buy && b == 1) return;
      if(!buy && b == -1) return;
     }
   double px = buy ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double slD = px * InpSLPercent / 100.0, tpD = (InpTPPercent > 0.0) ? px * InpTPPercent / 100.0 : 0.0;
   double lots = VolumeForRiskMoney(InpRiskMoney, slD);
   if(OpenMarket(buy, lots, slD, tpD, InpMagic, "T58 ATRBreakout")) g_tradesToday++;
  }
