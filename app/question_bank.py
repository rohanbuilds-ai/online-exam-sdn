"""
Question Bank Management for the Online Examination Network.
Loads, validates, and serves questions from structured JSON files.
"""

import json
import os
import random
from typing import Dict, List, Any, Optional, Tuple


class Question:
    def __init__(
        self,
        q_id: int,
        category: str,
        question: str,
        options: List[str],
        answer: int,
        explanation: str = "",
        points: int = 1
    ):
        self.id = q_id
        self.category = category
        self.question = question
        self.options = options
        self.answer = answer  # 1-indexed
        self.explanation = explanation
        self.points = points

    def to_client_dict(self, index: int, total: int, remaining_time: float) -> Dict[str, Any]:
        """Return safe view for client without revealing the correct answer."""
        return {
            "question_id": self.id,
            "number": index,
            "total": total,
            "category": self.category,
            "question": self.question,
            "options": self.options,
            "points": self.points,
            "remaining_seconds": max(0.0, round(remaining_time, 1))
        }

    def check_answer(self, selected_option: int) -> Tuple[bool, int, str]:
        """Check if selected option matches answer."""
        is_correct = (selected_option == self.answer)
        awarded_points = self.points if is_correct else 0
        return is_correct, awarded_points, self.explanation


class QuestionBank:
    def __init__(self, json_path: Optional[str] = None):
        self.questions: Dict[int, Question] = {}
        self.ordered_ids: List[int] = []

        if json_path:
            self.load_from_file(json_path)

    def load_from_file(self, json_path: str) -> None:
        """Load and validate questions from a JSON file."""
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Question bank file not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            raise ValueError("Question bank JSON must contain a list of question objects.")

        self.questions.clear()
        self.ordered_ids.clear()

        for idx, item in enumerate(raw_data, start=1):
            q_id = item.get("id", idx)
            category = item.get("category", "General")
            question_text = item.get("question", "").strip()
            options = item.get("options", [])
            answer = int(item.get("answer", 1))
            explanation = item.get("explanation", "")
            points = int(item.get("points", 1))

            if not question_text:
                raise ValueError(f"Question at index {idx} has empty question text.")
            if len(options) < 2:
                raise ValueError(f"Question '{q_id}' has fewer than 2 options.")
            if not (1 <= answer <= len(options)):
                raise ValueError(f"Question '{q_id}' answer {answer} out of bounds for {len(options)} options.")

            q_obj = Question(
                q_id=q_id,
                category=category,
                question=question_text,
                options=options,
                answer=answer,
                explanation=explanation,
                points=points
            )
            self.questions[q_id] = q_obj
            self.ordered_ids.append(q_id)

    def get_question(self, q_id: int) -> Optional[Question]:
        return self.questions.get(q_id)

    def get_exam_questions(self, count: Optional[int] = None, shuffle: bool = False) -> List[Question]:
        """Return a slice or full list of questions for an exam session."""
        ids = list(self.ordered_ids)
        if shuffle:
            random.shuffle(ids)
        if count is not None and count > 0:
            ids = ids[:count]
        return [self.questions[qid] for qid in ids]

    def total_count(self) -> int:
        return len(self.questions)
