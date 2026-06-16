from __future__ import annotations

import unittest

from tools.execution_order_validator import validate_execution_order_text


class ExecutionOrderValidatorTests(unittest.TestCase):
    def test_template_with_bracketed_fields_blocks_live_autonomy(self) -> None:
        report = validate_execution_order_text(
            """
ACCOUNT AND MARKET AUTHORITY
- Broker/API: [BROKER]
PRIMARY OBJECTIVE
NON-NEGOTIABLE RISK LIMITS
MANDATORY PRE-TRADE CHECK
ORDER EXECUTION RULES
POSITION MANAGEMENT
KILL SWITCH CONDITIONS
STRATEGY DISCIPLINE
LOGGING AND REPORTING
COMPLIANCE AND REFUSAL RULES
FINAL OPERATING COMMAND
Begin autonomous monitoring and trading only after all bracketed fields above are completed and validated.
"""
        )

        self.assertEqual(report["status"], "EXECUTION_ORDER_BLOCKED")
        self.assertEqual(report["decision"], "NO_GO_LIVE_AUTONOMY")
        self.assertIn("[BROKER]", report["unresolved_bracketed_fields"])
        self.assertIn("all_bracketed_fields_completed", report["blockers"])
        self.assertFalse(report["can_place_order_from_this_report"])

    def test_completed_order_can_pass_text_validation_only(self) -> None:
        report = validate_execution_order_text(
            """
ACCOUNT AND MARKET AUTHORITY
PRIMARY OBJECTIVE
NON-NEGOTIABLE RISK LIMITS
MANDATORY PRE-TRADE CHECK
ORDER EXECUTION RULES
POSITION MANAGEMENT
KILL SWITCH CONDITIONS
STRATEGY DISCIPLINE
LOGGING AND REPORTING
COMPLIANCE AND REFUSAL RULES
FINAL OPERATING COMMAND
Begin autonomous monitoring and trading only after all bracketed fields above are completed and validated.
"""
        )

        self.assertEqual(report["status"], "EXECUTION_ORDER_VALIDATED")
        self.assertEqual(report["decision"], "ORDER_TEXT_READY_FOR_STAGE_GATE_REVIEW")

    def test_live_cash_final_command_can_pass_text_validation(self) -> None:
        report = validate_execution_order_text(
            """
ACCOUNT AND MARKET AUTHORITY
PRIMARY OBJECTIVE
NON-NEGOTIABLE RISK LIMITS
MANDATORY PRE-TRADE CHECK
ORDER EXECUTION RULES
POSITION MANAGEMENT
KILL SWITCH CONDITIONS
STRATEGY DISCIPLINE
LOGGING AND REPORTING
COMPLIANCE AND REFUSAL RULES
FINAL OPERATING COMMAND
Begin limited live-cash autonomous monitoring and trading only after this live-cash authority package validates and every Stage 5 live-cash promotion gate passes.
"""
        )

        self.assertEqual(report["status"], "EXECUTION_ORDER_VALIDATED")


if __name__ == "__main__":
    unittest.main()
