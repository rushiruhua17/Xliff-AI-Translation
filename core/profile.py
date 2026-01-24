from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import json

class ProfileStatus(str, Enum):
    NEW = "new"
    DRAFT = "draft"
    CONFIRMED = "confirmed"

@dataclass
class ProjectMetadata:
    client_name: str = ""
    domain: str = ""
    project_type: str = ""  # e.g., "Software UI", "Marketing", "Legal"
    target_audience: str = ""

@dataclass
class TerminologyPolicy:
    strictness: str = "strict"  # strict, prefer, loose
    allow_explanation: bool = False
    use_termbase: bool = False
    use_translation_memory: bool = False
    do_not_translate: List[str] = field(default_factory=list)
    forbidden_terms: List[str] = field(default_factory=list)

@dataclass
class FormattingRules:
    preserve_source_numbers: bool = True
    decimal_separator: str = "."
    thousands_separator: str = ","
    preferred_date_format: str = "MMMM D, YYYY"
    preserve_source_numeric_dates: bool = True
    unit_system: str = "SI"  # SI, Imperial, Mixed
    dual_units: bool = False
    auto_convert_units: bool = False
    quotes_style: str = "double"  # double, single
    keep_source_capitalization: bool = True
    preserve_placeholders: bool = True  # Added back for {n} protection logic

@dataclass
class TranslationBrief:
    tone: str = "neutral"  # formal, casual, neutral
    formality: str = "neutral"
    locale_variant: str = ""  # e.g., "zh-CN", "zh-TW"
    style_guide_notes: str = ""
    terminology: TerminologyPolicy = field(default_factory=TerminologyPolicy)
    formatting: FormattingRules = field(default_factory=FormattingRules)

class ProfileTemplate(str, Enum):
    MANUAL = "manual"
    WARRANTY = "warranty_policy"
    TRAINING = "training_material"

@dataclass
class ControlsConfig:
    status: ProfileStatus = ProfileStatus.NEW
    last_modified: str = ""
    version: str = "1.0"

@dataclass
class TranslationProfile:
    project_metadata: ProjectMetadata = field(default_factory=ProjectMetadata)
    brief: TranslationBrief = field(default_factory=TranslationBrief)
    controls: ControlsConfig = field(default_factory=ControlsConfig)

