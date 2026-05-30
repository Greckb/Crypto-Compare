const express=require("express"),Redis=require("ioredis"),{query}=require("../services/db"),logger=require("../services/logger");
const router=express.Router(),redis=new Redis(process.env.REDIS_URL);
router.get("/latest",async(req,res)=>{
  try{
    const cached=await redis.get("latest_signal");
    if(cached){const s=JSON.parse(cached);await query("UPDATE signals SET status='sent' WHERE id=$1 AND status='pending'",[s.id]);return res.json({signal:s,source:"cache"});}
    const r=await query("SELECT * FROM signals WHERE status='pending' ORDER BY created_at DESC LIMIT 1");
    if(!r.rows.length) return res.json({signal:null});
    const s=r.rows[0]; await query("UPDATE signals SET status='sent' WHERE id=$1",[s.id]);
    res.json({signal:s});
  }catch(err){logger.error("signals_latest",{error:err.message});res.status(500).json({error:"Failed"}); }
});
router.get("/history",async(req,res)=>{
  try{
    const limit=Math.min(parseInt(req.query.limit)||50,200);
    const r=await query("SELECT s.*,mv.version as model_version_name FROM signals s LEFT JOIN model_versions mv ON s.model_version=mv.id ORDER BY s.created_at DESC LIMIT $1",[limit]);
    res.json({signals:r.rows});
  }catch(err){logger.error("signals_history",{error:err.message});res.status(500).json({error:"Failed"}); }
});
module.exports=router;
