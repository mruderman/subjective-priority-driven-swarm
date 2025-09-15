# Extended Model Token Limits Configuration

## Complete Max Tokens Configuration for Server-Side Settings

Based on comprehensive research of 2025 model specifications, here are the **completion/output token limits** (not context window) for various model families:

### 🤖 **ANTHROPIC MODELS (Claude)**

```python
# Claude 4 (2025 - Current)
"anthropic/claude-4-sonnet": {"max_tokens": 64000, "safe_max": 32000},
"anthropic/claude-4-opus": {"max_tokens": 32000, "safe_max": 16000},

# Claude 3.5 (Legacy)
"anthropic/claude-3-5-sonnet-20241022": {"max_tokens": 8192, "safe_max": 4000},
"anthropic/claude-3-5-haiku": {"max_tokens": 8192, "safe_max": 4000},
```

### 🔍 **GOOGLE MODELS**

```python
# Gemini 2.5 Pro (2025)
"google/gemini-2.5-pro": {"max_tokens": 64000, "safe_max": 32000},

# Gemini 2.0 Models
"google/gemini-2.0-flash": {"max_tokens": 8192, "safe_max": 4000},

# Gemma 3 (Open Source - for Ollama/local)
"google/gemma-3-27b": {"max_tokens": 8192, "safe_max": 4000},  # Configurable in Ollama
"google/gemma-3-9b": {"max_tokens": 8192, "safe_max": 4000},
"google/gemma-3-2b": {"max_tokens": 8192, "safe_max": 4000},
```

### 🌙 **MOONSHOT AI**

```python
# Kimi K2 (2025)
"moonshot/kimi-k2": {"max_tokens": 16000, "safe_max": 8000},  # Based on benchmark limits
"moonshot/kimi-k2-instruct": {"max_tokens": 16000, "safe_max": 8000},
```

### 🦙 **LOCAL OLLAMA MODELS**

```python
# Meta Llama Models
"ollama/llama3.3": {"max_tokens": 16384, "safe_max": 8000},
"ollama/llama3.1:70b": {"max_tokens": 16384, "safe_max": 8000},
"ollama/llama3.1:8b": {"max_tokens": 16384, "safe_max": 8000},
"ollama/llama3.1:405b": {"max_tokens": 16384, "safe_max": 8000},

# CodeLlama (Meta)
"ollama/codellama:34b": {"max_tokens": 16384, "safe_max": 8000},
"ollama/codellama:13b": {"max_tokens": 16384, "safe_max": 8000},
"ollama/codellama:7b": {"max_tokens": 16384, "safe_max": 8000},

# Mistral Models
"ollama/mistral:7b": {"max_tokens": 8192, "safe_max": 4000},
"ollama/mistral-large": {"max_tokens": 8192, "safe_max": 4000},
"ollama/mixtral:8x7b": {"max_tokens": 8192, "safe_max": 4000},

# DeepSeek Models (Popular in Ollama)
"ollama/deepseek-r1": {"max_tokens": 8192, "safe_max": 4000},
"ollama/deepseek-coder": {"max_tokens": 8192, "safe_max": 4000},

# Qwen Models
"ollama/qwen2.5:72b": {"max_tokens": 8192, "safe_max": 4000},
"ollama/qwen2.5:32b": {"max_tokens": 8192, "safe_max": 4000},
"ollama/qwen2.5:14b": {"max_tokens": 8192, "safe_max": 4000},
```

## 🔧 **Complete Config.py Addition**

Add this to your `spds/config.py` file:

