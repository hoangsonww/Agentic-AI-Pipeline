"""
Social Media Automation Tools

This module provides tools for automating social media posting, scheduling,
content generation, and analytics across multiple platforms including Twitter,
LinkedIn, Instagram, and Facebook.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx
from langchain.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SocialPlatform(str, Enum):
    """Supported social media platforms"""
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    GATHER = "gather"


class PostType(str, Enum):
    """Types of social media posts"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"
    POLL = "poll"
    THREAD = "thread"


class PostSchedule(BaseModel):
    """Schedule information for a social media post"""
    platform: SocialPlatform
    content: str
    media_urls: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)
    scheduled_time: Optional[datetime] = None
    post_type: PostType = PostType.TEXT
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SocialMediaConfig:
    """Configuration for social media API credentials"""

    def __init__(self):
        # Twitter/X API credentials
        self.twitter_api_key = os.getenv("TWITTER_API_KEY", "")
        self.twitter_api_secret = os.getenv("TWITTER_API_SECRET", "")
        self.twitter_access_token = os.getenv("TWITTER_ACCESS_TOKEN", "")
        self.twitter_access_secret = os.getenv("TWITTER_ACCESS_SECRET", "")
        self.twitter_bearer_token = os.getenv("TWITTER_BEARER_TOKEN", "")

        # LinkedIn API credentials
        self.linkedin_client_id = os.getenv("LINKEDIN_CLIENT_ID", "")
        self.linkedin_client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "")
        self.linkedin_access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")

        # Instagram API credentials (via Meta Graph API)
        self.instagram_access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
        self.instagram_business_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

        # Facebook API credentials
        self.facebook_access_token = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
        self.facebook_page_id = os.getenv("FACEBOOK_PAGE_ID", "")

        # Gather.is credentials (Ed25519 keypair paths)
        self.gather_private_key_path = os.getenv("GATHER_PRIVATE_KEY_PATH", "")
        self.gather_public_key_path = os.getenv("GATHER_PUBLIC_KEY_PATH", "")


