"""Detection rules: labels, colours, word lists and regular expressions (dates, addresses, IDs...)."""

LABELS = {
    "name": "[NOM]",
    "date": "[DATE]",
    "address": "[ADRESSE]",
    "signature": "[SIGNATURE]",
    "email": "[EMAIL]",
    "phone": "[TÉL]",
    "id": "[ID]",
    "org": "[SOCIÉTÉ]",
    "manual": "[MASQUÉ]",
}

# Highlight colours (RGB 0-1)
COLORS = {
    "name": (1, 0.85, 0),
    "date": (0.4, 0.8, 1),
    "address": (0.5, 1, 0.5),
    "signature": (1, 0.5, 0.5),
    "email": (0.85, 0.6, 1),
    "phone": (0.85, 0.6, 1),
    "id": (0.85, 0.6, 1),
    "org": (1, 0.7, 0.3),
    "manual": (1, 0.45, 0.75),
}

ALL_CATEGORIES = ["name", "date", "address", "signature", "email", "phone", "id", "org", "manual"]

CATEGORY_NAMES = {
    "name": "Noms",
    "date": "Dates",
    "address": "Adresses",
    "signature": "Signatures",
    "email": "Emails",
    "phone": "Téléphones",
    "id": "Numéros (IBAN, CIN, ICE…)",
    "org": "Sociétés",
    "manual": "Ajouts manuels",
}
DEFAULT_CATEGORIES = ["name", "date", "address", "signature", "email", "phone", "id"]

# Capitalised words that spaCy sometimes mistakes for people. Never hidden as names.
NOT_NAMES = {
    w.lower()
    for w in """
    article articles contrat contrats annexe annexes société sociétés client clients
    prestataire fournisseur vendeur acheteur bailleur preneur employeur salarié parties partie
    objet durée prix montant total paiement facture conditions générales particulières
    madame monsieur mademoiselle mme mlle mr mrs ms dr me maître
    signature signé signed date lieu fait page tél tel email mail adresse
    janvier février fevrier mars avril mai juin juillet août aout septembre octobre novembre décembre decembre
    january february march april may june july august september october november december
    lundi mardi mercredi jeudi vendredi samedi dimanche
    monday tuesday wednesday thursday friday saturday sunday
    rue avenue boulevard bd impasse résidence lot quartier
    sarl sa sas sasu eurl inc ltd llc gmbh
    euro euros dirham dirhams mad eur usd
    cin ice iban rib siret siren tva rc if patente cnss bic swift nif ref réf
    the and for with from this that agreement contract party parties section clause schedule
    """.split()
}

# Words / phrases that mark a signature area
SIGNATURE_MARKERS = [
    r"signatures?",
    r"sign[ée]e?s?\s+par",
    r"sign[ée]",
    r"lu\s+et\s+approuv[ée]",
    r"bon\s+pour\s+accord",
    r"cachet",
    r"signed(\s+by)?",
    r"(for\s+and\s+on\s+behalf\s+of)",
    r"pour\s+le\s+(client|prestataire|vendeur|bailleur|preneur|fournisseur|salari[ée]|employeur)",
    r"le\s+(client|prestataire|vendeur|acheteur|bailleur|preneur|fournisseur|salari[ée]|employeur)\s*:?\s*$",
]

# --------------------------------------------------------------------------------------
# Patterns (dates, addresses, extras)
# --------------------------------------------------------------------------------------

FR_MONTHS = r"(janv(?:ier)?|f[ée]v(?:rier)?|mars|avr(?:il)?|mai|juin|juil(?:let)?|ao[uû]t|sept(?:embre)?|oct(?:obre)?|nov(?:embre)?|d[ée]c(?:embre)?)\.?"
EN_MONTHS = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
DAYS = r"((lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+)?"

DATE_PATTERNS = [
    # 21/10/2026  21-10-26  21.10.2026
    r"\b\d{1,2}[/\-.]\d{1,2}[/\-.](\d{4}|\d{2})\b",
    # 2026-10-21  2026/10/21
    r"\b\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}\b",
    # (mardi) 21 octobre 2026 / 1er janvier 2026 / 21 oct. 2026 / 21 octobre
    DAYS + r"\b\d{1,2}(er|st|nd|rd|th)?\s+(de\s+)?" + FR_MONTHS + r"(\s+\d{4})?\b",
    DAYS + r"\b\d{1,2}(st|nd|rd|th)?\s+(of\s+)?" + EN_MONTHS + r"(,?\s+\d{4})?\b",
    # October 21, 2026 / Oct 21st 2026
    DAYS + r"\b" + EN_MONTHS + r"\s+\d{1,2}(st|nd|rd|th)?(,?\s+\d{4})?\b",
    # octobre 2026 / October 2026
    r"\b" + FR_MONTHS + r"\s+\d{4}\b",
    r"\b" + EN_MONTHS + r"\s+\d{4}\b",
    # 10/2026
    r"\b(0?[1-9]|1[0-2])/(19|20)\d{2}\b",
    # né(e) le ... / date de naissance : 1990  (year alone after a birth label)
    r"(?<=n[ée]\sen\s)\d{4}\b",
    r"(?<=n[ée]e\sen\s)\d{4}\b",
]

