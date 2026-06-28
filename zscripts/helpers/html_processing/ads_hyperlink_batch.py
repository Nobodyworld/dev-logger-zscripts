import logging
import os
import re
from typing import Dict, List, Tuple

import pandas as pd
from bs4 import BeautifulSoup
from helpers.utilities.paths import org_path


def load_data(excel_file: str) -> Dict[str, Dict[str, str]]:
    df = pd.read_excel(excel_file)
    df.drop_duplicates(subset="words", keep="first", inplace=True)
    return df.set_index("words").to_dict("index")


def process_file(
    input_file: str, words_dict: Dict[str, Dict[str, str]], max_ads: int
) -> Tuple[str, int]:
    with open(input_file, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "html.parser")
    linked_words: List[str] = []
    ads_count = 0

    def replace_with_case(match: re.Match[str], word_escaped: str, new_word: str) -> str:
        keyword = match.group()
        is_lower = keyword.islower()
        # find the keyword in new_word and replace it according to the case
        # TODO - add global path function
        return re.sub(
            rf"\b{word_escaped}\b", keyword if is_lower else keyword.title(), new_word, flags=re.I
        )

    for word, data in words_dict.items():
        if ads_count >= max_ads:
            break

        if word in linked_words:
            continue

        word_escaped: str = re.escape(word)
        regex: re.Pattern[str] = re.compile(rf"\b{word_escaped}\b", flags=re.I)

        for tag in soup.find_all(text=regex):
            if "h2" not in [parent.name for parent in tag.find_parents()]:
                new_word = (
                    data["with_strong"]
                    if tag.parent.name == "li" and tag.strip().startswith(word)
                    else data["code"]
                )

                def _subst(
                    m: re.Match[str],
                    word_escaped: str = word_escaped,
                    new_word: str = new_word,
                ) -> str:
                    return replace_with_case(m, word_escaped, new_word)

                new_text = re.sub(regex, _subst, tag.string, count=1)
                tag.replace_with(BeautifulSoup(new_text, "html.parser"))
                linked_words.append(word)
                ads_count += 1
                break

    return str(soup), ads_count


def add_hyperlinks(
    input_folder: str, output_folder: str, excel_file: str, max_ads: int, report_file: str
) -> None:
    logging.basicConfig(filename=report_file, level=logging.INFO)
    words_dict = load_data(excel_file)

    html_files = [f for f in os.listdir(input_folder) if f.endswith(".html")]
    for html_file in html_files:
        logging.info("Processing %s...", html_file)
        input_file = os.path.join(input_folder, html_file)
        output_file = os.path.join(output_folder, html_file)

        html, ads_count = process_file(input_file, words_dict, max_ads)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

        logging.info("Finished processing %s. %d ad(s) added.", html_file, ads_count)


if __name__ == "__main__":
    input_folder = str(org_path("Revenue Streams", "Blogs", "format_ai", "after_mst"))
    output_folder = str(org_path("Revenue Streams", "Blogs", "format_ai", "ads_after_mst"))
    excel_file = str(org_path("Revenue Streams", "Blogs", "format_ai", "data.xlsx"))
    max_ads = 15
    report_file = str(org_path("Revenue Streams", "Blogs", "format_ai", "ads_report.txt"))

    add_hyperlinks(input_folder, output_folder, excel_file, max_ads, report_file)
