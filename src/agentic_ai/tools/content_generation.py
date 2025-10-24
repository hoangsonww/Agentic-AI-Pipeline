"""
Content Generation Tools for Social Media

This module provides AI-powered tools for generating social media content,
hashtags, captions, and post ideas across different platforms.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import Field

logger = logging.getLogger(__name__)


class ContentGenerator:
    """AI-powered content generator for social media"""

    def __init__(self, llm: Optional[BaseChatModel] = None):
        self.llm = llm

    async def generate_post_content(
        self,
        topic: str,
        platform: str,
        tone: str = "professional",
        max_length: Optional[int] = None
    ) -> str:
        """Generate social media post content"""

        platform_limits = {
            "twitter": 280,
            "linkedin": 3000,
            "instagram": 2200,
            "facebook": 63206
        }

        char_limit = max_length or platform_limits.get(platform.lower(), 280)

        prompt = f"""Generate a {tone} social media post for {platform} about: {topic}

Platform: {platform}
Tone: {tone}
Character limit: {char_limit}

Requirements:
- Keep it concise and engaging
- Use appropriate tone for the platform
- Include a call-to-action if relevant
- Stay within the character limit
- DO NOT include hashtags (they will be added separately)

Generate only the post content, nothing else."""

        if self.llm:
            try:
                messages = [
                    SystemMessage(content="You are an expert social media content creator."),
                    HumanMessage(content=prompt)
                ]
                response = await self.llm.ainvoke(messages)
                content = response.content.strip()

                # Ensure we're within character limit
                if len(content) > char_limit:
                    content = content[:char_limit-3] + "..."

                return content
            except Exception as e:
                logger.error(f"Error generating content with LLM: {e}")

        # Fallback to template-based generation
        templates = {
            "twitter": f"🚀 Exciting news about {topic}! Learn more about how this is changing the game. #Innovation",
            "linkedin": f"I wanted to share some insights about {topic}.\n\nThis development represents a significant step forward in our industry. What are your thoughts?",
            "instagram": f"Today we're exploring {topic} ✨\n\nSwipe to learn more! 👉",
            "facebook": f"We're thrilled to share updates about {topic}!\n\nJoin the conversation and let us know what you think. 💭"
        }

        return templates.get(platform.lower(), f"Check out our latest update on {topic}!")

    async def generate_hashtags(
        self,
        content: str,
        platform: str,
        count: int = 5
    ) -> List[str]:
        """Generate relevant hashtags for content"""

        prompt = f"""Generate {count} relevant and popular hashtags for this {platform} post:

Content: {content}