STREET_TYPES = (
    r"(?i:rue|avenue|av\.?|boulevard|bd\.?|blvd\.?|chemin|impasse|all[ée]e|place|pl\.?|quai|route|rte\.?|"
    r"cours|passage|square|r[ée]sidence|r[ée]s\.?|lotissement|lot\.?|quartier|qrt\.?|hay|derb|douar|"
    r"immeuble|imm\.?|appartement|appt\.?|apt\.?|street|st\.?|road|rd\.?|lane|drive|dr\.?|way|"
    r"zone\s+industrielle|z\.?i\.?|bp|b\.p\.?|cedex)"
)

ADDRESS_PATTERNS = [
    # 12 rue Victor Hugo / 12 bis, avenue Mohammed V / Lot 45 / Résidence Al Andalous
    r"\b\d{1,5}\s*(bis|ter|[a-z])?\s*,?\s+" + STREET_TYPES + r"\b[^\n,;]{0,50}",
    r"\b" + STREET_TYPES + r"\s+[A-ZÀ-Ý0-9][^\n,;]{1,50}",
    # 221B Baker Street / 10 Downing Street (English: street type after the name)
    r"\b\d{1,5}[A-Za-z]?\s+(?:[A-Z][a-z]+\s+){1,3}(?:Street|St\.|Road|Rd\.|Avenue|Ave\.|Lane|Drive|Way|Boulevard|Place|Square|Court|Terrace)\b",
    # UK postcode: NW1 6XE / SW1A 2AA (with the city before it)
    r"(?:\b[A-Z][a-z]+\s+)?\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b",
    # 75001 Paris / 40000 Marrakech / Marrakech 40000
    r"\b\d{5}\s+(?!(?i:dirhams?|euros?|mad|eur|dh|usd|dollars?)\b)[A-ZÀ-Ý][A-Za-zÀ-ÿ\-']{2,30}(\s+(?:[A-ZÀ-Ý][A-Za-zÀ-ÿ\-']+|CEDEX\s*\d*))?",
    r"\b[A-ZÀ-Ý][A-Za-zÀ-ÿ\-']{2,30}\s+\d{5}\b(?!\s*(?i:dirhams?|euros?|mad|eur|dh|usd|€|\$))",
    # Anything after "Adresse :" / "demeurant" / "domicilié(e) à" up to end of line
    r"(?i)(?<=adresse\s:\s)[^\n]+",
    r"(?i)(?<=adresse:\s)[^\n]+",
    r"(?i)(?<=adresse\s:)[^\n]+",
    r"(?i)(?<=demeurant\s)[^\n]+",
    r"(?i)(?<=domicili[ée]\s[àa]\s)[^\n]+",
    r"(?i)(?<=domicili[ée]e\s[àa]\s)[^\n]+",
    r"(?i)(?<=address:\s)[^\n]+",
]

EXTRA_PATTERNS = {
    "email": [r"\b[\w.+\-]+@[\w\-]+\.[\w.\-]+\b"],
    "phone": [
        r"(?<![\d\w])(\+|00)\d{1,3}[\s.\-]?\(?\d{1,4}\)?([\s.\-]?\d{2,4}){2,5}",  # international
        r"\b0[1-9]([\s.\-]?\d{2}){4}\b",                               # FR / MA 10 digits
    ],
    "id": [
        r"\b[A-Z]{2}\d{2}[\s]?(\d{4}[\s]?){2,7}\d{1,4}\b",   # IBAN
        r"\bRIB\s*:?\s*(\d[\s]?){20,26}",                    # Moroccan RIB
        r"\b\d{3}\s?\d{3}\s?\d{3}\s?\d{5}\b",                # SIRET (14)
        r"\b\d{15}\b",                                       # ICE (15)
        r"\b[A-Z]{1,2}\d{5,7}\b",                            # CIN / passport
        r"(?<=CIN\s:\s)\S+|(?<=CIN:\s)\S+|(?<=CIN\s)\S+",
        r"\b[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}\b",  # French social security
    ],
}

TITLE_PATTERN = (
    r"\b(M\.|Mr\.?|Mrs\.?|Ms\.?|Mme\.?|Mlle\.?|Monsieur|Madame|Mademoiselle|Dr\.?|Docteur|Me\.?|Ma[iî]tre|Pr\.?)"
    r"\s+((?:[A-ZÀ-Ý][A-Za-zÀ-ÿ'\-]+|[A-ZÀ-Ý]\.)(?:\s+(?:el|al|de|du|des|la|le|ben|bin|ibn|van|von|da|di|[A-ZÀ-Ý][A-Za-zÀ-ÿ'\-]+)){0,4})"
)

