const express=require("express"),{query}=require("../services/db"),logger=require("../services/logger");
const router=express.Router();
router.get("/",async(req,res)=>{
  try{
    const[ls,ot,rp,am]=await Promise.all([
      query("SELECT ts,direction,confidence FROM signals ORDER BY created_at DESC LIMIT 1"),
      query("SELECT COUNT(*) as count FROM trades WHERE status='open'"),
      query("SELECT win_rate,total_trades,total_pnl_usd,sharpe_ratio FROM performance_metrics WHERE window='30d' ORDER BY computed_at DESC LIMIT 1"),
      query("SELECT version,val_accuracy,val_auc FROM model_versions WHERE is_active=TRUE LIMIT 1"),
    ]);
    res.json({ts:new Date().toISOString(),system:"online",latest_signal:ls.rows[0]||null,open_trades:parseInt(ot.rows[0]?.count||0),performance_30d:rp.rows[0]||null,active_model:am.rows[0]||null});
  }catch(err){logger.error("status",{error:err.message});res.status(500).json({error:"Failed"}); }
});
module.exports=router;
