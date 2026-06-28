import os
import random
from typing import Iterable, List, Sequence, Set, Tuple

import torch
from torch import nn
from torch.nn import CrossEntropyLoss
from torch.nn.utils.rnn import PackedSequence, pad_sequence
from torch.optim import Adam
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm


class Configuration:
    """Central configuration for training and model hyperparameters."""

    BATCH_SIZE = 8
    EMBEDDING_DIM = 256
    HIDDEN_DIM = 512
    N_LAYERS = 3
    DROPOUT = 0.25
    EPOCHS = 10
    TEACHER_FORCING_RATIO = 0.25
    CLIP = 1
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    MODEL_SAVE_PATH = "model.pt"


class HtmlDataPreprocessor:
    """Utility helpers for loading and tokenizing HTML data."""

    @staticmethod
    def load_html_pairs(before_folder: str, after_folder: str) -> List[Tuple[str, str]]:
        """Load before/after HTML file pairs from two folders."""
        pairs: List[Tuple[str, str]] = []
        for filename in os.listdir(before_folder):
            base_filename = filename.replace("_before.html", "")
            before_file_path = os.path.join(before_folder, filename)
            after_file_path = os.path.join(after_folder, base_filename + "_after.html")
            with open(before_file_path, "r", encoding="utf-8") as before_file:
                before_html = before_file.read()
            if os.path.exists(after_file_path):
                with open(after_file_path, "r", encoding="utf-8") as after_file:
                    after_html = after_file.read()
            else:
                print(f"Missing corresponding 'after' file for: {filename}")
                continue
            pairs.append((before_html, after_html))
        return pairs

    @staticmethod
    def get_all_tokens(html_pairs: Iterable[Tuple[str, str]]) -> Set[str]:
        """Return the set of unique characters across all pairs."""
        return {char for pair in html_pairs for char in pair[0] + pair[1]}


class HtmlDataset(Dataset):
    """Dataset producing token index sequences with <sos>/<eos> markers."""

    def __init__(
        self, html_pairs: Sequence[Tuple[str, str]], token2index: dict[str, int]
    ) -> None:
        """Initialize dataset with HTML pairs and a token-to-index mapping."""
        self.html_pairs = list(html_pairs)
        self.token2index = token2index

    def __getitem__(
        self, idx: int
    ) -> Tuple[Tuple[List[int], int], Tuple[List[int], int]]:
        """Return tokenized source/target sequences with their lengths for index."""
        before_html, after_html = self.html_pairs[idx]
        source = (
            [self.token2index["<sos>"]]
            + [self.token2index[char] for char in before_html]
            + [self.token2index["<eos>"]]
        )
        target = (
            [self.token2index["<sos>"]]
            + [self.token2index[char] for char in after_html]
            + [self.token2index["<eos>"]]
        )
        return (source, len(source)), (target, len(target))

    def __len__(self) -> int:
        """Return number of pairs in the dataset."""
        return len(self.html_pairs)


