# 📱 Social Media Automation - Quick Start Guide

An AI-powered social media automation system built on the Agentic AI Pipeline.

## 🚀 Features

- **AI Content Generation**: Create engaging posts with GPT-4 or Claude
- **Multi-Platform Support**: Twitter, LinkedIn, Instagram, Facebook
- **Smart Scheduling**: Post at optimal times automatically
- **Campaign Management**: Run multi-day, multi-platform campaigns
- **Thread Generation**: Create Twitter threads automatically
- **Hashtag Recommendations**: AI-powered hashtag suggestions
- **Analytics**: Track performance across platforms
- **Web Dashboard**: Beautiful UI for managing everything

## ⚡ Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up API Keys

Copy the example environment file:

```bash
cp .env.social_media.example .env
```

Edit `.env` and add your API keys:

```bash
# Minimum required (for content generation)
OPENAI_API_KEY=your_key_here

# Optional: Social media platform keys
TWITTER_BEARER_TOKEN=your_token_here
LINKEDIN_ACCESS_TOKEN=your_token_here
# ... etc
```

**Note**: The system works in **simulation mode** without social media API keys. Posts will be created and scheduled but not actually published.

### 3. Start the Server

```bash
uvicorn agentic_ai.app:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open the Dashboard

Navigate to: http://localhost:8000/social_media.html

## 📖 Usage Examples

### Generate Content with AI

```python
from agentic_ai.tools.content_generation import ContentGenerator
from agentic_ai.llm.client import get_llm

llm = get_llm()
generator = ContentGenerator(llm)

# Generate a post
content = await generator.generate_post_content(
    topic="AI innovation",
    platform="twitter",
    tone="professional"
)

# Generate hashtags
hashtags = await generator.generate_hashtags(content, "twitter", count=5)
```

### Schedule a Post

```python
from agentic_ai.social_media_scheduler import SocialMediaScheduler, ScheduledPost
from datetime import datetime, timedelta

scheduler = SocialMediaScheduler()

post = ScheduledPost(
    platform="twitter",
    content="Exciting AI news! 🚀",
    hashtags=["AI", "Tech"],
    scheduled_time=datetime.now() + timedelta(hours=2)
)

post_id = scheduler.schedule_post(post)
```

### Create a Campaign

```python
from agentic_ai.agents.social_media_agent import create_social_media_agent

agent = create_social_media_agent(llm)

result = await agent.create_content_campaign(
    topic="AI Innovation",
    platforms=["twitter", "linkedin"],
    duration_days=7,
    posts_per_day=2
)
```

### Using the REST API

```bash
# Generate content
curl -X POST http://localhost:8000/api/social/generate-content \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "AI in Healthcare",
    "platform": "linkedin",
    "count": 3
  }'

# Schedule a post
curl -X POST http://localhost:8000/api/social/post \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "twitter",
    "content": "Check out our latest AI innovation!",
    "hashtags": ["AI", "Innovation"],
    "scheduled_time": "2025-10-25T10:00:00"
  }'

# Create a campaign
curl -X POST http://localhost:8000/api/social/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Product Launch",
    "description": "New AI product campaign",
    "topic": "AI Product Launch",
    "platforms": ["twitter", "linkedin"],
    "duration_days": 7,
    "posts_per_day": 2
  }'
```

## 🎯 Key Features Explained

### 1. AI-Powered Content Generation

Generate platform-optimized content automatically:
- **Twitter**: Concise, engaging tweets (280 chars)
- **LinkedIn**: Professional, longer-form posts
- **Instagram**: Visual-focused captions
- **Facebook**: Community-oriented content

### 2. Smart Scheduling

Posts are automatically scheduled at optimal times:
- **Twitter**: Weekdays 9 AM, 12 PM, 3 PM
- **LinkedIn**: Tue-Thu 8 AM, 10 AM, 12 PM
- **Instagram**: Mon-Fri 11 AM, 2 PM, 7 PM
- **Facebook**: Tue-Thu 1 PM, 3 PM

### 3. Campaign Management

Create multi-day campaigns with:
- Multiple platforms simultaneously
- Customizable posting frequency
- Automatic content generation for each post
- Progress tracking and analytics

### 4. Thread Generation

Create engaging Twitter threads automatically:
```python
thread = await generator.generate_thread(
    topic="The Future of AI",
    num_tweets=7,
    tone="enthusiastic"
)
```

### 5. Content Optimization

Optimize posts for maximum engagement:
```python
optimization = await generator.optimize_content(
    content="Original post text",
    platform="linkedin",
    goal="engagement"
)
```

## 🛠️ API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/social/health` | GET | Health check |
| `/api/social/post` | POST | Create/schedule post |
| `/api/social/generate-content` | POST | Generate AI content |
| `/api/social/generate-thread` | POST | Generate Twitter thread |
| `/api/social/campaigns` | POST | Create campaign |
| `/api/social/campaigns` | GET | List campaigns |
| `/api/social/campaigns/{id}` | GET | Get campaign details |
| `/api/social/posts` | GET | List scheduled posts |
| `/api/social/posts/{id}` | DELETE | Delete post |
| `/api/social/trending/{platform}` | GET | Get trending topics |
| `/api/social/analytics` | GET | Get analytics |
| `/api/social/optimal-times/{platform}` | GET | Get best posting times |
| `/api/social/agent/query` | POST | Natural language queries |

