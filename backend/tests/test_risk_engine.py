"""The rules engine.

Pure functions over in-memory objects, so these are fast and exact. Each rule is
tested both ways: that it fires on the condition it describes, and that it stays
quiet otherwise. A signal that fires on everything is worse than no signal.
"""

import datetime
import uuid

import pytest

from models import AdjudicationStatus, RiskBand, SignalDirection
from services import risk


class FakeFinding:
    def __init__(self, status, chunk_id=None):
        self.status = status
        self.chunk_id = chunk_id


class FakeItem:
    def __init__(
        self, description, amount, *, category="Other", service_date=None,
        unit_price=None, quantity=None, finding=None,
    ):
        self.id = uuid.uuid4()
        self.description = description
        self.billed_amount = amount
        self.category = category
        self.service_date = service_date
        self.unit_price = unit_price
        self.quantity = quantity
        self.audit_finding = finding


class FakeClaim:
    def __init__(self, total=0.0, admission=None, discharge=None):
        self.id = uuid.uuid4()
        self.total_billed = total
        self.admission_date = admission
        self.discharge_date = discharge


class FakePolicy:
    def __init__(self, room_rent_cap=None, sum_insured=None):
        self.room_rent_cap = room_rent_cap
        self.sum_insured = sum_insured


class FakeFact:
    def __init__(self, located=True):
        self.extra = {"located": located}


def codes(signals) -> set[str]:
    return {s.code for s in signals}


# --- duplicates ------------------------------------------------------------

def test_duplicate_line_fires_on_identical_charges():
    day = datetime.date(2026, 7, 4)
    items = [
        FakeItem("MRI lumbar spine", 18500.0, service_date=day),
        FakeItem("MRI lumbar spine", 18500.0, service_date=day),
    ]
    signals = risk._duplicates(items)

    assert len(signals) == 1
    assert signals[0].code == "DUPLICATE_LINE_ITEM"
    assert signals[0].evidence_refs["occurrences"] == 2
    assert len(signals[0].evidence_refs["claim_item_ids"]) == 2


def test_duplicate_ignores_same_service_on_different_dates():
    """Two dressings on consecutive days are not a duplicate."""
    items = [
        FakeItem("Dressing change", 500.0, service_date=datetime.date(2026, 7, 4)),
        FakeItem("Dressing change", 500.0, service_date=datetime.date(2026, 7, 5)),
    ]
    assert risk._duplicates(items) == []


def test_duplicate_ignores_same_description_at_different_amounts():
    items = [
        FakeItem("Consultation", 500.0),
        FakeItem("Consultation", 900.0),
    ]
    assert risk._duplicates(items) == []


# --- room rent -------------------------------------------------------------

def test_room_rent_breach_uses_the_unit_price():
    items = [FakeItem("Private room", 45000.0, category="Room Rent", unit_price=9000.0)]
    signals = risk._room_rent(items, FakePolicy(room_rent_cap=5000.0))

    assert codes(signals) == {"ROOM_RENT_CAP_BREACH"}
    assert signals[0].evidence_refs["billed_per_day"] == 9000.0


def test_room_rent_derives_per_day_from_quantity():
    items = [FakeItem("Room, 5 days", 45000.0, category="Room Rent", quantity=5)]
    signals = risk._room_rent(items, FakePolicy(room_rent_cap=5000.0))
    assert codes(signals) == {"ROOM_RENT_CAP_BREACH"}


def test_room_rent_within_the_cap_is_silent():
    items = [FakeItem("Shared room", 13500.0, category="Room Rent", unit_price=4500.0)]
    assert risk._room_rent(items, FakePolicy(room_rent_cap=5000.0)) == []


def test_room_rent_needs_a_policy_cap_to_judge():
    """Without a stated limit there is nothing to breach."""
    items = [FakeItem("Suite", 90000.0, category="Room Rent", unit_price=30000.0)]
    assert risk._room_rent(items, FakePolicy(room_rent_cap=None)) == []
    assert risk._room_rent(items, None) == []


# --- dates -----------------------------------------------------------------

def test_service_outside_the_stay_fires():
    claim = FakeClaim(
        admission=datetime.date(2026, 7, 12), discharge=datetime.date(2026, 7, 15)
    )
    items = [FakeItem("Physiotherapy", 900.0, service_date=datetime.date(2026, 7, 20))]
    signals = risk._service_dates(claim, items)
    assert codes(signals) == {"SERVICE_DATE_OUTSIDE_STAY"}


