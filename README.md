# Grapher

This repository contains the **grapher.py** script.
This script is able to create automatically a set of graphs from data stored in InfluxDB and save them as images.

**Note: This project was created for fast post-processing of raw data stored inside InfluxDB in a particular use-case (my Ph.D. study), but can be used for other data too.**

## Installation

Create and activate a virtual environment for the project.

```console
$ python -m venv venv/grapher
$ source venv/grapher/bin/activate
```

Install the script using python's setuptools.

```console
$ python setup.py install
```

After installation the script can be run like any normal command:

```console
$ grapher.py --help
```

## Usage

1. Obtain the raw data from InfluxDB as a `.csv` file.
2. Run the script with custom parameters:
```console
$ grapher.py raw.csv -o out
```
3. Profit (?)
