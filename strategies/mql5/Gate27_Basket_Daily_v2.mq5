//+------------------------------------------------------------------------+
//|                                            Gate27_V1_EA_armored.mq5     |
//|  Owen Mantz's Gate27_V1_EA.mq5 (T58 Trading) + the gate-record armor.    |
//|                                                                          |
//|  v2 (T58 net-profit re-tune, 2026-11): ONLY the three input defaults    |
//|  below changed (SMA 210->150, vol window 60->40, daily vol target 0.5->   |
//|  1.0). Selected on 2020-2023, confirmed on 2024, read once on 2025-26;    |
//|  see docs/T58_STRATEGY_EVALUATION_2026-11.md. For a prop account keep    |
//|  the v1 defaults: this version doubles the risk and is for rule-free     |
//|  accounts (Objective C).                                                 |
//|                                                                          |
//|  CHANGELOG vs Owen's v1.00 (everything else is his, unchanged):          |
//|   FIX-A : transient data failure no longer flattens live positions —     |
//|           a leg that can't be evaluated CARRIES FORWARD last month's     |
//|           target instead of zeroing it.                                  |
//|   FIX-B : bar/month detection references the first ENABLED leg, not      |
//|           hardcoded leg 0.                                               |
//|   ARMOR-1: per-symbol force-flat guard — closes a leg when its floating  |
//|           loss hits -X% of the account BASELINE, ahead of FTP-class      |
//|           per-symbol termination lines. Guarded leg stays flat until     |
//|           the next monthly cycle (harness semantics). This guard is the  |
//|           difference between 46% and 64% funded on FTP's sheet in the    |
//|           gate record. OFF by default — turn ON for symbol-rule firms.   |
//|   ARMOR-2: account-level floating pre-protector — flattens ALL legs when |
//|           total floating P&L hits -X% of baseline. Built for FTUK-class  |
//|           "Account Protector" rules (theirs fires at -2% and counts      |
//|           strikes; firing OUR guard first at a tighter line never        |
//|           consumes one of their strikes). OFF by default.                |
//|   ARMOR-3: overall drawdown guard now supports STATIC-from-baseline mode |
//|           (default) matching how every verified firm actually measures   |
//|           it; Owen's trailing-from-peak mode kept as an option.          |
//|   ARMOR-4: explicit account BASELINE input — all guard percentages       |
//|           measure against the firm's initial account size, not whatever  |
//|           equity happened to be at EA start.                             |
//|                                                                          |
//|  PER-FIRM GUARD PRESETS (set inputs to these; guard lines sit INSIDE the |
//|  firm's rule with margin — a guard that equals the rule is not a guard): |
//|                                                                          |
//|            firm rule sheet              suggested inputs                 |
//|   FTP    : daily -4%, static -8%,       DailyLoss 3.0, OverallDD 7.0,    |
//|            symbol -3% HARD              SymbolGuard ON at 2.5            |
//|   E8 Pro : daily -2.5% PERMANENT,       DailyLoss 2.0, OverallDD 7.0,    |
//|            static -8%, no symbol rule   SymbolGuard OFF                  |
//|   FT     : daily -5%, static -10%,      DailyLoss 4.0, OverallDD 9.0,    |
//|            no symbol rule               SymbolGuard OFF                  |
//|   FTUK   : daily -5%, static -8%,       DailyLoss 4.0, OverallDD 7.0,    |
//|            protector -2% float/4 strikes AccountFloatGuard ON at 1.6     |
//|                                                                          |
//|  NOT COMPILED HERE — review in MetaEditor, compile, then demo through at |
//|  least one full monthly rebalance before any prop-firm capital. Same     |
//|  status line as everything in this record: rule-math port, zero live     |
//|  validation, the demo cycle is the referee.                              |
//+------------------------------------------------------------------------+
#property copyright "T58 Trading (Owen Mantz) + gate-record armor (Colin/Claude)"
#property version   "2.00"
#property strict
// T58_TWIN=gate27
// T58_TIMEFRAME=1d
// T58_MIN_TRADES=30
// (engine hooks: the Python backtester runs this EA through its vectorised twin in app/strategy/ea_twins, reading the
//  input lines below. MetaTrader ignores these comment lines.)

#include <Trade\Trade.mqh>

