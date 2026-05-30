const express=require("express"),{query}=require("../services/db"),logger=require("../services/logger");
const router=express.Router();
router.post("/",async(req,res)=>{
  const{signal_id,mt4_ticket,direction,lots,entry_price,tp_price,sl_price}=req.body;
  if(!mt4_ticket||!direction||!lots) return res.status(400).json({error:"mt4_ticket,direction,lots required"});
  try{
    const r=await query("INSERT INTO trades (signal_id,mt4_ticket,direction,lots,entry_price,tp_price,sl_price,open_ts,status) VALUES ($1,$2,$3,$4,$5,$6,$7,NOW(),'open') ON CONFLICT (mt4_ticket) DO NOTHING RETURNING id",[signal_id,mt4_ticket,direction,lots,entry_price,tp_price,sl_price]);
    logger.info("trade_opened",{mt4_ticket,direction,lots}); res.status(201).json({id:r.rows[0]?.id});
  }catch(err){logger.error("trade_open",{error:err.message});res.status(500).json({error:"Failed"}); }
});
router.put("/:ticket",async(req,res)=>{
  const mt4_ticket=parseInt(req.params.ticket);
  const{status,exit_price,pnl_usd,pnl_pips,outcome}=req.body;
  const allowed=["open","closed","tp_hit","sl_hit"];
  if(!allowed.includes(status)) return res.status(400).json({error:`status must be one of: ${allowed.join(",")}`});
  try{
    await query("UPDATE trades SET status=$1,exit_price=$2,pnl_usd=$3,pnl_pips=$4,outcome=$5,close_ts=CASE WHEN $1 IN ('closed','tp_hit','sl_hit') THEN NOW() ELSE close_ts END,updated_at=NOW() WHERE mt4_ticket=$6",[status,exit_price,pnl_usd,pnl_pips,outcome,mt4_ticket]);
    logger.info("trade_updated",{mt4_ticket,status,pnl_usd}); res.json({ok:true});
  }catch(err){logger.error("trade_update",{error:err.message});res.status(500).json({error:"Failed"}); }
});
router.get("/",async(req,res)=>{
  try{
    const limit=Math.min(parseInt(req.query.limit)||50,500);
    const r=await query("SELECT * FROM trades ORDER BY created_at DESC LIMIT $1",[limit]);
    res.json({trades:r.rows});
  }catch(err){logger.error("trades_list",{error:err.message});res.status(500).json({error:"Failed"}); }
});
module.exports=router;
