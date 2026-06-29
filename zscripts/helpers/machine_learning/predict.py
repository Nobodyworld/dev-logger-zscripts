import glob
import os
from typing import List, Optional

import torch
from helpers.utilities.paths import org_path
from model_work import Configuration, HtmlDataPreprocessor, HtmlDataset, load_model
from torch import nn
from torchtext.vocab import Vocab


def sample_model(
    model: nn.Module, src_vocab: Vocab, trg_vocab: Vocab, text: str, max_seq_len: int
) -> Optional[List[str]]:
    try:
        model.eval()

        tokens = list(HtmlDataPreprocessor.TOKENIZER(text))
        tokens = [src_vocab["<sos>"]] + [src_vocab[token] for token in tokens] + [src_vocab["<eos>"]]
        src_tensor = torch.LongTensor(tokens).unsqueeze(1).to(Configuration.DEVICE)
        print("src_tensor:", src_tensor)
        print("src_tensor shape:", src_tensor.shape)
        print("len(tokens):", len(tokens))

        # Ensure the source tensor has the maximum sequence length
        src_tensor = torch.cat(
            (
                src_tensor,
                torch.zeros(max_seq_len - len(tokens), 1, dtype=torch.long).to(Configuration.DEVICE),
            )
        )

        # Define the maximum target sequence length
        max_tgt_len = max_seq_len + 2  # Add 2 for <sos> and <eos> tokens

        # Generate the target tensor for decoding
        tgt_tensor = torch.zeros(max_tgt_len, 1, dtype=torch.long).to(Configuration.DEVICE)
        tgt_tensor[0] = trg_vocab["<sos>"]  # Set the <sos> token

        # Pass the source and target tensors through the model
        with torch.no_grad():
            output = model(src_tensor, torch.tensor([len(tokens)]), tgt_tensor)

        print("output:", output)
        print("output shape:", output.shape)

        # Extract the predicted tokens
        output_tokens = [trg_vocab.get_itos()[t.item()] for t in output.argmax(2).squeeze()]

        return output_tokens
    except Exception as e:
        print("Error during model sampling:")
        print(str(e))
        return None


def main() -> None:
    model, src_vocab, trg_vocab = load_model()

    before_folder = str(org_path("project_user", "projects", "format_ai", "before"))
    after_folder = str(org_path("project_user", "projects", "format_ai", "after"))
    os.makedirs(after_folder, exist_ok=True)
    html_files = glob.glob(os.path.join(before_folder, "*.html"))

    # Initialize max_seq_len with a lower value
    max_seq_len = 410  # Adjust this value based on the expected maximum sequence length

    html_pairs = HtmlDataPreprocessor.load_html_pairs(before_folder, after_folder)
    if model is None or src_vocab is None or trg_vocab is None:
        print("Model or vocabularies not available.")
        return
    dataset = HtmlDataset(html_pairs, src_vocab, trg_vocab)

    for file_path in html_files:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        try:
            print("Processing file:", file_path)
            # Sample the model
            predicted_tokens = sample_model(model, dataset.src_vocab, dataset.trg_vocab, content, max_seq_len)

            if predicted_tokens is None:
                print("Prediction failed for file:", file_path)
                continue

            # Write the output to the corresponding file in the after folder
            output_file_path = os.path.join(after_folder, os.path.basename(file_path))
            with open(output_file_path, "w", encoding="utf-8") as output_file:
                output_file.write(" ".join(predicted_tokens))

            print("Processed file:", file_path)
            break  # Break the loop after processing one file
        except Exception as e:
            print("Error processing file:", file_path)
            print("Error details:", str(e))

    print(f"Finished processing {len(html_files)} files.")
