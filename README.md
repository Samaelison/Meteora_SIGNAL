# ⚠️ Disclaimer

This project was developed with the help of both a human (me) and AI (ChatGPT).

The main purpose of this project was learning and experimentation. I tested it with real funds, and the results were mixed — sometimes profitable, sometimes not. However, I have not tested it continuously for more than 5 days, so its long-term performance and stability are unknown.

Please refrain from posting comments about "vibe coding." The goal of this repository is to share ideas, learn, and improve.

I hope this project will be useful or interesting to people who are building trading bots. If you have any suggestions, recommendations, or constructive feedback about the code, I would greatly appreciate hearing from you.

**Thank you!**


# **Project Title**
Meteora Meme Trading Bot Suite

**Overview**\
This repository contains two main components for automated cryptocurrency market analysis and trading on the Solana blockchain:

1. **Analytical Bot** (`main.py`):

   - Fetches and filters new trading pairs via Meteora API.
   - Applies liquidity and volume filters.
   - Tracks coin state in a SQLite database.
   - Generates entry signals and sends alerts via Telegram.

2. **Trading Bot + Wrapper** (`solana_test.py` + `meteora_wrapper.js`):

   - Provides a Node.js Express wrapper (`meteora_wrapper.js`) around the `@meteora-ag/dlmm` library.
   - Executes on-chain actions: swaps, add/remove liquidity, position management.
   - Implements a bid/spot rebalancing strategy in Python (`solana_test.py`).

---

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Configuration](#configuration)
- [Installation](#installation)
- [Usage](#usage)
  - [Analytical Bot](#analytical-bot)
  - [Trading Bot](#trading-bot)
- [Modules](#modules)
- [Database](#database)
- [Logging](#logging)
- [Testing](#testing)
- [License](#license)

---

## Features

- Real-time filtering of new trading pairs.
- Customizable thresholds for new pairs, liquidity, and volume.
- Multi-stage signal generation based on price ratio and history.
- Telegram notifications for entry signals.
- Safe, retry-enabled on-chain operations: swaps, liquidity management.
- Bid/Spot rebalancing strategy with adaptive position reopening.

---

## Project Structure

```
project_root/  
├── config/                  # Environment variables and secrets  
├── src/                     # Source code  
│   ├── modules/             # Business logic modules  
│   ├── db.py                # Database wrapper (SQLite)  
│   ├── helpers.py           # Utility functions  
│   ├── logger.py            # Logging configuration  
│   ├── project_settings.py  # Static settings  
│   ├── inspect_db.py        # DB inspection script  
│   ├── main.py              # Analytical bot entrypoint  
│   ├── meteora_wrapper.js   # Node.js DLMM REST wrapper  
│   ├── solana_test.py       # Trading bot entrypoint  
│   ├── test_telegram.py     # Telegram notifier tests  
│   └── meteora_bot.db       # SQLite DB file  
├── .gitignore               # Ignored files  
├── README.md                # This file  
├── package.json             # Node.js dependencies  
├── package-lock.json        # Locked Node.js deps  
└── requirements.txt         # Python dependencies
```

---

## Prerequisites

- **Python 3.9+**
- **Node.js 18+** & npm
- **Solana CLI** (optional, for keypair management)
- **Telegram Bot Token** and **Chat ID**

---

## Configuration

1. Copy the example environment file:
   ```bash
   cp config/secrets.env.example config/secrets.env
   ```
2. Open `config/secrets.env` and provide:
   ```ini
   # Solana
   SOLANA_RPC_ENDPOINT=https://api.mainnet-beta.solana.com
   SOLANA_PRIVATE_KEY=<base58-encoded key>
   MY_SOLANA_ADDRESS=<your wallet address>

   # Telegram
   TELEGRAM_BOT_TOKEN=<your bot token>
   TELEGRAM_CHAT_ID=<your chat id>
   ```
3. (Optional) Adjust thresholds and settings in `src/project_settings.py`.

---

## Installation

**1. Node.js wrapper**

```bash
cd src
npm install
```

**2. Python environment**

```bash
cd project_root
python -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

---

## Usage

### Analytical Bot

```bash
cd src
python main.py
```

- Runs every minute, logs to console/file, cleans DB hourly.
- Sends Telegram alerts when entry signals are generated.

### Trading Bot

1. Start the Node.js wrapper:
   ```bash
   cd src
   node meteora_wrapper.js
   ```
2. In a separate terminal, run the Python strategy:
   ```bash
   python solana_test.py
   ```

- Opens initial BID position, then rebalances according to price movements.
- Gracefully shuts down wrapper on exit.

---

## Modules

- \`\`
  - `meteora_api.py`: Fetch and filter pairs from Meteora.
- \`\`
  - Filtering, sorting, entry signal generation.
- \`\`
  - Telegram notifier client.
- \`\`
  - [In wrapper] Core functions to interact with DLMM pools.
- \`\`
  - Position management strategies (BID/SPOT).

---

## Database

- Uses SQLite (`meteora_bot.db`).
- Table \`\` tracks:
  - `coin_id`, `stage`, `current_ratio`, `price_history` (JSON).
- Reset logic in `main.py` and via hourly clear.

---

## Logging

- Configured via `src/logger.py`.
- Writes to console; can be extended to file/RotatingFileHandler.
- Verbose logs for debugging DLMM interactions.

---

## Testing

- `test_telegram.py`: validate Telegram notifications.
- Additional unit tests can be added under `tests/`.

---

## License

Distributed under the MIT License.

---

*Happy trading!*

