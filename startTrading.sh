#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
VENV_PATH="$SCRIPT_DIR/.venv/bin/activate"
PYTHON_SCRIPT="src/main.py"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
LOG_DIR="$SCRIPT_DIR/out/logs"
LOG_FILE="$LOG_DIR/trading_bot_v.4.0.log"

cd "$SCRIPT_DIR" || exit 1

mkdir -p "$LOG_DIR"

if [[ ! -f "$VENV_PATH" ]]; then
    echo "❌ Error: Virtual environment not found. Ensure .venv exists."
    exit 1
fi

echo "⚙️ Activating virtual environment..."
source "$VENV_PATH"

if [[ -f "$REQUIREMENTS_FILE" ]]; then
    echo "🔍 Checking for missing dependencies..."
    pip install -r "$REQUIREMENTS_FILE" --quiet
    if [[ $? -ne 0 ]]; then
        echo "❌ Error: Failed to install dependencies from requirements.txt."
        exit 1
    fi
else
    echo "❌ Error: requirements.txt not found in the script directory."
    exit 1
fi

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

echo "⚡ Starting Execution... logs: $LOG_FILE"
python3 "$PYTHON_SCRIPT" >> "$LOG_FILE" 2>&1
