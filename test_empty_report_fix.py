#!/usr/bin/env python3
"""
Test fix for empty report generation bug
Bug: Tasks without comments resulted in empty report_text even with title+description
Fix: Changed condition from <= 2 to <= 1 (allow header + title)
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.services.task_reports_service import TaskReportsService

async def test_report_generation():
    """Test report generation with various scenarios"""
    service = TaskReportsService()

    print("=" * 80)
    print("Testing _generate_report_text() fix for empty reports")
    print("=" * 80)

    # Scenario 1: Title only (no description, no comments) - SHOULD GENERATE
    print("\n📝 Test 1: Title only (no description, no comments)")
    print("-" * 80)
    report = await service._generate_report_text(
        title="Fix authentication bug",
        description=None,
        comments=[],
        sequence_id=123
    )
    print(f"Result length: {len(report)}")
    print(f"Expected: > 0 (header + title is meaningful)")
    if len(report) > 0:
        print("✅ PASS: Report generated")
        print(f"Preview:\n{report[:200]}")
    else:
        print("❌ FAIL: Report should have been generated")

    # Scenario 2: Title + short description (<=10 chars) - SHOULD GENERATE
    print("\n📝 Test 2: Title + very short description")
    print("-" * 80)
    report = await service._generate_report_text(
        title="Fix bug",
        description="Done",  # Only 4 chars
        comments=[],
        sequence_id=124
    )
    print(f"Result length: {len(report)}")
    print(f"Expected: > 0 (title exists, description too short but title is meaningful)")
    if len(report) > 0:
        print("✅ PASS: Report generated")
        print(f"Preview:\n{report[:200]}")
    else:
        print("❌ FAIL: Report should have been generated")

    # Scenario 3: Title + longer description (>10 chars) - SHOULD GENERATE
    print("\n📝 Test 3: Title + meaningful description (>10 chars)")
    print("-" * 80)
    report = await service._generate_report_text(
        title="Implement new feature",
        description="Added authentication system with JWT tokens",
        comments=[],
        sequence_id=125
    )
    print(f"Result length: {len(report)}")
    print(f"Expected: > 0 (header + title + description)")
    if len(report) > 0:
        print("✅ PASS: Report generated")
        print(f"Preview:\n{report[:200]}")
    else:
        print("❌ FAIL: Report should have been generated")

    # Scenario 4: No title, no description - SHOULD NOT GENERATE
    print("\n📝 Test 4: No title, no description (header only)")
    print("-" * 80)
    report = await service._generate_report_text(
        title=None,
        description=None,
        comments=[],
        sequence_id=126
    )
    print(f"Result length: {len(report)}")
    print(f"Expected: 0 (only header, no meaningful content)")
    if len(report) == 0:
        print("✅ PASS: Empty report (as expected)")
    else:
        print("❌ FAIL: Report should be empty (no title)")
        print(f"Preview:\n{report[:200]}")

    # Scenario 5: Title + 1 comment - SHOULD GENERATE
    print("\n📝 Test 5: Title + 1 comment")
    print("-" * 80)
    report = await service._generate_report_text(
        title="Fix login issue",
        description=None,
        comments=[
            {
                'comment_html': '<p>Fixed login validation</p>',
                'actor_detail': {'display_name': 'Test User'},
                'created_at': '2025-10-09T12:00:00Z'
            }
        ],
        sequence_id=127
    )
    print(f"Result length: {len(report)}")
    print(f"Expected: > 0 (header + title + comment)")
    if len(report) > 0:
        print("✅ PASS: Report generated")
        print(f"Preview:\n{report[:300]}")
    else:
        print("❌ FAIL: Report should have been generated")

    print("\n" + "=" * 80)
    print("Test completed!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_report_generation())
