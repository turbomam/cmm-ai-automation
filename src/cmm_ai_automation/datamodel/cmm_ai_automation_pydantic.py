from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "None"
version = "None"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias = True,
        validate_by_name = True,
        validate_assignment = True,
        validate_default = True,
        extra = "forbid",
        arbitrary_types_allowed = True,
        use_enum_values = True,
        strict = False,
    )

    @model_serializer(mode='wrap', when_used='unless-none')
    def treat_empty_lists_as_none(
            self, handler: SerializerFunctionWrapHandler,
            info: SerializationInfo) -> dict[str, Any]:
        if info.exclude_none:
            _instance = self.model_copy()
            for field, field_info in type(_instance).model_fields.items():
                if getattr(_instance, field) == [] and not(
                        field_info.is_required()):
                    setattr(_instance, field, None)
        else:
            _instance = self
        return handler(_instance, info)



class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = LinkMLMeta({'default_prefix': 'cmm',
     'default_range': 'string',
     'description': 'Schema for Critical Mineral Metabolism (CMM) data curation.\n'
                    '\n'
                    'Models microbial strains, growth media, ingredients, and '
                    'their relationships\n'
                    'for knowledge graph generation.',
     'id': 'https://w3id.org/turbomam/cmm-ai-automation',
     'imports': ['linkml:types'],
     'license': 'MIT',
     'name': 'cmm-ai-automation',
     'prefixes': {'ATCC': {'prefix_prefix': 'ATCC',
                           'prefix_reference': 'https://www.atcc.org/products/'},
                  'CAS': {'prefix_prefix': 'CAS',
                          'prefix_reference': 'http://identifiers.org/cas/'},
                  'CHEBI': {'prefix_prefix': 'CHEBI',
                            'prefix_reference': 'http://purl.obolibrary.org/obo/CHEBI_'},
                  'DRUGBANK': {'prefix_prefix': 'DRUGBANK',
                               'prefix_reference': 'http://identifiers.org/drugbank/'},
                  'DSMZ': {'prefix_prefix': 'DSMZ',
                           'prefix_reference': 'https://www.dsmz.de/collection/catalogue/details/culture/DSM-'},
                  'ENVO': {'prefix_prefix': 'ENVO',
                           'prefix_reference': 'http://purl.obolibrary.org/obo/ENVO_'},
                  'KEGG.COMPOUND': {'prefix_prefix': 'KEGG.COMPOUND',
                                    'prefix_reference': 'http://identifiers.org/kegg.compound/'},
                  'MESH': {'prefix_prefix': 'MESH',
                           'prefix_reference': 'http://identifiers.org/mesh/'},
                  'NCBITaxon': {'prefix_prefix': 'NCBITaxon',
                                'prefix_reference': 'http://purl.obolibrary.org/obo/NCBITaxon_'},
                  'OBI': {'prefix_prefix': 'OBI',
                          'prefix_reference': 'http://purl.obolibrary.org/obo/OBI_'},
                  'PUBCHEM.COMPOUND': {'prefix_prefix': 'PUBCHEM.COMPOUND',
                                       'prefix_reference': 'http://identifiers.org/pubchem.compound/'},
                  'RO': {'prefix_prefix': 'RO',
                         'prefix_reference': 'http://purl.obolibrary.org/obo/RO_'},
                  'UO': {'prefix_prefix': 'UO',
                         'prefix_reference': 'http://purl.obolibrary.org/obo/UO_'},
                  'biolink': {'prefix_prefix': 'biolink',
                              'prefix_reference': 'https://w3id.org/biolink/vocab/'},
                  'cmm': {'prefix_prefix': 'cmm',
                          'prefix_reference': 'https://w3id.org/turbomam/cmm-ai-automation/'},
                  'linkml': {'prefix_prefix': 'linkml',
                             'prefix_reference': 'https://w3id.org/linkml/'},
                  'schema': {'prefix_prefix': 'schema',
                             'prefix_reference': 'http://schema.org/'}},
     'see_also': ['https://turbomam.github.io/cmm-ai-automation'],
     'source_file': 'src/cmm_ai_automation/schema/cmm_ai_automation.yaml',
     'title': 'CMM AI Automation Schema'} )

