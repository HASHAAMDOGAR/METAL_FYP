"""Seed an admin, a publisher, and 3 approved free models (spec §10 verification).

Usage (with a running MongoDB and configured .env):

    python -m scripts.seed
"""
from __future__ import annotations

import asyncio

from app.db import init_db
from app.models.enums import Architecture, ModelStatus, Quantization, Role
from app.models.model import Artifact, CloudInference, ModelDoc
from app.models.user import PublisherProfile, User
from app.security import hash_password
from app.utils import slugify, unique_suffix

SEED_MODELS = [
    ("Llama 3 8B Instruct (Q4)", Architecture.llama, "llama-3-8b-instruct", 8.0),
    ("Mistral 7B Instruct (Q4)", Architecture.mistral, "mistral-7b-instruct", 7.0),
    ("Qwen2.5 7B Instruct (Q4)", Architecture.qwen, "qwen2.5-7b-instruct", 7.0),
]


async def main() -> None:
    await init_db()

    admin = await User.find_one(User.email == "admin@metal.dev")
    if admin is None:
        admin = User(
            email="admin@metal.dev",
            username="admin",
            password_hash=hash_password("admin12345"),
            roles=[Role.app_developer, Role.model_developer, Role.admin],
            display_name="Platform Admin",
            publisher_profile=PublisherProfile(org_name="Metal Marketplace"),
        )
        await admin.insert()
        print("Created admin@metal.dev / admin12345")

    for name, arch, ref, params in SEED_MODELS:
        if await ModelDoc.find_one(ModelDoc.name == name):
            continue
        model = ModelDoc(
            slug=f"{slugify(name)}-{unique_suffix()}",
            name=name,
            publisher_id=admin.id,
            description=f"{name} — Metal-optimized GGUF, free.",
            architecture=arch,
            quantization=Quantization.q4_k_m,
            param_count_b=params,
            context_length=8192,
            min_ram_gb=16,
            tags=["chat", "instruct"],
            use_cases=["chat", "summarization"],
            status=ModelStatus.approved,
            artifact=Artifact(
                storage_key=f"models/{ref}/model.gguf",
                size_bytes=4733280256,
                sha256="seed-placeholder-sha256",
                version="1.0.0",
            ),
            cloud_inference=CloudInference(enabled=True, served_model_ref=ref),
        )
        await model.insert()
        print(f"Created model: {name}")

    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