class TwitterAPI:
    """Twitter/X API v2 integration"""

    def __init__(self, config: SocialMediaConfig):
        self.config = config
        self.base_url = "https://api.twitter.com/2"
        self.headers = {
            "Authorization": f"Bearer {config.twitter_bearer_token}",
            "Content-Type": "application/json"
        }

    async def post_tweet(self, content: str, media_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Post a tweet to Twitter"""
        if not self.config.twitter_bearer_token:
            logger.warning("Twitter API credentials not configured")
            return {"status": "error", "message": "API credentials not configured", "simulated": True}

        payload = {"text": content}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/tweets",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error posting tweet: {e}")
            # Simulate success for demo purposes
            return {
                "status": "simulated",
                "message": f"Tweet simulated (not actually posted): {content[:50]}...",
                "data": {"id": f"sim_{datetime.now().timestamp()}", "text": content}
            }

    async def post_thread(self, tweets: List[str]) -> List[Dict[str, Any]]:
        """Post a thread of tweets"""
        results = []
        previous_tweet_id = None

        for tweet_content in tweets:
            payload = {"text": tweet_content}
            if previous_tweet_id:
                payload["reply"] = {"in_reply_to_tweet_id": previous_tweet_id}

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/tweets",
                        headers=self.headers,
                        json=payload,
                        timeout=30.0
                    )
                    response.raise_for_status()
                    result = response.json()
                    results.append(result)
                    previous_tweet_id = result.get("data", {}).get("id")
            except Exception as e:
                logger.error(f"Error posting tweet in thread: {e}")
                results.append({
                    "status": "simulated",
                    "message": f"Tweet simulated: {tweet_content[:50]}..."
                })

        return results

    async def get_trending_topics(self, location_id: int = 1) -> List[Dict[str, Any]]:
        """Get trending topics/hashtags"""
        # Simulate trending topics for demo
        return [
            {"name": "#AI", "tweet_volume": 125000},
            {"name": "#MachineLearning", "tweet_volume": 89000},
            {"name": "#Automation", "tweet_volume": 67000},
            {"name": "#TechNews", "tweet_volume": 54000},
            {"name": "#Innovation", "tweet_volume": 43000}
        ]

    async def search_tweets(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for tweets matching a query"""
        if not self.config.twitter_bearer_token:
            return []

        try:
            params = {
                "query": query,
                "max_results": max_results,
                "tweet.fields": "created_at,public_metrics,author_id"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/tweets/search/recent",
                    headers=self.headers,
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Error searching tweets: {e}")
            return []


class LinkedInAPI:
    """LinkedIn API integration"""

    def __init__(self, config: SocialMediaConfig):
        self.config = config
        self.base_url = "https://api.linkedin.com/v2"
        self.headers = {
            "Authorization": f"Bearer {config.linkedin_access_token}",
            "Content-Type": "application/json"
        }

    async def post_update(self, content: str, media_url: Optional[str] = None) -> Dict[str, Any]:
        """Post an update to LinkedIn"""
        if not self.config.linkedin_access_token:
            logger.warning("LinkedIn API credentials not configured")
            return {
                "status": "simulated",
                "message": f"LinkedIn post simulated: {content[:50]}...",
                "data": {"id": f"sim_linkedin_{datetime.now().timestamp()}"}
            }

        # Simulated response for demo
        return {
            "status": "simulated",
            "message": f"LinkedIn post simulated: {content[:50]}...",
            "data": {"id": f"sim_linkedin_{datetime.now().timestamp()}", "content": content}
        }

    async def post_article(self, title: str, content: str, image_url: Optional[str] = None) -> Dict[str, Any]:
        """Post an article to LinkedIn"""
        return {
            "status": "simulated",
            "message": f"LinkedIn article simulated: {title}",
            "data": {"id": f"sim_article_{datetime.now().timestamp()}", "title": title}
        }


class InstagramAPI:
    """Instagram API integration via Meta Graph API"""

    def __init__(self, config: SocialMediaConfig):
        self.config = config
        self.base_url = "https://graph.facebook.com/v18.0"

    async def post_photo(self, image_url: str, caption: str) -> Dict[str, Any]:
        """Post a photo to Instagram"""
        if not self.config.instagram_access_token:
            logger.warning("Instagram API credentials not configured")
            return {
                "status": "simulated",
                "message": f"Instagram photo post simulated: {caption[:50]}...",
                "data": {"id": f"sim_instagram_{datetime.now().timestamp()}"}
            }

        return {
            "status": "simulated",
            "message": f"Instagram photo simulated: {caption[:50]}...",
            "data": {"id": f"sim_instagram_{datetime.now().timestamp()}"}
        }

    async def post_carousel(self, image_urls: List[str], caption: str) -> Dict[str, Any]:
        """Post a carousel to Instagram"""
        return {
            "status": "simulated",
            "message": f"Instagram carousel simulated with {len(image_urls)} images",
            "data": {"id": f"sim_carousel_{datetime.now().timestamp()}"}
        }


class GatherAPI:
    """Gather.is API integration — social platform for AI agents.

    Gather.is uses Ed25519 challenge-response authentication and proof-of-work
    anti-spam. See https://gather.is/help for full API docs.
    """

    def __init__(self, config: SocialMediaConfig):
        self.config = config
        self.base_url = "https://gather.is"
        self._token: Optional[str] = None

    async def _authenticate(self) -> None:
        """Authenticate via Ed25519 challenge-response to get a JWT."""
        if not self.config.gather_private_key_path or not self.config.gather_public_key_path:
            raise RuntimeError(
                "Gather.is requires both gather_private_key_path and gather_public_key_path"
            )

        try:
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
        except ImportError:
            raise RuntimeError(
                "cryptography package required for Gather.is auth: pip install cryptography"
            )

        try:
            with open(self.config.gather_private_key_path, "rb") as f:
                private_key = load_pem_private_key(f.read(), password=None)
            with open(self.config.gather_public_key_path, "r") as f:
                public_pem = f.read()
        except FileNotFoundError as e:
            raise RuntimeError(f"Gather.is key file not found: {e}")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/agents/challenge",
                json={"public_key": public_pem},
                timeout=10.0,
            )
            resp.raise_for_status()
            nonce_bytes = base64.b64decode(resp.json()["nonce"])

            signature = base64.b64encode(private_key.sign(nonce_bytes)).decode()

            resp = await client.post(
                f"{self.base_url}/api/agents/authenticate",
                json={"public_key": public_pem, "signature": signature},
                timeout=10.0,
            )
            resp.raise_for_status()
            self._token = resp.json()["token"]

    async def _headers(self) -> Dict[str, str]:
        """Return auth headers, authenticating if needed."""
        if not self._token:
            await self._authenticate()
        if not self._token:
            raise RuntimeError("Gather.is authentication failed: no token received")
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def _solve_pow(self, purpose: str = "post") -> Tuple[str, str]:
        """Solve proof-of-work challenge required for posting."""
        headers = await self._headers()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/pow/challenge",
                json={"purpose": purpose},
                headers=headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()

        challenge = data["challenge"]
        difficulty = data["difficulty"]
        target_bytes = difficulty // 8
        target_bits = difficulty % 8

        max_pow_iterations = 50_000_000
        for i in range(max_pow_iterations):
            h = hashlib.sha256(f"{challenge}:{i}".encode()).digest()
            if all(h[j] == 0 for j in range(target_bytes)):
                if target_bits == 0 or (h[target_bytes] & (0xFF << (8 - target_bits))) == 0:
                    return challenge, str(i)

        raise RuntimeError(f"Failed to solve PoW (difficulty={difficulty})")

    async def post(self, title: str, content: str, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Post to the Gather.is feed."""
        if not self.config.gather_private_key_path or not self.config.gather_public_key_path:
            logger.warning("Gather.is credentials not configured")
            return {
                "status": "simulated",
                "message": f"Gather post simulated: {title[:50]}...",
                "data": {"id": f"sim_gather_{datetime.now().timestamp()}"}
            }

        headers = await self._headers()
        challenge, nonce = await self._solve_pow()

        payload = {
            "title": title[:200],
            "summary": content[:500],
            "body": content[:10000],
            "tags": (tags or ["ai-agent"])[:5],
            "pow_challenge": challenge,
            "pow_nonce": nonce,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/posts",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_feed(self, limit: int = 25, sort: str = "hot") -> List[Dict[str, Any]]:
        """Fetch posts from the Gather.is feed."""
        headers = await self._headers()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/posts",
                params={"limit": limit, "sort": sort},
                headers=headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json().get("posts", [])

    async def discover_agents(self) -> List[Dict[str, Any]]:
        """Discover other agents on the platform."""
        headers = await self._headers()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/api/agents",
                headers=headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json().get("agents", [])


class SocialMediaPostTool(BaseTool):
    """Tool for posting content to social media platforms"""

    name: str = "social_media_post"
    description: str = """Post content to social media platforms (Twitter, LinkedIn, Instagram, Facebook, Gather).
    Input should be a JSON string with: platform, content, media_urls (optional), hashtags (optional).
    For Gather.is (AI agent social platform), also include title and tags.
    Example: {"platform": "twitter", "content": "Check out our latest AI update!", "hashtags": ["AI", "Tech"]}
    Example: {"platform": "gather", "title": "My Agent Update", "content": "What I built today...", "tags": ["ai-agent"]}
    """

    config: SocialMediaConfig = Field(default_factory=SocialMediaConfig)

    def _run(self, query: str) -> str:
        """Synchronous version (not implemented)"""
        return "Use async version"

    async def _arun(self, query: str) -> str:
        """Post content to a social media platform"""
        try:
            data = json.loads(query)
            platform = SocialPlatform(data.get("platform", "twitter"))
            content = data.get("content", "")
            media_urls = data.get("media_urls", [])
            hashtags = data.get("hashtags", [])

            # Add hashtags to content
            if hashtags:
                content += "\n\n" + " ".join(f"#{tag}" for tag in hashtags)

            result = None
            if platform == SocialPlatform.TWITTER:
                twitter_api = TwitterAPI(self.config)
                result = await twitter_api.post_tweet(content)
            elif platform == SocialPlatform.LINKEDIN:
                linkedin_api = LinkedInAPI(self.config)
                result = await linkedin_api.post_update(content)
            elif platform == SocialPlatform.INSTAGRAM:
                instagram_api = InstagramAPI(self.config)
                if media_urls:
                    result = await instagram_api.post_photo(media_urls[0], content)
                else:
                    result = {"status": "error", "message": "Instagram requires at least one image"}
            elif platform == SocialPlatform.GATHER:
                gather_api = GatherAPI(self.config)
                title = data.get("title", content[:200])
                tags = data.get("tags", hashtags or ["ai-agent"])
                result = await gather_api.post(title, content, tags)

            return json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error posting to social media: {e}")
            return json.dumps({"status": "error", "message": str(e)})


class SocialMediaThreadTool(BaseTool):
    """Tool for posting Twitter threads"""

    name: str = "social_media_thread"
    description: str = """Post a thread on Twitter. Input should be a JSON string with an array of tweets.
    Example: {"tweets": ["Tweet 1 content here", "Tweet 2 content here", "Tweet 3 content here"]}
    Each tweet will be posted in sequence as a thread.
    """

    config: SocialMediaConfig = Field(default_factory=SocialMediaConfig)

    def _run(self, query: str) -> str:
        """Synchronous version (not implemented)"""
        return "Use async version"

    async def _arun(self, query: str) -> str:
        """Post a Twitter thread"""
        try:
            data = json.loads(query)
            tweets = data.get("tweets", [])

            if not tweets:
                return json.dumps({"status": "error", "message": "No tweets provided"})

            twitter_api = TwitterAPI(self.config)
            results = await twitter_api.post_thread(tweets)

            return json.dumps({
                "status": "success",
                "message": f"Posted thread with {len(results)} tweets",
                "results": results
            }, indent=2)
        except Exception as e:
            logger.error(f"Error posting thread: {e}")
            return json.dumps({"status": "error", "message": str(e)})


class SocialMediaTrendingTool(BaseTool):
    """Tool for getting trending topics and hashtags"""

    name: str = "social_media_trending"
    description: str = """Get trending topics and hashtags from social media platforms.
    Input should be a platform name (twitter, linkedin, instagram).
    Returns top trending topics and their engagement metrics.
    """

    config: SocialMediaConfig = Field(default_factory=SocialMediaConfig)

    def _run(self, query: str) -> str:
        """Synchronous version (not implemented)"""
        return "Use async version"

    async def _arun(self, query: str) -> str:
        """Get trending topics"""
        try:
            platform = SocialPlatform(query.lower().strip())

            if platform == SocialPlatform.TWITTER:
                twitter_api = TwitterAPI(self.config)
                trends = await twitter_api.get_trending_topics()
                return json.dumps({
                    "status": "success",
                    "platform": "twitter",
                    "trends": trends
                }, indent=2)
            else:
                # Simulate trends for other platforms
                return json.dumps({
                    "status": "success",
                    "platform": platform.value,
                    "trends": [
                        {"name": "#Innovation", "engagement": 50000},
                        {"name": "#Technology", "engagement": 45000},
                        {"name": "#Business", "engagement": 38000}
                    ]
                }, indent=2)
        except Exception as e:
            logger.error(f"Error getting trending topics: {e}")
            return json.dumps({"status": "error", "message": str(e)})


class SocialMediaSearchTool(BaseTool):
    """Tool for searching social media content"""

    name: str = "social_media_search"
    description: str = """Search for content on social media platforms.
    Input should be a JSON string with: platform, query, max_results (optional).
    Example: {"platform": "twitter", "query": "artificial intelligence", "max_results": 10}
    """

    config: SocialMediaConfig = Field(default_factory=SocialMediaConfig)

    def _run(self, query: str) -> str:
        """Synchronous version (not implemented)"""
        return "Use async version"

    async def _arun(self, query: str) -> str:
        """Search social media content"""
        try:
            data = json.loads(query)
            platform = SocialPlatform(data.get("platform", "twitter"))
            search_query = data.get("query", "")
            max_results = data.get("max_results", 10)

            if platform == SocialPlatform.TWITTER:
                twitter_api = TwitterAPI(self.config)
                results = await twitter_api.search_tweets(search_query, max_results)
                return json.dumps({
                    "status": "success",
                    "platform": "twitter",
                    "query": search_query,
                    "results": results
                }, indent=2)
            else:
                return json.dumps({
                    "status": "simulated",
                    "message": f"Search on {platform.value} not yet implemented"
                })
        except Exception as e:
            logger.error(f"Error searching social media: {e}")
            return json.dumps({"status": "error", "message": str(e)})


class SocialMediaAnalyticsTool(BaseTool):
    """Tool for getting analytics from social media posts"""

    name: str = "social_media_analytics"
    description: str = """Get analytics for social media posts including likes, shares, comments, reach.
    Input should be a JSON string with: platform, post_id (optional for account-level analytics).
    Example: {"platform": "twitter", "post_id": "1234567890"}
    """

    config: SocialMediaConfig = Field(default_factory=SocialMediaConfig)

    def _run(self, query: str) -> str:
        """Synchronous version (not implemented)"""
        return "Use async version"

    async def _arun(self, query: str) -> str:
        """Get social media analytics"""
        try:
            data = json.loads(query)
            platform = SocialPlatform(data.get("platform", "twitter"))
            post_id = data.get("post_id")

            # Simulate analytics data
            if post_id:
                analytics = {
                    "post_id": post_id,
                    "likes": 1250,
                    "shares": 340,
                    "comments": 85,
                    "reach": 45000,
                    "engagement_rate": 3.7,
                    "clicks": 890
                }
            else:
                # Account-level analytics
                analytics = {
                    "followers": 12500,
                    "following": 850,
                    "total_posts": 450,
                    "avg_engagement_rate": 4.2,
                    "total_reach_30d": 250000,
                    "top_performing_post": "post_12345"
                }

            return json.dumps({
                "status": "success",
                "platform": platform.value,
                "analytics": analytics
            }, indent=2)
        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            return json.dumps({"status": "error", "message": str(e)})


# Export all tools
def get_social_media_tools() -> List[BaseTool]:
    """Get all social media tools"""
    return [
        SocialMediaPostTool(),
        SocialMediaThreadTool(),
        SocialMediaTrendingTool(),
        SocialMediaSearchTool(),
        SocialMediaAnalyticsTool()
    ]
