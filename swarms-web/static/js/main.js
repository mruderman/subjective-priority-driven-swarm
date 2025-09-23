// SWARMS Web GUI JavaScript

class SwarmsApp {
    constructor() {
        this.socket = null;
        this.sessionId = null;
        this.agents = [];
        this.isConnected = false;
        this.currentPhase = null;

        this.init();
    }

    init() {
        // Check which page we're on
        const currentPage = document.body.getAttribute('data-page');

        // Only initialize socket for non-chat pages (chat.html has its own handler)
        if (currentPage !== 'chat') {
            // Initialize Socket.IO connection
            this.socket = io();
            this.setupSocketEvents();
        }

        // Initialize page-specific functionality
        this.initializePage();
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.isConnected = true;
            this.showToast('Connected to SWARMS server', 'success');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.isConnected = false;
            this.showToast('Disconnected from server', 'warning');
        });

        this.socket.on('joined', (data) => {
            console.log('Joined session:', data.session_id);
        });

        this.socket.on('chat_started', (data) => {
            this.handleChatStarted(data);
        });

        this.socket.on('user_message', (data) => {
            this.addMessage(data.speaker, data.message, 'user', data.timestamp);
        });

        this.socket.on('agent_message', (data) => {
            this.addMessage(data.speaker, data.message, 'agent', data.timestamp, data.phase);
            this.hideThinkingIndicator(data.speaker);
        });

        this.socket.on('system_message', (data) => {
            this.addMessage('System', data.message, 'system');
        });

        this.socket.on('secretary_minutes', (data) => {
            this.updateSecretaryMinutes(data.minutes);
        });

        this.socket.on('secretary_stats', (data) => {
            this.updateSecretaryStats(data.stats);
        });

        this.socket.on('assessing_agents', () => {
            this.showAssessmentIndicator();
        });

        this.socket.on('agent_scores', (data) => {
            this.updateAgentScores(data.scores);
        });

        this.socket.on('phase_change', (data) => {
            this.updatePhase(data.phase);
        });

        this.socket.on('agent_thinking', (data) => {
            this.showThinkingIndicator(data.agent, data.phase, data.progress);
        });

        this.socket.on('export_complete', (data) => {
            this.handleExportComplete(data);
        });

        this.socket.on('secretary_status', (data) => {
            this.handleSecretaryStatus(data);
        });

        this.socket.on('secretary_activity', (data) => {
            this.handleSecretaryActivity(data);
        });
    }

    initializePage() {
        const currentPage = document.body.getAttribute('data-page');

        switch (currentPage) {
            case 'setup':
                this.initializeSetupPage();
                break;
            case 'chat':
                // Skip chat initialization - SimpleChat handles this page
                // this.initializeChatPage();
                break;
        }
    }

    // Setup Page Functions
    initializeSetupPage() {
        this.loadAgents();
        this.setupAgentSelection();
        this.setupModeSelection();
        this.setupSecretaryOptions();
        this.setupFormSubmission();
    }

    async loadAgents() {
        try {
            const response = await fetch('/api/agents');
            const data = await response.json();

            if (data.error) {
                this.showToast('Error loading agents: ' + data.error, 'error');
                return;
            }

            this.agents = data.agents;
            this.renderAgentCards();

        } catch (error) {
            console.error('Error loading agents:', error);
            this.showToast('Failed to load agents from server', 'error');
        }
    }

    renderAgentCards() {
        const container = document.getElementById('agent-cards');
        const loadingDiv = document.getElementById('agents-loading');
        const noAgentsDiv = document.getElementById('no-agents');
        if (!container) return;

        if (loadingDiv) {
            loadingDiv.style.display = 'none';
        }

        if (this.agents.length === 0) {
            container.style.display = 'none';
            if (noAgentsDiv) {
                noAgentsDiv.classList.remove('hidden-by-default');
                noAgentsDiv.style.display = 'block';
            }
            return;
        }

        if (noAgentsDiv) {
            noAgentsDiv.style.display = 'none';
        }

        container.classList.remove('hidden-by-default');
        container.style.display = 'block';
        container.innerHTML = '';

        this.agents.forEach(agent => {
            const card = document.createElement('div');
            card.className = 'col-md-6 col-lg-4 mb-3';
            card.innerHTML = `
                <div class="card agent-card h-100" data-agent-id="${agent.id}">
                    <div class="card-body">
                        <div class="form-check">
                            <input class="form-check-input agent-checkbox" type="checkbox"
                                   value="${agent.id}" id="agent-${agent.id}">
                            <label class="form-check-label" for="agent-${agent.id}">
                                <h6 class="card-title mb-1">${agent.name}</h6>
                            </label>
                        </div>
                        <p class="card-text small text-muted mb-2">
                            <i class="bi bi-cpu"></i> ${agent.model}
                        </p>
                        <p class="card-text small text-muted">
                            <i class="bi bi-calendar"></i> Created: ${agent.created_at}
                        </p>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });

        // Add click handlers
        this.setupAgentCardClicks();
    }

    setupAgentCardClicks() {
        document.querySelectorAll('.agent-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.type !== 'checkbox') {
                    const checkbox = card.querySelector('input[type="checkbox"]');
                    checkbox.checked = !checkbox.checked;
                    this.updateAgentCardState(card, checkbox.checked);
                }
            });
        });

        document.querySelectorAll('.agent-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const card = e.target.closest('.agent-card');
                this.updateAgentCardState(card, e.target.checked);
            });
        });
    }

    updateAgentCardState(card, isSelected) {
        if (isSelected) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
    }

    setupAgentSelection() {
        // Already handled in renderAgentCards
    }

    setupModeSelection() {
        document.querySelectorAll('.mode-card').forEach(card => {
            card.addEventListener('click', () => {
                // Remove selected class from all cards
                document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('selected'));
                // Add selected class to clicked card
                card.classList.add('selected');
                // Update hidden input
                const modeInput = document.getElementById('conversation_mode');
                if (modeInput) {
                    modeInput.value = card.dataset.mode;
                }
            });
        });
    }

    setupSecretaryOptions() {
        const secretaryToggle = document.getElementById('enable_secretary');
        const secretaryOptions = document.getElementById('secretary-options');

        if (secretaryToggle && secretaryOptions) {
            const applyVisibility = (enabled) => {
                if (enabled) {
                    secretaryOptions.classList.remove('hidden-by-default');
                    secretaryOptions.style.display = 'block';
                } else {
                    secretaryOptions.style.display = 'none';
                    secretaryOptions.classList.add('hidden-by-default');
                }
            };

            secretaryToggle.addEventListener('change', () => {
                applyVisibility(secretaryToggle.checked);
            });

            applyVisibility(secretaryToggle.checked);
        }
    }

    setupFormSubmission() {
        const form = document.getElementById('setup-form');
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const selectedAgents = Array.from(document.querySelectorAll('.agent-checkbox:checked'))
                .map(checkbox => checkbox.value);

            if (selectedAgents.length === 0) {
                this.showToast('Please select at least one agent', 'warning');
                return;
            }

            const conversationMode = document.getElementById('conversation_mode').value;
            if (!conversationMode) {
                this.showToast('Please select a conversation mode', 'warning');
                return;
            }

            const topic = document.getElementById('topic').value.trim();
            if (!topic) {
                this.showToast('Please enter a conversation topic', 'warning');
                return;
            }

            const formData = {
                agent_ids: selectedAgents,
                conversation_mode: conversationMode,
                enable_secretary: document.getElementById('enable_secretary').checked,
                secretary_mode: document.getElementById('secretary_mode').value,
                meeting_type: document.getElementById('meeting_type').value,
                topic: topic
            };

            if (window.__PLAYWRIGHT_TEST === '1') {
                formData.playwright_test = true;
            }

            await this.startSession(formData);
        });
    }

    async startSession(formData) {
        try {
            const response = await fetch('/api/start_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (data.error) {
                this.showToast('Error starting session: ' + data.error, 'error');
                return;
            }

            // Store session data
            this.sessionId = data.session_id;
            sessionStorage.setItem('sessionId', this.sessionId);
            sessionStorage.setItem('topic', formData.topic);

            // Redirect to chat
            window.location.href = '/chat';

        } catch (error) {
            console.error('Error starting session:', error);
            this.showToast('Failed to start session', 'error');
        }
    }

    // Chat Page Functions
    initializeChatPage() {
        this.sessionId = sessionStorage.getItem('sessionId');
        const topic = sessionStorage.getItem('topic');

        if (!this.sessionId) {
            window.location.href = '/setup';
            return;
        }

        this.setupChatInterface();
        this.joinSession();

        // Start chat with topic if available
        if (topic) {
            setTimeout(() => {
                this.startChat(topic);
            }, 1000);
        }
    }

    setupChatInterface() {
        const chatInput = document.getElementById('chat-input');
        const sendButton = document.getElementById('send-button');

        if (chatInput && sendButton) {
            // Handle Enter key
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            // Handle send button click
            sendButton.addEventListener('click', () => {
                this.sendMessage();
            });
        }

        // Setup secretary commands
        this.setupSecretaryCommands();
    }

    setupSecretaryCommands() {
        document.querySelectorAll('.secretary-command').forEach(button => {
            button.addEventListener('click', (e) => {
                const command = e.target.dataset.command;
                this.sendSecretaryCommand(command);
            });
        });
    }

    joinSession() {
        if (this.socket && this.sessionId) {
            this.socket.emit('join_session', { session_id: this.sessionId });
        }
    }

    startChat(topic) {
        if (this.socket && this.sessionId) {
            this.socket.emit('start_chat', {
                session_id: this.sessionId,
                topic: topic
            });
        }
    }

    sendMessage() {
        const chatInput = document.getElementById('chat-input');
        if (!chatInput) return;

        const message = chatInput.value.trim();
        if (!message) return;

        // Clear input
        chatInput.value = '';

        // Send via WebSocket
        if (this.socket && this.sessionId) {
            this.socket.emit('user_message', {
                session_id: this.sessionId,
                message: message
            });
        }
    }

    sendSecretaryCommand(command) {
        if (this.socket && this.sessionId) {
            this.socket.emit('user_message', {
                session_id: this.sessionId,
                message: command
            });
        }
    }

    addMessage(speaker, content, type = 'agent', timestamp = null, phase = null) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;

        const messageElement = document.createElement('div');
        messageElement.className = `message ${type}`;

        const timeStr = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();

        let headerHtml = '';
        if (type !== 'system') {
            headerHtml = `
                <div class="message-header">
                    <span class="message-speaker">
                        ${speaker}
                        ${phase ? `<span class="badge bg-secondary ms-1">${phase}</span>` : ''}
                    </span>
                    <span class="message-timestamp">${timeStr}</span>
                </div>
            `;
        }

        messageElement.innerHTML = `
            ${headerHtml}
            <div class="message-content">${this.formatMessageContent(content)}</div>
        `;

        messagesContainer.appendChild(messageElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    formatMessageContent(content) {
        // Basic formatting for links and line breaks
        return content
            .replace(/\n/g, '<br>')
            .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
    }

    showThinkingIndicator(agentName, phase = null, progress = null) {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;

        // Remove existing thinking indicator for this agent
        this.hideThinkingIndicator(agentName);

        const thinkingElement = document.createElement('div');
        thinkingElement.className = 'thinking-indicator';
        thinkingElement.id = `thinking-${agentName}`;

        let progressText = progress ? ` (${progress})` : '';
        let phaseText = phase ? ` - ${phase} thoughts` : '';

        thinkingElement.innerHTML = `
            <i class="bi bi-robot"></i>
            <span>${agentName} is thinking${phaseText}${progressText}</span>
            <div class="thinking-dots">
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
            </div>
        `;

        messagesContainer.appendChild(thinkingElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    hideThinkingIndicator(agentName) {
        const thinkingElement = document.getElementById(`thinking-${agentName}`);
        if (thinkingElement) {
            thinkingElement.remove();
        }
    }

    showAssessmentIndicator() {
        const messagesContainer = document.getElementById('chat-messages');
        if (!messagesContainer) return;

        // Remove existing assessment indicator
        const existingIndicator = document.getElementById('assessment-indicator');
        if (existingIndicator) {
            existingIndicator.remove();
        }

        const assessmentElement = document.createElement('div');
        assessmentElement.className = 'progress-indicator';
        assessmentElement.id = 'assessment-indicator';

        assessmentElement.innerHTML = `
            <div class="spinner"></div>
            <span>Assessing agent motivations...</span>
        `;

        messagesContainer.appendChild(assessmentElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    updateAgentScores(scores) {
        // Remove assessment indicator
        const assessmentIndicator = document.getElementById('assessment-indicator');
        if (assessmentIndicator) {
            assessmentIndicator.remove();
        }

        // Update scores in sidebar if available
        const scoresContainer = document.getElementById('agent-scores');
        if (scoresContainer) {
            scoresContainer.innerHTML = scores.map(score => `
                <div class="agent-score-item">
                    <span class="agent-name">${score.name}</span>
                    <div class="score-badges">
                        <span class="score-badge">M: ${score.motivation_score}</span>
                        <span class="score-badge">P: ${score.priority_score}</span>
                    </div>
                </div>
            `).join('');
        }
    }

    updatePhase(phase) {
        this.currentPhase = phase;

        const phaseIndicator = document.getElementById('phase-indicator');
        if (phaseIndicator) {
            const phaseNames = {
                'initial_responses': 'Initial Responses',
                'response_round': 'Response Round',
                'all_speak': 'All Speak Mode',
                'sequential': 'Sequential Mode',
                'pure_priority': 'Pure Priority Mode'
            };

            phaseIndicator.textContent = phaseNames[phase] || phase;
        }
    }

    handleChatStarted(data) {
        this.showToast(`Chat started: ${data.topic}`, 'success');

        // Update UI with session info
        const topicElement = document.getElementById('current-topic');
        if (topicElement) {
            topicElement.textContent = data.topic;
        }

        const modeElement = document.getElementById('current-mode');
        if (modeElement) {
            modeElement.textContent = data.mode.toUpperCase();
        }

        // Show agent list
        const agentsList = document.getElementById('agents-list');
        if (agentsList && data.agents) {
            agentsList.innerHTML = data.agents.map(agent => `
                <div class="d-flex justify-content-between align-items-center py-1">
                    <span>${agent.name}</span>
                    <span class="badge bg-primary">Active</span>
                </div>
            `).join('');
        }
    }

    updateSecretaryMinutes(minutes) {
        const minutesContainer = document.getElementById('secretary-minutes');
        if (minutesContainer) {
            minutesContainer.innerHTML = `<pre class="text-wrap">${minutes}</pre>`;
        }
    }

    updateSecretaryStats(stats) {
        const statsContainer = document.getElementById('secretary-stats');
        if (statsContainer) {
            statsContainer.innerHTML = Object.entries(stats)
                .map(([key, value]) => `
                    <div class="d-flex justify-content-between">
                        <span>${key}:</span>
                        <strong>${value}</strong>
                    </div>
                `).join('');
        }
    }

    handleExportComplete(data) {
        if (data.files) {
            this.showToast(`Export complete: ${data.count} files generated`, 'success');
        } else if (data.file) {
            this.showToast(`Export complete: ${data.format}`, 'success');
        }
    }

    handleSecretaryStatus(data) {
        console.log('Secretary status update:', data);

        const secretaryContent = document.getElementById('secretary-content');
        if (secretaryContent) {
            secretaryContent.innerHTML = `
                <div class="text-center">
                    <div class="badge bg-success mb-2">${data.status.toUpperCase()}</div>
                    <h6 class="text-success">
                        <i class="bi bi-person-check"></i> ${data.agent_name}
                    </h6>
                    <p class="small text-muted mb-2">Mode: ${data.mode}</p>
                    <p class="small">${data.message}</p>
                </div>
            `;
        }

        this.showToast(data.message, 'success');
    }

    handleSecretaryActivity(data) {
        console.log('Secretary activity:', data);

        const secretaryContent = document.getElementById('secretary-content');
        if (secretaryContent) {
            // Show activity indicator
            const activityClass = data.activity === 'generating' ? 'text-warning' :
                                 data.activity === 'completed' ? 'text-success' : 'text-info';

            secretaryContent.innerHTML = `
                <div class="text-center ${activityClass}">
                    <div class="mb-2">
                        ${data.activity === 'generating' ?
                            '<div class="spinner-border spinner-border-sm" role="status"></div>' :
                            '<i class="bi bi-pencil-square"></i>'
                        }
                    </div>
                    <p class="small mb-0">${data.message}</p>
                </div>
            `;

            // Auto-clear completed messages after 3 seconds
            if (data.activity === 'completed') {
                setTimeout(() => {
                    if (secretaryContent.innerHTML.includes(data.message)) {
                        secretaryContent.innerHTML = `
                            <div class="text-center text-success">
                                <i class="bi bi-check-circle"></i>
                                <p class="small mb-0 mt-2">Ready for more activity...</p>
                            </div>
                        `;
                    }
                }, 3000);
            }
        }
    }

    // Utility Functions
    showToast(message, type = 'info') {
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container';
            document.body.appendChild(toastContainer);
        }

        // Create toast
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${this.getBootstrapColorClass(type)} border-0`;
        toast.setAttribute('role', 'alert');

        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto"
                        data-bs-dismiss="toast"></button>
            </div>
        `;

        toastContainer.appendChild(toast);

        // Initialize and show toast
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();

        // Remove toast element after it's hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    getBootstrapColorClass(type) {
        const colorMap = {
            'success': 'success',
            'error': 'danger',
            'warning': 'warning',
            'info': 'primary'
        };
        return colorMap[type] || 'primary';
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.swarmsApp = new SwarmsApp();
});
