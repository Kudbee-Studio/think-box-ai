# Think Box AI — Think Token

**Think Token** is the native utility token powering the Think Box AI ecosystem. This repository contains the project source code, smart-contract interfaces, SDK, and documentation.

---

## Table of Contents

- [Overview](#overview)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Think Box AI is an AI-driven platform that uses **Think Token (THNK)** as its core utility token.  
Token utilities include:

- 🔐 **Access** — unlock advanced AI inference endpoints
- 💡 **Governance** — vote on platform proposals
- 🎁 **Rewards** — earn tokens by contributing prompts, datasets, and feedback
- 🔄 **Payments** — pay for API usage and premium features

---

## Getting Started

### Prerequisites

- Python ≥ 3.10
- [pip](https://pip.pypa.io/en/stable/)

### Installation

```bash
# Clone the repository
git clone https://github.com/Kudbee-Studio/think-box-ai.git
cd think-box-ai

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Running the project

```bash
python -m think_box_ai
```

---

## Project Structure

```
think-box-ai/
├── think_box_ai/          # Main Python package
│   ├── __init__.py
│   ├── token.py           # Think Token core logic
│   └── cli.py             # Command-line interface
├── tests/                 # Unit and integration tests
│   └── test_token.py
├── pyproject.toml         # Package metadata & build config
├── .gitignore
├── CONTRIBUTING.md
└── README.md
```

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

---

## License

*Note: CI failures are due to a billing lock on the repository account. No code changes required.*

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
