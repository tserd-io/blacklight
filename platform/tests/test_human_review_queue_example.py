from decimal import Decimal

from blacklight.examples.document_extraction import (
    HumanReviewQueue,
    build_pangea_senior_housing_invoice,
    run_human_review_queue_example,
)
from blacklight.models import GuardrailOutcome


def test_pangea_work_order_invoice_is_public_safe_and_materialized():
    invoice = build_pangea_senior_housing_invoice()

    assert invoice.issuing_entity == "Pangea Ministry of Civic Housing"
    assert invoice.rfp_id == "RFP-PAN-SENIOR-HOUSING-2026-04"
    assert invoice.work_order_id == "WO-PAN-DIGNIFIED-SENIOR-HOMES-17"
    assert {address.country for address in invoice.project_addresses} == {"Pangea"}
    assert len(invoice.project_addresses) == 3
    assert len(invoice.material_line_items) == 6
    assert invoice.estimated_material_total == Decimal("29195.70")
    assert "fictional country of Pangea" in invoice.public_safe_note


def test_human_review_queue_routes_guardrail_outcomes():
    queue = HumanReviewQueue()
    accepted_invoice = build_pangea_senior_housing_invoice()
    review_invoice = build_pangea_senior_housing_invoice(needs_review=True)

    accepted_item = queue.route(
        source_id=accepted_invoice.work_order_id,
        outcome=GuardrailOutcome.accepted,
        reason="Accepted.",
        invoice=accepted_invoice,
    )
    review_item = queue.route(
        source_id=review_invoice.work_order_id,
        outcome=GuardrailOutcome.needs_review,
        reason="Needs procurement review.",
        invoice=review_invoice,
    )
    rejected_item = queue.route(
        source_id="WO-PAN-DIGNIFIED-SENIOR-HOMES-18",
        outcome=GuardrailOutcome.rejected,
        reason="Missing material lines.",
    )

    assert accepted_item is None
    assert len(queue.accepted) == 1
    assert review_item is not None
    assert review_item.outcome == GuardrailOutcome.needs_review
    assert rejected_item is not None
    assert rejected_item.outcome == GuardrailOutcome.rejected
    assert queue.report()["needs_review_count"] == 1
    assert queue.report()["rejected_count"] == 1


def test_human_review_queue_example_report_shows_needs_review_items():
    report = run_human_review_queue_example()

    assert report["scenario"] == "Synthetic Pangea senior housing RFP work-order invoice review"
    assert report["accepted_invoice_total"] == "29195.70"
    assert report["queue"]["accepted_count"] == 1
    assert report["queue"]["needs_review_count"] == 1
    assert report["queue"]["rejected_count"] == 1
    assert report["queue"]["needs_review"][0]["outcome"] == "needs_review"
    assert report["queue"]["needs_review"][0]["invoice"]["project_addresses"][0]["country"] == "Pangea"
    assert report["queue"]["rejected"][0]["outcome"] == "rejected"
