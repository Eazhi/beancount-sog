# Beancount SoG

`beancount-sog` is a beancount importer for Société Générale CSV files.

## Installation

```sh
$ pip install beancount-sog
```

## Usage

```python
from beancount_sog import SoGImporter

CONFIG = [SoGImporter("Assets:FR:SoG:Checking")]
```
