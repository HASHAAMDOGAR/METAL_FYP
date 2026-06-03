"""Public catalog: browse, search, detail, reviews (spec §5.2)."""
from __future__ import annotations

from typing import Literal

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, Query

from app import errors
from app.deps import get_current_user
from app.models.enums import Architecture, LicenseStatus, ModelStatus
from app.models.license import License
from app.models.model import ModelDoc
from app.models.review import Review
from app.models.user import User
from app.schemas.common import Page
from app.schemas.model import ModelDetail, ModelListItem, to_detail, to_list_item
from app.schemas.review import CreateReviewRequest, ReviewResponse

router = APIRouter(tags=["catalog"])

SortKey = Literal["downloads", "rating", "newest"]
_SORT = {
    "downloads": [("metrics.downloads", -1)],
    "rating": [("metrics.rating_avg", -1)],
    "newest": [("created_at", -1)],
}


@router.get("/models", response_model=Page[ModelListItem])
async def list_models(
    q: str | None = None,
    architecture: Architecture | None = None,
    tags: list[str] | None = Query(default=None),
    min_params: float | None = None,
    max_params: float | None = None,
    sort: SortKey = "newest",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[ModelListItem]:
    query: dict = {"status": ModelStatus.approved.value}
    if q:
        query["$text"] = {"$search": q}
    if architecture:
        query["architecture"] = architecture.value
    if tags:
        query["tags"] = {"$all": tags}
    if min_params is not None or max_params is not None:
        rng: dict = {}
        if min_params is not None:
            rng["$gte"] = min_params
        if max_params is not None:
            rng["$lte"] = max_params
        query["param_count_b"] = rng

    total = await ModelDoc.find(query).count()
    cursor = (
        ModelDoc.find(query)
        .sort(_SORT[sort])
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    docs = await cursor.to_list()
    return Page(
        items=[to_list_item(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
    )


async def _get_approved_by_slug(slug: str) -> ModelDoc:
    model = await ModelDoc.find_one(ModelDoc.slug == slug)
    if model is None or model.status != ModelStatus.approved:
        raise errors.not_found("Model not found", code="model_not_found")
    return model


@router.get("/models/{slug}", response_model=ModelDetail)
async def get_model(slug: str) -> ModelDetail:
    return to_detail(await _get_approved_by_slug(slug))


@router.get("/models/{slug}/reviews", response_model=Page[ReviewResponse])
async def list_reviews(
    slug: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[ReviewResponse]:
    model = await _get_approved_by_slug(slug)
    total = await Review.find(Review.model_id == model.id).count()
    docs = (
        await Review.find(Review.model_id == model.id)
        .sort([("created_at", -1)])
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list()
    )
    return Page(
        items=[
            ReviewResponse(
                id=str(r.id),
                model_id=str(r.model_id),
                user_id=str(r.user_id),
                rating=r.rating,
                title=r.title,
                body=r.body,
                created_at=r.created_at,
            )
            for r in docs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/models/{slug}/reviews", response_model=ReviewResponse, status_code=201)
async def create_review(
    slug: str,
    body: CreateReviewRequest,
    user: User = Depends(get_current_user),
) -> ReviewResponse:
    model = await _get_approved_by_slug(slug)

    # Must hold a license to review (community quality control, spec Feature 4).
    has_license = await License.find_one(
        License.user_id == user.id,
        License.model_id == model.id,
        License.status == LicenseStatus.active,
    )
    if has_license is None:
        raise errors.forbidden("Acquire the model before reviewing", code="license_required")

    existing = await Review.find_one(
        Review.model_id == model.id, Review.user_id == user.id
    )
    if existing is not None:
        raise errors.conflict("You already reviewed this model", code="review_exists")

    review = Review(
        model_id=model.id,
        user_id=user.id,
        rating=body.rating,
        title=body.title,
        body=body.body,
    )
    await review.insert()
    await _recompute_rating(model.id)

    return ReviewResponse(
        id=str(review.id),
        model_id=str(review.model_id),
        user_id=str(review.user_id),
        rating=review.rating,
        title=review.title,
        body=review.body,
        created_at=review.created_at,
    )


async def _recompute_rating(model_id: PydanticObjectId) -> None:
    pipeline = [
        {"$match": {"model_id": model_id}},
        {"$group": {"_id": "$model_id", "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
    ]
    agg = await Review.aggregate(pipeline).to_list()
    model = await ModelDoc.get(model_id)
    if model is None:
        return
    if agg:
        model.metrics.rating_avg = round(agg[0]["avg"], 2)
        model.metrics.rating_count = agg[0]["count"]
    else:
        model.metrics.rating_avg = 0.0
        model.metrics.rating_count = 0
    await model.save()