//============================================================================
// INPUTS
//============================================================================

input group "=== Universe — map each leg to your broker's exact symbol name ==="
input string InpSymbolUS500 = "US500.cash";
input string InpSymbolGold  = "XAUUSD";
input string InpSymbolOil   = "USOIL";
input string InpSymbolUSD   = "USDX";

input group "=== Leg toggles — disable a leg your broker doesn't offer ==="
input bool   InpUseUS500 = true;
input bool   InpUseGold  = true;
input bool   InpUseOil   = true;
input bool   InpUseUSD   = true;

input group "=== Signal (mirrors SignalConfig in the Python source) ==="
input int    InpSmaWindow = 150;    // v2: was 210 (re-tuned for net profit, docs/T58_STRATEGY_EVALUATION_2026-11.md)
input int    InpVolWindow = 40;     // v2: was 60
input double InpTwinStopSigma = 0.0;   // ENGINE TWIN ONLY (ignored by MetaTrader): 0 = no stop (the EA has none). >0 = a disaster stop of that many daily sigmas, which sizes each leg by 1/vol but is unaffordable at 1% risk on futures

input group "=== Sizing (mirrors SizingConfig — FROZEN, don't change casually) ==="
input double InpDailyVolTargetPct = 1.0;   // v2: was 0.5. LOAD-BEARING per the harness; 1.0 doubles the position size and the drawdown
input double InpLeverageCap       = 5.0;
input int    InpPhaseInDays       = 3;

input group "=== Execution ==="
input int    InpMagicNumber    = 27271;
input int    InpSlippagePoints = 50;
input bool   InpEnableTrading  = true;

input group "=== ARMOR-4: account baseline — guard %s measure against THIS ==="
input double InpAccountBaseline = 0.0;   // 0 = capture ACCOUNT_BALANCE at first init and persist; else the firm's initial size, e.g. 100000

input group "=== Halt guards (flatten + halt; see per-firm preset table in header) ==="
input double InpMaxDailyLossPct       = 3.0;   // vs day-start equity — set INSIDE the firm's daily line
input double InpMaxOverallDrawdownPct = 7.0;   // vs baseline (static mode) or peak (trailing mode)
input bool   InpUseStaticDrawdown     = true;  // ARMOR-3: true = static-from-baseline (matches firm rules); false = Owen's trailing-from-peak
input bool   InpRequireManualResume   = true;

input group "=== ARMOR-1: per-symbol force-flat guard (FTP-class symbol rules) ==="
input bool   InpUseSymbolGuard = false;  // ON for firms with per-symbol kill lines (FTP: hard -3%)
input double InpSymbolGuardPct = 2.5;    // close the leg at -X% of baseline floating loss; stays flat until next monthly cycle

input group "=== ARMOR-2: account floating pre-protector (FTUK-class) ==="
input double InpAccountFloatGuardPct = 0.0;  // 0 = off; FTUK preset 1.6 (their protector fires at 2.0 and counts strikes)

//============================================================================
// GLOBAL STATE
//============================================================================

CTrade trade;

string legSymbol[4];
string legKey[4];
bool   legEnabled[4];
bool   legGuarded[4];        // ARMOR-1 state: guarded-out until next monthly cycle

string g_refSymbol = "";     // FIX-B: first ENABLED leg drives bar/month detection

datetime g_lastBarTime   = 0;
bool     g_tradingHalted = false;

//============================================================================
// PERSISTENCE — MT5 GlobalVariables, namespaced by magic number. (Owen's.)
//============================================================================

string GVName(string suffix)
  {
   return "G27_" + IntegerToString(InpMagicNumber) + "_" + suffix;
  }

void SaveDouble(string suffix, double val)
  {
   GlobalVariableSet(GVName(suffix), val);
  }

double LoadDouble(string suffix, double def)
  {
   string name = GVName(suffix);
   if(GlobalVariableCheck(name))
      return GlobalVariableGet(name);
   return def;
  }

//============================================================================
// BASELINE (ARMOR-4)
//============================================================================

double Baseline()
  {
   if(InpAccountBaseline > 0.0)
      return InpAccountBaseline;
   double saved = LoadDouble("Baseline", 0.0);
   if(saved > 0.0)
      return saved;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   SaveDouble("Baseline", bal);
   return bal;
  }

