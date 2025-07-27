# SWARMS Web GUI

A modern web interface for the Subjective Priority-Driven Swarm (SPDS) framework, providing an intuitive way to configure and run multi-agent conversations through your browser.

## Features

- **🤖 Interactive Agent Selection**: Visual interface to select agents from your Letta server
- **🎭 Conversation Mode Configuration**: Choose from 4 different conversation modes with descriptions
- **📝 Secretary Integration**: Real-time meeting documentation with live commands
- **💬 Real-Time Chat**: WebSocket-powered live conversations with agent responses
- **📊 Live Statistics**: Monitor agent motivation scores and participation metrics
- **💾 Export Functionality**: Download meeting minutes, transcripts, and summaries
- **📱 Responsive Design**: Bootstrap 5 interface that works on desktop and mobile

## Quick Start

### Prerequisites

1. **Letta Server**: You need a running Letta server (self-hosted or Letta Cloud)
2. **Python 3.8+**: Required for the Flask application
3. **Agents**: At least one agent created in your Letta server

### Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment** (if not already done):
   ```bash
   # For self-hosted Letta
   export LETTA_BASE_URL="http://localhost:8283"
   export LETTA_PASSWORD="your-server-password"
   export LETTA_ENVIRONMENT="SELF_HOSTED"
   
   # For Letta Cloud
   export LETTA_BASE_URL="https://api.letta.com"
   export LETTA_API_KEY="your-api-key"
   export LETTA_ENVIRONMENT="LETTA_CLOUD"
   ```

3. **Start the Web Application**:
   ```bash
   python run.py
   ```
   
   Or manually:
   ```bash
   python app.py
   ```

4. **Open Your Browser**:
   Navigate to http://localhost:5002

## Usage Guide

### 1. Setup Page

**Agent Selection**:
- Browse available agents from your Letta server
- Select multiple agents using checkboxes
- View agent details (model, creation date)

**Conversation Mode**:
- **Hybrid** (Recommended): Two-phase conversations with independent thoughts then response rounds
- **All-Speak**: All motivated agents respond in priority order
- **Sequential**: Turn-taking with fairness rotation
- **Pure Priority**: Highest motivated agent always speaks

**Secretary Configuration**:
- Enable/disable meeting documentation
- Choose mode: Adaptive, Formal, or Casual
- Select meeting type for appropriate documentation style

### 2. Chat Interface

**Main Chat Area**:
- Real-time conversation display
- Agent thinking indicators
- Phase transitions (for Hybrid mode)
- Message timestamps and agent identification

**Sidebar Panels**:
- **Participants**: Active agents and their status
- **Secretary**: Live meeting documentation
- **Export Options**: Download various formats

**Secretary Commands**:
- `/minutes` - Generate current meeting minutes
- `/export [format]` - Export meeting data
- `/formal` - Switch to formal documentation mode
- `/casual` - Switch to casual documentation mode
- `/action-item [description]` - Add action item
- `/stats` - Show conversation statistics

### 3. Export Options

Available export formats:
- **Board Minutes**: Formal meeting minutes (Cyan Society format)
- **Casual Notes**: Friendly discussion summary
- **Raw Transcript**: Complete conversation log
- **Action Items**: Formatted task checklist
- **Executive Summary**: Brief meeting overview
- **Complete Package**: All formats bundled together

## Architecture

### Technology Stack

- **Backend**: Flask + letta-flask integration
- **Real-time**: Flask-SocketIO for WebSocket communication
- **Frontend**: Bootstrap 5 + vanilla JavaScript + Alpine.js
- **Templates**: Jinja2 templating engine

### Project Structure

```
swarms-web/
├── app.py                 # Main Flask application
├── run.py                 # Quick start script
├── requirements.txt       # Python dependencies
├── templates/
│   ├── base.html         # Base template with Bootstrap 5
│   ├── index.html        # Landing page
│   ├── setup.html        # Agent selection and configuration
│   ├── chat.html         # Main chat interface
│   └── components/       # Reusable UI components
├── static/
│   ├── css/
│   │   └── main.css      # Custom styles
│   ├── js/
│   │   └── main.js       # WebSocket handling and UI logic
│   └── assets/           # Images and icons
└── routes/               # Additional route handlers (future expansion)
```

### Key Components

**WebSwarmManager**: Web-adapted version of SwarmManager with WebSocket support
- Inherits from base SwarmManager
- Adds real-time event emission
- Handles secretary command processing
- Manages export operations

**SwarmsApp (JavaScript)**: Frontend application class
- WebSocket communication
- Real-time UI updates
- Agent selection logic
- Export handling

## Configuration

### Environment Variables

```bash
# Letta Configuration
LETTA_BASE_URL="http://localhost:8283"          # Letta server URL
LETTA_API_KEY="your-api-key"                    # For Letta Cloud
LETTA_PASSWORD="your-server-password"           # For self-hosted with auth
LETTA_ENVIRONMENT="SELF_HOSTED"                 # SELF_HOSTED or LETTA_CLOUD

# Export Configuration (optional)
EXPORT_DIRECTORY="./exports"                    # Where to save exported files
ORGANIZATION_NAME="CYAN SOCIETY"                # For formal meeting minutes
```

### Port Configuration

Default port is 5002. To change:

```python
# In app.py or run.py
socketio.run(app, host='0.0.0.0', port=YOUR_PORT)
```

## Development

### Adding New Features

1. **Backend Routes**: Add new Flask routes in `app.py` or create separate route files
2. **WebSocket Events**: Add new socket events in the `socketio` handlers
3. **Frontend Components**: Extend the `SwarmsApp` class in `main.js`
4. **Templates**: Create new Jinja2 templates or extend existing ones

### Debugging

Enable debug mode:
```bash
export FLASK_DEBUG=1
python app.py
```

View WebSocket logs in browser console and server terminal.

## Troubleshooting

### Common Issues

**"No agents found"**:
- Verify Letta server is running
- Check authentication credentials
- Ensure agents exist in your Letta server

**WebSocket connection failed**:
- Check firewall settings
- Verify port 5002 is available
- Try disabling browser extensions

**Import errors**:
- Install missing dependencies: `pip install -r requirements.txt`
- Ensure parent SPDS modules are accessible

**Secretary not working**:
- Verify secretary is enabled in setup
- Check Letta server has necessary permissions
- Review server logs for errors

### Getting Help

1. Check the main project documentation in `../README.md`
2. Review Letta documentation at https://docs.letta.com/
3. Check server logs for detailed error messages
4. Verify your Letta server configuration

## Security Notes

- The web interface runs on localhost by default for security
- For production deployment, consider:
  - Using a reverse proxy (nginx, Apache)
  - Enabling HTTPS
  - Implementing proper authentication
  - Restricting network access

## Future Enhancements

Planned features:
- User authentication and sessions
- Multi-tenant support
- Enhanced mobile interface
- Real-time collaboration features
- Advanced export customization
- Integration with external calendar systems

## License

This web interface is part of the SWARMS project and follows the same license terms.