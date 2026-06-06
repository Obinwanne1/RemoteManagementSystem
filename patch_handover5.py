#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fix 3 missed patches in HANDOVER_GUIDE."""

PATH = r'C:\Users\rigwe\Desktop\RemoteManagementSystem\HANDOVER_GUIDE.md'

with open(PATH, encoding='utf-8') as f:
    content = f.read()

original_len = len(content)
applied = []

def patch(old, new, label):
    global content
    if old not in content:
        print(f"  MISS: {label} -- old not found")
        return False
    content = content.replace(old, new, 1)
    applied.append(label)
    return True

# ── 1. Login MFA note -- straight quotes, em-dash ────────────────────────────
patch(
    '7. Correct credentials take you to the RMM Dashboard.\n'
    '8. "Invalid credentials" means wrong email or password. Check Caps Lock.\n'
    '\n'
    '> **NOTE:** Your session token is stored in browser memory only \u2014 it is not in the URL. '
    'If you share a page URL, the recipient must log in with their own credentials.',

    '7. If your account has **Multi-Factor Authentication (MFA)** enabled, you will see a '
    'second screen asking for a 6-digit code from your authenticator app. '
    'Enter the code and click **Verify \u2192**. See Chapter 9a for full MFA details.\n'
    '8. Correct credentials (and MFA code if required) take you to the RMM Dashboard.\n'
    '9. "Invalid credentials" means wrong email or password. Check Caps Lock.\n'
    '\n'
    '> **NOTE:** Your session is maintained in browser memory. '
    'If you share a page URL, the recipient must log in with their own credentials.',
    'login MFA note'
)

# ── 2. Superadmin env note ────────────────────────────────────────────────────
# From debug: ends with "on next startup.\n\n**Emergency password reset"
patch(
    'The account will be updated on next startup.\n'
    '\n'
    '**Emergency password reset (when locked out of the web interface):**',
    'The account will be updated on next startup.\n'
    '\n'
    '> **IMPORTANT:** `SUPERADMIN_PASSWORD` must be set before starting the API. '
    'If it is missing or blank, the API will raise a `RuntimeError` and refuse to start. '
    'Minimum length is 10 characters.\n'
    '\n'
    '**Emergency password reset (when locked out of the web interface):**',
    'superadmin env IMPORTANT note'
)

# ── 3. Alerts CSV export -- straight quotes ───────────────────────────────────
patch(
    '### Step-by-step: Acknowledging an Alert\n'
    '\n'
    'Acknowledging means "I have seen this and I am dealing with it."',
    '### Exporting Alerts to CSV\n'
    '\n'
    'A **Download CSV** button at the top of the Active Alerts tab exports all '
    'currently-filtered alerts to a CSV file with: device, rule name, severity, '
    'status, and triggered date.\n'
    '\n'
    '### Step-by-step: Acknowledging an Alert\n'
    '\n'
    'Acknowledging means "I have seen this and I am dealing with it."',
    'alerts CSV export'
)

# Save
with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'SAVED. {len(applied)} patches applied. Size: {len(content)} (was {original_len})')
print('Applied:', applied)
