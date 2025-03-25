# Magic Mirror

A tool to mirror websites.
You need to have wget installed.

`php_refactor` is totally experimental.

**Don't use any component of this package in production!!**

## Installation

```bash
pip install -r requirements.txt
```

Copy `config.ini.example` to `config.ini` and fill in the domains you want to mirror in the `domains_to_mirror` field, separated by commas.

## Usage

```bash
python main.py
```

## License

MIT
