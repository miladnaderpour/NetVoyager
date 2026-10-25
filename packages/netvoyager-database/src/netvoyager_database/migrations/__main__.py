"""Explicit migrations: python -m netvoyager_database.migrations upgrade --url sqlite:///experiment.db"""
import argparse
from pathlib import Path
from alembic import command
from alembic.config import Config

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action', choices=['upgrade','downgrade','current','heads'])
    p.add_argument('--url', required=True)
    p.add_argument('--revision', default=None)
    args=p.parse_args()
    cfg=Config()
    cfg.set_main_option('script_location', str(Path(__file__).resolve().parent))
    cfg.attributes['database_url']=args.url
    if args.action=='upgrade':command.upgrade(cfg,args.revision or 'head')
    elif args.action=='downgrade':
        if not args.revision:p.error('downgrade requires --revision')
        command.downgrade(cfg,args.revision)
    elif args.action=='current':command.current(cfg)
    else:command.heads(cfg)
if __name__=='__main__':main()
