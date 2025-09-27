# Conversation Logic Refactor Project

## Project Overview

This document tracks the comprehensive refactor of SPDS conversation logic to address fundamental flaws in the current system. The goal is to replace static, repetitive conversation management with dynamic, context-aware agent interactions.

## Problem Statement

### Current System Flaws
- **Static Topic Assessment**: Agents always assess motivation based on original topic ("Hi Jack and Jill..."), never evolving conversation
- **Monolithic History**: Entire conversation bundled into confusing flat strings each turn
- **Generic Prompting**: Vague instructions without specific context
- **Round Cycling Issues**: Assessment doesn't reflect current conversation state

### Impact
- Conversations become repetitive and stagnant
- Agents lose context as discussions evolve
- Poor user experience with irrelevant responses
- Inefficient processing of conversation history

## Technical Specifications

### 1. Message Class Architecture
```python
@dataclass
class ConversationMessage:
    sender: str           # Agent name or "You" for human
    content: str         # Message text content
    timestamp: datetime  # When message was sent
    
# Usage Example:
message = ConversationMessage(
    sender="Alice", 
    content="I think we should prioritize security",
    timestamp=datetime.now()
)
```

### 2. History Management System
- **Current**: `List[Tuple[str, str]]` → flat string conversion
- **New**: `List[ConversationMessage]` → structured access
- **Key Method**: `get_new_messages_since_last_turn(agent)` returns only unprocessed messages

### 3. Assessment Logic Changes
- **Current**: `assess_motivation_and_priority(static_topic)`
- **New**: `assess_motivation_and_priority(recent_messages, original_topic)`
- **Benefit**: Real-time relevance assessment based on conversation evolution

## Implementation Plan

### Phase 1: Project Documentation ✅
- [x] Create comprehensive project tracker
- [x] Define technical specifications
- [x] Establish operationalized todos

### Phase 2: Core Infrastructure 
- [ ] **Task 2.1**: Create `spds/message.py` with ConversationMessage class
  - [ ] Define dataclass with sender, content, timestamp
  - [ ] Add helper methods for formatting and comparison
  - [ ] Include type hints and documentation
  - **Assignee**: _Available_
  - **Estimated Time**: 1-2 hours
  - **Dependencies**: None

- [ ] **Task 2.2**: Update SwarmManager history system in `spds/swarm_manager.py`
  - [ ] Replace `self._history` with `List[ConversationMessage]`
  - [ ] Implement `get_new_messages_since_last_turn(agent)` method
  - [ ] Update `_append_history()` for ConversationMessage objects
  - [ ] Maintain backward compatibility with `conversation_history` property
  - **Assignee**: _Available_
  - **Estimated Time**: 4-6 hours
  - **Dependencies**: Task 2.1 (ConversationMessage class)

### Phase 3: Fix Round Cycling Problem
- [ ] **Task 3.1**: Update agent assessment logic in `spds/spds_agent.py`
  - [ ] Modify `assess_motivation_and_priority()` signature
  - [ ] Update `_get_full_assessment()` to use recent messages
  - [ ] Revise assessment prompts for current conversation context
  - [ ] Remove static topic references in motivation calculation
  - **Assignee**: _Available_
  - **Estimated Time**: 6-8 hours
  - **Dependencies**: Task 2.2 (Message delivery system)

- [ ] **Task 3.2**: Update conversation modes in `spds/swarm_manager.py`
  - [ ] Modify `_agent_turn()` to pass recent messages
  - [ ] Update `_hybrid_turn()` for incremental message delivery
  - [ ] Update `_all_speak_turn()` for structured history
  - [ ] Update `_sequential_turn()` and `_pure_priority_turn()`
  - [ ] Remove generic prompts, let agents be contextually smart
  - **Assignee**: _Available_
  - **Estimated Time**: 6-8 hours
  - **Dependencies**: Task 3.1 (Assessment logic)

