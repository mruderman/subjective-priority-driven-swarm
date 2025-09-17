#!/usr/bin/env python3
"""
Response Validator Test - Testing and Validating Agent Response Mechanisms

This script reproduces and validates the initial response issue to understand
why the first agent response fails in hybrid group chat mode but subsequent
responses work correctly.

Based on Letta principles:
- Agents are stateful (maintain conversation history)
- Send only single new messages per request
- Response contains multiple message types
- Multi-agent communication via built-in tools
"""

import sys

sys.path.append(".")

import json
import time
from typing import Any, Dict, List

from letta_client import Letta
from letta_client.types import LettaResponse, Message

from spds import config
from spds.spds_agent import SPDSAgent
from spds.swarm_manager import SwarmManager


class ResponseValidator:
    """Validates agent response mechanisms and identifies failure patterns."""

    def __init__(self):
        self.client = self._get_client()
        self.test_results = {}
        self.failure_patterns = []

    def _get_client(self):
        """Get Letta client with proper authentication."""
        if config.LETTA_ENVIRONMENT == "SELF_HOSTED" and config.LETTA_SERVER_PASSWORD:
            return Letta(
                token=config.LETTA_SERVER_PASSWORD, base_url=config.LETTA_BASE_URL
            )
        elif config.LETTA_API_KEY:
            return Letta(token=config.LETTA_API_KEY, base_url=config.LETTA_BASE_URL)
        else:
            return Letta(base_url=config.LETTA_BASE_URL)

    def get_usable_agents(self) -> List[Any]:
        """Get list of usable agents (excluding problematic ones)."""
        agents = self.client.agents.list()
        usable_agents = []

        for agent in agents:
            # Skip problematic agents based on test patterns
            if "Adaptive Secretary" in agent.name and "20" not in agent.name:
                continue
            if "scratch-agent" in agent.name:
                continue
            if "test-" in agent.name.lower():
                continue

            usable_agents.append(agent)

        return usable_agents[:4]  # Use maximum 4 agents for testing

    def test_initial_response_failure(self):
        """
        Test Case 1: Reproduce the initial response failure pattern

        This test specifically reproduces the scenario where:
        1. SwarmManager is created with hybrid mode
        2. First agent response fails or returns fallback
        3. Subsequent responses work correctly
        """
        print("🧪 Test 1: Initial Response Failure Pattern")
        print("=" * 60)

        usable_agents = self.get_usable_agents()
        if len(usable_agents) < 2:
            print("❌ Not enough usable agents for testing")
            return False

        agent_ids = [agent.id for agent in usable_agents[:3]]
        print(f"Using agents: {[a.name for a in usable_agents[:3]]}")

        # Create SwarmManager in hybrid mode (where the issue occurs)
        try:
            manager = SwarmManager(
                client=self.client,
                agent_ids=agent_ids,
                conversation_mode="hybrid",
                enable_secretary=False,  # Simplify test - no secretary
            )
            print("✅ SwarmManager created successfully")
        except Exception as e:
            print(f"❌ Failed to create SwarmManager: {e}")
            return False

        # Test the exact sequence that causes initial response failure
        test_message = "What do you think about collaborative problem-solving in teams?"
        topic = "collaborative problem-solving"

        print(f"\n📝 Test message: {test_message}")

        # Step 1: Update agent memories (this works)
        print("\n🔄 Step 1: Updating agent memories...")
        try:
            manager._update_agent_memories(test_message, "Test User")
            print("✅ Agent memories updated successfully")
        except Exception as e:
            print(f"❌ Failed to update memories: {e}")
            return False

        # Step 2: Assess motivation (this works)
        print("\n🧠 Step 2: Assessing agent motivation...")
        motivated_agents = []
        for agent in manager.agents:
            try:
                agent.assess_motivation_and_priority(topic)
                print(
                    f"  {agent.name}: motivation={agent.motivation_score}, priority={agent.priority_score:.2f}"
                )
                if agent.priority_score > 0:
                    motivated_agents.append(agent)
            except Exception as e:
                print(f"  ❌ {agent.name} assessment failed: {e}")

        if not motivated_agents:
            print("❌ No agents motivated to speak")
            return False

        # Step 3: Test initial responses (THIS IS WHERE FAILURE OCCURS)
        print(
            f"\n🎭 Step 3: Testing initial responses from {len(motivated_agents)} motivated agents..."
        )

        initial_responses = []
        failure_count = 0

        for i, agent in enumerate(motivated_agents):
            print(f"\n  Testing {agent.name} (attempt {i+1})...")

            try:
                # This is the exact call that fails on first attempt
                response = agent.speak(mode="initial", topic=topic)
                message_text = manager._extract_agent_response(response)

                # Analyze the response
                response_analysis = self._analyze_response(
                    agent.name, message_text, response
                )
                initial_responses.append((agent, message_text, response_analysis))

                print(f"    Response: {message_text[:100]}...")
                print(f"    Analysis: {response_analysis['status']}")

                if response_analysis["is_failure"]:
                    failure_count += 1
                    self.failure_patterns.append(
                        {
                            "agent": agent.name,
                            "attempt": i + 1,
                            "response": message_text,
                            "analysis": response_analysis,
                        }
                    )

            except Exception as e:
                print(f"    ❌ Exception occurred: {e}")
                failure_count += 1
                self.failure_patterns.append(
                    {"agent": agent.name, "attempt": i + 1, "exception": str(e)}
                )

        # Step 4: Test subsequent responses (these usually work)
        print(f"\n🔄 Step 4: Testing subsequent responses...")

        # Update memories with initial responses
        for agent, message_text, _ in initial_responses:
            if message_text and "having trouble" not in message_text:
                manager._update_agent_memories(message_text, agent.name)

        # Test response round
        subsequent_success = 0
        for agent in motivated_agents:
            try:
                response = agent.speak(mode="response", topic=topic)
                message_text = manager._extract_agent_response(response)

                response_analysis = self._analyze_response(
                    agent.name, message_text, response
                )
                print(f"    {agent.name} subsequent: {response_analysis['status']}")

                if not response_analysis["is_failure"]:
                    subsequent_success += 1

            except Exception as e:
                print(f"    ❌ {agent.name} subsequent failed: {e}")

        # Results summary
        print(f"\n📊 Test Results Summary:")
        print(
            f"  Initial responses: {len(initial_responses) - failure_count}/{len(motivated_agents)} successful"
        )
        print(
            f"  Subsequent responses: {subsequent_success}/{len(motivated_agents)} successful"
        )
        print(f"  Failure patterns identified: {len(self.failure_patterns)}")

        self.test_results["initial_response_test"] = {
            "total_agents": len(motivated_agents),
            "initial_failures": failure_count,
            "subsequent_successes": subsequent_success,
            "failure_patterns": self.failure_patterns,
        }

        return (
            len(self.failure_patterns) > 0
        )  # Return True if we found failure patterns

    def test_message_format_validation(self):
        """
        Test Case 2: Validate message formatting and API usage

        Tests the exact message formats and API calls to identify
        formatting issues that might cause initial response failures.
        """
        print("\n🧪 Test 2: Message Format Validation")
        print("=" * 60)

        usable_agents = self.get_usable_agents()
        if len(usable_agents) < 1:
            print("❌ No usable agents for testing")
            return False

        agent_state = usable_agents[0]
        agent = SPDSAgent(agent_state, self.client)

        print(f"Testing with agent: {agent.name}")

        # Test different message formats that might cause issues
        test_scenarios = [
            {
                "name": "Empty conversation history",
                "conversation": "",
                "expected": "fallback_or_error",
            },
            {
                "name": "Basic user message",
                "conversation": "User: Hello, how are you?",
                "expected": "success",
            },
            {
                "name": "Complex conversation with context",
                "conversation": "User: What are your thoughts on teamwork?\nAgent1: I think collaboration is key.\nUser: Can you elaborate?",
                "expected": "success",
            },
            {
                "name": "Very long conversation",
                "conversation": "User: " + "This is a very long message. " * 100,
                "expected": "success_or_truncation",
            },
        ]

        format_results = []

        for scenario in test_scenarios:
            print(f"\n  📝 Testing: {scenario['name']}")

            try:
                # Direct API call to test message format
                response = self.client.agents.messages.create(
                    agent_id=agent.agent.id,
                    messages=[
                        {
                            "role": "user",
                            "content": f"{scenario['conversation']}\nBased on my assessment, here is my contribution:",
                        }
                    ],
                )

                # Analyze response format
                analysis = self._analyze_response_format(response)
                format_results.append(
                    {
                        "scenario": scenario["name"],
                        "success": analysis["valid"],
                        "response_types": analysis["message_types"],
                        "has_content": analysis["has_content"],
                        "tool_calls": analysis["tool_calls"],
                    }
                )

                print(
                    f"    Status: {'✅' if analysis['valid'] else '❌'} {analysis['summary']}"
                )

            except Exception as e:
                print(f"    ❌ Exception: {e}")
                format_results.append(
                    {
                        "scenario": scenario["name"],
                        "success": False,
                        "exception": str(e),
                    }
                )

        self.test_results["format_validation"] = format_results
        return True

    def test_state_persistence(self):
        """
        Test Case 3: Agent state persistence between rounds

        Validates that agent state (memories, assessments) persists
        correctly between conversation rounds.
        """
        print("\n🧪 Test 3: State Persistence Testing")
        print("=" * 60)

        usable_agents = self.get_usable_agents()
        if len(usable_agents) < 1:
            print("❌ No usable agents for testing")
            return False

        agent_state = usable_agents[0]
        agent = SPDSAgent(agent_state, self.client)

        print(f"Testing with agent: {agent.name}")

        # Initial state
        print(f"\n🔄 Initial state:")
        print(f"  Motivation: {agent.motivation_score}")
        print(f"  Priority: {agent.priority_score}")
        print(f"  Assessment: {agent.last_assessment}")

        # Update memory and assess
        test_topic = "innovation strategies"
        self.client.agents.messages.create(
            agent_id=agent.agent.id,
            messages=[
                {
                    "role": "user",
                    "content": "User: Let's discuss innovation strategies in tech teams.",
                }
            ],
        )

        # First assessment
        agent.assess_motivation_and_priority(test_topic)
        first_assessment = {
            "motivation": agent.motivation_score,
            "priority": agent.priority_score,
            "assessment": agent.last_assessment,
        }

        print(f"\n📊 After first assessment:")
        print(f"  Motivation: {first_assessment['motivation']}")
        print(f"  Priority: {first_assessment['priority']:.2f}")

        # Second message and assessment
        self.client.agents.messages.create(
            agent_id=agent.agent.id,
            messages=[
                {
                    "role": "user",
                    "content": "User: What specific innovation practices work best?",
                }
            ],
        )

        agent.assess_motivation_and_priority("innovation practices")
        second_assessment = {
            "motivation": agent.motivation_score,
            "priority": agent.priority_score,
            "assessment": agent.last_assessment,
        }

        print(f"\n📊 After second assessment:")
        print(f"  Motivation: {second_assessment['motivation']}")
        print(f"  Priority: {second_assessment['priority']:.2f}")

        # Check persistence
        state_changed = (
            first_assessment["motivation"] != second_assessment["motivation"]
            or first_assessment["priority"] != second_assessment["priority"]
        )

        print(f"\n🔍 State persistence analysis:")
        print(f"  State changed between rounds: {'✅' if state_changed else '❌'}")
        print(f"  Assessment object updated: {'✅' if agent.last_assessment else '❌'}")

        self.test_results["state_persistence"] = {
            "first_assessment": first_assessment,
            "second_assessment": second_assessment,
            "state_changed": state_changed,
            "assessment_valid": agent.last_assessment is not None,
        }

        return True

    def _analyze_response(
        self, agent_name: str, message_text: str, response: LettaResponse
    ) -> Dict[str, Any]:
        """Analyze an agent response to identify failure patterns."""
        analysis = {
            "agent": agent_name,
            "is_failure": False,
            "status": "unknown",
            "message_types": [],
            "has_tool_calls": False,
            "content_length": len(message_text) if message_text else 0,
            "response_raw": (
                str(response)[:200] + "..."
                if len(str(response)) > 200
                else str(response)
            ),
        }

        # Check for common failure patterns
        if not message_text or len(message_text.strip()) == 0:
            analysis["is_failure"] = True
            analysis["status"] = "empty_response"
        elif "having trouble" in message_text.lower():
            analysis["is_failure"] = True
            analysis["status"] = "fallback_response"
        elif len(message_text) < 10:
            analysis["is_failure"] = True
            analysis["status"] = "too_short"
        elif "error" in message_text.lower():
            analysis["is_failure"] = True
            analysis["status"] = "error_in_content"
        else:
            analysis["status"] = "success"

        # Analyze response structure
        if hasattr(response, "messages") and response.messages:
            for msg in response.messages:
                analysis["message_types"].append(
                    msg.role if hasattr(msg, "role") else "unknown"
                )
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    analysis["has_tool_calls"] = True

        return analysis

    def _analyze_response_format(self, response: LettaResponse) -> Dict[str, Any]:
        """Analyze response format for validation."""
        analysis = {
            "valid": False,
            "message_types": [],
            "has_content": False,
            "tool_calls": 0,
            "summary": "",
        }

        try:
            if hasattr(response, "messages") and response.messages:
                analysis["valid"] = True

                for msg in response.messages:
                    msg_type = msg.role if hasattr(msg, "role") else "unknown"
                    analysis["message_types"].append(msg_type)

                    if hasattr(msg, "content") and msg.content:
                        analysis["has_content"] = True

                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        analysis["tool_calls"] += len(msg.tool_calls)

                analysis["summary"] = (
                    f"{len(response.messages)} messages, {len(set(analysis['message_types']))} types"
                )
            else:
                analysis["summary"] = "No messages in response"

        except Exception as e:
            analysis["summary"] = f"Analysis error: {e}"

        return analysis

    def run_validation_suite(self):
        """Run the complete validation suite."""
        print("🎯 LETTA AGENT RESPONSE VALIDATION SUITE")
        print("=" * 80)
        print("Testing agent response mechanisms to identify initial response failures")
        print()

        # Test 1: Initial response failure pattern
        test1_result = self.test_initial_response_failure()

        # Test 2: Message format validation
        test2_result = self.test_message_format_validation()

        # Test 3: State persistence
        test3_result = self.test_state_persistence()

        # Generate final report
        self._generate_validation_report()

        return all([test1_result, test2_result, test3_result])

    def _generate_validation_report(self):
        """Generate comprehensive validation report."""
        print("\n" + "=" * 80)
        print("📊 VALIDATION REPORT")
        print("=" * 80)

        if "initial_response_test" in self.test_results:
            test1 = self.test_results["initial_response_test"]
            print(f"\n🔍 Initial Response Test:")
            print(f"  Total agents tested: {test1['total_agents']}")
            print(f"  Initial failures: {test1['initial_failures']}")
            print(f"  Subsequent successes: {test1['subsequent_successes']}")
            print(
                f"  Failure rate: {(test1['initial_failures']/test1['total_agents']*100):.1f}%"
            )

            if test1["failure_patterns"]:
                print(f"\n🚨 Failure Patterns Identified:")
                for i, pattern in enumerate(test1["failure_patterns"][:3], 1):
                    print(f"  {i}. Agent: {pattern['agent']}")
                    if "analysis" in pattern:
                        print(f"     Status: {pattern['analysis']['status']}")
                        print(
                            f"     Content length: {pattern['analysis']['content_length']}"
                        )
                    if "exception" in pattern:
                        print(f"     Exception: {pattern['exception']}")

        if "format_validation" in self.test_results:
            test2 = self.test_results["format_validation"]
            print(f"\n📝 Message Format Validation:")
            successful_formats = sum(1 for r in test2 if r.get("success", False))
            print(f"  Successful formats: {successful_formats}/{len(test2)}")

            for result in test2:
                status = "✅" if result.get("success", False) else "❌"
                print(f"  {status} {result['scenario']}")

        if "state_persistence" in self.test_results:
            test3 = self.test_results["state_persistence"]
            print(f"\n🧠 State Persistence:")
            print(
                f"  State changes detected: {'✅' if test3['state_changed'] else '❌'}"
            )
            print(
                f"  Assessment object valid: {'✅' if test3['assessment_valid'] else '❌'}"
            )

        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")

        if self.failure_patterns:
            print("  🔧 Initial response failures detected:")
            print("     - Implement retry logic for first responses")
            print("     - Add response validation before processing")
            print("     - Consider pre-warming agent context")

        if "format_validation" in self.test_results:
            failed_formats = [
                r
                for r in self.test_results["format_validation"]
                if not r.get("success", True)
            ]
            if failed_formats:
                print("  📝 Message format issues found:")
                print("     - Validate message structure before sending")
                print("     - Implement robust error handling")

        print("\n✅ Validation complete. Use results to improve response reliability.")


def main():
    """Run the response validation test suite."""
    validator = ResponseValidator()

    try:
        success = validator.run_validation_suite()

        if success:
            print("\n🎉 Validation suite completed successfully!")
            print("📄 Check the validation report above for detailed findings.")
        else:
            print("\n⚠️ Some validation tests encountered issues.")
            print("🔧 Review the report and logs for troubleshooting guidance.")

    except Exception as e:
        print(f"\n❌ Validation suite failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
