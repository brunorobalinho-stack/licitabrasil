#!/bin/bash
# Wrapper para rodar coleta CBTU em background
cd /Users/brunorobalinho/Projects/licitabrasil || exit 1
nohup .venv/bin/python scripts/run_cbtu_scrape.py > /tmp/cbtu_scrape.log 2>&1 &
echo $! > /tmp/cbtu_scrape.pid
disown
