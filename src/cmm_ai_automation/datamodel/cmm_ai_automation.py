# Auto generated from cmm_ai_automation.yaml by pythongen.py version: 0.0.1
# Generation date: 2025-12-09T19:54:48
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

from linkml_runtime.linkml_model.types import Float, Integer, String, Uriorcurie
from linkml_runtime.utils.metamodelcore import URIorCURIE

metamodel_version = "1.7.0"
version = None

# Namespaces
ATCC = CurieNamespace('ATCC', 'https://www.atcc.org/products/')
CHEBI = CurieNamespace('CHEBI', 'http://purl.obolibrary.org/obo/CHEBI_')
DSMZ = CurieNamespace('DSMZ', 'https://www.dsmz.de/collection/catalogue/details/culture/DSM-')
ENVO = CurieNamespace('ENVO', 'http://purl.obolibrary.org/obo/ENVO_')
NCBITAXON = CurieNamespace('NCBITaxon', 'http://purl.obolibrary.org/obo/NCBITaxon_')
OBI = CurieNamespace('OBI', 'http://purl.obolibrary.org/obo/OBI_')
RO = CurieNamespace('RO', 'http://purl.obolibrary.org/obo/RO_')
UO = CurieNamespace('UO', 'http://purl.obolibrary.org/obo/UO_')
BIOLINK = CurieNamespace('biolink', 'https://w3id.org/biolink/')
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

    ingredient: Optional[Union[str, IngredientId]] = None
    concentration_value: Optional[float] = None
    concentration_unit: Optional[Union[str, "ConcentrationUnit"]] = None
    roles: Optional[Union[Union[str, "IngredientRole"], list[Union[str, "IngredientRole"]]]] = empty_list()
    notes: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.ingredient is not None and not isinstance(self.ingredient, IngredientId):
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

    solution: Optional[Union[str, SolutionId]] = None
    volume_per_liter: Optional[float] = None
    volume_unit: Optional[Union[str, "VolumeUnit"]] = None
    notes: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.solution is not None and not isinstance(self.solution, SolutionId):
            self.solution = SolutionId(self.solution)

        if self.volume_per_liter is not None and not isinstance(self.volume_per_liter, float):
            self.volume_per_liter = float(self.volume_per_liter)

        if self.volume_unit is not None and not isinstance(self.volume_unit, VolumeUnit):
            self.volume_unit = VolumeUnit(self.volume_unit)

        if self.notes is not None and not isinstance(self.notes, str):
            self.notes = str(self.notes)

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

    xref_type: Optional[str] = None
    xref_id: Optional[str] = None
    xref_label: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self.xref_type is not None and not isinstance(self.xref_type, str):
            self.xref_type = str(self.xref_type)

        if self.xref_id is not None and not isinstance(self.xref_id, str):
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
    Classification of growth media
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
    selective = PermissibleValue(
        text="selective",
        description="Contains agents to select for specific organisms")
    differential = PermissibleValue(
        text="differential",
        description="Allows differentiation between organism types")

    _defn = EnumDefinition(
        name="MediumType",
        description="Classification of growth media",
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
        description="Essential vitamin or growth factor")
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
        description="Milligrams per liter")
    ug_per_L = PermissibleValue(
        text="ug_per_L",
        description="Micrograms per liter")
    M = PermissibleValue(
        text="M",
        description="Molar",
        meaning=UO["0000062"])
    mM = PermissibleValue(
        text="mM",
        description="Millimolar")
    uM = PermissibleValue(
        text="uM",
        description="Micromolar")
    percent_w_v = PermissibleValue(
        text="percent_w_v",
        description="Weight/volume percentage")
    percent_v_v = PermissibleValue(
        text="percent_v_v",
        description="Volume/volume percentage")

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

slots.cMMDatabase__ingredients = Slot(uri=CMM.ingredients, name="cMMDatabase__ingredients", curie=CMM.curie('ingredients'),
                   model_uri=CMM.cMMDatabase__ingredients, domain=None, range=Optional[Union[dict[Union[str, IngredientId], Union[dict, Ingredient]], list[Union[dict, Ingredient]]]])

slots.cMMDatabase__solutions = Slot(uri=CMM.solutions, name="cMMDatabase__solutions", curie=CMM.curie('solutions'),
                   model_uri=CMM.cMMDatabase__solutions, domain=None, range=Optional[Union[dict[Union[str, SolutionId], Union[dict, Solution]], list[Union[dict, Solution]]]])

slots.cMMDatabase__media = Slot(uri=CMM.media, name="cMMDatabase__media", curie=CMM.curie('media'),
                   model_uri=CMM.cMMDatabase__media, domain=None, range=Optional[Union[dict[Union[str, GrowthMediumId], Union[dict, GrowthMedium]], list[Union[dict, GrowthMedium]]]])