## 📊 Web Dashboard

The dashboard provides:

1. **Dashboard Tab**: Overview of activity and stats
2. **Create Post Tab**: Manual post creation and scheduling
3. **Campaigns Tab**: Create and manage campaigns
4. **Generate Content Tab**: AI content generation interface
5. **Scheduled Posts Tab**: View and manage scheduled content
6. **Analytics Tab**: Performance metrics and insights

## 🔐 Getting Social Media API Keys

### Twitter/X API
1. Go to https://developer.twitter.com/portal/dashboard
2. Create a new app
3. Generate API keys and bearer token
4. Add to `.env` file

### LinkedIn API
1. Go to https://www.linkedin.com/developers/apps
2. Create a new app
3. Get client ID, secret, and access token
4. Add to `.env` file

### Instagram API
1. Go to https://developers.facebook.com/apps/
2. Set up Facebook Business integration
3. Get access token for Instagram Business Account
4. Add to `.env` file

### Facebook API
1. Go to https://developers.facebook.com/apps/
2. Create app and get page access token
3. Add to `.env` file

## 🧪 Running Examples

Run the included example script:

```bash
python examples/social_media_example.py
```

This demonstrates:
- Content generation
- Post scheduling
- Campaign creation
- Trend analysis
- Content optimization
- Analytics

## 📁 Project Structure

```
src/agentic_ai/
├── agents/
│   └── social_media_agent.py      # Main orchestration agent
├── tools/
│   ├── social_media_tools.py      # Platform integrations
│   └── content_generation.py      # AI content tools
├── social_media_scheduler.py      # Scheduling system
└── social_media_api.py            # REST API endpoints

web/
└── social_media.html              # Web dashboard

examples/
└── social_media_example.py        # Usage examples

docs/
└── SOCIAL_MEDIA_AUTOMATION.md     # Full documentation
```

## 💡 Tips & Best Practices

### Content Strategy
- Post consistently (2-3 times per day)
- Mix content types (educational, promotional, engaging)
- Use relevant hashtags (but don't overdo it)
- Engage with your audience
- Monitor trends and adapt

### Hashtag Usage
- **Twitter**: 1-2 hashtags
- **LinkedIn**: 3-5 hashtags
- **Instagram**: 10-20 hashtags
- **Facebook**: 2-3 hashtags

### Optimal Timing
- Use the built-in optimal time recommendations
- Test different times for your audience
- Consider time zones
- Maintain consistency

### Campaign Planning
1. Define clear goals
2. Know your target audience
3. Create a content calendar
4. Monitor performance
5. Adjust strategy based on results

## 🐛 Troubleshooting

### Content Generation Not Working
- Check `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is set
- Verify API key is valid
- Check internet connectivity

### Posts Not Publishing
- Verify social media API credentials
- Check scheduler service is running
- Review logs for errors
- Ensure posts are scheduled (not in draft)

### Database Errors
- Check `.sqlite/` directory exists
- Verify write permissions
- Check disk space

## 🚀 Advanced Usage

### Custom Agent Queries

Use natural language with the agent:

```python
result = await agent.process_request(
    "Create a week-long Twitter campaign about AI ethics with 2 posts per day"
)
```

### Batch Operations

Schedule multiple posts at once:

```python
for topic in topics:
    content = await generator.generate_post_content(topic, platform)
    post = ScheduledPost(...)
    scheduler.schedule_post(post)
```

### Analytics Integration

Track and analyze performance:

```python
analytics = await agent.analyze_performance(platform="twitter", days=30)
print(f"Total engagement: {analytics['total_engagement']}")
```

## 📚 Learn More

- **Full Documentation**: See `docs/SOCIAL_MEDIA_AUTOMATION.md`
- **API Reference**: See `docs/API.md`
- **Examples**: Check `examples/` directory
- **Code**: Explore `src/agentic_ai/` for implementation

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional platform integrations
- Advanced analytics features
- UI/UX enhancements
- Testing coverage
- Documentation improvements

## 📄 License

Part of the Agentic AI Pipeline project.

## 🆘 Support

- **Issues**: Create a GitHub issue
- **Questions**: Check the documentation
- **Examples**: See the examples directory

---

**Built with ❤️ using LangChain, FastAPI, and AI**