def test_service_inside_the_stay_is_silent():
    claim = FakeClaim(
        admission=datetime.date(2026, 7, 12), discharge=datetime.date(2026, 7, 15)
    )
    items = [FakeItem("Physiotherapy", 900.0, service_date=datetime.date(2026, 7, 13))]
    assert risk._service_dates(claim, items) == []


def test_no_stay_dates_means_no_judgement():
    items = [FakeItem("Physiotherapy", 900.0, service_date=datetime.date(2026, 7, 20))]
    assert risk._service_dates(FakeClaim(), items) == []


# --- adjudication ----------------------------------------------------------

def test_rejections_and_caps_produce_signals():
    items = [
        FakeItem("Gloves", 3100.0, finding=FakeFinding(AdjudicationStatus.REJECTED)),
        FakeItem("Room", 45000.0, finding=FakeFinding(AdjudicationStatus.CAPPED)),
        FakeItem("Ambulance", 4500.0, finding=FakeFinding(AdjudicationStatus.NEEDS_REVIEW)),
    ]
    assert codes(risk._adjudication(items)) == {
        "EXCLUDED_ITEM_BILLED", "CAPPED_ITEM", "UNADJUDICATED_ITEM"
    }


def test_full_citation_coverage_is_mitigating():
    items = [
        FakeItem("A", 1.0, finding=FakeFinding(AdjudicationStatus.APPROVED, chunk_id=uuid.uuid4())),
        FakeItem("B", 2.0, finding=FakeFinding(AdjudicationStatus.APPROVED, chunk_id=uuid.uuid4())),
    ]
    signals = risk._adjudication(items)
    assert codes(signals) == {"EVERY_ITEM_CITES_A_CLAUSE"}
    assert signals[0].direction is SignalDirection.MITIGATING
    assert signals[0].weight < 0


def test_partial_citation_coverage_earns_no_credit():
    items = [
        FakeItem("A", 1.0, finding=FakeFinding(AdjudicationStatus.APPROVED, chunk_id=uuid.uuid4())),
        FakeItem("B", 2.0, finding=FakeFinding(AdjudicationStatus.APPROVED)),
    ]
    assert "EVERY_ITEM_CITES_A_CLAUSE" not in codes(risk._adjudication(items))


def test_unadjudicated_claim_produces_no_adjudication_signals():
    assert risk._adjudication([FakeItem("A", 1.0)]) == []


# --- totals ----------------------------------------------------------------

def test_total_mismatch_fires():
    claim = FakeClaim(total=100000.0)
    items = [FakeItem("A", 40000.0), FakeItem("B", 40000.0)]
    assert "TOTAL_MISMATCH" in codes(risk._totals(claim, items, None))


def test_rounding_slack_is_tolerated():
    claim = FakeClaim(total=80000.5)
    items = [FakeItem("A", 40000.0), FakeItem("B", 40000.0)]
    assert "TOTAL_MISMATCH" not in codes(risk._totals(claim, items, None))


def test_concentration_fires_when_one_line_dominates():
    claim = FakeClaim(total=100000.0)
    items = [FakeItem("Surgery", 90000.0), FakeItem("Pharmacy", 10000.0)]
    signals = risk._totals(claim, items, None)
    concentration = next(s for s in signals if s.code == "CHARGE_CONCENTRATION")
    assert concentration.evidence_refs["share"] == pytest.approx(0.9)


def test_balanced_bill_has_no_concentration_signal():
    claim = FakeClaim(total=100000.0)
    items = [FakeItem("A", 30000.0), FakeItem("B", 35000.0), FakeItem("C", 35000.0)]
    assert "CHARGE_CONCENTRATION" not in codes(risk._totals(claim, items, None))


def test_sum_insured_breach_and_headroom_are_opposite_signals():
    claim = FakeClaim(total=600000.0)
    over = risk._totals(claim, [FakeItem("Big", 600000.0)], FakePolicy(sum_insured=500000.0))
    under = risk._totals(claim, [FakeItem("Small", 50000.0)], FakePolicy(sum_insured=500000.0))

    assert "EXCEEDS_SUM_INSURED" in codes(over)
    assert "WITHIN_SUM_INSURED" in codes(under)
    assert "EXCEEDS_SUM_INSURED" not in codes(under)


# --- evidence quality ------------------------------------------------------

def test_unlocated_values_are_flagged():
    signals = risk._evidence_quality([FakeFact(True), FakeFact(False)])
    assert codes(signals) == {"UNLOCATED_VALUES"}
    assert signals[0].evidence_refs == {"unlocated": 1, "total": 2}


