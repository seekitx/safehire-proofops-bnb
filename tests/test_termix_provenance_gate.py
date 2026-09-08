from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app
from proofops.services.submission import SubmissionValidator
from proofops.settings import Settings


def test_archived_report_never_passes_current_human_control_gate():
    gate = SubmissionValidator(registry=None, scorer=None, ledger=None, project_root=Path('.'), settings=Settings())
    result = gate._check_termix()
    assert not result.passed and result.severity == 'P1'


def test_public_report_keeps_originals_and_surfaces_provenance_hold():
    with TestClient(app) as client:
        result = client.get('/api/evidence/termix/report').json()
        assert result['report_role'] == 'archived_automated_baseline'
        assert result['eligibility_supported_by_this_report'] is False
        assert result['provenance_review']['hold_eligibility_claims'] is True
        assert len(result['tasks']) == 3