```python
# Extended Model Token Limits - 2025 Edition
EXTENDED_MODEL_TOKEN_LIMITS = {
    # Anthropic Claude 4 (2025)
    "anthropic/claude-4-sonnet": {"max_tokens": 64000, "safe_max": 32000},
    "anthropic/claude-4-opus": {"max_tokens": 32000, "safe_max": 16000},
    
    # Anthropic Claude 3.5 (Legacy)
    "anthropic/claude-3-5-sonnet-20241022": {"max_tokens": 8192, "safe_max": 4000},
    "anthropic/claude-3-5-haiku": {"max_tokens": 8192, "safe_max": 4000},
    
    # Google Gemini 2.5
    "google/gemini-2.5-pro": {"max_tokens": 64000, "safe_max": 32000},
    "google/gemini-2.0-flash": {"max_tokens": 8192, "safe_max": 4000},
    
    # Google Gemma 3 (Open Source)
    "google/gemma-3-27b": {"max_tokens": 8192, "safe_max": 4000},
    "google/gemma-3-9b": {"max_tokens": 8192, "safe_max": 4000},
    "google/gemma-3-2b": {"max_tokens": 8192, "safe_max": 4000},
    
    # Moonshot AI Kimi K2
    "moonshot/kimi-k2": {"max_tokens": 16000, "safe_max": 8000},
    "moonshot/kimi-k2-instruct": {"max_tokens": 16000, "safe_max": 8000},
    
    # Local Ollama Models - Meta Llama
    "ollama/llama3.3": {"max_tokens": 16384, "safe_max": 8000},
    "ollama/llama3.1:70b": {"max_tokens": 16384, "safe_max": 8000},
    "ollama/llama3.1:8b": {"max_tokens": 16384, "safe_max": 8000},
    "ollama/llama3.1:405b": {"max_tokens": 16384, "safe_max": 8000},
    
    # Local Ollama Models - CodeLlama
    "ollama/codellama:34b": {"max_tokens": 16384, "safe_max": 8000},
    "ollama/codellama:13b": {"max_tokens": 16384, "safe_max": 8000},
    "ollama/codellama:7b": {"max_tokens": 16384, "safe_max": 8000},
    
    # Local Ollama Models - Mistral
    "ollama/mistral:7b": {"max_tokens": 8192, "safe_max": 4000},
    "ollama/mistral-large": {"max_tokens": 8192, "safe_max": 4000},
    "ollama/mixtral:8x7b": {"max_tokens": 8192, "safe_max": 4000},
    
    # Local Ollama Models - Other Popular Models
    "ollama/deepseek-r1": {"max_tokens": 8192, "safe_max": 4000},
    "ollama/deepseek-coder": {"max_tokens": 8192, "safe_max": 4000},
    "ollama/qwen2.5:72b": {"max_tokens": 8192, "safe_max": 4000},
    "ollama/qwen2.5:32b": {"max_tokens": 8192, "safe_max": 4000},
    "ollama/qwen2.5:14b": {"max_tokens": 8192, "safe_max": 4000},
}

# Merge with existing token limits
MODEL_TOKEN_LIMITS.update(EXTENDED_MODEL_TOKEN_LIMITS)
```

## 📊 **Key Recommendations**

### **For Server-Side Context Window Settings:**

1. **High-Capacity Models** (Claude 4 Sonnet, Gemini 2.5 Pro): 
   - Max: 32,000 tokens (safe)
   - Conservative: 16,000 tokens

2. **Standard Models** (Most Ollama, older models):
   - Max: 4,000-8,000 tokens (safe)
   - Conservative: 2,048 tokens

3. **Local Ollama Configuration:**
   ```bash
   # Set larger context in Ollama
   ollama run llama3.1:8b --num_ctx 32768
   ```

### **Memory Requirements by Model Size:**
- **7B models**: 8GB RAM minimum
- **13B models**: 16GB RAM minimum  
- **27B-34B models**: 32GB RAM minimum
- **70B+ models**: 64GB+ RAM recommended

## ⚠️ **Important Notes**

1. **Safe Limits**: Use "safe_max" values (50% of maximum) to leave room for system prompts and context
2. **Context Window ≠ Output Tokens**: Context window includes input + output; max_tokens is output only
3. **Ollama Default**: Ollama defaults to 2048 tokens - configure `num_ctx` for larger contexts
4. **Hardware Dependent**: Local model limits depend on your available RAM and GPU memory

This configuration should cover all the models you mentioned! 🚀