class CollateFunction:
    """Collate and pad variable-length sequences for batching."""

    def __init__(self, pad_value: int, max_seq_length: int) -> None:
        """Create a collator with padding id and maximum sequence length."""
        self.pad_value = pad_value
        self.max_seq_length = max_seq_length

    def collate_batch(
        self, batch: List[Tuple[Tuple[List[int], int], Tuple[List[int], int]]]
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        """Pad and batch sequences, returning tensors and length vectors."""
        batch.sort(key=lambda x: x[0][1], reverse=True)
        src_list, trg_list, src_len_list, trg_len_list = [], [], [], []
        for _src, _trg in batch:
            src, trg = _src[0], _trg[0]
            src_len, trg_len = len(src), len(trg)
            if src_len > self.max_seq_length:
                src = src[: self.max_seq_length]
            else:
                src.extend([self.pad_value] * (self.max_seq_length - src_len))
            if trg_len > self.max_seq_length:
                trg = trg[: self.max_seq_length]
            else:
                trg.extend([self.pad_value] * (self.max_seq_length - trg_len))
            src_list.append(src)
            trg_list.append(trg)
            src_len_list.append(src_len)
            trg_len_list.append(trg_len)
        src_padded = pad_sequence(
            [torch.tensor(seq, device=Configuration.DEVICE) for seq in src_list],
            padding_value=self.pad_value,
        )
        trg_padded = pad_sequence(
            [torch.tensor(seq, device=Configuration.DEVICE) for seq in trg_list],
            padding_value=self.pad_value,
        )
        src_len_tensor = torch.tensor(src_len_list, dtype=torch.long)
        trg_len_tensor = torch.tensor(trg_len_list, dtype=torch.long)
        return src_padded, trg_padded, src_len_tensor, trg_len_tensor


class Encoder(nn.Module):
    """Embedding + LSTM encoder producing hidden/cell states."""

    def __init__(self, input_dim: int) -> None:
        """Initialize embedding, LSTM encoder, and dropout."""
        super().__init__()
        self.embedding = nn.Embedding(input_dim, Configuration.EMBEDDING_DIM)
        self.rnn = nn.LSTM(
            Configuration.EMBEDDING_DIM,
            Configuration.HIDDEN_DIM,
            Configuration.N_LAYERS,
            dropout=Configuration.DROPOUT,
        )
        self.dropout = nn.Dropout(Configuration.DROPOUT)

    def forward(
        self, src: torch.Tensor, src_len: torch.Tensor
    ) -> Tuple[PackedSequence, torch.Tensor, torch.Tensor]:
        """Encode a batch of padded sequences and lengths."""
        embedded = self.dropout(self.embedding(src))
        packed_embedded = nn.utils.rnn.pack_padded_sequence(
            embedded, src_len.cpu(), batch_first=False, enforce_sorted=False
        )
        packed_output, (hidden, cell) = self.rnn(packed_embedded)
        return packed_output, hidden, cell


class Decoder(nn.Module):
    """LSTM decoder projecting to vocabulary logits."""

    def __init__(self, output_dim: int) -> None:
        """Initialize embedding, LSTM decoder, projection, and dropout."""
        super().__init__()
        self.embedding = nn.Embedding(output_dim, Configuration.EMBEDDING_DIM)
        self.rnn = nn.LSTM(
            Configuration.EMBEDDING_DIM,
            Configuration.HIDDEN_DIM,
            Configuration.N_LAYERS,
            dropout=Configuration.DROPOUT,
        )
        self.fc_out = nn.Linear(Configuration.HIDDEN_DIM, output_dim)
        self.dropout = nn.Dropout(Configuration.DROPOUT)

    def forward(
        self, input: torch.Tensor, hidden: torch.Tensor, cell: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Decode one time step and project to output logits."""
        input = input.unsqueeze(0)
        embedded = self.dropout(self.embedding(input))
        output, (hidden, cell) = self.rnn(embedded, (hidden, cell))
        prediction = self.fc_out(output.squeeze(0))
        return prediction, hidden, cell


class Seq2Seq(nn.Module):
    """Encoder/decoder wrapper with teacher forcing control."""

    def __init__(self, encoder: Encoder, decoder: Decoder) -> None:
        """Bind encoder and decoder modules."""
        super().__init__()
        self.encoder = encoder
        self.decoder = decoder

    def forward(
        self,
        src: torch.Tensor,
        src_len: torch.Tensor,
        trg: torch.Tensor,
        trg_len: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Run teacher-forced training loop for a full target sequence."""
        batch_size = src.shape[1]
        trg_len = trg.shape[0]
        trg_vocab_size = self.decoder.fc_out.out_features
        outputs = torch.zeros(
            trg_len, batch_size, trg_vocab_size, device=Configuration.DEVICE
        )
        output, hidden, cell = self.encoder(src, src_len)
        hidden = hidden[:, :batch_size, :]
        cell = cell[:, :batch_size, :]
        input = trg[0, :]
        for t in range(1, trg_len):
            output, hidden, cell = self.decoder(input, hidden, cell)
            outputs[t] = output
            teacher_force = (
                random.random() < Configuration.TEACHER_FORCING_RATIO
            )  # nosec B311
            top1 = output.argmax(1)
            input = trg[t] if teacher_force else top1
        return outputs


def load_model(input_dim: int, output_dim: int) -> Seq2Seq:
    """Construct Seq2Seq and optionally load saved weights."""
    encoder = Encoder(input_dim)
    decoder = Decoder(output_dim)
    model = Seq2Seq(encoder, decoder)
    model = model.to(Configuration.DEVICE)
    if os.path.exists(Configuration.MODEL_SAVE_PATH):
        try:
            model.load_state_dict(
                torch.load(Configuration.MODEL_SAVE_PATH)
            )  # nosec B614
            print("Loaded saved model.")
        except Exception as e:
            print(f"Error loading the model: {e}")
    else:
        print("No saved model found.")
    return model


def train_model(
    model: Seq2Seq, data_iterator: DataLoader, src_vocab: dict[str, int]
) -> None:
    """Train the model for configured epochs and persist checkpoints."""
    optimizer = Adam(model.parameters())
    PAD_IDX = src_vocab["<pad>"] if "<pad>" in src_vocab else None
    EOS_IDX = src_vocab["<eos>"] if "<eos>" in src_vocab else None
    criterion = CrossEntropyLoss(ignore_index=PAD_IDX)
    print(f"Total number of samples: {len(data_iterator.dataset)}")
    for epoch in range(Configuration.EPOCHS):
        model.train()
        epoch_loss = 0
        with tqdm(
            total=len(data_iterator), desc=f"Epoch {epoch + 1}", unit="batch"
        ) as pbar:
            for _i, batch in enumerate(data_iterator):
                src, trg, src_len = batch
                src = src.to(Configuration.DEVICE)
                trg = trg.to(Configuration.DEVICE)
                optimizer.zero_grad()
                output = model(src, src_len, trg)
                output_dim = output.shape[-1]
                non_pad_mask = trg.view(-1).ne(PAD_IDX) & trg.view(-1).ne(EOS_IDX)
                output_masked = output.view(-1, output_dim)[non_pad_mask]
                trg_masked = trg.view(-1)[non_pad_mask]
                output_masked = output_masked.view(-1, output_dim)
                trg_masked = trg_masked.contiguous().view(-1)
                loss = criterion(output_masked, trg_masked)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                pbar.set_postfix({"Loss": epoch_loss / (pbar.n + 1)})
                pbar.update(1)
        print(f"Epoch: {epoch + 1}, Loss: {epoch_loss / len(data_iterator):.4f}")
        try:
            torch.save(model.state_dict(), Configuration.MODEL_SAVE_PATH)
            print(f"Saved model after epoch {epoch + 1}.")
        except Exception as e:
            print(f"Error saving the model: {e}")


def main() -> None:
    """Entry point for local training using ./data before/after pairs."""
    data_folder = os.path.join(os.getcwd(), "data")
    before_folder = os.path.join(data_folder, "before_mst")
    after_folder = os.path.join(data_folder, "after_mst")
    html_pairs = HtmlDataPreprocessor.load_html_pairs(before_folder, after_folder)
    src_vocab = HtmlDataPreprocessor.get_all_tokens(html_pairs)
    src_token2index = {token: i for i, token in enumerate(src_vocab)}
    src_token2index["<pad>"] = len(src_token2index)
    src_token2index["<sos>"] = len(src_token2index)
    src_token2index["<eos>"] = len(src_token2index)
    dataset = HtmlDataset(html_pairs, src_token2index)
    max_seq_length = 6000
    collate_fn = CollateFunction(src_token2index["<pad>"], max_seq_length).collate_batch
    data_iterator = DataLoader(
        dataset,
        batch_size=Configuration.BATCH_SIZE,
        shuffle=True,
        collate_fn=collate_fn,
        drop_last=True,
    )
    model = load_model(len(src_token2index), len(src_token2index))
    train_model(model, data_iterator, src_token2index)


if __name__ == "__main__":
    main()
