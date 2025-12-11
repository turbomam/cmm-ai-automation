# Auto generated from cmm_ai_automation.yaml by pythongen.py version: 0.0.1
# Generation date: 2025-12-11T12:01:25
# Schema: cmm-ai-automation
#
# id: https://w3id.org/turbomam/cmm-ai-automation
# description: Schema for Critical Mineral Metabolism (CMM) data curation.
#
#   Models microbial strains, growth media, ingredients, and their relationships
#   for knowledge graph generation.
# license: MIT

import dataclasses
import re
from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    time
)
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Union
)

from jsonasobj2 import (
    JsonObj,
    as_dict
)
from linkml_runtime.linkml_model.meta import (
    EnumDefinition,
    PermissibleValue,
    PvFormulaOptions
)
from linkml_runtime.utils.curienamespace import CurieNamespace
from linkml_runtime.utils.enumerations import EnumDefinitionImpl
from linkml_runtime.utils.formatutils import (
    camelcase,
    sfx,
    underscore
)
from linkml_runtime.utils.metamodelcore import (
    bnode,
    empty_dict,
    empty_list
)
from linkml_runtime.utils.slot import Slot
from linkml_runtime.utils.yamlutils import (
    YAMLRoot,
    extended_float,
    extended_int,
    extended_str
)
from rdflib import (
    Namespace,
    URIRef
)

from linkml_runtime.linkml_model.types import Datetime, Float, Integer, String, Uriorcurie
from linkml_runtime.utils.metamodelcore import URIorCURIE, XSDDateTime

metamodel_version = "1.7.0"
version = None

# Namespaces
ATCC = CurieNamespace('ATCC', 'https://www.atcc.org/products/')
CAS = CurieNamespace('CAS', 'http://identifiers.org/cas/')
CHEBI = CurieNamespace('CHEBI', 'http://purl.obolibrary.org/obo/CHEBI_')
DRUGBANK = CurieNamespace('DRUGBANK', 'http://identifiers.org/drugbank/')
DSMZ = CurieNamespace('DSMZ', 'https://www.dsmz.de/collection/catalogue/details/culture/DSM-')
ENVO = CurieNamespace('ENVO', 'http://purl.obolibrary.org/obo/ENVO_')
KEGG_COMPOUND = CurieNamespace('KEGG_COMPOUND', 'http://identifiers.org/kegg.compound/')
MESH = CurieNamespace('MESH', 'http://identifiers.org/mesh/')
NCBITAXON = CurieNamespace('NCBITaxon', 'http://purl.obolibrary.org/obo/NCBITaxon_')
OBI = CurieNamespace('OBI', 'http://purl.obolibrary.org/obo/OBI_')
PUBCHEM_COMPOUND = CurieNamespace('PUBCHEM_COMPOUND', 'http://identifiers.org/pubchem.compound/')
RO = CurieNamespace('RO', 'http://purl.obolibrary.org/obo/RO_')
UO = CurieNamespace('UO', 'http://purl.obolibrary.org/obo/UO_')
BIOLINK = CurieNamespace('biolink', 'https://w3id.org/biolink/vocab/')
CMM = CurieNamespace('cmm', 'https://w3id.org/turbomam/cmm-ai-automation/')
LINKML = CurieNamespace('linkml', 'https://w3id.org/linkml/')
SCHEMA = CurieNamespace('schema', 'http://schema.org/')
DEFAULT_ = CMM


# Types

# Class references
class NamedThingId(URIorCURIE):
    pass


class IngredientId(NamedThingId):
    pass


class MixtureId(NamedThingId):
    pass


class SolutionId(MixtureId):
    pass


class GrowthMediumId(MixtureId):
    pass


class EnrichedIngredientId(URIorCURIE):
    pass


