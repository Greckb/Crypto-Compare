//+------------------------------------------------------------------+
//|  XauUsdAI_EA.mq4 — AI Signal Executor for XAU/USD               |
//+------------------------------------------------------------------+
#property strict
#property version   "1.00"

input string   ApiBaseUrl      = "http://127.0.0.1:3000";
input string   ApiKey          = "";
input double   RiskPctPerTrade = 1.0;
input double   MaxSpreadPips   = 3.0;
input int      MagicNumber     = 20240101;
input int      PollIntervalSec = 60;
input bool     EnableTrading   = false;

datetime g_lastPollTime=0; string g_lastSignalId=""; int g_openTicket=-1;

int OnInit(){
   if(!EnableTrading) Print("XauUsdAI: MONITOR ONLY mode");
   if(StringLen(ApiKey)==0){Alert("ApiKey is empty!");return INIT_PARAMETERS_INCORRECT;}
   return INIT_SUCCEEDED;
}

void OnTick(){
   datetime now=TimeCurrent();
   if(g_openTicket>0) MonitorOpenTrade();
   if(now-g_lastPollTime<PollIntervalSec) return;
   g_lastPollTime=now;
   if(g_openTicket>0) return;
   PollAndExecuteSignal();
}

void PollAndExecuteSignal(){
   string url=ApiBaseUrl+"/api/signals/latest";
   string headers="X-API-Key: "+ApiKey+"\r\nContent-Type: application/json";
   char post[],response[];
   int res=WebRequest("GET",url,headers,5000,post,response,headers);
   if(res!=200){Print("XauUsdAI: poll failed HTTP ",res);return;}
   string json=CharArrayToString(response);
   string signalId=JsonGetString(json,"id");
   string direction=JsonGetString(json,"direction");
   double slPrice=JsonGetDouble(json,"sl_price");
   double tpPrice=JsonGetDouble(json,"tp_price");
   double confidence=JsonGetDouble(json,"confidence");
   if(StringLen(signalId)==0||signalId==g_lastSignalId) return;
   if(direction=="0"||direction=="") return;
   g_lastSignalId=signalId;
   int dir=(int)StringToInteger(direction);
   if(dir!=1&&dir!=-1) return;
   double spread=(Ask-Bid)/Point/10.0;
   if(spread>MaxSpreadPips){Print("XauUsdAI: spread ",DoubleToStr(spread,1)," too wide");return;}
   if(!EnableTrading){Print("[MONITOR] dir=",dir," conf=",confidence," tp=",tpPrice," sl=",slPrice);return;}
   ExecuteSignal(signalId,dir,slPrice,tpPrice,confidence);
}

void ExecuteSignal(string signalId,int direction,double sl,double tp,double confidence){
   double lots=CalculateLots(sl);
   if(lots<=0) return;
   int orderType=(direction==1)?OP_BUY:OP_SELL;
   double entry=(direction==1)?Ask:Bid;
   int ticket=OrderSend(Symbol(),orderType,lots,entry,30,sl,tp,"AI_"+StringSubstr(signalId,0,8),MagicNumber,0,(direction==1)?clrGreen:clrRed);
   if(ticket<0){Print("XauUsdAI: OrderSend error ",GetLastError());return;}
   g_openTicket=ticket;
   Print("XauUsdAI: Opened ticket=",ticket," lots=",lots," dir=",direction," tp=",tp," sl=",sl);
   ReportTradeToApi(signalId,ticket,direction,lots,entry,tp,sl);
}

