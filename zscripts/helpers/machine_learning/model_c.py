import os
import random
from typing import Callable, Iterable, List, Sequence, Tuple

import torch
from helpers.utilities.paths import org_path
from torch import nn
from torch.nn import CrossEntropyLoss
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence, pad_sequence
from torch.optim import Adam
from torch.utils.data import DataLoader, Dataset
from torchtext.data.utils import get_tokenizer
from torchtext.vocab import build_vocab_from_iterator

tokenizer = get_tokenizer("basic_english")


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


data_folder = str(org_path("project_user", "projects", "format_ai", "data"))
before_folder = os.path.join(data_folder, "before_mst")
after_folder = os.path.join(data_folder, "after_mst")
html_pairs = load_html_pairs(before_folder, after_folder)

src_vocab = build_vocab_from_iterator(
    (token for pair in html_pairs for token in tokenizer(pair[0])),
    specials=["<unk>", "<pad>", "<sos>", "<eos>"],
)
trg_vocab = build_vocab_from_iterator(
    (token for pair in html_pairs for token in tokenizer(pair[1])),
    specials=["<unk>", "<pad>", "<sos>", "<eos>"],
)
src_vocab.set_default_index(src_vocab["<unk>"])
trg_vocab.set_default_index(trg_vocab["<unk>"])


def collate_batch(
    batch: List[Tuple[Tuple[List[int], int], Tuple[List[int], int]]],
) -> Tuple[torch.Tensor, torch.Tensor, List[int], List[int]]:
    """Collate a batch of sequences into padded tensors and length lists."""
    batch.sort(key=lambda x: x[0][1], reverse=True)
    src_list, trg_list, src_len_list, trg_len_list = [], [], [], []
    for (src, src_len), (trg, trg_len) in batch:
        src_list.append(torch.tensor(src))
        trg_list.append(torch.tensor(trg))
        src_len_list.append(src_len)
        trg_len_list.append(trg_len)
    return (
        pad_sequence(src_list, padding_value=src_vocab["<pad>"]).to(device),
        pad_sequence(trg_list, padding_value=trg_vocab["<pad>"]).to(device),
        src_len_list,
        trg_len_list,
    )


class HtmlDataset(Dataset):
    """Dataset of tokenized HTML before/after pairs."""

    def __init__(
        self,
        html_pairs: Sequence[Tuple[str, str]],
        src_vocab: dict,
        trg_vocab: dict,
        tokenizer: Callable[[str], Iterable[str]],
    ) -> None:
        """Store pairs, vocabularies, and tokenizer."""
        self.html_pairs = list(html_pairs)
        self.src_vocab = src_vocab
        self.trg_vocab = trg_vocab
        self.tokenizer = tokenizer

    def __getitem__(
        self, idx: int
    ) -> Tuple[Tuple[List[int], int], Tuple[List[int], int]]:
        """Return tokenized source/target pair and their lengths."""
        before_html, after_html = self.html_pairs[idx]
        source = [self.src_vocab[token] for token in self.tokenizer(before_html)]
        target = [self.trg_vocab[token] for token in self.tokenizer(after_html)]
        return (source, len(source)), (target, len(target))

    def __len__(self) -> int:
        """Return the number of HTML pairs in the dataset."""
        return len(self.html_pairs)


batch_size = 12
emb_dim = 256
hid_dim = 512
n_layers = 4
dropout = 0.25
epochs = 10
teacher_forcing_ratio = 0.5
clip = 1
DEBUG = False
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

dataset = HtmlDataset(html_pairs, src_vocab, trg_vocab, tokenizer)
data_iterator = DataLoader(
    dataset, batch_size=batch_size, shuffle=True, collate_fn=collate_batch
)


