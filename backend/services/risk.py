"""The risk engine.

Every signal here is computed from data already in the claim — line items,
adjudication findings, extracted facts, the policy. Nothing is estimated and
nothing is written by hand.

**On the weights.** The weights are chosen, not learned. That is what a rules
engine is: a stated policy about how much each observation matters, reviewable
and arguable by the people who own the decision. They are declared in one table
below and stamped onto every score, so a score can always be reproduced and a
disagreement is about the policy rather than about a black box. When P11 trains a
model, its output will sit alongside these — labelled as a model estimate — not
quietly replace them.

What is genuinely computed:
  * which rules fired, and on which items
  * the evidence each firing rests on
  * the aggregate score and band

What is a stated policy:
  * the weight attached to each rule
  * the score thresholds between bands
"""

import datetime
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from models import (
    AdjudicationStatus,
    Claim,
    ClaimItem,
    ExtractedFact,
    Policy,
    RiskBand,
    SignalDirection,
)

# Version the weights so a stored score records the policy that produced it.
# Changing any weight below means bumping this.
WEIGHTS_VERSION = "rules-v1"

# Aggravating weights are positive, mitigating negative. Sized relative to each
# other: a duplicated charge is the strongest single indicator of a billing
# problem, while an unlocated value is a data-quality caveat rather than
# evidence of anything wrong.
WEIGHTS = {
    "DUPLICATE_LINE_ITEM": 26.0,
    "ROOM_RENT_CAP_BREACH": 18.0,
    "SERVICE_DATE_OUTSIDE_STAY": 16.0,
    "EXCLUDED_ITEM_BILLED": 14.0,
    "TOTAL_MISMATCH": 12.0,
    "CHARGE_CONCENTRATION": 9.0,
    "CAPPED_ITEM": 8.0,
    "UNADJUDICATED_ITEM": 6.0,
    "UNLOCATED_VALUES": 10.0,
    "EXCEEDS_SUM_INSURED": 20.0,
    # Mitigating
    "ALL_VALUES_LOCATED": -8.0,
    "EVERY_ITEM_CITES_A_CLAUSE": -7.0,
    "WITHIN_SUM_INSURED": -5.0,
}

BAND_THRESHOLDS = [(75.0, RiskBand.CRITICAL), (50.0, RiskBand.HIGH), (25.0, RiskBand.MEDIUM)]

# A single rule firing many times should not dominate the score on its own.
MAX_CONTRIBUTION_PER_RULE = 30.0

# Share of the bill above which one line is worth flagging for attention.
CONCENTRATION_THRESHOLD = 0.6

# Rupees of slack allowed between the stated total and the sum of the lines,
# to absorb rounding rather than flag it.
TOTAL_TOLERANCE = 1.0


@dataclass
class Signal:
    code: str
    title: str
    detail: str
    direction: SignalDirection
    weight: float
    claim_item_id: uuid.UUID | None = None
    evidence_refs: dict = field(default_factory=dict)


def _weight(code: str) -> tuple[float, SignalDirection]:
    value = WEIGHTS[code]
    direction = SignalDirection.AGGRAVATING if value > 0 else SignalDirection.MITIGATING
    return value, direction


def _signal(code: str, title: str, detail: str, **extra) -> Signal:
    value, direction = _weight(code)
    return Signal(code=code, title=title, detail=detail, direction=direction, weight=value, **extra)


def _duplicates(items: list[ClaimItem]) -> list[Signal]:
    """The same service billed more than once on the same date.

    Keyed on description, amount and service date together. Two genuinely
    separate dressings on the same day would share a description but usually
    differ in amount; requiring all three to match keeps this specific.
    """
    groups: dict[tuple, list[ClaimItem]] = defaultdict(list)
    for item in items:
        groups[(item.description.strip().casefold(), item.billed_amount, item.service_date)].append(item)

    signals = []
    for (description, amount, service_date), group in groups.items():
        if len(group) < 2:
            continue
        when = f" on {service_date.isoformat()}" if service_date else ""
        signals.append(
            _signal(
                "DUPLICATE_LINE_ITEM",
                "Same charge billed more than once",
                f"'{group[0].description}' appears {len(group)} times at "
                f"{amount:,.0f}{when}.",
                claim_item_id=group[0].id,
                evidence_refs={
                    "claim_item_ids": [str(i.id) for i in group],
                    "occurrences": len(group),
                    "amount": amount,
                },
            )
        )
    return signals


