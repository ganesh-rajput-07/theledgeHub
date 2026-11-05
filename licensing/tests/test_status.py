from datetime import date

from app.models import Firm, Subscription
from app.services import firm_status

TODAY = date(2026, 11, 5)


def firm(ends_on=None, trial=False, blocked=False):
    f = Firm(name="F", email="f@example.com", reference="KH-1", blocked=blocked)
    f.subscription = (
        Subscription(ends_on=ends_on, is_trial=trial, computers_allowed=1, price_paise=0) if ends_on else None
    )
    return f


def test_statuses():
    assert firm_status(firm(), 0, TODAY).code == "pending"
    active = firm_status(firm(date(2026, 11, 7)), 0, TODAY)
    assert (active.code, active.days_left, active.can_use) == ("active", 3, True)
    assert firm_status(firm(TODAY), 0, TODAY).days_left == 1  # the end date itself is still usable
    assert firm_status(firm(date(2026, 11, 4)), 0, TODAY).code == "expired"
    assert firm_status(firm(date(2026, 11, 20), blocked=True), 0, TODAY).code == "blocked"
    assert firm_status(firm(date(2026, 11, 20), trial=True), 0, TODAY).code == "trial"


def test_grace_period_counts_days_after_expiry_and_skips_trials():
    assert firm_status(firm(date(2026, 11, 4)), 3, TODAY).code == "grace"
    assert firm_status(firm(date(2026, 11, 2)), 3, TODAY).code == "grace"  # 3rd day after expiry
    assert firm_status(firm(date(2026, 11, 1)), 3, TODAY).code == "expired"
    assert firm_status(firm(date(2026, 11, 4), trial=True), 3, TODAY).code == "expired"
    assert not firm_status(firm(date(2026, 11, 1)), 3, TODAY).can_use
