from __future__ import annotations

from typing import Dict, List, Tuple

import torch

from zscripts.helpers.machine_learning import model_copy_3 as ml_model


def test_tokenization() -> None:
    pairs: List[Tuple[str, str]] = [
        ("hello", "world"),
        ("abc", "abd"),
    ]
    tokens = ml_model.HtmlDataPreprocessor.get_all_tokens(pairs)
    assert "h" in tokens and "d" in tokens

    token2index: Dict[str, int] = {ch: i for i, ch in enumerate(sorted(tokens))}
    token2index["<pad>"] = len(token2index)
    token2index["<sos>"] = len(token2index)
    token2index["<eos>"] = len(token2index)

    ds = ml_model.HtmlDataset(pairs, token2index)
    (src, src_len), (trg, trg_len) = ds[0]
    assert src_len == len(src) and trg_len == len(trg)
    assert src_len > 0 and trg_len > 0


def test_seq2seq_forward_cpu() -> None:
    # Shrink configuration for a fast CPU-only smoke test
    ml_model.Configuration.EMBEDDING_DIM = 8
    ml_model.Configuration.HIDDEN_DIM = 16
    ml_model.Configuration.N_LAYERS = 1
    ml_model.Configuration.DROPOUT = 0.0
    ml_model.Configuration.DEVICE = torch.device("cpu")

    pairs: List[Tuple[str, str]] = [
        ("hello", "hullo"),
        ("world", "wurld"),
    ]
    tokens = ml_model.HtmlDataPreprocessor.get_all_tokens(pairs)
    token2index: Dict[str, int] = {ch: i for i, ch in enumerate(sorted(tokens))}
    token2index["<pad>"] = len(token2index)
    token2index["<sos>"] = len(token2index)
    token2index["<eos>"] = len(token2index)

    ds = ml_model.HtmlDataset(pairs, token2index)
    collate = ml_model.CollateFunction(token2index["<pad>"], max_seq_length=64).collate_batch
    src, trg, src_len, _ = collate([ds[0], ds[1]])

    input_dim = len(token2index)
    output_dim = len(token2index)
    enc = ml_model.Encoder(input_dim)
    dec = ml_model.Decoder(output_dim)
    seq2seq = ml_model.Seq2Seq(enc, dec)

    outputs = seq2seq(src, src_len, trg)
    assert outputs.shape[0] == trg.shape[0]
    assert outputs.shape[1] == trg.shape[1]
    assert outputs.shape[2] == output_dim


def test_seq2seq_train_step_cpu() -> None:
    # Small deterministic-ish setup
    ml_model.Configuration.EMBEDDING_DIM = 8
    ml_model.Configuration.HIDDEN_DIM = 16
    ml_model.Configuration.N_LAYERS = 1
    ml_model.Configuration.DROPOUT = 0.0
    ml_model.Configuration.DEVICE = torch.device("cpu")
    ml_model.Configuration.TEACHER_FORCING_RATIO = 1.0

    pairs: List[Tuple[str, str]] = [("ab", "ac"), ("ba", "bc")]
    tokens = ml_model.HtmlDataPreprocessor.get_all_tokens(pairs)
    token2index: Dict[str, int] = {ch: i for i, ch in enumerate(sorted(tokens))}
    token2index["<pad>"] = len(token2index)
    token2index["<sos>"] = len(token2index)
    token2index["<eos>"] = len(token2index)

    ds = ml_model.HtmlDataset(pairs, token2index)
    collate = ml_model.CollateFunction(token2index["<pad>"], max_seq_length=16).collate_batch
    src, trg, src_len, _ = collate([ds[0], ds[1]])

    input_dim = len(token2index)
    output_dim = len(token2index)
    enc = ml_model.Encoder(input_dim)
    dec = ml_model.Decoder(output_dim)
    seq2seq = ml_model.Seq2Seq(enc, dec)

    pad_idx = token2index["<pad>"]
    criterion = torch.nn.CrossEntropyLoss(ignore_index=pad_idx)
    optim = torch.optim.Adam(seq2seq.parameters(), lr=1e-2)

    # Snapshot one param
    first_param = next(seq2seq.parameters()).detach().clone()

    optim.zero_grad()
    outputs = seq2seq(src, src_len, trg[:, :-1])
    output_dim = outputs.shape[-1]
    loss = criterion(outputs.reshape(-1, output_dim), trg[:, 1:].reshape(-1))
    loss.backward()
    optim.step()

    # Ensure parameters changed
    assert not torch.equal(first_param, next(seq2seq.parameters()).detach())


if __name__ == "__main__":
    test_tokenization()
    test_seq2seq_forward_cpu()
    print("ml seq2seq smoke tests passed")