//============================================================================
// SYMBOL / LOT MATH (Owen's, unchanged)
//============================================================================

int LotDigits(double step)
  {
   if(step >= 1.0)    return 0;
   if(step >= 0.1)    return 1;
   if(step >= 0.01)   return 2;
   return 3;
  }

double NormalizeLots(string symbol, double lots)
  {
   double step   = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double minVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxVol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   if(step <= 0.0)
      return 0.0;

   double rounded = MathFloor(lots / step + 1e-8) * step;
   rounded = MathMax(0.0, MathMin(rounded, maxVol));
   if(rounded > 0.0 && rounded < minVol)
      rounded = 0.0;

   return NormalizeDouble(rounded, LotDigits(step));
  }

double GetMidPrice(string symbol)
  {
   double bid = SymbolInfoDouble(symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(symbol, SYMBOL_ASK);
   if(bid > 0.0 && ask > 0.0)
      return (bid + ask) / 2.0;
   if(bid > 0.0)
      return bid;
   return ask;
  }

double LotsToNotional(string symbol, double lots)
  {
   double price        = GetMidPrice(symbol);
   double contractSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(price <= 0.0 || contractSize <= 0.0)
      return 0.0;
   return lots * price * contractSize;
  }

double NotionalToLots(string symbol, double notional)
  {
   double price        = GetMidPrice(symbol);
   double contractSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   if(price <= 0.0 || contractSize <= 0.0 || notional <= 0.0)
      return 0.0;
   double lots = notional / (price * contractSize);
   return NormalizeLots(symbol, lots);
  }

//============================================================================
// POSITION HELPERS (Owen's, plus per-symbol floating P&L for ARMOR-1/2)
//============================================================================

double GetSymbolPositionVolume(string symbol)
  {
   double total = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != symbol)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
         continue;
      if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY)
         continue;
      total += PositionGetDouble(POSITION_VOLUME);
     }
   return total;
  }

// ARMOR: floating P&L (incl. swap, which is 0 on a genuinely swap-free
// account and a red flag worth seeing if it isn't) for this EA's positions
// on one symbol, in account currency.
double GetSymbolFloatingPL(string symbol)
  {
   double total = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != symbol)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
         continue;
      total += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   return total;
  }

void LogTradeResult(string action, string symbol, bool ok)
  {
   if(ok)
      PrintFormat("Gate27: %s OK on %s — retcode=%d", action, symbol, trade.ResultRetcode());
   else
      PrintFormat("Gate27: %s FAILED on %s — retcode=%d (%s)",
                  action, symbol, trade.ResultRetcode(), trade.ResultRetcodeDescription());
  }

void IncreasePositionVolume(string symbol, double lots)
  {
   lots = NormalizeLots(symbol, lots);
   if(lots <= 0.0)
      return;
   trade.SetTypeFillingBySymbol(symbol);
   bool ok = trade.Buy(lots, symbol, 0.0, 0.0, 0.0, "Gate27 phase-in");
   LogTradeResult("BUY " + DoubleToString(lots, 2), symbol, ok);
  }

void ReducePositionVolume(string symbol, double reduceBy)
  {
   double remaining = reduceBy;
   double minVol    = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);

   for(int i = PositionsTotal() - 1; i >= 0 && remaining > minVol * 0.5; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != symbol)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagicNumber)
         continue;
      if(PositionGetInteger(POSITION_TYPE) != POSITION_TYPE_BUY)
         continue;

      double posVol   = PositionGetDouble(POSITION_VOLUME);
      double closeVol = NormalizeLots(symbol, MathMin(posVol, remaining));
      if(closeVol <= 0.0)
         continue;

      trade.SetTypeFillingBySymbol(symbol);
      bool ok = trade.PositionClosePartial(ticket, closeVol);
      LogTradeResult("CLOSE " + DoubleToString(closeVol, 2), symbol, ok);
      if(ok)
         remaining -= closeVol;
     }
  }

void AdjustPositionToLots(string symbol, double targetLots)
  {
   double curLots = GetSymbolPositionVolume(symbol);
   double diff    = targetLots - curLots;
   double minVol  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);

   if(MathAbs(diff) < minVol * 0.5)
      return;

   if(diff > 0.0)
      IncreasePositionVolume(symbol, diff);
   else
      ReducePositionVolume(symbol, -diff);
  }

