import pytest
from app.models.domain import Organization, Project, User
from app.models.db import DBOrganization, DBProject, DBUser
from app.core.session_manager import SessionManager
from app.core.token_budget import (
    TokenBudgetManager,
    TokenBudgetExceededError,
    BudgetConfig,
    BudgetCheckResult,
    token_budget_manager
)


@pytest.fixture
def fresh_budget_manager():
    manager = TokenBudgetManager()
    yield manager
    manager.reset_all_usage()


def test_domain_and_db_models():
    org = Organization(slug="acme-corp", display_name="ACME Corp")
    assert org.org_id.startswith("org-")
    assert org.status == "active"

    project = Project(org_id=org.org_id, slug="backend", display_name="Backend System")
    assert project.project_id.startswith("proj-")
    assert project.org_id == org.org_id

    user = User(org_id=org.org_id, email="dev@acme.com", full_name="Jane Doe")
    assert user.user_id.startswith("usr-")
    assert user.roles == ["developer"]

    db_org = DBOrganization(
        org_id=org.org_id,
        slug=org.slug,
        display_name=org.display_name,
        status=org.status
    )
    assert db_org.org_id == org.org_id


def test_session_manager_tenant_binding(tmp_path):
    sm = SessionManager(sessions_dir=tmp_path)
    session_id = sm.create(
        cwd=str(tmp_path),
        org_id="org-acme",
        project_id="proj-web",
        user_id="usr-alice"
    )

    meta = sm.open(session_id)
    assert meta.session_id == session_id
    assert meta.org_id == "org-acme"
    assert meta.project_id == "proj-web"
    assert meta.user_id == "usr-alice"


def test_hierarchical_budget_setting_and_getting(fresh_budget_manager):
    mgr = fresh_budget_manager
    cfg = mgr.set_budget(
        scope="organization",
        scope_id="org-123",
        max_tokens=100000,
        warning_threshold_ratio=0.80
    )

    assert cfg.scope == "organization"
    assert cfg.max_tokens == 100000

    fetched = mgr.get_budget("organization", "org-123")
    assert fetched is not None
    assert fetched.max_tokens == 100000

    mgr.remove_budget("organization", "org-123")
    assert mgr.get_budget("organization", "org-123") is None


def test_hierarchical_usage_aggregation_and_org_budget_enforcement(fresh_budget_manager):
    mgr = fresh_budget_manager

    # Define Organization budget limit of 100,000 tokens
    mgr.set_budget("organization", "org-acme", max_tokens=100000, warning_threshold_ratio=0.80)

    # Define User budget limit of 60,000 tokens for User Alice (80% threshold = 48,000)
    mgr.set_budget("user", "usr-alice", max_tokens=60000, warning_threshold_ratio=0.80)

    org_id = "org-acme"

    # User Alice in Session 1 consumes 40,000 tokens
    mgr.record_usage(
        session_id="sess-1",
        tokens_consumed=40000,
        user_id="usr-alice",
        project_id="proj-1",
        org_id=org_id
    )

    # Check budget for Alice's session with additional 5,000 tokens (45,000 < 48,000 threshold)
    res = mgr.check_budget("sess-1", additional_tokens=5000, user_id="usr-alice", org_id=org_id)
    assert not res.is_warning
    assert not res.is_blocked

    # User Alice in Session 1 consumes another 15,000 tokens (Alice total: 55,000 / 60,000 -> 91.6% warning)
    mgr.record_usage(
        session_id="sess-1",
        tokens_consumed=15000,
        user_id="usr-alice",
        project_id="proj-1",
        org_id=org_id
    )

    res_alice = mgr.check_budget("sess-1", user_id="usr-alice", org_id=org_id)
    assert res_alice.is_warning
    assert "user:usr-alice" in res_alice.warning_scopes
    assert not res_alice.is_blocked

    # User Bob in Session 2 consumes 35,000 tokens
    # Total Organization usage = 55,000 (Alice) + 35,000 (Bob) = 90,000 tokens (Org limit: 100,000)
    mgr.record_usage(
        session_id="sess-2",
        tokens_consumed=35000,
        user_id="usr-bob",
        project_id="proj-1",
        org_id=org_id
    )

    assert mgr.get_usage("organization", org_id) == 90000
    assert mgr.get_usage("user", "usr-alice") == 55000
    assert mgr.get_usage("user", "usr-bob") == 35000

    # Check Organization status: usage is 90,000 / 100,000 -> warning active
    res_org = mgr.check_budget("sess-2", user_id="usr-bob", org_id=org_id)
    assert res_org.is_warning
    assert "organization:org-acme" in res_org.warning_scopes
    assert not res_org.is_blocked

    # User Bob attempts a request of 15,000 tokens (candidate Org total: 105,000 > 100,000 limit)
    res_candidate = mgr.check_budget(
        session_id="sess-2",
        additional_tokens=15000,
        user_id="usr-bob",
        org_id=org_id
    )
    assert res_candidate.is_blocked
    assert res_candidate.exceeded_scope == "organization"
    assert res_candidate.exceeded_scope_id == org_id

    # Verify raise_on_block=True raises TokenBudgetExceededError specifying Organization level
    with pytest.raises(TokenBudgetExceededError) as exc_info:
        mgr.check_budget(
            session_id="sess-2",
            additional_tokens=15000,
            user_id="usr-bob",
            org_id=org_id,
            raise_on_block=True
        )

    err = exc_info.value
    assert err.scope == "organization"
    assert err.scope_id == "org-acme"
    assert err.max_tokens == 100000
    assert err.current_usage == 90000
    assert err.requested_tokens == 15000


def test_project_and_session_level_blocking(fresh_budget_manager):
    mgr = fresh_budget_manager

    mgr.set_budget("project", "proj-alpha", max_tokens=20000)
    mgr.set_budget("session", "sess-10", max_tokens=10000)

    mgr.record_usage(session_id="sess-10", tokens_consumed=8000, project_id="proj-alpha")

    # Session limit test: requesting 3000 tokens brings session to 11,000 > 10,000
    res_sess = mgr.check_budget(session_id="sess-10", additional_tokens=3000, project_id="proj-alpha")
    assert res_sess.is_blocked
    assert res_sess.exceeded_scope == "session"

    # Reset usage and test project limit
    mgr.reset_all_usage()
    mgr.record_usage(session_id="sess-10", tokens_consumed=18000, project_id="proj-alpha")
    mgr.record_usage(session_id="sess-11", tokens_consumed=3000, project_id="proj-alpha")

    res_proj = mgr.check_budget(session_id="sess-11", project_id="proj-alpha")
    assert res_proj.is_blocked
    assert res_proj.exceeded_scope == "project"
    assert res_proj.exceeded_scope_id == "proj-alpha"
