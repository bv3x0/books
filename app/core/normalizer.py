"""
Structure Normalizer for Markdown Notes

Normalizes markdown structure after LLM generation to ensure consistent
heading hierarchy and formatting across all book notes.

All operations are regex-based and run locally (no API calls).
"""
import re
from typing import List


class StructureNormalizer:
    """
    Normalizes markdown structure after LLM generation.
    All operations are regex-based and run locally (no API calls).
    """
    
    def normalize(self, content: str) -> str:
        """
        Main entry point. Applies all normalization rules.
        
        Args:
            content: Raw markdown content from merged notes
            
        Returns:
            Normalized markdown content with consistent structure
        """
        lines = content.split('\n')
        lines = self._remove_bullet_prefixes_from_headings(lines)
        lines = self._normalize_indentation(lines)
        lines = self._normalize_chapter_numbers(lines)
        lines = self._strip_chapter_prefixes(lines)
        lines = self._fix_heading_levels(lines)
        lines = self._promote_headings_if_no_parts(lines)
        # lines = self._normalize_heading_case(lines)  # Disabled to preserve author's original heading style
        return '\n'.join(lines)
    
    def _promote_headings_if_no_parts(self, lines: List[str]) -> List[str]:
        """
        Promotes heading levels when no Part-level (##) headings exist.
        
        If a document has ### chapters but no ## parts, the TOC will be flat.
        This promotes: ### → ## and #### → ### for proper hierarchy.
        
        Skips the first # (title) and ## Metadata section.
        """
        # Check if any ## headings exist (excluding "## Metadata")
        has_parts = False
        for line in lines:
            if line.startswith('## ') and not line.startswith('## Metadata'):
                has_parts = True
                break
        
        if has_parts:
            # Document has Parts, no promotion needed
            return lines
        
        # No Parts found - promote ### to ## and #### to ###
        result = []
        for line in lines:
            if line.startswith('#### '):
                # Promote section to chapter level
                result.append('### ' + line[5:])
            elif line.startswith('### '):
                # Promote chapter to part level
                result.append('## ' + line[4:])
            else:
                result.append(line)
        
        return result
    
    # Mapping of spelled-out numbers to numerals (covers 1-20 and special cases)
    WORD_TO_NUMBER = {
        'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
        'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
        'eleven': '11', 'twelve': '12', 'thirteen': '13', 'fourteen': '14',
        'fifteen': '15', 'sixteen': '16', 'seventeen': '17', 'eighteen': '18',
        'nineteen': '19', 'twenty': '20',
        # Also support ordinals (first, second, etc.) if used
        'first': '1', 'second': '2', 'third': '3', 'fourth': '4', 'fifth': '5',
        'sixth': '6', 'seventh': '7', 'eighth': '8', 'ninth': '9', 'tenth': '10',
    }
    
    def _normalize_chapter_numbers(self, lines: List[str]) -> List[str]:
        """
        Converts spelled-out chapter numbers to numerals for consistency.
        
        Transforms: "### Chapter Six: Title" → "### Chapter 6: Title"
        Transforms: "## Part One" → "## Part 1"
        
        Applies to Chapter, Part, and similar structural headings.
        """
        result = []
        # Pattern to match chapter/part headings with spelled-out numbers
        # Captures: (hashes) (Chapter/Part) (spelled word) (optional colon and rest)
        pattern = re.compile(
            r'^(#+\s+)(Chapter|Part|Section)\s+([A-Za-z]+)(\s*:?.*)$',
            re.IGNORECASE
        )
        
        for line in lines:
            match = pattern.match(line)
            if match:
                prefix, label, word_num, rest = match.groups()
                word_lower = word_num.lower()
                if word_lower in self.WORD_TO_NUMBER:
                    # Replace spelled-out number with numeral
                    numeral = self.WORD_TO_NUMBER[word_lower]
                    # Preserve original case of Chapter/Part label
                    line = f"{prefix}{label} {numeral}{rest}"
            result.append(line)
        
        return result
    
    def _strip_chapter_prefixes(self, lines: List[str]) -> List[str]:
        """
        Removes "Chapter X:" prefixes from headings, leaving just the title.
        
        Transforms: "### Chapter 1: The Beginning" → "### The Beginning"
        Transforms: "### Chapter: Optimus Unveiled" → "### Optimus Unveiled"
        Transforms: "### Ch. IV: The End" → "### The End"
        Transforms: "### Chapter 8" → (removed - no title)
        
        Applies to ### level headings (chapter level).
        """
        result = []
        # Pattern to match chapter headings with various formats
        # Captures: (hashes) (Chapter/Ch./Ch) (optional number/roman) (optional colon) (optional title)
        # Changed .+ to .* to handle headings with no title
        pattern = re.compile(
            r'^(###\s+)(?:Chapter|Ch\.?)\s*(?:[IVXivx\d]+)?[:\s]*(.*)$',
            re.IGNORECASE
        )
        
        for line in lines:
            match = pattern.match(line)
            if match:
                hashes, title = match.groups()
                title = title.strip()
                if title:
                    # We have a real title after stripping the chapter prefix
                    line = f"{hashes}{title}"
                else:
                    # No title after "Chapter X" - skip this line entirely
                    # (it's just a standalone "### Chapter 8" with no actual title)
                    continue
            result.append(line)
        
        return result
    
    def _remove_bullet_prefixes_from_headings(self, lines: List[str]) -> List[str]:
        """
        Transforms: "- ## Part I" → "## Part I"
        Transforms: "    - ### Chapter" → "### Chapter"
        
        Removes any leading whitespace, bullets, or dashes before heading markers.
        """
        result = []
        for line in lines:
            # Match: optional whitespace, optional bullet/dash, then heading
            # Only process lines that have headings
            if '#' in line:
                # Remove any leading whitespace, dashes, or asterisks before #
                cleaned = re.sub(r'^[\s\-\*]*(?=#+\s)', '', line)
                result.append(cleaned)
            else:
                result.append(line)
        return result
    
    def _normalize_indentation(self, lines: List[str]) -> List[str]:
        """
        Normalizes indentation to consistent 4-space increments for Hugo/Goldmark compatibility.
        
        Hugo's Goldmark parser requires 4 spaces for nested list indentation.
        
        Handles both legacy 2-space increments and new 4-space increments from LLM.
        
        Ensures consistent bullet indentation:
        - Level 0: 0 spaces (top-level bullets)
        - Level 1: 4 spaces (nested bullets)
        - Level 2: 8 spaces (sub-nested bullets)
        - Level 3: 12 spaces (deep nested, capped here)
        """
        result = []
        for line in lines:
            stripped = line.lstrip()
            if not stripped:
                result.append(line)
                continue
                
            # If it's a heading, no indent
            if stripped.startswith('#'):
                result.append(stripped)
            # If it's a bullet point
            elif stripped.startswith(('*', '-')):
                # Determine indent level - handle both 2-space and 4-space input
                original_indent = len(line) - len(stripped)
                
                # Detect if input uses 4-space increments (new LLM output) or 2-space (legacy)
                # 4-space: 0, 4, 8, 12 → levels 0, 1, 2, 3
                # 2-space: 0, 2, 4, 6 → levels 0, 1, 2, 3
                if original_indent >= 4 and original_indent % 4 <= 1:
                    # Likely 4-space increments
                    indent_level = original_indent // 4
                else:
                    # Legacy 2-space increments - convert to levels
                    indent_level = (original_indent + 1) // 2
                
                # Cap at 3 levels of nesting (0, 1, 2, 3)
                indent_level = min(3, indent_level)
                new_indent = indent_level * 4  # 4 spaces per level for Hugo
                result.append(' ' * new_indent + stripped)
            else:
                # Preserve other lines as-is
                result.append(line)
        return result
    
    def _is_duplicate_title(self, main_title: str, candidate: str) -> bool:
        """
        Check if candidate is a duplicate of the main title using fuzzy matching.

        Handles cases where Claude generates the full book title (with subtitle)
        but the exporter used a shorter version.

        Returns True if:
        - Exact match
        - Main title is contained in candidate (subtitle case)
        - First 4+ words match (handles punctuation differences)
        """
        if main_title == candidate:
            return True

        # Check if main title is a prefix of candidate (subtitle case)
        if candidate.startswith(main_title):
            return True

        # Check if main title is contained in candidate
        if main_title in candidate:
            return True

        # Normalize for word-by-word comparison (remove punctuation)
        def normalize_words(text):
            return [w for w in re.sub(r'[^\w\s]', '', text).split() if w]

        main_words = normalize_words(main_title)
        candidate_words = normalize_words(candidate)

        # If first 4+ words match, consider it a duplicate
        if len(main_words) >= 4 and len(candidate_words) >= 4:
            if main_words[:4] == candidate_words[:4]:
                return True

        return False

    def _fix_heading_levels(self, lines: List[str]) -> List[str]:
        """
        Ensures proper heading hierarchy:
        - # reserved for title (handled by exporter)
        - ## for Parts
        - ### for Chapters
        - #### for Sections

        Detects content type from headings and adjusts levels if needed.
        Skips duplicate title H1 headings to prevent redundancy.
        """
        result = []
        # First pass: detect if document has Parts
        has_parts = any(re.match(r'^##\s+Part\s+', line, re.I) for line in lines)
        
        # Track the main title (first H1 we encounter)
        main_title = None
        
        for line in lines:
            if not line.startswith('#'):
                result.append(line)
                continue
            
            # Count heading level
            match = re.match(r'^(#+)\s+(.*)$', line)
            if not match:
                result.append(line)
                continue
                
            hashes, title = match.groups()
            level = len(hashes)
            
            # Normalize based on content
            title_lower = title.lower().strip()
            
            # Detect Part headings (case-insensitive, handles Roman/Arabic)
            if re.match(r'part\s+[ivx\d]+', title_lower):
                # This is a Part → should be ##
                result.append(f'## {title}')
            # Detect Chapter headings
            elif re.match(r'(chapter|ch\.?)\s+[ivx\d]+', title_lower):
                # This is a Chapter → should be ###
                result.append(f'### {title}')
            # Detect other common chapter indicators (standalone sections only)
            elif re.match(r'^(epilogue|prologue|introduction|afterword|preface)(\s*:|$)', title_lower):
                # Special sections at chapter level
                if has_parts:
                    result.append(f'### {title}')
                else:
                    result.append(f'### {title}')
            # Handle H1 headings
            elif level == 1:
                if main_title is None:
                    # First H1 is the main title - keep it
                    main_title = title_lower
                    result.append(line)
                elif self._is_duplicate_title(main_title, title_lower):
                    # Duplicate title (exact or fuzzy match) - skip entirely
                    continue
                else:
                    # Different H1 → demote to appropriate level
                    if has_parts:
                        result.append(f'#### {title}')  # Section level
                    else:
                        result.append(f'### {title}')   # Chapter level
            # Handle #### headings that are duplicate titles (from previous normalization)
            elif level == 4 and main_title and self._is_duplicate_title(main_title, title_lower):
                # Skip duplicate title that was previously demoted to ####
                continue
            # Handle excessive heading levels (> 4)
            elif level > 4:
                # Cap at 4 levels (####)
                result.append(f'#### {title}')
            else:
                # Keep as-is if already reasonable
                result.append(line)
        
        return result
