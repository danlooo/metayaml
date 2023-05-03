#!/usr/bin/env python

#
# Collect meta data attributes of files or directories stored in meta.yml files
# More specific attributes override those from its parent directories
#

import click
import yaml
import os
from pathlib import Path
import logging
from cachetools import cached, TTLCache
from datetime import datetime, timedelta

def parse_string(s):
    if s in ["True", "False"]:
        return bool(s)
    try:
        return(float(s))
    except ValueError:
        return s

def merge(a, b, key = None):
    if a is not None and b is None:
        return a
    elif b is not None and a is None:
        return b
    else:
        logging.info(f"overwrite {key} from '{b}' to '{a}'")
        return a

@cached(cache=TTLCache(maxsize=1e6, ttl=timedelta(hours=1), timer=datetime.now))
def get_meta_data(path):
    yml_paths = []
    if os.path.isfile(path):
        yml_paths = [os.path.abspath(path) + ".yml"]
    else:
        yml_paths = [os.path.abspath(path) + "/meta.yml"]

    yml_paths += [os.path.abspath(path) + ".yaml"]
    yml_paths += [os.path.abspath(path) + ".meta.yml"]
    yml_paths += [os.path.abspath(path) + ".meta.yaml"]

    yml_paths += [f"{x}/meta.yml" for x in Path(os.path.abspath(path)).parents]
    yml_paths += [f"{x}/meta.yaml" for x in Path(os.path.abspath(path)).parents]

    yml_paths = [x for x in yml_paths if os.path.exists(x)]
    yml_paths.reverse() # child overrides parent

    d = {}
    for yml_path in yml_paths:        
        with open(yml_path, "r") as f:
            cur_d = yaml.safe_load(f)
            keys = set((*d.keys(), *cur_d.keys()))
            d = {k: merge(cur_d.get(k), d.get(k), k)  for k in keys}
    return d

@click.group()
def main():
    logging.basicConfig(filename="/dev/stderr", encoding="utf-8", level=logging.DEBUG)

@main.command()
@click.argument("arg1", required = True)
@click.argument("operator", default = "=", type=click.Choice(["=", "is", "in", "<", ">", "<=", ">="]))
@click.argument("arg2", required = True)
@click.option("--directory", "-d", default=".", show_default=True, help="Search everything recursiveley inside this root directory")
def find(arg1, operator, arg2, directory):
    """
    Find files and directories based on a specific attribute stored in YAML meta data sidecar files.
    """
    if not os.path.isdir(directory):
        raise ValueError("Must be a directory path and not a file.")

    # handle strings
    already_harmonized = lambda x: x.startswith("\"") and x.endswith("\"")
    harmonize_string = lambda x: f"\"{x}\"" if isinstance(x, str) and not already_harmonized(x) else x

    arg1 = parse_string(arg1)
    arg2 = parse_string(arg2)
 
    if operator in ["=", "is"] and isinstance(arg2, bool):
         expr = f"m.get({harmonize_string(arg1)}) == {arg2}"
    elif operator in ["=", "is"]:
        expr = f"m.get({harmonize_string(arg1)}) == {harmonize_string(arg2)}"
    elif operator in ["<", ">", "<=", ">=", "=", "is", "=="] and isinstance(arg2, float):
        expr = f"m.get({harmonize_string(arg1)}) {operator} {harmonize_string(arg2)}"
    elif operator == "in":
        expr = f'{harmonize_string(arg1)} in m.get({harmonize_string(arg2)})'
    else:
        raise ValueError("Operator and arguments do not match")
    
    for path in Path(directory).rglob("*meta.yml"):
        m = get_meta_data(path)
        try:
            if eval(expr):
                print(path.parents[0])
        except:
            continue

@main.command()
@click.argument("path", type=click.Path(exists=True)) 
def get(path):
    """
    Retrieves attributes of a directory or file based on YAML meta data sidecar files.
    """
    d = get_meta_data(path)
    print(yaml.dump(d))

if __name__ == '__main__':
    main()
