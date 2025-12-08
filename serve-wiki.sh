#!/bin/bash
# Serve the Agentic AI Wiki locally

echo "🤖 Agentic AI Wiki Server"
echo "=========================="
echo ""
echo "Starting local web server..."
echo ""
echo "📍 Wiki will be available at:"
echo "   http://localhost:8080/index.html"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Check if Python 3 is available
if command -v python3 &> /dev/null; then
    python3 -m http.server 8080
elif command -v python &> /dev/null; then
    python -m http.server 8080
else
    echo "❌ Python not found. Please install Python to serve the wiki."
    exit 1
fi
