#!/usr/bin/env python3
"""
Social Media Automation Example

This script demonstrates how to use the social media automation features
of the Agentic AI Pipeline.
"""

import asyncio
import json
from datetime import datetime, timedelta

# Import the social media components
from agentic_ai.agents.social_media_agent import create_social_media_agent
from agentic_ai.social_media_scheduler import (
    SocialMediaScheduler,
    ScheduledPost,
    Campaign,
    PostStatus,
    CampaignStatus
)
from agentic_ai.tools.social_media_tools import (
    SocialMediaPostTool,
    SocialMediaTrendingTool,
    get_social_media_tools
)
from agentic_ai.tools.content_generation import (
    ContentGenerator,
    get_content_generation_tools
)
from agentic_ai.llm.client import get_llm


async def example_1_generate_content():
    """Example 1: Generate social media content using AI"""
    print("\n" + "="*70)
    print("Example 1: Generate Social Media Content")
    print("="*70 + "\n")

    llm = get_llm()
    generator = ContentGenerator(llm)

    # Generate a Twitter post
    print("Generating Twitter post about AI innovation...")
    content = await generator.generate_post_content(
        topic="AI innovation in healthcare",
        platform="twitter",
        tone="professional"
    )
    print(f"Generated content: {content}\n")

    # Generate hashtags
    print("Generating hashtags...")
    hashtags = await generator.generate_hashtags(content, "twitter", count=5)
    print(f"Hashtags: {', '.join(['#' + tag for tag in hashtags])}\n")

    # Generate a thread
    print("Generating Twitter thread...")
    thread = await generator.generate_thread(
        topic="The future of artificial intelligence",
        num_tweets=5,
        tone="enthusiastic"
    )
    print("Thread:")
    for i, tweet in enumerate(thread, 1):
        print(f"  {i}. {tweet}")
    print()


async def example_2_schedule_posts():
    """Example 2: Schedule social media posts"""
    print("\n" + "="*70)
    print("Example 2: Schedule Social Media Posts")
    print("="*70 + "\n")

    scheduler = SocialMediaScheduler()

    # Schedule a post for tomorrow
    tomorrow = datetime.now() + timedelta(days=1)
    post = ScheduledPost(
        platform="twitter",
        content="Excited to share our latest AI breakthrough! 🚀",
        hashtags=["AI", "Innovation", "TechNews"],
        scheduled_time=tomorrow,
        status=PostStatus.SCHEDULED
    )

    post_id = scheduler.schedule_post(post)
    print(f"✅ Post scheduled successfully!")
    print(f"   Post ID: {post_id}")
    print(f"   Platform: {post.platform}")
    print(f"   Scheduled for: {post.scheduled_time}")
    print(f"   Content: {post.content}\n")


async def example_3_create_campaign():
    """Example 3: Create a multi-platform campaign"""
    print("\n" + "="*70)
    print("Example 3: Create Multi-Platform Campaign")
    print("="*70 + "\n")

    llm = get_llm()
    agent = create_social_media_agent(llm)

    # Create a week-long campaign
    print("Creating 7-day campaign across Twitter and LinkedIn...")
    result = await agent.create_content_campaign(
        topic="AI and Machine Learning Best Practices",
        platforms=["twitter", "linkedin"],
        duration_days=7,
        posts_per_day=2
    )

    if result["status"] == "success":
        print(f"✅ Campaign created successfully!")
        print(f"   Campaign ID: {result['campaign_id']}")
        print(f"   Total posts scheduled: {result['posts_created']}")
        print(f"\n   First 5 scheduled posts:")
        for i, post in enumerate(result['posts'][:5], 1):
            print(f"   {i}. [{post['platform']}] at {post['scheduled_time']}")
    else:
        print(f"❌ Campaign creation failed: {result['message']}")
    print()


async def example_4_get_trends():
    """Example 4: Get trending topics"""
    print("\n" + "="*70)
    print("Example 4: Get Trending Topics")
    print("="*70 + "\n")

    trending_tool = SocialMediaTrendingTool()

    # Get Twitter trends
    print("Fetching trending topics on Twitter...")
    result = await trending_tool._arun("twitter")
    data = json.loads(result)

    if data["status"] == "success":
        print("Top trending topics:")
        for i, trend in enumerate(data["trends"][:10], 1):
            volume = trend.get("tweet_volume", trend.get("engagement", 0))
            print(f"   {i}. {trend['name']} ({volume:,} engagements)")
    print()


async def example_5_optimize_content():
    """Example 5: Optimize content for better engagement"""
    print("\n" + "="*70)
    print("Example 5: Optimize Content")
    print("="*70 + "\n")

    llm = get_llm()
    generator = ContentGenerator(llm)

    original_content = "We just launched a new product"

    print(f"Original content: {original_content}\n")
    print("Optimizing for LinkedIn...")

    optimization = await generator.optimize_content(
        content=original_content,
        platform="linkedin",
        goal="engagement"
    )

    print(f"Optimized content: {optimization['optimized_content']}")
    print(f"Best time to post: {optimization['best_time']}")
    print(f"Recommended hashtags: {', '.join(['#' + tag for tag in optimization['hashtags']])}")
    print(f"\nEngagement tips:")
    for tip in optimization['tips']:
        print(f"   • {tip}")
    print()