def test_fully_located_evidence_is_mitigating():
    signals = risk._evidence_quality([FakeFact(True), FakeFact(True)])
    assert codes(signals) == {"ALL_VALUES_LOCATED"}
    assert signals[0].weight < 0


def test_no_facts_means_no_evidence_signal():
    assert risk._evidence_quality([]) == []


# --- scoring ---------------------------------------------------------------

def test_score_is_the_sum_of_contributions():
    signals = [
        risk._signal("DUPLICATE_LINE_ITEM", "t", "d"),
        risk._signal("CAPPED_ITEM", "t", "d"),
    ]
    total, band, _ = risk.score(signals)
    assert total == pytest.approx(26.0 + 8.0)
    assert band is RiskBand.MEDIUM


def test_mitigating_signals_reduce_the_score():
    aggravating = risk.score([risk._signal("DUPLICATE_LINE_ITEM", "t", "d")])[0]
    with_credit = risk.score([
        risk._signal("DUPLICATE_LINE_ITEM", "t", "d"),
        risk._signal("ALL_VALUES_LOCATED", "t", "d"),
    ])[0]
    assert with_credit < aggravating


def test_one_rule_cannot_saturate_the_score():
    """Ten duplicates is bad, but should not alone reach maximum risk."""
    signals = [risk._signal("DUPLICATE_LINE_ITEM", "t", "d") for _ in range(10)]
    total, _, _ = risk.score(signals)
    assert total == pytest.approx(risk.MAX_CONTRIBUTION_PER_RULE)


def test_score_is_clamped_to_the_range():
    many = [
        risk._signal(code, "t", "d")
        for code in ("DUPLICATE_LINE_ITEM", "ROOM_RENT_CAP_BREACH",
                     "SERVICE_DATE_OUTSIDE_STAY", "EXCLUDED_ITEM_BILLED",
                     "TOTAL_MISMATCH", "EXCEEDS_SUM_INSURED")
    ] * 3
    total, band, _ = risk.score(many)
    assert 0.0 <= total <= 100.0
    assert band is RiskBand.CRITICAL


def test_a_clean_claim_scores_zero_and_bands_low():
    total, band, _ = risk.score([
        risk._signal("ALL_VALUES_LOCATED", "t", "d"),
        risk._signal("WITHIN_SUM_INSURED", "t", "d"),
    ])
    assert total == 0.0
    assert band is RiskBand.LOW


def test_no_signals_scores_zero():
    total, band, breakdown = risk.score([])
    assert (total, band, breakdown) == (0.0, RiskBand.LOW, [])


def test_breakdown_is_ordered_by_magnitude():
    _, _, breakdown = risk.score([
        risk._signal("CAPPED_ITEM", "small", "d"),
        risk._signal("DUPLICATE_LINE_ITEM", "large", "d"),
    ])
    assert [row["title"] for row in breakdown] == ["large", "small"]


def test_every_weight_has_a_consistent_direction():
    """A positive weight must never be labelled mitigating, or vice versa."""
    for code, value in risk.WEIGHTS.items():
        weight, direction = risk._weight(code)
        expected = SignalDirection.AGGRAVATING if value > 0 else SignalDirection.MITIGATING
        assert direction is expected, code


# --- end to end over the rule set ------------------------------------------

def test_a_problematic_claim_scores_higher_than_a_clean_one():
    day = datetime.date(2026, 7, 4)
    policy = FakePolicy(room_rent_cap=5000.0, sum_insured=500000.0)

    clean_claim = FakeClaim(total=13500.0)
    clean_items = [
        FakeItem("Shared room", 13500.0, category="Room Rent", unit_price=4500.0,
                 finding=FakeFinding(AdjudicationStatus.APPROVED, chunk_id=uuid.uuid4())),
    ]
    clean = risk.score(risk.evaluate(clean_claim, clean_items, [FakeFact(True)], policy))[0]

    bad_claim = FakeClaim(total=99000.0)
    bad_items = [
        FakeItem("MRI", 18500.0, service_date=day),
        FakeItem("MRI", 18500.0, service_date=day),
        FakeItem("Private room", 45000.0, category="Room Rent", unit_price=9000.0,
                 finding=FakeFinding(AdjudicationStatus.REJECTED)),
    ]
    bad = risk.score(risk.evaluate(bad_claim, bad_items, [FakeFact(False)], policy))[0]

    assert bad > clean
    assert clean == 0.0
