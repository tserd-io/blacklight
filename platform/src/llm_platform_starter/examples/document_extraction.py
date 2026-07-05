from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from llm_platform_starter.models import GuardrailOutcome


class ProjectAddress(BaseModel):
    street: str
    municipality: str
    country: str = "Pangea"


class MaterialLineItem(BaseModel):
    description: str
    quantity: int = Field(gt=0)
    unit: str
    unit_cost: Decimal = Field(ge=0)

    @property
    def line_total(self) -> Decimal:
        return self.unit_cost * self.quantity


class WorkOrderInvoice(BaseModel):
    invoice_id: str
    issuing_entity: str
    rfp_id: str
    work_order_id: str
    project_name: str
    project_addresses: list[ProjectAddress]
    material_line_items: list[MaterialLineItem]
    public_safe_note: str
    needs_review: bool = False

    @property
    def estimated_material_total(self) -> Decimal:
        return sum((item.line_total for item in self.material_line_items), Decimal("0"))


class ReviewQueueItem(BaseModel):
    item_id: str
    source_id: str
    outcome: GuardrailOutcome
    reason: str
    invoice: WorkOrderInvoice | None = None


class HumanReviewQueue:
    def __init__(self) -> None:
        self.accepted: list[WorkOrderInvoice] = []
        self.needs_review: list[ReviewQueueItem] = []
        self.rejected: list[ReviewQueueItem] = []

    def route(
        self,
        *,
        source_id: str,
        outcome: GuardrailOutcome,
        reason: str,
        invoice: WorkOrderInvoice | None = None,
    ) -> ReviewQueueItem | None:
        if outcome == GuardrailOutcome.accepted and invoice is not None:
            self.accepted.append(invoice)
            return None

        item = ReviewQueueItem(
            item_id=f"review-{len(self.needs_review) + len(self.rejected) + 1}",
            source_id=source_id,
            outcome=outcome,
            reason=reason,
            invoice=invoice,
        )
        if outcome == GuardrailOutcome.needs_review:
            self.needs_review.append(item)
        else:
            self.rejected.append(item)
        return item

    def report(self) -> dict[str, Any]:
        return {
            "accepted_count": len(self.accepted),
            "needs_review_count": len(self.needs_review),
            "rejected_count": len(self.rejected),
            "needs_review": [item.model_dump(mode="json") for item in self.needs_review],
            "rejected": [item.model_dump(mode="json") for item in self.rejected],
        }


def build_pangea_senior_housing_invoice(*, needs_review: bool = False) -> WorkOrderInvoice:
    return WorkOrderInvoice(
        invoice_id="INV-PAN-2026-014",
        issuing_entity="Pangea Ministry of Civic Housing",
        rfp_id="RFP-PAN-SENIOR-HOUSING-2026-04",
        work_order_id="WO-PAN-DIGNIFIED-SENIOR-HOMES-17",
        project_name="Dignified Senior Housing Materials Package",
        project_addresses=[
            ProjectAddress(street="12 Lumen Terrace", municipality="North Mariner Ward"),
            ProjectAddress(street="44 Orchard Signal Road", municipality="East Bellwether"),
            ProjectAddress(street="7 Kindling Court", municipality="South Aster Commons"),
        ],
        material_line_items=[
            MaterialLineItem(
                description="Accessible exterior door kits",
                quantity=18,
                unit="kit",
                unit_cost=Decimal("640.00"),
            ),
            MaterialLineItem(
                description="Non-slip flooring bundles",
                quantity=42,
                unit="bundle",
                unit_cost=Decimal("118.50"),
            ),
            MaterialLineItem(
                description="Bathroom grab bar sets",
                quantity=36,
                unit="set",
                unit_cost=Decimal("74.25"),
            ),
            MaterialLineItem(
                description="Low-flow fixture assemblies",
                quantity=24,
                unit="assembly",
                unit_cost=Decimal("132.00"),
            ),
            MaterialLineItem(
                description="Emergency call button units",
                quantity=30,
                unit="unit",
                unit_cost=Decimal("96.75"),
            ),
            MaterialLineItem(
                description="High-efficiency insulation panels",
                quantity=96,
                unit="panel",
                unit_cost=Decimal("41.20"),
            ),
        ],
        public_safe_note=(
            "Synthetic RFP/work-order example for the fictional country of Pangea; "
            "all addresses, identifiers, and entities are fake."
        ),
        needs_review=needs_review,
    )


def run_human_review_queue_example() -> dict[str, Any]:
    queue = HumanReviewQueue()
    accepted_invoice = build_pangea_senior_housing_invoice()
    review_invoice = build_pangea_senior_housing_invoice(needs_review=True)

    queue.route(
        source_id=accepted_invoice.work_order_id,
        outcome=GuardrailOutcome.accepted,
        reason="Invoice extraction passed schema and guardrail checks.",
        invoice=accepted_invoice,
    )
    queue.route(
        source_id=review_invoice.work_order_id,
        outcome=GuardrailOutcome.needs_review,
        reason="Senior housing procurement flagged for human review before approval.",
        invoice=review_invoice,
    )
    queue.route(
        source_id="WO-PAN-DIGNIFIED-SENIOR-HOMES-18",
        outcome=GuardrailOutcome.rejected,
        reason="Extraction was rejected because required material lines were missing.",
    )
    return {
        "scenario": "Synthetic Pangea senior housing RFP work-order invoice review",
        "accepted_invoice_total": str(accepted_invoice.estimated_material_total),
        "queue": queue.report(),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_human_review_queue_example(), indent=2))
