import re
from typing import Optional, Dict, Any

class IndianPlateNormalizer:
    """
    Standardizes Indian License Plates (HSRP & Legacy)
    e.g. 'GJ-01-AB-1234' -> 'GJ01AB1234'
    'GJ 05 CD 9999' -> 'GJ05CD9999'
    Also supports modern BH (Bharat) series: '22BH1234AA'
    """
    # Standard Indian Plate Regex: State (2) + District (2) + Series (1-3) + Unique (4)
    STANDARD_PLATE_REGEX = re.compile(r"^([A-Z]{2})([0-9]{1,2})([A-Z]{1,3})([0-9]{4})$")
    BH_SERIES_REGEX = re.compile(r"^([0-9]{2})BH([0-9]{4})([A-Z]{1,2})$")

    # Character confusion correction maps
    LETTER_TO_DIGIT = {
        "O": "0", "D": "0", "Q": "0",
        "I": "1", "L": "1",
        "Z": "2",
        "E": "3",
        "A": "4",
        "S": "5",
        "G": "6",
        "B": "8"
    }

    DIGIT_TO_LETTER = {
        "0": "O",
        "1": "I",
        "2": "Z",
        "3": "E",
        "4": "A",
        "5": "S",
        "6": "G",
        "8": "B"
    }

    @classmethod
    def clean_raw_text(cls, raw_text: str) -> str:
        """Removes whitespace, hyphens, colons, dots, and non-alphanumeric noise."""
        if not raw_text:
            return ""
        # Remove common separators and noise characters
        cleaned = re.sub(r"[^A-Za-z0-9]", "", raw_text).upper()
        return cleaned

    @classmethod
    def normalize_plate(cls, raw_text: str) -> Dict[str, Any]:
        """
        Cleans and normalizes plate text with positional heuristic error correction.
        Returns:
            {
                "raw": raw_text,
                "normalized": "GJ01AB1234",
                "is_valid": True,
                "state": "GJ",
                "rto_code": "01",
                "series": "AB",
                "number": "1234",
                "plate_type": "STANDARD" | "BH_SERIES" | "CUSTOM"
            }
        """
        cleaned = cls.clean_raw_text(raw_text)
        if len(cleaned) < 6:
            return {
                "raw": raw_text,
                "normalized": cleaned,
                "is_valid": False,
                "plate_type": "UNKNOWN"
            }

        # Check BH Series first: e.g. 22BH1234AA
        bh_match = cls.BH_SERIES_REGEX.match(cleaned)
        if bh_match:
            return {
                "raw": raw_text,
                "normalized": cleaned,
                "is_valid": True,
                "state": "BH",
                "year": bh_match.group(1),
                "number": bh_match.group(2),
                "series": bh_match.group(3),
                "plate_type": "BH_SERIES"
            }

        # Apply positional character heuristic correction
        corrected = list(cleaned)
        
        # Positions 0 and 1 MUST be letters (e.g. GJ, MH, DL)
        for i in range(min(2, len(corrected))):
            if corrected[i] in cls.DIGIT_TO_LETTER:
                corrected[i] = cls.DIGIT_TO_LETTER[corrected[i]]

        # Positions 2 and 3 MUST be digits (RTO code: e.g. 01, 05)
        for i in range(2, min(4, len(corrected))):
            if corrected[i] in cls.LETTER_TO_DIGIT:
                corrected[i] = cls.LETTER_TO_DIGIT[corrected[i]]

        # Last 4 characters MUST be digits (Vehicle unique number: e.g. 1234)
        if len(corrected) >= 8:
            for i in range(len(corrected) - 4, len(corrected)):
                if corrected[i] in cls.LETTER_TO_DIGIT:
                    corrected[i] = cls.LETTER_TO_DIGIT[corrected[i]]

        candidate = "".join(corrected)
        match = cls.STANDARD_PLATE_REGEX.match(candidate)
        if match:
            return {
                "raw": raw_text,
                "normalized": candidate,
                "is_valid": True,
                "state": match.group(1),
                "rto_code": match.group(2),
                "series": match.group(3),
                "number": match.group(4),
                "plate_type": "STANDARD"
            }

        return {
            "raw": raw_text,
            "normalized": candidate,
            "is_valid": False,
            "plate_type": "NON_STANDARD"
        }