void FlattenAll()
  {
   for(int i = 0; i < 4; i++)
     {
      if(!legEnabled[i])
         continue;
      double vol = GetSymbolPositionVolume(legSymbol[i]);
      if(vol > 0.0)
         ReducePositionVolume(legSymbol[i], vol);
     }
  }

//============================================================================
// SIGNAL + VOLATILITY (Owen's, unchanged)
//============================================================================

bool ComputeSignalForLeg(string symbol, bool &isLongOut, double &volOut)
  {
   double smaCloses[];
   ArraySetAsSeries(smaCloses, true);
   int gotSma = CopyClose(symbol, PERIOD_D1, 1, InpSmaWindow, smaCloses);
   if(gotSma < InpSmaWindow)
     {
      PrintFormat("Gate27: insufficient SMA history for %s (%d/%d bars) — carrying forward last target (FIX-A)",
                  symbol, gotSma, InpSmaWindow);
      return false;
     }

   double smaSum = 0.0;
   for(int i = 0; i < InpSmaWindow; i++)
      smaSum += smaCloses[i];
   double sma       = smaSum / InpSmaWindow;
   double lastClose = smaCloses[0];

   double volCloses[];
   ArraySetAsSeries(volCloses, true);
   int gotVol = CopyClose(symbol, PERIOD_D1, 1, InpVolWindow + 1, volCloses);
   if(gotVol < InpVolWindow + 1)
     {
      PrintFormat("Gate27: insufficient vol history for %s (%d/%d bars) — carrying forward last target (FIX-A)",
                  symbol, gotVol, InpVolWindow + 1);
      return false;
     }

   double rets[];
   ArrayResize(rets, InpVolWindow);
   for(int i = 0; i < InpVolWindow; i++)
      rets[i] = (volCloses[i] - volCloses[i + 1]) / volCloses[i + 1];

   double mean = 0.0;
   for(int i = 0; i < InpVolWindow; i++)
      mean += rets[i];
   mean /= InpVolWindow;

   double var = 0.0;
   for(int i = 0; i < InpVolWindow; i++)
      var += (rets[i] - mean) * (rets[i] - mean);
   var /= (InpVolWindow - 1);

   volOut    = MathSqrt(var);
   isLongOut = (lastClose > sma);
   return true;
  }

//============================================================================
// CYCLE MANAGEMENT (Owen's + FIX-A + ARMOR-1 release)
//============================================================================

void StartNewCycle(int monthCode)
  {
   bool   isLong[4];
   double vol[4];
   bool   dataOk[4];
   int    nLong = 0;

   for(int i = 0; i < 4; i++)
     {
      isLong[i] = false;
      vol[i]    = 0.0;
      dataOk[i] = false;
      if(!legEnabled[i])
         continue;
      dataOk[i] = ComputeSignalForLeg(legSymbol[i], isLong[i], vol[i]);
      if(dataOk[i] && isLong[i])
         nLong++;
     }

   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskBudget = equity * (InpDailyVolTargetPct / 100.0);
   double k          = (nLong > 0) ? riskBudget / MathSqrt((double)nLong) : 0.0;

   double targetNotional[4];
   double gross = 0.0;
   for(int i = 0; i < 4; i++)
     {
      targetNotional[i] = 0.0;
      if(!legEnabled[i])
         continue;
      if(dataOk[i])
        {
         if(isLong[i] && vol[i] > 1e-9)
            targetNotional[i] = k / vol[i];
        }
      else
        {
         // FIX-A: a leg we couldn't evaluate HOLDS last month's target
         // instead of being flattened by a data hiccup.
         targetNotional[i] = LoadDouble("Target_" + legKey[i], 0.0);
        }
      gross += targetNotional[i];
     }

   double maxGross = equity * InpLeverageCap;
   if(gross > maxGross && gross > 0.0)
     {
      double scale = maxGross / gross;
      for(int i = 0; i < 4; i++)
         targetNotional[i] *= scale;
      PrintFormat("Gate27: leverage cap hit (%.1fx) — scaled gross target notional by %.3f", InpLeverageCap, scale);
     }

   for(int i = 0; i < 4; i++)
     {
      if(!legEnabled[i])
         continue;

      // ARMOR-1 release: new monthly cycle clears the guard (harness
      // semantics — guarded leg is out until the next monthly signal).
      if(legGuarded[i])
        {
         legGuarded[i] = false;
         SaveDouble("Guard_" + legKey[i], 0.0);
         PrintFormat("Gate27: symbol guard RELEASED on %s (new monthly cycle)", legKey[i]);
        }

      double curLots     = GetSymbolPositionVolume(legSymbol[i]);
      double curNotional = LotsToNotional(legSymbol[i], curLots);
      SaveDouble("Start_" + legKey[i], curNotional);
      SaveDouble("Target_" + legKey[i], targetNotional[i]);
      PrintFormat("Gate27: %s signal=%s vol=%.5f start_notional=%.2f target_notional=%.2f%s",
                  legKey[i],
                  (dataOk[i] ? (isLong[i] ? "LONG" : "FLAT") : "CARRIED-FWD"),
                  vol[i], curNotional, targetNotional[i],
                  dataOk[i] ? "" : "  (FIX-A: data unavailable, holding prior target)");
     }

   SaveDouble("PhaseStep", 0);
   SaveDouble("LastCycleMonth", (double)monthCode);
   GlobalVariablesFlush();
  }

