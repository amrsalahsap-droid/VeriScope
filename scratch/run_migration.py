"""Run alembic upgrade to head."""
import sys, os
sys.path.insert(0, r'c:\Users\amrsa\Downloads\veriscope')
os.chdir(r'c:\Users\amrsa\Downloads\veriscope')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\amrsa\Downloads\veriscope\.env')

from alembic.config import Config
from alembic import command

cfg = Config(r'c:\Users\amrsa\Downloads\veriscope\alembic.ini')
cfg.set_main_option('script_location', r'c:\Users\amrsa\Downloads\veriscope\alembic')

print("Running upgrade to head...")
command.upgrade(cfg, 'a1b2c3d4e5f6')
print("Done.")
