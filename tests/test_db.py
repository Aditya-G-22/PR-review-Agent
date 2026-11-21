"""Tests for the persistence layer: saving reviews and the idempotency check.

We reach everything through the `db` module (db.save_review, db.SessionLocal, ...)
rather than importing the names directly, so the `fresh_db` fixture's in-memory
database is the one actually used.
"""

import db

SAMPLE = [{
    "file": "a.py", "line": 3, "category": "security", "severity": "high",
    "title": "SQL injection", "confidence": 1.0, "posted": True,
}]


def test_save_review_persists_review_and_findings(fresh_db):
    db.save_review("me/repo", 1, "sha123", SAMPLE)

    session = db.SessionLocal()
    try:
        rows = session.query(db.Review).all()
        # read everything (incl. the lazily-loaded `findings`) while the session is open
        assert len(rows) == 1
        assert rows[0].repo == "me/repo"
        assert rows[0].commit_sha == "sha123"
        assert len(rows[0].findings) == 1
        assert rows[0].findings[0].title == "SQL injection"
    finally:
        session.close()


def test_already_reviewed_is_false_for_a_new_commit(fresh_db):
    assert db.already_reviewed("me/repo", 1, "sha123") is False


def test_already_reviewed_is_true_after_saving(fresh_db):
    db.save_review("me/repo", 1, "sha123", SAMPLE)
    assert db.already_reviewed("me/repo", 1, "sha123") is True
    # a different commit on the same PR is NOT a duplicate — it should be reviewed
    assert db.already_reviewed("me/repo", 1, "sha999") is False
