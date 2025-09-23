# Agent Profiles Cache Invalidation Guide

## Overview

The agent profiles system now includes automatic cache invalidation based on source data fingerprinting. This ensures that changes to `config.AGENT_PROFILES` are automatically detected and reflected without manual cache clearing.

## Key Features

### Automatic Cache Invalidation

The `get_agent_profiles_validated()` function now automatically detects when the source profiles data changes and invalidates the cache accordingly.

**How it works:**
1. Computes a SHA256 fingerprint of the profiles source data
2. Compares current fingerprint with cached fingerprint
3. If fingerprints differ, cache is invalidated and profiles are re-validated
4. If fingerprints match, cached result is returned

### Fingerprinting Algorithm

- Uses stable JSON serialization with sorted keys
- Generates SHA256 hash of the serialized data
- Considers both structure and content changes
- Dictionary key order doesn't affect fingerprint (sorted automatically)
- List/array order DOES affect fingerprint (maintains semantic meaning)

## API Reference

### Core Functions

#### `get_agent_profiles_validated(profiles_source=None)`

Main function for getting validated agent profiles with automatic cache invalidation.

**Parameters:**
- `profiles_source` (Optional[Union[dict, list]]): Explicit profiles source. If None, uses `config.AGENT_PROFILES`

**Returns:**
- `ProfilesConfig`: Validated profiles configuration

**Behavior:**
- Automatically detects changes in source data
- Invalidates cache when data changes
- Reuses cache when data is unchanged
- Works with both explicit source and `config.AGENT_PROFILES`

#### `clear_profiles_cache()`

Manually clears the profiles cache.

**Use cases:**
- Force re-validation regardless of data changes
- Testing scenarios
- Cache reset after configuration changes

#### `get_profiles_cache_info()`

Returns information about the current cache state.

**Returns:**
- `Tuple[bool, Optional[str]]`: (is_cached, fingerprint_prefix)
  - `is_cached`: Whether profiles are currently cached
  - `fingerprint_prefix`: First 8 characters of cache fingerprint, or None

## Integration Guide for CLI Team

### Basic Usage Pattern

```python
from spds.profiles_schema import get_agent_profiles_validated

# Simple usage - automatically uses config.AGENT_PROFILES
validated_config = get_agent_profiles_validated()

# With explicit source
custom_profiles = [{"name": "Agent", "persona": "...", "expertise": [...]}]
validated_config = get_agent_profiles_validated(custom_profiles)
```

### Runtime Configuration Changes

The cache automatically handles runtime changes to `config.AGENT_PROFILES`:

```python
# Initial configuration
config.AGENT_PROFILES = [{"name": "Agent 1", ...}]
config1 = get_agent_profiles_validated()  # Loads and caches

# Configuration change (e.g., from environment variable, user input, etc.)
config.AGENT_PROFILES = [{"name": "Agent 1", ...}, {"name": "Agent 2", ...}]
config2 = get_agent_profiles_validated()  # Automatically detects change and re-validates

# Same configuration
config3 = get_agent_profiles_validated()  # Uses cache (config2 is config3)
```

### Migration from Previous Version

**Before (manual cache management):**
```python
from spds.profiles_schema import get_agent_profiles_validated, clear_profiles_cache

# Had to manually clear cache when changing configuration
clear_profiles_cache()
config.AGENT_PROFILES = new_profiles
validated_config = get_agent_profiles_validated()
```

**After (automatic cache invalidation):**
```python
from spds.profiles_schema import get_agent_profiles_validated

# Cache invalidation is automatic
config.AGENT_PROFILES = new_profiles
validated_config = get_agent_profiles_validated()  # Automatically detects change
```

### Performance Characteristics

- **Cache Hit**: Near-instant return (object reference)
- **Cache Miss/Invalidation**: Full validation required
- **Fingerprint Computation**: Fast SHA256 hash (microseconds for typical profiles)
- **Memory Usage**: Minimal (single cached object + fingerprint string)

### Testing Integration

The cache invalidation system is fully tested with both unit and integration tests.

**Test Categories:**
- Fingerprint computation stability and correctness
- Cache invalidation on data changes
- Cache reuse when data unchanged
- Mixed usage patterns (explicit source vs config)
- Error handling with cache invalidation
- Performance characteristics

**Example Test Pattern:**
```python
from spds.profiles_schema import get_agent_profiles_validated, clear_profiles_cache

def test_cache_invalidation():
    clear_profiles_cache()  # Clean state
    
    # Test cache invalidation behavior
    with patch("spds.config.AGENT_PROFILES", initial_profiles):
        config1 = get_agent_profiles_validated()
        
    with patch("spds.config.AGENT_PROFILES", changed_profiles):
        config2 = get_agent_profiles_validated()  # Should invalidate
        
    assert config1 is not config2
```

## Best Practices

### For CLI Development

1. **Let the cache handle invalidation automatically** - don't manually clear unless necessary
2. **Use `get_profiles_cache_info()` for debugging** - check cache state when troubleshooting
3. **Test with different data patterns** - ensure your CLI works with various profile configurations
4. **Handle validation errors gracefully** - cache invalidation preserves validation behavior

### Performance Optimization

1. **Batch configuration changes** when possible to minimize re-validation
2. **Use explicit source parameter** for temporary profile sets to avoid cache pollution
3. **Monitor cache hit rates** in production using `get_profiles_cache_info()`

### Error Handling

The cache system preserves all existing error handling behavior:

```python
try:
    validated_config = get_agent_profiles_validated()
except ValueError as e:
    # Handle validation errors as before
    logger.error(f"Profile validation failed: {e}")
```

## Implementation Details

### Cache Storage

- **Global variables**: `_validated_profiles_cache`, `_cache_fingerprint`
- **Thread safety**: Not implemented (single-threaded application)
- **Persistence**: In-memory only (cleared on application restart)

### Fingerprint Algorithm

```python
def _compute_profiles_fingerprint(profiles_source):
    json_str = json.dumps(profiles_source, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
```

### Cache Validation Logic

```python
cache_valid = (
    _validated_profiles_cache is not None and 
    _cache_fingerprint == current_fingerprint
)
```

## Troubleshooting

### Common Issues

1. **Cache not invalidating**: Check if `config.AGENT_PROFILES` is actually changing
2. **Unexpected re-validation**: Data might be changing in subtle ways (e.g., object references)
3. **Performance issues**: Large profile sets may take longer to fingerprint and validate

### Debugging Tools

```python
from spds.profiles_schema import get_profiles_cache_info

# Check cache state
is_cached, fingerprint = get_profiles_cache_info()
print(f"Cached: {is_cached}, Fingerprint: {fingerprint}")

# Force cache clear for testing
from spds.profiles_schema import clear_profiles_cache
clear_profiles_cache()
```

### Logging

The system includes debug logging for cache operations:

```python
import logging
logging.getLogger('spds.profiles_schema').setLevel(logging.DEBUG)
```

Log messages include:
- Cache updates with fingerprint prefixes
- Manual cache clears

## Future Considerations

### Potential Enhancements

1. **TTL-based invalidation**: Automatic cache expiry after time period
2. **Size-based invalidation**: Clear cache when memory usage exceeds threshold
3. **Metrics collection**: Track cache hit/miss rates for monitoring
4. **Distributed caching**: Share cache across multiple application instances

### Backward Compatibility

The cache invalidation system is fully backward compatible:
- All existing function signatures unchanged
- All existing behavior preserved
- Additional functions are optional to use
- Error handling behavior identical

### Migration Path

No migration required. The enhanced caching is a drop-in replacement that improves performance while maintaining all existing functionality.