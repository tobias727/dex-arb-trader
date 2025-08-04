[![linting: pylint](https://img.shields.io/badge/linting-pylint-yellowgreen)](https://github.com/pylint-dev/pylint)
[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# DEX Arbitrage Trader

DEX Arbitrage Trader is a Python (and future Rust) based automated trading framework designed for decentralized exchange (DEX) and centralized exchange (CEX) arbitrage opportunities.

## Setup and Usage

### Setup

Run the following setup in a Linux/wsl environment.

Copy the provided `.env.example` file to create your `.env` file and populate necessary values.
```bash
cp .env.example .env
```

| Environment Variable   | Description                                               |
|------------------------|-----------------------------------------------------------|
| `BINANCE_API_KEY`      | API key for accessing Binance for trading or data.        |
| `BINANCE_API_SECRET`   | Secret key for Binance API authentication.                |
| `ALCHEMY_API_KEY`      | API key for interacting with Alchemy Ethereum services.   |
| `ETHERSCAN_API_KEY`    | API key for accessing Etherscan for contract verification or data. |

Ensure Python (>= `3.12`) and `pip` are installed.

Next, setup a venv and install dependencies, using:
```
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

### Usage

To stream Binance and Unichain data, use

```
./startDataStream.sh
```

To analyse price discrepancies use `notebooks/data-analysis.ipynb`.

## Configuration

Modify `values.yaml` to configure values.

## Next Steps

Planned next steps are:

- Mid-cap token volatility analysis
- Rust execution layer
- Execution slippage modeling
- On-chain simulation

## License

This project is licensed under the MIT License.
See the [LICENSE](LICENSE) file for more details.
