# swarms-web/app.py

import os
import sys
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
import uuid
import json
from datetime import datetime

# Add parent directory to path to import existing SPDS modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from letta_flask import LettaFlask, LettaFlaskConfig
from letta_client import Letta
from spds import config
from spds.swarm_manager import SwarmManager
from spds.secretary_agent import SecretaryAgent
from spds.export_manager import ExportManager

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Initialize SocketIO for real-time communication
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Initialize letta-flask
letta_flask = LettaFlask(config=LettaFlaskConfig(
    base_url=config.LETTA_BASE_URL,
    api_key=config.LETTA_API_KEY if config.LETTA_API_KEY else None
))
letta_flask.init_app(app)

# Global storage for active swarm sessions
active_sessions = {}

class WebSwarmManager:
    """Web-adapted version of SwarmManager with WebSocket support."""
    
    def __init__(self, session_id, socketio_instance, **kwargs):
        self.session_id = session_id
        self.socketio = socketio_instance
        
        # Initialize Letta client
        if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and config.LETTA_SERVER_PASSWORD:
            self.client = Letta(token=config.LETTA_SERVER_PASSWORD, base_url=config.LETTA_BASE_URL)
        elif config.LETTA_API_KEY:
            self.client = Letta(token=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)
        else:
            self.client = Letta(base_url=config.LETTA_BASE_URL)
        
        # Initialize the base SwarmManager
        self.swarm = SwarmManager(client=self.client, **kwargs)
        self.export_manager = ExportManager()
        self.current_topic = None
        
    def emit_message(self, event, data):
        """Emit WebSocket message to the session room."""
        self.socketio.emit(event, data, room=self.session_id)
    
    def start_web_chat(self, topic):
        """Start chat with WebSocket notifications."""
        self.current_topic = topic
        self.emit_message('chat_started', {
            'topic': topic,
            'mode': self.swarm.conversation_mode,
            'agents': [{'name': agent.name, 'id': agent.agent.id} for agent in self.swarm.agents],
            'secretary_enabled': self.swarm.enable_secretary
        })
        
        # Start meeting if secretary is enabled
        if self.swarm.secretary:
            participant_names = [agent.name for agent in self.swarm.agents]
            self.swarm.secretary.start_meeting(
                topic=topic,
                participants=participant_names,
                meeting_type=self.swarm.meeting_type
            )
            self.swarm.secretary.meeting_metadata["conversation_mode"] = self.swarm.conversation_mode
            
            # Notify about secretary initialization
            self.emit_message('secretary_status', {
                'status': 'active',
                'mode': self.swarm.secretary.mode,
                'agent_name': self.swarm.secretary.agent.name if self.swarm.secretary.agent else 'Secretary',
                'message': f"📝 {self.swarm.secretary.agent.name if self.swarm.secretary.agent else 'Secretary'} is now taking notes in {self.swarm.secretary.mode} mode"
            })
    
    def process_user_message(self, message):
        """Process user message and trigger agent responses."""
        # Add to conversation history
        self.swarm.conversation_history += f"You: {message}\n"
        
        # Update all agent memories with the new user message
        self.swarm._update_agent_memories(message, "You")
        
        # Let secretary observe
        if self.swarm.secretary:
            self.swarm.secretary.observe_message("You", message)
            self.emit_message('secretary_activity', {
                'activity': 'observing',
                'message': f'📝 Recording your message...'
            })
        
        # Emit user message
        self.emit_message('user_message', {
            'speaker': 'You',
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Check for secretary commands
        if message.startswith('/'):
            self._handle_secretary_command(message)
            return
        
        # Process agent turn (follow CLI pattern)
        self._web_agent_turn(self.current_topic)
    
    def _handle_secretary_command(self, command):
        """Handle secretary commands with WebSocket responses."""
        command_parts = command[1:].split(' ', 1)
        cmd = command_parts[0].lower()
        args = command_parts[1] if len(command_parts) > 1 else ""
        
        if not self.swarm.secretary:
            self.emit_message('system_message', {
                'message': 'Secretary is not enabled for this session.'
            })
            return
        
        if cmd == "minutes":
            self.emit_message('secretary_activity', {
                'activity': 'generating',
                'message': '📝 Generating meeting minutes...'
            })
            minutes = self.swarm.secretary.generate_minutes()
            self.emit_message('secretary_minutes', {'minutes': minutes})
            self.emit_message('secretary_activity', {
                'activity': 'completed',
                'message': '✅ Meeting minutes generated!'
            })
        
        elif cmd == "export":
            self._handle_export_command(args)
        
        elif cmd in ["formal", "casual"]:
            self.swarm.secretary.set_mode(cmd)
            self.emit_message('system_message', {
                'message': f'Secretary mode changed to {cmd}'
            })
        
        elif cmd == "action-item":
            if args:
                self.swarm.secretary.add_action_item(args)
                self.emit_message('system_message', {
                    'message': f'Action item added: {args}'
                })
            else:
                self.emit_message('system_message', {
                    'message': 'Usage: /action-item <description>'
                })
        
        elif cmd == "stats":
            stats = self.swarm.secretary.get_conversation_stats()
            self.emit_message('secretary_stats', {'stats': stats})
    
    def _handle_export_command(self, args):
        """Handle export commands."""
        if not self.swarm.secretary:
            return
        
        meeting_data = {
            "metadata": self.swarm.secretary.meeting_metadata,
            "conversation_log": self.swarm.secretary.conversation_log,
            "action_items": self.swarm.secretary.action_items,
            "decisions": self.swarm.secretary.decisions,
            "stats": self.swarm.secretary.get_conversation_stats()
        }
        
        format_type = args.strip().lower() if args else "minutes"
        
        try:
            if format_type in ["minutes", "formal"]:
                file_path = self.export_manager.export_meeting_minutes(meeting_data, "formal")
            elif format_type == "casual":
                file_path = self.export_manager.export_meeting_minutes(meeting_data, "casual")
            elif format_type == "all":
                files = self.export_manager.export_complete_package(meeting_data, self.swarm.secretary.mode)
                self.emit_message('export_complete', {
                    'files': files,
                    'count': len(files)
                })
                return
            else:
                self.emit_message('system_message', {
                    'message': f'Unknown export format: {format_type}'
                })
                return
            
            self.emit_message('export_complete', {
                'file': file_path,
                'format': format_type
            })
            
        except Exception as e:
            self.emit_message('system_message', {
                'message': f'Export failed: {str(e)}'
            })
    
    def _web_agent_turn(self, topic: str):
        """Process agent turn with WebSocket notifications (follows CLI pattern)."""
        # Assess motivations
        self.emit_message('assessing_agents', {})
        
        for agent in self.swarm.agents:
            agent.assess_motivation_and_priority(topic)
        
        motivated_agents = sorted(
            [agent for agent in self.swarm.agents if agent.priority_score > 0],
            key=lambda x: x.priority_score,
            reverse=True,
        )
        
        if not motivated_agents:
            self.emit_message('system_message', {
                'message': 'No agent is motivated to speak at this time.'
            })
            return
        
        # Emit motivation scores
        agent_scores = [
            {
                'name': agent.name,
                'motivation_score': agent.motivation_score,
                'priority_score': round(agent.priority_score, 2)
            }
            for agent in self.swarm.agents
        ]
        self.emit_message('agent_scores', {'scores': agent_scores})
        
        # Warm up motivated agents before they speak (follow CLI pattern)
        for agent in motivated_agents:
            self.swarm._warm_up_agent(agent, topic)
        
        # Process based on conversation mode
        if self.swarm.conversation_mode == "hybrid":
            self._web_hybrid_turn(motivated_agents)
        elif self.swarm.conversation_mode == "all_speak":
            self._web_all_speak_turn(motivated_agents)
        elif self.swarm.conversation_mode == "sequential":
            self._web_sequential_turn(motivated_agents)
        else:  # pure_priority
            self._web_pure_priority_turn(motivated_agents)
    
    def _web_hybrid_turn(self, motivated_agents):
        """Hybrid mode with WebSocket updates."""
        self.emit_message('phase_change', {'phase': 'initial_responses'})
        
        original_history = self.swarm.conversation_history
        initial_responses = []
        
        # Phase 1: Independent responses
        for i, agent in enumerate(motivated_agents):
            self.emit_message('agent_thinking', {
                'agent': agent.name,
                'phase': 'initial',
                'progress': f"{i+1}/{len(motivated_agents)}"
            })
            
            try:
                print(f"[DEBUG] Agent {agent.name} speaking with history length: {len(original_history)}")
                response = agent.speak(mode="initial", topic=self.current_topic)
                print(f"[DEBUG] Agent {agent.name} response type: {type(response)}")
                
                message_text = self.swarm._extract_agent_response(response)
                print(f"[DEBUG] Agent {agent.name} extracted message: {message_text[:100]}...")
                
                initial_responses.append((agent, message_text))
                
                self.emit_message('agent_message', {
                    'speaker': agent.name,
                    'message': message_text,
                    'timestamp': datetime.now().isoformat(),
                    'phase': 'initial'
                })
                
                # Notify secretary
                if self.swarm.secretary:
                    self.swarm.secretary.observe_message(agent.name, message_text)
                    self.emit_message('secretary_activity', {
                        'activity': 'recording',
                        'message': f'📝 Recording {agent.name}\'s initial thoughts...'
                    })
                    
            except Exception as e:
                print(f"[ERROR] Agent {agent.name} failed in initial phase: {e}")
                print(f"[ERROR] Exception type: {type(e)}")
                import traceback
                traceback.print_exc()
                
                fallback = "I have some thoughts but I'm having trouble expressing them."
                initial_responses.append((agent, fallback))
                
                self.emit_message('agent_message', {
                    'speaker': agent.name,
                    'message': fallback,
                    'timestamp': datetime.now().isoformat(),
                    'phase': 'initial',
                    'error': True
                })
        
        # Phase 2: Response round
        self.emit_message('phase_change', {'phase': 'response_round'})
        
        history_with_initials = original_history
        for agent, response in initial_responses:
            history_with_initials += f"{agent.name}: {response}\n"
        
        response_prompt = "\n\nNow that you've heard everyone's initial thoughts, please respond to what others have said..."
        
        for i, agent in enumerate(motivated_agents):
            self.emit_message('agent_thinking', {
                'agent': agent.name,
                'phase': 'response',
                'progress': f"{i+1}/{len(motivated_agents)}"
            })
            
            try:
                response = agent.speak(mode="response", topic=self.current_topic)
                message_text = self.swarm._extract_agent_response(response)
                
                self.emit_message('agent_message', {
                    'speaker': agent.name,
                    'message': message_text,
                    'timestamp': datetime.now().isoformat(),
                    'phase': 'response'
                })
                
                # Add to conversation history
                self.swarm.conversation_history += f"{agent.name}: {message_text}\n"
                
                # Update all agent memories with this response
                self.swarm._update_agent_memories(message_text, agent.name)
                
                # Notify secretary
                if self.swarm.secretary:
                    self.swarm.secretary.observe_message(agent.name, message_text)
                    self.emit_message('secretary_activity', {
                        'activity': 'recording',
                        'message': f'📝 Recording {agent.name}\'s response...'
                    })
                    
            except Exception as e:
                fallback = "I find the different perspectives here really interesting."
                
                self.emit_message('agent_message', {
                    'speaker': agent.name,
                    'message': fallback,
                    'timestamp': datetime.now().isoformat(),
                    'phase': 'response',
                    'error': True
                })
                
                self.swarm.conversation_history += f"{agent.name}: {fallback}\n"
    
    def _web_all_speak_turn(self, motivated_agents):
        """All-speak mode with WebSocket updates."""
        self.emit_message('phase_change', {'phase': 'all_speak'})
        
        for i, agent in enumerate(motivated_agents):
            self.emit_message('agent_thinking', {
                'agent': agent.name,
                'progress': f"{i+1}/{len(motivated_agents)}"
            })
            
            try:
                response = agent.speak(mode="initial", topic=self.current_topic)
                message_text = self.swarm._extract_agent_response(response)
                
                self.emit_message('agent_message', {
                    'speaker': agent.name,
                    'message': message_text,
                    'timestamp': datetime.now().isoformat()
                })
                
                self.swarm.conversation_history += f"{agent.name}: {message_text}\n"
                
                # Update all agent memories with this response
                self.swarm._update_agent_memories(message_text, agent.name)
                
                if self.swarm.secretary:
                    self.swarm.secretary.observe_message(agent.name, message_text)
                    
            except Exception as e:
                fallback = "I have some thoughts but I'm having trouble expressing them clearly."
                
                self.emit_message('agent_message', {
                    'speaker': agent.name,
                    'message': fallback,
                    'timestamp': datetime.now().isoformat(),
                    'error': True
                })
                
                self.swarm.conversation_history += f"{agent.name}: {fallback}\n"
    
    def _web_sequential_turn(self, motivated_agents):
        """Sequential mode with WebSocket updates."""
        # Implement fairness rotation
        if len(motivated_agents) > 1 and hasattr(self.swarm, 'last_speaker'):
            if self.swarm.last_speaker == motivated_agents[0].name:
                speaker = motivated_agents[1]
            else:
                speaker = motivated_agents[0]
        else:
            speaker = motivated_agents[0]
        
        self.swarm.last_speaker = speaker.name
        
        self.emit_message('agent_thinking', {'agent': speaker.name})
        
        try:
            response = speaker.speak(mode="initial", topic=self.current_topic)
            message_text = self.swarm._extract_agent_response(response)
            
            self.emit_message('agent_message', {
                'speaker': speaker.name,
                'message': message_text,
                'timestamp': datetime.now().isoformat()
            })
            
            self.swarm.conversation_history += f"{speaker.name}: {message_text}\n"
            
            # Update all agent memories with this response
            self.swarm._update_agent_memories(message_text, speaker.name)
            
            if self.swarm.secretary:
                self.swarm.secretary.observe_message(speaker.name, message_text)
                
        except Exception as e:
            fallback = "I have some thoughts but I'm having trouble phrasing them."
            
            self.emit_message('agent_message', {
                'speaker': speaker.name,
                'message': fallback,
                'timestamp': datetime.now().isoformat(),
                'error': True
            })
            
            self.swarm.conversation_history += f"{speaker.name}: {fallback}\n"
    
    def _web_pure_priority_turn(self, motivated_agents):
        """Pure priority mode with WebSocket updates."""
        speaker = motivated_agents[0]
        
        self.emit_message('agent_thinking', {'agent': speaker.name})
        
        try:
            response = speaker.speak(mode="initial", topic=self.current_topic)
            message_text = self.swarm._extract_agent_response(response)
            
            self.emit_message('agent_message', {
                'speaker': speaker.name,
                'message': message_text,
                'timestamp': datetime.now().isoformat()
            })
            
            self.swarm.conversation_history += f"{speaker.name}: {message_text}\n"
            
            # Update all agent memories with this response
            self.swarm._update_agent_memories(message_text, speaker.name)
            
            if self.swarm.secretary:
                self.swarm.secretary.observe_message(speaker.name, message_text)
                
        except Exception as e:
            fallback = "I have thoughts on this topic but I'm having difficulty expressing them."
            
            self.emit_message('agent_message', {
                'speaker': speaker.name,
                'message': fallback,
                'timestamp': datetime.now().isoformat(),
                'error': True
            })
            
            self.swarm.conversation_history += f"{speaker.name}: {fallback}\n"


# Routes
@app.route('/')
def index():
    """Landing page."""
    return render_template('index.html')

@app.route('/setup')
def setup():
    """Agent selection and configuration page."""
    return render_template('setup.html')

@app.route('/chat')
def chat():
    """Main chat interface."""
    if 'session_id' not in session:
        return redirect(url_for('setup'))
    return render_template('chat.html')

@app.route('/api/agents')
def get_agents():
    """API endpoint to get available agents."""
    try:
        # Initialize Letta client
        if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and config.LETTA_SERVER_PASSWORD:
            client = Letta(token=config.LETTA_SERVER_PASSWORD, base_url=config.LETTA_BASE_URL)
        elif config.LETTA_API_KEY:
            client = Letta(token=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)
        else:
            client = Letta(base_url=config.LETTA_BASE_URL)
        
        agents = client.agents.list()
        agent_list = []
        
        for agent in agents:
            agent_list.append({
                'id': agent.id,
                'name': agent.name,
                'model': getattr(agent, 'model', 'Unknown'),
                'created_at': str(agent.created_at)[:10] if hasattr(agent, 'created_at') else 'Unknown'
            })
        
        return jsonify({'agents': agent_list})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/start_session', methods=['POST'])
def start_session():
    """Start a new swarm session."""
    try:
        data = request.get_json()
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id
        
        # Create WebSwarmManager
        web_swarm = WebSwarmManager(
            session_id=session_id,
            socketio_instance=socketio,
            agent_ids=data.get('agent_ids'),
            conversation_mode=data.get('conversation_mode', 'hybrid'),
            enable_secretary=data.get('enable_secretary', False),
            secretary_mode=data.get('secretary_mode', 'adaptive'),
            meeting_type=data.get('meeting_type', 'discussion')
        )
        
        active_sessions[session_id] = web_swarm
        
        return jsonify({
            'session_id': session_id,
            'status': 'success'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/exports/<path:filename>')
def download_export(filename):
    """Download exported files."""
    export_dir = os.path.join(os.path.dirname(__file__), '..', 'exports')
    return send_from_directory(export_dir, filename, as_attachment=True)

# WebSocket events
@socketio.on('connect')
def on_connect():
    """Handle client connection."""
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    """Handle client disconnection."""
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_session')
def on_join_session(data):
    """Join a swarm session room."""
    session_id = data.get('session_id')
    if session_id:
        join_room(session_id)
        emit('joined', {'session_id': session_id})

@socketio.on('start_chat')
def on_start_chat(data):
    """Start chat with topic."""
    session_id = data.get('session_id')
    topic = data.get('topic')
    
    if session_id in active_sessions:
        web_swarm = active_sessions[session_id]
        web_swarm.start_web_chat(topic)

@socketio.on('user_message')
def on_user_message(data):
    """Handle user message."""
    session_id = data.get('session_id')
    message = data.get('message')
    
    if session_id in active_sessions:
        web_swarm = active_sessions[session_id]
        web_swarm.process_user_message(message)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5002, allow_unsafe_werkzeug=True)
