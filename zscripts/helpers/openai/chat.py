import datetime
import json
import logging
import os
from pathlib import Path
from time import sleep, time
from typing import Any, Dict, List, Optional, Sequence

import openai
from helpers.utilities.paths import org_path

logger = logging.getLogger(__name__)


def open_file(filepath: str) -> str:
    """Read text file and return contents.

    Args:
        filepath: Path to the file to read.

    Returns:
        File contents as string.
    """
    path = Path(filepath)
    return path.read_text(encoding="utf-8")


def save_file(filepath: str, content: str) -> None:
    """Save content to text file.

    Args:
        filepath: Path where to save the file.
        content: Content to write.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def load_json(filepath: str) -> Dict[str, Any]:
    """Load JSON file and return parsed dictionary.

    Args:
        filepath: Path to the JSON file.

    Returns:
        Parsed JSON data.
    """
    path = Path(filepath)
    with path.open("r", encoding="utf-8") as infile:
        return json.load(infile)


def save_json(filepath: str, payload: Dict[str, Any]) -> None:
    """Save dictionary as JSON file.

    Args:
        filepath: Path where to save the JSON file.
        payload: Data to serialize.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as outfile:
        json.dump(payload, outfile, ensure_ascii=False, sort_keys=True, indent=2)


def timestamp_to_datetime(unix_time: float) -> str:
    """Convert Unix timestamp to formatted datetime string.

    Args:
        unix_time: Unix timestamp.

    Returns:
        Formatted datetime string.
    """
    return datetime.datetime.fromtimestamp(unix_time).strftime("%A, %B %d, %Y at %I:%M%p %Z")


def gpt3_embedding(content: str, engine: str = "text-embedding-ada-002") -> List[float]:
    """Generate embeddings for content using OpenAI.

    Args:
        content: Text content to embed.
        engine: Embedding model to use.

    Returns:
        List of embedding vectors.
    """
    content = content.encode(encoding="ASCII", errors="ignore").decode()  # fix any UNICODE errors
    response = openai.Embedding.create(input=content, engine=engine)
    vector = response["data"][0]["embedding"]  # this is a normal list
    return vector


def chatgpt_completion(messages: Sequence[Dict[str, str]], model: str = "gpt-3.5-turbo") -> str:
    """Generate ChatGPT completion for messages.

    Args:
        messages: Sequence of message dictionaries.
        model: Model to use for completion.

    Returns:
        Generated text response.
    """
    response = openai.ChatCompletion.create(model=model, messages=list(messages))
    text = response["choices"][0]["message"]["content"]
    filename = "%s_chat.txt" % time()
    logs_dir = org_path("gpt3_logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    save_file(str(logs_dir / filename), str(messages) + "\n\n==========\n\n" + text)
    return text


def gpt3_completion(
    prompt: str,
    engine: str = "text-davinci-003",
    temp: float = 0.0,
    top_p: float = 1.0,
    tokens: int = 400,
    freq_pen: float = 0.0,
    pres_pen: float = 0.0,
    stop: Optional[List[str]] = None,
) -> str:
    """Generate GPT-3 completion for prompt.

    Args:
        prompt: Input prompt.
        engine: Model engine to use.
        temp: Temperature parameter.
        top_p: Top-p parameter.
        tokens: Maximum tokens.
        freq_pen: Frequency penalty.
        pres_pen: Presence penalty.
        stop: Stop sequences.

    Returns:
        Generated text response.
    """
    max_retry = 5
    retry = 0
    prompt = prompt.encode(encoding="ASCII", errors="ignore").decode()
    if stop is None:
        stop = ["USER:", "LIV:"]
    while True:
        try:
            response = openai.Completion.create(
                engine=engine,
                prompt=prompt,
                temperature=temp,
                max_tokens=tokens,
                top_p=top_p,
                frequency_penalty=freq_pen,
                presence_penalty=pres_pen,
                stop=stop,
            )
            text = response["choices"][0]["text"].strip()
            filename = "%s_gpt3.txt" % time()
            logs_dir = org_path("gpt3_logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            save_file(str(logs_dir / filename), prompt + "\n\n==========\n\n" + text)
            return text
        except Exception as oops:
            retry += 1
            if retry >= max_retry:
                return "GPT3 error: %s" % oops
            logger.error("Error communicating with OpenAI: %s", oops)
            sleep(1)


def flatten_convo(conversation: Sequence[Dict[str, str]]) -> str:
    """Flatten conversation to readable string.

    Args:
        conversation: Sequence of conversation messages.

    Returns:
        Formatted conversation string.
    """
    convo = ""
    for i in conversation:
        convo += "%s: %s\n" % (i["role"].upper(), i["content"])
    return convo.strip()


def main() -> None:
    """Run interactive LIV AI conversation."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        key_file = org_path("key_openai.txt")
        if key_file.exists():
            api_key = open_file(str(key_file))
    if not api_key:
        raise ValueError("No OpenAI API key found in OPENAI_API_KEY env var or key_openai.txt file")

    openai.api_key = api_key
    conversation: List[Dict[str, str]] = []
    conversation.append(
        {
            "role": "system",
            "content": (
                "I am an AI named LIV. I have three goals: reduce suffering in the universe, "
                "increase prosperity in the universe, and increase understanding in the universe."
            ),
        }
    )
    while True:
        # get user input
        try:
            a = input("\n\nUSER: ")
        except (EOFError, KeyboardInterrupt):
            break
        conversation.append({"role": "user", "content": a})
        flat = flatten_convo(conversation)
        # infer user intent, disposition, valence, needs
        prompt_file = org_path("prompt_anticipate.txt")
        if not prompt_file.exists():
            logger.error("Prompt file not found: %s", prompt_file)
            continue
        prompt = open_file(str(prompt_file)).replace("<<INPUT>>", flat)
        anticipation = gpt3_completion(prompt)
        print("\n\nANTICIPATION: %s" % anticipation)
        # summarize the conversation to the most salient points
        prompt_file = org_path("prompt_salience.txt")
        if not prompt_file.exists():
            logger.error("Prompt file not found: %s", prompt_file)
            continue
        prompt = open_file(str(prompt_file)).replace("<<INPUT>>", flat)
        salience = gpt3_completion(prompt)
        print("\n\nSALIENCE: %s" % salience)
        # update SYSTEM based upon user needs and salience
        conversation[0]["content"] = (
            "I am an AI named LIV. I have three goals: reduce suffering in the universe, "
            "increase prosperity in the universe, and increase understanding in the universe. "
            "I am in the middle of a conversation: %s. I anticipate the user needs: %s. "
            "I will do my best to fulfill my objectives." % (salience, anticipation)
        )
        # generate a response
        response = chatgpt_completion(conversation)
        conversation.append({"role": "assistant", "content": response})
        print("\n\nLIV: %s" % response)


if __name__ == "__main__":
    main()
