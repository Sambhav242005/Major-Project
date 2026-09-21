"""spaCy NER — type mapping and extraction."""

import spacy

# Load spaCy model once
_nlp = spacy.load("en_core_web_sm")

# Entity type mapping from spaCy → our schema
SPACY_TYPE_MAP = {
    "PERSON": "person",
    "ORG": "organization",
    "GPE": "location",
    "LOC": "location",
    "DATE": "date",
    "TIME": "date",
    "NORP": "concept",
    "EVENT": "concept",
    "WORK_OF_ART": "concept",
    "PRODUCT": "concept",
}

ENTITY_TYPES = {"person", "organization", "concept", "location", "date", "other"}

BATCH_SIZE = 10


def _spacy_ner(text: str) -> list[dict]:
    """Run spaCy NER on text, return normalized entities."""
    doc = _nlp(text)
    entities = []
    seen = set()
    for ent in doc.ents:
        name = ent.text.strip()
        if len(name) < 2 or len(name) > 100:
            continue
        if name.isdigit():
            continue
        raw_type = SPACY_TYPE_MAP.get(ent.label_, "other")
        key = (name.lower(), raw_type)
        if key not in seen:
            seen.add(key)
            entities.append({"name": name, "type": raw_type})
    return entities
