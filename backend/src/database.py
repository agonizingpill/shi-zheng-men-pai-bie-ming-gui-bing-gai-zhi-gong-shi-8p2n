import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,DeclarativeBase
url=os.environ['DATABASE_URL']
# MySQL 演示库按 READ COMMITTED 运行；SQLite 仅用于本地测试，不设置该隔离级别。
options={'pool_pre_ping':True}
if url.startswith('mysql'):options['isolation_level']='READ COMMITTED'
if url.startswith('sqlite'):options['connect_args']={'check_same_thread':False}
engine=create_engine(url,**options)
Session=sessionmaker(engine,expire_on_commit=False)
class Base(DeclarativeBase):pass
