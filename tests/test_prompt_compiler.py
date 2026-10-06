from pathlib import Path
from mvstudio.models import MusicVideoProject
from mvstudio.prompt_compiler import compile_shot
from mvstudio.qc import evaluate_project

ROOT = Path(__file__).resolve().parents[1]

def load_example():
    return MusicVideoProject.model_validate_json(
        (ROOT / "examples" / "project.example.json").read_text(encoding="utf-8")
    )

def test_example_valid():
    project = load_example()
    assert len(project.shots) == 3
    assert project.shots[0].duration_sec == 6.0

def test_runway_prompt_is_motion_forward():
    project = load_example()
    pack = compile_shot(project, project.shots[0], "runway")
    assert "Camera" in pack.prompt
    assert "Preserve" in pack.prompt
    assert pack.references

def test_qc_score():
    project = load_example()
    qc = evaluate_project(project)
    assert qc.score >= 70