void ExecutePhaseStep()
  {
   int step = (int)MathRound(LoadDouble("PhaseStep", (double)InpPhaseInDays));
   if(step >= InpPhaseInDays)
      return;

   double frac = (double)(step + 1) / (double)InpPhaseInDays;

   for(int i = 0; i < 4; i++)
     {
      if(!legEnabled[i])
         continue;
      if(legGuarded[i])
         continue;   // ARMOR-1: guarded-out leg is NOT rebuilt until next cycle
      double startN    = LoadDouble("Start_" + legKey[i], 0.0);
      double targetN   = LoadDouble("Target_" + legKey[i], 0.0);
      double dayTarget = startN + frac * (targetN - startN);
      double dayLots   = NotionalToLots(legSymbol[i], dayTarget);
      AdjustPositionToLots(legSymbol[i], dayLots);
     }

   SaveDouble("PhaseStep", (double)(step + 1));
   GlobalVariablesFlush();
   PrintFormat("Gate27: phase-in step %d/%d executed", step + 1, InpPhaseInDays);
  }

//============================================================================
// ARMOR-1: per-symbol force-flat guard. Runs intraday (every tick). The
// harness models this close-only; checking intraday is strictly SAFER
// against gap-through on the firm's hard line.
//============================================================================

void CheckSymbolGuard()
  {
   if(!InpUseSymbolGuard)
      return;
   double base = Baseline();
   if(base <= 0.0)
      return;

   for(int i = 0; i < 4; i++)
     {
      if(!legEnabled[i] || legGuarded[i])
         continue;
      double vol = GetSymbolPositionVolume(legSymbol[i]);
      if(vol <= 0.0)
         continue;
      double flPct = GetSymbolFloatingPL(legSymbol[i]) / base * 100.0;
      if(flPct <= -InpSymbolGuardPct)
        {
         PrintFormat("Gate27: SYMBOL GUARD on %s at %.2f%% of baseline — force-flat, out until next monthly cycle.",
                     legKey[i], flPct);
         ReducePositionVolume(legSymbol[i], vol);
         legGuarded[i] = true;
         SaveDouble("Guard_" + legKey[i], 1.0);
         GlobalVariablesFlush();
        }
     }
  }

//============================================================================
// ARMOR-2: account-level floating pre-protector (FTUK-class). Fires before
// the FIRM'S protector can, so their strike counter never increments.
// Flattens everything; positions rebuild at the next monthly cycle.
//============================================================================

void CheckAccountFloatGuard()
  {
   if(InpAccountFloatGuardPct <= 0.0)
      return;
   double base = Baseline();
   if(base <= 0.0)
      return;

   double totalFl = 0.0;
   for(int i = 0; i < 4; i++)
      if(legEnabled[i])
         totalFl += GetSymbolFloatingPL(legSymbol[i]);

   if(totalFl / base * 100.0 <= -InpAccountFloatGuardPct)
     {
      PrintFormat("Gate27: ACCOUNT FLOAT PRE-PROTECTOR at %.2f%% of baseline — flattening all legs (rebuild next cycle).",
                  totalFl / base * 100.0);
      FlattenAll();
      for(int i = 0; i < 4; i++)
        {
         if(!legEnabled[i])
            continue;
         legGuarded[i] = true;
         SaveDouble("Guard_" + legKey[i], 1.0);
        }
      GlobalVariablesFlush();
     }
  }

