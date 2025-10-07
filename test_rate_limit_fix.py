#!/usr/bin/env python3
"""Test script to verify rate limiting fixes"""
import asyncio
from app.integrations.plane import plane_api

async def main():
    print("🔍 Testing rate limit fixes for zarudesu@gmail.com...")
    print("=" * 60)

    try:
        tasks = await plane_api.get_user_tasks("zarudesu@gmail.com")
        print(f"\n✅ SUCCESS: Retrieved {len(tasks)} tasks without rate limit errors!")
        print(f"📋 Tasks retrieved successfully")

        if tasks:
            print(f"\n📝 First few tasks:")
            for i, task in enumerate(tasks[:3], 1):
                print(f"  {i}. {task.name} (#{task.sequence_id})")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
