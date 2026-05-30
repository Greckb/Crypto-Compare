const {Pool}=require("pg"),logger=require("./logger");
const pool=new Pool({connectionString:process.env.DATABASE_URL,max:10,idleTimeoutMillis:30000,connectionTimeoutMillis:5000});
pool.on("error",(err)=>logger.error("pg_pool_error",{error:err.message}));
async function query(text,params){
  const start=Date.now(),res=await pool.query(text,params),d=Date.now()-start;
  if(d>1000) logger.warn("slow_query",{duration:d,text:text.slice(0,80)});
  return res;
}
module.exports={query,pool};