async def example_6_manage_campaigns():
    """Example 6: Manage campaigns and view statistics"""
    print("\n" + "="*70)
    print("Example 6: Campaign Management")
    print("="*70 + "\n")

    scheduler = SocialMediaScheduler()

    # Create a sample campaign
    campaign = Campaign(
        name="Summer Product Launch",
        description="Promoting our new AI-powered features",
        platforms=["twitter", "linkedin", "instagram"],
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=14),
        status=CampaignStatus.ACTIVE,
        budget=5000.0,
        goals=["brand_awareness", "engagement", "conversions"]
    )

    campaign_id = scheduler.create_campaign(campaign)
    print(f"✅ Campaign created: {campaign.name}")
    print(f"   Campaign ID: {campaign_id}")
    print(f"   Platforms: {', '.join(campaign.platforms)}")
    print(f"   Duration: {campaign.start_date.date()} to {campaign.end_date.date()}")
    print(f"   Budget: ${campaign.budget:,.2f}")
    print(f"   Status: {campaign.status.value}")

    # List all campaigns
    print("\nAll campaigns:")
    campaigns = scheduler.list_campaigns()
    for i, camp in enumerate(campaigns[:5], 1):
        print(f"   {i}. {camp.name} - {camp.status.value}")
    print()


async def example_7_agent_natural_language():
    """Example 7: Use the agent with natural language"""
    print("\n" + "="*70)
    print("Example 7: Natural Language Agent Interaction")
    print("="*70 + "\n")

    llm = get_llm()
    agent = create_social_media_agent(llm)

    # Ask the agent to perform tasks using natural language
    queries = [
        "What are the best times to post on Twitter?",
        "Generate 3 ideas for LinkedIn posts about AI ethics",
        "Create a professional tweet about machine learning",
    ]

    for query in queries:
        print(f"Query: {query}")
        result = await agent.process_request(query)

        if result["status"] == "success":
            print(f"Response: {result['response']}\n")
        else:
            print(f"Error: {result['message']}\n")


async def example_8_scheduled_posts_management():
    """Example 8: Manage scheduled posts"""
    print("\n" + "="*70)
    print("Example 8: Scheduled Posts Management")
    print("="*70 + "\n")

    scheduler = SocialMediaScheduler()

    # Schedule multiple posts
    platforms = ["twitter", "linkedin"]
    for i in range(3):
        for platform in platforms:
            post = ScheduledPost(
                platform=platform,
                content=f"Sample post {i+1} for {platform}",
                hashtags=["AI", "Tech"],
                scheduled_time=datetime.now() + timedelta(days=i+1, hours=10),
                status=PostStatus.SCHEDULED
            )
            scheduler.schedule_post(post)

    # List scheduled posts
    print("Scheduled posts:")
    posts = scheduler.list_posts(status=PostStatus.SCHEDULED, limit=10)
    for i, post in enumerate(posts, 1):
        print(f"   {i}. [{post.platform}] {post.content[:50]}...")
        print(f"      Scheduled for: {post.scheduled_time}")
        print(f"      Hashtags: {', '.join(['#' + tag for tag in post.hashtags])}")
        print()

    # Get posts due soon
    print("Posts due in the next 24 hours:")
    due_posts = scheduler.get_posts_due(within_minutes=1440)  # 24 hours
    print(f"   {len(due_posts)} posts due")
    print()


async def example_9_analytics():
    """Example 9: View analytics and performance"""
    print("\n" + "="*70)
    print("Example 9: Analytics & Performance")
    print("="*70 + "\n")

    llm = get_llm()
    agent = create_social_media_agent(llm)

    # Get performance analytics
    print("Analyzing social media performance (last 30 days)...")
    analytics = await agent.analyze_performance(days=30)

    if analytics["status"] == "success":
        print(f"Total posts: {analytics['total_posts']}")
        print(f"Platforms used: {analytics['platforms_used']}")
        print(f"Average posts per day: {analytics['avg_posts_per_day']:.1f}")

        if analytics.get('platform_breakdown'):
            print("\nPlatform breakdown:")
            for platform, stats in analytics['platform_breakdown'].items():
                print(f"   {platform}: {stats['posts']} posts ({stats['percentage']:.1f}%)")
    print()


async def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("SOCIAL MEDIA AUTOMATION EXAMPLES")
    print("="*70)

    examples = [
        ("Generate Content", example_1_generate_content),
        ("Schedule Posts", example_2_schedule_posts),
        ("Create Campaign", example_3_create_campaign),
        ("Get Trends", example_4_get_trends),
        ("Optimize Content", example_5_optimize_content),
        ("Manage Campaigns", example_6_manage_campaigns),
        ("Natural Language Agent", example_7_agent_natural_language),
        ("Scheduled Posts Management", example_8_scheduled_posts_management),
        ("Analytics", example_9_analytics),
    ]

    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"   {i}. {name}")

    print("\nRunning quick demo with Examples 1, 2, and 4...\n")

    try:
        # Run a few examples (not all to keep it quick)
        await example_1_generate_content()
        await example_2_schedule_posts()
        await example_4_get_trends()

        print("\n" + "="*70)
        print("Demo completed! To run specific examples, modify the main() function.")
        print("="*70 + "\n")

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        print("Make sure you have:")
        print("   1. Installed all dependencies: pip install -r requirements.txt")
        print("   2. Set up your .env file with API credentials")
        print("   3. Set OPENAI_API_KEY or ANTHROPIC_API_KEY for content generation")


if __name__ == "__main__":
    asyncio.run(main())