@dataclass(repr=False)
class NamedThing(YAMLRoot):
    """
    A generic grouping for any identifiable entity
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = SCHEMA["Thing"]
    class_class_curie: ClassVar[str] = "schema:Thing"
    class_name: ClassVar[str] = "NamedThing"
    class_model_uri: ClassVar[URIRef] = CMM.NamedThing

    id: Union[str, NamedThingId] = None
    name: Optional[str] = None
    description: Optional[str] = None
    synonyms: Optional[Union[str, list[str]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, NamedThingId):
            self.id = NamedThingId(self.id)

        if self.name is not None and not isinstance(self.name, str):
            self.name = str(self.name)

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if not isinstance(self.synonyms, list):
            self.synonyms = [self.synonyms] if self.synonyms is not None else []
        self.synonyms = [v if isinstance(v, str) else str(v) for v in self.synonyms]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Ingredient(NamedThing):
    """
    A chemical entity that can be a component of solutions or media. Represents the abstract ingredient, not a
    specific instance with concentration.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = CMM["Ingredient"]
    class_class_curie: ClassVar[str] = "cmm:Ingredient"
    class_name: ClassVar[str] = "Ingredient"
    class_model_uri: ClassVar[URIRef] = CMM.Ingredient

    id: Union[str, IngredientId] = None
    chemical_formula: Optional[str] = None
    chebi_id: Optional[Union[str, URIorCURIE]] = None
    cas_rn: Optional[str] = None
    inchikey: Optional[str] = None
    pubchem_cid: Optional[int] = None
    xrefs: Optional[Union[Union[dict, "CrossReference"], list[Union[dict, "CrossReference"]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, IngredientId):
            self.id = IngredientId(self.id)

        if self.chemical_formula is not None and not isinstance(self.chemical_formula, str):
            self.chemical_formula = str(self.chemical_formula)

        if self.chebi_id is not None and not isinstance(self.chebi_id, URIorCURIE):
            self.chebi_id = URIorCURIE(self.chebi_id)

        if self.cas_rn is not None and not isinstance(self.cas_rn, str):
            self.cas_rn = str(self.cas_rn)

        if self.inchikey is not None and not isinstance(self.inchikey, str):
            self.inchikey = str(self.inchikey)

        if self.pubchem_cid is not None and not isinstance(self.pubchem_cid, int):
            self.pubchem_cid = int(self.pubchem_cid)

        if not isinstance(self.xrefs, list):
            self.xrefs = [self.xrefs] if self.xrefs is not None else []
        self.xrefs = [v if isinstance(v, CrossReference) else CrossReference(**as_dict(v)) for v in self.xrefs]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Mixture(NamedThing):
    """
    Abstract base class for things composed of ingredients. Both Solution and GrowthMedium are mixtures.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = CMM["Mixture"]
    class_class_curie: ClassVar[str] = "cmm:Mixture"
    class_name: ClassVar[str] = "Mixture"
    class_model_uri: ClassVar[URIRef] = CMM.Mixture

    id: Union[str, MixtureId] = None
    has_ingredient_component: Optional[Union[Union[dict, "IngredientComponent"], list[Union[dict, "IngredientComponent"]]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if not isinstance(self.has_ingredient_component, list):
            self.has_ingredient_component = [self.has_ingredient_component] if self.has_ingredient_component is not None else []
        self.has_ingredient_component = [v if isinstance(v, IngredientComponent) else IngredientComponent(**as_dict(v)) for v in self.has_ingredient_component]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class Solution(Mixture):
    """
    A pre-made concentrated mixture of ingredients, typically diluted into media. Examples: Trace element solution
    SL-6, Vitamin solution, Phosphate buffer stock.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = CMM["Solution"]
    class_class_curie: ClassVar[str] = "cmm:Solution"
    class_name: ClassVar[str] = "Solution"
    class_model_uri: ClassVar[URIRef] = CMM.Solution

    id: Union[str, SolutionId] = None
    solution_type: Optional[Union[str, "SolutionType"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, SolutionId):
            self.id = SolutionId(self.id)

        if self.solution_type is not None and not isinstance(self.solution_type, SolutionType):
            self.solution_type = SolutionType(self.solution_type)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class GrowthMedium(Mixture):
    """
    A complete formulation for cultivating microorganisms. Contains ingredients directly and/or pre-made solutions.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = CMM["GrowthMedium"]
    class_class_curie: ClassVar[str] = "cmm:GrowthMedium"
    class_name: ClassVar[str] = "GrowthMedium"
    class_model_uri: ClassVar[URIRef] = CMM.GrowthMedium

    id: Union[str, GrowthMediumId] = None
    medium_type: Optional[Union[str, "MediumType"]] = None
    ph: Optional[float] = None
    sterilization_method: Optional[str] = None
    has_solution_component: Optional[Union[Union[dict, "SolutionComponent"], list[Union[dict, "SolutionComponent"]]]] = empty_list()
    target_organisms: Optional[Union[str, list[str]]] = empty_list()
    references: Optional[Union[str, list[str]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, GrowthMediumId):
            self.id = GrowthMediumId(self.id)

        if self.medium_type is not None and not isinstance(self.medium_type, MediumType):
            self.medium_type = MediumType(self.medium_type)

        if self.ph is not None and not isinstance(self.ph, float):
            self.ph = float(self.ph)

        if self.sterilization_method is not None and not isinstance(self.sterilization_method, str):
            self.sterilization_method = str(self.sterilization_method)

        if not isinstance(self.has_solution_component, list):
            self.has_solution_component = [self.has_solution_component] if self.has_solution_component is not None else []
        self.has_solution_component = [v if isinstance(v, SolutionComponent) else SolutionComponent(**as_dict(v)) for v in self.has_solution_component]

        if not isinstance(self.target_organisms, list):
            self.target_organisms = [self.target_organisms] if self.target_organisms is not None else []
        self.target_organisms = [v if isinstance(v, str) else str(v) for v in self.target_organisms]

        if not isinstance(self.references, list):
            self.references = [self.references] if self.references is not None else []
        self.references = [v if isinstance(v, str) else str(v) for v in self.references]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class IngredientComponent(YAMLRoot):
    """
    Reified relationship: an ingredient as used in a mixture, with concentration and role. This captures the
    context-dependent properties of ingredient usage.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = CMM["IngredientComponent"]
    class_class_curie: ClassVar[str] = "cmm:IngredientComponent"
    class_name: ClassVar[str] = "IngredientComponent"
    class_model_uri: ClassVar[URIRef] = CMM.IngredientComponent

    ingredient: Union[str, IngredientId] = None
    concentration_value: Optional[float] = None
    concentration_unit: Optional[Union[str, "ConcentrationUnit"]] = None
    roles: Optional[Union[Union[str, "IngredientRole"], list[Union[str, "IngredientRole"]]]] = empty_list()
    notes: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.ingredient):
            self.MissingRequiredField("ingredient")
        if not isinstance(self.ingredient, IngredientId):
            self.ingredient = IngredientId(self.ingredient)

        if self.concentration_value is not None and not isinstance(self.concentration_value, float):
            self.concentration_value = float(self.concentration_value)

        if self.concentration_unit is not None and not isinstance(self.concentration_unit, ConcentrationUnit):
            self.concentration_unit = ConcentrationUnit(self.concentration_unit)

        if not isinstance(self.roles, list):
            self.roles = [self.roles] if self.roles is not None else []
        self.roles = [v if isinstance(v, IngredientRole) else IngredientRole(v) for v in self.roles]

        if self.notes is not None and not isinstance(self.notes, str):
            self.notes = str(self.notes)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class SolutionComponent(YAMLRoot):
    """
    Reified relationship: a solution as used in a medium, with volume/dilution.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = CMM["SolutionComponent"]
    class_class_curie: ClassVar[str] = "cmm:SolutionComponent"
    class_name: ClassVar[str] = "SolutionComponent"
    class_model_uri: ClassVar[URIRef] = CMM.SolutionComponent

    solution: Union[str, SolutionId] = None
    volume_per_liter: Optional[float] = None
    volume_unit: Optional[Union[str, "VolumeUnit"]] = None
    notes: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.solution):
            self.MissingRequiredField("solution")
        if not isinstance(self.solution, SolutionId):
            self.solution = SolutionId(self.solution)

        if self.volume_per_liter is not None and not isinstance(self.volume_per_liter, float):
            self.volume_per_liter = float(self.volume_per_liter)

        if self.volume_unit is not None and not isinstance(self.volume_unit, VolumeUnit):
            self.volume_unit = VolumeUnit(self.volume_unit)

        if self.notes is not None and not isinstance(self.notes, str):
            self.notes = str(self.notes)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class EnrichedIngredient(YAMLRoot):
    """
    A chemical entity enriched with data from multiple sources. Uses (inchikey, cas_rn) tuple as the primary key for
    entity resolution. Each primary API is authoritative for its own ID type: - PubChem is authoritative for
    pubchem_cid - ChEBI is authoritative for chebi_id and biological/chemical roles - CAS is authoritative for cas_rn
    - MediaDive is authoritative for mediadive_id
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = BIOLINK["SmallMolecule"]
    class_class_curie: ClassVar[str] = "biolink:SmallMolecule"
    class_name: ClassVar[str] = "EnrichedIngredient"
    class_model_uri: ClassVar[URIRef] = CMM.EnrichedIngredient

    id: Union[str, EnrichedIngredientId] = None
    inchikey: Optional[str] = None
    cas_rn: Optional[str] = None
    name: Optional[str] = None
    synonyms: Optional[Union[str, list[str]]] = empty_list()
    description: Optional[str] = None
    chemical_formula: Optional[str] = None
    chebi_id: Optional[Union[str, URIorCURIE]] = None
    pubchem_cid: Optional[int] = None
    mediadive_id: Optional[int] = None
    kegg_id: Optional[str] = None
    mesh_id: Optional[str] = None
    drugbank_id: Optional[str] = None
    inchi: Optional[str] = None
    smiles: Optional[str] = None
    molecular_mass: Optional[float] = None
    monoisotopic_mass: Optional[float] = None
    charge: Optional[int] = None
    biological_roles: Optional[Union[str, list[str]]] = empty_list()
    chemical_roles: Optional[Union[str, list[str]]] = empty_list()
    application_roles: Optional[Union[str, list[str]]] = empty_list()
    xrefs: Optional[Union[Union[dict, "CrossReference"], list[Union[dict, "CrossReference"]]]] = empty_list()
    source_records: Optional[Union[Union[dict, "SourceRecord"], list[Union[dict, "SourceRecord"]]]] = empty_list()
    conflicts: Optional[Union[Union[dict, "DataConflict"], list[Union[dict, "DataConflict"]]]] = empty_list()
    last_enriched: Optional[Union[str, XSDDateTime]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.id):
            self.MissingRequiredField("id")
        if not isinstance(self.id, EnrichedIngredientId):
            self.id = EnrichedIngredientId(self.id)

        if self.inchikey is not None and not isinstance(self.inchikey, str):
            self.inchikey = str(self.inchikey)

        if self.cas_rn is not None and not isinstance(self.cas_rn, str):
            self.cas_rn = str(self.cas_rn)

        if self.name is not None and not isinstance(self.name, str):
            self.name = str(self.name)

        if not isinstance(self.synonyms, list):
            self.synonyms = [self.synonyms] if self.synonyms is not None else []
        self.synonyms = [v if isinstance(v, str) else str(v) for v in self.synonyms]

        if self.description is not None and not isinstance(self.description, str):
            self.description = str(self.description)

        if self.chemical_formula is not None and not isinstance(self.chemical_formula, str):
            self.chemical_formula = str(self.chemical_formula)

        if self.chebi_id is not None and not isinstance(self.chebi_id, URIorCURIE):
            self.chebi_id = URIorCURIE(self.chebi_id)

        if self.pubchem_cid is not None and not isinstance(self.pubchem_cid, int):
            self.pubchem_cid = int(self.pubchem_cid)

        if self.mediadive_id is not None and not isinstance(self.mediadive_id, int):
            self.mediadive_id = int(self.mediadive_id)

        if self.kegg_id is not None and not isinstance(self.kegg_id, str):
            self.kegg_id = str(self.kegg_id)

        if self.mesh_id is not None and not isinstance(self.mesh_id, str):
            self.mesh_id = str(self.mesh_id)

        if self.drugbank_id is not None and not isinstance(self.drugbank_id, str):
            self.drugbank_id = str(self.drugbank_id)

        if self.inchi is not None and not isinstance(self.inchi, str):
            self.inchi = str(self.inchi)

        if self.smiles is not None and not isinstance(self.smiles, str):
            self.smiles = str(self.smiles)

        if self.molecular_mass is not None and not isinstance(self.molecular_mass, float):
            self.molecular_mass = float(self.molecular_mass)

        if self.monoisotopic_mass is not None and not isinstance(self.monoisotopic_mass, float):
            self.monoisotopic_mass = float(self.monoisotopic_mass)

        if self.charge is not None and not isinstance(self.charge, int):
            self.charge = int(self.charge)

        if not isinstance(self.biological_roles, list):
            self.biological_roles = [self.biological_roles] if self.biological_roles is not None else []
        self.biological_roles = [v if isinstance(v, str) else str(v) for v in self.biological_roles]

        if not isinstance(self.chemical_roles, list):
            self.chemical_roles = [self.chemical_roles] if self.chemical_roles is not None else []
        self.chemical_roles = [v if isinstance(v, str) else str(v) for v in self.chemical_roles]

        if not isinstance(self.application_roles, list):
            self.application_roles = [self.application_roles] if self.application_roles is not None else []
        self.application_roles = [v if isinstance(v, str) else str(v) for v in self.application_roles]

        if not isinstance(self.xrefs, list):
            self.xrefs = [self.xrefs] if self.xrefs is not None else []
        self.xrefs = [v if isinstance(v, CrossReference) else CrossReference(**as_dict(v)) for v in self.xrefs]

        if not isinstance(self.source_records, list):
            self.source_records = [self.source_records] if self.source_records is not None else []
        self.source_records = [v if isinstance(v, SourceRecord) else SourceRecord(**as_dict(v)) for v in self.source_records]

        if not isinstance(self.conflicts, list):
            self.conflicts = [self.conflicts] if self.conflicts is not None else []
        self.conflicts = [v if isinstance(v, DataConflict) else DataConflict(**as_dict(v)) for v in self.conflicts]

        if self.last_enriched is not None and not isinstance(self.last_enriched, XSDDateTime):
            self.last_enriched = XSDDateTime(self.last_enriched)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class SourceRecord(YAMLRoot):
    """
    Tracks the provenance of data from a specific source. Each field value can be traced back to its authoritative
    source.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = CMM["SourceRecord"]
    class_class_curie: ClassVar[str] = "cmm:SourceRecord"
    class_name: ClassVar[str] = "SourceRecord"
    class_model_uri: ClassVar[URIRef] = CMM.SourceRecord

    source_name: Optional[str] = None
    source_id: Optional[str] = None
    source_timestamp: Optional[Union[str, XSDDateTime]] = None
    source_query: Optional[str] = None
    source_fields: Optional[Union[str, list[str]]] = empty_list()

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.source_name is not None and not isinstance(self.source_name, str):
            self.source_name = str(self.source_name)

        if self.source_id is not None and not isinstance(self.source_id, str):
            self.source_id = str(self.source_id)

        if self.source_timestamp is not None and not isinstance(self.source_timestamp, XSDDateTime):
            self.source_timestamp = XSDDateTime(self.source_timestamp)

        if self.source_query is not None and not isinstance(self.source_query, str):
            self.source_query = str(self.source_query)

        if not isinstance(self.source_fields, list):
            self.source_fields = [self.source_fields] if self.source_fields is not None else []
        self.source_fields = [v if isinstance(v, str) else str(v) for v in self.source_fields]

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class DataConflict(YAMLRoot):
    """
    Records conflicts between data sources for reconciliation review. Primary APIs are considered authoritative for
    their own ID types.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = CMM["DataConflict"]
    class_class_curie: ClassVar[str] = "cmm:DataConflict"
    class_name: ClassVar[str] = "DataConflict"
    class_model_uri: ClassVar[URIRef] = CMM.DataConflict

    field_name: Optional[str] = None
    primary_source: Optional[str] = None
    primary_value: Optional[str] = None
    conflicting_source: Optional[str] = None
    conflicting_value: Optional[str] = None
    resolution: Optional[Union[str, "ConflictResolution"]] = None
    resolution_notes: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.field_name is not None and not isinstance(self.field_name, str):
            self.field_name = str(self.field_name)

        if self.primary_source is not None and not isinstance(self.primary_source, str):
            self.primary_source = str(self.primary_source)

        if self.primary_value is not None and not isinstance(self.primary_value, str):
            self.primary_value = str(self.primary_value)

        if self.conflicting_source is not None and not isinstance(self.conflicting_source, str):
            self.conflicting_source = str(self.conflicting_source)

        if self.conflicting_value is not None and not isinstance(self.conflicting_value, str):
            self.conflicting_value = str(self.conflicting_value)

        if self.resolution is not None and not isinstance(self.resolution, ConflictResolution):
            self.resolution = ConflictResolution(self.resolution)

        if self.resolution_notes is not None and not isinstance(self.resolution_notes, str):
            self.resolution_notes = str(self.resolution_notes)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class CrossReference(YAMLRoot):
    """
    A cross-reference to an external database or identifier
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = CMM["CrossReference"]
    class_class_curie: ClassVar[str] = "cmm:CrossReference"
    class_name: ClassVar[str] = "CrossReference"
    class_model_uri: ClassVar[URIRef] = CMM.CrossReference

    xref_type: str = None
    xref_id: str = None
    xref_label: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.xref_type):
            self.MissingRequiredField("xref_type")
        if not isinstance(self.xref_type, str):
            self.xref_type = str(self.xref_type)

        if self._is_empty(self.xref_id):
            self.MissingRequiredField("xref_id")
        if not isinstance(self.xref_id, str):
            self.xref_id = str(self.xref_id)

        if self.xref_label is not None and not isinstance(self.xref_label, str):
            self.xref_label = str(self.xref_label)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class CMMDatabase(YAMLRoot):
    """
    Container for all CMM entities
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = CMM["CMMDatabase"]
    class_class_curie: ClassVar[str] = "cmm:CMMDatabase"
    class_name: ClassVar[str] = "CMMDatabase"
    class_model_uri: ClassVar[URIRef] = CMM.CMMDatabase

    ingredients: Optional[Union[dict[Union[str, IngredientId], Union[dict, Ingredient]], list[Union[dict, Ingredient]]]] = empty_dict()
    solutions: Optional[Union[dict[Union[str, SolutionId], Union[dict, Solution]], list[Union[dict, Solution]]]] = empty_dict()
    media: Optional[Union[dict[Union[str, GrowthMediumId], Union[dict, GrowthMedium]], list[Union[dict, GrowthMedium]]]] = empty_dict()

    def __post_init__(self, *_: str, **kwargs: Any):
        self._normalize_inlined_as_list(slot_name="ingredients", slot_type=Ingredient, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="solutions", slot_type=Solution, key_name="id", keyed=True)

        self._normalize_inlined_as_list(slot_name="media", slot_type=GrowthMedium, key_name="id", keyed=True)

        super().__post_init__(**kwargs)


# Enumerations
class MediumType(EnumDefinitionImpl):
    """
    Classification of growth media by composition. Note: Functional properties like selective/differential are
    orthogonal and should be captured separately if needed.
    """
    minimal = PermissibleValue(
        text="minimal",
        description="Defined medium with minimal components")
    complex = PermissibleValue(
        text="complex",
        description="Contains undefined components like yeast extract")
    defined = PermissibleValue(
        text="defined",
        description="All components are chemically defined")
    semi_defined = PermissibleValue(
        text="semi_defined",
        description="Mostly defined but contains some complex components")

    _defn = EnumDefinition(
        name="MediumType",
        description="""Classification of growth media by composition. Note: Functional properties like selective/differential are orthogonal and should be captured separately if needed.""",
    )

class SolutionType(EnumDefinitionImpl):
    """
    Classification of stock solutions
    """
    trace_elements = PermissibleValue(
        text="trace_elements",
        description="Concentrated trace element mixture")
    vitamin = PermissibleValue(
        text="vitamin",
        description="Vitamin mixture")
    buffer = PermissibleValue(
        text="buffer",
        description="pH buffer stock")
    carbon_source = PermissibleValue(
        text="carbon_source",
        description="Concentrated carbon source")
    other = PermissibleValue(
        text="other",
        description="Other type of stock solution")

    _defn = EnumDefinition(
        name="SolutionType",
        description="Classification of stock solutions",
    )

class IngredientRole(EnumDefinitionImpl):
    """
    Functional role of an ingredient in a growth medium. TODO: Map to grounded ontology terms (METPO, OBI, or custom).
    See issue #11.
    """
    carbon_source = PermissibleValue(
        text="carbon_source",
        description="Provides carbon for biosynthesis and/or energy")
    nitrogen_source = PermissibleValue(
        text="nitrogen_source",
        description="Provides nitrogen for biosynthesis")
    phosphorus_source = PermissibleValue(
        text="phosphorus_source",
        description="Provides phosphorus")
    sulfur_source = PermissibleValue(
        text="sulfur_source",
        description="Provides sulfur")
    trace_element = PermissibleValue(
        text="trace_element",
        description="Micronutrient required in small amounts")
    mineral = PermissibleValue(
        text="mineral",
        description="Macro-mineral component")
    buffer = PermissibleValue(
        text="buffer",
        description="pH buffering agent",
        meaning=CHEBI["35225"])
    vitamin = PermissibleValue(
        text="vitamin",
        description="Essential vitamin or growth factor",
        meaning=CHEBI["33229"])
    solidifying_agent = PermissibleValue(
        text="solidifying_agent",
        description="Agent for solid media (e.g., agar)")
    selective_agent = PermissibleValue(
        text="selective_agent",
        description="Antibiotic or other selective compound")
    osmotic_stabilizer = PermissibleValue(
        text="osmotic_stabilizer",
        description="Maintains osmotic balance")

    _defn = EnumDefinition(
        name="IngredientRole",
        description="""Functional role of an ingredient in a growth medium. TODO: Map to grounded ontology terms (METPO, OBI, or custom). See issue #11.""",
    )

class ConcentrationUnit(EnumDefinitionImpl):
    """
    Units for concentration
    """
    g_per_L = PermissibleValue(
        text="g_per_L",
        description="Grams per liter",
        meaning=UO["0000175"])
    mg_per_L = PermissibleValue(
        text="mg_per_L",
        description="Milligrams per liter",
        meaning=UO["0000176"])
    ug_per_L = PermissibleValue(
        text="ug_per_L",
        description="Micrograms per liter",
        meaning=UO["0000301"])
    M = PermissibleValue(
        text="M",
        description="Molar",
        meaning=UO["0000062"])
    mM = PermissibleValue(
        text="mM",
        description="Millimolar",
        meaning=UO["0000063"])
    uM = PermissibleValue(
        text="uM",
        description="Micromolar",
        meaning=UO["0000064"])
    percent_w_v = PermissibleValue(
        text="percent_w_v",
        description="Weight/volume percentage: % (w/v)")
    percent_v_v = PermissibleValue(
        text="percent_v_v",
        description="Volume/volume percentage: % (v/v)")

    _defn = EnumDefinition(
        name="ConcentrationUnit",
        description="Units for concentration",
    )

class VolumeUnit(EnumDefinitionImpl):
    """
    Units for volume
    """
    mL = PermissibleValue(
        text="mL",
        description="Milliliters",
        meaning=UO["0000098"])
    L = PermissibleValue(
        text="L",
        description="Liters",
        meaning=UO["0000099"])
    uL = PermissibleValue(
        text="uL",
        description="Microliters",
        meaning=UO["0000101"])

    _defn = EnumDefinition(
        name="VolumeUnit",
        description="Units for volume",
    )

class ConflictResolution(EnumDefinitionImpl):
    """
    How a data conflict between sources was resolved. Primary APIs are considered authoritative for their own ID types.
    """
    primary_source_wins = PermissibleValue(
        text="primary_source_wins",
        description="Primary/authoritative source value was used")
    manual_review = PermissibleValue(
        text="manual_review",
        description="Conflict flagged for manual review")
    merged = PermissibleValue(
        text="merged",
        description="Values were merged (e.g., for lists)")
    unresolved = PermissibleValue(
        text="unresolved",
        description="Conflict not yet resolved")

    _defn = EnumDefinition(
        name="ConflictResolution",
        description="""How a data conflict between sources was resolved. Primary APIs are considered authoritative for their own ID types.""",
    )

class DataSource(EnumDefinitionImpl):
    """
    Names of data sources used for enrichment. Each source is authoritative for its own ID type.
    """
    pubchem = PermissibleValue(
        text="pubchem",
        description="PubChem (authoritative for pubchem_cid)")
    chebi = PermissibleValue(
        text="chebi",
        description="ChEBI 2.0 (authoritative for chebi_id, biological/chemical roles)")
    cas = PermissibleValue(
        text="cas",
        description="CAS Common Chemistry (authoritative for cas_rn)")
    mediadive = PermissibleValue(
        text="mediadive",
        description="MediaDive (authoritative for mediadive_id)")
    node_normalization = PermissibleValue(
        text="node_normalization",
        description="NCATS Translator NodeNormalization API (identifier bridging)")
    kg_microbe = PermissibleValue(
        text="kg_microbe",
        description="KG-Microbe knowledge graph")

    _defn = EnumDefinition(
        name="DataSource",
        description="Names of data sources used for enrichment. Each source is authoritative for its own ID type.",
    )

# Slots
class slots:
    pass

slots.id = Slot(uri=SCHEMA.identifier, name="id", curie=SCHEMA.curie('identifier'),
                   model_uri=CMM.id, domain=None, range=URIRef)

slots.name = Slot(uri=SCHEMA.name, name="name", curie=SCHEMA.curie('name'),
                   model_uri=CMM.name, domain=None, range=Optional[str])

slots.description = Slot(uri=SCHEMA.description, name="description", curie=SCHEMA.curie('description'),
                   model_uri=CMM.description, domain=None, range=Optional[str])

slots.synonyms = Slot(uri=CMM.synonyms, name="synonyms", curie=CMM.curie('synonyms'),
                   model_uri=CMM.synonyms, domain=None, range=Optional[Union[str, list[str]]])

slots.chemical_formula = Slot(uri=CMM.chemical_formula, name="chemical_formula", curie=CMM.curie('chemical_formula'),
                   model_uri=CMM.chemical_formula, domain=None, range=Optional[str])

slots.chebi_id = Slot(uri=CMM.chebi_id, name="chebi_id", curie=CMM.curie('chebi_id'),
                   model_uri=CMM.chebi_id, domain=None, range=Optional[Union[str, URIorCURIE]])

slots.cas_rn = Slot(uri=CMM.cas_rn, name="cas_rn", curie=CMM.curie('cas_rn'),
                   model_uri=CMM.cas_rn, domain=None, range=Optional[str],
                   pattern=re.compile(r'^\d{2,7}-\d{2}-\d$'))

slots.inchikey = Slot(uri=CMM.inchikey, name="inchikey", curie=CMM.curie('inchikey'),
                   model_uri=CMM.inchikey, domain=None, range=Optional[str],
                   pattern=re.compile(r'^[A-Z]{14}-[A-Z]{10}-[A-Z]$'))

slots.pubchem_cid = Slot(uri=CMM.pubchem_cid, name="pubchem_cid", curie=CMM.curie('pubchem_cid'),
                   model_uri=CMM.pubchem_cid, domain=None, range=Optional[int])

slots.xrefs = Slot(uri=CMM.xrefs, name="xrefs", curie=CMM.curie('xrefs'),
                   model_uri=CMM.xrefs, domain=None, range=Optional[Union[Union[dict, CrossReference], list[Union[dict, CrossReference]]]])

slots.xref_type = Slot(uri=CMM.xref_type, name="xref_type", curie=CMM.curie('xref_type'),
                   model_uri=CMM.xref_type, domain=None, range=Optional[str])

slots.xref_id = Slot(uri=CMM.xref_id, name="xref_id", curie=CMM.curie('xref_id'),
                   model_uri=CMM.xref_id, domain=None, range=Optional[str])

slots.xref_label = Slot(uri=CMM.xref_label, name="xref_label", curie=CMM.curie('xref_label'),
                   model_uri=CMM.xref_label, domain=None, range=Optional[str])

slots.has_ingredient_component = Slot(uri=CMM.has_ingredient_component, name="has_ingredient_component", curie=CMM.curie('has_ingredient_component'),
                   model_uri=CMM.has_ingredient_component, domain=None, range=Optional[Union[Union[dict, IngredientComponent], list[Union[dict, IngredientComponent]]]])

slots.has_solution_component = Slot(uri=CMM.has_solution_component, name="has_solution_component", curie=CMM.curie('has_solution_component'),
                   model_uri=CMM.has_solution_component, domain=None, range=Optional[Union[Union[dict, SolutionComponent], list[Union[dict, SolutionComponent]]]])

slots.ingredient = Slot(uri=CMM.ingredient, name="ingredient", curie=CMM.curie('ingredient'),
                   model_uri=CMM.ingredient, domain=None, range=Optional[Union[str, IngredientId]])

slots.solution = Slot(uri=CMM.solution, name="solution", curie=CMM.curie('solution'),
                   model_uri=CMM.solution, domain=None, range=Optional[Union[str, SolutionId]])

slots.concentration_value = Slot(uri=CMM.concentration_value, name="concentration_value", curie=CMM.curie('concentration_value'),
                   model_uri=CMM.concentration_value, domain=None, range=Optional[float])

slots.concentration_unit = Slot(uri=CMM.concentration_unit, name="concentration_unit", curie=CMM.curie('concentration_unit'),
                   model_uri=CMM.concentration_unit, domain=None, range=Optional[Union[str, "ConcentrationUnit"]])

slots.volume_per_liter = Slot(uri=CMM.volume_per_liter, name="volume_per_liter", curie=CMM.curie('volume_per_liter'),
                   model_uri=CMM.volume_per_liter, domain=None, range=Optional[float])

slots.volume_unit = Slot(uri=CMM.volume_unit, name="volume_unit", curie=CMM.curie('volume_unit'),
                   model_uri=CMM.volume_unit, domain=None, range=Optional[Union[str, "VolumeUnit"]])

slots.roles = Slot(uri=CMM.roles, name="roles", curie=CMM.curie('roles'),
                   model_uri=CMM.roles, domain=None, range=Optional[Union[Union[str, "IngredientRole"], list[Union[str, "IngredientRole"]]]])

slots.medium_type = Slot(uri=CMM.medium_type, name="medium_type", curie=CMM.curie('medium_type'),
                   model_uri=CMM.medium_type, domain=None, range=Optional[Union[str, "MediumType"]])

slots.solution_type = Slot(uri=CMM.solution_type, name="solution_type", curie=CMM.curie('solution_type'),
                   model_uri=CMM.solution_type, domain=None, range=Optional[Union[str, "SolutionType"]])

slots.ph = Slot(uri=CMM.ph, name="ph", curie=CMM.curie('ph'),
                   model_uri=CMM.ph, domain=None, range=Optional[float])

slots.sterilization_method = Slot(uri=CMM.sterilization_method, name="sterilization_method", curie=CMM.curie('sterilization_method'),
                   model_uri=CMM.sterilization_method, domain=None, range=Optional[str])

slots.target_organisms = Slot(uri=CMM.target_organisms, name="target_organisms", curie=CMM.curie('target_organisms'),
                   model_uri=CMM.target_organisms, domain=None, range=Optional[Union[str, list[str]]])

slots.references = Slot(uri=CMM.references, name="references", curie=CMM.curie('references'),
                   model_uri=CMM.references, domain=None, range=Optional[Union[str, list[str]]])

slots.notes = Slot(uri=CMM.notes, name="notes", curie=CMM.curie('notes'),
                   model_uri=CMM.notes, domain=None, range=Optional[str])

slots.mediadive_id = Slot(uri=CMM.mediadive_id, name="mediadive_id", curie=CMM.curie('mediadive_id'),
                   model_uri=CMM.mediadive_id, domain=None, range=Optional[int])

slots.kegg_id = Slot(uri=CMM.kegg_id, name="kegg_id", curie=CMM.curie('kegg_id'),
                   model_uri=CMM.kegg_id, domain=None, range=Optional[str])

slots.mesh_id = Slot(uri=CMM.mesh_id, name="mesh_id", curie=CMM.curie('mesh_id'),
                   model_uri=CMM.mesh_id, domain=None, range=Optional[str])

slots.drugbank_id = Slot(uri=CMM.drugbank_id, name="drugbank_id", curie=CMM.curie('drugbank_id'),
                   model_uri=CMM.drugbank_id, domain=None, range=Optional[str])

slots.inchi = Slot(uri=CMM.inchi, name="inchi", curie=CMM.curie('inchi'),
                   model_uri=CMM.inchi, domain=None, range=Optional[str])

slots.smiles = Slot(uri=CMM.smiles, name="smiles", curie=CMM.curie('smiles'),
                   model_uri=CMM.smiles, domain=None, range=Optional[str])

slots.molecular_mass = Slot(uri=CMM.molecular_mass, name="molecular_mass", curie=CMM.curie('molecular_mass'),
                   model_uri=CMM.molecular_mass, domain=None, range=Optional[float])

slots.monoisotopic_mass = Slot(uri=CMM.monoisotopic_mass, name="monoisotopic_mass", curie=CMM.curie('monoisotopic_mass'),
                   model_uri=CMM.monoisotopic_mass, domain=None, range=Optional[float])

slots.charge = Slot(uri=CMM.charge, name="charge", curie=CMM.curie('charge'),
                   model_uri=CMM.charge, domain=None, range=Optional[int])

slots.biological_roles = Slot(uri=CMM.biological_roles, name="biological_roles", curie=CMM.curie('biological_roles'),
                   model_uri=CMM.biological_roles, domain=None, range=Optional[Union[str, list[str]]])

slots.chemical_roles = Slot(uri=CMM.chemical_roles, name="chemical_roles", curie=CMM.curie('chemical_roles'),
                   model_uri=CMM.chemical_roles, domain=None, range=Optional[Union[str, list[str]]])

slots.application_roles = Slot(uri=CMM.application_roles, name="application_roles", curie=CMM.curie('application_roles'),
                   model_uri=CMM.application_roles, domain=None, range=Optional[Union[str, list[str]]])

slots.source_records = Slot(uri=CMM.source_records, name="source_records", curie=CMM.curie('source_records'),
                   model_uri=CMM.source_records, domain=None, range=Optional[Union[Union[dict, SourceRecord], list[Union[dict, SourceRecord]]]])

slots.conflicts = Slot(uri=CMM.conflicts, name="conflicts", curie=CMM.curie('conflicts'),
                   model_uri=CMM.conflicts, domain=None, range=Optional[Union[Union[dict, DataConflict], list[Union[dict, DataConflict]]]])

slots.last_enriched = Slot(uri=CMM.last_enriched, name="last_enriched", curie=CMM.curie('last_enriched'),
                   model_uri=CMM.last_enriched, domain=None, range=Optional[Union[str, XSDDateTime]])

slots.source_name = Slot(uri=CMM.source_name, name="source_name", curie=CMM.curie('source_name'),
                   model_uri=CMM.source_name, domain=None, range=Optional[str])

slots.source_id = Slot(uri=CMM.source_id, name="source_id", curie=CMM.curie('source_id'),
                   model_uri=CMM.source_id, domain=None, range=Optional[str])

slots.source_timestamp = Slot(uri=CMM.source_timestamp, name="source_timestamp", curie=CMM.curie('source_timestamp'),
                   model_uri=CMM.source_timestamp, domain=None, range=Optional[Union[str, XSDDateTime]])

slots.source_query = Slot(uri=CMM.source_query, name="source_query", curie=CMM.curie('source_query'),
                   model_uri=CMM.source_query, domain=None, range=Optional[str])

slots.source_fields = Slot(uri=CMM.source_fields, name="source_fields", curie=CMM.curie('source_fields'),
                   model_uri=CMM.source_fields, domain=None, range=Optional[Union[str, list[str]]])

slots.field_name = Slot(uri=CMM.field_name, name="field_name", curie=CMM.curie('field_name'),
                   model_uri=CMM.field_name, domain=None, range=Optional[str])

slots.primary_source = Slot(uri=CMM.primary_source, name="primary_source", curie=CMM.curie('primary_source'),
                   model_uri=CMM.primary_source, domain=None, range=Optional[str])

slots.primary_value = Slot(uri=CMM.primary_value, name="primary_value", curie=CMM.curie('primary_value'),
                   model_uri=CMM.primary_value, domain=None, range=Optional[str])

slots.conflicting_source = Slot(uri=CMM.conflicting_source, name="conflicting_source", curie=CMM.curie('conflicting_source'),
                   model_uri=CMM.conflicting_source, domain=None, range=Optional[str])

slots.conflicting_value = Slot(uri=CMM.conflicting_value, name="conflicting_value", curie=CMM.curie('conflicting_value'),
                   model_uri=CMM.conflicting_value, domain=None, range=Optional[str])

slots.resolution = Slot(uri=CMM.resolution, name="resolution", curie=CMM.curie('resolution'),
                   model_uri=CMM.resolution, domain=None, range=Optional[Union[str, "ConflictResolution"]])

slots.resolution_notes = Slot(uri=CMM.resolution_notes, name="resolution_notes", curie=CMM.curie('resolution_notes'),
                   model_uri=CMM.resolution_notes, domain=None, range=Optional[str])

slots.cMMDatabase__ingredients = Slot(uri=CMM.ingredients, name="cMMDatabase__ingredients", curie=CMM.curie('ingredients'),
                   model_uri=CMM.cMMDatabase__ingredients, domain=None, range=Optional[Union[dict[Union[str, IngredientId], Union[dict, Ingredient]], list[Union[dict, Ingredient]]]])

slots.cMMDatabase__solutions = Slot(uri=CMM.solutions, name="cMMDatabase__solutions", curie=CMM.curie('solutions'),
                   model_uri=CMM.cMMDatabase__solutions, domain=None, range=Optional[Union[dict[Union[str, SolutionId], Union[dict, Solution]], list[Union[dict, Solution]]]])

slots.cMMDatabase__media = Slot(uri=CMM.media, name="cMMDatabase__media", curie=CMM.curie('media'),
                   model_uri=CMM.cMMDatabase__media, domain=None, range=Optional[Union[dict[Union[str, GrowthMediumId], Union[dict, GrowthMedium]], list[Union[dict, GrowthMedium]]]])

slots.IngredientComponent_ingredient = Slot(uri=CMM.ingredient, name="IngredientComponent_ingredient", curie=CMM.curie('ingredient'),
                   model_uri=CMM.IngredientComponent_ingredient, domain=IngredientComponent, range=Union[str, IngredientId])

slots.SolutionComponent_solution = Slot(uri=CMM.solution, name="SolutionComponent_solution", curie=CMM.curie('solution'),
                   model_uri=CMM.SolutionComponent_solution, domain=SolutionComponent, range=Union[str, SolutionId])

slots.CrossReference_xref_type = Slot(uri=CMM.xref_type, name="CrossReference_xref_type", curie=CMM.curie('xref_type'),
                   model_uri=CMM.CrossReference_xref_type, domain=CrossReference, range=str)

slots.CrossReference_xref_id = Slot(uri=CMM.xref_id, name="CrossReference_xref_id", curie=CMM.curie('xref_id'),
                   model_uri=CMM.CrossReference_xref_id, domain=CrossReference, range=str)
