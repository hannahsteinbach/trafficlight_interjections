import os
import spacy
from tqdm import tqdm
import re
import regex
import xml.etree.ElementTree as ET
import pandas as pd
import itertools

nlp = spacy.load("de_core_news_sm")

# refer to stammdaten to get gender
stammdaten = "MdB-Stammdaten/MDB_STAMMDATEN.XML"
sd_tree = ET.parse(stammdaten)
sd_root = sd_tree.getroot()

# Load the XML file
data_directory = 'data'


# build index once
def build_mdb_index(root):
    index = {}

    # auto-build from XML
    for mdb in tqdm(root.findall('./MDB'), desc="Building index", unit="MDB"):
        for name in mdb.findall('.//NAMEN/NAME'):
            vorname = name.find('.//VORNAME').text or ''
            nachname = name.find('.//NACHNAME').text or ''
            adel = name.find('.//ADEL').text or ''
            praefix = name.find('.//PRAEFIX').text or ''

            full_first_name = " ".join(vorname.strip().split())
            full_last_name = " ".join(f"{adel} {praefix} {nachname}".strip().split())
            full_name = f"{full_first_name} {full_last_name}".lower().strip()

            gender = mdb.find('.//GESCHLECHT').text
            party = mdb.find('.//PARTEI_KURZ').text
            periods = {wp.find('.//WP').text for wp in mdb.findall('.//WAHLPERIODEN/WAHLPERIODE')}

            entry = {
                "gender": gender,
                "party": party,
                "name": f"{full_first_name} {full_last_name}",
                "periods": periods
            }

            index[full_name] = entry

    # ----- manual additions for government figures not in Bundestag -----
    manual_entries = [
        {"name": "Joachim Stamp",    "gender": "männlich", "party": "FDP",    "periods": {"20"}},
        {"name": "Ulrich Grötsch",  "gender": "männlich", "party": "SPD",    "periods": {"20"}},
        {"name": "Nancy Faeser",    "gender": "weiblich","party": "SPD",    "periods": {"20"}},
        {"name": "Anne Spiegel",    "gender": "weiblich","party": "GRUENE", "periods": {"20"}},
        {"name": "Klara Geywitz",   "gender": "weiblich","party": "SPD",    "periods": {"20"}},
        {"name": "Christine Lambrecht", "gender": "weiblich", "party": "SPD", "periods": {"20"}},
        {"name": "Wolfgang Schmidt","gender": "männlich", "party": "SPD",    "periods": {"20"}}
    ]

    for person in manual_entries:
        key = person["name"].lower()
        entry = {
            "gender": person["gender"],
            "party": person["party"],
            "name": person["name"],
            "periods": person["periods"]
        }
        index[key] = entry

    return index



index = build_mdb_index(sd_root)

def get_gender_from_name(full_name, index, period):
    def normalize_name(name):
        titles_to_remove = ["Dr.-Ing.", "Dr. h. c.", "Dr.", "Prof.", "h. c."]
        for title in titles_to_remove:
            name = name.replace(title, "")
        return name.strip()

    normalized = normalize_name(full_name).lower()
    names = normalized.split()
    first = names[0] if names else ""
    second = names[1] if len(names) > 1 else ""
    last = names[-1] if names else ""

    # 1. Exact match, check if name + legislature period match
    if normalized in index:
        entry = index[normalized]
        if str(period) in entry["periods"]:
            return entry
    return None


def get_metadata(name):
    titel = name.findtext('titel', default='')
    vorname = name.findtext('vorname', default='')
    nachname = name.findtext('nachname', default='')

    speaker_name = f"{titel} {vorname} {nachname}".strip()
    result = get_gender_from_name(speaker_name, index, period)
    speaker_gender = result["gender"] if result else "Unknown"
    speaker_name_clean = result["name"] if result else speaker_name

    fraktion_text = name.findtext('fraktion', default='Unknown')
    if fraktion_text != 'Unknown':
        speaker_party = fraktion_text
    else:
        result = get_gender_from_name(speaker_name_clean, index, period)
        speaker_party = result["party"] if result and "party" in result else "Unknown"

    speaker_role = name.find('rolle')
    speaker_role_long = speaker_role.findtext('rolle_lang') if speaker_role is not None else ''
    speaker_role_short = speaker_role.findtext('rolle_kurz') if speaker_role is not None else ''

    return speaker_name_clean, speaker_gender, speaker_party, speaker_role_long


def clean_presidency_name(name):
    """Only obtain name of presidency, without title at front and colon at end"""
    name = re.sub(r"(?i)^(präsident(?:in)?|vizepräsident(?:in)?|alterspräsident(?:in)?)\s+", "", name)
    name = re.sub(r":$", "", name)
    return name.strip()

def handle_sub(element):
    parts = []

    for node in element.iter():
        if node.tag == 'sub': #so co2 is not separated
            if node.text:
                parts.append(node.text)

            if node.tail:
                if not node.tail.startswith((' ', '.', ',', '!', '?', ':', ';', '-', '–', '—')):
                    parts.append(' ')
                parts.append(node.tail)
        elif node == element:
            if node.text:
                parts.append(node.text)
        else:
            if node.tail:
                parts.append(node.tail)

    return ''.join(parts).strip()



replacements = {
    'BÜNDNISSES 90/DIE GRÜNEN': 'BÜNDNIS 90/DIE GRÜNEN',
    'LINKEN': 'LINKE',
    'Die Linke': 'LINKE',
    'Linken': 'LINKE',
    'FPD': 'FDP',
    'SDP': 'SPD',
    'CDU': 'CDU/CSU'
}

all_speech_data = []

no_colon_speechacts = ["Lachen", "Widerspruch", "Beifall", "Heiterkeit", "Zurufe", "Zuruf", "Unruhe", "Zustimmung", "Gegenruf", "Gegenrufe"]
colon_speechacts = ["Zurufe", "Zuruf"]
parties = ["Die Linke", "LINKE", "LINKEN", "DIE LINKE", "Linken", "CDU", "CDU/CSU", "CDU/ CSU", "BÜNDNIS 90/DIE GRÜNEN", "BÜNDNISSES 90/DIE GRÜNEN",
           'BÜNDNIS 90/Die Grünen', 'GRÜNE', 'BÜNDIS 90/DIE GRÜNEN', "SPD", "FDP", "FPD", "AfD", "Die PARTEI", "Der PARTEI", "parteilos", "LKR",
           "DP", "CVP", "GB/ BHE", "GB/BHE", "DA", "DZP", "BSW", "fraktionslos"]
speechact_pattern_no_colon = (
    rf"(?P<speechact>(?:{'|'.join(no_colon_speechacts)})(?:\s+(?:und)\s+(?:{'|'.join(no_colon_speechacts)}))*)(?!\s*:)"
)
speechact_pattern_colon = rf"(?P<speechact>{'|'.join(colon_speechacts)})"