def _room_rent(items: list[ClaimItem], policy: Policy | None) -> list[Signal]:
    """Room charges above the policy's per-day limit."""
    if policy is None or not policy.room_rent_cap:
        return []

    signals = []
    for item in items:
        if "room" not in item.category.casefold():
            continue

        per_day = item.unit_price
        if per_day is None and item.quantity:
            per_day = item.billed_amount / item.quantity
        if per_day is None or per_day <= policy.room_rent_cap:
            continue

        excess = per_day - policy.room_rent_cap
        signals.append(
            _signal(
                "ROOM_RENT_CAP_BREACH",
                "Room rate exceeds the policy limit",
                f"Billed {per_day:,.0f} per day against an eligible "
                f"{policy.room_rent_cap:,.0f}; excess of {excess:,.0f} per day.",
                claim_item_id=item.id,
                evidence_refs={
                    "claim_item_id": str(item.id),
                    "billed_per_day": per_day,
                    "policy_cap": policy.room_rent_cap,
                },
            )
        )
    return signals


def _service_dates(claim: Claim, items: list[ClaimItem]) -> list[Signal]:
    """Services dated outside the admission window."""
    if not claim.admission_date or not claim.discharge_date:
        return []

    outside = [
        item for item in items
        if item.service_date
        and not (claim.admission_date <= item.service_date <= claim.discharge_date)
    ]
    if not outside:
        return []

    return [
        _signal(
            "SERVICE_DATE_OUTSIDE_STAY",
            "Service dated outside the hospital stay",
            f"{len(outside)} line(s) dated outside "
            f"{claim.admission_date.isoformat()} to {claim.discharge_date.isoformat()}.",
            claim_item_id=outside[0].id,
            evidence_refs={
                "claim_item_ids": [str(i.id) for i in outside],
                "admission": claim.admission_date.isoformat(),
                "discharge": claim.discharge_date.isoformat(),
            },
        )
    ]


def _adjudication(items: list[ClaimItem]) -> list[Signal]:
    """Signals derived from what the adjudicator actually decided."""
    signals: list[Signal] = []
    outcomes = Counter()
    cited = 0

    for item in items:
        finding = item.audit_finding
        if finding is None:
            continue
        outcomes[finding.status] += 1
        if finding.chunk_id is not None:
            cited += 1

    rejected = outcomes[AdjudicationStatus.REJECTED]
    if rejected:
        signals.append(
            _signal(
                "EXCLUDED_ITEM_BILLED",
                "Charges billed that the policy excludes",
                f"{rejected} line(s) were rejected against a cited policy clause.",
                evidence_refs={"rejected_count": rejected},
            )
        )

    capped = outcomes[AdjudicationStatus.CAPPED]
    if capped:
        signals.append(
            _signal(
                "CAPPED_ITEM",
                "Charges above a policy sub-limit",
                f"{capped} line(s) exceed a limit and are only partly payable.",
                evidence_refs={"capped_count": capped},
            )
        )

    unresolved = outcomes[AdjudicationStatus.NEEDS_REVIEW]
    if unresolved:
        signals.append(
            _signal(
                "UNADJUDICATED_ITEM",
                "Charges the policy does not settle",
                f"{unresolved} line(s) need a human decision because no clause "
                "addresses them.",
                evidence_refs={"needs_review_count": unresolved},
            )
        )

    adjudicated = sum(outcomes.values())
    if adjudicated and cited == adjudicated:
        signals.append(
            _signal(
                "EVERY_ITEM_CITES_A_CLAUSE",
                "Every verdict rests on a retrieved clause",
                f"All {adjudicated} adjudicated line(s) cite a passage from the policy.",
                evidence_refs={"adjudicated": adjudicated},
            )
        )

    return signals


