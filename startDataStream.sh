#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
VENV_PATH="$SCRIPT_DIR/.venv/bin/activate"
PYTHON_SCRIPT="src/stream_data.py"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

cd "$SCRIPT_DIR" || exit 1

if [[ ! -f "$VENV_PATH" ]]; then
    echo -e "❌ Error: Virtual environment not found. Ensure .venv exists."
    exit 1
fi

echo -e "⚙️ Activating virtual environment..."
source "$VENV_PATH"

if [[ -f "$REQUIREMENTS_FILE" ]]; then
    echo -e "🔍 Checking for missing dependencies..."
    pip install -r "$REQUIREMENTS_FILE" --quiet

    if [[ $? -ne 0 ]]; then
        echo -e "❌ Error: Failed to install dependencies from requirements.txt."
        exit 1
    fi
else
    echo -e "❌ Error: requirements.txt not found in the script directory."
    exit 1
fi

export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

echo -e "📡 Starting Stream..."
python3 "$PYTHON_SCRIPT"