class Encoder(nn.Module):
    """Token-level LSTM encoder with packing for variable lengths."""

    def __init__(
        self, input_dim: int, emb_dim: int, hid_dim: int, n_layers: int, dropout: float
    ) -> None:
        """Initialize embeddings, LSTM, and dropout layers for the encoder."""
        super().__init__()
        self.hid_dim = hid_dim
        self.n_layers = n_layers
        self.embedding = nn.Embedding(input_dim, emb_dim)
        self.rnn = nn.LSTM(emb_dim, hid_dim, n_layers, dropout=dropout)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self, src: torch.Tensor, src_len: List[int]
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Encode a padded source sequence and return outputs, hidden, and cell."""
        embedded = self.dropout(self.embedding(src))
        packed_embedded = pack_padded_sequence(embedded, src_len, enforce_sorted=False)
        packed_output, (hidden, cell) = self.rnn(packed_embedded)
        output, _ = pad_packed_sequence(packed_output)
        if DEBUG:
            print("Output Shape:", output.shape)
            print("Hidden Shape:", hidden.shape)
            print("Cell Shape:", cell.shape)
        return output, hidden, cell


class Decoder(nn.Module):
    """Token-level LSTM decoder with projection to output vocab."""

    def __init__(
        self, output_dim: int, emb_dim: int, hid_dim: int, n_layers: int, dropout: float
    ) -> None:
        """Initialize embeddings, LSTM, linear projection, and dropout layers."""
        super().__init__()
        self.output_dim = output_dim
        self.hid_dim = hid_dim
        self.n_layers = n_layers
        self.embedding = nn.Embedding(output_dim, emb_dim)
        self.rnn = nn.LSTM(emb_dim, hid_dim, n_layers, dropout=dropout)
        self.fc_out = nn.Linear(hid_dim, output_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(
        self, input: torch.Tensor, hidden: torch.Tensor, cell: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Decode one time step and return logits, hidden, and cell states."""
        input = input.unsqueeze(0)
        embedded = self.dropout(self.embedding(input))
        output, (hidden, cell) = self.rnn(embedded, (hidden, cell))
        prediction = self.fc_out(output.squeeze(0))
        if DEBUG:
            print("Decoder Hidden State Shape:", hidden.shape)
            print("Decoder Cell State Shape:", cell.shape)
        return prediction, hidden, cell


class Seq2Seq(nn.Module):
    """Encoder-decoder wrapper with teacher forcing support."""

    def __init__(
        self, encoder: Encoder, decoder: Decoder, device: torch.device
    ) -> None:
        """Wire encoder/decoder modules and training device."""
        super().__init__()
        self.encoder: Encoder = encoder
        self.decoder: Decoder = decoder
        self.device: torch.device = device

    def forward(
        self,
        src: torch.Tensor,
        src_len: List[int],
        trg: torch.Tensor,
        teacher_forcing_ratio: float = 0.5,
    ) -> torch.Tensor:
        """Run seq2seq with optional teacher forcing and return logits tensor."""
        batch_size = trg.shape[1]
        trg_len = trg.shape[0]
        trg_vocab_size = self.decoder.output_dim
        outputs = torch.zeros(trg_len, batch_size, trg_vocab_size).to(self.device)
        output, hidden, cell = self.encoder(src, src_len)
        hidden = hidden[:, :batch_size, :]
        cell = cell[:, :batch_size, :]
        input = trg[0, :]
        for t in range(1, trg_len):
            output, hidden, cell = self.decoder(input, hidden, cell)
            outputs[t] = output
            teacher_force = random.random() < teacher_forcing_ratio  # nosec B311
            top1 = output.argmax(1)
            input = trg[t] if teacher_force else top1

            if DEBUG:
                print(f"t: {t}, trg_len: {trg_len}")
                print(f"teacher_force: {teacher_force}")
                print(f"top1: {top1}")
                print(f"input: {input}")

        if DEBUG:
            print("Encoder Hidden State Shape:", hidden.shape)
            print("Encoder Cell State Shape:", cell.shape)

        return outputs


input_dim = len(src_vocab)
output_dim = len(trg_vocab)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model_save_path = "model.pt"

encoder = Encoder(input_dim, emb_dim, hid_dim, n_layers, dropout)
decoder = Decoder(output_dim, emb_dim, hid_dim, n_layers, dropout)
model = Seq2Seq(encoder, decoder, device).to(device)

try:
    if os.path.exists(model_save_path):
        model.load_state_dict(torch.load(model_save_path))  # nosec B614
        print("Loaded saved model.")
except Exception as e:
    print(f"Error loading the model: {e}")

optimizer = Adam(model.parameters())
PAD_IDX = src_vocab["<pad>"] if "<pad>" in src_vocab else None
criterion = CrossEntropyLoss(ignore_index=PAD_IDX)

for epoch in range(epochs):
    model.train()
    epoch_loss = 0
    try:
        for batch in data_iterator:
            src, trg, src_len, trg_len = batch
            src = src.to(device)
            trg = trg.to(device)
            optimizer.zero_grad()
            output = model(src, src_len, trg[:, :-1])
            output_dim = output.shape[-1]
            output = output.contiguous().view(-1, output_dim)
            trg = trg[:, 1:].contiguous().view(-1)
            loss = criterion(output, trg)
            print("Loss:", loss)
            loss.backward()
            print("Backward pass completed")
            optimizer.step()
            epoch_loss += loss.item()

    except Exception as e:
        print(f"Error during training: {e}")
        break

    print(f"Epoch: {epoch + 1}, Loss: {epoch_loss / len(data_iterator):.4f}")

    try:
        torch.save(model.state_dict(), model_save_path)
        print(f"Saved model after epoch {epoch + 1}.")
    except Exception as e:
        print(f"Error saving the model: {e}")