//============================================================================
// HALT GUARDS (Owen's + ARMOR-3 static mode + ARMOR-4 baseline)
//============================================================================

void ManageDailyResetAndGuards()
  {
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   int todayCode = now.year * 10000 + now.mon * 100 + now.day;

   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   int    savedDay = (int)MathRound(LoadDouble("DayCode", -1));

   if(savedDay != todayCode)
     {
      SaveDouble("DayCode", (double)todayCode);
      SaveDouble("DayStartEquity", equity);
     }

   double dayStartEquity = LoadDouble("DayStartEquity", equity);
   double peakEquity     = LoadDouble("PeakEquity", equity);
   if(equity > peakEquity)
     {
      peakEquity = equity;
      SaveDouble("PeakEquity", peakEquity);
     }

   double dailyLossPct = (dayStartEquity > 0.0) ? (dayStartEquity - equity) / dayStartEquity * 100.0 : 0.0;

   // ARMOR-3: static-from-baseline is how every verified firm measures the
   // overall line; trailing-from-peak (Owen's original) kept as an option —
   // note it is STRICTER than any firm rule and will eventually halt a
   // healthy account if used on this strategy.
   double ddPct;
   if(InpUseStaticDrawdown)
     {
      double base = Baseline();
      ddPct = (base > 0.0) ? (base - equity) / base * 100.0 : 0.0;
     }
   else
      ddPct = (peakEquity > 0.0) ? (peakEquity - equity) / peakEquity * 100.0 : 0.0;

   if(!g_tradingHalted)
     {
      if(dailyLossPct >= InpMaxDailyLossPct)
        {
         PrintFormat("Gate27: DAILY LOSS GUARD breached (%.2f%% >= %.2f%%) — flattening all legs and halting.",
                     dailyLossPct, InpMaxDailyLossPct);
         FlattenAll();
         g_tradingHalted = true;
         SaveDouble("TradingHalted", 1.0);
        }
      else if(ddPct >= InpMaxOverallDrawdownPct)
        {
         PrintFormat("Gate27: %s DRAWDOWN GUARD breached (%.2f%% >= %.2f%%) — flattening all legs and halting.",
                     InpUseStaticDrawdown ? "STATIC" : "TRAILING", ddPct, InpMaxOverallDrawdownPct);
         FlattenAll();
         g_tradingHalted = true;
         SaveDouble("TradingHalted", 1.0);
        }
     }
  }

//============================================================================
// CHART DISPLAY (Owen's + guard states)
//============================================================================

void UpdateChartComment()
  {
   string s = "=== Gate 27 V1 EA (armored v1.10) ===\n";
   s += StringFormat("Trading halted : %s\n", g_tradingHalted ? "YES — flat, awaiting manual resume" : "no");
   s += StringFormat("Baseline       : %.2f\n", Baseline());
   s += StringFormat("Phase step     : %d / %d\n", (int)MathRound(LoadDouble("PhaseStep", 0)), InpPhaseInDays);
   s += "-----------------------------\n";
   for(int i = 0; i < 4; i++)
     {
      if(!legEnabled[i])
         continue;
      double lots   = GetSymbolPositionVolume(legSymbol[i]);
      double target = LoadDouble("Target_" + legKey[i], 0.0);
      s += StringFormat("%-5s (%s): lots=%.2f  target_notional=%.0f%s\n",
                        legKey[i], legSymbol[i], lots, target,
                        legGuarded[i] ? "  [GUARDED-OUT until next cycle]" : "");
     }
   Comment(s);
  }

//============================================================================
// EA LIFECYCLE (Owen's + FIX-B + guard-state restore)
//============================================================================

