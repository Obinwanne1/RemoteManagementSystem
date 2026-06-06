#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix missed sync_patch_status patch."""

PATH = r'C:\Users\rigwe\Desktop\RemoteManagementSystem\TECHNICAL_GUIDE.md'

with open(PATH, encoding='utf-8') as f:
    content = f.read()

old = (
    "#### `sync_patch_status()`\n"
    "- Iterates all active `PatchPolicy` records\n"
    "- For each policy's scope (customer or global):\n"
    "  - Auto-approves `PatchRecord` rows where `status='pending'` matching policy flags\n"
    "  - Respects `excluded_software` name patterns"
)
new = (
    "#### `sync_patch_status()`\n"
    "- Iterates all active `PatchPolicy` records\n"
    "- **Maintenance window enforcement:** checks `PatchPolicy.maintenance_window` JSON\n"
    "  (`{\"day\": \"sunday\", \"time\": \"02:00\", \"duration_hours\": 4}`) via helper\n"
    "  `_within_maintenance_window(window: dict | None) -> bool`. If current UTC time is\n"
    "  outside the configured window, the policy is silently skipped for that cycle.\n"
    "- For each policy's scope (customer or global):\n"
    "  - Auto-approves `PatchRecord` rows where `status='pending'` matching policy flags\n"
    "  - Respects `excluded_software` name patterns"
)

assert old in content, "sync_patch_status section not found"
content = content.replace(old, new, 1)

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("SAVED. sync_patch_status maintenance window applied.")
