from __future__ import annotations


def sample_next_token(logits, temperature: float = 1.0):
    try:
        import torch
    except Exception as exc:
        raise RuntimeError("PyTorch is required for generation") from exc
    logits = logits / max(temperature, 1e-5)
    probs = torch.softmax(logits, dim=-1)
    return torch.multinomial(probs, num_samples=1)


def apply_repetition_penalty(logits, generated_tokens, penalty: float = 1.0):
    if penalty <= 1.0 or not generated_tokens:
        return logits
    adjusted = logits.clone()
    unique_tokens = set(int(token) for token in generated_tokens)
    for token in unique_tokens:
        adjusted[..., token] = adjusted[..., token] / penalty
    return adjusted


def top_k_top_p_filter(logits, top_k: int = 0, top_p: float = 1.0):
    try:
        import torch
    except Exception as exc:
        raise RuntimeError("PyTorch is required for generation") from exc

    filtered = logits.clone()
    if top_k > 0:
        values, _ = torch.topk(filtered, min(top_k, filtered.shape[-1]))
        cutoff = values[..., -1, None]
        filtered[filtered < cutoff] = float("-inf")

    if 0.0 < top_p < 1.0:
        sorted_logits, sorted_indices = torch.sort(filtered, descending=True)
        probs = torch.softmax(sorted_logits, dim=-1)
        cumulative = torch.cumsum(probs, dim=-1)
        remove = cumulative > top_p
        remove[..., 1:] = remove[..., :-1].clone()
        remove[..., 0] = False
        sorted_logits[remove] = float("-inf")
        filtered = torch.full_like(filtered, float("-inf"))
        filtered.scatter_(dim=-1, index=sorted_indices, src=sorted_logits)
    return filtered
