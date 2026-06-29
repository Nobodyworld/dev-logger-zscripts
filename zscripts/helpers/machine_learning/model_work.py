import os
import random
from typing import Iterable, List, Sequence, Tuple

import torch
from torch import nn
from torch.nn import CrossEntropyLoss
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence, pad_sequence
from torch.optim import Adam
from torch.utils.data import DataLoader, Dataset
from torchtext.data.utils import get_tokenizer
from torchtext.vocab import Vocab, build_vocab_from_iterator
from tqdm import tqdm


class Configuration:
    """Training and model configuration constants."""

    BATCH_SIZE = 64
    EMBEDDING_DIM = 256
    HIDDEN_DIM = 512
    N_LAYERS = 4
    DROPOUT = 0.0
    EPOCHS = 10
    TEACHER_FORCING_RATIO = 0.5
    CLIP = 1
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    MODEL_SAVE_PATH = "model.pt"


class HtmlDataPreprocessor:
    """Utilities for preparing HTML pairs and vocabularies."""

    TOKENIZER = get_tokenizer("basic_english")

    @classmethod
    def build_vocab(cls, html_pairs: Iterable[Tuple[str, str]]) -> Tuple[Vocab, Vocab]:
        """Build source and target vocabularies from HTML pairs."""
        src_vocab: Vocab = build_vocab_from_iterator(
            (token for pair in html_pairs for token in cls.TOKENIZER(pair[0])),
            specials=["<unk>", "<pad>", "<sos>", "<eos>"],
        )
        trg_vocab: Vocab = build_vocab_from_iterator(
            (token for pair in html_pairs for token in cls.TOKENIZER(pair[1])),
            specials=["<unk>", "<pad>", "<sos>", "<eos>"],
        )
        src_vocab.set_default_index(src_vocab["<unk>"])
        trg_vocab.set_default_index(trg_vocab["<unk>"])
        return src_vocab, trg_vocab

    @staticmethod
    def load_html_pairs(before_folder: str, after_folder: str) -> List[Tuple[str, str]]:
        """Load before/after HTML file pairs from two folders."""
        pairs: List[Tuple[str, str]] = []
        for filename in os.listdir(before_folder):
            base_filename = filename.replace("_before.html", "")
            before_file_path = os.path.join(before_folder, filename)
            after_file_path = os.path.join(after_folder, base_filename + "_after.html")

            print(f"Processing: {before_file_path} -> {after_file_path}")

            with open(before_file_path, "r", encoding="utf-8") as before_file:
                before_html = before_file.read()
            if os.path.exists(after_file_path):
                with open(after_file_path, "r", encoding="utf-8") as after_file:
                    after_html = after_file.read()
            else:
                print(f"Missing corresponding 'after' file for: {filename}")
                continue

            print(f"Loaded pair: {before_file_path} -> {after_file_path}")
            pairs.append((before_html, after_html))
        return pairs


class HtmlDataset(Dataset):
    """Dataset of tokenized HTML before/after pairs."""

    def __init__(self, html_pairs: Sequence[Tuple[str, str]], src_vocab: Vocab, trg_vocab: Vocab) -> None:
        """Store pairs and vocabularies for tokenization."""
        self.html_pairs = list(html_pairs)
        self.src_vocab = src_vocab
        self.trg_vocab = trg_vocab

    def __getitem__(self, idx: int) -> Tuple[Tuple[List[int], int], Tuple[List[int], int]]:
        """Return tokenized source/target sequences and their lengths for index."""
        before_html, after_html = self.html_pairs[idx]
        source = (
            [self.src_vocab["<sos>"]]
            + [self.src_vocab[token] for token in HtmlDataPreprocessor.TOKENIZER(before_html)]
            + [self.src_vocab["<eos>"]]
        )
        target = (
            [self.trg_vocab["<sos>"]]
            + [self.trg_vocab[token] for token in HtmlDataPreprocessor.TOKENIZER(after_html)]
            + [self.trg_vocab["<eos>"]]
        )
        return (source, len(source)), (target, len(target))

    def __len__(self) -> int:
        """Return the number of pairs in the dataset."""
        return len(self.html_pairs)


