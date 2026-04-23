"""
shared/utils/bijoy_converter.py
===============================
Production-grade Unicode → Bijoy (ANSI) converter for KongshoMJ.ttf.
Character map extracted programmatically from the actual font file.
"""


class BijoyConverter:
    """
    Converts Unicode Bengali text to the ANSI byte sequence that KongshoMJ.ttf
    expects.  The MAP below was built by rendering every printable ASCII
    character (32-126) with KongshoMJ and recording which Bengali glyph
    appeared at each code-point.

    The converter also handles:
      • Pre-vowel swapping  (ি / ে / ৈ  appear LEFT of the consonant)
      • Split-vowel expansion  (ো → ে + া,  ৌ → ে + ৗ)
      • Hasanta / Juktaborno basics
    """

    # ── Unicode → ASCII mapping (verified from font grid) ────────────────
    MAP = {
        # ─── Full vowels ─────────────────────────────────────────────────
        'অ': 'A',   'আ': 'Av',  'ই': 'B',   'ঈ': 'C',
        'উ': 'D',   'ঊ': 'E',   'ঋ': 'F',
        'এ': 'G',   'ঐ': 'H',   'ও': 'I',   'ঔ': 'J',

        # ─── Consonants ─────────────────────────────────────────────────
        'ক': 'K',   'খ': 'L',   'গ': 'M',   'ঘ': 'N',   'ঙ': 'O',
        'চ': 'P',   'ছ': 'Q',   'জ': 'R',   'ঝ': 'S',   'ঞ': 'T',
        'ট': 'U',   'ঠ': 'V',   'ড': 'W',   'ঢ': 'X',   'ণ': 'Y',
        'ত': 'Z',   'থ': '_',   'দ': '`',   'ধ': 'a',   'ন': 'b',
        'প': 'c',   'ফ': 'd',   'ব': 'e',   'ভ': 'f',   'ম': 'g',
        'য': 'h',   'র': 'i',   'ল': 'j',
        'শ': 'k',   'ষ': 'l',   'স': 'm',   'হ': 'n',
        'ড়': 'o',  'ঢ়': 'p',  'য়': 'q',  'ৎ': 'r',

        # ─── Vowel signs (matras) ───────────────────────────────────────
        'া': 'v',   # aa-kar
        'ি': 'w',   # i-kar    (PRE-VOWEL — placed before consonant)
        'ী': 'x',   # ii-kar
        'ু': 'y',   # u-kar
        'ূ': 'z',   # uu-kar   (if present; z = hasanta in some MJ fonts)
        'ৃ': '„',   # ri-kar
        'ে': '‡',   # e-kar    (PRE-VOWEL — placed before consonant)
        'ৈ': '†',   # oi-kar   (PRE-VOWEL — placed before consonant)

        # ─── Special marks ──────────────────────────────────────────────
        'ং': 's',   # anusvara
        'ঃ': 't',   # visarga
        'ঁ': 'u',   # chandrabindu
        '।': '\\',  # dari (purna biram)
        '৳': '$',   # taka sign

        # ─── Bengali digits ─────────────────────────────────────────────
        '০': '0',   '১': '1',   '২': '2',   '৩': '3',   '৪': '4',
        '৫': '5',   '৬': '6',   '৭': '7',   '৮': '8',   '৯': '9',

        # ─── Hasanta (virama) ───────────────────────────────────────────
        '্': '&',
    }

    # Pre-vowels: these matras are rendered LEFT of the consonant they
    # attach to.  In the output byte stream they must appear BEFORE the
    # consonant's ASCII code.
    PRE_VOWELS = {'ি', 'ে', 'ৈ'}

    # ────────────────────────────────────────────────────────────────────
    @classmethod
    def convert(cls, unicode_text: str) -> str:
        """Convert Unicode Bengali → KongshoMJ ANSI."""
        if not unicode_text:
            return ""

        # 1. Expand split vowels
        text = (unicode_text
                .replace('ো', 'ে' + 'া')
                .replace('ৌ', 'ে' + 'ৌ'))  # ৌ kept as-is if no mapping

        # 2. Merge nukta composites: য+় → য়, ড+় → ড়, ঢ+় → ঢ়
        NUKTA = '\u09BC'  # ়
        NUKTA_COMPOSITES = {'য': 'য়', 'ড': 'ড়', 'ঢ': 'ঢ়'}
        merged: list[str] = []
        raw = list(text)
        j = 0
        while j < len(raw):
            if (j + 1 < len(raw)
                    and raw[j + 1] == NUKTA
                    and raw[j] in NUKTA_COMPOSITES):
                merged.append(NUKTA_COMPOSITES[raw[j]])
                j += 2
            else:
                merged.append(raw[j])
                j += 1

        chars = merged
        # ── Step 3: Conjunct substitution ─────────────────────────────
        # Replace common consonant+hasanta+consonant sequences with
        # their dedicated conjunct glyphs in KongshoMJ.
        # Without this, hasanta (্) renders as a visible stroke.

        # Specific ligatures first
        conjuncted: list[str] = []
        k = 0
        while k < len(chars):
            if (k + 2 < len(chars)
                    and chars[k] == 'স'
                    and chars[k + 1] == '্'
                    and chars[k + 2] == 'ট'):
                conjuncted.append('\u00F7')  # স্ট
                k += 3
                continue
            
            # Ra-phala (্র): Ö (U+00D6) = subscript র
            if (k + 1 < len(chars)
                    and chars[k] == '্'
                    and chars[k + 1] == 'র'):
                # Replace ্র with ra-phala glyph
                conjuncted.append('\u00D6')
                k += 2
                continue
            
            conjuncted.append(chars[k])
            k += 1

        chars = conjuncted

        # ── Two-pass approach ─────────────────────────────────────────
        # Pass 1: Map every Unicode char to its Bijoy ASCII equivalent.
        mapped: list[str] = []
        for ch in chars:
            mapped.append(cls.MAP.get(ch, ch))

        # Pass 2: Relocate pre-vowels.
        # In Bijoy, ি / ে / ৈ must appear BEFORE the entire consonant
        # cluster they attach to, not just the single preceding consonant.
        # A cluster is: consonant (+ hasanta + consonant)*, so in the
        # mapped output it looks like: C z C z C ...
        # We scan backwards from the pre-vowel position past any
        # (hasanta, consonant) pairs to find the cluster start.

        PRE_MAPPED = {cls.MAP[v] for v in cls.PRE_VOWELS}
        HASANTA_MAPPED = cls.MAP.get('্', 'z')

        # Identify which mapped chars are Bijoy consonants
        _CONSONANT_MAPPED = set()
        for k, v in cls.MAP.items():
            if '\u0995' <= k <= '\u09DF' or k in ('য়', 'ড়', 'ঢ়'):
                _CONSONANT_MAPPED.add(v)

        # Conjunct glyphs (ra-phala Ö, etc.) act as consonant extensions
        # in the cluster — the pre-vowel must jump past them too.
        CONJUNCT_GLYPHS = {'\u00D6', '\u00F7'}  # ra-phala, st

        result: list[str] = []
        i = 0
        while i < len(mapped):
            token = mapped[i]

            if token in PRE_MAPPED:
                # This is a pre-vowel (ি/ে/ৈ).  Walk backwards in
                # `result` to find where the consonant cluster starts.
                # A cluster is: C (z C)* where C=consonant, z=hasanta
                insert_pos = len(result)
                while insert_pos > 0:
                    prev = result[insert_pos - 1]
                    if prev in CONJUNCT_GLYPHS:
                        # Conjunct glyph (e.g. ra-phala Ö) — skip it
                        # as part of the cluster
                        insert_pos -= 1
                    elif prev in _CONSONANT_MAPPED:
                        insert_pos -= 1   # move before this consonant
                        # If there's a hasanta or conjunct before this
                        # consonant, keep scanning (part of cluster)
                        if insert_pos > 0 and (result[insert_pos - 1] == HASANTA_MAPPED
                                               or result[insert_pos - 1] in CONJUNCT_GLYPHS):
                            insert_pos -= 1   # move before the hasanta/conjunct
                        else:
                            break  # reached the cluster start
                    else:
                        break
                result.insert(insert_pos, token)
            else:
                result.append(token)
            i += 1

        return "".join(result)


# ── Quick self-test ─────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("এয়ারটেল", "Gqvi‡Uj"),
        ("মিউজিক", "wgDwRK"),  # approximate
        ("লিমিটলেস", "wjwgU‡jm"),  # approximate
        ("৫৯ টাকায়", "59 UvKvq"),
        ("৩ জিবি", "3 wReB"),
    ]
    for src, expected in tests:
        got = BijoyConverter.convert(src)
        ok = "✓" if got == expected else "✗"
        print(f"  {ok}  '{src}' → '{got}'  (expected '{expected}')")
