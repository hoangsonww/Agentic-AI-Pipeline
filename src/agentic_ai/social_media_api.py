"""
FastAPI endpoints for Social Media Automation

This module provides REST API endpoints for social media automation features.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from .agents.social_media_agent import SocialMediaAgent, create_social_media_agent
from .social_media_scheduler import (
    SocialMediaScheduler,
    ScheduledPost,
    Campaign,
    PostStatus,
    CampaignStatus,
    SchedulerService
)
from .llm.client import get_llm

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/social", tags=["social_media"])

# Global instances (will be initialized on startup)
social_media_agent: Optional[SocialMediaAgent] = None
scheduler: Optional[SocialMediaScheduler] = None
scheduler_service: Optional[SchedulerService] = None


def init_social_media_services():
    """Initialize social media services"""
    global social_media_agent, scheduler, scheduler_service

    try:
        llm = get_llm()
        scheduler = SocialMediaScheduler()
        social_media_agent = create_social_media_agent(llm)
        scheduler_service = SchedulerService(scheduler)

        logger.info("Social media services initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing social media services: {e}")
        raise


# Request/Response Models
class PostRequest(BaseModel):
    """Request model for posting to social media"""
    platform: str
    content: str
    media_urls: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    scheduled_time: Optional[str] = None  # ISO format datetime


class ContentGenerationRequest(BaseModel):
    """Request model for content generation"""
    topic: str
    platform: str
    tone: str = "professional"
    count: int = 1


class ThreadGenerationRequest(BaseModel):
    """Request model for thread generation"""
    topic: str
    num_tweets: int = 5
    tone: str = "professional"


class CampaignCreationRequest(BaseModel):
    """Request model for campaign creation"""
    name: str
    description: str
    platforms: List[str]
    topic: str
    duration_days: int = 7
    posts_per_day: int = 2


class AgentQueryRequest(BaseModel):
    """Request model for agent queries"""
    query: str
    chat_history: List[Dict[str, str]] = Field(default_factory=list)


# API Endpoints

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "social_media_automation",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/post")
async def create_post(request: PostRequest):
    """Post content to a social media platform immediately or schedule it"""
    try:
        if not scheduler:
            raise HTTPException(status_code=500, detail="Scheduler not initialized")

        # Parse scheduled time if provided
        scheduled_time = None
        if request.scheduled_time:
            try:
                scheduled_time = datetime.fromisoformat(request.scheduled_time)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO format.")

        # Create scheduled post
        post = ScheduledPost(
            platform=request.platform,
            content=request.content,
            media_urls=request.media_urls,
            hashtags=request.hashtags,
            scheduled_time=scheduled_time or datetime.now(),
            status=PostStatus.SCHEDULED if scheduled_time else PostStatus.SCHEDULED
        )

        post_id = scheduler.schedule_post(post)

        return {
            "status": "success",
            "post_id": post_id,
            "message": f"Post {'scheduled' if scheduled_time else 'queued'} for {request.platform}",
            "scheduled_time": post.scheduled_time.isoformat()
        }

    except Exception as e:
        logger.error(f"Error creating post: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-content")
async def generate_content(request: ContentGenerationRequest):
    """Generate social media content using AI"""
    try:
        if not social_media_agent:
            raise HTTPException(status_code=500, detail="Social media agent not initialized")

        suggestions = await social_media_agent.get_content_suggestions(
            platform=request.platform,
            topic=request.topic,
            count=request.count
        )

        return suggestions

    except Exception as e:
        logger.error(f"Error generating content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-thread")
async def generate_thread(request: ThreadGenerationRequest):
    """Generate a Twitter thread"""
    try:
        if not social_media_agent:
            raise HTTPException(status_code=500, detail="Social media agent not initialized")

        # Use the agent's LLM to generate thread
        from .tools.content_generation import ContentGenerator
        generator = ContentGenerator(social_media_agent.llm)
        tweets = await generator.generate_thread(
            topic=request.topic,
            num_tweets=request.num_tweets,
            tone=request.tone
        )

        return {
            "status": "success",
            "topic": request.topic,
            "num_tweets": len(tweets),
            "tweets": tweets
        }

    except Exception as e:
        logger.error(f"Error generating thread: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/campaigns")
async def create_campaign(request: CampaignCreationRequest):
    """Create a new social media campaign with scheduled posts"""
    try:
        if not social_media_agent:
            raise HTTPException(status_code=500, detail="Social media agent not initialized")

        result = await social_media_agent.create_content_campaign(
            topic=request.topic,
            platforms=request.platforms,
            duration_days=request.duration_days,
            posts_per_day=request.posts_per_day
        )

        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])

        return result

    except Exception as e:
        logger.error(f"Error creating campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns")
async def list_campaigns(status: Optional[str] = None):
    """List all campaigns"""
    try:
        if not scheduler:
            raise HTTPException(status_code=500, detail="Scheduler not initialized")

        campaign_status = CampaignStatus(status) if status else None
        campaigns = scheduler.list_campaigns(status=campaign_status)

        return {
            "status": "success",
            "count": len(campaigns),
            "campaigns": [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "platforms": c.platforms,
                    "start_date": c.start_date.isoformat(),
                    "end_date": c.end_date.isoformat() if c.end_date else None,
                    "status": c.status.value,
                    "created_at": c.created_at.isoformat()
                }
                for c in campaigns
            ]
        }

    except Exception as e:
        logger.error(f"Error listing campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get campaign details and statistics"""
    try:
        if not social_media_agent:
            raise HTTPException(status_code=500, detail="Social media agent not initialized")

        overview = social_media_agent.get_campaign_overview(campaign_id)

        if overview["status"] == "error":
            raise HTTPException(status_code=404, detail=overview["message"])

        return overview

    except Exception as e:
        logger.error(f"Error getting campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/posts")
