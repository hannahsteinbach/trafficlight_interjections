# *You Are Coalition Partners!*—Alignment and Conflict in the Traffic Light Coalition Through Interjections and Policy Topics 🚦 

This repository contains the code for my Master's thesis analyzing how verbal interjections are used among the three parties of the German Traffic Light Coalition to express alignment and conflict. <br><br>


## Preprocessing Parliamentary Protocols
The script preprocess.py takes XML-structured parliamentary protocols ([Bundestag Open Data](https://www.bundestag.de/services/opendata)) and generates a structured CSV file extracting the following features:

| Category           | Columns                                                                                                                                                                                                                                     | Description                                                                                                                                                                                                                |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **General Debate** | `Filename` <br> `Period` <br> `Date` <br> `Speech #` <br> `Paragraph #`                                                                                                                                                                     | Identifiers for each speech and paragraph, including the file, legislative period, debate date, speech number, and paragraph ID within that speech.                                                                        |
| **Speaker**        | `Speaker` <br> `Role` <br> `Gender` <br> `Party`                                                                                                                                                                                            | Metadata about the person delivering the speech: name, role (optional; e.g., *chancellor*), gender, and party affiliation. Always filled, also as context if a row corresponds to an interjection.                         |
| **Paragraph**      | `Paragraph` <br> `Paragraph tokens` <br> `paragraph_token_count` <br> `Quote`                                                                                                                                                               | The speech paragraph text itself, tokenized version, number of tokens, and whether the paragraph is a quotation (i.e., the speaker cites something). Always filled, also as context if a row corresponds to an interjection. |
| **Interjection**   | `Interjection` <br> `Interjection Text` <br> `Verbal interjection` <br> `Nonverbal interjection` <br> `Interjection type` <br> `Interjection tokens` <br> `interjection_token_count` <br> `Directed at (Person)` <br> `Directed at (Party)` | Information about paragraphs that are interjections (reactions to speech). Includes type, verbal/nonverbal distinction, text (if any), tokenized text and count, and target (person or party). Empty for regular speech paragraphs.                   |
| **Interjector**    | `Interjector` <br> `Interjector Gender` <br> `Interjector Party`                                                                                                                                                                            | Metadata about who is reacting to a speech, including name, gender, and party. Defaults to "unknown" if not identified. If a whole party or some members interject (common for applause), Interjector is `all` or `some`. Empty for regular speech paragraphs.                                    |
| **Context**        | `Agenda Item` <br> `Context` <br> `Supplementary Context` <br> `Previous Paragraphs` <br> `Previous Interjections`                                                                                                                          | Surrounding context for a paragraph or interjection. Includes agenda item, (supplementary) context, up to two previous paragraphs by the speaker, and prior interjections (with type, text, and party info).                 |


**Notes**
- Interjection includes any reaction (verbal or nonverbal), not limited to the type `Zuruf`.
- *Verbal types*: `Zuruf` (verbal interjection), `Gegenruf` (counter-interjection), `Widerspruch` (objection), `Zustimmung` (agreement)
- *Nonverbal types*: `Beifall` (applause), `Lachen` (laughter), `Heiterkeit` (amusement), `Unruhe` (commotion)
- Default target (`Directed at`) is the speaker, unless otherwise specified in the protocol.

To generate annotated dataframes for other legislative periods (works for XML files starting from the 18th legislative period), update the content in `data/` and run `preprocess.py`.

The structured CSV for the entire 20th legislative period can be found on [HuggingFace](https://huggingface.co/datasets/hannahsteinbach/bundestag-20/tree/main). <br> <br> <br>

## RQs
Code used to answer the research questions is in `RQs/`.

The dataframe of all verbal interjections between SPD, FDP, and Greens, annotated with CAP-annotated topic labels and interjection types, is located in `annotations/final_labels_rq2`.  <br> <br> <br>


## How to use interjection and topic model

Run the prediction script:

```python predict.py input_file.csv output_file.csv [flags]```
<br><br>

### Flags
```--predict_topics```<br>Predict the topic of each paragraph. <br>
Default behavior: Uses 1 previous paragraph as context (requires column: `Previous Paragraphs`) and includes the agenda block (requires columns: `Agenda Item`, `Context`, `Supplementary Context`).

```--predict_interjections```<br>
Predict interjection type

```--no_previous_paragraphs```<br>
Disable using previous paragraphs for context.

```--no_agenda_block```<br>
Disable including the agenda block in predictions. <br><br>

#### Examples
Default interjection + topic prediction (1 previous paragraph + agenda block): <br>
```python predict.py input_file.csv output_file.csv --predict_interjections --predict_topics```

Interjection + topic prediction without previous paragraph and agenda block: <br>
```python predict.py input_file.csv output_file.csv --predict_topics --predict_interjections --no_previous_paragraphs --no_agenda_block```

Only topic prediction: <br>
```python predict.py input_file.csv output_file.csv --predict_topics```

Only interjection prediction:<br>
```python predict.py input_file.csv output_file.csv --predict_interjections```<br><br><br>


### Topic Classification Model
Our topic classification model is a fine-tuned parlBERT based on [chkla/parlbert-topic-german](https://huggingface.co/chkla/parlbert-topic-german) ([Klamm et al., 2022](https://aclanthology.org/2022.parlaclarin-1.13/)). <br>
It was fine-tuned on CAP-annotated quasi-sentences by [Breunig et al., 2023](https://www.tandfonline.com/doi/abs/10.1080/13572334.2021.2010395?casa_token=MTatRdAME5oAAAAA:nUMscjmO9f69wKeFguwpfxlorG5f8QXpLELZQ4hMczVhN8jiuyvTIsOmLhnSJlDXN0RmKDI4aNj2MA) ([dataset](https://www.gpa.uni-konstanz.de/data/)) and manual annotations. <br>
Our fine-tuned model is available on [HuggingFace](https://huggingface.co/hannahsteinbach/finetuned_parlBERT_phaseIII). <br><br><br>

### Requirements
All necessary dependencies are listed in `environment.yml`.  <br> <br><br>


### Contact
For questions, contact the author: **hannahsteinbach0312@gmail.com**. <br> <br><br>


###  License
- All files in `data/`  were directly downlaoded from https://www.bundestag.de/services/opendata.
- The tool for structuring files and the manual annotations are under **CC-BY-NC-4.0**. <br> <br> <br>


**Enjoyyyyy** 🫧

