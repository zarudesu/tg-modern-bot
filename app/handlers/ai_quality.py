"""
AI Quality Analytics — /ai_quality command.

Analyzes DetectedIssue records to compute AI detection quality metrics:
precision, detection rate, confidence distribution, correction distance.
"""

from datetime import datetime, timedelta, timezone
from collections import defaultdict

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy import select

from ..config import settings
from ..utils.logger import bot_logger
from ..database.chat_ai_models import DetectedIssue
from ..database.database import AsyncSessionLocal

router = Router(name="ai_quality")


async def compute_quality_metrics(days: int = 30) -> dict:
    """Compute AI detection quality metrics from DetectedIssue records."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DetectedIssue)
            .where(DetectedIssue.created_at >= cutoff)
            .order_by(DetectedIssue.created_at)
        )
        issues = result.scalars().all()

    if not issues:
        return {"total": 0, "days": days}

    # Feedback distribution
    feedback_counts = defaultdict(int)
    for issue in issues:
        fb = issue.user_feedback or "no_feedback"
        feedback_counts[fb] += 1

    total = len(issues)
    accepted = feedback_counts.get("accepted", 0)
    rejected = feedback_counts.get("rejected", 0)
    corrected = feedback_counts.get("corrected", 0)
    no_feedback = feedback_counts.get("no_feedback", 0)

    # Precision: accepted / (accepted + rejected)
    decided = accepted + rejected
    precision = (accepted / decided * 100) if decided > 0 else None

    # Detection rate
    detection_rate = total / days if days > 0 else 0

    # Confidence buckets
    buckets = [
        (0.0, 0.3, "0.0-0.3"),
        (0.3, 0.5, "0.3-0.5"),
        (0.5, 0.7, "0.5-0.7"),
        (0.7, 0.9, "0.7-0.9"),
        (0.9, 1.01, "0.9-1.0"),
    ]
    confidence_stats = []
    for low, high, label in buckets:
        bucket_issues = [
            i for i in issues
            if i.confidence is not None and low <= i.confidence < high
        ]
        if not bucket_issues:
            continue
        bucket_accepted = sum(1 for i in bucket_issues if i.user_feedback == "accepted")
        bucket_decided = sum(
            1 for i in bucket_issues if i.user_feedback in ("accepted", "rejected")
        )
        accept_rate = (bucket_accepted / bucket_decided * 100) if bucket_decided > 0 else None
        confidence_stats.append({
            "label": label,
            "count": len(bucket_issues),
            "accept_rate": accept_rate,
        })

    # Correction distance
    correction_distances = [
        i.correction_distance
        for i in issues
        if i.correction_distance is not None
    ]
    avg_correction = (
        sum(correction_distances) / len(correction_distances)
        if correction_distances
        else None
    )

    # Per-model stats
    model_stats = defaultdict(lambda: {"total": 0, "accepted": 0, "rejected": 0})
    for issue in issues:
        model = issue.ai_model_used or "unknown"
        model_stats[model]["total"] += 1
        if issue.user_feedback == "accepted":
            model_stats[model]["accepted"] += 1
        elif issue.user_feedback == "rejected":
            model_stats[model]["rejected"] += 1

    return {
        "total": total,
        "days": days,
        "precision": precision,
        "detection_rate": round(detection_rate, 1),
        "feedback": {
            "accepted": accepted,
            "rejected": rejected,
            "corrected": corrected,
            "no_feedback": no_feedback,
        },
        "confidence_buckets": confidence_stats,
        "avg_correction_distance": round(avg_correction, 2) if avg_correction is not None else None,
        "models": dict(model_stats),
    }


def format_quality_report(metrics: dict) -> str:
    """Format metrics dict as HTML message."""
    if metrics["total"] == 0:
        return f"<b>AI Detection Quality ({metrics['days']} days)</b>\n\nNo data"

    lines = [f"<b>AI Detection Quality ({metrics['days']} days)</b>\n"]

    # Precision
    if metrics["precision"] is not None:
        fb = metrics["feedback"]
        decided = fb["accepted"] + fb["rejected"]
        lines.append(f"Precision: <b>{metrics['precision']:.0f}%</b> ({fb['accepted']}/{decided})")
    else:
        lines.append("Precision: N/A (no feedback)")

    lines.append(f"Detection rate: <b>{metrics['detection_rate']}/day</b>")
    lines.append(f"Total: {metrics['total']}\n")

    # Feedback
    fb = metrics["feedback"]
    total = metrics["total"]
    parts = []
    for key, label in [("accepted", "Accepted"), ("rejected", "Rejected"),
                         ("corrected", "Corrected"), ("no_feedback", "No feedback")]:
        count = fb.get(key, 0)
        pct = int(count / total * 100) if total > 0 else 0
        parts.append(f"{label} {count} ({pct}%)")
    lines.append("Feedback: " + " | ".join(parts))

    # Confidence buckets
    if metrics["confidence_buckets"]:
        lines.append("\nConfidence distribution:")
        for b in metrics["confidence_buckets"]:
            rate_str = f"{b['accept_rate']:.0f}% accepted" if b["accept_rate"] is not None else "no feedback"
            lines.append(f"  {b['label']}: {b['count']} det. ({rate_str})")

    # Correction distance
    if metrics["avg_correction_distance"] is not None:
        dist = metrics["avg_correction_distance"]
        quality = "minor edits" if dist < 0.3 else "moderate edits" if dist < 0.6 else "major rewrites"
        lines.append(f"\nAvg correction: {dist} ({quality})")

    # Models
    if metrics["models"]:
        lines.append("\nModels:")
        for model, stats in metrics["models"].items():
            decided = stats["accepted"] + stats["rejected"]
            if decided > 0:
                prec = stats["accepted"] / decided * 100
                lines.append(f"  {model}: {stats['total']} det. | {prec:.0f}% precision")
            else:
                lines.append(f"  {model}: {stats['total']} det. | no feedback")

    return "\n".join(lines)


@router.message(Command("ai_quality"))
async def cmd_ai_quality(message: Message):
    """
    /ai_quality [days] — AI detection quality report.
    Admin-only. Default: last 30 days.
    """
    if not settings.is_admin(message.from_user.id):
        await message.answer("Admin only")
        return

    args = message.text.split(maxsplit=1)
    days = 30
    if len(args) > 1:
        try:
            days = int(args[1].strip())
        except ValueError:
            await message.answer("Usage: /ai_quality [days]")
            return

    status_msg = await message.answer(f"Analyzing AI quality ({days} days)...")

    try:
        metrics = await compute_quality_metrics(days)
        report = format_quality_report(metrics)
        await status_msg.edit_text(report, parse_mode="HTML")
        bot_logger.info(f"AI quality report: {metrics['total']} issues, {days} days")
    except Exception as e:
        bot_logger.error(f"Error in ai_quality: {e}")
        import traceback
        bot_logger.error(traceback.format_exc())
        await status_msg.edit_text(f"Error: {e}")
