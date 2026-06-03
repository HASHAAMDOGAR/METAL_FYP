"""Shared enums used across documents and schemas (spec §4, §8.3)."""
from enum import Enum


class Role(str, Enum):
    app_developer = "app_developer"
    model_developer = "model_developer"
    admin = "admin"


class Architecture(str, Enum):
    llama = "llama"
    mistral = "mistral"
    qwen = "qwen"
    phi = "phi"
    gemma = "gemma"
    other = "other"


class Quantization(str, Enum):
    q4_k_m = "Q4_K_M"
    q4_0 = "Q4_0"
    q5_k_m = "Q5_K_M"
    q6_k = "Q6_K"
    q8_0 = "Q8_0"
    f16 = "F16"


class FileFormat(str, Enum):
    gguf = "gguf"


class ModelStatus(str, Enum):
    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    archived = "archived"


class LicenseStatus(str, Enum):
    active = "active"
    revoked = "revoked"


class DeviceStatus(str, Enum):
    active = "active"
    unbound = "unbound"


class EventType(str, Enum):
    deploy = "deploy"
    inference = "inference"
    unload = "unload"
    download = "download"


class InferencePath(str, Enum):
    local_metal = "local_metal"
    cloud_modal = "cloud_modal"


class InferenceReason(str, Enum):
    no_metal_device = "no_metal_device"
    oom = "oom"
    daemon_down = "daemon_down"
