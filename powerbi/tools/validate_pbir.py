"""Validates every PBIR JSON file of the report against its published Microsoft schema.

Needs internet access and: pip install jsonschema referencing
"""
import json
import urllib.request
from pathlib import Path

from jsonschema import Draft7Validator, Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

REPORT = Path(__file__).resolve().parents[1] / "OrdenesRetiro.Report"
cache = {}


def retrieve(uri):
    url = uri.split("#")[0].replace("https://developer.microsoft.com/json-schemas/",
                                    "https://raw.githubusercontent.com/microsoft/json-schemas/main/")
    if url not in cache:
        with urllib.request.urlopen(url) as resp:
            cache[url] = json.loads(resp.read().decode("utf-8-sig"))
    return Resource.from_contents(cache[url], default_specification=DRAFT7)


registry = Registry(retrieve=retrieve)
errors = 0
files = [REPORT / "definition.pbir"] + sorted((REPORT / "definition").rglob("*.json"))
for path in files:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if "$schema" not in doc:
        print(f"skip {path.relative_to(REPORT)} (no $schema)")
        continue
    schema = retrieve(doc["$schema"]).contents
    cls = Draft202012Validator if "2020-12" in str(schema.get("$schema", "")) else Draft7Validator
    validator = cls(schema, registry=registry)
    problems = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    rel = path.relative_to(REPORT)
    if problems:
        errors += len(problems)
        print(f"FAIL {rel}")
        for e in problems[:5]:
            print("   ", "/".join(map(str, e.path)), "->", e.message[:300])
    else:
        print(f"ok   {rel}")
print("errors:", errors)