escaped_parties = [re.escape(p) for p in parties]
party_pattern = "|".join(escaped_parties)
party_pattern_bracket = rf"(?:{'|'.join(re.escape(p) for p in parties)})"

mp_party_pattern = r"""
(?:(?:Abg\.|Dr\.|Dr\.-Ing\.|Dr\. h\. c\.| h\. c\.|Prof\.|Bundesminister(?:in)?s?)\s+)?      # optional title
(
    \p{Lu}[\p{L}\-]+\.?                                  # first part
    (?:\s+(?!(?:und)\b)(?:[a-zäöü]{1,3}|\p{Lu}[\p{L}\-]*\.?))*         # middle/last parts, exclude "und" to avoid mistakes
)
\s*
(?:\[[^\]]*\]\s*)?                                         # optional location
\[\s*(""" + party_pattern_bracket + r""")\s*\]             # party in brackets
"""



mp_party_regex = regex.compile(mp_party_pattern, regex.VERBOSE)


pattern_colon = r".*: "  # matches anything between square brackets# matches multiple speech acts in one interjection
# Matches the party of the interjection with a colon
pattern_party_colon = r"(?:\[[^\]]*\]\s*)?\[([A-Za-zÜÄÖ0-9/\s]*[A-Z])\]"
# Matches the person of the interjection with a colon(occurs before party)
pattern_person_colon = r"^(?:Abg\.\s*)?(.*?)(?:,\s*Bundesminister(?:in)?)?\s*(?:\[|:)"
pattern_text_colon =  r"\]?(.*?):\s*(.*)" # match text after potentially ]: (or there can be something between ] and : or just :
pattern_text_colon_zuruf =  r"\:\s*(.*)" # match text of interjection
pattern_speechact = "|".join(no_colon_speechacts) # all speechacts from list NOT preceding a colon


## Get meta information for colon speechacts (Zurufe)
pattern_speechact_colon = "|".join(colon_speechacts)

# catch multiple parties in "Zurufe"
multi_party_pattern = rf"(?:den|der|des|dem)?\s*{party_pattern_bracket}(?:\s*,\s*(?:den|der|des|dem)?\s*{party_pattern_bracket})*(?:\s+und\s+(?:den|der|des|dem)?\s*{party_pattern_bracket})?"
# Matches: Zuruf von der AfD: Hört! Hört!


# Matches: Gegenruf des Abg. Sebastian Hartmann [SPD]: Frau Lindholz, das sind Fakten!
pattern_gegenruf = regex.compile(
    rf"(?P<interjection_type>Gegenruf[e]?)\s+"
    rf"(?:des\s+Abg\.\s+|der\s+Abg\.\s+)?"  # optional Abg.
    rf"(?:(?:Dr\.|Dr\.-Ing\.|Dr\. h\. c\.|h\. c\.|Prof\.|Bundesminister(?:in)?s?)\s+)?"  # optional title
    rf"(?P<speaker>[\p{{Lu}}\p{{Lt}}][\p{{L}}\.\-]+(?:\s[\p{{L}}\.\-]+)*)\s*"  # speaker name
    rf"(?:\[[^\]]*\])?\s+"  # optional location
    rf"\[(?P<party>{party_pattern})\]\s*:\s*"  # party in brackets
    rf"(?P<text>.+)",
    flags=regex.UNICODE
)

# Matches: Gegenruf der AfD: ...
pattern_gegenruf_nospeaker = regex.compile(
    rf"(?P<interjection_type>Gegenruf[e]?)\s+"
    rf"(?:von (?:dem|der|den)|vom)\s+"
    rf"(?:(?P<party>{party_pattern})|(?P<speaker>[^\:]+))\s*:\s*"
    rf"(?P<text>.+)",
    flags=regex.UNICODE
)

# Matches: Zurufe der Abg. Merle Spellerberg [...] und Jürgen Trittin [...]: ...
pattern_zurufe_named = regex.compile(
    rf"(?P<interjection_type>{pattern_speechact_colon})\s+"
    rf"(?:von|der|vom|des|dem)\s+(?P<speakers>.+?)\s*:\s*"
    rf"(?P<text>.+)",
    flags=regex.UNICODE | regex.IGNORECASE
)

pattern_zurufe_fallback = regex.compile(
    rf"(?P<speakers>(?:[\p{{L}}\.\-]+(?:\s+[\p{{L}}\.\-]+)+(?:\s*\[[^\]]+\])+\s*(?:\bund\b|,)?\s*)+):\s*(?P<text>.+)",
    flags=regex.UNICODE
)



interjection_patterns = [
    ("Gegenruf_with_speaker", pattern_gegenruf),
    ("Gegenruf_without_speaker", pattern_gegenruf_nospeaker),
    ("Zurufe_named", pattern_zurufe_named),
    ("Zurufe_fallback", pattern_zurufe_fallback)
]
#     ("Zuruf_colon", pattern_zurufe),

# Split by '--—' to capture several speech acts separately, e.g. "Beifall bei Abgeordneten der SPD – Christian Dürr [FDP]: Und Sie gar nicht? Sie waren nie dabei, Herr Daldrup?"
# important: not split WITHIN a verbal interjection (e.g. ), so only split if there is a speechact or party following

split_pattern = r" (?<= )[-–—](?= ) "

paragraph_list = []

# Keep track of speech ID's
speech_id = 0

