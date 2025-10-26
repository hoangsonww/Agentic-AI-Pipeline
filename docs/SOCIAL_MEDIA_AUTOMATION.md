# Social Media Automation

## Overview

The Social Media Automation module provides AI-powered tools for managing social media presence across multiple platforms including Twitter/X, LinkedIn, Instagram, and Facebook.

## Features

### 🤖 AI-Powered Content Generation
- **Intelligent Post Creation**: Generate platform-specific content using LLMs
- **Hashtag Recommendations**: AI-generated relevant hashtags for maximum reach
- **Thread Generation**: Create engaging Twitter threads automatically
- **Content Optimization**: Optimize posts for engagement and reach
- **Caption Writing**: Generate compelling captions for visual content

### 📅 Smart Scheduling
- **Optimal Timing**: Posts scheduled at platform-specific optimal times
- **Campaign Management**: Create multi-platform, multi-day campaigns
- **Bulk Scheduling**: Schedule multiple posts across platforms
- **Post Status Tracking**: Track draft, scheduled, published, and failed posts
- **SQLite Backend**: Persistent storage for all scheduled content

### 📊 Analytics & Insights
- **Performance Tracking**: Monitor post engagement and reach
- **Platform Comparison**: Compare performance across platforms
- **Trend Analysis**: Identify trending topics and hashtags
- **Campaign Statistics**: Comprehensive campaign performance metrics

### 🔧 Multi-Platform Support
- **Twitter/X**: Tweets, threads, trending topics, search
- **LinkedIn**: Professional posts, articles, company updates
- **Instagram**: Photos, carousels, stories (via Meta Graph API)
- **Facebook**: Posts, page management

## Architecture

```
src/agentic_ai/
├── agents/
│   └── social_media_agent.py      # Main orchestration agent
├── tools/
│   ├── social_media_tools.py      # Platform API integrations
│   └── content_generation.py      # AI content generation tools
├── social_media_scheduler.py      # Scheduling & campaign management
└── social_media_api.py            # FastAPI REST endpoints

web/
└── social_media.html              # Web-based dashboard UI
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Credentials

Create a `.env` file with your social media API credentials:

```bash
# Twitter/X API (v2)
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_SECRET=your_access_secret
TWITTER_BEARER_TOKEN=your_bearer_token

# LinkedIn API
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
LINKEDIN_ACCESS_TOKEN=your_access_token

# Instagram API (Meta Graph API)
INSTAGRAM_ACCESS_TOKEN=your_access_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_account_id

# Facebook API
FACEBOOK_ACCESS_TOKEN=your_access_token
FACEBOOK_PAGE_ID=your_page_id

# LLM for content generation
OPENAI_API_KEY=your_openai_key
# or
ANTHROPIC_API_KEY=your_anthropic_key
```

### 3. Initialize the Database

The SQLite database will be automatically created on first run at `.sqlite/social_media.db`.

## Usage

### Starting the Server

```bash
# Start the FastAPI server
uvicorn agentic_ai.app:app --reload --host 0.0.0.0 --port 8000
```

Access the dashboard at: `http://localhost:8000/social_media.html`

### API Endpoints

#### Health Check
```bash
GET /api/social/health
```

#### Create/Schedule Post
```bash
POST /api/social/post
Content-Type: application/json

{
  "platform": "twitter",
  "content": "Check out our latest AI innovation!",
  "hashtags": ["AI", "Innovation", "Tech"],
  "scheduled_time": "2025-10-25T10:00:00"  # Optional
}
```

#### Generate Content
```bash
POST /api/social/generate-content
Content-Type: application/json

{
  "topic": "AI in Healthcare",
  "platform": "linkedin",
  "tone": "professional",
  "count": 3
}
```

#### Generate Twitter Thread
```bash
POST /api/social/generate-thread
Content-Type: application/json

{
  "topic": "The Future of AI",
  "num_tweets": 5,
  "tone": "enthusiastic"
}
```

#### Create Campaign
```bash
POST /api/social/campaigns
Content-Type: application/json

{
  "name": "Product Launch Campaign",
  "description": "Promoting our new AI product",
  "topic": "AI Product Innovation",
  "platforms": ["twitter", "linkedin", "instagram"],
  "duration_days": 7,
  "posts_per_day": 2
}
```

#### List Campaigns
```bash
GET /api/social/campaigns?status=active
```

#### Get Campaign Details
```bash
GET /api/social/campaigns/{campaign_id}
```

#### List Scheduled Posts
```bash
GET /api/social/posts?platform=twitter&status=scheduled&limit=50
```

#### Delete Post
```bash
DELETE /api/social/posts/{post_id}
```

#### Get Trending Topics
```bash
GET /api/social/trending/twitter
```

#### Get Analytics
```bash
GET /api/social/analytics?platform=twitter&days=30
```

#### Get Optimal Posting Times
```bash
GET /api/social/optimal-times/linkedin
```

#### Query Agent (Natural Language)
```bash
POST /api/social/agent/query
Content-Type: application/json

{
  "query": "Create a week-long campaign about AI innovation on Twitter and LinkedIn",
  "chat_history": []
}
```

#### Start/Stop Scheduler Service
```bash
POST /api/social/scheduler/start
POST /api/social/scheduler/stop
```

## Using the Agent

### Python API

```python
from agentic_ai.agents.social_media_agent import create_social_media_agent
from agentic_ai.llm.client import get_llm

# Initialize agent
llm = get_llm()
agent = create_social_media_agent(llm)

# Generate content
result = await agent.process_request(
    "Create 3 engaging tweets about AI innovation"
)

# Create campaign
campaign_result = await agent.create_content_campaign(
    topic="AI in Healthcare",
    platforms=["twitter", "linkedin"],
    duration_days=7,
    posts_per_day=2
)

# Get content suggestions
suggestions = await agent.get_content_suggestions(
    platform="linkedin",
    topic="Machine Learning",
    count=5
)

# Analyze performance
analytics = await agent.analyze_performance(
    platform="twitter",
    days=30
)
```

