#!/usr/bin/env python3
"""
Fetch workspace members and projects from Plane API
"""
import asyncio
import os
from app.integrations.plane import plane_api

async def fetch_all_data():
    """Fetch workspace members and projects"""

    if not plane_api.configured:
        print("❌ Plane API not configured!")
        return

    print(f"📡 Plane API configured:")
    print(f"   URL: {plane_api.api_url}")
    print(f"   Workspace: {plane_api.workspace_slug}")
    print()

    # Fetch workspace members
    print("👥 Fetching workspace members...")
    members = await plane_api.get_workspace_members()

    if members:
        print(f"\n✅ Found {len(members)} workspace members:\n")
        for idx, member in enumerate(members, 1):
            display_name = member.get('member', {}).get('display_name') or member.get('member', {}).get('first_name', 'Unknown')
            email = member.get('member', {}).get('email', 'No email')
            user_id = member.get('member', {}).get('id', 'No ID')
            role = member.get('role', 'No role')

            print(f"  {idx}. {display_name}")
            print(f"     Email: {email}")
            print(f"     Role: {role}")
            print(f"     ID: {user_id[:8]}...")
            print()
    else:
        print("❌ No members found")

    # Fetch projects
    print("\n📋 Fetching projects...")
    projects = await plane_api.get_all_projects()

    if projects:
        print(f"\n✅ Found {len(projects)} projects:\n")
        for idx, project in enumerate(projects, 1):
            name = project.get('name', 'Unknown')
            proj_id = project.get('id', 'No ID')
            description = project.get('description', '')

            print(f"  {idx}. {name}")
            print(f"     ID: {proj_id[:8]}...")
            if description:
                desc_short = description[:80] + "..." if len(description) > 80 else description
                print(f"     Description: {desc_short}")
            print()
    else:
        print("❌ No projects found")

if __name__ == "__main__":
    asyncio.run(fetch_all_data())
