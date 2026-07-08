from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentDomain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retrieval_surface: list[str] = Field(min_length=1)
    context_inputs: list[str] = Field(min_length=1)
    context_boundaries: list[str] = Field(min_length=1)
    tools: list[str] = Field(default_factory=list)
    provider_policy: str
    prompt_ids: list[str] = Field(min_length=1)
    prompt_versions: dict[str, list[int]] = Field(default_factory=dict)
    limits: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_prompt_versions(self) -> AgentDomain:
        prompt_ids = set(self.prompt_ids)
        prompt_version_keys = set(self.prompt_versions)
        missing = sorted(prompt_ids - prompt_version_keys)
        unknown = sorted(prompt_version_keys - prompt_ids)
        if missing:
            raise ValueError(
                f"Prompt version mapping missing prompt_id(s): {', '.join(missing)}"
            )
        if unknown:
            raise ValueError(
                f"Prompt version mapping includes unknown prompt_id(s): {', '.join(unknown)}"
            )
        for prompt_id, versions in self.prompt_versions.items():
            if not versions:
                raise ValueError(f"Prompt {prompt_id} must declare at least one version")
            invalid_versions = [version for version in versions if version < 1]
            if invalid_versions:
                raise ValueError(f"Prompt {prompt_id} has invalid version(s): {invalid_versions}")
        return self


class AgentRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    touch_surface: list[str] = Field(min_length=1)
    output_schema: str
    output_expectations: list[str] = Field(min_length=1)
    allowed_side_effects: list[str] = Field(default_factory=list)
    review_requirements: list[str] = Field(min_length=1)
    guardrail_enforcement: list[str] = Field(min_length=1)


class TraceContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    required_steps: list[str] = Field(min_length=1)
    evidence_fields: list[str] = Field(min_length=1)
    eval_evidence: list[str] = Field(min_length=1)

    @field_validator("required_steps")
    @classmethod
    def validate_required_steps(cls, steps: list[str]) -> list[str]:
        expected_steps = [
            "domain_boundary",
            "run_inputs",
            "context_bundle",
            "prompt_provider_call",
            "validation",
            "guardrail_decision",
            "range_output",
            "review_export_touch_decision",
            "eval_evidence",
        ]
        missing = [step for step in expected_steps if step not in steps]
        if missing:
            raise ValueError(f"Trace contract missing required step(s): {', '.join(missing)}")
        return steps


class AgentDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    version: int = Field(ge=1)
    display_name: str
    description: str
    workflow_id: str
    active: bool = True
    tags: list[str] = Field(default_factory=list)
    domain: AgentDomain
    governed_range: AgentRange
    trace_contract: TraceContract


class AgentRegistry:
    def __init__(self, definition_dir: Path | None = None) -> None:
        self.definition_dir = definition_dir

    def list(self) -> list[AgentDefinition]:
        agent_ids = self._list_agent_ids()
        return [self.get(agent_id) for agent_id in agent_ids]

    def get(self, agent_id: str) -> AgentDefinition:
        payload = self._load_definition_file(agent_id)
        return AgentDefinition.model_validate(payload)

    def get_optional(self, agent_id: str) -> AgentDefinition | None:
        if agent_id not in self._list_agent_ids():
            return None
        return self.get(agent_id)

    def _load_definition_file(self, agent_id: str) -> dict:
        filename = f"{agent_id}.json"
        if self.definition_dir:
            raw = (self.definition_dir / filename).read_text(encoding="utf-8")
        else:
            raw = resources.files("blacklight.agents.definitions").joinpath(
                filename
            ).read_text(encoding="utf-8")
        return json.loads(raw)

    def _list_agent_ids(self) -> list[str]:
        if self.definition_dir:
            paths = self.definition_dir.glob("*.json")
            return sorted(path.stem for path in paths)
        definition_root = resources.files("blacklight.agents.definitions")
        return sorted(
            path.name.removesuffix(".json")
            for path in definition_root.iterdir()
            if path.name.endswith(".json")
        )
