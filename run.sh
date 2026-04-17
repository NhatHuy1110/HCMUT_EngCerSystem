#!/bin/bash
cd backend
export FLASK_APP=server.py
flask run --host=0.0.0.0 --port=8000
