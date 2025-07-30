#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
VENV_PATH="$SCRIPT_DIR/.venv/bin/activate"
PYTHON_SCRIPT="stream_data.py"
cd "$SCRIPT_DIR" || exit 1

if [[ ! -f "$VENV_PATH" ]]; then
    echo -e "❌ Error: Virtual environment not found. Ensure .venv exists."
    exit 1
fi

echo -e "⚙️ Activating virtual environment..."
source "$VENV_PATH"

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

echo -e "📡 Starting Stream..."
python3 "$PYTHON_SCRIPT"
