"""Static checks for files that cannot run inside the Python test-suite (n8n templates, skill)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_n8n_templates_are_valid_workflows():
    templates = sorted((ROOT / "integrations" / "n8n" / "templates").glob("*.json"))
    assert len(templates) >= 2
    for path in templates:
        wf = json.loads(path.read_text(encoding="utf-8"))
        names = {n["name"] for n in wf["nodes"]}
        for source, outputs in wf["connections"].items():
            assert source in names
            for branch in outputs["main"]:
                for link in branch:
                    assert link["node"] in names
        text = path.read_text(encoding="utf-8").lower()
        assert "apikey" not in text and "bearer " not in text, "no secret may be stored in a template"


def test_skill_mentions_every_cli_command():
    skill = (ROOT / "skills" / "zahlbar" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: zahlbar")
    for command in ["zahlbar invoice create", "zahlbar invoice list", "zahlbar invoice bill",
                    "zahlbar reconcile", "zahlbar unmatched", "zahlbar config set-creditor"]:
        assert command in skill
