"""List and optionally fix users with admin flags.

Usage:
    python scripts/list_staff_users.py           # just list
    python scripts/list_staff_users.py --fix     # clear is_staff for non-superusers (destructive!)

Run from project root where `manage.py` exists.
"""
import os
import sys
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'redmovierec_project.settings')

import django
django.setup()

from django.contrib.auth.models import User

parser = argparse.ArgumentParser(description='List or fix users with is_staff/is_superuser flags')
parser.add_argument('--fix', action='store_true', help='Clear is_staff for non-superusers')
args = parser.parse_args()

staff_users = User.objects.filter(is_staff=True)
if not staff_users.exists():
    print('No users with is_staff=True found.')
else:
    print('Users with is_staff=True:')
    for u in staff_users:
        print(f" - {u.username}: is_superuser={u.is_superuser}")

if args.fix:
    confirm = input('This will clear is_staff=True for all non-superusers. Continue? [y/N]: ')
    if confirm.lower() != 'y':
        print('Aborted.')
        sys.exit(0)

    changed = 0
    for u in staff_users:
        if not u.is_superuser:
            u.is_staff = False
            u.save()
            changed += 1
            print(f'Cleared is_staff for {u.username}')
    print(f'Done. Cleared is_staff for {changed} user(s).')
