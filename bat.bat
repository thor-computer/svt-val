@echo off

echo [COMMAND PROMPT] Activating virtual environment
python -m venv venv
call venv\Scripts\activate

echo [COMMAND PROMPT] Installing Python dependencies
python -m pip install -r requirements.txt

echo [COMMAND PROMPT] Running py.py
python py.py

echo [COMMAND PROMPT] Deactivating virtual environment
deactivate
