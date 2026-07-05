from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from string import Template


@dataclass(frozen=True)
class PromptTemplate:
    prompt_id: str
    version: int
    template: str
    input_variables: list[str]
    display_name: str = ""
    domain: str = ""
    task_type: str = ""
    output_schema: str = ""
    eval_fixture: str = ""
    comparison_group: str = ""
    tags: list[str] | None = None
    notes: str = ""
    active: bool = True

    def render(self, **kwargs: str) -> str:
        missing = sorted(set(self.input_variables) - set(kwargs))
        if missing:
            raise ValueError(f"Missing prompt variables: {', '.join(missing)}")
        return Template(self.template).safe_substitute(**kwargs)


class PromptRegistry:
    def __init__(self, template_dir: Path | None = None) -> None:
        self.template_dir = template_dir

    def list(self) -> list[PromptTemplate]:
        prompt_ids = self._list_prompt_ids()
        return [self.get(prompt_id) for prompt_id in prompt_ids]

    def get(self, prompt_id: str, version: int | None = None) -> PromptTemplate:
        prompt_file = self._load_prompt_file(prompt_id)
        templates = prompt_file["versions"]
        if version is None:
            candidates = [item for item in templates if item.get("active", True)]
            if not candidates:
                raise ValueError(f"No active versions found for prompt_id={prompt_id}")
            item = max(candidates, key=lambda entry: entry["version"])
        else:
            matches = [item for item in templates if item["version"] == version]
            if not matches:
                raise ValueError(f"Prompt {prompt_id} version {version} not found")
            item = matches[0]
        return PromptTemplate(
            prompt_id=prompt_id,
            version=item["version"],
            template=item["template"],
            input_variables=item["input_variables"],
            display_name=prompt_file.get("display_name", ""),
            domain=prompt_file.get("domain", ""),
            task_type=prompt_file.get("task_type", ""),
            output_schema=prompt_file.get("output_schema", ""),
            eval_fixture=prompt_file.get("eval_fixture", ""),
            comparison_group=prompt_file.get("comparison_group", ""),
            tags=prompt_file.get("tags", []),
            notes=item.get("notes", ""),
            active=item.get("active", True),
        )

    def _load_prompt_file(self, prompt_id: str) -> dict:
        filename = f"{prompt_id}.json"
        if self.template_dir:
            raw = (self.template_dir / filename).read_text(encoding="utf-8")
        else:
            raw = resources.files("llm_platform_starter.prompts.templates").joinpath(
                filename
            ).read_text(encoding="utf-8")
        payload = json.loads(raw)
        return payload

    def _list_prompt_ids(self) -> list[str]:
        if self.template_dir:
            paths = self.template_dir.glob("*.json")
            return sorted(path.stem for path in paths)
        template_root = resources.files("llm_platform_starter.prompts.templates")
        return sorted(path.name.removesuffix(".json") for path in template_root.iterdir())
