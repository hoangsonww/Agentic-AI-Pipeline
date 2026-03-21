"""
Agents module for Agentic AI Pipeline

This module contains specialized agents for various automation tasks.
"""

from .social_media_agent import SocialMediaAgent, SocialMediaAgentProfile, create_social_media_agent

__all__ = [
    "SocialMediaAgent",
    "create_social_media_agent",
    "SocialMediaAgentProfile",
]
