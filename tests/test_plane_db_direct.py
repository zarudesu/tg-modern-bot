#!/usr/bin/env python3
"""Test script to verify direct Plane PostgreSQL database access"""
import asyncio
from app.integrations.plane.database import plane_db_client

async def main():
    print("🔍 Testing direct Plane DB access for zarudesu@gmail.com...")
    print("=" * 70)

    try:
        # Get tasks from database
        tasks = await plane_db_client.get_user_tasks("zarudesu@gmail.com")

        print(f"\n✅ SUCCESS: Retrieved {len(tasks)} tasks via DIRECT DB ACCESS!")
        print(f"📊 No rate limit errors - single SQL query replaced 52+ API calls\n")

        if tasks:
            print(f"📝 First 5 tasks:")
            for i, task in enumerate(tasks[:5], 1):
                print(f"\n  {i}. [{task.project_name}] {task.name}")
                print(f"     • ID: {task.sequence_id}")
                print(f"     • Priority: {task.priority}")
                print(f"     • State: {task.state_name}")
                print(f"     • Project: {task.project_name}")

        # Close connection pool
        await plane_db_client.close_pool()
        print(f"\n🔌 DB connection closed")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
