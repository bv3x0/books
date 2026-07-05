"""Shared structured-output schema for unified book summaries."""

SUMMARY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["book", "chapters"],
    "additionalProperties": False,
    "properties": {
        "book": {
            "type": "object",
            "required": [
                "title",
                "author",
                "year",
                "thesis",
                "topics",
                "categories",
            ],
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string"},
                "author": {"type": ["string", "null"]},
                "year": {"type": ["number", "null"]},
                "thesis": {"type": ["string", "null"]},
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "part",
                    "title",
                    "summary",
                    "pull_quote",
                    "key_points",
                ],
                "additionalProperties": False,
                "properties": {
                    "part": {"type": ["string", "null"]},
                    "title": {"type": "string"},
                    "summary": {"type": ["string", "null"]},
                    "pull_quote": {"type": ["string", "null"]},
                    "key_points": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": [
                                "point",
                                "sub_points",
                                "concepts",
                                "entities",
                            ],
                            "additionalProperties": False,
                            "properties": {
                                "point": {"type": "string"},
                                "sub_points": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["type", "text", "speaker"],
                                        "additionalProperties": False,
                                        "properties": {
                                            "type": {
                                                "type": "string",
                                                "enum": [
                                                    "example",
                                                    "number",
                                                    "mechanism",
                                                    "quote",
                                                    "contrast",
                                                    "caveat",
                                                    "source_detail",
                                                ],
                                            },
                                            "text": {"type": "string"},
                                            "speaker": {"type": ["string", "null"]},
                                        },
                                    },
                                },
                                "concepts": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "entities": {
                                    "type": "object",
                                    "required": [
                                        "people",
                                        "places",
                                        "events",
                                        "works",
                                    ],
                                    "additionalProperties": False,
                                    "properties": {
                                        "people": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "places": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "events": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "works": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}