for filename in tqdm(os.listdir(data_directory), desc="Processing files", unit="file"):
    file_path = os.path.join(data_directory, filename)
    tree = ET.parse(file_path)
    root = tree.getroot()

    period = root.attrib.get("wahlperiode")
    date = root.attrib.get("sitzung-datum")
    session = root.attrib.get("sitzung-nr")

    # Locate the session Verlauf (speech flow)
    sitzungsverlauf = root.find('sitzungsverlauf')
    if sitzungsverlauf is None:
        continue

    keywords = ["themenbereich", "teilbereich", "bereich"]

    for tagesordnungspunkt in sitzungsverlauf.findall('.//tagesordnungspunkt'):
        speeches = tagesordnungspunkt.findall('.//rede')
        speech_id = 0

        t_fett_texts = []
        t_nas_texts = []
        t_zp_nas_texts = []
        other_texts = []

        top_id = tagesordnungspunkt.attrib.get('top-id', '').strip()

        # Special case: Einzelplan -> take the first <p> as agenda
        if top_id.lower().startswith('einzelplan'):
            first_p = tagesordnungspunkt.find('./p')
            if first_p is not None and first_p.text:
                t_fett_texts.append(first_p.text.strip())

        # Loop over <p> elements
        for p in tagesordnungspunkt.findall('./p'):
            klasse = p.attrib.get('klasse', '').strip()
            text = ''.join(p.itertext()).strip()

            # Skip non-relevant paragraphs early
            if text.startswith('Drucksache'):
                continue

            # T_NaS / T_fett / T_ZP_NaS
            if 'T_fett' in klasse.split():
                t_fett_texts.append(text)
                continue
            elif 'T_NaS' in klasse.split():
                t_nas_texts.append(text)
                continue
            elif 'T_ZP_NaS' in klasse.split():
                t_zp_nas_texts.append(text)
                continue

            # Only run spaCy if keywords are present
            if any(kw in text.lower() for kw in keywords):
                doc = nlp(text)
                for i, token in enumerate(doc):
                    if any(token.text.lower().startswith(kw) for kw in keywords):
                        phrase = []
                        for j in range(i + 1, len(doc)):
                            tok = doc[j]
                            if tok.is_punct and tok.text in {".", ";", "–"}:
                                break
                            if tok.pos_ in {"NOUN", "PROPN", "CCONJ"} or tok.text == ",":
                                phrase.append(tok.text)
                            else:
                                break
                        if phrase:
                            cleaned = " ".join(phrase).replace(" ,", ",").strip()
                            # skip if it's just ", und" or similar
                            if cleaned.lower() not in {", und", ", oder", ","}:
                                other_texts.append(cleaned)

        # join texts once at the end
        t_nas = '. '.join(t_nas_texts)
        t_zp_nas = '. '.join(t_zp_nas_texts)
        other_texts = list(dict.fromkeys(other_texts))  # remove duplicates ('Bildung und Forschung. Bildung und Forschung')
        t_other = '. '.join(other_texts)

        combined_texts = t_fett_texts + other_texts
        t_fett = '. '.join(combined_texts)

        for speech in speeches:
            elements = list(speech.iter())
            speech_id += 1

            redner_p = speech.find('p[@klasse="redner"]')
            if redner_p is None:
                continue

            redner = redner_p.find('redner')
            if redner is None:
                continue

            name = redner.find('name')
            if name is None:
                continue
            speaker_name, speaker_gender, speaker_party, speaker_role_long = get_metadata(name)

            main_name = speaker_name
            main_gender = speaker_gender
            main_party = speaker_party
            main_role_long = speaker_role_long


            # Jetzt sammeln wir alle Absätze, außer den "redner"-Abschnitt
            paragraphs = []
            interjections = []


            # skip contributions by presidency + reactions to contributions by presidency to avoid wrong speaker contribution
            skip_next_paragraph = False
            skip_next_comment = False
            idx_element = 0

            use_presidency_speaker = False
            presidency_speaker = None
            presidency_gender = None
            presidency_party = None

            use_question_speaker = False
            question_speaker = None
            question_gender = None
            question_party = None

            is_intervention = False

            for element in elements:
                speaker_name_int = ""
                is_interjection = False
                interjection = None
                interjector = None
                gender_int = None
                interjector_party = None
                is_verbal_interjection = False
                is_nonverbal_interjection = False
                interjection_type = None

                # Recognizing presidency
                if element.tag == "name" and element.text:
                    name_presidency = element.text.strip()
                    if name_presidency.startswith(("Präsident", "Präsidentin", "Vizepräsident", "Vizepräsidentin",
                                             "Alterspräsident", "Alterspräsidentin")):
                        # Extract only the name (e.g., remove "Präsidentin ")
                        presidency_speaker = clean_presidency_name(name_presidency)
                        meta_info = get_gender_from_name(presidency_speaker, index, period)
                        if meta_info:
                            presidency_speaker = meta_info["name"]
                            presidency_gender = meta_info["gender"]
                            presidency_party = meta_info["party"]
                        else:
                            presidency_gender = "Unknown"
                            presidency_party = "Unknown"
                        use_presidency_speaker = True
                        is_intervention = True

                # Recognizing non-presidency + option to recognize Questions
                if element.tag == "p" and element.attrib.get("klasse") == "redner":
                    use_presidency_speaker = False
                    redner = element.find('redner')
                    if redner is not None:
                        name = redner.find('name')
                        if name is not None:
                            speaker_name_int, speaker_gender_int, speaker_party_int, speaker_role_long_int = get_metadata(
                                name)
                            speaker_name = speaker_name_int
                            speaker_gender = speaker_gender_int
                            speaker_party = speaker_party_int
                            speaker_role_long = speaker_role_long_int
                            if speaker_name_int != main_name:
                                use_question_speaker = True
                                is_intervention = True
                            else:
                                use_question_speaker = False
                                is_intervention = False
                    continue  # redner tag does not have its own paragraph

                # add actual text
                if element.tag == "p":
                    # mark quotes/citations as such
                    if element.get("klasse") == "Z":
                        is_quote = True
                    else:
                        is_quote = False

                    text = handle_sub(element)
                    idx_element += 1

                    if use_presidency_speaker:
                        # add presidency
                        paragraph_list.append({
                            'Filename': filename,
                            'Period': period,
                            'Date': date,
                            'Speech #': speech_id,
                            'Paragraph #': idx_element,
                            'Speaker': presidency_speaker,
                            'Role': "Presidency",
                            'Gender': presidency_gender,
                            'Party': presidency_party,
                            'Paragraph': text,
                            'Interjection Text': None,
                            'Interjection': False,
                            'Intervention': True,
                            'Quote': is_quote,
                            'Agenda Item': t_fett,
                            'Context': t_nas,
                            'Supplementary Context': t_zp_nas
                        })

                    elif use_question_speaker:
                        paragraph_list.append({
                            'Filename': filename,
                            'Period': period,
                            'Date': date,
                            'Speech #': speech_id,
                            'Paragraph #': idx_element,
                            'Speaker': speaker_name,
                            'Role': speaker_role_long,
                            'Gender': speaker_gender,
                            'Party': speaker_party,
                            'Paragraph': text,
                            'Interjection Text': None,
                            'Interjection': False,
                            'Intervention': True,
                            'Quote': is_quote,
                            'Agenda Item': t_fett,
                            'Context': t_nas,
                            'Supplementary Context': t_zp_nas
                        })
                    else:
                        # add normal speaker
                        paragraph_list.append({
                            'Filename': filename,
                            'Period': period,
                            'Date': date,
                            'Speech #': speech_id,
                            'Paragraph #': idx_element,
                            'Speaker': speaker_name,
                            'Role': speaker_role_long,
                            'Gender': speaker_gender,
                            'Party': speaker_party,
                            'Paragraph': text,
                            'Interjection Text': None,
                            'Interjection': False,
                            'Intervention': False,
                            'Quote': is_quote,
                            'Agenda Item': t_fett,
                            'Context': t_nas,
                            'Supplementary Context': t_zp_nas
                        })

                elif element.tag == "kommentar":
                    is_interjection = True
                    interjection_nonverbal_meta = []

                    interjection_text = element.text
                    interjection_text = re.sub(r"[()]", "", interjection_text)  # remove brackets around interjections
                     # Split the text at -–—
                    potential_parts = re.split(split_pattern, interjection_text)
                    parts = [potential_parts[0]]

                    for p in potential_parts[1:]:
                        # Check if it contains any party or speechact (only split at dash if its actually separating speechacts"
                        if (any(party in p for party in parties) or any(sa in p for sa in no_colon_speechacts)
                                or "Abg." in p or "Bundesminister" in p or "Bundesministerin" in p or "Redner" in p
                                or "Rednerin" in p or "Gegenruf" in p or "Gegenrufe" in p
                                or "Staatssekretärin" in p or "Staatssekretär" in p
                                or "Präsident" in p or "Präsidentin" in p
                                or "Vizepräsident" in p or "Vizepräsidentin" in p
                                or "Mikrofon" in p):
                            parts.append(p)
                        else:
                            # Join it to the previous part if no party/speechact
                            parts[-1] += " – " + p

                    for part in parts:
                        directed_at_party = presidency_party if use_presidency_speaker else speaker_party
                        directed_at_person = presidency_speaker if use_presidency_speaker else speaker_name

                        direction = re.search(
                            r'(?:an|auf)\s+'  # "an" or "auf"
                            r'(?P<article>den|die|das|dem)?\s*'  # optional article
                            r'(?:Abg\.\s+)?'  # optional "Abg."
                            r'(?: (?P<title>[A-Za-zÄÖÜäöüß]+\.)\s* )*'  # optional title(s)
                            r'(?P<name>[A-ZÄÖÜa-zäöüß0-9\s/-]+?)'  # name or group
                            r'(?:\s+\[[^\]]+\])*?'  # optional intermediate brackets (non-capturing)
                            r'(?:\s+\[(?P<party>[^\]]+)\])?'  # final bracket as party (allowing spaces)
                            r'\s+(?P<type>gewandt|zeigend|weisend )',  # interaction type
                            part,
                            re.IGNORECASE
                        )

                        if direction:
                            name = direction.group("name").strip()
                            party_bracket = direction.group("party")

                            if party_bracket:
                                # Example: "an den Abg. Philipp Amthor [CDU/CSU] gewandt"
                                directed_at_person = name
                                directed_at_party = replacements.get(party_bracket, party_bracket)
                            else:
                                lower_name = name.lower()
                                if any(kw in lower_name for kw in [
                                    "präsident", "vizepräsident", "bundesregierung", "regierung", "ministerium", "fraktion",
                                    "senat", "amt", "bmz"
                                ]):
                                    directed_at_person = None
                                    directed_at_party = replacements.get(name, name)
                                else:
                                    directed_at_person = None
                                    directed_at_party = replacements.get(name, name)

                        text_interjection = None

                        ### ONLY VERBAL INTERJECTIONS ("Widerspruch", "Gegenruf", "Gegenrufe", "Zuruf", "Zustimmung") WITH COLON
                        if re.findall(pattern_colon, part):
                            is_verbal_interjection = True
                            is_nonverbal_interjection = False

                            matched_any = False

                            for label, pattern in interjection_patterns[:-1]:
                                for match in pattern.finditer(part):
                                    matched_any = True
                                    interjection_type = match.groupdict().get("interjection_type")
                                    text_interjection = match.group("text")
                                    is_verbal_interjection = True
                                    is_nonverbal_interjection = False

                                    if "speakers" in match.groupdict():
                                        # Handle multiple speakers (e.g. 'Zurufe der Abg. A [SPD] und Abg. B [SPD]')

                                        raw_speakers = match.group("speakers").strip()
                                        parts_speakers = regex.split(
                                            r"\s*(?:,|\bund\b|\bsowie\b)\s+",
                                            raw_speakers,
                                            flags=regex.IGNORECASE
                                        )

                                        #exclude cases like this: Zuruf von der CDU/CSU, an die Abg. Canan Bayram [BÜNDNIS 90/DIE GRÜNEN] gewandt
                                        parts_speakers = [
                                            part for part in parts_speakers
                                            if not regex.match(r'^(an|auf)\b', part, flags=regex.IGNORECASE)
                                        ]

                                        for raw_speaker in parts_speakers:
                                            # Remove Abg. prefix
                                            raw_speaker = regex.sub(
                                                r"^(?:der|des|dem|den)?\s*(?:Abg\.|Dr\.-Ing\.|Dr\. h\. c\.|h\. c\.|Dr\.|Prof\.|Bundesminister(?:in)?s?)\s*",
                                                "",
                                                raw_speaker,
                                                flags=regex.IGNORECASE
                                            ).strip()

                                            # Remove leading articles/prepositions for party extraction:
                                            raw_speaker_clean = regex.sub(
                                                r"^(?:der|den|des|dem|vom|von der|von dem|von)\s+", "", raw_speaker.strip(),
                                                flags=regex.IGNORECASE)

                                            # Try to match name + party in brackets:
                                            match_name_party = regex.match(
                                                r"([\p{L}\-\.]+(?:\s[\p{L}\-\.]+)*)\s*\[([^\]]+)\]",
                                                raw_speaker_clean,
                                                flags=regex.UNICODE)

                                            if match_name_party:
                                                interjector, interjector_party = match_name_party.groups()
                                            else:
                                                meta_info = get_gender_from_name(raw_speaker_clean, index, period)
                                                if meta_info:
                                                    interjector = meta_info.get("name", None)
                                                    interjector_party = meta_info.get("party", None)
                                                else:
                                                # If no brackets, treat whole cleaned string as party name, no person name:
                                                    interjector = "Unknown"
                                                    interjector_party = raw_speaker_clean

                                            # Normalize party names
                                            for old, new in replacements.items():
                                                if old in interjector_party and new not in interjector_party:
                                                    interjector_party = regex.sub(rf'\b{old}\b', new, interjector_party)


                                            gender_int = None
                                            if interjector not in ["Unknown", "all", "some"]:
                                                meta_info = get_gender_from_name(interjector, index, period)
                                                if meta_info:
                                                    interjector = meta_info["name"]
                                                    gender_int = meta_info["gender"]
                                                    if interjector_party == "Unknown" or interjector_party[-1].islower():
                                                        interjector_party = meta_info["party"]

                                            if not interjector or str(interjector).strip().lower() == "none":
                                                interjector = "Unknown"

                                            paragraph_list.append({
                                                'Filename': filename,
                                                'Period': period,
                                                'Date': date,
                                                'Speech #': speech_id,
                                                'Paragraph #': idx_element,
                                                'Speaker': presidency_speaker if use_presidency_speaker else speaker_name,
                                                'Role': "Presidency" if use_presidency_speaker else speaker_role_long,
                                                'Gender': presidency_gender if use_presidency_speaker else speaker_gender,
                                                'Party': presidency_party if use_presidency_speaker else speaker_party,
                                                'Paragraph': text,
                                                'Interjection Text': text_interjection,
                                                'Interjection': is_interjection,
                                                'Intervention': is_intervention,
                                                'Quote': is_quote,
                                                'Interjector': interjector,
                                                'Interjector Gender': gender_int,
                                                'Interjector Party': interjector_party,
                                                'Verbal interjection': is_verbal_interjection,
                                                'Nonverbal interjection': is_nonverbal_interjection,
                                                'Interjection type': interjection_type,
                                                'Directed at (Person)': directed_at_person,
                                                'Directed at (Party)': directed_at_party,
                                                'Agenda Item': t_fett,
                                                'Context': t_nas,
                                                'Supplementary Context': t_zp_nas
                                            })

                                    else:
                                        # Handle only one speaker or party
                                        interjector = match.groupdict().get("speaker", "Unknown")
                                        interjector_party = match.groupdict().get("party", "Unknown")

                                        if interjector_party and interjector != "Unknown":
                                            full_blob = f"{interjector} [{interjector_party}]"
                                        else:
                                            full_blob = interjector if interjector != "Unknown" else interjector_party

                                        full_blob = regex.sub(
                                            r"\b(?:der|des|dem)?\s*Abg\.\b\s*",
                                            "",
                                            full_blob,
                                            flags=regex.IGNORECASE
                                        ).strip()

                                        match_name_party = regex.match(r"([\p{L}\-\.]+(?:\s[\p{L}\-\.]+)*)\s*\[([^\]]+)\]",
                                                                       full_blob, flags=regex.UNICODE)

                                        if match_name_party:
                                            interjector, interjector_party = match_name_party.groups()
                                        else:
                                            interjector = "Unknown"
                                            interjector_party = regex.sub(
                                                r"^(?:der|den|des|dem|vom|von der|von dem|von)\s+",
                                                "", full_blob.strip(), flags=regex.IGNORECASE
                                            )

                                        for old, new in replacements.items():
                                            if old in interjector_party and new not in interjector_party:
                                                interjector_party = regex.sub(rf'\b{old}\b', new, interjector_party)

                                        gender_int = None
                                        if interjector not in ["Unknown", "all", "some"]:
                                            meta_info = get_gender_from_name(interjector, index, period)
                                            if meta_info:
                                                interjector = meta_info["name"]
                                                gender_int = meta_info["gender"]
                                                if interjector_party == "Unknown" or interjector_party[-1].islower():
                                                    interjector_party = meta_info["party"]

                                        if not interjector or str(interjector).strip().lower() == "none":
                                            interjector = "Unknown"

                                        paragraph_list.append({
                                            'Filename': filename,
                                            'Period': period,
                                            'Date': date,
                                            'Speech #': speech_id,
                                            'Paragraph #': idx_element,
                                            'Speaker': presidency_speaker if use_presidency_speaker else speaker_name,
                                            'Role': "Presidency" if use_presidency_speaker else speaker_role_long,
                                            'Gender': presidency_gender if use_presidency_speaker else speaker_gender,
                                            'Party': presidency_party if use_presidency_speaker else speaker_party,
                                            'Paragraph': text,
                                            'Interjection Text': text_interjection,
                                            'Interjection': is_interjection,
                                            'Intervention': is_intervention,
                                            'Quote': is_quote,
                                            'Interjector': interjector,
                                            'Interjector Gender': gender_int,
                                            'Interjector Party': interjector_party,
                                            'Verbal interjection': is_verbal_interjection,
                                            'Nonverbal interjection': is_nonverbal_interjection,
                                            'Interjection type': interjection_type,
                                            'Directed at (Person)': directed_at_person,
                                            'Directed at (Party)': directed_at_party,
                                            'Agenda Item': t_fett,
                                            'Context': t_nas,
                                            'Supplementary Context': t_zp_nas
                                        })
                            if not matched_any:
                                # Zuruf not marked as such
                                label, fallback_pattern = interjection_patterns[-1]
                                matches = list(fallback_pattern.finditer(part))
                                if matches:
                                    for match in matches:
                                        matched_any = True
                                        interjection_type = "Zuruf"
                                        text_interjection = match.group("text")
                                        is_verbal_interjection = True
                                        is_nonverbal_interjection = False

                                        if "speakers" in match.groupdict():
                                            raw_speakers = match.group("speakers").strip()
                                            parts_speakers = regex.split(
                                                r"\s*(?:,|\bund\b|\bsowie\b)\s+", raw_speakers,
                                                flags=regex.IGNORECASE
                                            )

                                            # exclude cases like this: Zuruf von der CDU/CSU, an die Abg. Canan Bayram [BÜNDNIS 90/DIE GRÜNEN] gewandt
                                            parts_speakers = [
                                                part for part in parts_speakers
                                                if not regex.match(r'^(an|auf)\b', part, flags=regex.IGNORECASE)
                                            ]

                                            for raw_speaker in parts_speakers:
                                                # Remove Abg. prefix
                                                raw_speaker = regex.sub(
                                                    r"^(?:der|des|dem|den)?\s*(?:Abg\.|Dr\.-Ing\.|Dr\. h\. c\.|h\. c\.|Dr\.|Prof\.|Bundesminister(?:in)?s?)\s*",
                                                    "",
                                                    raw_speaker,
                                                    flags=regex.IGNORECASE
                                                ).strip()

                                                # Remove leading articles/prepositions for party extraction:
                                                raw_speaker_clean = regex.sub(
                                                    r"^(?:der|den|des|dem|vom|von der|von dem|von)\s+", "",
                                                    raw_speaker.strip(),
                                                    flags=regex.IGNORECASE)

                                                # Try to match name + party in brackets:
                                                match_name_party = regex.match(
                                                    r"([\p{L}\-\.]+(?:\s[\p{L}\-\.]+)*)\s*\[([^\]]+)\]",
                                                    raw_speaker_clean,
                                                    flags=regex.UNICODE)

                                                if match_name_party:
                                                    interjector, interjector_party = match_name_party.groups()
                                                else:
                                                    meta_info = get_gender_from_name(raw_speaker_clean, index, period)
                                                    if meta_info:
                                                        interjector = meta_info.get("name", None)
                                                        interjector_party = meta_info.get("party", None)
                                                    else:
                                                        # If no brackets, treat whole cleaned string as party name, no person name:
                                                        interjector = "Unknown"
                                                        interjector_party = raw_speaker_clean

                                                # Normalize party names
                                                for old, new in replacements.items():
                                                    if old in interjector_party and new not in interjector_party:
                                                        interjector_party = regex.sub(rf'\b{old}\b', new, interjector_party)

                                                gender_int = None
                                                if interjector not in ["Unknown", "all", "some"]:
                                                    meta_info = get_gender_from_name(interjector, index, period)
                                                    if meta_info:
                                                        interjector = meta_info["name"]
                                                        gender_int = meta_info["gender"]
                                                        if interjector_party == "Unknown" or interjector_party[
                                                            -1].islower():
                                                            interjector_party = meta_info["party"]

                                                if not interjector or str(interjector).strip().lower() == "none":
                                                    interjector = "Unknown"

                                                paragraph_list.append({
                                                    'Filename': filename,
                                                    'Period': period,
                                                    'Date': date,
                                                    'Speech #': speech_id,
                                                    'Paragraph #': idx_element,
                                                    'Speaker': presidency_speaker if use_presidency_speaker else speaker_name,
                                                    'Role': "Presidency" if use_presidency_speaker else speaker_role_long,
                                                    'Gender': presidency_gender if use_presidency_speaker else speaker_gender,
                                                    'Party': presidency_party if use_presidency_speaker else speaker_party,
                                                    'Paragraph': text,
                                                    'Interjection Text': text_interjection,
                                                    'Interjection': is_interjection,
                                                    'Intervention': is_intervention,
                                                    'Quote': is_quote,
                                                    'Interjector': interjector,
                                                    'Interjector Gender': gender_int,
                                                    'Interjector Party': interjector_party,
                                                    'Verbal interjection': is_verbal_interjection,
                                                    'Nonverbal interjection': is_nonverbal_interjection,
                                                    'Interjection type': interjection_type,
                                                    'Directed at (Person)': directed_at_person,
                                                    'Directed at (Party)': directed_at_party,
                                                    'Agenda Item': t_fett,
                                                    'Context': t_nas,
                                                    'Supplementary Context': t_zp_nas
                                                })

                                else:
                                    person_match = re.search(pattern_person_colon, part)
                                    party_match = re.search(pattern_party_colon, part)
                                    text_match = re.search(pattern_text_colon, part)

                                    interjector = person_match.group(1).strip() if person_match else "Unknown"
                                    interjector_party = party_match.group(1).strip() if party_match else "Unknown"
                                    text_interjection = text_match.group(2).strip() if text_match else None
                                    interjection_type = "Zuruf"

                                    gender_int = None
                                    if interjector != "all":
                                        names = " ".join(interjector.split())
                                        meta_info = get_gender_from_name(names, index, period)

                                        if meta_info:
                                            interjector = meta_info["name"]
                                            gender_int = meta_info["gender"]
                                            if interjector_party == "Unknown" or interjector_party[-1].islower():
                                                interjector_party = meta_info["party"]

                                    if interjector_party == "Unknown":
                                        interjector = "Unknown"
                                    paragraph_list.append({
                                        'Filename': filename,
                                        'Period': period,
                                        'Date': date,
                                        'Speech #': speech_id,
                                        'Paragraph #': idx_element,
                                        'Speaker': presidency_speaker if use_presidency_speaker else speaker_name,
                                        'Role': "Presidency" if use_presidency_speaker else speaker_role_long,
                                        'Gender': presidency_gender if use_presidency_speaker else speaker_gender,
                                        'Party': presidency_party if use_presidency_speaker else speaker_party,
                                        'Paragraph': text,
                                        'Interjection Text': text_interjection,
                                        'Interjection': is_interjection,
                                        'Intervention': is_intervention,
                                        'Quote': is_quote,
                                        'Interjector': interjector,
                                        'Interjector Gender': gender_int,
                                        'Interjector Party': interjector_party,
                                        'Verbal interjection': is_verbal_interjection,
                                        'Nonverbal interjection': is_nonverbal_interjection,
                                        'Interjection type': interjection_type,
                                        'Directed at (Person)': directed_at_person,
                                        'Directed at (Party)': directed_at_party,
                                        'Agenda Item': t_fett,
                                        'Context': t_nas,
                                        'Supplementary Context': t_zp_nas
                                    })


                        ### CAN BE NONVERBAL OR VERBAL INTERJECTIONS "Lachen", "Widerspruch", "Beifall",
                        # "Heiterkeit", "Zurufe", "Zuruf", "Unruhe", "Zustimmung", "Ruf", "Rufe", "Gegenruf", "Gegenrufe"
                        #  WITHOUT COLON
                        else:
                            is_verbal_interjection = False
                            is_nonverbal_interjection = True
                            speechact_matches = list(re.finditer(speechact_pattern_no_colon, part))
                            if speechact_matches:
                                results = []
                                for i, match in enumerate(speechact_matches):
                                    interjector = "Unknown"
                                    start = match.end()

                                    end = speechact_matches[i + 1].start() if i + 1 < len(
                                        speechact_matches) else len(part)

                                    segment = part[start:end]

                                    split_sowie = r'\bsowie\b'
                                    parts_sowie = re.split(split_sowie, segment)
                                    for part_sowie in parts_sowie:
                                        few_mps = "Abgeordneten" in part_sowie
                                        parties_found = re.findall(party_pattern, part_sowie)
                                        if ':' in part_sowie:
                                            lookup_area = part_sowie.split(':', 1)[0]
                                        else:
                                            lookup_area = part_sowie

                                        parties_found = re.findall(party_pattern, lookup_area)
                                        matches_mp = mp_party_regex.findall(part_sowie)

                                        for party in parties_found:
                                            few_mps = "Abgeordneten" in part_sowie  # check if ALL abgeordnete
                                            for old, new in replacements.items():
                                                if party is not None and old in party and new not in party:
                                                    party = re.sub(rf'\b{old}\b', new, party)
                                            individual_added = False

                                            if matches_mp:
                                                for interjector, interjector_party in matches_mp:
                                                    for old, new in replacements.items():
                                                        if old in interjector_party and new not in interjector_party:
                                                            # avoid cdu/csu/csu
                                                            interjector_party = re.sub(rf'\b{old}\b', new,
                                                                                       interjector_party)
                                                    names = interjector.split()
                                                    names = " ".join(names)
                                                    last_name_int = names[-1]
                                                    first_name_int = " ".join(names[:-1])
                                                    meta_info = get_gender_from_name(names, index,  period)
                                                    if meta_info:
                                                        gender_int = meta_info.get("gender", None)
                                                        interjector = meta_info.get("name", None)
                                                    if interjector_party == party:
                                                        interjection_type = match.group("speechact")
                                                        is_verbal = interjection_type in ["Zuruf", "Zurufe",
                                                                                              "Widerspruch",
                                                                                              "Zustimmung", "Ruf", "Rufe",
                                                                                          "Gegenruf", "Gegenrufe"]

                                                        paragraph_list.append({'Filename': filename,
                                                                                   'Period': period,
                                                                                   'Date': date,
                                                                                   'Speech #': speech_id,
                                                                                   'Paragraph #': idx_element,
                                                                                   'Speaker': presidency_speaker if use_presidency_speaker else speaker_name,
                                                                                   'Role': "Presidency" if use_presidency_speaker else speaker_role_long,
                                                                                   'Gender': presidency_gender if use_presidency_speaker else speaker_gender,
                                                                                   'Party': presidency_party if use_presidency_speaker else speaker_party,
                                                                                   'Paragraph': text,
                                                                                   'Interjection Text': None,
                                                                                   'Interjection': is_interjection,
                                                                                   'Intervention': is_intervention,
                                                                                    'Quote': is_quote,
                                                                                   'Interjector': interjector,
                                                                                   'Interjector Gender': gender_int,
                                                                                   'Interjector Party': interjector_party,
                                                                                   'Verbal interjection': True if is_verbal else False,
                                                                                   'Nonverbal interjection': False if is_verbal else True,
                                                                                   'Interjection type': interjection_type,
                                                                                   'Directed at (Person)': directed_at_person,
                                                                                   'Directed at (Party)': directed_at_party,
                                                                                   'Agenda Item': t_fett,
                                                                                   'Context': t_nas,
                                                                                   'Supplementary Context': t_zp_nas
                                                                                   })
                                                        individual_added = True

                                            if not individual_added:
                                                interjection_types = re.split(r'\s+\bund\b\s+', match.group("speechact"))
                                                for interjection_type in interjection_types:
                                                    is_verbal = interjection_type in ["Zuruf", "Zurufe",
                                                                                      "Widerspruch",
                                                                                      "Zustimmung", "Ruf", "Rufe",
                                                                                      "Gegenruf", "Gegenrufe"]
                                                    paragraph_list.append({'Filename': filename,
                                                                           'Period': period,
                                                                           'Date': date,
                                                                           'Speech #': speech_id,
                                                                           'Paragraph #': idx_element,
                                                                           'Speaker': presidency_speaker if use_presidency_speaker else speaker_name,
                                                                           'Role': "Presidency" if use_presidency_speaker else speaker_role_long,
                                                                           'Gender': presidency_gender if use_presidency_speaker else speaker_gender,
                                                                           'Party': presidency_party if use_presidency_speaker else speaker_party,
                                                                           'Paragraph': text,
                                                                           'Interjection Text': None,
                                                                           'Interjection': is_interjection,
                                                                           'Intervention': is_intervention,
                                                                           'Quote': is_quote,
                                                                           'Interjector': (
                                                                               'some' if few_mps and (
                                                                                       (not is_verbal) or (
                                                                                           interjection_type or "").lower() in [
                                                                                           'widerspruch', 'zustimmung']
                                                                               ) else (
                                                                                   'Unknown' if (
                                                                                                            interjection_type or "").lower() in [
                                                                                                    'zuruf', 'gegenruf', 'zurufe', 'rufe', 'gegenrufe,'
                                                                                                    'ruf']
                                                                                   else 'all'
                                                                               )
                                                                           ),
                                                                           'Interjector Gender': None,
                                                                           'Interjector Party': party,
                                                                           'Verbal interjection': True if is_verbal else False,
                                                                           'Nonverbal interjection': False if is_verbal else True,
                                                                           'Interjection type': interjection_type,
                                                                           'Directed at (Person)': directed_at_person,
                                                                           'Directed at (Party)': directed_at_party,
                                                                           'Agenda Item': t_fett,
                                                                           'Context': t_nas,
                                                                           'Supplementary Context': t_zp_nas
                                                                           })
                                        if not parties_found:
                                            last_end = speechact_matches[-1].end() if speechact_matches else 0
                                            trailing_text = part[last_end:]

                                            if "im ganzen Hause" in trailing_text:
                                                parties_found = ['all']
                                            else:
                                                # Zuruf der Bundesministerin Annalena Baerbock
                                                minister_match = re.search(
                                                    r"Bundesminister(?:in)?\s+([^\d\W][\w\-]+(?:\s+[^\d\W][\w\-]+)+)",
                                                    trailing_text,
                                                    flags=re.UNICODE
                                                )
                                                if minister_match:
                                                    name = minister_match.group(1)
                                                    meta_info = get_gender_from_name(name, index, period)
                                                    if meta_info:
                                                        gender_int = meta_info.get("gender", None)
                                                        interjector = meta_info.get("name", None)
                                                        party_int = meta_info.get("party", None)
                                                        parties_found = speaker_party
                                                        paragraph_list.append({'Filename': filename,
                                                                               'Period': period,
                                                                               'Date': date,
                                                                               'Speech #': speech_id,
                                                                               'Paragraph #': idx_element,
                                                                               'Speaker': presidency_speaker if use_presidency_speaker else speaker_name,
                                                                               'Role': "Presidency" if use_presidency_speaker else speaker_role_long,
                                                                               'Gender': presidency_gender if use_presidency_speaker else speaker_gender,
                                                                               'Party': presidency_party if use_presidency_speaker else speaker_party,
                                                                               'Paragraph': text,
                                                                               'Interjection Text': text_interjection,
                                                                               'Interjection': is_interjection,
                                                                               'Intervention': is_intervention,
                                                                               'Quote': is_quote,
                                                                               'Interjector': interjector,
                                                                               'Interjector Gender': gender_int,
                                                                               'Interjector Party': party_int,
                                                                               'Verbal interjection': True if is_verbal else False,
                                                                               'Nonverbal interjection': False if is_verbal else True,
                                                                               'Interjection type': interjection_type,
                                                                               'Directed at (Person)': directed_at_person,
                                                                               'Directed at (Party)': directed_at_party,
                                                                               'Agenda Item': t_fett,
                                                                               'Context': t_nas,
                                                                               'Supplementary Context': t_zp_nas
                                                                               })
                                                else:
                                                    found_parties = re.findall(party_pattern, trailing_text)
                                                    if found_parties:
                                                        parties_found = found_parties

                                        if not parties_found:
                                            interjection_type = match.group("speechact")
                                            is_verbal = interjection_type in ["Zuruf", "Zurufe",
                                                                              "Widerspruch",
                                                                              "Zustimmung", "Ruf", "Rufe",
                                                                              "Gegenruf", "Gegenrufe"]
                                            paragraph_list.append({'Filename': filename,
                                                                   'Period': period,
                                                                   'Date': date,
                                                                   'Speech #': speech_id,
                                                                   'Paragraph #': idx_element,
                                                                   'Speaker': presidency_speaker if use_presidency_speaker else speaker_name,
                                                                   'Role': "Presidency" if use_presidency_speaker else speaker_role_long,
                                                                   'Gender': presidency_gender if use_presidency_speaker else speaker_gender,
                                                                   'Party': presidency_party if use_presidency_speaker else speaker_party,
                                                                   'Paragraph': text,
                                                                   'Interjection Text': text_interjection,
                                                                   'Interjection': is_interjection,
                                                                   'Intervention': is_intervention,
                                                                   'Quote': is_quote,
                                                                   'Interjector': 'Unknown' if is_verbal else 'all',
                                                                   'Interjector Gender': None,
                                                                   'Interjector Party': 'Unknown' if is_verbal else 'all',
                                                                   'Verbal interjection': True if is_verbal else False,
                                                                   'Nonverbal interjection': False if is_verbal else True,
                                                                   'Interjection type': interjection_type,
                                                                   'Directed at (Person)': directed_at_person,
                                                                   'Directed at (Party)': directed_at_party,
                                                                   'Agenda Item': t_fett,
                                                                   'Context': t_nas,
                                                                   'Supplementary Context': t_zp_nas
                                                                   })


