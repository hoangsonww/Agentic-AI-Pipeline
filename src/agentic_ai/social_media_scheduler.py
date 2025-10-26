"""
Social Media Scheduler and Campaign Manager

This module provides scheduling capabilities for social media posts,
campaign management, and automated posting at optimal times.
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PostStatus(str, Enum):
    """Status of a scheduled post"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CampaignStatus(str, Enum):
    """Status of a campaign"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    DRAFT = "draft"


class ScheduledPost(BaseModel):
    """Model for a scheduled social media post"""
    id: Optional[str] = None
    platform: str
    content: str
    media_urls: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    scheduled_time: datetime
    status: PostStatus = PostStatus.SCHEDULED
    campaign_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    published_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Campaign(BaseModel):
    """Model for a social media campaign"""
    id: Optional[str] = None
    name: str
    description: str
    platforms: List[str]
    start_date: datetime
    end_date: Optional[datetime] = None
    status: CampaignStatus = CampaignStatus.DRAFT
    budget: Optional[float] = None
    target_audience: Optional[str] = None
    goals: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SocialMediaScheduler:
    """Scheduler for social media posts with SQLite backend"""

    def __init__(self, db_path: str = ".sqlite/social_media.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize the SQLite database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create campaigns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    platforms TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    status TEXT DEFAULT 'draft',
                    budget REAL,
                    target_audience TEXT,
                    goals TEXT,
                    created_at TEXT NOT NULL,
                    metadata TEXT
                )
            """)

            # Create scheduled_posts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_posts (
                    id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    content TEXT NOT NULL,
                    media_urls TEXT,
                    hashtags TEXT,
                    scheduled_time TEXT NOT NULL,
                    status TEXT DEFAULT 'scheduled',
                    campaign_id TEXT,
                    created_at TEXT NOT NULL,
                    published_at TEXT,
                    error_message TEXT,
                    metadata TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_posts_scheduled_time
                ON scheduled_posts(scheduled_time)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_posts_status
                ON scheduled_posts(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_posts_campaign
                ON scheduled_posts(campaign_id)
            """)

            conn.commit()

    def _generate_id(self, prefix: str = "post") -> str:
        """Generate a unique ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return f"{prefix}_{timestamp}"

    def create_campaign(self, campaign: Campaign) -> str:
        """Create a new campaign"""
        if not campaign.id:
            campaign.id = self._generate_id("campaign")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO campaigns (
                    id, name, description, platforms, start_date, end_date,
                    status, budget, target_audience, goals, created_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                campaign.id,
                campaign.name,
                campaign.description,
                json.dumps(campaign.platforms),
                campaign.start_date.isoformat(),
                campaign.end_date.isoformat() if campaign.end_date else None,
                campaign.status.value,
                campaign.budget,
                campaign.target_audience,
                json.dumps(campaign.goals),
                campaign.created_at.isoformat(),
                json.dumps(campaign.metadata)
            ))
            conn.commit()

        logger.info(f"Created campaign: {campaign.id} - {campaign.name}")
        return campaign.id

    def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get a campaign by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return Campaign(
                id=row[0],
                name=row[1],
                description=row[2],
                platforms=json.loads(row[3]),
                start_date=datetime.fromisoformat(row[4]),
                end_date=datetime.fromisoformat(row[5]) if row[5] else None,
                status=CampaignStatus(row[6]),
                budget=row[7],
                target_audience=row[8],
                goals=json.loads(row[9]),
                created_at=datetime.fromisoformat(row[10]),
                metadata=json.loads(row[11]) if row[11] else {}
            )

    def list_campaigns(self, status: Optional[CampaignStatus] = None) -> List[Campaign]:
        """List all campaigns, optionally filtered by status"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute("SELECT * FROM campaigns WHERE status = ? ORDER BY created_at DESC", (status.value,))
            else:
                cursor.execute("SELECT * FROM campaigns ORDER BY created_at DESC")

            campaigns = []
            for row in cursor.fetchall():
                campaigns.append(Campaign(
                    id=row[0],
                    name=row[1],
                    description=row[2],
                    platforms=json.loads(row[3]),
                    start_date=datetime.fromisoformat(row[4]),
                    end_date=datetime.fromisoformat(row[5]) if row[5] else None,
                    status=CampaignStatus(row[6]),
                    budget=row[7],
                    target_audience=row[8],
                    goals=json.loads(row[9]),
                    created_at=datetime.fromisoformat(row[10]),
                    metadata=json.loads(row[11]) if row[11] else {}
                ))

            return campaigns

    def schedule_post(self, post: ScheduledPost) -> str:
        """Schedule a new post"""
        if not post.id:
            post.id = self._generate_id("post")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO scheduled_posts (
                    id, platform, content, media_urls, hashtags, scheduled_time,
                    status, campaign_id, created_at, published_at, error_message, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post.id,
                post.platform,
                post.content,
                json.dumps(post.media_urls),
                json.dumps(post.hashtags),
                post.scheduled_time.isoformat(),
                post.status.value,
                post.campaign_id,
                post.created_at.isoformat(),
                post.published_at.isoformat() if post.published_at else None,
                post.error_message,
                json.dumps(post.metadata)
            ))
            conn.commit()

        logger.info(f"Scheduled post: {post.id} for {post.scheduled_time}")
        return post.id

    def get_post(self, post_id: str) -> Optional[ScheduledPost]:
        """Get a scheduled post by ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scheduled_posts WHERE id = ?", (post_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return ScheduledPost(
                id=row[0],
                platform=row[1],
                content=row[2],
                media_urls=json.loads(row[3]),
                hashtags=json.loads(row[4]),
                scheduled_time=datetime.fromisoformat(row[5]),
                status=PostStatus(row[6]),
                campaign_id=row[7],
                created_at=datetime.fromisoformat(row[8]),
                published_at=datetime.fromisoformat(row[9]) if row[9] else None,
                error_message=row[10],
                metadata=json.loads(row[11]) if row[11] else {}
            )

    def update_post_status(
        self,
        post_id: str,
        status: PostStatus,
        error_message: Optional[str] = None
    ):
        """Update the status of a scheduled post"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            published_at = datetime.now().isoformat() if status == PostStatus.PUBLISHED else None

            cursor.execute("""
                UPDATE scheduled_posts
                SET status = ?, published_at = ?, error_message = ?
                WHERE id = ?
            """, (status.value, published_at, error_message, post_id))
            conn.commit()

        logger.info(f"Updated post {post_id} status to {status.value}")

    def get_posts_due(self, within_minutes: int = 5) -> List[ScheduledPost]:
        """Get posts that are due to be published"""
        now = datetime.now()
        due_time = now + timedelta(minutes=within_minutes)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM scheduled_posts
                WHERE status = 'scheduled'
                AND scheduled_time <= ?
                AND scheduled_time >= ?
                ORDER BY scheduled_time ASC
            """, (due_time.isoformat(), now.isoformat()))

            posts = []
            for row in cursor.fetchall():
                posts.append(ScheduledPost(
                    id=row[0],
                    platform=row[1],
                    content=row[2],
                    media_urls=json.loads(row[3]),
                    hashtags=json.loads(row[4]),
                    scheduled_time=datetime.fromisoformat(row[5]),
                    status=PostStatus(row[6]),
                    campaign_id=row[7],
                    created_at=datetime.fromisoformat(row[8]),
                    published_at=datetime.fromisoformat(row[9]) if row[9] else None,
                    error_message=row[10],
                    metadata=json.loads(row[11]) if row[11] else {}
                ))

            return posts

    def list_posts(
        self,
        campaign_id: Optional[str] = None,
        status: Optional[PostStatus] = None,
        platform: Optional[str] = None,
        limit: int = 100
    ) -> List[ScheduledPost]:
        """List scheduled posts with optional filters"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM scheduled_posts WHERE 1=1"
            params = []

            if campaign_id:
                query += " AND campaign_id = ?"
                params.append(campaign_id)

            if status:
                query += " AND status = ?"
                params.append(status.value)

            if platform:
                query += " AND platform = ?"
                params.append(platform)

            query += " ORDER BY scheduled_time DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            posts = []
            for row in cursor.fetchall():
                posts.append(ScheduledPost(
                    id=row[0],
                    platform=row[1],
                    content=row[2],
                    media_urls=json.loads(row[3]),
                    hashtags=json.loads(row[4]),
                    scheduled_time=datetime.fromisoformat(row[5]),
                    status=PostStatus(row[6]),
                    campaign_id=row[7],
                    created_at=datetime.fromisoformat(row[8]),
                    published_at=datetime.fromisoformat(row[9]) if row[9] else None,
                    error_message=row[10],
                    metadata=json.loads(row[11]) if row[11] else {}
                ))

            return posts

    def cancel_post(self, post_id: str):
        """Cancel a scheduled post"""
        self.update_post_status(post_id, PostStatus.CANCELLED)

    def delete_post(self, post_id: str):
        """Delete a scheduled post"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scheduled_posts WHERE id = ?", (post_id,))
            conn.commit()

        logger.info(f"Deleted post: {post_id}")

    def get_campaign_stats(self, campaign_id: str) -> Dict[str, Any]:
        """Get statistics for a campaign"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Count posts by status
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM scheduled_posts
                WHERE campaign_id = ?
                GROUP BY status
            """, (campaign_id,))

            status_counts = {row[0]: row[1] for row in cursor.fetchall()}

            # Get total posts
            cursor.execute("""
                SELECT COUNT(*) FROM scheduled_posts WHERE campaign_id = ?
            """, (campaign_id,))
            total_posts = cursor.fetchone()[0]

            return {
                "campaign_id": campaign_id,
                "total_posts": total_posts,
                "status_breakdown": status_counts,
                "published": status_counts.get("published", 0),
                "scheduled": status_counts.get("scheduled", 0),
                "failed": status_counts.get("failed", 0),
                "draft": status_counts.get("draft", 0)
            }

    def get_optimal_posting_times(self, platform: str) -> List[Dict[str, str]]:
        """Get optimal posting times for a platform"""
        # Based on general best practices
        optimal_times = {
            "twitter": [
                {"day": "Monday-Friday", "time": "12:00 PM", "timezone": "Local"},
                {"day": "Monday-Friday", "time": "3:00 PM", "timezone": "Local"},
                {"day": "Wednesday", "time": "9:00 AM", "timezone": "Local"},
            ],
            "linkedin": [
                {"day": "Tuesday-Thursday", "time": "8:00 AM", "timezone": "Local"},
                {"day": "Tuesday-Thursday", "time": "12:00 PM", "timezone": "Local"},
                {"day": "Wednesday", "time": "10:00 AM", "timezone": "Local"},
            ],
            "instagram": [
                {"day": "Monday-Friday", "time": "11:00 AM", "timezone": "Local"},
                {"day": "Monday-Friday", "time": "2:00 PM", "timezone": "Local"},
                {"day": "Wednesday", "time": "7:00 PM", "timezone": "Local"},
            ],
            "facebook": [
                {"day": "Tuesday-Thursday", "time": "1:00 PM", "timezone": "Local"},
                {"day": "Tuesday-Thursday", "time": "3:00 PM", "timezone": "Local"},
                {"day": "Wednesday", "time": "11:00 AM", "timezone": "Local"},
            ]
        }

        return optimal_times.get(platform.lower(), optimal_times["twitter"])


