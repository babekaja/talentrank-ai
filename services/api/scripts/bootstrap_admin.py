"""Provision a first organization and its administrator; CLI only, not an HTTP route."""
import argparse
import getpass
import sys
import re
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Organization, OrganizationMember, User


def main():
    parser = argparse.ArgumentParser(description='Create initial tenant and org_admin')
    parser.add_argument('--organization', required=True)
    parser.add_argument('--slug', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--password-stdin',action='store_true',
                        help='Read password from standard input (automated synthetic testing only)')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]{2,80}', args.slug):
        parser.error('slug: 2-80 lowercase letters, digits or hyphens')
    if '@' not in args.email:
        parser.error('Invalid email')
    password = sys.stdin.readline().rstrip('\r\n') if args.password_stdin else getpass.getpass('Password (12 characters minimum): ')
    if len(password) < 12:
        parser.error('Password is too short')
    with SessionLocal.begin() as db:
        if db.scalar(select(Organization).where(Organization.slug == args.slug)):
            parser.error('Organization slug exists')
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if not user:
            user = User(email=args.email.strip().lower(), full_name=args.name.strip(), password_hash=hash_password(password))
            db.add(user)
            db.flush()
        org = Organization(name=args.organization.strip(), slug=args.slug)
        db.add(org)
        db.flush()
        db.add(OrganizationMember(user_id=user.id, organization_id=org.id, role='org_admin'))
    print('Organization and administrator created.')


if __name__ == '__main__':
    main()
