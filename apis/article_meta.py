from collections import Counter

from fastapi import APIRouter, Depends, Query

from fields.article_meta import (
    ArticleCategoryCreate,
    ArticleCategoryUpdate,
    ArticleTagCreate,
    ArticleTagUpdate,
)
from models.article import SystemArticle
from models.article_meta import SystemArticleCategory, SystemArticleTag
from utils.pagination import PageParams, get_page_params
from utils.response import ResponseUtil


articleCategoryAPI = APIRouter(prefix="/article-category", tags=["article-category"])
articleTagAPI = APIRouter(prefix="/article-tag", tags=["article-tag"])


def normalize_tag_ids(tag_ids: list[str] | None) -> list[str]:
    if not tag_ids:
        return []
    return [str(item) for item in tag_ids if item]


async def build_category_usage_counts(category_ids: list[str] | None = None) -> dict[str, int]:
    queryset = SystemArticle.filter(is_del=False)
    if category_ids:
        queryset = queryset.filter(category_id__in=category_ids)

    rows = await queryset.values("category_id")
    counter: Counter[str] = Counter()
    for row in rows:
        category_id = row.get("category_id")
        if category_id:
            counter[str(category_id)] += 1
    return dict(counter)


async def build_tag_usage_counts(tag_ids: list[str] | None = None) -> dict[str, int]:
    rows = await SystemArticle.filter(is_del=False).values("tag_ids")
    counter: Counter[str] = Counter()
    target_ids = {str(item) for item in tag_ids or []}

    for row in rows:
        article_tag_ids = normalize_tag_ids(row.get("tag_ids"))
        for tag_id in article_tag_ids:
            if target_ids and tag_id not in target_ids:
                continue
            counter[tag_id] += 1

    return dict(counter)


async def ensure_unique_category_name(name: str, exclude_id: str | None = None) -> bool:
    queryset = SystemArticleCategory.filter(name=name.strip(), is_del=False)
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    return not await queryset.exists()


async def ensure_unique_tag_name(name: str, exclude_id: str | None = None) -> bool:
    queryset = SystemArticleTag.filter(name=name.strip(), is_del=False)
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    return not await queryset.exists()


async def sync_article_tag_names(target_tag_id: str | None = None) -> None:
    tag_rows = await SystemArticleTag.filter(is_del=False).values("id", "name")
    tag_map = {str(item["id"]): item["name"] for item in tag_rows}
    article_rows = await SystemArticle.filter(is_del=False).values("id", "tag_ids")

    for article in article_rows:
        current_tag_ids = normalize_tag_ids(article.get("tag_ids"))
        if target_tag_id and target_tag_id not in current_tag_ids:
            continue
        tag_names = [tag_map[item] for item in current_tag_ids if item in tag_map]
        await SystemArticle.filter(id=article["id"], is_del=False).update(tag_names=tag_names)


@articleCategoryAPI.get("/list", summary="Article category list")
async def list_article_categories(
    name: str | None = Query(default=None),
    status: int | None = Query(default=None),
    page: PageParams = Depends(get_page_params),
):
    queryset = SystemArticleCategory.filter(is_del=False)
    if name:
        queryset = queryset.filter(name__icontains=name)
    if status is not None:
        queryset = queryset.filter(status=status)

    total = await queryset.count()
    records = (
        await queryset.order_by("-status", "sort", "-created_at")
        .offset(page.offset)
        .limit(page.size)
        .values("id", "name", "status", "sort", "remark", "created_at", "updated_at")
    )
    usage_counts = await build_category_usage_counts([str(item["id"]) for item in records])

    for item in records:
        item["article_count"] = usage_counts.get(str(item["id"]), 0)

    return ResponseUtil.success(
        data={"records": records, "total": total, "current": page.current, "size": page.size}
    )


@articleCategoryAPI.get("/options", summary="Article category options")
async def article_category_options():
    rows = (
        await SystemArticleCategory.filter(is_del=False, status=1)
        .order_by("sort", "-created_at")
        .values("id", "name", "status", "sort")
    )
    return ResponseUtil.success(data=rows)


@articleCategoryAPI.get("/info/{category_id}", summary="Article category info")
async def article_category_info(category_id: str):
    rows = await SystemArticleCategory.filter(id=category_id, is_del=False).values()
    if not rows:
        return ResponseUtil.failure(msg="Article category does not exist")
    return ResponseUtil.success(data=rows[0])


@articleCategoryAPI.post("/add", summary="Add article category")
async def add_article_category(payload: ArticleCategoryCreate):
    if not await ensure_unique_category_name(payload.name):
        return ResponseUtil.failure(msg="Article category name already exists")

    created = await SystemArticleCategory.create(**payload.model_dump())
    return ResponseUtil.success(msg="Created successfully", data={"id": str(created.id)})