speeches_df = pd.DataFrame(paragraph_list)

#drop complete duplicates
speeches_df = speeches_df.drop_duplicates()

### POSTPROCESSING

# 1. Remove whitespaces
def clean_party_name(name):
    if pd.isna(name):
        return ""
    name = str(name).replace("\n", " ").strip()
    name = " ".join(name.split())  # collapse multiple spaces
    name = name.replace(".", "")
    return name

speeches_df['Party'] = speeches_df['Party'].apply(clean_party_name)
speeches_df['Interjector Party'] = speeches_df['Interjector Party'].apply(clean_party_name)
speeches_df['Directed at (Party)'] = speeches_df['Directed at (Party)'].apply(clean_party_name)

speeches_df['Party'] = speeches_df['Party'].replace({
    'CDU': 'CDU/CSU', 'CSU': 'CDU/CSU',
    'UNIV KYIV': 'CDU/CSU', 'ERLANGEN': 'CDU/CSU',
    'BÜNDNIS 90/D': 'GRUENE',
    'BÜNDNIS 90/DIE GRÜNE' : 'GRUENE',
    'BÜNDNISSES 90/DIE GRÜNEN': 'GRUENE',
    'BÜNDNIS 90/DIE GRÜNEN': 'GRUENE',
    'BÜNDIS 90/DIE GRÜNEN': 'GRUENE',
    'LINKEN': 'DIE LINKE', 'LINKE': 'DIE LINKE', 'Die Linke': 'DIE LINKE',
    'Fraktionslos': 'fraktionslos',
    'GB/ BHE': 'GB/BHE'
})

