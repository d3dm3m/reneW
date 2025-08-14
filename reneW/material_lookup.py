# material_lookup.py
# Helper to select (mu, sigma) from parameters.json based on:
#   domain ('water' or 'sewer'),
#   subtype ('spill' or 'storm' for sewer; ignored for water),
#   material name (any common Swedish/English alias),
#   construction year (to pick correct split, e.g. segjärn <1980/≥1980).

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import json
import unicodedata

@dataclass(frozen=True)
class MaterialParams:
    mu: float
    sigma: float

def load_parameters(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def _norm(s: str) -> str:
    return _strip_accents(s).lower().strip()

# This is a comprehensive mapping of user-provided material names to internal keys.
# It is designed to be very flexible.
MATERIAL_ALIASES = {
    'bly': {'blyrör', 'blyledning', 'blyservis'},
    'grajarn': {'gjutjärn', 'gråjärn', 'gjutjärnsrör'},
    'grajarn_blymuff': {'gjutjärn blymuff', 'blystoppade gjutjärnsrör'},
    'grajarn_gummiring': {'gjutjärn gummiring', 'gjutjärn med gummiring', 'tytonfog gjutjärn'},
    'segjarn': {'segjärn', 'duktilt gjutjärn', 'duktiljärn', 'pam-rör', 'sg-järn', 'sferogjutjärn', 'duktilt järn'},
    'segjarn_cement': {'segjärn cementfodrat', 'cementbruksbelagt segjärn', 'di cementfodrat'},
    'segjarn_pe': {'segjärn pe-mantlat', 'polyetenmantlat segjärn', 'di pe-mantel'},
    'stal': {'stålrör', 'svartstål', 'galvrör', 'galvaniserat stålrör', 'alvenius', 'tryckstål', 'sprängledningsstål', 'mantelrör stål'},
    'stal_rostfritt': {'rostfritt stålrör', 'syrafast stålrör', 'duplex rostfritt', 'syrafast rör', 'aisi 316 rör'},
    'tra': {'trärör', 'stockrör', 'träledning', 'stockledning'},
    'lergods': {'lergods', 'lerrör', 'stengodsrör', 'tegelrör', 'keramikrör'},
    'lergods_glaserat': {'lergods glaserat', 'saltglaserat stengods', 'vitrifierat lergods'},
    'stengods': {'stengodsrör', 'steinzeug', 'steinzeug-keramo', 'keramorör'},
    'tegel': {'tegelkulvert', 'murad tegelledning', 'tegelavloppskulvert', 'äggprofil tegel'},
    'betong': {'betongrör', 'armerade betongrör', 'spännarmerade betongrör', 'sr-betongrör', 'sulfatresistenta betongrör', 'pg-fog-betong', 'kanmax', 'germax'},
    'betong_obearmerad': {'betongrör obearmerade', 'o-betongrör'},
    'betong_aggformad': {'äggformad betongledning', 'äggprofil', 'äggrör'},
    'betong_trumma': {'betongtrumma', 'vägtrumma betong', 'kulvertrör betong'},
    'betong_alfa': {'alfa betongrör', 'alfa-rör', 'alfa va-system', 'alfa pg-rör', 'pg-fog', 'gummiringstätade betongrör'},
    'polymerbetong': {'polymerbetongrör', 'polymerbetong', 'pmb'},
    'stal_korrugerad': {'korrugerade stålrör', 'vägtrumma stål', 'ståltrumma', 'ksp', 'helcor', 'multiplate', 'aluzink'},
    'asbestcement': {'asbestcementrör', 'asbestbetongrör', 'fibercementrör', 'eternit'},
    'pvc': {'pvc-rör', 'pvc-u', 'hård-pvc', 'styv pvc', 'pvc tryckrör', 'pvc spillrör'},
    'pvc_m': {'pvc-m', 'modifierad pvc', 'slagtålig pvc'},
    'pvc_o': {'pvc-o-rör', 'orienterad pvc', 'pvc-o'},
    'pvc_slatt': {'pvc självfall slätt', 'släta pvc självfallsrör', 'kanalrör pvc'},
    'pe': {'pe-rör', 'peh-rör', 'hdpe-rör', 'pe80', 'pe100', 'pe100-rc', 'rc-rör', 'pem-slang', 'pel-slang', 'lta-rör', 'servisrör pe', 'svart pe', 'blåstripat pe', 'tryck-pe'},
    'pe_barriar': {'barriär-pe', 'barriär-pe100', 'sla-barriär', 'förorenad mark pe'},
    'pe_skyddsmantel': {'pe skyddsmantel', 'tripelskikts-pe', 'coex-pe', 'profuse-pe'},
    'pe_barriar_evoh': {'pe barriär evoh', 'evoh-barriär-pe'},
    'pe_sjo': {'pe tryckrör sjöledning', 'sjö-pe', 'svart pe sjö'},
    'pe_servis': {'pe servicelina', 'servisledning pe', 'blå-pe'},
    'pp': {'pp-rör', 'polypropenrör', 'pp sn8', 'pp självfall', 'släta pp-rör', 'konstruktionsrör typ b'},
    'pp_hm': {'pp-hm', 'pp högmodul', 'pp-b', 'pp sn-klasser'},
    'pp_slatt': {'pp självfall slätt', 'släta pp självfallsrör', 'kanalrör pp'},
    'glasfiber': {'glasfiberrör', 'glasfiberarmerad plast', 'gup-rör', 'grp-rör', 'kompositrör', 'hobas', 'flowtite', 'bondstrand', 'grp självfall', 'grp tryck', 'gup självbärande'},
    'glasfiber_ve': {'grp vinylester', 'glasfiber vinylester', 'gup ve'},
    'glasfiber_ep': {'grp epoxi', 'glasfiber epoxi', 'gup ep'},
    'struktur': {'strukturväggsrör', 'korrugerade rör', 'dubbelväggsrör', 'spiralrör', 'profilrör'},
    'struktur_pp': {'strukturväggsrör (pp)', 'korrugerade pp-rör', 'dubbbelvägg pp', 'profilrör pp', 'x-stream', 'pragma', 'iq-rör', 'uponor iq'},
    'struktur_pe': {'strukturväggsrör (pe)', 'korrugerade pe-rör', 'dubbbelvägg pe', 'profilrör pe', 'weholite', 'spiralvinda pe', 'spiralrör pe'},
    'plasttrumma': {'plastrumma', 'vägtrumma plast', 'culvert pe', 'culvert pp'},
    'ribbad': {'ribbade rör', 'rib', 'ribb', 'uribb', 'ultrarib', 'ultraribb', 'ultrarib2', 'ultraribb2', 'spiralribb'},
    'dran_plast': {'dränrör plast', 'dräneringsrör', 'slitsade rör', 'dränrör pp', 'dränrör pe'},
    'dran_keramisk': {'keramisk drän', 'drän lergods', 'dräneringsrör lergods'},
    'foder_cipp': {'foder', 'strumpinfodring', 'slanginfodring', 'strumpa', 'cipp', 'uv-foder', 'glasfiberfoder', 'filtfoder', 'epoxyfoder', 'polyesterfoder', 'vinylesterfoder'},
    'foder_pe': {'pe-infodring', 'sliplining', 'rör-i-rör', 'close-fit pe', 'compact pipe'},
    'ovrigt':  {"övrigt", "ovrigt", "okänt", "okant", "unknown", "other", "misc", "diverse"}
}

# The old year-based splitting logic is no longer needed, as the user has provided a much more
# detailed material list with more specific categories. We now do a direct lookup.
# The find_material_key function is now much simpler.

def _match_alias(material: str) -> Optional[str]:
    """Finds the internal key for a given material string."""
    norm_material = _norm(material)
    # Exact match first
    for key, vocab in MATERIAL_ALIASES.items():
        if norm_material in (_norm(x) for x in vocab):
            return key
    # Fallback to substring search
    for key, vocab in MATERIAL_ALIASES.items():
        # Avoid short keywords causing false positives
        for token in vocab:
            norm_token = _norm(token)
            if len(norm_token) > 3 and norm_token in norm_material:
                return key
    return None

def _as_mat(bucket: Dict, key: str) -> MaterialParams:
    if key not in bucket:
        # If the specific key isn't in the bucket (e.g. water vs sewer), fall back to 'ovrigt'
        key = 'ovrigt'
    if key not in bucket:
        # If 'ovrigt' is also missing, raise an error
        raise KeyError(f"Material key '{key}' and fallback 'ovrigt' not found in parameters")
    rec = bucket[key]
    return MaterialParams(mu=float(rec["mu"]), sigma=float(rec["sigma"]))

def find_material_key(
    params: Dict,
    *,
    domain: str,                # 'water' or 'sewer'
    subtype: Optional[str],     # for sewer: 'spill' or 'storm'
    material_name: str,
    year: Optional[int]         # Year is no longer used for splitting, but kept for future use
) -> Tuple[str, MaterialParams]:

    dom = _norm(domain)
    if dom not in ("water", "sewer"):
        raise KeyError(f"domain must be 'water' or 'sewer', got: {domain}")

    if dom == "water":
        bucket = params.get("water")
    else: # sewer
        sec = _norm(subtype or "")
        if sec not in ("spill", "storm"):
            raise KeyError("For 'sewer', subtype must be 'spill' or 'storm'")
        bucket = params.get("sewer", {}).get(sec)

    if not bucket:
        raise KeyError(f"parameters.json lacks required section for '{domain}/{subtype}'")

    # Find the matching internal key from the alias list
    matched_key = _match_alias(material_name) or "ovrigt"

    return matched_key, _as_mat(bucket, matched_key)

def find_liner_key(
    params: Dict,
    *,
    domain: str,
    subtype: Optional[str],
    method_name: str
) -> Optional[Tuple[str, MaterialParams]]:
    """
    Finds the material parameters for a given renovation/lining method.
    Returns None if no match is found.
    """
    # Liners are assumed to have the same params in water/sewer for now
    # We can use the water bucket as the primary source for liner params
    bucket = params.get("water")
    if not bucket:
        return None

    matched_key = _match_alias(method_name)
    if matched_key and 'foder' in matched_key:
        return matched_key, _as_mat(bucket, matched_key)

    return None
