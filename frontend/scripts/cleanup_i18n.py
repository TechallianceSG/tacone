#!/usr/bin/env python3
"""Clean up i18n JSON files: consolidate validation.invalid_* into reusable key, remove dead keys."""

import json
import os
import sys

I18N_DIR = os.path.join(os.path.dirname(__file__), '..', 'src', 'i18n')
LANGS = ['en', 'ja', 'zh']

# Keys to KEEP (actually used in source code)
KEEP_VALIDATION = {
    'validation.invalid_login',
    'validation.change_ack_required',
    'validation.parent_department_required',
    'validation.parent_entity_required',
}

# New reusable key to ADD
NEW_KEY = 'validation.invalid'
NEW_VALUES = {
    'en': '{field} is invalid',
    'ja': '{field}が正しくありません',
    'zh': '{field}不正确',
}


def load_json(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: str, data: dict):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def get_keys_to_delete(data: dict) -> set:
    """Identify all dead validation.* keys and unused *invalid* keys."""
    to_delete = set()

    for key in data:
        # validation.* keys except the 4 kept ones
        if key.startswith('validation.') and key not in KEEP_VALIDATION:
            to_delete.add(key)

        # Cross-namespace *invalid* keys that are unused dead code
        if key in {
            'clock_entry.invalid_date',
            'onboarding.email_cc_invalid',
            'onboarding.email_invalid_recipient',
            'onboarding.invalid_link_description',
            'onboarding.invalid_link_title',
            'onboarding.verification_invalid',
            'system_parameters.validation.department_manager_cc_invalid',
        }:
            to_delete.add(key)

    return to_delete


def main():
    for lang in LANGS:
        path = os.path.join(I18N_DIR, f'{lang}.json')
        print(f'Processing {lang}.json...')

        data = load_json(path)
        original_count = len(data)

        # Identify keys to delete
        to_delete = get_keys_to_delete(data)
        deleted_count = 0
        for key in to_delete:
            if key in data:
                del data[key]
                deleted_count += 1

        # Add new reusable key
        if NEW_KEY in data:
            print(f'  WARNING: {NEW_KEY} already exists, overwriting')
        data[NEW_KEY] = NEW_VALUES[lang]

        # Sort keys alphabetically (maintain existing convention)
        sorted_data = dict(sorted(data.items(), key=lambda x: x[0]))

        save_json(path, sorted_data)
        new_count = len(sorted_data)
        print(f'  {original_count} → {new_count} keys ({deleted_count} deleted, 1 added)')

    print('\nDone. All three files updated.')


if __name__ == '__main__':
    main()
