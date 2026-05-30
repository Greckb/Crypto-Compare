const winston=require("winston");
const logger=winston.createLogger({level:process.env.LOG_LEVEL||"info",format:winston.format.combine(winston.format.timestamp(),winston.format.errors({stack:true}),winston.format.json()),transports:[new winston.transports.Console()]});
module.exports={info:(a,c={})=>logger.info({action:a,...c}),warn:(a,c={})=>logger.warn({action:a,...c}),error:(a,c={})=>logger.error({action:a,...c}),debug:(a,c={})=>logger.debug({action:a,...c})};
