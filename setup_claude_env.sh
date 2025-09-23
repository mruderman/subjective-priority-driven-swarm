#!/bin/bash
# Setup script for SWARMS project as claude user

echo "🚀 Setting up SWARMS environment for claude user..."

# Change to project directory
cd /home/claude/SWARMS

# Activate virtual environment if it exists, create if it doesn't
if [ -d "venv" ]; then
    echo "📦 Activating existing virtual environment..."
    source venv/bin/activate
else
    echo "📦 Creating new virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
fi

# Install/update dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Make scripts executable
chmod +x setup_claude_env.sh

echo "✅ Setup complete!"
echo ""
echo "🎯 Quick start commands:"
echo "  cd /home/claude/SWARMS"
echo "  source venv/bin/activate"
echo "  python -m spds.main                    # Run CLI interface"
echo "  cd swarms-web && python app.py         # Run web GUI"
echo "  python test_token_fixes.py             # Test token fixes"
echo ""
echo "📝 Key changes implemented:"
echo "  • Fixed token limit issues using Letta's stateful agent design"
echo "  • Agents now use internal memory instead of conversation history"
echo "  • Automatic error recovery and memory management"
echo "  • All conversation modes updated and working"
echo ""
echo "🔧 Use with Claude Code: claude --dangerously-skip-commands"