### Using Tools Directly

```python
from agentic_ai.tools.social_media_tools import SocialMediaPostTool, SocialMediaTrendingTool
from agentic_ai.tools.content_generation import ContentGenerationTool, HashtagGenerationTool

# Post to social media
post_tool = SocialMediaPostTool()
result = await post_tool._arun(json.dumps({
    "platform": "twitter",
    "content": "Exciting AI news!",
    "hashtags": ["AI", "Tech"]
}))

# Generate content
content_tool = ContentGenerationTool(llm=llm)
content = await content_tool._arun(json.dumps({
    "topic": "AI Innovation",
    "platform": "twitter",
    "tone": "professional"
}))

# Generate hashtags
hashtag_tool = HashtagGenerationTool(llm=llm)
hashtags = await hashtag_tool._arun(json.dumps({
    "content": "Just launched our new AI product!",
    "platform": "twitter",
    "count": 5
}))
```

## Web Dashboard

The web dashboard provides a user-friendly interface for:

- **Dashboard**: Overview of posts, campaigns, and activity
- **Create Post**: Manually create and schedule posts
- **Campaigns**: Create and manage multi-platform campaigns
- **Generate Content**: AI-powered content generation
- **Scheduled Posts**: View and manage scheduled content
- **Analytics**: Performance metrics and insights

Access at: `http://localhost:8000/social_media.html`

## Best Practices

### Content Strategy

1. **Platform-Specific Content**: Tailor content for each platform's audience and format
2. **Consistent Posting**: Maintain regular posting schedule using campaigns
3. **Engage with Trends**: Use trending topics and hashtags strategically
4. **Mix Content Types**: Alternate between promotional, educational, and engaging content
5. **Monitor Performance**: Review analytics regularly and adjust strategy

### Optimal Posting Times

The system provides platform-specific optimal posting times:

- **Twitter**: Weekdays at 9 AM, 12 PM, 3 PM
- **LinkedIn**: Tuesday-Thursday at 8 AM, 10 AM, 12 PM
- **Instagram**: Weekdays at 11 AM, 2 PM, 7 PM
- **Facebook**: Tuesday-Thursday at 1 PM, 3 PM

### Hashtag Strategy

- **Twitter**: 1-2 relevant hashtags
- **LinkedIn**: 3-5 professional hashtags
- **Instagram**: 10-20 mix of broad and niche hashtags
- **Facebook**: 2-3 hashtags (optional)

## Scheduling System

### Campaign Structure

A campaign consists of:
- Name and description
- Target platforms
- Start and end dates
- Status (active, paused, completed, draft)
- Budget and target audience (optional)
- Goals and objectives

### Post Lifecycle

```
DRAFT → SCHEDULED → PUBLISHED
                  → FAILED
                  → CANCELLED
```

### Scheduler Service

The background scheduler service:
1. Checks for posts due every minute
2. Publishes posts at scheduled times
3. Updates post status (published/failed)
4. Logs all activities
5. Handles errors gracefully

## Database Schema

### Campaigns Table
```sql
CREATE TABLE campaigns (
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
```

### Scheduled Posts Table
```sql
CREATE TABLE scheduled_posts (
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
```

## API Rate Limits

Be aware of platform API rate limits:

- **Twitter**: 300 requests per 15 minutes (user context)
- **LinkedIn**: Varies by endpoint, typically 100 requests per day
- **Instagram**: 200 calls per hour per user
- **Facebook**: 200 calls per hour per user

The system includes retry logic and exponential backoff for rate limit handling.

## Troubleshooting

### Posts Not Publishing

1. Check API credentials in `.env`
2. Verify scheduler service is running: `POST /api/social/scheduler/start`
3. Check post status in database or via API
4. Review logs for error messages

### Content Generation Issues

1. Ensure `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is set
2. Check LLM model availability
3. Verify internet connectivity
4. Review error logs for specific issues

### Database Errors

1. Check database file permissions: `.sqlite/social_media.db`
2. Verify SQLite version compatibility
3. Check disk space
4. Review database integrity

## Security Considerations

1. **API Keys**: Never commit API keys to version control
2. **Access Tokens**: Rotate tokens regularly
3. **Rate Limiting**: Implement rate limiting on API endpoints
4. **Input Validation**: All user inputs are validated
5. **HTTPS**: Use HTTPS in production
6. **Authentication**: Add authentication for production use

## Future Enhancements

- [ ] Media upload support (images, videos)
- [ ] Advanced analytics with charts
- [ ] A/B testing for content
- [ ] Automated response to mentions/comments
- [ ] Competitor analysis
- [ ] Sentiment analysis
- [ ] Multi-user support with roles
- [ ] Post approval workflows
- [ ] Integration with social media management tools
- [ ] Mobile app

## Contributing

Contributions are welcome! Areas for contribution:

1. Additional platform integrations (TikTok, Pinterest, etc.)
2. Advanced analytics features
3. Machine learning models for post optimization
4. UI/UX improvements
5. Testing and documentation
6. Bug fixes and performance improvements

## License

This module is part of the Agentic AI Pipeline project.

## Support

For issues, questions, or suggestions:
- GitHub Issues: [Create an issue]
- Documentation: See `docs/` directory
- Examples: See `examples/` directory

## Acknowledgments

- LangChain for agent framework
- FastAPI for web framework
- OpenAI/Anthropic for LLM capabilities
- Platform API providers (Twitter, LinkedIn, Meta)