void MonitorOpenTrade(){
   if(!OrderSelect(g_openTicket,SELECT_BY_TICKET)) return;
   if(OrderType()>OP_SELL) return;
   if(OrderCloseTime()==0){
      double pnlPips=(OrderType()==OP_BUY)?(Bid-OrderOpenPrice())/Point/10.0:(OrderOpenPrice()-Ask)/Point/10.0;
      double riskPips=MathAbs(OrderOpenPrice()-OrderStopLoss())/Point/10.0;
      if(pnlPips>riskPips*0.8&&OrderStopLoss()!=OrderOpenPrice())
         OrderModify(g_openTicket,OrderOpenPrice(),OrderOpenPrice(),OrderTakeProfit(),0);
      return;
   }
   double exit=OrderClosePrice(),pnlUsd=OrderProfit()+OrderSwap()+OrderCommission();
   double pnlPips=(OrderType()==OP_BUY)?(exit-OrderOpenPrice())/Point/10.0:(OrderOpenPrice()-exit)/Point/10.0;
   string outcome="manual_close";
   if(MathAbs(exit-OrderTakeProfit())<Point*5) outcome="tp_hit";
   if(MathAbs(exit-OrderStopLoss())<Point*5) outcome="sl_hit";
   Print("XauUsdAI: Closed ticket=",g_openTicket," ",outcome," pnl=",DoubleToStr(pnlUsd,2));
   UpdateTradeApi(g_openTicket,"closed",exit,pnlUsd,pnlPips,outcome);
   g_openTicket=-1;
}

double CalculateLots(double slPrice){
   double riskUsd=AccountBalance()*RiskPctPerTrade/100.0;
   double entry=(Ask+Bid)/2.0;
   double slPips=MathAbs(entry-slPrice)/Point/10.0;
   if(slPips<=0) return 0;
   double pipVal=MarketInfo(Symbol(),MODE_TICKVALUE)/MarketInfo(Symbol(),MODE_TICKSIZE)*Point*10;
   if(pipVal<=0) return 0;
   double lots=NormalizeDouble(riskUsd/(slPips*pipVal),2);
   return MathMax(MathMin(lots,MarketInfo(Symbol(),MODE_MAXLOT)),MarketInfo(Symbol(),MODE_MINLOT));
}

void ReportTradeToApi(string sid,int ticket,int dir,double lots,double entry,double tp,double sl){
   string body=StringFormat("{\"signal_id\":\"%s\",\"mt4_ticket\":%d,\"direction\":%d,\"lots\":%.2f,\"entry_price\":%.5f,\"tp_price\":%.5f,\"sl_price\":%.5f}",sid,ticket,dir,lots,entry,tp,sl);
   _postJson(ApiBaseUrl+"/api/trades",body);
}

void UpdateTradeApi(int ticket,string status,double exit,double pnlUsd,double pnlPips,string outcome){
   string body=StringFormat("{\"status\":\"%s\",\"exit_price\":%.5f,\"pnl_usd\":%.4f,\"pnl_pips\":%.2f,\"outcome\":\"%s\"}",status,exit,pnlUsd,pnlPips,outcome);
   _putJson(ApiBaseUrl+"/api/trades/"+IntegerToString(ticket),body);
}

void _postJson(string url,string body){
   string h="X-API-Key: "+ApiKey+"\r\nContent-Type: application/json"; char p[],r[];
   StringToCharArray(body,p,0,StringLen(body));
   int res=WebRequest("POST",url,h,5000,p,r,h);
   if(res!=200&&res!=201) Print("POST failed: ",res);
}

void _putJson(string url,string body){
   string h="X-API-Key: "+ApiKey+"\r\nContent-Type: application/json"; char p[],r[];
   StringToCharArray(body,p,0,StringLen(body));
   int res=WebRequest("PUT",url,h,5000,p,r,h);
   if(res!=200) Print("PUT failed: ",res);
}

string JsonGetString(string json,string key){
   string s="\""+key+"\":\""; int pos=StringFind(json,s); if(pos<0) return "";
   pos+=StringLen(s); int end=StringFind(json,"\"",pos); if(end<0) return "";
   return StringSubstr(json,pos,end-pos);
}

double JsonGetDouble(string json,string key){
   string s="\""+key+"\":"; int pos=StringFind(json,s); if(pos<0) return 0.0;
   pos+=StringLen(s); string num="";
   for(int i=pos;i<StringLen(json)&&i<pos+20;i++){string ch=StringSubstr(json,i,1);if(ch==","||ch=="}"||ch==" "||ch=="\n") break;num+=ch;}
   return StringToDouble(num);
}
