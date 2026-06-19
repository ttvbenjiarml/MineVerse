from __future__ import annotations

from dataclasses import dataclass


MODEL_PRESETS = {
    "tiny": {"context_length": 512, "n_layers": 4, "n_heads": 4, "d_model": 256, "d_ff": 1024},
    "small": {"context_length": 1024, "n_layers": 6, "n_heads": 6, "d_model": 384, "d_ff": 1536},
    "medium": {"context_length": 2048, "n_layers": 8, "n_heads": 8, "d_model": 512, "d_ff": 2048},
    "large_local": {"context_length": 4096, "n_layers": 12, "n_heads": 12, "d_model": 768, "d_ff": 3072},
}


@dataclass
class ModelConfig:
    vocab_size: int = 256
    context_length: int = 128
    n_layers: int = 2
    n_heads: int = 2
    d_model: int = 64
    d_ff: int = 128
    dropout: float = 0.1


def create_model(config: ModelConfig):
    try:
        import torch
        from torch import nn
    except Exception as exc:
        raise RuntimeError("PyTorch is required to create the transformer model") from exc

    class DecoderOnlyTransformer(nn.Module):
        def __init__(self, cfg: ModelConfig):
            super().__init__()
            self.token_embedding = nn.Embedding(cfg.vocab_size, cfg.d_model)
            self.position_embedding = nn.Embedding(cfg.context_length, cfg.d_model)
            layer = nn.TransformerEncoderLayer(
                d_model=cfg.d_model,
                nhead=cfg.n_heads,
                dim_feedforward=cfg.d_ff,
                dropout=cfg.dropout,
                batch_first=True,
                activation="gelu",
            )
            self.transformer = nn.TransformerEncoder(layer, num_layers=cfg.n_layers)
            self.norm = nn.LayerNorm(cfg.d_model)
            self.output = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
            self.output.weight = self.token_embedding.weight

        def forward(self, input_ids):
            positions = torch.arange(input_ids.shape[1], device=input_ids.device).unsqueeze(0)
            x = self.token_embedding(input_ids) + self.position_embedding(positions)
            mask = torch.triu(torch.ones(input_ids.shape[1], input_ids.shape[1], device=input_ids.device), diagonal=1).bool()
            x = self.transformer(x, mask=mask)
            x = self.norm(x)
            return self.output(x)

    return DecoderOnlyTransformer(config)
