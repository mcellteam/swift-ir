#!/usr/bin/env python3

import csv
import json
import xml.etree.ElementTree as ET

PARSERS = {}

def parse_csv(file_path):
    with open(file_path, mode='r') as file:
        reader = csv.reader(file)
        return list(reader)


def parse_json(file_path):
    with open(file_path, mode='r') as file:
        return json.load(file)


def parse_xml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    return root


def register_parser(file_type):
    def decorator(fn):
        PARSERS[file_type] = fn
        return fn

    return decorator


@register_parser('csv')
def csv_parser(file_path):
    return parse_csv(file_path)


@register_parser('json')
def json_parser(file_path):
    return parse_json(file_path)


@register_parser('xml')
def xml_parser(file_path):
    return parse_xml(file_path)


def get_parser(file_type):
    return PARSERS.get(file_type)