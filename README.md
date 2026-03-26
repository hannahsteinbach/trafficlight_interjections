
## Overview of extracted dataframe columns
| Category           | Columns                                                                                                                                                                                                                                     | Description                                                                                                                                                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **General Debate** | `Filename` <br> `Period` <br> `Date` <br> `Speech #` <br> `Paragraph #`                                                                                                                                                                     | Identifiers for each speech and paragraph, including the file, legislative period, debate date, speech number, and paragraph ID within that speech.                                                                        |
| **Speaker**        | `Speaker` <br> `Role` <br> `Gender` <br> `Party`                                                                                                                                                                                            | Metadata about the person delivering the speech: name, role (optional; e.g., *chancellor*), gender, and party affiliation. Always filled, also as context if a row corresponds to an interjection.                         |
| **Paragraph**      | `Paragraph` <br> `Paragraph Tokens` <br> `paragraph_token_count` <br> `Quote`                                                                                                                                                               | The speech paragraph text itself, tokenized version, number of tokens, and whether the paragraph is a quotation (i.e., the speaker cites something). Always filled, also as context if a row corresponds to an interjection. |
| **Interjection**   | `Interjection` <br> `Interjection Text` <br> `Verbal Interjection` <br> `Nonverbal Interjection` <br> `Interjection Type` <br> `Interjection Tokens` <br> `interjection_token_count` <br> `Directed at (Person)` <br> `Directed at (Party)` | Information about paragraphs that are interjections (reactions to speech). Includes type, verbal/nonverbal distinction, text (if any), tokenized text and count, and target (person or party). Empty for regular speech paragraphs.                   |
| **Interjector**    | `Interjector` <br> `Interjector Gender` <br> `Interjector Party`                                                                                                                                                                            | Metadata about who is reacting to a speech, including name, gender, and party. Defaults to "unknown" if not identified. If a whole party or some members interject (common for applause), Interjector is `all` or `some`. Empty for regular speech paragraphs.                                    |
| **Context**        | `Agenda Item` <br> `Context` <br> `Supplementary Context` <br> `Previous Paragraphs` <br> `Previous Interjections`                                                                                                                          | Surrounding context for a paragraph or interjection. Includes agenda item, (supplementary) context, up to two previous paragraphs by the speaker, and prior interjections (with type, text, and party info).                 |


**Notes**:

In this context, interjection includes any reaction (verbal or nonverbal) and is not limited to the specific type `Zuruf` (verbal interjection).

**Verbal Types**: `Zuruf` (verbal interjection), `Gegenruf` (counter-interjection), `Widerspruch` (objection), `Zustimmung` (agreement)

**Nonverbal Types**: `Beifall` (applause), `Lachen` (laughter), `Heiterkeit` (amusement), `Unruhe` (commotion)

Default target (`Directed at`) is the speaker, unless specified otherwise in the protocol. <br> <br> <br>


## How to use interjection and topic model

Run the script with:

```python predict.py input_file.csv output_file.csv [flags]```
<br><br>

#### Flags
```--predict_topics```<br>Predict the topic of each paragraph. <br>
Default behavior: Uses 1 previous paragraph as context (requires column: `Previous Paragraphs`) and includes the agenda block (requires columns: `Agenda Item`, `Context`, `Supplementary Context`).

```--predict_interjections```<br>
Predict interjection type

```--no_previous_paragraphs```<br>
Disable using previous paragraphs for context.

```--no_agenda_block```<br>
Disable including the agenda block in predictions. <br>

#### Examples
Default interjection + topic prediction (1 previous paragraph + agenda block): <br>
```python predict.py input_file.csv output_file.csv --predict_interjections --predict_topics```

Interjection + topic prediction without previous paragraph and agenda block: <br>
```python predict.py input_file.csv output_file.csv --predict_topics --predict_interjections --no_previous_paragraphs --no_agenda_block```

Only topic prediction: <br>
```python predict.py input_file.csv output_file.csv --predict_topics```

Only interjection prediction:<br>
```python predict.py input_file.csv output_file.csv --predict_interjections```