class SchedulerService:
    """Background service that monitors and publishes scheduled posts"""

    def __init__(self, scheduler: SocialMediaScheduler):
        self.scheduler = scheduler
        self.running = False

    async def start(self):
        """Start the scheduler service"""
        self.running = True
        logger.info("Scheduler service started")

        while self.running:
            try:
                # Check for posts due in the next 5 minutes
                posts = self.scheduler.get_posts_due(within_minutes=5)

                for post in posts:
                    await self._publish_post(post)

                # Wait 1 minute before checking again
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Error in scheduler service: {e}")
                await asyncio.sleep(60)

    async def _publish_post(self, post: ScheduledPost):
        """Publish a scheduled post"""
        logger.info(f"Publishing post {post.id} to {post.platform}")

        try:
            # Here you would integrate with the actual social media APIs
            # For now, we'll simulate publishing
            from .tools.social_media_tools import SocialMediaConfig, TwitterAPI, LinkedInAPI, InstagramAPI

            config = SocialMediaConfig()

            if post.platform == "twitter":
                api = TwitterAPI(config)
                result = await api.post_tweet(post.content)
            elif post.platform == "linkedin":
                api = LinkedInAPI(config)
                result = await api.post_update(post.content)
            elif post.platform == "instagram":
                api = InstagramAPI(config)
                if post.media_urls:
                    result = await api.post_photo(post.media_urls[0], post.content)
                else:
                    raise ValueError("Instagram requires media URLs")
            else:
                raise ValueError(f"Unsupported platform: {post.platform}")

            # Update status to published
            self.scheduler.update_post_status(post.id, PostStatus.PUBLISHED)
            logger.info(f"Successfully published post {post.id}")

        except Exception as e:
            logger.error(f"Failed to publish post {post.id}: {e}")
            self.scheduler.update_post_status(post.id, PostStatus.FAILED, str(e))

    def stop(self):
        """Stop the scheduler service"""
        self.running = False
        logger.info("Scheduler service stopped")
