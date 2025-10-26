"""
Social Media Automation Agent

This module provides an intelligent agent for social media automation that can:
- Generate and optimize content
- Schedule posts across platforms
- Analyze trends and engagement
- Manage campaigns
- Provide recommendations
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field

from ..tools.social_media_tools import get_social_media_tools
from ..tools.content_generation import get_content_generation_tools
from ..social_media_scheduler import (
    SocialMediaScheduler,
    ScheduledPost,
    Campaign,
    PostStatus,
    CampaignStatus
)

logger = logging.getLogger(__name__)


class SocialMediaAgentProfile:
    """Profile definition for the Social Media Agent"""

    name = "SocialMediaAgent"
    emoji = "📱"

    system_prompt = """You are a professional social media manager and content strategist.

Your capabilities include:
- Creating engaging content for Twitter, LinkedIn, Instagram, and Facebook
- Optimizing posts for maximum reach and engagement
- Scheduling posts at optimal times
- Analyzing trends and competitor content
- Managing multi-platform campaigns
- Providing data-driven recommendations

Your personality:
- Creative yet professional
- Data-driven decision maker
- Brand-conscious and audience-focused
- Proactive in suggesting improvements
- Clear communicator

When helping users:
1. Ask clarifying questions about their goals and target audience
2. Provide specific, actionable recommendations
3. Explain your reasoning behind content and timing decisions
4. Share best practices for each platform
5. Track and report on campaign performance

Always maintain brand voice consistency and ensure content aligns with platform best practices."""

    tools_description = """You have access to the following tools:

Content Generation:
- generate_social_content: Create platform-specific post content
- generate_hashtags: Generate relevant hashtags for posts
- generate_twitter_thread: Create multi-tweet threads
- optimize_social_content: Improve content for better engagement
- generate_image_caption: Create captions for visual content

Social Media Actions:
- social_media_post: Post content to platforms
- social_media_thread: Post Twitter threads
- social_media_trending: Get trending topics
- social_media_search: Search social media content
- social_media_analytics: Get post and account analytics

Use these tools to help users manage their social media presence effectively."""


class SocialMediaAgent:
    """Intelligent agent for social media automation"""

    def __init__(
        self,
        llm: BaseChatModel,
        scheduler: Optional[SocialMediaScheduler] = None
    ):
        self.llm = llm
        self.scheduler = scheduler or SocialMediaScheduler()

        # Initialize tools
        self.tools = []
        self.tools.extend(get_social_media_tools())
        self.tools.extend(get_content_generation_tools(llm))

        # Create agent
        self.agent = self._create_agent()

    def _create_agent(self) -> AgentExecutor:
        """Create the agent executor"""
        profile = SocialMediaAgentProfile()

        # Create prompt template
        prompt = ChatPromptTemplate.from_messages([
            ("system", profile.system_prompt),
            ("system", profile.tools_description),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # Create agent
        agent = create_openai_functions_agent(self.llm, self.tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=10
        )

        return agent_executor

    async def process_request(
        self,
        request: str,
        chat_history: Optional[List] = None
    ) -> Dict[str, Any]:
        """Process a user request"""
        try:
            result = await self.agent.ainvoke({
                "input": request,
                "chat_history": chat_history or []
            })

            return {
                "status": "success",
                "response": result.get("output", ""),
                "intermediate_steps": result.get("intermediate_steps", [])
            }
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def create_content_campaign(
        self,
        topic: str,
        platforms: List[str],
        duration_days: int = 7,
        posts_per_day: int = 2
    ) -> Dict[str, Any]:
        """Create a complete content campaign with scheduled posts"""
        try:
            # Create campaign
            campaign = Campaign(
                name=f"{topic} Campaign",
                description=f"Automated campaign for {topic}",
                platforms=platforms,
                start_date=datetime.now(),
                end_date=datetime.now() + timedelta(days=duration_days),
                status=CampaignStatus.ACTIVE,
                goals=["engagement", "reach", "brand_awareness"]
            )

            campaign_id = self.scheduler.create_campaign(campaign)

            # Generate content for each day
            posts_created = []
            current_date = datetime.now()

            for day in range(duration_days):
                for post_num in range(posts_per_day):
                    for platform in platforms:
                        # Generate content using LLM
                        content_prompt = f"""Generate a {platform} post about {topic}.
                        This is post {post_num + 1} on day {day + 1} of the campaign.
                        Make it engaging and relevant."""

                        messages = [
                            SystemMessage(content="You are an expert social media content creator."),
                            HumanMessage(content=content_prompt)
                        ]

                        response = await self.llm.ainvoke(messages)
                        content = response.content.strip()

                        # Generate hashtags
                        hashtags = await self._generate_hashtags(content, platform)

                        # Calculate optimal posting time
                        optimal_times = self.scheduler.get_optimal_posting_times(platform)
                        hour = int(optimal_times[post_num % len(optimal_times)]["time"].split(":")[0])

                        scheduled_time = current_date.replace(hour=hour, minute=0) + timedelta(days=day)

                        # Create scheduled post
                        post = ScheduledPost(
                            platform=platform,
                            content=content,
                            hashtags=hashtags,
                            scheduled_time=scheduled_time,
                            campaign_id=campaign_id,
                            status=PostStatus.SCHEDULED
                        )

                        post_id = self.scheduler.schedule_post(post)
                        posts_created.append({
                            "post_id": post_id,
                            "platform": platform,
                            "scheduled_time": scheduled_time.isoformat()
                        })

            return {
                "status": "success",
                "campaign_id": campaign_id,
                "posts_created": len(posts_created),
                "posts": posts_created[:10],  # Return first 10 as preview
                "message": f"Created campaign with {len(posts_created)} scheduled posts"
            }

        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def _generate_hashtags(self, content: str, platform: str, count: int = 3) -> List[str]:
        """Generate hashtags for content"""
        try:
            prompt = f"Generate {count} relevant hashtags for this {platform} post: {content}"
            messages = [
                SystemMessage(content="Generate only hashtag words without # symbol, one per line."),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)
            hashtags = [line.strip().replace("#", "") for line in response.content.strip().split("\n")]
            return [tag for tag in hashtags if tag][:count]

        except Exception as e:
            logger.error(f"Error generating hashtags: {e}")
            return ["Innovation", "Technology", "Business"]

    async def get_content_suggestions(
        self,
        platform: str,
        topic: Optional[str] = None,
        count: int = 5
    ) -> Dict[str, Any]:
        """Get content suggestions based on trends and best practices"""
        try:
            prompt = f"""Suggest {count} engaging post ideas for {platform}"""
            if topic:
                prompt += f" about {topic}"

            prompt += """\n\nFor each idea provide:
1. A brief title
2. The post content (platform-appropriate length)
3. Why this would perform well

Format as JSON array with keys: title, content, reasoning"""

            messages = [
                SystemMessage(content="You are a social media strategist."),
                HumanMessage(content=prompt)
            ]

            response = await self.llm.ainvoke(messages)

            try:
                suggestions = json.loads(response.content)
                return {
                    "status": "success",
                    "platform": platform,
                    "suggestions": suggestions
                }
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    "status": "success",
                    "platform": platform,
                    "suggestions": [
                        {
                            "title": "Industry Insight",
                            "content": f"Share your perspective on the latest trends in {topic or 'your industry'}",
                            "reasoning": "Educational content performs well and establishes thought leadership"
                        }
                    ]
                }

        except Exception as e:
            logger.error(f"Error getting suggestions: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    def get_campaign_overview(self, campaign_id: str) -> Dict[str, Any]:
        """Get comprehensive overview of a campaign"""
        try:
            campaign = self.scheduler.get_campaign(campaign_id)
            if not campaign:
                return {
                    "status": "error",
                    "message": "Campaign not found"
                }

            stats = self.scheduler.get_campaign_stats(campaign_id)
            posts = self.scheduler.list_posts(campaign_id=campaign_id, limit=50)

            return {
                "status": "success",
                "campaign": {
                    "id": campaign.id,
                    "name": campaign.name,
                    "description": campaign.description,
                    "platforms": campaign.platforms,
                    "start_date": campaign.start_date.isoformat(),
                    "end_date": campaign.end_date.isoformat() if campaign.end_date else None,
                    "status": campaign.status.value
                },
                "stats": stats,
                "recent_posts": [
                    {
                        "id": post.id,
                        "platform": post.platform,
                        "content": post.content[:100] + "..." if len(post.content) > 100 else post.content,
                        "scheduled_time": post.scheduled_time.isoformat(),
                        "status": post.status.value
                    }
                    for post in posts[:10]
                ]
            }

        except Exception as e:
            logger.error(f"Error getting campaign overview: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    async def analyze_performance(
        self,
        platform: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Analyze social media performance"""
        try:
            # Get published posts from the last N days
            cutoff_date = datetime.now() - timedelta(days=days)
            posts = self.scheduler.list_posts(
                status=PostStatus.PUBLISHED,
                platform=platform,
                limit=1000
            )

            # Filter by date
            recent_posts = [
                p for p in posts
                if p.published_at and p.published_at >= cutoff_date
            ]

            # Calculate metrics
            total_posts = len(recent_posts)
            platforms_used = len(set(p.platform for p in recent_posts))

            # Group by platform
            by_platform = {}
            for post in recent_posts:
                if post.platform not in by_platform:
                    by_platform[post.platform] = []
                by_platform[post.platform].append(post)

            platform_summary = {
                platform: {
                    "posts": len(posts),
                    "percentage": (len(posts) / total_posts * 100) if total_posts > 0 else 0
                }
                for platform, posts in by_platform.items()
            }

            return {
                "status": "success",
                "period_days": days,
                "total_posts": total_posts,
                "platforms_used": platforms_used,
                "platform_breakdown": platform_summary,
                "avg_posts_per_day": total_posts / days if days > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return {
                "status": "error",
                "message": str(e)
            }


# Convenience function to create agent
def create_social_media_agent(llm: BaseChatModel) -> SocialMediaAgent:
    """Create a social media automation agent"""
    return SocialMediaAgent(llm)