def _totals(claim: Claim, items: list[ClaimItem], policy: Policy | None) -> list[Signal]:
    signals: list[Signal] = []
    line_sum = sum(item.billed_amount for item in items)

    if items and claim.total_billed and abs(line_sum - claim.total_billed) > TOTAL_TOLERANCE:
        signals.append(
            _signal(
                "TOTAL_MISMATCH",
                "Stated total does not match the lines",
                f"Lines add to {line_sum:,.0f} but the bill states "
                f"{claim.total_billed:,.0f}.",
                evidence_refs={"line_sum": line_sum, "stated_total": claim.total_billed},
            )
        )

    if items and line_sum > 0:
        largest = max(items, key=lambda i: i.billed_amount)
        share = largest.billed_amount / line_sum
        if share >= CONCENTRATION_THRESHOLD:
            signals.append(
                _signal(
                    "CHARGE_CONCENTRATION",
                    "One charge dominates the bill",
                    f"'{largest.description}' is {share:.0%} of the billed total.",
                    claim_item_id=largest.id,
                    evidence_refs={"claim_item_id": str(largest.id), "share": round(share, 3)},
                )
            )

    if policy is not None and policy.sum_insured:
        if line_sum > policy.sum_insured:
            signals.append(
                _signal(
                    "EXCEEDS_SUM_INSURED",
                    "Claim exceeds the sum insured",
                    f"Billed {line_sum:,.0f} against a sum insured of "
                    f"{policy.sum_insured:,.0f}.",
                    evidence_refs={"line_sum": line_sum, "sum_insured": policy.sum_insured},
                )
            )
        elif items:
            signals.append(
                _signal(
                    "WITHIN_SUM_INSURED",
                    "Claim is within the sum insured",
                    f"Billed {line_sum:,.0f} of {policy.sum_insured:,.0f} available.",
                    evidence_refs={"line_sum": line_sum, "sum_insured": policy.sum_insured},
                )
            )

    return signals


def _evidence_quality(facts: list[ExtractedFact]) -> list[Signal]:
    """How much of the bill could be tied back to the page.

    A data-quality observation, not an accusation: values the pipeline could not
    locate are ones a reviewer should check by eye.
    """
    if not facts:
        return []

    unlocated = [f for f in facts if not (f.extra or {}).get("located")]

    if unlocated:
        return [
            _signal(
                "UNLOCATED_VALUES",
                "Some values could not be found on the page",
                f"{len(unlocated)} of {len(facts)} extracted values could not be "
                "located in the document and should be checked against the source.",
                evidence_refs={"unlocated": len(unlocated), "total": len(facts)},
            )
        ]

    return [
        _signal(
            "ALL_VALUES_LOCATED",
            "Every extracted value was found on the page",
            f"All {len(facts)} values trace to a region of the source document.",
            evidence_refs={"total": len(facts)},
        )
    ]


def evaluate(
    claim: Claim,
    items: list[ClaimItem],
    facts: list[ExtractedFact],
    policy: Policy | None,
) -> list[Signal]:
    """Run every rule and return the ones that fired."""
    signals: list[Signal] = []
    signals += _duplicates(items)
    signals += _room_rent(items, policy)
    signals += _service_dates(claim, items)
    signals += _adjudication(items)
    signals += _totals(claim, items, policy)
    signals += _evidence_quality(facts)
    return signals


def score(signals: list[Signal]) -> tuple[float, RiskBand, list[dict]]:
    """Aggregate fired signals into a score, band and breakdown.

    Each rule's total contribution is capped so that one rule firing repeatedly
    cannot saturate the score by itself, and the result is clamped to 0-100. The
    breakdown is frozen into the stored score so an analyst sees the same
    decomposition later even if the weights are retuned.
    """
    per_rule: dict[str, float] = defaultdict(float)
    for signal in signals:
        per_rule[signal.code] += signal.weight

    total = 0.0
    for code, contribution in per_rule.items():
        if contribution > 0:
            contribution = min(contribution, MAX_CONTRIBUTION_PER_RULE)
        else:
            contribution = max(contribution, -MAX_CONTRIBUTION_PER_RULE)
        total += contribution

    bounded = max(0.0, min(100.0, total))

    band = RiskBand.LOW
    for threshold, candidate in BAND_THRESHOLDS:
        if bounded >= threshold:
            band = candidate
            break

    breakdown = [
        {
            "code": signal.code,
            "title": signal.title,
            "weight": signal.weight,
            "direction": signal.direction.value,
        }
        for signal in sorted(signals, key=lambda s: abs(s.weight), reverse=True)
    ]

    return bounded, band, breakdown
