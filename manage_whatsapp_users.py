#!/usr/bin/env python
# manage_whatsapp_users.py
"""
CLI tool for managing WhatsApp user permissions
Production-ready user administration
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from integrations.whatsapp.authorization import WhatsAppAuthorization
import argparse

def main():
    parser = argparse.ArgumentParser(
        description='Manage WhatsApp user permissions and LGPD clearance levels',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add new user with ALTO clearance
  python manage_whatsapp_users.py add 5511999999999 "John Doe" --clearance ALTO --department TI
  
  # Add admin user
  python manage_whatsapp_users.py add 5511888888888 "Admin User" --clearance ALTO --admin
  
  # List all users
  python manage_whatsapp_users.py list
  
  # Disable user
  python manage_whatsapp_users.py disable 5511999999999
  
  # Remove user
  python manage_whatsapp_users.py remove 5511999999999
  
  # Check user permissions
  python manage_whatsapp_users.py check 5511999999999

Clearance Levels:
  BAIXO  - Can access only aggregated/public data
  MEDIO  - Can access order numbers and values
  ALTO   - Full access to customer names and sensitive data
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Add user
    add_parser = subparsers.add_parser('add', help='Add or update user')
    add_parser.add_argument('phone', help='Phone number (e.g., 5511999999999)')
    add_parser.add_argument('name', help='User name')
    add_parser.add_argument('--clearance', choices=['BAIXO', 'MEDIO', 'ALTO'], 
                           default='BAIXO', help='LGPD clearance level')
    add_parser.add_argument('--department', default='N/A', help='User department')
    add_parser.add_argument('--admin', action='store_true', help='Make user an admin')
    
    # Remove user
    remove_parser = subparsers.add_parser('remove', help='Remove user')
    remove_parser.add_argument('phone', help='Phone number')
    
    # Disable user
    disable_parser = subparsers.add_parser('disable', help='Disable user')
    disable_parser.add_argument('phone', help='Phone number')
    
    # Enable user
    enable_parser = subparsers.add_parser('enable', help='Enable user')
    enable_parser.add_argument('phone', help='Phone number')
    
    # List users
    list_parser = subparsers.add_parser('list', help='List all users')
    list_parser.add_argument('--format', choices=['table', 'json'], default='table',
                            help='Output format')
    
    # Check user
    check_parser = subparsers.add_parser('check', help='Check user permissions')
    check_parser.add_argument('phone', help='Phone number')
    
    # Reload
    reload_parser = subparsers.add_parser('reload', help='Reload permissions from file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize authorization system
    auth = WhatsAppAuthorization()
    
    # Execute command
    if args.command == 'add':
        # Normalize phone
        phone = args.phone
        if '@' not in phone:
            phone = f"{phone}@s.whatsapp.net"
        
        success = auth.add_user(
            phone_number=phone,
            name=args.name,
            clearance_level=args.clearance,
            department=args.department,
            is_admin=args.admin
        )
        
        if success:
            print(f"✓ User added/updated successfully:")
            print(f"  Phone: {phone}")
            print(f"  Name: {args.name}")
            print(f"  Clearance: {args.clearance}")
            print(f"  Department: {args.department}")
            print(f"  Admin: {args.admin}")
        else:
            print("✗ Failed to add user", file=sys.stderr)
            sys.exit(1)
    
    elif args.command == 'remove':
        phone = args.phone
        if '@' not in phone:
            phone = f"{phone}@s.whatsapp.net"
        
        success = auth.remove_user(phone)
        
        if success:
            print(f"✓ User {phone} removed successfully")
        else:
            print(f"✗ User {phone} not found", file=sys.stderr)
            sys.exit(1)
    
    elif args.command == 'disable':
        phone = args.phone
        if '@' not in phone:
            phone = f"{phone}@s.whatsapp.net"
        
        success = auth.disable_user(phone)
        
        if success:
            print(f"✓ User {phone} disabled")
        else:
            print(f"✗ User {phone} not found", file=sys.stderr)
            sys.exit(1)
    
    elif args.command == 'enable':
        phone = args.phone
        if '@' not in phone:
            phone = f"{phone}@s.whatsapp.net"
        
        success = auth.enable_user(phone)
        
        if success:
            print(f"✓ User {phone} enabled")
        else:
            print(f"✗ User {phone} not found", file=sys.stderr)
            sys.exit(1)
    
    elif args.command == 'list':
        users = auth.list_users()
        
        if not users:
            print("No users registered")
            return
        
        if args.format == 'json':
            import json
            print(json.dumps(users, indent=2, ensure_ascii=False))
        else:
            # Table format
            print(f"\n{'Phone':<35} {'Name':<20} {'Clearance':<10} {'Dept':<15} {'Enabled':<8} {'Admin':<6}")
            print("-" * 110)
            
            for user in users:
                enabled_str = "Yes" if user['enabled'] else "No"
                admin_str = "Yes" if user['is_admin'] else "No"
                
                print(f"{user['phone']:<35} {user['name']:<20} {user['clearance']:<10} "
                      f"{user['department']:<15} {enabled_str:<8} {admin_str:<6}")
            
            print(f"\nTotal: {len(users)} users")
    
    elif args.command == 'check':
        phone = args.phone
        if '@' not in phone:
            phone = f"{phone}@s.whatsapp.net"
        
        context = auth.get_user_context(phone)
        
        print(f"\nUser: {phone}")
        print(f"  Name: {context.get('user_name', 'Unknown')}")
        print(f"  Clearance: {context.get('lgpd_clearance', 'BAIXO')}")
        print(f"  Department: {context.get('department', 'N/A')}")
        print(f"  Enabled: {context.get('enabled', False)}")
        print(f"  Admin: {context.get('is_admin', False)}")
        
        # Show what user can access
        print(f"\nAccess Permissions:")
        clearance = context.get('lgpd_clearance', 'BAIXO')
        if clearance == 'BAIXO':
            print("  ✓ Aggregated data")
            print("  ✗ Order numbers and values")
            print("  ✗ Customer names and sensitive data")
        elif clearance == 'MEDIO':
            print("  ✓ Aggregated data")
            print("  ✓ Order numbers and values")
            print("  ✗ Customer names and sensitive data")
        else:  # ALTO
            print("  ✓ Aggregated data")
            print("  ✓ Order numbers and values")
            print("  ✓ Customer names and sensitive data (FULL ACCESS)")
    
    elif args.command == 'reload':
        auth.reload_permissions()
        print("✓ Permissions reloaded")
        print(f"  Loaded {len(auth.users)} users")

if __name__ == '__main__':
    main()
