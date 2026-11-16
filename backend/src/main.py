import os,logging
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from src.config.database import Base,engine
from src.models import entities
from src.routes.api import router
from src.middlewares.request import RequestId,SecurityHeaders
def ensure_columns():
 try:
  with engine.connect() as c:
   cols={r[1] for r in c.execute(text('SHOW COLUMNS FROM settlements'))}
   if 'manual_checked' not in cols:c.execute(text('ALTER TABLE settlements ADD COLUMN manual_checked INTEGER'))
   if 'verification_id' not in cols:c.execute(text('ALTER TABLE settlements ADD COLUMN verification_id INTEGER'))
   c.commit()
 except Exception:logging.exception('migrate settlements')
@asynccontextmanager
async def lifespan(app):
 Base.metadata.create_all(engine)
 ensure_columns()
 if os.getenv('SEED_DEMO')=='true':
  try:
   from scripts.seed_demo import seed
   seed()
  except Exception:logging.exception('seed failed')
 yield
app=FastAPI(title='剧院场次结算透视',lifespan=lifespan)
app.add_middleware(RequestId);app.add_middleware(SecurityHeaders)
app.include_router(router)
@app.get('/health')
def health():
 from sqlalchemy import text
 import redis
 with engine.connect() as c:c.execute(text('SELECT 1'))
 redis.Redis.from_url(os.environ['REDIS_URL']).ping()
 return {'status':'ok'}
@app.exception_handler(Exception)
async def errors(request:Request,exc:Exception):
 logging.exception('request failed');return JSONResponse(status_code=500,content={'detail':'服务暂时异常，请稍后重试'})