async def list_posts(
    campaign_id: Optional[str] = None,
    status: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 50
):
    """List scheduled posts"""
    try:
        if not scheduler:
            raise HTTPException(status_code=500, detail="Scheduler not initialized")

        post_status = PostStatus(status) if status else None
        posts = scheduler.list_posts(
            campaign_id=campaign_id,
            status=post_status,
            platform=platform,
            limit=limit
        )

        return {
            "status": "success",
            "count": len(posts),
            "posts": [
                {
                    "id": p.id,
                    "platform": p.platform,
                    "content": p.content,
                    "hashtags": p.hashtags,
                    "scheduled_time": p.scheduled_time.isoformat(),
                    "status": p.status.value,
                    "campaign_id": p.campaign_id,
                    "published_at": p.published_at.isoformat() if p.published_at else None
                }
                for p in posts
            ]
        }

    except Exception as e:
        logger.error(f"Error listing posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/posts/{post_id}")
async def delete_post(post_id: str):
    """Delete a scheduled post"""
    try:
        if not scheduler:
            raise HTTPException(status_code=500, detail="Scheduler not initialized")

        post = scheduler.get_post(post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        scheduler.delete_post(post_id)

        return {
            "status": "success",
            "message": f"Post {post_id} deleted"
        }

    except Exception as e:
        logger.error(f"Error deleting post: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending/{platform}")
async def get_trending(platform: str):
    """Get trending topics for a platform"""
    try:
        from .tools.social_media_tools import SocialMediaConfig, TwitterAPI

        if platform.lower() == "twitter":
            config = SocialMediaConfig()
            api = TwitterAPI(config)
            trends = await api.get_trending_topics()

            return {
                "status": "success",
                "platform": platform,
                "trends": trends
            }
        else:
            # Simulated trends for other platforms
            return {
                "status": "success",
                "platform": platform,
                "trends": [
                    {"name": "#Innovation", "engagement": 50000},
                    {"name": "#Technology", "engagement": 45000},
                    {"name": "#AI", "engagement": 40000}
                ]
            }

    except Exception as e:
        logger.error(f"Error getting trending topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def get_analytics(platform: Optional[str] = None, days: int = 30):
    """Get social media analytics"""
    try:
        if not social_media_agent:
            raise HTTPException(status_code=500, detail="Social media agent not initialized")

        analytics = await social_media_agent.analyze_performance(
            platform=platform,
            days=days
        )

        return analytics

    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/optimal-times/{platform}")
async def get_optimal_times(platform: str):
    """Get optimal posting times for a platform"""
    try:
        if not scheduler:
            raise HTTPException(status_code=500, detail="Scheduler not initialized")

        times = scheduler.get_optimal_posting_times(platform)

        return {
            "status": "success",
            "platform": platform,
            "optimal_times": times
        }

    except Exception as e:
        logger.error(f"Error getting optimal times: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/query")
async def query_agent(request: AgentQueryRequest):
    """Query the social media agent with natural language"""
    try:
        if not social_media_agent:
            raise HTTPException(status_code=500, detail="Social media agent not initialized")

        result = await social_media_agent.process_request(
            request=request.query,
            chat_history=request.chat_history
        )

        return result

    except Exception as e:
        logger.error(f"Error querying agent: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/start")
async def start_scheduler(background_tasks: BackgroundTasks):
    """Start the background scheduler service"""
    try:
        if not scheduler_service:
            raise HTTPException(status_code=500, detail="Scheduler service not initialized")

        if not scheduler_service.running:
            background_tasks.add_task(scheduler_service.start)
            return {
                "status": "success",
                "message": "Scheduler service started"
            }
        else:
            return {
                "status": "info",
                "message": "Scheduler service already running"
            }

    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the background scheduler service"""
    try:
        if not scheduler_service:
            raise HTTPException(status_code=500, detail="Scheduler service not initialized")

        if scheduler_service.running:
            scheduler_service.stop()
            return {
                "status": "success",
                "message": "Scheduler service stopped"
            }
        else:
            return {
                "status": "info",
                "message": "Scheduler service not running"
            }

    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))