@dataclass
class TranslationProfileContainer:
    schema_version: str = "1.0"
    profile: TranslationProfile = field(default_factory=TranslationProfile)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile": {
                "project_metadata": self.profile.project_metadata.__dict__,
                "brief": {
                    "tone": self.profile.brief.tone,
                    "formality": self.profile.brief.formality,
                    "locale_variant": self.profile.brief.locale_variant,
                    "style_guide_notes": self.profile.brief.style_guide_notes,
                    "terminology": {
                        "strictness": self.profile.brief.terminology.strictness,
                        "allow_explanation": self.profile.brief.terminology.allow_explanation,
                        "use_termbase": self.profile.brief.terminology.use_termbase,
                        "use_translation_memory": self.profile.brief.terminology.use_translation_memory,
                        "do_not_translate": self.profile.brief.terminology.do_not_translate,
                        "forbidden_terms": self.profile.brief.terminology.forbidden_terms
                    },
                    "formatting": {
                        "preserve_source_numbers": self.profile.brief.formatting.preserve_source_numbers,
                        "decimal_separator": self.profile.brief.formatting.decimal_separator,
                        "thousands_separator": self.profile.brief.formatting.thousands_separator,
                        "preferred_date_format": self.profile.brief.formatting.preferred_date_format,
                        "preserve_source_numeric_dates": self.profile.brief.formatting.preserve_source_numeric_dates,
                        "unit_system": self.profile.brief.formatting.unit_system,
                        "dual_units": self.profile.brief.formatting.dual_units,
                        "auto_convert_units": self.profile.brief.formatting.auto_convert_units,
                        "quotes_style": self.profile.brief.formatting.quotes_style,
                        "keep_source_capitalization": self.profile.brief.formatting.keep_source_capitalization,
                        "preserve_placeholders": self.profile.brief.formatting.preserve_placeholders
                    }
                },
                "controls": {
                    "status": self.profile.controls.status.value,
                    "last_modified": self.profile.controls.last_modified,
                    "version": self.profile.controls.version
                }
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TranslationProfileContainer':
        container = cls()
        container.schema_version = data.get("schema_version", "1.0")
        
        prof_data = data.get("profile", {})
        
        # Metadata
        meta_data = prof_data.get("project_metadata", {})
        container.profile.project_metadata = ProjectMetadata(**meta_data)
        
        # Brief
        brief_data = prof_data.get("brief", {})
        term_data = brief_data.get("terminology", {})
        fmt_data = brief_data.get("formatting", {})
        
        brief = TranslationBrief()
        brief.tone = brief_data.get("tone", "neutral")
        brief.formality = brief_data.get("formality", "neutral")
        brief.locale_variant = brief_data.get("locale_variant", "")
        brief.style_guide_notes = brief_data.get("style_guide_notes", "")
        
        # Mapping Terminology
        brief.terminology.strictness = term_data.get("strictness", "strict")
        brief.terminology.allow_explanation = term_data.get("allow_explanation", False)
        brief.terminology.use_termbase = term_data.get("use_termbase", False)
        brief.terminology.use_translation_memory = term_data.get("use_translation_memory", False)
        brief.terminology.do_not_translate = term_data.get("do_not_translate", [])
        brief.terminology.forbidden_terms = term_data.get("forbidden_terms", [])
        
        # Mapping Formatting
        brief.formatting.preserve_source_numbers = fmt_data.get("preserve_source_numbers", True)
        brief.formatting.decimal_separator = fmt_data.get("decimal_separator", ".")
        brief.formatting.thousands_separator = fmt_data.get("thousands_separator", ",")
        brief.formatting.preferred_date_format = fmt_data.get("preferred_date_format", "MMMM D, YYYY")
        brief.formatting.preserve_source_numeric_dates = fmt_data.get("preserve_source_numeric_dates", True)
        brief.formatting.unit_system = fmt_data.get("unit_system", "SI")
        brief.formatting.dual_units = fmt_data.get("dual_units", False)
        brief.formatting.auto_convert_units = fmt_data.get("auto_convert_units", False)
        brief.formatting.quotes_style = fmt_data.get("quotes_style", "double")
        brief.formatting.keep_source_capitalization = fmt_data.get("keep_source_capitalization", True)
        brief.formatting.preserve_placeholders = fmt_data.get("preserve_placeholders", True)
        
        container.profile.brief = brief
        
        # Controls
        ctrl_data = prof_data.get("controls", {})
        controls = ControlsConfig()
        controls.status = ProfileStatus(ctrl_data.get("status", "new"))
        controls.last_modified = ctrl_data.get("last_modified", "")
        controls.version = ctrl_data.get("version", "1.0")
        container.profile.controls = controls
        
        return container

    @staticmethod
    def get_template(template_type: ProfileTemplate) -> TranslationProfile:
        p = TranslationProfile()
        if template_type == ProfileTemplate.MANUAL:
            p.brief.tone = "neutral"
            p.brief.formality = "neutral"
            p.brief.style_guide_notes = "Clear, concise, and instructive. Avoid jargon unless necessary."
            p.project_metadata.project_type = "User Manual"
        elif template_type == ProfileTemplate.WARRANTY:
            p.brief.tone = "authoritative"
            p.brief.formality = "formal"
            p.brief.terminology.strictness = "strict"
            p.brief.style_guide_notes = "Use legal terminology. Ensure all liability disclaimers are precise."
            p.project_metadata.project_type = "Legal / Warranty"
        elif template_type == ProfileTemplate.TRAINING:
            p.brief.tone = "friendly"
            p.brief.formality = "informal"
            p.brief.style_guide_notes = "Engaging and encouraging. Use direct address ('You')."
            p.project_metadata.project_type = "Training Course"
        return p
