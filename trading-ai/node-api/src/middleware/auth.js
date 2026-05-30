const logger=require("../services/logger");
const VALID_KEY=process.env.API_KEY_INTERNAL;
if(!VALID_KEY) throw new Error("API_KEY_INTERNAL required");
function authMiddleware(req,res,next){
  const key=req.headers["x-api-key"];
  if(!key||key!==VALID_KEY){logger.warn("auth_failed",{ip:req.ip,path:req.path});return res.status(401).json({error:"Unauthorized"});}
  next();
}
module.exports={authMiddleware};