class CollateFunction:
    """Pad variable-length sequences and collect batch tensors."""

    def __init__(self, src_vocab: Vocab, trg_vocab: Vocab) -> None:
        """Initialize collator with padding token ids from vocabularies."""
        self.src_vocab = src_vocab
        self.trg_vocab = trg_vocab

    def collate_batch(
        self, batch: List[Tuple[Tuple[List[int], int], Tuple[List[int], int]]]
    ) -> Tuple[torch.Tensor, torch.Tensor, List[int], List[int]]:
        """Pad sequences and return (src, trg, src_len_list, trg_len_list)."""
        batch.sort(key=lambda x: x[0][1], reverse=True)
        src_list, trg_list, src_len_list, trg_len_list = [], [], [], []
        for _src, _trg in batch:
            src_list.append(torch.tensor(_src[0]))
            trg_list.append(torch.tensor(_trg[0]))
            src_len_list.append(_src[1])
            trg_len_list.append(_trg[1])
        src_padded = pad_sequence(src_list, padding_value=self.src_vocab["<pad>"])
        trg_padded = pad_sequence(trg_list, padding_value=self.trg_vocab["<pad>"])
        return src_padded, trg_padded, src_len_list, trg_len_list


class Encoder(nn.Module):
    """Token-level LSTM encoder with packing for variable lengths."""

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
        self, src: torch.Tensor, src_len: List[int] | torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Encode a batch of padded sequences and lengths."""
        embedded = self.dropout(self.embedding(src))
        packed_embedded = pack_padded_sequence(embedded, src_len, enforce_sorted=False)
        packed_output, (hidden, cell) = self.rnn(packed_embedded)
        output, _ = pad_packed_sequence(packed_output)
        return output, hidden, cell


class Decoder(nn.Module):
    """Token-level LSTM decoder with projection to output vocab."""

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
        """Decode one time step and return logits and new states."""
        input = input.unsqueeze(0)
        embedded = self.dropout(self.embedding(input))
        output, (hidden, cell) = self.rnn(embedded, (hidden, cell))
        prediction = self.fc_out(output.squeeze(0))
        return prediction, hidden, cell


class Seq2Seq(nn.Module):
    """Encoder/decoder wrapper with teacher forcing support."""

    def __init__(self, encoder: Encoder, decoder: Decoder) -> None:
        """Bind encoder and decoder modules."""
        super().__init__()
        self.encoder = encoder
        self.decoder = decoder

    def forward(
        self,
        src: torch.Tensor,
        src_len: List[int] | torch.Tensor,
        trg: torch.Tensor,
        trg_len: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Run teacher-forced decoding over the target sequence length."""
        batch_size = src.shape[1]
        t_len = trg.shape[0]
        trg_vocab_size = self.decoder.fc_out.out_features
        outputs = torch.zeros(t_len, batch_size, trg_vocab_size, device=Configuration.DEVICE)
        output, hidden, cell = self.encoder(src, src_len)
        hidden = hidden[:, :batch_size, :]
        cell = cell[:, :batch_size, :]
        input = trg[0, :]
        for t in range(1, t_len):
            print("t:", t)
            output, hidden, cell = self.decoder(input, hidden, cell)
            print("output:", output)
            print("hidden:", hidden)
            print("cell:", cell)
            outputs[t] = output
            teacher_force = random.random() < Configuration.TEACHER_FORCING_RATIO  # nosec B311
            top1 = output.argmax(1)
            input = trg[t] if teacher_force else top1
        return outputs


