"""
End-to-end API smoke test for researcher-advisor permission management.

Usage:
    python scripts/test_researcher_advisor_permissions.py
    python scripts/test_researcher_advisor_permissions.py --base-url http://127.0.0.1:8000

Prerequisites:
    - FastAPI server is running
    - `requests` is installed
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
API_PREFIX = "/api/v1"


@dataclass
class TestReport:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def add_pass(self, message: str) -> None:
        self.passed.append(message)
        print(f"[PASS] {message}")

    def add_fail(self, message: str) -> None:
        self.failed.append(message)
        print(f"[FAIL] {message}")


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{API_PREFIX}{path}"


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    expected_status: int | None = None,
    json_body: dict[str, Any] | None = None,
) -> requests.Response:
    response = session.request(method, url, json=json_body, timeout=15)
    print(f"{method} {url} -> {response.status_code}")
    if response.text:
        print(response.text)
    if expected_status is not None and response.status_code != expected_status:
        raise AssertionError(
            f"Expected status {expected_status}, got {response.status_code}: {response.text}"
        )
    return response


def assert_equal(actual: Any, expected: Any, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def assert_in(member: Any, container: Any, message: str) -> None:
    if member not in container:
        raise AssertionError(f"{message}: {member!r} not found in {container!r}")


def run_test(base_url: str) -> TestReport:
    report = TestReport()
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    unique_suffix = str(int(time.time()))
    advisor_email = f"advisor_{unique_suffix}@example.com"
    researcher_email = f"researcher_{unique_suffix}@example.com"

    advisor_id = None
    researcher_id = None

    try:
        print("\n1. Create advisor")
        advisor_payload = {
            "name": f"Advisor {unique_suffix}",
            "email": advisor_email,
            "affiliation": "Tsinghua University",
            "research_areas": ["governance", "policy"],
            "bio": "API automated test advisor",
        }
        response = request_json(
            session,
            "POST",
            build_url(base_url, "/advisors"),
            expected_status=201,
            json_body=advisor_payload,
        )
        advisor = response.json()
        advisor_id = advisor["id"]
        report.add_pass("Created advisor successfully")

        print("\n2. Create advisor sub-fields")
        for index, field_name in enumerate(("governance", "policy"), start=1):
            sub_field_payload = {
                "field_name": field_name,
                "description": f"{field_name} test sub-field",
                "display_order": index,
                "advisor_id": advisor_id,
            }
            request_json(
                session,
                "POST",
                build_url(base_url, f"/advisors/{advisor_id}/sub-fields"),
                expected_status=201,
                json_body=sub_field_payload,
            )
        report.add_pass("Created governance and policy sub-fields successfully")

        print("\n3. Create researcher")
        researcher_payload = {
            "name": f"Researcher {unique_suffix}",
            "email": researcher_email,
            "password": "test123456",
            "research_group": "Public Governance Lab",
            "academic_level": "PhD",
            "bio": "API automated test researcher",
        }
        response = request_json(
            session,
            "POST",
            build_url(base_url, "/researchers/"),
            expected_status=201,
            json_body=researcher_payload,
        )
        researcher = response.json()
        researcher_id = researcher["id"]
        report.add_pass("Created researcher successfully")

        print("\n4. Create researcher-advisor relationship with partial sub-field access")
        relationship_payload = {
            "advisor_id": advisor_id,
            "relationship_type": "co_advisor",
            "access_level": "readonly",
            "sub_fields_access": ["governance"],
        }
        response = request_json(
            session,
            "POST",
            build_url(base_url, f"/researchers/{researcher_id}/advisors"),
            expected_status=201,
            json_body=relationship_payload,
        )
        relationship = response.json()
        assert_equal(relationship["relationship_type"], "co_advisor", "Initial relationship_type")
        assert_equal(relationship["access_level"], "readonly", "Initial access_level")
        assert_equal(relationship["sub_fields_access"], ["governance"], "Initial sub_fields_access")
        report.add_pass("Created advisor relationship with governance-only access")

        print("\n5. Get single relationship and verify governance access")
        response = request_json(
            session,
            "GET",
            build_url(base_url, f"/researchers/{researcher_id}/advisors/{advisor_id}"),
            expected_status=200,
        )
        relationship_detail = response.json()
        assert_in("governance", relationship_detail["sub_fields_access"], "Governance access check")
        report.add_pass("Fetched single relationship detail with governance access")

        print("\n6. Update relationship to primary advisor with full sub-field access")
        update_payload = {
            "relationship_type": "primary_advisor",
            "access_level": "full",
            "sub_fields_access": ["governance", "policy"],
        }
        response = request_json(
            session,
            "PUT",
            build_url(base_url, f"/researchers/{researcher_id}/advisors/{advisor_id}"),
            expected_status=200,
            json_body=update_payload,
        )
        updated_relationship = response.json()
        assert_equal(updated_relationship["relationship_type"], "primary_advisor", "Updated relationship_type")
        assert_equal(updated_relationship["access_level"], "full", "Updated access_level")
        assert_equal(
            updated_relationship["sub_fields_access"],
            ["governance", "policy"],
            "Updated sub_fields_access",
        )
        report.add_pass("Updated relationship to primary advisor with full access")

        print("\n7. Get updated relationship and verify fields")
        response = request_json(
            session,
            "GET",
            build_url(base_url, f"/researchers/{researcher_id}/advisors/{advisor_id}"),
            expected_status=200,
        )
        relationship_detail = response.json()
        assert_equal(relationship_detail["relationship_type"], "primary_advisor", "Fetched updated relationship_type")
        assert_equal(relationship_detail["access_level"], "full", "Fetched updated access_level")
        assert_equal(
            relationship_detail["sub_fields_access"],
            ["governance", "policy"],
            "Fetched updated sub_fields_access",
        )
        report.add_pass("Verified updated relationship detail successfully")

        print("\n8. Delete relationship")
        request_json(
            session,
            "DELETE",
            build_url(base_url, f"/researchers/{researcher_id}/advisors/{advisor_id}"),
            expected_status=204,
        )
        report.add_pass("Deleted researcher-advisor relationship successfully")

        print("\n9. Negative test with nonexistent sub-field")
        invalid_relationship_payload = {
            "advisor_id": advisor_id,
            "relationship_type": "co_advisor",
            "access_level": "readonly",
            "sub_fields_access": ["nonexistent-field"],
        }
        response = request_json(
            session,
            "POST",
            build_url(base_url, f"/researchers/{researcher_id}/advisors"),
            json_body=invalid_relationship_payload,
        )
        if response.status_code == 409:
            report.add_pass("Invalid sub-field request correctly returned conflict")
        else:
            report.add_fail(
                "Invalid sub-field request did not return conflict "
                f"(status={response.status_code})"
            )

    except Exception as exc:
        report.add_fail(f"Unexpected exception during test run: {exc}")

    finally:
        print("\nCleanup")
        if researcher_id:
            response = session.delete(
                build_url(base_url, f"/researchers/{researcher_id}"),
                timeout=15,
            )
            print(f"DELETE researcher -> {response.status_code}")
        if advisor_id:
            response = session.delete(
                build_url(base_url, f"/advisors/{advisor_id}"),
                timeout=15,
            )
            print(f"DELETE advisor -> {response.status_code}")
        session.close()

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Test researcher-advisor permission APIs.")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"FastAPI base URL, default: {DEFAULT_BASE_URL}",
    )
    args = parser.parse_args()

    report = run_test(args.base_url)

    print("\n=== Test Report ===")
    print(f"Passed: {len(report.passed)}")
    print(f"Failed: {len(report.failed)}")

    if report.passed:
        print("\nPassed steps:")
        for item in report.passed:
            print(f"- {item}")

    if report.failed:
        print("\nFailed steps:")
        for item in report.failed:
            print(f"- {item}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
