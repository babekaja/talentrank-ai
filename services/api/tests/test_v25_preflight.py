from pathlib import Path
import subprocess
from scripts.model_preflight_v25 import check


def test_pretrained_model_gate_closed_without_weights(tmp_path):
    res=check(tmp_path)
    assert res['deployment_enabled'] is False
    assert res['pretrained_neural_inference_executed'] is False
    assert not res['ready_for_real_model_benchmark']


def test_docker_preflight_fails_closed_without_cli(monkeypatch):
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
    import check_stack_v25
    monkeypatch.setattr(check_stack_v25.shutil,'which',lambda _:None)
    res=check_stack_v25.diagnose()
    assert res['blocker']=='DOCKER_CLI_NOT_INSTALLED'
    assert not res['production_approved']
