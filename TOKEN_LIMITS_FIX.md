# Token Limits Fix - Letta Agent Response Issue

## Issue Summary

**Problem**: Agents in the web GUI were not responding to any messages due to a `max_tokens` configuration error:
```
[OpenAI] Bad request (400): Error code: 400 - {'error': {'message': 'max_tokens is too large: 62286. This model supports at most 32768 completion tokens', 'type': 'invalid_request_error', 'param': 'max_tokens', 'code': 'invalid_value'}}
```

**Root Cause**: Letta agents were being created without explicit `max_tokens` parameters, causing the system to use dangerously high default values (62286) that exceed OpenAI model limits (32768 for most models, 4096 for completion tokens).

**Your Code Was Correct**: The application correctly sends only single messages to stateful Letta agents (not entire conversation histories), following proper Letta patterns.

## Solution Implemented

### 1. Added Token Limit Configuration (`config.py`)
```python
# Token Limit Configuration - Safe limits to prevent max_tokens errors
DEFAULT_MAX_TOKENS = 2048  # Safe limit for most models (under 4096 max)
DEFAULT_CONTEXT_WINDOW = 16000  # Conservative context window

# Model-specific token limits (for reference)
MODEL_TOKEN_LIMITS = {
    "openai/gpt-4": {"max_tokens": 4096, "safe_max": 2048},
    "openai/gpt-4o": {"max_tokens": 4096, "safe_max": 2048},
    "openai/gpt-4o-mini": {"max_tokens": 16384, "safe_max": 4096},
    "anthropic/claude-3-5-sonnet-20241022": {"max_tokens": 4000, "safe_max": 2000},
    "together/nvidia/Llama-3.1-Nemotron-70B-Instruct-HF": {"max_tokens": 4096, "safe_max": 2048},
}
```

### 2. Updated Agent Creation (`spds_agent.py`)
Added explicit `max_tokens` parameter to all new agent creation:
```python
# Get safe token limit for the model
safe_max_tokens = config.MODEL_TOKEN_LIMITS.get(
    agent_model, 
    {"safe_max": config.DEFAULT_MAX_TOKENS}
)["safe_max"]

agent_state = client.agents.create(
    name=name,
    system=system_prompt,
    model=agent_model,
    embedding=agent_embedding,
    include_base_tools=True,
    max_tokens=safe_max_tokens,  # Explicit token limit to prevent errors
)
```

### 3. Updated Secretary Agent (`secretary_agent.py`)
Applied the same token limit fix to secretary agent creation.

### 4. Created Fix Script (`fix_token_limits.py`)
- Diagnoses existing agents for token limit issues
- Tests agent responsiveness
- Generates recreation scripts for problematic agents

## Token Limits by Model

| Model | Max Completion Tokens | Safe Limit Used |
|-------|----------------------|-----------------|
| GPT-4 | 4,096 | 2,048 |
| GPT-4o | 4,096 | 2,048 |
| GPT-4o-mini | 16,384 | 4,096 |
| Claude 3.5 Sonnet | 4,000 | 2,000 |
| Llama 3.1 Nemotron | 4,096 | 2,048 |

**Safe limits are set at 50% of maximum** to provide buffer for system prompts and context.

## How to Apply the Fix

### For New Agents (Automatic)
- All new agents created through the application will automatically use safe token limits
- No action required

### For Existing Agents (Manual)
1. **Run the diagnostic script:**
   ```bash
   python fix_token_limits.py
   ```

2. **Test your web GUI** - it should now work for new conversations

3. **If existing agents still fail:**
   - Review the generated `recreate_agents.py` script
   - Customize it with proper persona/expertise for each agent
   - Run it to recreate problematic agents with correct limits

## Testing the Fix

### 1. Web GUI Test
- Open your web application
- Send a message in the chat
- Agents should now respond in both rounds (initial + response)
- No more silent failures

### 2. Command Line Test
```bash
python test_hybrid_fix.py
```

### 3. Check Logs
Look for the absence of `max_tokens is too large` errors in your Letta ADE server logs.

## Prevention Measures

### 1. Code Changes Made
- ✅ Explicit `max_tokens` in all agent creation calls
- ✅ Model-specific token limit lookup
- ✅ Safe defaults for unknown models

### 2. Future Best Practices
- Always specify `max_tokens` when creating Letta agents
- Use conservative values (50% of model maximum)
- Test agents immediately after creation
- Monitor server logs for token-related errors

## Understanding the Error

### Why 62286 Tokens?
This appears to be a Letta default that doesn't account for model-specific limits. It may be calculated as:
- Base context window (e.g., 128k) minus some overhead
- But OpenAI's **completion token limit** is much lower (4096 for most models)

### Completion Tokens vs Context Tokens
- **Context tokens**: Total input + output (can be 128k+)
- **Completion tokens**: Just the response (limited to 4096-16384)
- The error was about **completion tokens** specifically

### Why Agents Weren't Responding
- Letta server was receiving 400 errors from OpenAI
- Errors were not properly propagated to the frontend
- Agents appeared to "ignore" messages when they actually couldn't respond

## Files Modified

1. `spds/config.py` - Added token limit constants
2. `spds/spds_agent.py` - Added explicit max_tokens to agent creation
3. `spds/secretary_agent.py` - Added explicit max_tokens to secretary creation
4. `fix_token_limits.py` - New diagnostic and fix script
5. `TOKEN_LIMITS_FIX.md` - This documentation

## Expected Results

After applying this fix:
- ✅ Web GUI agents respond to messages
- ✅ No more `max_tokens is too large` errors
- ✅ Both initial and response rounds work in hybrid mode
- ✅ New agents automatically use safe limits
- ✅ Existing agents can be diagnosed and fixed

## Troubleshooting

### If agents still don't respond:
1. Check Letta server logs for other errors
2. Verify agent IDs are correct
3. Test with newly created agents first
4. Ensure Letta server restart if configuration changed

### If you see different token errors:
1. Check the specific model being used
2. Update `MODEL_TOKEN_LIMITS` in config.py
3. Recreate agents with updated limits

### If responses are too short:
1. Increase token limits (but stay under model maximums)
2. Consider using higher-capacity models (e.g., GPT-4o-mini)

The fix addresses the immediate issue while providing a robust framework for preventing similar problems in the future.