Requirements:
- Generate exactly {count} hashtags
- Make them relevant to the content
- Use popular and trending hashtags when appropriate
- Mix broad and specific hashtags
- Format: return only hashtag words (without #), one per line

Generate hashtags:"""

        if self.llm:
            try:
                messages = [
                    SystemMessage(content="You are an expert in social media hashtag strategy."),
                    HumanMessage(content=prompt)
                ]
                response = await self.llm.ainvoke(messages)
                hashtags_text = response.content.strip()

                # Parse hashtags
                hashtags = []
                for line in hashtags_text.split('\n'):
                    line = line.strip()
                    # Remove # if present, remove numbering, clean up
                    tag = re.sub(r'^[\d\.\)\-\s#]+', '', line)
                    tag = tag.replace('#', '').strip()
                    if tag:
                        hashtags.append(tag)

                return hashtags[:count]
            except Exception as e:
                logger.error(f"Error generating hashtags with LLM: {e}")

        # Fallback hashtags based on common keywords
        common_hashtags = [
            "Innovation", "Technology", "Business", "Growth", "Success",
            "AI", "MachineLearning", "Automation", "Digital", "Future"
        ]
        return common_hashtags[:count]

    async def generate_thread(
        self,
        topic: str,
        num_tweets: int = 5,
        tone: str = "professional"
    ) -> List[str]:
        """Generate a Twitter thread"""

        prompt = f"""Generate a Twitter thread with {num_tweets} tweets about: {topic}

Tone: {tone}

Requirements:
- Each tweet must be under 280 characters
- Start with a hook in the first tweet
- Build a narrative across the thread
- End with a call-to-action or conclusion
- Use thread numbering (1/{num_tweets}, 2/{num_tweets}, etc.)
- DO NOT include hashtags

Format: Return each tweet on a new line, separated by "---"

Generate the thread:"""

        if self.llm:
            try:
                messages = [
                    SystemMessage(content="You are an expert at creating engaging Twitter threads."),
                    HumanMessage(content=prompt)
                ]
                response = await self.llm.ainvoke(messages)
                thread_text = response.content.strip()

                # Parse tweets
                tweets = [t.strip() for t in thread_text.split('---') if t.strip()]

                # Ensure character limits
                tweets = [t[:277] + "..." if len(t) > 280 else t for t in tweets]

                return tweets[:num_tweets]
            except Exception as e:
                logger.error(f"Error generating thread with LLM: {e}")

        # Fallback thread
        return [
            f"1/{num_tweets} Let's talk about {topic} 🧵",
            f"2/{num_tweets} This is an important development that's shaping our industry.",
            f"3/{num_tweets} Here's what you need to know about the key benefits and opportunities.",
            f"4/{num_tweets} The implications are far-reaching and will impact how we work.",
            f"{num_tweets}/{num_tweets} What are your thoughts? Let's discuss in the comments! 💬"
        ][:num_tweets]

    async def optimize_content(
        self,
        content: str,
        platform: str,
        goal: str = "engagement"
    ) -> Dict[str, Any]:
        """Optimize content for a specific platform and goal"""

        prompt = f"""Optimize this social media content for {platform}:

Original content: {content}

Platform: {platform}
Goal: {goal}

Provide optimization suggestions:
1. Improved version of the content
2. Best time to post
3. Recommended hashtags (3-5)
4. Engagement tips

Format your response as JSON with keys: optimized_content, best_time, hashtags, tips"""

        if self.llm:
            try:
                messages = [
                    SystemMessage(content="You are a social media optimization expert."),
                    HumanMessage(content=prompt)
                ]
                response = await self.llm.ainvoke(messages)

                # Try to parse JSON response
                try:
                    result = json.loads(response.content)
                    return result
                except json.JSONDecodeError:
                    # Fallback structure
                    pass
            except Exception as e:
                logger.error(f"Error optimizing content with LLM: {e}")

        # Fallback optimization
        return {
            "optimized_content": content,
            "best_time": "9:00 AM or 1:00 PM on weekdays",
            "hashtags": ["Innovation", "Technology", "Business"],
            "tips": [
                "Add emojis for visual appeal",
                "Ask a question to encourage engagement",
                "Include a call-to-action"
            ]
        }

    async def generate_caption(
        self,
        image_description: str,
        platform: str,
        tone: str = "casual"
    ) -> str:
        """Generate a caption for an image post"""

        prompt = f"""Generate a {tone} caption for a {platform} image post.

Image description: {image_description}

Requirements:
- Match the {tone} tone
- Be engaging and relevant
- Appropriate length for {platform}
- DO NOT include hashtags

Generate only the caption:"""

        if self.llm:
            try:
                messages = [
                    SystemMessage(content="You are an expert at writing engaging social media captions."),
                    HumanMessage(content=prompt)
                ]
                response = await self.llm.ainvoke(messages)
                return response.content.strip()
            except Exception as e:
                logger.error(f"Error generating caption with LLM: {e}")

        # Fallback caption
        return f"Capturing the moment 📸 {image_description}"


class ContentGenerationTool(BaseTool):
    """Tool for generating social media content"""

    name: str = "generate_social_content"
    description: str = """Generate social media post content using AI.
    Input should be a JSON string with: topic, platform, tone (optional), max_length (optional).
    Example: {"topic": "AI innovation", "platform": "twitter", "tone": "professional"}
    Supported tones: professional, casual, enthusiastic, informative, humorous
    """

    llm: Optional[BaseChatModel] = Field(default=None)

    def _run(self, query: str) -> str:
        """Synchronous version (not implemented)"""
        return "Use async version"

    async def _arun(self, query: str) -> str:
        """Generate social media content"""
        try:
            data = json.loads(query)
            topic = data.get("topic", "")
            platform = data.get("platform", "twitter")
            tone = data.get("tone", "professional")
            max_length = data.get("max_length")

            if not topic:
                return json.dumps({"status": "error", "message": "Topic is required"})

            generator = ContentGenerator(self.llm)
            content = await generator.generate_post_content(topic, platform, tone, max_length)

            return json.dumps({
                "status": "success",
                "content": content,
                "platform": platform,
                "tone": tone,
                "character_count": len(content)
            }, indent=2)
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return json.dumps({"status": "error", "message": str(e)})


class HashtagGenerationTool(BaseTool):
    """Tool for generating hashtags"""

    name: str = "generate_hashtags"
    description: str = """Generate relevant hashtags for social media content.
    Input should be a JSON string with: content, platform, count (optional, default 5).
    Example: {"content": "Check out our new AI product!", "platform": "twitter", "count": 5}
    """

    llm: Optional[BaseChatModel] = Field(default=None)

    def _run(self, query: str) -> str:
        """Synchronous version (not implemented)"""
        return "Use async version"

    async def _arun(self, query: str) -> str:
        """Generate hashtags for content"""
        try:
            data = json.loads(query)
            content = data.get("content", "")
            platform = data.get("platform", "twitter")
            count = data.get("count", 5)

            if not content:
                return json.dumps({"status": "error", "message": "Content is required"})

            generator = ContentGenerator(self.llm)
            hashtags = await generator.generate_hashtags(content, platform, count)

            return json.dumps({
                "status": "success",
                "hashtags": hashtags,
                "formatted": " ".join(f"#{tag}" for tag in hashtags)
            }, indent=2)
        except Exception as e:
            logger.error(f"Error generating hashtags: {e}")
            return json.dumps({"status": "error", "message": str(e)})


class ThreadGenerationTool(BaseTool):
    """Tool for generating Twitter threads"""

    name: str = "generate_twitter_thread"
    description: str = """Generate a Twitter thread on a topic.
    Input should be a JSON string with: topic, num_tweets (optional, default 5), tone (optional).
    Example: {"topic": "The future of AI", "num_tweets": 7, "tone": "enthusiastic"}
    """

    llm: Optional[BaseChatModel] = Field(default=None)

    def _run(self, query: str) -> str:
        """Synchronous version (not implemented)"""
        return "Use async version"

    async def _arun(self, query: str) -> str:
        """Generate a Twitter thread"""
        try:
            data = json.loads(query)
            topic = data.get("topic", "")
            num_tweets = data.get("num_tweets", 5)
            tone = data.get("tone", "professional")

            if not topic:
                return json.dumps({"status": "error", "message": "Topic is required"})

            generator = ContentGenerator(self.llm)
            tweets = await generator.generate_thread(topic, num_tweets, tone)

            return json.dumps({
                "status": "success",
                "topic": topic,
                "num_tweets": len(tweets),
                "tweets": tweets
            }, indent=2)
        except Exception as e:
            logger.error(f"Error generating thread: {e}")
            return json.dumps({"status": "error", "message": str(e)})


class ContentOptimizationTool(BaseTool):
    """Tool for optimizing social media content"""

    name: str = "optimize_social_content"
    description: str = """Optimize social media content for better engagement.
    Input should be a JSON string with: content, platform, goal (optional, default 'engagement').
    Example: {"content": "Our new product launch", "platform": "linkedin", "goal": "engagement"}
    Goals: engagement, reach, conversions, brand_awareness
    """

    llm: Optional[BaseChatModel] = Field(default=None)

    def _run(self, query: str) -> str:
        """Synchronous version (not implemented)"""
        return "Use async version"

    async def _arun(self, query: str) -> str:
        """Optimize social media content"""
        try:
            data = json.loads(query)
            content = data.get("content", "")
            platform = data.get("platform", "twitter")
            goal = data.get("goal", "engagement")

            if not content:
                return json.dumps({"status": "error", "message": "Content is required"})

            generator = ContentGenerator(self.llm)
            optimization = await generator.optimize_content(content, platform, goal)

            return json.dumps({
                "status": "success",
                "original_content": content,
                "optimization": optimization
            }, indent=2)
        except Exception as e:
            logger.error(f"Error optimizing content: {e}")
            return json.dumps({"status": "error", "message": str(e)})


class CaptionGenerationTool(BaseTool):
    """Tool for generating image captions"""

    name: str = "generate_image_caption"
    description: str = """Generate a caption for an image post.
    Input should be a JSON string with: image_description, platform, tone (optional).
    Example: {"image_description": "sunset over mountains", "platform": "instagram", "tone": "inspiring"}
    """

    llm: Optional[BaseChatModel] = Field(default=None)

    def _run(self, query: str) -> str:
        """Synchronous version (not implemented)"""
        return "Use async version"

    async def _arun(self, query: str) -> str:
        """Generate an image caption"""
        try:
            data = json.loads(query)
            image_description = data.get("image_description", "")
            platform = data.get("platform", "instagram")
            tone = data.get("tone", "casual")

            if not image_description:
                return json.dumps({"status": "error", "message": "Image description is required"})

            generator = ContentGenerator(self.llm)
            caption = await generator.generate_caption(image_description, platform, tone)

            return json.dumps({
                "status": "success",
                "caption": caption,
                "platform": platform,
                "tone": tone
            }, indent=2)
        except Exception as e:
            logger.error(f"Error generating caption: {e}")
            return json.dumps({"status": "error", "message": str(e)})


# Export all content generation tools
def get_content_generation_tools(llm: Optional[BaseChatModel] = None) -> List[BaseTool]:
    """Get all content generation tools"""
    return [
        ContentGenerationTool(llm=llm),
        HashtagGenerationTool(llm=llm),
        ThreadGenerationTool(llm=llm),
        ContentOptimizationTool(llm=llm),
        CaptionGenerationTool(llm=llm)
    ]