def load_model(
    input_dim: int | None = None, output_dim: int | None = None, is_eval: bool = False
) -> Tuple[Seq2Seq | None, Vocab | None, Vocab | None]:
    """Load a saved model and vocabs if available, or construct a new one."""
    if input_dim is None or output_dim is None:
        if os.path.exists(Configuration.MODEL_SAVE_PATH):
            try:
                checkpoint = torch.load(Configuration.MODEL_SAVE_PATH)  # nosec B614
                src_vocab = checkpoint["src_vocab"]
                trg_vocab = checkpoint["trg_vocab"] if not is_eval else None
                input_dim = len(src_vocab)
                output_dim = len(trg_vocab) if trg_vocab is not None else None
            except Exception as e:
                print(f"Error loading the vocabularies: {e}")
        else:
            print("No saved model found.")
            src_vocab, trg_vocab = None, None
            return None, None, None
    encoder = Encoder(input_dim)
    decoder = Decoder(output_dim)
    model = Seq2Seq(encoder, decoder)
    model = model.to(Configuration.DEVICE)
    if os.path.exists(Configuration.MODEL_SAVE_PATH):
        try:
            checkpoint = torch.load(Configuration.MODEL_SAVE_PATH)  # nosec B614
            model.load_state_dict(checkpoint["model_state_dict"])
            src_vocab = checkpoint["src_vocab"]
            trg_vocab = checkpoint["trg_vocab"] if not is_eval else None
            print("Loaded saved model and vocabularies.")
        except Exception as e:
            print(f"Error loading the model and vocabularies: {e}")
    else:
        print("No saved model found.")
    return model, src_vocab, trg_vocab


def train_model(model: Seq2Seq, data_iterator: DataLoader, src_vocab: Vocab, trg_vocab: Vocab) -> None:
    """Train the model for configured epochs and save checkpoints."""
    optimizer = Adam(model.parameters())
    PAD_IDX = src_vocab["<pad>"] if "<pad>" in src_vocab else None
    # EOS index unused in current loss; PAD masking is sufficient.
    criterion = CrossEntropyLoss(ignore_index=PAD_IDX)

    print(f"Total number of samples: {len(data_iterator.dataset)}")

    for epoch in range(Configuration.EPOCHS):
        model.train()
        epoch_loss = 0

        with tqdm(total=len(data_iterator), desc=f"Epoch {epoch + 1}", unit="batch") as pbar:
            for _, batch in enumerate(data_iterator):
                src, trg, src_len, trg_len = batch
                src = src.to(Configuration.DEVICE)
                trg = trg.to(Configuration.DEVICE)

                optimizer.zero_grad()
                print(src_len)
                print(trg_len)
                # Exclude the <eos> token from trg input to the model
                output = model(src, src_len, trg[:-1])

                output_dim = output.shape[-1]

                # Compute mask to apply to the loss, to avoid taking into account the <pad> tokens
                non_pad_mask = trg[:-1].view(-1).ne(PAD_IDX)

                # Apply mask to output and trg
                print(output.shape)
                print(trg.shape)

                output_masked = output.view(-1, output_dim)[non_pad_mask]
                trg_masked = trg[:-1].view(-1)[non_pad_mask]

                # Reshape the tensors
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
            # Save the model after each epoch
            save_model(model, src_vocab, trg_vocab)
        except Exception as e:
            print(f"Error saving the model: {e}")


def save_model(model: Seq2Seq, src_vocab: Vocab, trg_vocab: Vocab) -> None:
    """Persist model parameters with associated vocabularies."""
    checkpoint = {
        "model_state_dict": model.state_dict(),
        "src_vocab": src_vocab,
        "trg_vocab": trg_vocab,
    }
    torch.save(checkpoint, Configuration.MODEL_SAVE_PATH)


def main() -> None:
    data_folder = os.path.join(os.getcwd(), "data")
    before_folder = os.path.join(data_folder, "before_mst")
    after_folder = os.path.join(data_folder, "after_mst")
    html_pairs = HtmlDataPreprocessor.load_html_pairs(before_folder, after_folder)

    src_vocab, trg_vocab = HtmlDataPreprocessor.build_vocab(html_pairs)

    dataset = HtmlDataset(html_pairs, src_vocab, trg_vocab)
    collate_fn = CollateFunction(src_vocab, trg_vocab).collate_batch
    data_iterator = DataLoader(
        dataset,
        batch_size=Configuration.BATCH_SIZE,
        shuffle=True,
        collate_fn=collate_fn,
        drop_last=True,
    )

    model, _, _ = load_model(len(src_vocab), len(trg_vocab), is_eval=False)
    train_model(model, data_iterator, src_vocab, trg_vocab)


if __name__ == "__main__":
    main()
