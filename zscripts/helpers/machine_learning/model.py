import os
import random
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import torch
from torch import nn
from torch.nn.utils.rnn import pad_sequence
from torch.optim import Adam
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm


class Configuration:
    """Training and model configuration constants."""

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
    """Utilities for preparing HTML pairs for training."""

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
        """Return the set of unique characters across all HTML pairs."""
        return {char for before, after in html_pairs for char in (before + after)}


class HtmlDataset(Dataset):
    """Simple dataset over pairs of HTML strings as character sequences."""

    def __init__(self, html_pairs: Sequence[Tuple[str, str]], token2index: Dict[str, int]) -> None:
        """Store pairs and vocabulary mapping."""
        self.html_pairs = list(html_pairs)
        self.token2index = token2index

    def __getitem__(self, idx: int) -> Tuple[Tuple[List[int], int], Tuple[List[int], int]]:
        """Return (source_ids, len) and (target_ids, len) for index."""
        before_html, after_html = self.html_pairs[idx]
        source = [self.token2index[char] for char in before_html]
        target = [self.token2index[char] for char in after_html]
        return (source, len(source)), (target, len(target))

    def __len__(self) -> int:
        """Dataset size (number of pairs)."""
        return len(self.html_pairs)


class CollateFunction:
    """Pad variable-length sequences and collect batch tensors."""

    def __init__(self, pad_value: int) -> None:
        """Initialize collator with a padding token id."""
        self.pad_value = pad_value

    def collate_batch(
        self, batch: List[Tuple[Tuple[List[int], int], Tuple[List[int], int]]]
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Pad sequences and return (src, trg, trg_len) tensors."""
        batch.sort(key=lambda x: x[0][1], reverse=True)
        src_list, trg_list, trg_len_list = [], [], []

        for _src, _trg in batch:
            src, trg = _src[0], _trg[0]
            trg_len = len(trg)

            src_list.append(src)
            trg_list.append(trg)
            trg_len_list.append(trg_len)

        src_padded = pad_sequence(
            [torch.tensor(seq, device=Configuration.DEVICE) for seq in src_list],
            padding_value=self.pad_value,
        )
        trg_padded = pad_sequence(
            [torch.tensor(seq, device=Configuration.DEVICE) for seq in trg_list],
            padding_value=self.pad_value,
        )

        trg_len_tensor = torch.tensor(trg_len_list, dtype=torch.long)

        return src_padded, trg_padded, trg_len_tensor


class Encoder(nn.Module):
    """Character-level LSTM encoder."""

    def __init__(self, input_dim: int) -> None:
        """Create embedding + LSTM encoder for a given vocab size."""
        super().__init__()
        self.embedding = nn.Embedding(input_dim, Configuration.EMBEDDING_DIM)
        self.rnn = nn.LSTM(
            Configuration.EMBEDDING_DIM,
            Configuration.HIDDEN_DIM,
            Configuration.N_LAYERS,
            dropout=Configuration.DROPOUT,
        )
        self.dropout = nn.Dropout(Configuration.DROPOUT)

    def forward(self, src: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Encode a batch of sequences into hidden and cell states."""
        embedded = self.dropout(self.embedding(src))
        hidden, cell = self.rnn(embedded)
        return hidden, cell


class Decoder(nn.Module):
    """Character-level LSTM decoder with linear projection to vocab."""

    def __init__(self, output_dim: int) -> None:
        """Create embedding + LSTM decoder for a given vocab size."""
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
        """Decode one time-step and return logits and new states."""
        input = input.unsqueeze(0)
        embedded = self.dropout(self.embedding(input))
        output, (hidden, cell) = self.rnn(embedded, (hidden, cell))
        prediction = self.fc_out(output.squeeze(0))
        return prediction, hidden, cell


class Seq2Seq(nn.Module):
    """Minimal seq2seq model composed of an encoder and decoder."""

    def __init__(self, encoder: Encoder, decoder: Decoder) -> None:
        """Wire encoder and decoder into a seq2seq module."""
        super().__init__()
        self.encoder: Encoder = encoder
        self.decoder: Decoder = decoder

    def forward(self, src: torch.Tensor, trg: torch.Tensor) -> torch.Tensor:
        """Run teacher-forced decoding over the target sequence length."""
        batch_size = src.shape[1]
        trg_len = trg.shape[0]
        trg_vocab_size = self.decoder.fc_out.out_features
        outputs = torch.zeros(trg_len, batch_size, trg_vocab_size, device=Configuration.DEVICE)
        hidden, cell = self.encoder(src)
        input = trg[0, :]

        for t in range(1, trg_len):
            output, hidden, cell = self.decoder(input, hidden, cell)
            outputs[t] = output
            teacher_force = random.random() < Configuration.TEACHER_FORCING_RATIO
            top1 = output.argmax(1)
            input = trg[t] if teacher_force else top1

        return outputs


def load_model(input_dim: int, output_dim: int) -> Seq2Seq:
    encoder = Encoder(input_dim)
    decoder = Decoder(output_dim)
    model = Seq2Seq(encoder, decoder)
    model = model.to(Configuration.DEVICE)

    if os.path.exists(Configuration.MODEL_SAVE_PATH):
        try:
            model.load_state_dict(torch.load(Configuration.MODEL_SAVE_PATH))
            print("Loaded saved model.")
        except Exception as e:
            print(f"Error loading the model: {e}")
            print("Creating a new model.")
    else:
        print("No saved model found. Creating a new model.")

    return model


def train_model(model: Seq2Seq, data_iterator: DataLoader, src_vocab: Dict[str, int]) -> None:
    optimizer = Adam(model.parameters())
    PAD_IDX = src_vocab["<pad>"] if "<pad>" in src_vocab else None
    criterion = nn.CrossEntropyLoss(ignore_index=PAD_IDX)
    print(f"Total number of samples: {len(data_iterator.dataset)}")

    for epoch in range(Configuration.EPOCHS):
        model.train()
        epoch_loss = 0

        with tqdm(total=len(data_iterator), desc=f"Epoch {epoch + 1}", unit="batch") as pbar:
            for _, batch in enumerate(data_iterator):
                src, trg, _ = batch
                src = src.to(Configuration.DEVICE)
                trg = trg.to(Configuration.DEVICE)
                optimizer.zero_grad()
                output = model(src, trg)
                output_dim = output.shape[-1]
                output = output[1:].reshape(-1, output_dim)
                trg = trg[1:].reshape(-1)

                loss = criterion(output, trg)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                pbar.set_postfix({"Loss": loss.item()})
                pbar.update(1)

        print(f"Epoch: {epoch + 1}, Loss: {epoch_loss / len(data_iterator):.4f}")

        try:
            torch.save(model.state_dict(), Configuration.MODEL_SAVE_PATH)
            print(f"Saved model after epoch {epoch + 1}.")
        except Exception as e:
            print(f"Error saving the model: {e}")


def main() -> None:
    data_folder = os.path.join(os.getcwd(), "data")
    before_folder = os.path.join(data_folder, "before_mst")
    after_folder = os.path.join(data_folder, "after_mst")
    html_pairs = HtmlDataPreprocessor.load_html_pairs(before_folder, after_folder)
    src_vocab = HtmlDataPreprocessor.get_all_tokens(html_pairs)
    src_token2index = {token: i for i, token in enumerate(src_vocab)}
    src_token2index["<pad>"] = len(src_token2index)
    dataset = HtmlDataset(html_pairs, src_token2index)
    collate_fn = CollateFunction(src_token2index["<pad>"]).collate_batch
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