class MediumType(str, Enum):
    """
    Classification of growth media by composition. Note: Functional properties like selective/differential are orthogonal and should be captured separately if needed.
    """
    minimal = "minimal"
    """
    Defined medium with minimal components
    """
    complex = "complex"
    """
    Contains undefined components like yeast extract
    """
    defined = "defined"
    """
    All components are chemically defined
    """
    semi_defined = "semi_defined"
    """
    Mostly defined but contains some complex components
    """


class SolutionType(str, Enum):
    """
    Classification of stock solutions
    """
    trace_elements = "trace_elements"
    """
    Concentrated trace element mixture
    """
    vitamin = "vitamin"
    """
    Vitamin mixture
    """
    buffer = "buffer"
    """
    pH buffer stock
    """
    carbon_source = "carbon_source"
    """
    Concentrated carbon source
    """
    other = "other"
    """
    Other type of stock solution
    """


class IngredientRole(str, Enum):
    """
    Functional role of an ingredient in a growth medium. TODO: Map to grounded ontology terms (METPO, OBI, or custom). See issue #11.
    """
    carbon_source = "carbon_source"
    """
    Provides carbon for biosynthesis and/or energy
    """
    nitrogen_source = "nitrogen_source"
    """
    Provides nitrogen for biosynthesis
    """
    phosphorus_source = "phosphorus_source"
    """
    Provides phosphorus
    """
    sulfur_source = "sulfur_source"
    """
    Provides sulfur
    """
    trace_element = "trace_element"
    """
    Micronutrient required in small amounts
    """
    mineral = "mineral"
    """
    Macro-mineral component
    """
    buffer = "buffer"
    """
    pH buffering agent
    """
    vitamin = "vitamin"
    """
    Essential vitamin or growth factor
    """
    solidifying_agent = "solidifying_agent"
    """
    Agent for solid media (e.g., agar)
    """
    selective_agent = "selective_agent"
    """
    Antibiotic or other selective compound
    """
    osmotic_stabilizer = "osmotic_stabilizer"
    """
    Maintains osmotic balance
    """


class ConcentrationUnit(str, Enum):
    """
    Units for concentration
    """
    g_per_L = "g_per_L"
    """
    Grams per liter
    """
    mg_per_L = "mg_per_L"
    """
    Milligrams per liter
    """
    ug_per_L = "ug_per_L"
    """
    Micrograms per liter
    """
    M = "M"
    """
    Molar
    """
    mM = "mM"
    """
    Millimolar
    """
    uM = "uM"
    """
    Micromolar
    """
    percent_w_v = "percent_w_v"
    """
    Weight/volume percentage: % (w/v)
    """
    percent_v_v = "percent_v_v"
    """
    Volume/volume percentage: % (v/v)
    """


class VolumeUnit(str, Enum):
    """
    Units for volume
    """
    mL = "mL"
    """
    Milliliters
    """
    L = "L"
    """
    Liters
    """
    uL = "uL"
    """
    Microliters
    """


class ConflictResolution(str, Enum):
    """
    How a data conflict between sources was resolved. Primary APIs are considered authoritative for their own ID types.
    """
    primary_source_wins = "primary_source_wins"
    """
    Primary/authoritative source value was used
    """
    manual_review = "manual_review"
    """
    Conflict flagged for manual review
    """
    merged = "merged"
    """
    Values were merged (e.g., for lists)
    """
    unresolved = "unresolved"
    """
    Conflict not yet resolved
    """


class DataSource(str, Enum):
    """
    Names of data sources used for enrichment. Each source is authoritative for its own ID type.
    """
    pubchem = "pubchem"
    """
    PubChem (authoritative for pubchem_cid)
    """
    chebi = "chebi"
    """
    ChEBI 2.0 (authoritative for chebi_id, biological/chemical roles)
    """
    cas = "cas"
    """
    CAS Common Chemistry (authoritative for cas_rn)
    """
    mediadive = "mediadive"
    """
    MediaDive (authoritative for mediadive_id)
    """
    node_normalization = "node_normalization"
    """
    NCATS Translator NodeNormalization API (identifier bridging)
    """
    kg_microbe = "kg_microbe"
    """
    KG-Microbe knowledge graph
    """



