import os
from datetime import datetime, timezone
from sqlalchemy import (create_engine, Column, Integer, String, Float,
                        Boolean, DateTime, ForeignKey)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# SQLite locally; on Railway set DATABASE_URL to the Postgres URL — same code.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///reviews.db")
# Some hosts (Heroku-style) hand out the legacy "postgres://" scheme, which
# SQLAlchemy no longer accepts — normalize it to "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True)
    repo = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=False)
    commit_sha = Column(String, nullable=False)        # the idempotency key
    status = Column(String, default="done")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    findings = relationship("Finding", back_populates="review",
                            cascade="all, delete-orphan")

class Finding(Base):
    __tablename__ = "findings"
    id = Column(Integer, primary_key=True)
    review_id = Column(Integer, ForeignKey("reviews.id"), nullable=False)
    file = Column(String)
    line = Column(Integer)
    category = Column(String)
    severity = Column(String)
    title = Column(String)
    confidence = Column(Float)
    posted = Column(Boolean, default=True)              # posted vs flagged-only
    review = relationship("Review", back_populates="findings")

def init_db():
    Base.metadata.create_all(engine)

def save_review(repo, pr_number, commit_sha, findings, status="done"):
    """Persist one review run and its findings. Returns the new review id."""
    db = SessionLocal()
    try:
        review = Review(repo=repo, pr_number=pr_number,
                        commit_sha=commit_sha, status=status)
        for f in findings:
            review.findings.append(Finding(
                file=f["file"], line=f["line"], category=f["category"],
                severity=f["severity"], title=f["title"],
                confidence=f["confidence"], posted=f.get("posted", True)))
        db.add(review)
        db.commit()
        return review.id
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    s = SessionLocal()
    r = Review(repo="octocat/Hello-World", pr_number=1, commit_sha="abc123",
               findings=[Finding(file="app.py", line=10, category="security",
                                 severity="high", title="SQL injection", confidence=1.0)])
    s.add(r)
    s.commit()
    for rev in s.query(Review).all():
        print(rev.repo, f"PR#{rev.pr_number}", rev.commit_sha, "->",
              len(rev.findings), "finding(s)")
    s.close()