int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpSlippagePoints);

   legSymbol[0] = InpSymbolUS500; legKey[0] = "US500"; legEnabled[0] = InpUseUS500;
   legSymbol[1] = InpSymbolGold;  legKey[1] = "GOLD";  legEnabled[1] = InpUseGold;
   legSymbol[2] = InpSymbolOil;   legKey[2] = "OIL";   legEnabled[2] = InpUseOil;
   legSymbol[3] = InpSymbolUSD;   legKey[3] = "USD";   legEnabled[3] = InpUseUSD;

   int enabledCount = 0;
   g_refSymbol = "";
   for(int i = 0; i < 4; i++)
     {
      legGuarded[i] = false;
      if(!legEnabled[i])
         continue;
      enabledCount++;
      if(g_refSymbol == "")
         g_refSymbol = legSymbol[i];   // FIX-B: first ENABLED leg is the clock

      if(!SymbolSelect(legSymbol[i], true))
        {
         PrintFormat("Gate27: FATAL — symbol '%s' not found. Check spelling against Market Watch, "
                     "or disable that leg.", legSymbol[i]);
         return(INIT_PARAMETERS_INCORRECT);
        }

      ENUM_SYMBOL_TRADE_MODE tm = (ENUM_SYMBOL_TRADE_MODE)SymbolInfoInteger(legSymbol[i], SYMBOL_TRADE_MODE);
      if(tm == SYMBOL_TRADE_MODE_DISABLED)
        {
         PrintFormat("Gate27: FATAL — trading is disabled on '%s' at this broker.", legSymbol[i]);
         return(INIT_PARAMETERS_INCORRECT);
        }

      // restore ARMOR-1 guard state across restarts
      legGuarded[i] = (LoadDouble("Guard_" + legKey[i], 0.0) > 0.5);
     }

   if(enabledCount == 0)
     {
      Print("Gate27: FATAL — no legs enabled. Enable at least one leg toggle.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   if(InpPhaseInDays < 1)
     {
      Print("Gate27: FATAL — InpPhaseInDays must be at least 1.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   if(InpUseSymbolGuard && InpSymbolGuardPct <= 0.0)
     {
      Print("Gate27: FATAL — symbol guard enabled with a non-positive threshold.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   g_tradingHalted = (LoadDouble("TradingHalted", 0.0) > 0.5) && InpRequireManualResume;
   g_lastBarTime   = 0;

   PrintFormat("Gate27 V1 EA (armored) initialized — %d leg(s), magic=%d, baseline=%.2f, "
               "symbol_guard=%s, float_guard=%s, dd_mode=%s, halted=%s",
               enabledCount, InpMagicNumber, Baseline(),
               InpUseSymbolGuard ? "ON" : "off",
               (InpAccountFloatGuardPct > 0.0) ? "ON" : "off",
               InpUseStaticDrawdown ? "static" : "trailing",
               g_tradingHalted ? "true" : "false");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   Comment("");
  }

void OnTick()
  {
   if(!InpEnableTrading)
      return;

   ManageDailyResetAndGuards();
   if(g_tradingHalted)
     {
      UpdateChartComment();
      return;
     }

   // ARMOR guards run intraday, every tick, BEFORE any phase-in order.
   CheckSymbolGuard();
   CheckAccountFloatGuard();

   datetime t0 = iTime(g_refSymbol, PERIOD_D1, 0);   // FIX-B
   if(t0 == 0)
      return;
   if(t0 == g_lastBarTime)
     {
      UpdateChartComment();
      return;
     }
   g_lastBarTime = t0;

   MqlDateTime dt0, dt1;
   TimeToStruct(iTime(g_refSymbol, PERIOD_D1, 0), dt0);
   TimeToStruct(iTime(g_refSymbol, PERIOD_D1, 1), dt1);
   int monthCode0 = dt0.year * 100 + dt0.mon;

   bool newMonth = (dt0.mon != dt1.mon) || (dt0.year != dt1.year);
   if(newMonth)
     {
      int lastCycleMonth = (int)MathRound(LoadDouble("LastCycleMonth", -1));
      if(lastCycleMonth != monthCode0)
        {
         PrintFormat("Gate27: new month detected (%d) — computing signal off the prior month-end close", monthCode0);
         StartNewCycle(monthCode0);
        }
     }

   ExecutePhaseStep();
   UpdateChartComment();
  }
//+------------------------------------------------------------------------+
