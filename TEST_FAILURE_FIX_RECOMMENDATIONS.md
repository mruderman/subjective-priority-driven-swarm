# Test Failure Fix Recommendations

## Priority 1: Critical Infrastructure Fixes

### 1.1 Fix SwarmManager Initialization Issues

**Problem**: Multiple tests fail due to missing `_history` attribute in SwarmManager

**Recommended Fix**:
```python
# In spds/swarm_manager.py, add to __init__ method:
def __init__(self, mode: str = "hybrid", agent_profiles: Optional[List[Dict]] = None):
    # ... existing code ...
    self._history: List[ConversationMessage] = []  # Add this line
    # ... rest of initialization ...
```

**Affected Tests**:
- `test_agent_turn_no_motivated_prints`
- `test_agent_turn_dispatches_modes` (2 instances)

### 1.2 Fix Method Signature Mismatches

**Problem**: DummyAgent mocks don't match actual method signatures

**Recommended Fix**:
```python
# Update test mocks to match actual signature:
# Current: assess_motivation_and_priority(topic)
# Required: assess_motivation_and_priority(recent_messages, topic)

# In affected test files, update mock creation:
mock_agent = Mock()
mock_agent.assess_motivation_and_priority = Mock(return_value=(25, 8.0))
```

**Affected Tests**:
- `test_sequential_fairness_prints`
- `test_pure_priority_mode`
- `test_all_speak_mode_two_agents`
- `test_hybrid_turn_error_in_response`

## Priority 2: Assessment Tool Integration Fixes

### 2.1 Fix Tool Disabling Logic

**Problem**: Tool not properly disabled after error

**Recommended Fix**:
```python
# In spds/spds_agent.py, update _get_full_assessment method:
def _get_full_assessment(self, conversation_history: str, topic: str):
    if self._assessment_tool_disabled:
        return self._fallback_assessment(conversation_history, topic)
    
    # ... existing tool logic ...
    
    except Exception as e:
        logger.warning(f"Error getting assessment from {self.name}: {e}")
        self._assessment_tool_disabled = True  # Ensure this is set
        self.assessment_tool = None  # Clear the tool reference
        return self._fallback_assessment(conversation_history, topic)
```

**Affected Test**: `test_get_full_assessment_disables_tool_on_invalid_error`

### 2.2 Fix Mock Configuration Issues

**Problem**: Mock return values not properly configured

**Recommended Fix**:
```python
# Update test mocks to return proper assessment objects:
from unittest.mock import Mock, PropertyMock

# Create proper mock assessment
mock_assessment = Mock()
mock_assessment.importance_to_self = 8
mock_assessment.urgency = 4
mock_assessment.importance_to_group = 7

# Configure mock to return this assessment
mock_assessment_func.return_value = mock_assessment
```

**Affected Tests**:
- `test_get_full_assessment_with_tool_return`
- `test_get_full_assessment_with_new_message_format`

### 2.3 Fix Fallback Assessment Implementation

**Problem**: Missing `model_dump` method in fallback objects

**Recommended Fix**:
```python
# In spds/tools.py, update FallbackSubjectiveAssessment:
class FallbackSubjectiveAssessment:
    def __init__(self, importance_to_self=3, urgency=5, importance_to_group=4):
        self.importance_to_self = importance_to_self
        self.urgency = urgency
        self.importance_to_group = importance_to_group
    
    def model_dump(self):
        """Provide compatibility with Pydantic models"""
        return {
            "importance_to_self": self.importance_to_self,
            "urgency": self.urgency,
            "importance_to_group": self.importance_to_group
        }
```

**Affected Tests**: All E2E user scenarios

## Priority 3: Test Infrastructure Fixes

### 3.1 Add Missing Helper Method

**Problem**: Test class missing `_extract_keywords_from_messages` method

**Recommended Fix**:
```python
# In tests/unit/test_assessment_refactor.py, add to TestNewAssessmentPattern:
def _extract_keywords_from_messages(self, messages):
    """Extract simple keywords from message content for testing"""
    content = " ".join(msg.content for msg in messages)
    # Simple keyword extraction for testing
    keywords = []
    for word in content.lower().split():
        if len(word) > 3 and word not in ["the", "and", "for", "with"]:
            keywords.append(word)
    return keywords[:5]  # Return top 5 keywords
```

**Affected Test**: `test_new_assessment_with_recent_messages`

### 3.2 Fix Conversation Message Test

**Problem**: Test attempting to create message with empty content

**Recommended Fix**:
```python
# In tests/unit/test_conversation_message.py, update test:
def test_empty_content_handling(self):
    """Test handling of empty or whitespace-only content."""
    # Test that empty content raises ValueError
    with pytest.raises(ValueError, match="Message content cannot be empty"):
        ConversationMessage(
            sender="Dave",
            content="",
            timestamp=datetime.now()
        )
    
    # Test whitespace-only content also raises ValueError
    with pytest.raises(ValueError, match="Message content cannot be empty"):
        ConversationMessage(
            sender="Eve",
            content="   \n\t  ",
            timestamp=datetime.now()
        )
```

**Affected Test**: `test_empty_content_handling`

## Priority 4: Mock Object Comparison Fix

**Problem**: Mock object comparison issue in message indexing

**Recommended Fix**:
```python
# In tests/unit/test_swarm_manager_modes_additional.py, fix mock setup:
def test_agent_turn_dispatches_modes(self):
    # Setup proper mock that supports comparison
    mock_agent = Mock()
    mock_agent.last_message_index = 0  # Ensure this is an integer, not a Mock
    mock_agent.assess_motivation_and_priority = Mock(return_value=(25, 8.0))
    mock_agent.speak = Mock(return_value="Test response")
    
    # ... rest of test ...
```

**Affected Test**: `test_agent_turn_dispatches_modes`

## Environment and Configuration Recommendations

### 1. Update Test Dependencies
```bash
# Ensure all test dependencies are up to date
pip install -r requirements.txt
pip install pytest pytest-cov pytest-mock pytest-asyncio
```

### 2. Configure Test Environment
```python
# Add to conftest.py for better test isolation
@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset any global state between tests"""
    # Clear any global caches or state
    pass
```

### 3. Improve Test Coverage
```bash
# Run specific test categories to identify coverage gaps
pytest tests/unit/ --cov=spds --cov-report=html
pytest tests/integration/ --cov=spds --cov-report=html
pytest tests/e2e/ --cov=spds --cov-report=html
```

## Implementation Priority Order

1. **Immediate** (Blocking): Fix SwarmManager initialization and method signature mismatches
2. **High Priority**: Fix assessment tool integration issues
3. **Medium Priority**: Fix test infrastructure and helper methods
4. **Low Priority**: Environment and configuration improvements

## Expected Outcomes After Fixes

- **Test Pass Rate**: 100% (580/580 tests passing)
- **Code Coverage**: Maintain or improve 89% coverage
- **Build Stability**: All CI/CD pipelines should pass
- **Development Velocity**: Faster iteration with reliable test suite

## Verification Steps

After implementing fixes, run:
```bash
# Comprehensive test suite
pytest --tb=short -v

# Coverage verification
pytest --cov=spds --cov-report=html

# Specific failure categories
pytest tests/unit/test_spds_agent.py -v
pytest tests/unit/test_swarm_manager*.py -v
pytest tests/e2e/test_user_scenarios.py -v
```

These fixes will restore test suite reliability and ensure the codebase maintains high quality standards.