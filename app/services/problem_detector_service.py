"""
Problem Detector Service

AI-powered detection of problems and issues in chat messages.
Uses keyword matching + AI analysis for accurate detection.
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from ..core.ai.ai_manager import ai_manager
from ..services.chat_context_service import chat_context_service
from ..utils.logger import bot_logger


@dataclass
class DetectionResult:
    """Result of problem detection"""
    is_problem: bool
    confidence: float  # 0.0 to 1.0
    problem_type: str  # problem, urgent, question, complaint
    title: str
    description: str
    suggested_action: str  # create_task, notify_admin, auto_reply
    keywords_matched: List[str]


class ProblemDetectorService:
    """
    Service for detecting problems in chat messages.

    Detection methods:
    1. Keyword matching (fast, always runs)
    2. AI analysis (semantic, runs if keywords match or high suspicion)
    """

    # Problem keywords (Russian)
    PROBLEM_KEYWORDS = [
        # Technical issues
        "не работает", "сломалось", "ошибка", "проблема", "баг", "bug",
        "упало", "висит", "тормозит", "глючит", "не отвечает", "недоступен",
        "не запускается", "вылетает", "крашится", "crash",

        # User frustration
        "не могу", "не получается", "помогите", "help",
        "не понимаю", "как сделать", "что делать",

        # Urgency
        "срочно", "urgent", "asap", "критично", "важно",
        "немедленно", "прямо сейчас",

        # Negative sentiment
        "плохо", "ужас", "кошмар", "невозможно", "достало",
    ]

    # Question patterns
    QUESTION_PATTERNS = [
        r'\?$',  # Ends with ?
        r'^как\s',  # Starts with "как"
        r'^что\s',  # Starts with "что"
        r'^почему\s',  # Starts with "почему"
        r'^когда\s',  # Starts with "когда"
        r'^где\s',  # Starts with "где"
        r'^кто\s',  # Starts with "кто"
        r'можно ли',  # "можно ли"
        r'подскажите',  # "подскажите"
    ]

    # Urgency boosters (increase confidence)
    URGENCY_BOOSTERS = [
        "срочно", "urgent", "asap", "критично", "немедленно",
        "!!!", "CAPS",  # Special markers
    ]

    # Minimum confidence for notification
    MIN_CONFIDENCE = 0.6

    # Rate limiting
    _last_detection: Dict[int, datetime] = {}  # chat_id -> last detection time
    DETECTION_COOLDOWN = 60  # seconds between detections per chat

    async def analyze_message(
        self,
        chat_id: int,
        user_id: int,
        username: str,
        message_text: str,
        use_ai: bool = True,
        ai_only: bool = True  # NEW: Use AI-only detection (no keyword requirement)
    ) -> Optional[DetectionResult]:
        """
        Analyze a message for problems.

        Args:
            chat_id: Telegram chat ID
            user_id: User's Telegram ID
            username: User's display name
            message_text: Message content
            use_ai: Whether to use AI analysis (slower but more accurate)
            ai_only: If True, use AI for all messages (no keyword requirement)

        Returns:
            DetectionResult if problem detected, None otherwise
        """
        if not message_text or len(message_text) < 10:  # Minimum 10 chars for AI analysis
            return None

        # Rate limiting
        if not self._check_rate_limit(chat_id):
            return None

        text_lower = message_text.lower()

        # Step 1: Keyword matching (still useful for metadata)
        matched_keywords = self._match_keywords(text_lower)
        is_question = self._is_question(message_text)
        urgency_score = self._calculate_urgency(message_text)

        # Calculate base confidence from keywords
        base_confidence = min(len(matched_keywords) * 0.2 + urgency_score * 0.3, 0.7)

        # Step 2: AI analysis
        ai_result = None
        if use_ai:
            if ai_only:
                # AI-only mode: always analyze with AI (no keyword requirement)
                ai_result = await self._ai_analyze(chat_id, username, message_text)
            elif base_confidence >= 0.3 or is_question:
                # Classic mode: AI only if keywords match or question
                ai_result = await self._ai_analyze(chat_id, username, message_text)

        # If AI-only mode and no AI result, skip (don't fallback to keywords)
        if ai_only and not ai_result:
            return None

        # Combine results
        if ai_result:
            # AI result takes precedence
            final_confidence = ai_result['confidence']  # Use AI confidence directly
            problem_type = ai_result.get('type', 'problem')
            title = ai_result.get('title', message_text[:50])
            description = ai_result.get('description', message_text)
            suggested_action = ai_result.get('action', 'notify')
        else:
            # Use keyword-based result (only in non-AI-only mode)
            if not matched_keywords and urgency_score < 0.3 and not is_question:
                return None
            final_confidence = base_confidence
            problem_type = 'urgent' if urgency_score > 0.5 else ('question' if is_question else 'problem')
            title = message_text[:50] + ('...' if len(message_text) > 50 else '')
            description = message_text
            suggested_action = 'create_task' if final_confidence > 0.7 else 'notify'

        # Check minimum confidence
        if final_confidence < self.MIN_CONFIDENCE:
            return None

        # Update rate limit
        self._last_detection[chat_id] = datetime.utcnow()

        return DetectionResult(
            is_problem=True,
            confidence=final_confidence,
            problem_type=problem_type,
            title=title,
            description=description,
            suggested_action=suggested_action,
            keywords_matched=matched_keywords
        )

    def _match_keywords(self, text: str) -> List[str]:
        """Find matching problem keywords in text"""
        matched = []
        for keyword in self.PROBLEM_KEYWORDS:
            if keyword.lower() in text:
                matched.append(keyword)
        return matched

    def _is_question(self, text: str) -> bool:
        """Check if message is a question"""
        for pattern in self.QUESTION_PATTERNS:
            if re.search(pattern, text.lower()):
                return True
        return False

    def _calculate_urgency(self, text: str) -> float:
        """Calculate urgency score (0.0 to 1.0)"""
        score = 0.0
        text_lower = text.lower()

        for booster in self.URGENCY_BOOSTERS:
            if booster == "CAPS":
                # Check for excessive caps
                caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
                if caps_ratio > 0.5:
                    score += 0.2
            elif booster == "!!!":
                if "!!!" in text:
                    score += 0.2
            elif booster in text_lower:
                score += 0.2

        return min(score, 1.0)

    def _check_rate_limit(self, chat_id: int) -> bool:
        """Check if detection is allowed (rate limiting)"""
        last = self._last_detection.get(chat_id)
        if last:
            elapsed = (datetime.utcnow() - last).total_seconds()
            if elapsed < self.DETECTION_COOLDOWN:
                return False
        return True

    async def _ai_analyze(
        self,
        chat_id: int,
        username: str,
        message_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Use AI to analyze message for problems.

        Returns dict with:
        - confidence: float
        - type: problem/urgent/question/complaint
        - title: short summary
        - description: full context
        - action: notify/create_task/auto_reply
        """
        try:
            # Get recent context for better analysis
            context = await chat_context_service.get_context_as_text(chat_id, limit=10)

            system_prompt = """You are a support issue detector. Analyze the message and determine if it describes a problem or issue that needs attention.

Respond ONLY with JSON (no markdown):
{
    "is_problem": true/false,
    "confidence": 0.0-1.0,
    "type": "problem|urgent|question|complaint|info",
    "title": "short summary (max 50 chars)",
    "description": "what the issue is about",
    "action": "notify|create_task|ignore"
}

Rules:
- "urgent" = needs immediate attention (mentions срочно, критично, etc.)
- "problem" = technical issue or something broken
- "question" = user asking for help/info
- "complaint" = user expressing frustration
- "info" = just information, not an issue

- action "create_task" = high confidence real issue
- action "notify" = might need attention
- action "ignore" = not a real issue"""

            user_prompt = f"""Recent chat context:
{context}

New message from {username}:
"{message_text}"

Analyze this message."""

            response = await ai_manager.chat(
                user_message=user_prompt,
                system_prompt=system_prompt
            )

            if response and response.content:
                import json
                content = response.content.strip()

                # Clean up markdown if present
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                result = json.loads(content)

                if result.get('is_problem'):
                    return {
                        'confidence': float(result.get('confidence', 0.5)),
                        'type': result.get('type', 'problem'),
                        'title': result.get('title', message_text[:50]),
                        'description': result.get('description', message_text),
                        'action': result.get('action', 'notify')
                    }

        except Exception as e:
            bot_logger.warning(f"AI analysis failed: {e}")

        return None

    async def detect_unanswered_questions(
        self,
        chat_id: int,
        minutes: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Find questions that haven't been answered.

        Args:
            chat_id: Chat to check
            minutes: Questions older than this without reply

        Returns:
            List of unanswered questions with metadata
        """
        messages = await chat_context_service.get_unanswered_questions(chat_id, minutes)

        results = []
        for msg in messages:
            results.append({
                'message_id': msg.message_id,
                'user_id': msg.user_id,
                'username': msg.display_name or msg.username,
                'text': msg.message_text,
                'asked_at': msg.created_at,
                'minutes_waiting': int((datetime.utcnow() - msg.created_at).total_seconds() / 60)
            })

        return results


# Global instance
problem_detector = ProblemDetectorService()