speeches_df['Interjector Party'] = speeches_df['Interjector Party'].replace({
    'CDU': 'CDU/CSU', 'CSU': 'CDU/CSU',
    'UNIV KYIV': 'CDU/CSU', 'ERLANGEN': 'CDU/CSU',
    'BÜNDNIS 90/D': 'GRUENE',
    'BÜNDNIS 90/DIE GRÜNE' : 'GRUENE',
    'BÜNDNISSES 90/DIE GRÜNEN': 'GRUENE',
    'BÜNDNIS 90/DIE GRÜNEN': 'GRUENE',
    'BÜNDIS 90/DIE GRÜNEN': 'GRUENE',
    'LINKEN': 'DIE LINKE', 'LINKE': 'DIE LINKE', 'Die Linke': 'DIE LINKE',
    'Fraktionslos': 'fraktionslos',
    'GB/ BHE': 'GB/BHE'
})

speeches_df['Directed at (Party)'] = speeches_df['Directed at (Party)'].replace({
    'CDU': 'CDU/CSU', 'CSU': 'CDU/CSU', 'CDU/CSU-Fraktion': 'CDU/CSU',
    'UNIV KYIV': 'CDU/CSU', 'ERLANGEN': 'CDU/CSU',
    'BÜNDNIS 90/D': 'GRUENE',
    'BÜNDNIS 90/DIE GRÜNE' : 'GRUENE',
    'BÜNDNISSES 90/DIE GRÜNEN': 'GRUENE',
    'BÜNDNIS 90/DIE GRÜNEN': 'GRUENE',
    'BÜNDIS 90/DIE GRÜNEN': 'GRUENE',
    'LINKEN': 'DIE LINKE', 'LINKE': 'DIE LINKE', 'Die Linke': 'DIE LINKE',
    'Fraktionslos': 'fraktionslos',
    'GB/ BHE': 'GB/BHE'
})