### Phase 4: Testing & Validation
- [ ] **Task 4.1**: Unit tests for new components
  - [ ] ConversationMessage class tests
  - [ ] Message filtering and delivery tests
  - [ ] Assessment logic validation tests
  - **Assignee**: _Available_
  - **Estimated Time**: 3-4 hours
  - **Dependencies**: Tasks 2.1, 2.2, 3.1

- [ ] **Task 4.2**: Integration tests for conversation flow
  - [ ] End-to-end conversation scenarios
  - [ ] Performance comparison (old vs new)
  - [ ] Agent context awareness validation
  - **Assignee**: _Available_
  - **Estimated Time**: 4-5 hours
  - **Dependencies**: Task 3.2 (All core changes)

- [ ] **Task 4.3**: Migration strategy implementation
  - [ ] Feature flag for gradual rollout
  - [ ] Fallback to old system capability
  - [ ] Documentation updates
  - **Assignee**: _Available_
  - **Estimated Time**: 2-3 hours
  - **Dependencies**: Task 4.2 (Validation complete)

## Code Change Locations

### Primary Files to Modify
1. **`spds/swarm_manager.py`** - Core conversation orchestration (Lines 84-86, 170-180, 619-674)
2. **`spds/spds_agent.py`** - Agent assessment and motivation logic (Lines 728-763)
3. **`spds/message.py`** - New file for structured message handling

### Key Methods to Update
- `SwarmManager._append_history()` (Line 199)
- `SwarmManager._get_filtered_conversation_history()` (Line 170)
- `SwarmManager._agent_turn()` (Line 619)
- `SPDSAgent.assess_motivation_and_priority()` (Line 728)
- `SPDSAgent._get_full_assessment()` (Line 253)

## Progress Tracking

### Overall Status: 🟡 In Progress
- **Started**: [Current Date]
- **Expected Completion**: [Target Date]
- **Current Phase**: Phase 1 - Project Documentation

### Team Assignments
| Task | Assignee | Status | Start Date | Est. Completion |
|------|----------|--------|------------|-----------------|
| 2.1 | _Available_ | ⏳ Pending | - | - |
| 2.2 | _Available_ | ⏳ Pending | - | - |
| 3.1 | _Available_ | ⏳ Pending | - | - |
| 3.2 | _Available_ | ⏳ Pending | - | - |
| 4.1 | _Available_ | ⏳ Pending | - | - |
| 4.2 | _Available_ | ⏳ Pending | - | - |
| 4.3 | _Available_ | ⏳ Pending | - | - |

### Risk Assessment
- **High Risk**: Breaking existing conversation flows during transition
- **Medium Risk**: Performance impact from message object overhead
- **Low Risk**: Test coverage gaps for edge cases

### Mitigation Strategies
- Implement feature flag for safe rollback
- Maintain backward compatibility during transition
- Comprehensive testing before deployment

## Success Metrics

### Technical Objectives
- [ ] Agents assess motivation based on recent conversation (not static topic)
- [ ] Message delivery uses only new content per agent per turn
- [ ] Eliminated "Hi Jack and Jill" repetitive assessment problem
- [ ] Natural conversation flow driven by human user messages
- [ ] Structured message management with proper separation of concerns

### Performance Goals
- [ ] < 2 second response time for agent turns
- [ ] < 50% memory usage for conversation history storage
- [ ] 100% backward compatibility during transition period

### User Experience Improvements
- [ ] More relevant agent responses to current conversation
- [ ] Better conversation flow and context awareness
- [ ] Reduced repetitive or off-topic agent contributions

## Notes & Decisions

### Architecture Decisions
- **Message Format**: Simple dataclass over complex object hierarchy
- **History Management**: Incremental delivery over full history caching
- **Assessment Context**: Recent messages over dynamic topic generation
- **Prompting Strategy**: Minimal intervention, let agents be smart

### Implementation Notes
- Maintain backward compatibility with existing `conversation_history` string property
- Use feature flags for gradual rollout
- Focus on core cycling problem rather than overengineering
- Preserve existing conversation modes, improve their context delivery

---

**Last Updated**: [Auto-update timestamp]
**Document Owner**: SPDS Development Team
**Review Schedule**: Weekly during active development