@articleCategoryAPI.put("/update/{category_id}", summary="Update article category")
async def update_article_category(category_id: str, payload: ArticleCategoryUpdate):
    rows = await SystemArticleCategory.filter(id=category_id, is_del=False).values()
    if not rows:
        return ResponseUtil.failure(msg="Article category does not exist")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return ResponseUtil.failure(msg="No fields to update")

    if "name" in data and not await ensure_unique_category_name(data["name"], exclude_id=category_id):
        return ResponseUtil.failure(msg="Article category name already exists")

    await SystemArticleCategory.filter(id=category_id, is_del=False).update(**data)

    if data.get("name"):
        await SystemArticle.filter(category_id=category_id, is_del=False).update(
            category_name=data["name"]
        )

    return ResponseUtil.success(msg="Updated successfully")


@articleCategoryAPI.delete("/delete/{category_id}", summary="Delete article category")
async def delete_article_category(category_id: str):
    exists = await SystemArticleCategory.filter(id=category_id, is_del=False).exists()
    if not exists:
        return ResponseUtil.failure(msg="Article category does not exist")

    usage_count = await SystemArticle.filter(category_id=category_id, is_del=False).count()
    if usage_count > 0:
        return ResponseUtil.failure(msg=f"Category is used by {usage_count} article(s)")

    await SystemArticleCategory.filter(id=category_id, is_del=False).update(is_del=True)
    return ResponseUtil.success(msg="Deleted successfully")


@articleTagAPI.get("/list", summary="Article tag list")
async def list_article_tags(
    name: str | None = Query(default=None),
    status: int | None = Query(default=None),
    page: PageParams = Depends(get_page_params),
):
    queryset = SystemArticleTag.filter(is_del=False)
    if name:
        queryset = queryset.filter(name__icontains=name)
    if status is not None:
        queryset = queryset.filter(status=status)

    total = await queryset.count()
    records = (
        await queryset.order_by("-status", "sort", "-created_at")
        .offset(page.offset)
        .limit(page.size)
        .values("id", "name", "color", "status", "sort", "remark", "created_at", "updated_at")
    )
    usage_counts = await build_tag_usage_counts([str(item["id"]) for item in records])

    for item in records:
        item["article_count"] = usage_counts.get(str(item["id"]), 0)

    return ResponseUtil.success(
        data={"records": records, "total": total, "current": page.current, "size": page.size}
    )


@articleTagAPI.get("/options", summary="Article tag options")
async def article_tag_options():
    rows = (
        await SystemArticleTag.filter(is_del=False, status=1)
        .order_by("sort", "-created_at")
        .values("id", "name", "color", "status", "sort")
    )
    return ResponseUtil.success(data=rows)


@articleTagAPI.get("/info/{tag_id}", summary="Article tag info")
async def article_tag_info(tag_id: str):
    rows = await SystemArticleTag.filter(id=tag_id, is_del=False).values()
    if not rows:
        return ResponseUtil.failure(msg="Article tag does not exist")
    return ResponseUtil.success(data=rows[0])


@articleTagAPI.post("/add", summary="Add article tag")
async def add_article_tag(payload: ArticleTagCreate):
    if not await ensure_unique_tag_name(payload.name):
        return ResponseUtil.failure(msg="Article tag name already exists")

    created = await SystemArticleTag.create(**payload.model_dump())
    return ResponseUtil.success(msg="Created successfully", data={"id": str(created.id)})


@articleTagAPI.put("/update/{tag_id}", summary="Update article tag")
async def update_article_tag(tag_id: str, payload: ArticleTagUpdate):
    rows = await SystemArticleTag.filter(id=tag_id, is_del=False).values()
    if not rows:
        return ResponseUtil.failure(msg="Article tag does not exist")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return ResponseUtil.failure(msg="No fields to update")

    if "name" in data and not await ensure_unique_tag_name(data["name"], exclude_id=tag_id):
        return ResponseUtil.failure(msg="Article tag name already exists")

    await SystemArticleTag.filter(id=tag_id, is_del=False).update(**data)

    if "name" in data:
        await sync_article_tag_names(target_tag_id=tag_id)

    return ResponseUtil.success(msg="Updated successfully")


@articleTagAPI.delete("/delete/{tag_id}", summary="Delete article tag")
async def delete_article_tag(tag_id: str):
    exists = await SystemArticleTag.filter(id=tag_id, is_del=False).exists()
    if not exists:
        return ResponseUtil.failure(msg="Article tag does not exist")

    usage_count = (await build_tag_usage_counts([tag_id])).get(tag_id, 0)
    if usage_count > 0:
        return ResponseUtil.failure(msg=f"Tag is used by {usage_count} article(s)")

    await SystemArticleTag.filter(id=tag_id, is_del=False).update(is_del=True)
    return ResponseUtil.success(msg="Deleted successfully")
