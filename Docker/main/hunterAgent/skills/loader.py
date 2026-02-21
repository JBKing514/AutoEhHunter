import importlib
import importlib.util
import sys
import types
from pathlib import Path

from hunterAgent.skills.registry import list_skills


def load_all_skills(plugin_dir: str) -> list[dict]:
    importlib.import_module("hunterAgent.skills.builtin")
    reg_mod = importlib.import_module("hunterAgent.skills.registry")
    skills_pkg = sys.modules.get("skills")
    if skills_pkg is None:
        skills_pkg = types.ModuleType("skills")
        sys.modules["skills"] = skills_pkg
    setattr(skills_pkg, "registry", reg_mod)
    sys.modules.setdefault("skills.registry", reg_mod)

    p = Path(plugin_dir)
    p.mkdir(parents=True, exist_ok=True)
    for f in sorted(p.glob("*.py")):
        if f.name.startswith("__"):
            continue
        mod_name = f"hunterAgent.user_plugins.{f.stem}"
        spec = importlib.util.spec_from_file_location(mod_name, str(f))
        if not spec or not spec.loader:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            continue
    return list_skills()