# 2. Add tokenized paragraph + token count for normalization later, exclude punctuation
def tokenize_clean(text):
    if not text:
        return []
    doc = nlp.make_doc(str(text))
    return [
        token.text for token in doc
        if not token.is_punct and not token.is_space and len(token.text.strip()) > 1
    ]


tqdm.pandas()

nlp = spacy.load("de_core_news_md", disable=["parser", "ner", "tagger"])

print("Tokenizing speeches...")
speeches_df.loc[speeches_df['Interjection'] == False, 'Paragraph tokens'] = (
    speeches_df.loc[speeches_df['Interjection'] == False, 'Paragraph']
    .progress_apply(tokenize_clean)
)

print("Tokenizing interjections...")
speeches_df.loc[speeches_df['Interjection'] == True, 'Interjection tokens'] = (
    speeches_df.loc[speeches_df['Interjection'] == True, 'Interjection Text']
    .progress_apply(tokenize_clean)
)


# Count tokens
speeches_df['paragraph_token_count'] = speeches_df['Paragraph tokens'].progress_apply(
    lambda x: len(x) if isinstance(x, list) else 0
)

speeches_df['interjection_token_count'] = speeches_df['Interjection tokens'].progress_apply(
    lambda x: len(x) if isinstance(x, list) else 0
)

