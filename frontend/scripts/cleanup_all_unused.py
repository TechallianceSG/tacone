#!/usr/bin/env python3
"""Comprehensive i18n cleanup: remove all unused keys while protecting data dictionary keys."""

import json
import os

I18N_DIR = '/Users/wangchen/Desktop/TACAI/tacone/frontend/src/i18n'
LANGS = ['en', 'ja', 'zh']
REFS_FILE = '/tmp/all_refs.txt'

# Load all referenced keys from source code
with open(REFS_FILE) as f:
    raw_refs = set(l.strip() for l in f if l.strip())

# Filter: only dotted keys (real i18n keys, not URLs/paths/artifacts)
used_refs = {r for r in raw_refs if '.' in r}

# Namespaces protected as data dictionary for MSG[locale][key] lookups
# These are accessed dynamically via field metadata, not via t() calls
PROTECTED_PREFIXES = (
    'field.',          # Field label data dictionary
    'detail.group.',   # Detail group labels
    'form.group.',     # Form group labels
    'section.',        # Section labels
)

for lang in LANGS:
    path = os.path.join(I18N_DIR, f'{lang}.json')
    print(f'Processing {lang}...')

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    original_count = len(data)
    to_delete = []

    for key in data:
        # Keep if referenced in source code
        if key in used_refs:
            continue
        # Keep if protected data dictionary key
        if key.startswith(PROTECTED_PREFIXES):
            continue
        # Mark for deletion
        to_delete.append(key)

    for key in to_delete:
        del data[key]

    # Sort keys alphabetically
    sorted_data = dict(sorted(data.items(), key=lambda x: x[0]))

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sorted_data, f, indent=2, ensure_ascii=False)
        f.write('\n')

    new_count = len(sorted_data)
    print(f'  {original_count} → {new_count} keys ({len(to_delete)} deleted)')

print('\nDone.')
