from __future__ import annotations


MODEL_PRICES_PER_1K = {
    "mock-ticket-classifier": {"input": 0.0, "output": 0.0},
    "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = MODEL_PRICES_PER_1K.get(model, {"input": 0.0, "output": 0.0})
    return round(
        (input_tokens / 1000 * prices["input"]) + (output_tokens / 1000 * prices["output"]),
        8,
    )