cols = [c for c in speeches_df.columns if c not in ["Agenda Item", "Context", "Supplementary Context"]] \
       + ["Agenda Item", "Context", "Supplementary Context"]

speeches_df = speeches_df[cols]

def add_interjection_context(group):
    context_list = []
    contexts = []
    for _, row in group.iterrows():
        if row["Interjection"]:
            contexts.append(context_list.copy())
            context_list.append((
                row["Interjection type"],
                row["Interjector Party"],
                row["Interjection Text"] if row["Interjection Text"] else None
            ))
        else:
            contexts.append(None)  # not an interjection with text
    return pd.Series(contexts, index=group.index)

speeches_df['Previous Interjections'] = speeches_df.groupby(['Date', 'Speech #', 'Speaker', 'Paragraph #', 'Agenda Item', 'Context', 'Supplementary Context']).progress_apply(
    add_interjection_context
).reset_index(level=[0,1,2,3,4,5,6], drop=True)


def add_paragraph_context(group):
    paragraph_list = []
    prev_paragraphs_all = []  # will store per-row results

    for _, row in group.iterrows():
        if not row["Interjection"]:
            paragraph_list.append(row["Paragraph"])
            prev_paragraphs_all.append(None)  # non-interjection rows get no context
        else:
            # store last 2 non-interjection paragraphs for this row
            prev_paragraphs_all.append(paragraph_list[-3:-1].copy())

    return pd.Series(prev_paragraphs_all, index=group.index)

# Apply per paragraph-group
speeches_df["Previous Paragraphs"] = (
    speeches_df.groupby(
        ["Date", "Speech #", "Speaker", "Agenda Item", "Context", "Supplementary Context"]
    ).progress_apply(add_paragraph_context)
    .reset_index(level=[0, 1, 2, 3, 4, 5], drop=True)
)


speeches_df.to_csv('all_20_output_test.csv', index=False)
print("Data successfully saved to 'all_20_output.csv'")
