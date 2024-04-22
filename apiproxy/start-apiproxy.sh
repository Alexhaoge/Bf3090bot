#!/bin/bash

source /home/openblas/venv/bin/activate
cd /home/openblas/bf3090bot/apiproxy/
uvicorn apiproxy:app --host 0.0.0.0 --port 8000 --workers 2