from __future__ import annotations

import hashlib
import time
import uuid

from llm_platform_starter.errors import GuardrailValidationError
from llm_platform_starter.guardrails.validation import validate_ticket_output
from llm_platform_starter.models import (
    GuardrailOutcome,
    ProviderRequest,
    TicketClassification,
    TicketRequest,
    TraceRecord,
)
from llm_platform_starter.observability.cost import estimate_cost
from llm_platform_starter.observability.idempotency import (
    IdempotencyInProgressError,
    IdempotencyStore,
)
from llm_platform_starter.observability.storage import TraceStore
from llm_platform_starter.prompts.registry import PromptRegistry
from llm_platform_starter.providers.base import LLMProvider
from llm_platform_starter.providers.reliability import (
    KeyedRateLimiter,
    ProviderCallError,
    complete_with_retries,
)


class TicketClassifier:
    prompt_id = "ticket_classifier"

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        prompt_registry: PromptRegistry | None = None,
        trace_store: TraceStore | None = None,
        idempotency_store: IdempotencyStore | None = None,
        provider_timeout_seconds: float = 30.0,
        provider_max_retries: int = 2,
        provider_rate_limit_requests: int = 3,
        provider_rate_limit_window_seconds: float = 10.0,
        provider_rate_limiter: KeyedRateLimiter | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.prompt_registry = prompt_registry or PromptRegistry()
        self.trace_store = trace_store
        self.idempotency_store = idempotency_store
        self.provider_timeout_seconds = provider_timeout_seconds
        self.provider_max_retries = provider_max_retries
        self.provider_rate_limiter = provider_rate_limiter or KeyedRateLimiter(
            max_requests=provider_rate_limit_requests,
            window_seconds=provider_rate_limit_window_seconds,
        )

    def classify(self, ticket: TicketRequest) -> TicketClassification:
        request_id = str(uuid.uuid4())
        prompt_template = self.prompt_registry.get(self.prompt_id)
        prompt = prompt_template.render(subject=ticket.subject, body=ticket.body)
        idempotency_key = ticket.idempotency_key or self._default_idempotency_key(
            ticket=ticket,
            prompt_version=prompt_template.version,
        )
        started = time.perf_counter()
        error_category: str | None = None
        validation_passed = False
        guardrail_outcome = GuardrailOutcome.rejected
        try:
            if self.idempotency_store:
                cached = self.idempotency_store.get_ticket_classification(idempotency_key)
                if cached:
                    return cached
                claimed = self.idempotency_store.claim(
                    idempotency_key,
                    request_fingerprint=self._request_fingerprint(
                        ticket=ticket,
                        prompt_version=prompt_template.version,
                    ),
                )
                if not claimed:
                    error_category = "idempotency_in_progress"
                    raise IdempotencyInProgressError(
                        f"Request with idempotency key {idempotency_key!r} is already in progress."
                    )
            request = ProviderRequest(
                prompt=prompt,
                model=self.model,
                metadata={
                    "request_id": request_id,
                    "prompt_id": self.prompt_id,
                    "idempotency_key": idempotency_key,
                },
            )
            response = complete_with_retries(
                self.provider,
                request,
                timeout_seconds=self.provider_timeout_seconds,
                max_retries=self.provider_max_retries,
                rate_limiter=self.provider_rate_limiter.limiter_for(ticket.session_id or "anonymous"),
            )
            parsed, validation = validate_ticket_output(
                response.text,
                source_text=f"{ticket.subject}\n{ticket.body}",
            )
            validation_passed = validation.passed
            guardrail_outcome = validation.outcome
            if parsed is None:
                error_category = "validation_error"
                raise GuardrailValidationError("; ".join(validation.errors))
            if self.idempotency_store:
                self.idempotency_store.complete_ticket_classification(idempotency_key, parsed)
            return parsed
        except ProviderCallError as exc:
            error_category = exc.category
            raise
        except IdempotencyInProgressError:
            raise
        except Exception:
            if self.idempotency_store:
                self.idempotency_store.fail(idempotency_key)
            raise
        finally:
            if self.trace_store:
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                if "response" in locals():
                    self.trace_store.insert(
                        TraceRecord(
                            request_id=request_id,
                            session_id=ticket.session_id or "anonymous",
                            prompt_id=self.prompt_id,
                            prompt_version=prompt_template.version,
                            provider=response.provider,
                            model=response.model,
                            latency_ms=latency_ms,
                            input_tokens=response.input_tokens,
                            output_tokens=response.output_tokens,
                            estimated_cost_usd=estimate_cost(
                                response.model,
                                response.input_tokens,
                                response.output_tokens,
                            ),
                            validation_passed=validation_passed,
                            guardrail_outcome=guardrail_outcome,
                            error_category=error_category,
                        )
                    )
                elif error_category:
                    self.trace_store.insert(
                        TraceRecord(
                            request_id=request_id,
                            session_id=ticket.session_id or "anonymous",
                            prompt_id=self.prompt_id,
                            prompt_version=prompt_template.version,
                            provider=self.provider.name,
                            model=self.model,
                            latency_ms=latency_ms,
                            input_tokens=0,
                            output_tokens=0,
                            estimated_cost_usd=0,
                            validation_passed=False,
                            guardrail_outcome=guardrail_outcome,
                            error_category=error_category,
                        )
                    )

    def _default_idempotency_key(self, ticket: TicketRequest, prompt_version: int) -> str:
        return self._request_fingerprint(ticket=ticket, prompt_version=prompt_version)

    def _request_fingerprint(self, ticket: TicketRequest, prompt_version: int) -> str:
        payload = "\n".join(
            [
                ticket.session_id or "anonymous",
                self.prompt_id,
                str(prompt_version),
                self.model,
                ticket.subject,
                ticket.body,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
