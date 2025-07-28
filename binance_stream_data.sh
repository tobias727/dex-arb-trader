#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
VENV_PATH="$SCRIPT_DIR/.venv/bin/activate"
PYTHON_SCRIPT="src/binance/ws_stream.py"
cd "$SCRIPT_DIR" || exit 1

if [[ ! -f "$VENV_PATH" ]]; then
    echo "Error: Virtual environment not found. Ensure .venv exists."
    exit 1
fi

echo "Activating virtual environment..."
source "$VENV_PATH"

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

echo "Starting WebSocket data stream..."
python3 "$PYTHON_SCRIPT"