class NamedThing(ConfiguredBaseModel):
    """
    A generic grouping for any identifiable entity
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True,
         'class_uri': 'schema:Thing',
         'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation'})

    id: str = Field(default=..., description="""A unique identifier for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:identifier'} })
    name: Optional[str] = Field(default=None, description="""A human-readable name for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'], 'slot_uri': 'schema:name'} })
    description: Optional[str] = Field(default=None, description="""A human-readable description for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:description'} })
    synonyms: Optional[list[str]] = Field(default=[], description="""Alternative names for this entity""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient']} })


class Ingredient(NamedThing):
    """
    A chemical entity that can be a component of solutions or media. Represents the abstract ingredient, not a specific instance with concentration.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation',
         'id_prefixes': ['cmm', 'CHEBI']})

    chemical_formula: Optional[str] = Field(default=None, description="""Chemical formula (e.g., NaCl, MgSO4·7H2O)""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient']} })
    chebi_id: Optional[str] = Field(default=None, description="""ChEBI identifier""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient'], 'id_prefixes': ['CHEBI']} })
    cas_rn: Optional[str] = Field(default=None, description="""CAS Registry Number""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient']} })
    inchikey: Optional[str] = Field(default=None, description="""InChIKey for structural identification""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient']} })
    pubchem_cid: Optional[int] = Field(default=None, description="""PubChem Compound ID""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient']} })
    xrefs: Optional[list[CrossReference]] = Field(default=[], description="""Cross-references to external databases""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient']} })
    id: str = Field(default=..., description="""A unique identifier for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:identifier'} })
    name: Optional[str] = Field(default=None, description="""A human-readable name for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'], 'slot_uri': 'schema:name'} })
    description: Optional[str] = Field(default=None, description="""A human-readable description for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:description'} })
    synonyms: Optional[list[str]] = Field(default=[], description="""Alternative names for this entity""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient']} })

    @field_validator('cas_rn')
    def pattern_cas_rn(cls, v):
        pattern=re.compile(r"^\d{2,7}-\d{2}-\d$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid cas_rn format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid cas_rn format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('inchikey')
    def pattern_inchikey(cls, v):
        pattern=re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid inchikey format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid inchikey format: {v}"
            raise ValueError(err_msg)
        return v


class Mixture(NamedThing):
    """
    Abstract base class for things composed of ingredients. Both Solution and GrowthMedium are mixtures.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'abstract': True, 'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation'})

    has_ingredient_component: Optional[list[IngredientComponent]] = Field(default=[], description="""Ingredients contained in this mixture with their concentrations""", json_schema_extra = { "linkml_meta": {'domain_of': ['Mixture']} })
    id: str = Field(default=..., description="""A unique identifier for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:identifier'} })
    name: Optional[str] = Field(default=None, description="""A human-readable name for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'], 'slot_uri': 'schema:name'} })
    description: Optional[str] = Field(default=None, description="""A human-readable description for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:description'} })
    synonyms: Optional[list[str]] = Field(default=[], description="""Alternative names for this entity""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient']} })


class Solution(Mixture):
    """
    A pre-made concentrated mixture of ingredients, typically diluted into media. Examples: Trace element solution SL-6, Vitamin solution, Phosphate buffer stock.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation',
         'id_prefixes': ['cmm']})

    solution_type: Optional[SolutionType] = Field(default=None, description="""Classification of the solution""", json_schema_extra = { "linkml_meta": {'domain_of': ['Solution']} })
    has_ingredient_component: Optional[list[IngredientComponent]] = Field(default=[], description="""Ingredients contained in this mixture with their concentrations""", json_schema_extra = { "linkml_meta": {'domain_of': ['Mixture']} })
    id: str = Field(default=..., description="""A unique identifier for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:identifier'} })
    name: Optional[str] = Field(default=None, description="""A human-readable name for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'], 'slot_uri': 'schema:name'} })
    description: Optional[str] = Field(default=None, description="""A human-readable description for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:description'} })
    synonyms: Optional[list[str]] = Field(default=[], description="""Alternative names for this entity""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient']} })


class GrowthMedium(Mixture):
    """
    A complete formulation for cultivating microorganisms. Contains ingredients directly and/or pre-made solutions.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation',
         'id_prefixes': ['cmm', 'DSMZ', 'ATCC']})

    medium_type: Optional[MediumType] = Field(default=None, description="""Classification of the medium""", json_schema_extra = { "linkml_meta": {'domain_of': ['GrowthMedium']} })
    ph: Optional[float] = Field(default=None, description="""Target pH of the medium""", ge=0, le=14, json_schema_extra = { "linkml_meta": {'domain_of': ['GrowthMedium']} })
    sterilization_method: Optional[str] = Field(default=None, description="""How the medium is sterilized (e.g., autoclave, filter)""", json_schema_extra = { "linkml_meta": {'domain_of': ['GrowthMedium']} })
    has_solution_component: Optional[list[SolutionComponent]] = Field(default=[], description="""Solutions contained in this medium""", json_schema_extra = { "linkml_meta": {'domain_of': ['GrowthMedium']} })
    target_organisms: Optional[list[str]] = Field(default=[], description="""Taxa or organism types this medium is designed for""", json_schema_extra = { "linkml_meta": {'domain_of': ['GrowthMedium']} })
    references: Optional[list[str]] = Field(default=[], description="""Literature references for this medium formulation""", json_schema_extra = { "linkml_meta": {'domain_of': ['GrowthMedium']} })
    has_ingredient_component: Optional[list[IngredientComponent]] = Field(default=[], description="""Ingredients contained in this mixture with their concentrations""", json_schema_extra = { "linkml_meta": {'domain_of': ['Mixture']} })
    id: str = Field(default=..., description="""A unique identifier for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:identifier'} })
    name: Optional[str] = Field(default=None, description="""A human-readable name for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'], 'slot_uri': 'schema:name'} })
    description: Optional[str] = Field(default=None, description="""A human-readable description for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:description'} })
    synonyms: Optional[list[str]] = Field(default=[], description="""Alternative names for this entity""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient']} })


class IngredientComponent(ConfiguredBaseModel):
    """
    Reified relationship: an ingredient as used in a mixture, with concentration and role. This captures the context-dependent properties of ingredient usage.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation',
         'slot_usage': {'ingredient': {'name': 'ingredient', 'required': True}}})

    ingredient: str = Field(default=..., description="""Reference to the ingredient entity""", json_schema_extra = { "linkml_meta": {'domain_of': ['IngredientComponent']} })
    concentration_value: Optional[float] = Field(default=None, description="""Numeric concentration value""", json_schema_extra = { "linkml_meta": {'domain_of': ['IngredientComponent']} })
    concentration_unit: Optional[ConcentrationUnit] = Field(default=None, description="""Unit of concentration""", json_schema_extra = { "linkml_meta": {'domain_of': ['IngredientComponent']} })
    roles: Optional[list[IngredientRole]] = Field(default=[], description="""Functional roles of this ingredient in this specific mixture. An ingredient can have multiple roles, and roles are context-dependent.""", json_schema_extra = { "linkml_meta": {'domain_of': ['IngredientComponent']} })
    notes: Optional[str] = Field(default=None, description="""Free-text notes about this component""", json_schema_extra = { "linkml_meta": {'domain_of': ['IngredientComponent', 'SolutionComponent']} })


class SolutionComponent(ConfiguredBaseModel):
    """
    Reified relationship: a solution as used in a medium, with volume/dilution.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation',
         'slot_usage': {'solution': {'name': 'solution', 'required': True}}})

    solution: str = Field(default=..., description="""Reference to the solution entity""", json_schema_extra = { "linkml_meta": {'domain_of': ['SolutionComponent']} })
    volume_per_liter: Optional[float] = Field(default=None, description="""Volume of solution added per liter of medium""", json_schema_extra = { "linkml_meta": {'domain_of': ['SolutionComponent']} })
    volume_unit: Optional[VolumeUnit] = Field(default=None, description="""Unit of volume (typically mL)""", json_schema_extra = { "linkml_meta": {'domain_of': ['SolutionComponent']} })
    notes: Optional[str] = Field(default=None, description="""Free-text notes about this component""", json_schema_extra = { "linkml_meta": {'domain_of': ['IngredientComponent', 'SolutionComponent']} })


class EnrichedIngredient(ConfiguredBaseModel):
    """
    A chemical entity enriched with data from multiple sources. Uses (inchikey, cas_rn) tuple as the primary key for entity resolution. Each primary API is authoritative for its own ID type: - PubChem is authoritative for pubchem_cid - ChEBI is authoritative for chebi_id and biological/chemical roles - CAS is authoritative for cas_rn - MediaDive is authoritative for mediadive_id
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'class_uri': 'biolink:SmallMolecule',
         'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation',
         'id_prefixes': ['cmm', 'CHEBI'],
         'unique_keys': {'inchikey_cas_key': {'unique_key_name': 'inchikey_cas_key',
                                              'unique_key_slots': ['inchikey',
                                                                   'cas_rn']}}})

    id: str = Field(default=..., description="""A unique identifier for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:identifier'} })
    inchikey: Optional[str] = Field(default=None, description="""InChIKey for structural identification""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient']} })
    cas_rn: Optional[str] = Field(default=None, description="""CAS Registry Number""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient']} })
    name: Optional[str] = Field(default=None, description="""A human-readable name for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'], 'slot_uri': 'schema:name'} })
    synonyms: Optional[list[str]] = Field(default=[], description="""Alternative names for this entity""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient']} })
    description: Optional[str] = Field(default=None, description="""A human-readable description for a thing""", json_schema_extra = { "linkml_meta": {'domain_of': ['NamedThing', 'EnrichedIngredient'],
         'slot_uri': 'schema:description'} })
    chemical_formula: Optional[str] = Field(default=None, description="""Chemical formula (e.g., NaCl, MgSO4·7H2O)""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient']} })
    chebi_id: Optional[str] = Field(default=None, description="""ChEBI identifier""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient'], 'id_prefixes': ['CHEBI']} })
    pubchem_cid: Optional[int] = Field(default=None, description="""PubChem Compound ID""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient']} })
    mediadive_id: Optional[int] = Field(default=None, description="""MediaDive ingredient ID (MediaDive is authoritative)""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    kegg_id: Optional[str] = Field(default=None, description="""KEGG Compound ID (e.g., C00031)""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    mesh_id: Optional[str] = Field(default=None, description="""MeSH identifier""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    drugbank_id: Optional[str] = Field(default=None, description="""DrugBank identifier""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    inchi: Optional[str] = Field(default=None, description="""InChI string for structural identification""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    smiles: Optional[str] = Field(default=None, description="""SMILES string for structural representation""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    molecular_mass: Optional[float] = Field(default=None, description="""Average molecular mass in Daltons""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    monoisotopic_mass: Optional[float] = Field(default=None, description="""Monoisotopic mass in Daltons""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    charge: Optional[int] = Field(default=None, description="""Formal charge of the molecule""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    biological_roles: Optional[list[str]] = Field(default=[], description="""Biological roles from ChEBI (ChEBI is authoritative). Examples: nutrient, metabolite, cofactor.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    chemical_roles: Optional[list[str]] = Field(default=[], description="""Chemical roles from ChEBI (ChEBI is authoritative). Examples: acid, base, reducing agent.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    application_roles: Optional[list[str]] = Field(default=[], description="""Application roles from ChEBI. Examples: drug, pesticide, food additive.""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    xrefs: Optional[list[CrossReference]] = Field(default=[], description="""Cross-references to external databases""", json_schema_extra = { "linkml_meta": {'domain_of': ['Ingredient', 'EnrichedIngredient']} })
    source_records: Optional[list[SourceRecord]] = Field(default=[], description="""Records tracking which source provided which data""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    conflicts: Optional[list[DataConflict]] = Field(default=[], description="""Recorded conflicts between data sources""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })
    last_enriched: Optional[datetime ] = Field(default=None, description="""Timestamp of last enrichment run""", json_schema_extra = { "linkml_meta": {'domain_of': ['EnrichedIngredient']} })

    @field_validator('inchikey')
    def pattern_inchikey(cls, v):
        pattern=re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid inchikey format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid inchikey format: {v}"
            raise ValueError(err_msg)
        return v

    @field_validator('cas_rn')
    def pattern_cas_rn(cls, v):
        pattern=re.compile(r"^\d{2,7}-\d{2}-\d$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.match(element):
                    err_msg = f"Invalid cas_rn format: {element}"
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.match(v):
            err_msg = f"Invalid cas_rn format: {v}"
            raise ValueError(err_msg)
        return v


class SourceRecord(ConfiguredBaseModel):
    """
    Tracks the provenance of data from a specific source. Each field value can be traced back to its authoritative source.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation'})

    source_name: Optional[str] = Field(default=None, description="""Name of the data source (e.g., pubchem, chebi, cas, mediadive, node_normalization)""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceRecord']} })
    source_id: Optional[str] = Field(default=None, description="""Identifier returned by this source""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceRecord']} })
    source_timestamp: Optional[datetime ] = Field(default=None, description="""When this data was retrieved from the source""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceRecord']} })
    source_query: Optional[str] = Field(default=None, description="""The query used to retrieve data from this source""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceRecord']} })
    source_fields: Optional[list[str]] = Field(default=[], description="""List of field names populated by this source""", json_schema_extra = { "linkml_meta": {'domain_of': ['SourceRecord']} })


class DataConflict(ConfiguredBaseModel):
    """
    Records conflicts between data sources for reconciliation review. Primary APIs are considered authoritative for their own ID types.
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation'})

    field_name: Optional[str] = Field(default=None, description="""Name of the field with conflicting values""", json_schema_extra = { "linkml_meta": {'domain_of': ['DataConflict']} })
    primary_source: Optional[str] = Field(default=None, description="""The authoritative source for this field""", json_schema_extra = { "linkml_meta": {'domain_of': ['DataConflict']} })
    primary_value: Optional[str] = Field(default=None, description="""Value from the authoritative source""", json_schema_extra = { "linkml_meta": {'domain_of': ['DataConflict']} })
    conflicting_source: Optional[str] = Field(default=None, description="""The source with a different value""", json_schema_extra = { "linkml_meta": {'domain_of': ['DataConflict']} })
    conflicting_value: Optional[str] = Field(default=None, description="""Value that conflicts with the authoritative source""", json_schema_extra = { "linkml_meta": {'domain_of': ['DataConflict']} })
    resolution: Optional[ConflictResolution] = Field(default=None, description="""How the conflict was resolved""", json_schema_extra = { "linkml_meta": {'domain_of': ['DataConflict']} })
    resolution_notes: Optional[str] = Field(default=None, description="""Notes about the conflict resolution""", json_schema_extra = { "linkml_meta": {'domain_of': ['DataConflict']} })


class CrossReference(ConfiguredBaseModel):
    """
    A cross-reference to an external database or identifier
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation',
         'slot_usage': {'xref_id': {'name': 'xref_id', 'required': True},
                        'xref_type': {'name': 'xref_type', 'required': True}}})

    xref_type: str = Field(default=..., description="""Type of cross-reference (e.g., CHEBI, CAS-RN, kg-microbe-ingredient)""", json_schema_extra = { "linkml_meta": {'domain_of': ['CrossReference']} })
    xref_id: str = Field(default=..., description="""The identifier value""", json_schema_extra = { "linkml_meta": {'domain_of': ['CrossReference']} })
    xref_label: Optional[str] = Field(default=None, description="""Human-readable label from the external source""", json_schema_extra = { "linkml_meta": {'domain_of': ['CrossReference']} })


class CMMDatabase(ConfiguredBaseModel):
    """
    Container for all CMM entities
    """
    linkml_meta: ClassVar[LinkMLMeta] = LinkMLMeta({'from_schema': 'https://w3id.org/turbomam/cmm-ai-automation',
         'tree_root': True})

    ingredients: Optional[list[Ingredient]] = Field(default=[], json_schema_extra = { "linkml_meta": {'domain_of': ['CMMDatabase']} })
    solutions: Optional[list[Solution]] = Field(default=[], json_schema_extra = { "linkml_meta": {'domain_of': ['CMMDatabase']} })
    media: Optional[list[GrowthMedium]] = Field(default=[], json_schema_extra = { "linkml_meta": {'domain_of': ['CMMDatabase']} })


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
NamedThing.model_rebuild()
Ingredient.model_rebuild()
Mixture.model_rebuild()
Solution.model_rebuild()
GrowthMedium.model_rebuild()
IngredientComponent.model_rebuild()
SolutionComponent.model_rebuild()
EnrichedIngredient.model_rebuild()
SourceRecord.model_rebuild()
DataConflict.model_rebuild()
CrossReference.model_rebuild()
CMMDatabase.model_rebuild()
